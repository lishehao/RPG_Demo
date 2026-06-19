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


def test_reviewer_launch_explains_async_progress_to_external_reviewers() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    assert "REVIEWER_LAUNCH_STEPS" in source
    assert "Reviewer session" in source
    assert "Story brief" in source
    assert "Playable runtime" in source
    assert "Evidence mode" in source
    assert 'data-reviewer-launch-plan="true"' in source
    assert 'data-reviewer-launch-state={busy ? launchPhase : "ready"}' in source
    assert 'data-reviewer-launch-step={step.phase}' in source
    assert 'data-reviewer-launch-step-state={state}' in source
    assert 'data-reviewer-launch-cta={busy ? "starting" : "ready"}' in source
    assert 'setLaunchPhase("brief")' in source
    assert 'setLaunchPhase("runtime")' in source
    assert 'setLaunchPhase("opening")' in source
    assert ".reviewer-launch-plan" in theme
    assert '.reviewer-launch-plan li[data-reviewer-launch-step-state="active"]' in theme
    assert ".reviewer-launch-plan__head" in theme


def test_reviewer_seed_is_concrete_enough_to_avoid_generic_scaffold_roles() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()
    service = (ROOT / "rpg_backend/narrative/service.py").read_text()

    for expected in (
        "Mira the anxious publicist",
        "Producer Han",
        "Rina the backup dancer witness",
        "Eun Sol the fan-channel reporter",
        "Choi the sponsor director",
        "singer Seo Mina disappears",
    ):
        assert expected in source

    forbidden_seed_fragments = ("player", "rival", "deadline holder", "Room mediator")
    seed_source = source[source.index("REVIEWER_DEMO_SEED") : source.index("export const REVIEWER_DEMO_ACTIONS")]
    for forbidden in forbidden_seed_fragments:
        assert forbidden not in seed_source

    assert "Publicist under pressure" in service
    assert "Witness handler" in service
    assert "Sponsor-room liaison" in service


def test_brief_card_surfaces_object_constraints_before_collapsed_details() -> None:
    source = (ROOT / "frontend2/src/pages/create/components/create-flow-panels.tsx").read_text()

    visible_constraints_idx = source.index("surfacedConstraints.length")
    collapsed_details_idx = source.index("<details style={cpStyles.briefDetails}>")

    assert visible_constraints_idx < collapsed_details_idx
    assert 'label={t("create.brief_key_details")}' in source
