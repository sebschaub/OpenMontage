import pytest
from runner import pipelines

def test_resolve_known_aliases():
    assert pipelines.resolve("reel").manifest == "animated-explainer"
    assert pipelines.resolve("reel").default_profile == "instagram_reels"
    assert pipelines.resolve("reel").renders_via_runner is True
    assert pipelines.resolve("avatar-spokesperson").renders_via_runner is False
    assert pipelines.resolve("animated-explainer").default_profile == "youtube_landscape"
    assert pipelines.resolve("localization-dub").manifest == "localization-dub"

def test_resolve_unknown_raises():
    with pytest.raises(ValueError):
        pipelines.resolve("nope")

def test_build_prompt_mentions_manifest_budget_and_stop_point():
    p = pipelines.build_prompt("reel", "/w/brief.json", "/w", "instagram_reels", 2.0)
    assert "animated-explainer" in p and "instagram_reels" in p
    assert "2.0" in p and "/w/brief.json" in p
    assert "edit_decisions" in p          # reel stops at edit_decisions (runner renders)
    p2 = pipelines.build_prompt("localization-dub", "/w/brief.json", "/w", "source", 2.0)
    assert "final.mp4" in p2               # dub runs through to final.mp4
