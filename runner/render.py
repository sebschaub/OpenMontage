import json, os
from dataclasses import dataclass, field

@dataclass
class RenderResult:
    ok: bool
    final_path: str | None = None
    asset_manifest: dict = field(default_factory=dict)
    error: str | None = None

def _load(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return None

def ensure_final(workspace, profile, video_compose_factory=None):
    if video_compose_factory is None:
        from tools.video.video_compose import VideoCompose
        video_compose_factory = VideoCompose
    final = os.path.join(workspace, "renders", "final.mp4")
    ed = os.path.join(workspace, "artifacts", "edit_decisions.json")
    am = os.path.join(workspace, "artifacts", "asset_manifest.json")
    manifest = _load(am) or {}

    if os.path.exists(final) and os.path.getsize(final) > 0:
        return RenderResult(True, final, manifest)

    edd, amd = _load(ed), _load(am)
    if edd is not None and amd is not None:
        os.makedirs(os.path.dirname(final), exist_ok=True)
        res = video_compose_factory().execute({
            "operation": "render", "edit_decisions": edd, "asset_manifest": amd,
            "output_path": final, "profile": profile,
        })
        if getattr(res, "success", False) and os.path.exists(final):
            return RenderResult(True, final, amd)
        return RenderResult(False, None, amd, error=getattr(res, "error", "render failed"))

    return RenderResult(False, None, manifest,
                        error="no final.mp4 and no edit_decisions/asset_manifest to render")
