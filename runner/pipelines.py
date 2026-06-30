from dataclasses import dataclass

@dataclass(frozen=True)
class Pipeline:
    manifest: str
    default_profile: str
    renders_via_runner: bool   # True => agent stops at edit_decisions; runner renders

PIPELINES = {
    "reel":                Pipeline("animated-explainer", "instagram_reels",  True),
    "animated-explainer":  Pipeline("animated-explainer", "youtube_landscape", True),
    "avatar-spokesperson": Pipeline("avatar-spokesperson", "instagram_reels", False),
    "localization-dub":    Pipeline("localization-dub",   "source",           False),
}

def resolve(alias: str) -> Pipeline:
    if alias not in PIPELINES:
        raise ValueError(f"unknown pipeline alias: {alias!r}")
    return PIPELINES[alias]

def build_prompt(alias, brief_path, workspace, profile, budget_cap):
    p = resolve(alias)
    stop = ("Stop after writing artifacts/edit_decisions.json and "
            "artifacts/asset_manifest.json — do NOT run the final render."
            if p.renders_via_runner else
            "Run the pipeline through to renders/final.mp4.")
    return (
        f"You are running the OpenMontage `{p.manifest}` pipeline headlessly.\n"
        f"Working directory for this job: {workspace}\n"
        f"Read the brief at {brief_path}.\n"
        f"Media profile: {profile}. Budget: cap at ${budget_cap} (mode budget:cap).\n"
        f"Checkpoint policy: auto_noncreative — never wait for human approval.\n"
        f"Write all artifacts and assets under {workspace}.\n"
        f"{stop}\n"
    )
