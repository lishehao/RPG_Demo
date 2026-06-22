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
    assert "Playable run" in source
    assert "Playable runtime" not in source
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


def test_reviewer_page_normalizes_direct_entry_to_english() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()

    mount_language_idx = source.index('useEffect(() => {\n    setLang("en")')
    handle_start_idx = source.index("const handleStart = async")

    assert mount_language_idx < handle_start_idx
    assert '}, [setLang])' in source[mount_language_idx:handle_start_idx]
    assert 'setLang("en")' in source[source.index("const handleStart = async") :]
    assert "A locked English demo path designed for portfolio review" in source


def test_portfolio_page_normalizes_application_entry_to_english() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()

    mount_language_idx = source.index('useEffect(() => {\n    setLang("en")')
    hero_idx = source.index("<h1>Tiny Stories")

    assert mount_language_idx < hero_idx
    assert '}, [setLang])' in source[mount_language_idx:hero_idx]
    assert 'import { useLanguage } from "../../shared/lib/i18n"' in source
    assert "Portfolio Case Study" in source
    assert "portfolio-grade AI product-system evidence" in source
    assert "not a launched consumer adoption claim" in source


def test_reviewer_launch_failure_keeps_recovery_story_facing() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    assert "REVIEWER_LAUNCH_ERROR" in source
    assert "REVIEWER_LAUNCH_RECOVERY" in source
    assert "launchErrorRef" in source
    assert "The reviewer run did not open this time." in source
    assert "The locked seed and evidence checklist are still here" in source
    assert "Retry the reviewer run" in source
    assert "review the Portfolio evidence page" in source
    assert "write your own story" in source
    assert "return to Story Desk" in source
    assert 'data-reviewer-launch-error="true"' in source
    assert 'data-reviewer-launch-error-actions="true"' in source
    assert 'data-reviewer-launch-error-retry="true"' in source
    assert 'data-reviewer-launch-error-portfolio="true"' in source
    assert 'data-reviewer-launch-error-create="true"' in source
    assert 'data-reviewer-launch-error-home="true"' in source
    assert "Retry reviewer run" in source
    assert "Review portfolio evidence" in source
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
    error_action_start = theme.index(".reviewer-error__action {")
    error_action_end = theme.index(".reviewer-error__action--primary", error_action_start)
    error_action_styles = theme[error_action_start:error_action_end]
    assert "min-height: 44px" in error_action_styles


def test_reviewer_launch_enters_reviewer_mode_play_evidence_path() -> None:
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()

    reviewer_case = app[app.index('case "reviewer":') : app.index('case "about":')]
    assert "ReviewerPage" in reviewer_case
    assert 'onOpenPortfolio={() => navigate({ name: "portfolio" })}' in reviewer_case
    assert 'onSessionStarted={(sessionId) => navigate({ name: "play", sessionId, reviewer: true })}' in reviewer_case

    play_build_hash = routes[routes.index('case "play":') : routes.index('case "replay":')]
    assert "route.reviewer" in play_build_hash
    assert '?reviewer=1' in play_build_hash

    play_parse_route = routes[routes.index('if (segments[0] === "play"') : routes.index('if (segments[0] === "replay"')]
    assert 'reviewer: params.get("reviewer") === "1"' in play_parse_route

    assert "const canRequestAgentTrace = reviewerMode && auth.canViewAgentTrace" in play_page
    assert 'data-reviewer-evidence-jump="true"' in play_page
    assert 'data-reviewer-evidence-jump-button="true"' in play_page
    assert "Story UI stays playable; evidence stays separate." in play_page
    assert "first consequence after a move" in play_page
    assert "View evidence summary" in play_page
    assert "reviewerMode ? (" in play_page
    assert "<RuntimeInspector" in play_page


def test_reviewer_launch_previews_runtime_evidence_points() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    hero_proof_idx = source.index('data-reviewer-hero-proof-strip="true"')
    seed_summary_idx = source.index('data-reviewer-seed-summary="true"')
    local_note_idx = source.index('data-reviewer-local-evidence-note="true"')
    actions_idx = source.index('className="reviewer-actions"')
    evidence_idx = source.index('data-reviewer-evidence-preview="true"')
    launch_idx = source.index('data-reviewer-launch-plan="true"')

    assert local_note_idx < actions_idx < hero_proof_idx < evidence_idx < seed_summary_idx < launch_idx
    assert "REVIEWER_HERO_PROOF_POINTS" in source
    assert "Real run" in source
    assert "Launch creates a playable session from the locked seed, not a static mockup." in source
    assert "One-move consequence" in source
    assert "Take one move and inspect how the room, assets, and next choices change." in source
    assert "Evidence boundary" in source
    assert "Reviewer evidence stays beside Play and should be cited only after preflight." in source
    assert "data-reviewer-hero-proof-item={item.label}" in source
    assert local_note_idx < actions_idx < hero_proof_idx < evidence_idx < launch_idx
    assert "Public evidence boundary: inspect the current local build here" in source
    assert "application links, cite this route only after Portfolio preflight" in source
    assert "keeps the player-facing story UI intact" in source
    assert "playable state and the first" in source
    assert "consequence after a move" in source
    assert 'aria-label="Reviewer evidence path"' in source
    assert "Reviewer proof path" not in source
    assert "playable state and consequences" not in source
    assert "Korean-webtoon visual language" not in source
    assert "Start reviewer run" in source
    assert "Write your own story" in source
    assert "Start curated run" not in source
    assert "Use normal author flow" not in source
    assert "REVIEWER_EVIDENCE_CHECKS" in source
    assert "After launch, verify" in source
    assert "4 evidence checks" in source
    assert "Playable state" in source
    assert "Consequence after one move" in source
    assert "Play one move, then verify character reactions and story-item consequences" in source
    assert "Evidence limits" in source
    assert "The opening shows playable setup; consequence evidence waits until the run produces it" in source
    assert "Replay artifact" in source
    assert "A completed run should become highlights, Full read, and same-opening restart evidence." in source
    assert "Live state is visible immediately" not in source
    assert "State changed" not in source
    assert "relationship pulse and inventory consequences" not in source
    assert "Archived checks" not in source
    assert 'data-reviewer-evidence-preview="true"' in source
    assert "data-reviewer-evidence-preview-item={item.label}" in source
    assert ".reviewer-hero-proof" in theme
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in theme
    assert ".reviewer-evidence-preview" in theme
    assert ".reviewer-evidence-preview__head" in theme
    assert "grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))" in theme
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in theme
    reviewer_local_link_start = theme.index(".reviewer-local-evidence-link")
    reviewer_local_link_end = theme.index(".reviewer-local-evidence-link:hover", reviewer_local_link_start)
    reviewer_local_link_styles = theme[reviewer_local_link_start:reviewer_local_link_end]
    assert "min-height: 44px" in reviewer_local_link_styles
    assert "align-items: center" in reviewer_local_link_styles


def test_reviewer_launch_keeps_full_seed_secondary_to_proof_preview() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    summary_idx = source.index('data-reviewer-seed-summary="true"')
    local_note_idx = source.index('data-reviewer-local-evidence-note="true"')
    actions_idx = source.index('className="reviewer-actions"')
    proof_idx = source.index('data-reviewer-hero-proof-strip="true"')
    evidence_idx = source.index('data-reviewer-evidence-preview="true"')
    launch_idx = source.index('data-reviewer-launch-plan="true"')
    details_idx = source.index('data-reviewer-seed-details="true"')

    assert local_note_idx < actions_idx < proof_idx < evidence_idx < summary_idx < launch_idx < details_idx
    assert "Locked seed preview" in source
    assert "Missing singer, live awards stream, sponsor pressure" in source
    assert "Read locked seed" in source
    assert "<details className=\"reviewer-seed-details\"" in source
    assert ".reviewer-seed-summary" in theme
    assert ".reviewer-seed-details summary" in theme


def test_portfolio_hero_surfaces_public_evidence_gate_before_proofbar() -> None:
    source = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    actions_idx = source.index('className="portfolio-hero__actions"')
    gate_idx = source.index('data-portfolio-public-evidence-gate="true"')
    review_order_idx = source.index('data-portfolio-review-order="true"')
    proofbar_idx = source.index('className="portfolio-proofbar"')
    source_evidence_idx = source.index('data-portfolio-source-evidence="true"')

    assert actions_idx < gate_idx < review_order_idx < proofbar_idx < source_evidence_idx
    assert "PORTFOLIO_PUBLIC_EVIDENCE_GATE" in source
    assert 'data-portfolio-public-evidence-gate-summary="true"' in source
    assert 'data-portfolio-public-evidence-gate-details="true"' in source
    assert "Public repo and Pages links can lag this local build" in source
    assert "How to verify public links" in source
    assert "python3 tools/portfolio_public_evidence_preflight.py" in source
    assert "do not cite the current Portfolio, Reviewer path, Story Desk, Create, Play, or Replay" in source
    assert "until the intended branch is pushed, deployed, rechecked, and the preflight passes" in source
    assert "Verify replay artifact" in source
    assert "Local build only: inspect a completed memory" in source
    assert 'localHref: "#/qa/replay"' in source
    assert "public reviewers will not see" not in source
    assert ".portfolio-public-evidence-gate" in theme
    assert ".portfolio-public-evidence-gate details" in theme
    gate_summary_start = theme.index(".portfolio-public-evidence-gate summary")
    gate_summary_end = theme.index(".portfolio-public-evidence-gate details p", gate_summary_start)
    gate_summary_styles = theme[gate_summary_start:gate_summary_end]
    assert "min-height: 44px" in gate_summary_styles
    review_order_link_start = theme.index(".portfolio-review-order a {")
    review_order_link_end = theme.index(".portfolio-review-order a:hover", review_order_link_start)
    review_order_link_styles = theme[review_order_link_start:review_order_link_end]
    assert "min-height: 44px" in review_order_link_styles
    assert "align-items: center" in review_order_link_styles


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
