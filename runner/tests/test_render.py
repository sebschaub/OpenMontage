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
