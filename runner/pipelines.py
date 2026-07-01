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
    stop = (
        f"STOP after the edit stage: once {workspace}/artifacts/edit_decisions.json and "
        f"{workspace}/artifacts/asset_manifest.json exist and validate against their "
        "schemas, do NOT run the compose/render stage — the runner renders separately."
        if p.renders_via_runner else
        f"Run all stages through to {workspace}/renders/final.mp4."
    )
    return (
        "You are operating OpenMontage HEADLESLY to produce ONE video, unattended. "
        "There is no human to answer questions — make every decision yourself and proceed.\n\n"
        "FIRST read AGENT_GUIDE.md and obey its Rule Zero: ALL production goes through the "
        "pipeline system. Read the pipeline manifest, run preflight, then execute stage by "
        "stage — for EACH stage read its director skill "
        f"(skills/pipelines/{p.manifest}/<stage>-director.md) and any referenced Layer 3 "
        "skills BEFORE calling tools. Do NOT improvise ad-hoc scripts or asset formats; the "
        "intelligence is in the skills.\n\n"
        f"Pipeline manifest: pipeline_defs/{p.manifest}.yaml\n"
        f"Media profile: {profile}.\n"
        f"Budget: stay under ${budget_cap} (mode budget:cap). Prefer FREE stock B-roll "
        "(Pexels/Pixabay) over paid generation wherever it fits.\n"
        "Checkpoint policy: auto_noncreative — never pause for human approval; auto-approve "
        "every checkpoint and continue.\n\n"
        f"The production brief (title/body/angle) is at {brief_path}; use it as the source "
        "material for research and the script.\n\n"
        f"JOB WORKSPACE: {workspace}\n"
        f"  - Write ALL artifacts to {workspace}/artifacts/ and ALL downloaded/generated "
        f"assets to {workspace}/assets/.\n"
        "  - CRITICAL asset contract (renders fail otherwise): every "
        "edit_decisions.cuts[].source MUST be an asset id that exists in "
        "asset_manifest.json; every asset_manifest entry MUST have an absolute 'path' to a "
        "file that actually exists on disk. Do NOT put bare filenames, relative paths, or "
        "un-manifested ids in cuts[].source.\n\n"
        f"{stop}\n"
    )
