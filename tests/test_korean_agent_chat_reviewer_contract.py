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
    assert "launchPlanRef" in source
    assert 'if (!busy || launchPhase === "ready") return' in source
    assert "plan.scrollIntoView" in source
    assert 'block: "start"' in source
    assert 'prefers-reduced-motion: reduce' in source
    assert 'setLaunchPhase("brief")' in source
    assert 'setLaunchPhase("runtime")' in source
    assert 'setLaunchPhase("opening")' in source
    assert ".reviewer-launch-plan" in theme
    assert '.reviewer-launch-plan li[data-reviewer-launch-step-state="active"]' in theme
    assert ".reviewer-launch-plan__head" in theme


def test_reviewer_launch_failure_keeps_recovery_story_facing() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()

    assert "REVIEWER_LAUNCH_ERROR" in source
    assert "launchErrorRef" in source
    assert "The reviewer run did not open this time." in source
    assert "The locked seed is still here" in source
    assert "press Start curated run again" in source
    assert "use normal author flow" in source
    assert 'data-reviewer-launch-error="true"' in source
    assert 'role="status"' in source
    assert 'aria-live="polite"' in source
    assert "if (!error) return" in source
    assert "launchErrorRef.current" in source
    assert "panel.scrollIntoView" in source
    assert 'block: "center"' in source
    assert 'prefers-reduced-motion: reduce' in source
    assert "Could not launch" not in source
    assert "server" not in source.lower()
    assert "backend" not in source.lower()


def test_reviewer_launch_previews_runtime_evidence_proof_points() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    assert "keeps the player-facing story UI intact" in source
    assert "playable state and consequences" in source
    assert "Korean-webtoon visual language" not in source
    assert "REVIEWER_EVIDENCE_CHECKS" in source
    assert "After launch, verify" in source
    assert "Playable state" in source
    assert "State changed" in source
    assert "Checks boundary" in source
    assert "Live state is visible immediately" in source
    assert "archived judge checks appear only after they exist" in source
    assert "Archived checks" not in source
    assert 'data-reviewer-evidence-preview="true"' in source
    assert "data-reviewer-evidence-preview-item={item.label}" in source
    assert ".reviewer-evidence-preview" in theme
    assert ".reviewer-evidence-preview__head" in theme


def test_reviewer_launch_keeps_full_seed_secondary_to_proof_preview() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    summary_idx = source.index('data-reviewer-seed-summary="true"')
    actions_idx = source.index('className="reviewer-actions"')
    evidence_idx = source.index('data-reviewer-evidence-preview="true"')
    launch_idx = source.index('data-reviewer-launch-plan="true"')
    details_idx = source.index('data-reviewer-seed-details="true"')

    assert summary_idx < actions_idx < evidence_idx < launch_idx < details_idx
    assert "Locked seed preview" in source
    assert "Missing singer, live awards stream, sponsor pressure" in source
    assert "Read locked seed" in source
    assert "<details className=\"reviewer-seed-details\"" in source
    assert ".reviewer-seed-summary" in theme
    assert ".reviewer-seed-details summary" in theme


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
