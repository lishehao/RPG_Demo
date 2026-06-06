from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_reviewer_launch_uses_story_brief_backed_template_path() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()

    brief_idx = source.index("createNarrativeStoryBrief")
    template_idx = source.index("createNarrativeTemplate")

    assert brief_idx < template_idx
    assert 'desired_tension_profile: "high_drama"' in source
    assert "story_brief: briefResponse.brief" in source
    assert "AI service isn't configured" not in source
    assert "site maintainer" not in source


def test_brief_card_surfaces_object_constraints_before_collapsed_details() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()

    visible_constraints_idx = source.index("surfacedConstraints.length")
    collapsed_details_idx = source.index("<details style={cpStyles.briefDetails}>")

    assert visible_constraints_idx < collapsed_details_idx
    assert 'label={t("create.brief_key_details")}' in source
