import json, os, re, subprocess
from dataclasses import dataclass, field

@dataclass
class RenderResult:
    ok: bool
    final_path: str | None = None
    asset_manifest: dict = field(default_factory=dict)
    error: str | None = None

SILENCE_DB = -80.0

def _load(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return None

def _mean_volume_db(path):
    """Mean volume in dB via ffmpeg volumedetect, or None if it can't be measured."""
    try:
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=120)
        m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", p.stderr)
        return float(m.group(1)) if m else None
    except Exception:
        return None

def _ffmpeg_concat_narration(parts, out_path):
    """parts = [(path, start_seconds), ...]; mix each at its offset into out_path.
    Non-overlapping segments -> a single continuous narration track (gaps become silence)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    inputs, filters, labels = [], [], []
    for i, (path, start) in enumerate(parts):
        inputs += ["-i", path]
        ms = int(round(float(start or 0) * 1000))
        filters.append(f"[{i}]adelay={ms}:all=1[a{i}]")
        labels.append(f"[a{i}]")
    fc = ";".join(filters) + ";" + "".join(labels) + \
        f"amix=inputs={len(parts)}:normalize=0:dropout_transition=0[out]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
                    "-filter_complex", fc, "-map", "[out]", out_path],
                   check=True, timeout=300)

def _prepare_audio(workspace, ed, am, concat_fn=None):
    """The explainer pipeline emits multi-segment narration, but the Remotion
    composition plays a single narration.src. Concatenate the segments (at their
    start_seconds) into one 'narration-full' track and rewrite the audio block to
    reference it. Single-segment narration is left untouched."""
    concat_fn = concat_fn or _ffmpeg_concat_narration
    segs = (((ed.get("audio") or {}).get("narration") or {}).get("segments")) or []
    if len(segs) <= 1:
        return ed, am
    lookup = {a["id"]: a for a in am.get("assets", [])}
    parts = []
    for s in segs:
        a = lookup.get(s.get("asset_id"))
        if not (a and a.get("path")):
            return ed, am  # unresolvable segment -> let the asset gate report it
        parts.append((a["path"], s.get("start_seconds", 0)))
    ed = json.loads(json.dumps(ed)); am = json.loads(json.dumps(am))
    out_path = os.path.join(workspace, "assets", "audio", "narration_full.mp3")
    concat_fn(parts, out_path)
    am["assets"].append({"id": "narration-full", "type": "narration", "path": out_path})
    ed["audio"]["narration"]["segments"] = [{"asset_id": "narration-full", "start_seconds": 0}]
    return ed, am

def ensure_final(workspace, profile, video_compose_factory=None, volume_check=None):
    if video_compose_factory is None:
        from tools.video.video_compose import VideoCompose
        video_compose_factory = VideoCompose
    if volume_check is None:
        volume_check = _mean_volume_db
    final = os.path.join(workspace, "renders", "final.mp4")
    ed = os.path.join(workspace, "artifacts", "edit_decisions.json")
    am = os.path.join(workspace, "artifacts", "asset_manifest.json")
    manifest = _load(am) or {}

    def _finalize(path, mani):
        mv = volume_check(path)
        if mv is not None and mv <= SILENCE_DB:
            return RenderResult(False, None, mani,
                                error=f"rendered video is SILENT (mean_volume {mv} dB) — audio block unresolved")
        return RenderResult(True, path, mani)

    if os.path.exists(final) and os.path.getsize(final) > 0:
        return _finalize(final, manifest)

    edd, amd = _load(ed), _load(am)
    if edd is not None and amd is not None:
        edd, amd = _prepare_audio(workspace, edd, amd)   # concat multi-segment narration
        os.makedirs(os.path.dirname(final), exist_ok=True)
        res = video_compose_factory().execute({
            "operation": "render", "edit_decisions": edd, "asset_manifest": amd,
            "output_path": final, "profile": profile,
        })
        if getattr(res, "success", False) and os.path.exists(final):
            return _finalize(final, amd)
        return RenderResult(False, None, amd, error=getattr(res, "error", "render failed"))

    return RenderResult(False, None, manifest,
                        error="no final.mp4 and no edit_decisions/asset_manifest to render")
