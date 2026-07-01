import json, os
from runner import render

_AUDIBLE = lambda p: -20.0   # injected volume checker: pretend audio is fine

def _mk(ws, *, final=False, artifacts=False):
    os.makedirs(os.path.join(ws, "renders"), exist_ok=True)
    os.makedirs(os.path.join(ws, "artifacts"), exist_ok=True)
    if final:
        open(os.path.join(ws, "renders", "final.mp4"), "wb").write(b"\x00" * 10)
    if artifacts:
        json.dump({"cuts": []}, open(os.path.join(ws, "artifacts", "edit_decisions.json"), "w"))
        json.dump({"assets": [{"cost_usd": 0.1}]},
                  open(os.path.join(ws, "artifacts", "asset_manifest.json"), "w"))

def test_uses_existing_final(tmp_path):
    ws = str(tmp_path); _mk(ws, final=True)
    res = render.ensure_final(ws, "instagram_reels", video_compose_factory=lambda: 1/0, volume_check=_AUDIBLE)
    assert res.ok and res.final_path.endswith("renders/final.mp4")

def test_renders_from_artifacts_when_no_final(tmp_path):
    ws = str(tmp_path); _mk(ws, artifacts=True)
    class FakeVC:
        def execute(self, inputs):
            open(inputs["output_path"], "wb").write(b"\x00" * 10)
            class TR: success = True; error = None
            return TR()
    res = render.ensure_final(ws, "instagram_reels", video_compose_factory=FakeVC, volume_check=_AUDIBLE)
    assert res.ok and res.asset_manifest["assets"][0]["cost_usd"] == 0.1

def test_fails_when_nothing(tmp_path):
    res = render.ensure_final(str(tmp_path), "instagram_reels", video_compose_factory=lambda: 1/0, volume_check=_AUDIBLE)
    assert res.ok is False and res.error

def test_silent_render_is_rejected(tmp_path):
    # A rendered file that measures as silence must FAIL (never ship a silent reel).
    ws = str(tmp_path); _mk(ws, final=True)
    res = render.ensure_final(ws, "instagram_reels", video_compose_factory=lambda: 1/0,
                              volume_check=lambda p: -91.0)
    assert res.ok is False and "silent" in (res.error or "").lower()

def test_unmeasurable_audio_passes(tmp_path):
    # If volume can't be measured (None), don't block the render on it.
    ws = str(tmp_path); _mk(ws, final=True)
    res = render.ensure_final(ws, "instagram_reels", video_compose_factory=lambda: 1/0,
                              volume_check=lambda p: None)
    assert res.ok is True

def test_prepare_audio_concatenates_multi_segment_narration(tmp_path):
    calls = {}
    def fake_concat(parts, out_path):
        calls["parts"] = parts; calls["out"] = out_path
    ed = {"audio": {"narration": {"segments": [
            {"asset_id": "narration-s1", "start_seconds": 0},
            {"asset_id": "narration-s2", "start_seconds": 5.2}]},
          "music": {"asset_id": "music-bg"}}}
    am = {"assets": [
            {"id": "narration-s1", "type": "narration", "path": "/a/s1.mp3"},
            {"id": "narration-s2", "type": "narration", "path": "/a/s2.mp3"},
            {"id": "music-bg", "type": "music", "path": "/a/m.mp3"}]}
    ed2, am2 = render._prepare_audio(str(tmp_path), ed, am, concat_fn=fake_concat)
    assert calls["parts"] == [("/a/s1.mp3", 0), ("/a/s2.mp3", 5.2)]   # ordered, with offsets
    assert calls["out"].endswith("assets/audio/narration_full.mp3")
    assert ed2["audio"]["narration"]["segments"] == [{"asset_id": "narration-full", "start_seconds": 0}]
    assert any(a["id"] == "narration-full" for a in am2["assets"])

def test_prepare_audio_leaves_single_segment(tmp_path):
    ed = {"audio": {"narration": {"segments": [{"asset_id": "narration-full", "start_seconds": 0}]}}}
    am = {"assets": [{"id": "narration-full", "type": "narration", "path": "/a/n.mp3"}]}
    ed2, am2 = render._prepare_audio(str(tmp_path), ed, am, concat_fn=lambda *a: 1/0)
    assert ed2 is ed and am2 is am   # untouched, concat never called
