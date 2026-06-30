"""Tests for the Remotion render fix: audio-block transform, public-dir asset
staging, and the pre-render asset-resolution gate. (Plan 2 Tasks 3-5.)"""
import json
from pathlib import Path

import pytest

from tools.video.video_compose import VideoCompose


# ---------------------------------------------------------------------------
# Task 5: _resolve_audio_block — edit_decisions audio (asset_ids) -> composition
# audio (src paths + camelCase fade fields the Explainer <Audio> reads).
# ---------------------------------------------------------------------------

def test_resolve_audio_block_narration_segment_to_src():
    vc = VideoCompose()
    lookup = {"narration-full": {"id": "narration-full",
                                 "path": "/abs/audio/narration_full.mp3",
                                 "type": "narration"}}
    audio = {"narration": {"segments": [
        {"asset_id": "narration-full", "start_seconds": 0.0, "end_seconds": 39.4}]}}
    out = vc._resolve_audio_block(audio, lookup)
    assert out["narration"]["src"] == "/abs/audio/narration_full.mp3"


def test_resolve_audio_block_music_to_src_with_camelcase_fades():
    vc = VideoCompose()
    lookup = {"music-bg": {"id": "music-bg", "path": "/abs/music/bg.mp3",
                           "type": "music"}}
    audio = {"music": {"asset_id": "music-bg", "volume": 0.12,
                       "fade_in_seconds": 1.0, "fade_out_seconds": 2.5}}
    out = vc._resolve_audio_block(audio, lookup)
    assert out["music"]["src"] == "/abs/music/bg.mp3"
    assert out["music"]["volume"] == 0.12
    assert out["music"]["fadeInSeconds"] == 1.0
    assert out["music"]["fadeOutSeconds"] == 2.5


def test_resolve_audio_block_leaves_unresolvable_ids_without_src():
    vc = VideoCompose()
    audio = {"music": {"asset_id": "missing", "volume": 0.1}}
    out = vc._resolve_audio_block(audio, {})
    # Unknown id -> no src field (the asset gate will reject the render).
    assert "src" not in out.get("music", {})


# ---------------------------------------------------------------------------
# Task 3: _remotion_render stages every referenced asset (cuts + audio) under a
# --public-dir with public-relative paths (OffthreadVideo/Audio reject file://),
# and uses the 1800s timeout (a full reel takes >600s on a 4-vCPU box).
# ---------------------------------------------------------------------------

def _touch(p: Path, data: bytes = b"\x00\x00") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def _run_remotion_capture(vc, ed, out_path):
    """Invoke _remotion_render with run_command mocked; return captured cmd/props/timeout."""
    captured: dict = {}

    def fake_run(cmd, timeout=None, cwd=None, **kw):
        cmd = [str(c) for c in cmd]
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        pp = next(c.split("=", 1)[1] for c in cmd if c.startswith("--props="))
        captured["props"] = json.loads(Path(pp).read_text())

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    vc.run_command = fake_run
    vc._remotion_render(
        {"edit_decisions": ed, "output_path": str(out_path), "profile": "instagram_reels"}
    )
    return captured


def _is_relative(s: str) -> bool:
    return bool(s) and not s.startswith(("/", "file://", "http://", "https://")) and "://" not in s


def test_remotion_render_stages_cuts_and_audio_under_public_dir(tmp_path):
    vc = VideoCompose()
    v1 = _touch(tmp_path / "assets" / "video" / "s1.mp4")
    nar = _touch(tmp_path / "assets" / "audio" / "narration_full.mp3")
    mus = _touch(tmp_path / "assets" / "music" / "bg.mp3")
    ed = {
        "render_runtime": "remotion",
        "renderer_family": "explainer-data",
        "cuts": [{"id": "c1", "source": str(v1)}],
        "audio": {"narration": {"src": str(nar)},
                  "music": {"src": str(mus), "volume": 0.12}},
    }
    cap = _run_remotion_capture(vc, ed, tmp_path / "renders" / "final.mp4")

    cmd = cap["cmd"]
    pub = [c.split("=", 1)[1] for c in cmd if c.startswith("--public-dir=")]
    assert pub, "render command must pass --public-dir"
    pubdir = Path(pub[0])

    props = cap["props"]
    src0 = props["cuts"][0]["source"]
    assert _is_relative(src0), f"cut source must be public-relative, got {src0!r}"
    assert (pubdir / src0).exists(), "cut asset must be staged into the public dir"
    # Must be a REAL file, not a symlink: Remotion copies --public-dir into its
    # webpack bundle and does not follow symlinks (404 at frame 0 otherwise).
    assert not (pubdir / src0).is_symlink(), "staged asset must be a real file, not a symlink"
    assert (pubdir / src0).is_file()

    nsrc = props["audio"]["narration"]["src"]
    assert _is_relative(nsrc) and (pubdir / nsrc).exists(), "narration must be staged"
    msrc = props["audio"]["music"]["src"]
    assert _is_relative(msrc) and (pubdir / msrc).exists(), "music must be staged"


def test_remotion_render_uses_1800s_timeout(tmp_path):
    vc = VideoCompose()
    v1 = _touch(tmp_path / "assets" / "video" / "s1.mp4")
    ed = {
        "render_runtime": "remotion",
        "renderer_family": "explainer-data",
        "cuts": [{"id": "c1", "source": str(v1)}],
    }
    cap = _run_remotion_capture(vc, ed, tmp_path / "renders" / "final.mp4")
    assert cap["timeout"] == 1800


# ---------------------------------------------------------------------------
# Task 5 (wiring): execute(operation="render") must run the audio block through
# _resolve_audio_block so the props carry staged narration/music src paths.
# ---------------------------------------------------------------------------

def test_execute_render_resolves_audio_block_into_props(tmp_path):
    vc = VideoCompose()
    v1 = _touch(tmp_path / "assets" / "video" / "s1.mp4")
    nar = _touch(tmp_path / "assets" / "audio" / "narration_full.mp3")
    mus = _touch(tmp_path / "assets" / "music" / "bg.mp3")
    captured: dict = {}

    def fake_run(cmd, timeout=None, cwd=None, **kw):
        cmd = [str(c) for c in cmd]
        captured["props"] = json.loads(
            Path(next(c.split("=", 1)[1] for c in cmd if c.startswith("--props="))).read_text()
        )
        captured["pubdir"] = Path(
            next(c.split("=", 1)[1] for c in cmd if c.startswith("--public-dir="))
        )

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    vc.run_command = fake_run
    ed = {
        "render_runtime": "remotion",
        "renderer_family": "explainer-data",
        "cuts": [{"id": "c1", "source": "vid-s1", "out_seconds": 3.0}],
        "audio": {
            "narration": {"segments": [{"asset_id": "narration-full", "start_seconds": 0.0}]},
            "music": {"asset_id": "music-bg", "volume": 0.12,
                      "fade_in_seconds": 1.0, "fade_out_seconds": 2.5},
        },
    }
    am = {"version": "1.0", "assets": [
        {"id": "vid-s1", "type": "video", "path": str(v1)},
        {"id": "narration-full", "type": "narration", "path": str(nar)},
        {"id": "music-bg", "type": "music", "path": str(mus)},
    ]}
    vc.execute({"operation": "render", "edit_decisions": ed, "asset_manifest": am,
                "output_path": str(tmp_path / "renders" / "final.mp4"),
                "profile": "instagram_reels"})

    assert "props" in captured, "render did not reach Remotion (blocked upstream?)"
    props, pub = captured["props"], captured["pubdir"]
    nsrc = props["audio"]["narration"].get("src")
    assert nsrc and _is_relative(nsrc) and (pub / nsrc).exists(), "narration not resolved+staged"
    msrc = props["audio"]["music"].get("src")
    assert msrc and _is_relative(msrc) and (pub / msrc).exists(), "music not resolved+staged"
    assert props["audio"]["music"].get("fadeInSeconds") == 1.0


# ---------------------------------------------------------------------------
# Task 4: fail fast when a cut.source can't be resolved to a real file, instead
# of 404-ing deep inside Remotion after minutes of rendering (the cta-card bug).
# ---------------------------------------------------------------------------

def test_execute_render_rejects_unresolvable_cut_source(tmp_path):
    vc = VideoCompose()
    called = {"n": 0}
    vc.run_command = lambda *a, **k: called.__setitem__("n", called["n"] + 1)
    ed = {
        "render_runtime": "remotion",
        "renderer_family": "explainer-data",
        "cuts": [{"id": "c9", "source": "cta-card"}],  # not in manifest, no file
    }
    am = {"version": "1.0", "assets": []}
    res = vc.execute({"operation": "render", "edit_decisions": ed, "asset_manifest": am,
                      "output_path": str(tmp_path / "o.mp4"), "profile": "instagram_reels"})
    assert res.success is False
    assert "cta-card" in (res.error or ""), f"error must name the bad source, got: {res.error!r}"
    assert called["n"] == 0, "must fail BEFORE invoking the renderer"
