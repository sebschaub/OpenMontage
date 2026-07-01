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
        # Never accept a silent render — a reel with no narration is not shippable,
        # and silence signals an unresolved audio block.
        mv = volume_check(path)
        if mv is not None and mv <= SILENCE_DB:
            return RenderResult(False, None, mani,
                                error=f"rendered video is SILENT (mean_volume {mv} dB) — audio block unresolved")
        return RenderResult(True, path, mani)

    if os.path.exists(final) and os.path.getsize(final) > 0:
        return _finalize(final, manifest)

    edd, amd = _load(ed), _load(am)
    if edd is not None and amd is not None:
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
