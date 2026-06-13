from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_play_route_mounts_direction_a_editorial_primitives() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()

    assert "from \"./components/play-editorial-primitives\"" in play_page
    for component in (
        "PlayShell",
        "MoodPlate",
        "PlaySurfaceGrid",
        "StoryTimeline",
        "SceneSupportRail",
    ):
        assert component in play_page
        assert f"function {component}" in primitives

    assert 'data-play-direction="editorial-primitive-kit"' in primitives
    assert 'data-play-primitive="MoodPlate"' in primitives
    assert 'data-play-primitive="StoryTimeline"' in primitives
    assert 'data-play-primitive="SceneSupportRail"' in primitives
    assert "<RunContextPanel" not in play_page


def test_play_primitives_keep_story_world_mental_model() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert "ActionArea" in play_page
    assert "AdvisorSidechat" in play_page
    assert "MoodPlate" in primitives
    assert "SceneSupportRail" in primitives
    assert "Narrator/World" in readme
    assert "Story Butler is not the primary Play speaker" in readme
    assert "Story Butler" not in primitives


def test_scene_support_rail_uses_webtoon_portrait_images() -> None:
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    assets = (ROOT / "frontend2/src/shared/lib/webtoon-assets.ts").read_text()
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()

    assert "getAvatarForCastMember" in primitives
    assert "getDefaultAvatar" in primitives
    assert 'data-play-player-portrait="true"' in primitives
    assert 'data-play-cast-portrait="true"' in primitives
    assert 'data-play-advisor-card="true"' in primitives
    assert 'data-play-advisor-ask="true"' in primitives
    assert 'data-play-advisor-portrait="true"' in primitives
    assert "advisorAvatarUrl={advisorAvatar}" in play_page
    assert "onAskAdvisor={openAdvisor}" in play_page
    assert "play.advisor_card_name" in primitives
    assert "play.advisor_card_background" in primitives
    assert "advisorRow" in primitives
    assert "advisorRowCompact" in primitives
    assert "advisorCard:" not in primitives
    assert "advisorHeaderRow" in primitives
    assert 'gridTemplateColumns: "44px minmax(0, 1fr)"' in primitives
    assert 'gridTemplateColumns: "minmax(0, 1fr) max-content"' in primitives
    assert 'width: "fit-content"' in primitives
    assert "maxWidth: 64" in primitives
    assert "advisorAskButtonCompact" in primitives
    assert "<img" in primitives
    assert "avatarUrl: getAvatarForCastMember" in primitives
    assert "getAvatarForCastMember(story.template.template_id, member, story.template)" in primitives
    assert "playerPortraitForStory" in primitives
    assert "handlePortraitError" in primitives
    assert "initialsFor" not in primitives
    assert "actor.initials" not in primitives
    assert "{actor.initials}" not in primitives
    assert "/webtoons/avatars/" in assets
    assert "export function getAvatarForCastMember" in assets


def test_direction_a_uses_local_primitives_not_other_ui_kit_paths() -> None:
    package_json = (ROOT / "frontend2/package.json").read_text()
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()

    assert "@heroui" not in package_json
    assert "@mantine" not in package_json
    assert "@heroui" not in play_page
    assert "@mantine" not in play_page
    assert "@heroui" not in primitives
    assert "@mantine" not in primitives
    assert "borderRadius: 999" not in primitives


def test_reviewer_evaluation_drawer_is_gated_and_uses_persisted_evidence() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    route_map = (ROOT / "frontend2/src/api/route-map.ts").read_text()
    client = (ROOT / "frontend2/src/api/client.ts").read_text()

    assert "canRequestAgentTrace" in play_page
    assert "api.getNarrativeLLMEvents(sessionId)" in play_page
    assert "llmEvents={llmEvents}" in play_page
    assert 'data-play-primitive="EvaluationDrawer"' in panels
    assert 'data-reviewer-evidence="true"' in panels
    assert "evaluationCriteria" in panels
    assert "trajectoryEvidence" in panels
    assert "NarrativeLLMCallEvent" in panels
    assert "getNarrativeLLMEvents" in client
    assert "/narrative/sessions/:session_id/llm-events" in route_map


def test_normal_play_keeps_evaluation_terms_outside_default_surface() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()

    assert "reviewerMode ? (" in play_page
    assert "<RuntimeInspector" in play_page
    assert "Evaluation evidence" in panels
    assert "data-reviewer-evidence" in panels
    assert "token" not in (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text().casefold()


def test_finish_mode_normal_play_reduces_top_metadata_density() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()

    mood_plate = primitives[primitives.index("export function MoodPlate") : primitives.index("export function SceneSupportRail")]
    scene_rail = primitives[primitives.index("export function SceneSupportRail") : primitives.index("function PrimitiveSection")]
    story_beat = panels[panels.index("export function StoryBeat") : panels.index("export function computeLiveInventory")]

    assert "cast={story.template.cast.map" not in play_page
    assert "const castLine" not in mood_plate
    assert "story.template.seed" not in mood_plate
    assert "First shot is live" in mood_plate
    assert '<PrimitiveSection title="Progress">' not in scene_rail
    assert ".slice(0, 3)" in primitives[primitives.index("function sceneActors") : primitives.index("function playerPortraitForStory")]
    assert "return items.slice(0, 3)" in panels
    assert "impactPulses.slice(0, 3).map" in story_beat
    assert "pulseImpactReason" not in story_beat


def test_play_turn_submission_has_parent_level_duplicate_guard() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    recovery = (ROOT / "frontend2/src/pages/play/components/play-retry-recovery.tsx").read_text()

    handle_advance = play_page[play_page.index("const handleAdvance") : play_page.index("const openAdvisor")]

    assert "const advanceInFlightRef = useRef(false)" in play_page
    assert "if (advanceInFlightRef.current || busy) return" in handle_advance
    assert "advanceInFlightRef.current = true" in handle_advance
    assert "advanceInFlightRef.current = false" in handle_advance
    assert "disabled={busy}" in recovery
    assert "errorInlineRetryDisabled" in recovery
    assert "keepRecoveryVisible" in play_page
    assert "lastFailedActionRef.current = null" in handle_advance
    assert "errorInlineRetryDisabled" in styles


def test_play_retry_failure_harness_is_dev_only_and_reuses_retry_guard() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()

    harness = play_page[play_page.index("function shouldUseLocalAdvanceFailureHarness") : play_page.index("export function PlayPage")]
    handle_advance = play_page[play_page.index("const handleAdvance") : play_page.index("const openAdvisor")]

    assert "import.meta.env.DEV" in harness
    assert 'get("playTurnFailure") === "once"' in harness
    assert "localAdvanceFailureHarnessRef" in play_page
    assert "throw new Error(t(\"play.error_advance\"))" in handle_advance
    assert "lastFailedActionRef.current = action" in handle_advance
    assert "if (advanceInFlightRef.current || busy) return" in handle_advance


def test_play_retry_fixture_route_is_local_only_and_reuses_player_safe_banner() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    recovery = (ROOT / "frontend2/src/pages/play/components/play-retry-recovery.tsx").read_text()

    assert "allowsLocalQaRoute" in routes
    assert 'segments[0] === "qa" && allowsLocalQaRoute()' in routes
    assert 'segments[1] === "play-retry"' in routes
    assert 'host === "localhost" || host === "127.0.0.1" || host === "::1"' in routes
    assert 'case "playRetryFixture"' in app
    assert "PlayRetryFailureFixture" in app
    assert 'data-play-retry-fixture="true"' in recovery
    assert 'data-play-retry-recovery="true"' in recovery
    assert "PlayRetryRecoveryBanner" in recovery
    assert "without advancing the story" in recovery
    for forbidden in ("provider", "model", "schema", "token", "fallback", "deterministic"):
        assert forbidden not in recovery.casefold()


def test_play_action_fixture_rehearses_normal_move_flow_without_live_calls() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    fixture = (ROOT / "frontend2/src/pages/play/components/play-action-state-fixture.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()

    assert 'segments[1] === "play-action"' in routes
    assert 'case "playActionFixture"' in app
    assert "PlayActionStateFixture" in app
    assert 'data-play-action-fixture="true"' in fixture
    assert "<ActionArea" in fixture
    assert "setBusy(true)" in fixture
    assert "setTurn((value) => value + 1)" in fixture
    assert "data-play-action-state={actionState}" in panels
    assert 'aria-live="polite"' in panels
    assert 'aria-atomic="true"' in panels
    assert "srOnly" in styles
    for forbidden in ("provider", "model", "schema", "token", "fallback", "deterministic"):
        assert forbidden not in fixture.casefold()


def test_gameplay_loop_fixture_proves_typed_state_loop_without_live_calls() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    fixture = (ROOT / "frontend2/src/pages/play/components/play-gameplay-loop-fixture.tsx").read_text()
    prd = (ROOT / "docs/play-gameplay-loop-prd.md").read_text()

    assert 'segments[1] === "play-gameplay-loop"' in routes
    assert '"#/qa/play-gameplay-loop"' in routes
    assert 'case "playGameplayLoopFixture"' in app
    assert "PlayGameplayLoopFixture" in app
    assert 'data-gameplay-loop-fixture="true"' in fixture
    assert 'data-gameplay-objective="true"' in fixture
    assert "data-gameplay-pressure-track={track.id}" in fixture
    assert 'data-gameplay-person-action="true"' in fixture
    assert 'data-gameplay-clue-card={unlockedClue ? "green-room-badge" : "locked"}' in fixture
    assert 'data-gameplay-forecast-chip={hook === "forecast" ? "true" : undefined}' in fixture
    assert 'data-gameplay-delta={hook === "delta" ? "true" : undefined}' in fixture
    assert 'data-gameplay-unlocked-action={unlockedClue ? "true" : undefined}' in fixture
    assert 'data-play-move-receipt="true"' in fixture
    assert 'data-play-room-reacting="true"' in fixture
    assert "setPhase(\"pending\")" in fixture
    assert "setPhase(\"resolved\")" in fixture
    assert "setUnlockedClue(true)" in fixture
    assert "unlockedClue ? UNLOCKED_ACTIONS : INITIAL_ACTIONS" in fixture
    assert "fetch(" not in fixture
    assert "episodeGoal" in prd
    assert "pressure" in prd
    assert "people" in prd
    assert "clues" in prd
    assert "typed game-state envelope" in prd
    assert "Fixture first" in prd or "fixture first" in prd
    for forbidden in ("provider", "model", "schema", "token", "fallback", "deterministic"):
        assert forbidden not in fixture.casefold()


def test_play_selected_action_expands_card_in_place_with_explicit_confirm() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    selected_confirm = panels[
        panels.index("const renderSelectedOptionConfirm") : panels.index("const renderSelectedOptionDetail")
    ]
    selected_confirm_styles = styles[
        styles.index("optionCardConfirmPanel") : styles.index("optionCardSecondaryRow")
    ]
    selected_button_styles = styles[
        styles.index("optionPrimaryCommitButton") : styles.index("optionQuietChangeButton")
    ]

    assert 'data-play-decision-tray="true"' not in panels
    assert 'data-play-action-card-expanded={isSelected ? "true" : undefined}' in panels
    assert 'data-play-action-card-detail="true"' in panels
    assert 'data-play-action-card-confirm="true"' in panels
    assert 'data-play-action-card-confirm-panel="true"' in panels
    assert 'data-play-action-option-card="true"' in panels
    assert 'data-play-action-collapse-zone="true"' in panels
    assert 'data-play-inner-motive-primary="true"' in panels
    assert 'data-play-inner-motive-panel={context === "option" ? "true" : undefined}' in panels
    assert "isWritingOptionDiary ? null : (" in selected_confirm
    assert 'data-play-selected-move={isSelected ? "true" : undefined}' in panels
    assert 'data-play-primary-commit="true"' in panels
    assert 'data-play-support-actions="true"' in panels
    assert 'data-play-move-receipt="true"' in panels
    assert 'data-play-room-reacting="true"' in panels
    assert 'data-play-pending-reaction-panel="true"' in panels
    assert "const showStandardOptions = !armedCard && !showFreeComposer && !showPickedReflection" in panels
    assert ".filter(({ i }) => focusedOptionIndex" not in panels
    assert "handleActionAreaPointerDownCapture" in panels
    assert "target.closest(" in panels
    assert 'setSelectedOptionIndex(i)' in panels
    assert 'setSelectedOptionIndex(null)' in panels
    assert "optionCardConfirmPanel" in styles
    assert "optionCardConfirmRail" in styles
    assert "optionCardPrimaryActionGrid" in styles
    assert 'gridTemplateColumns: "auto minmax(0, 1fr)"' not in selected_confirm_styles
    assert "borderRadius: 999" in selected_confirm_styles
    assert "minHeight: 40" in selected_button_styles
    assert "optionExpandedDetail" in styles
    assert "optionPrimaryCommitButton" in styles
    assert "optionMotiveCommitButton" in styles
    assert "diarySubmitButton" in styles
    assert "moveReceiptPanel" in styles
    assert "roomReactingPanel" in styles
    assert "reducedMotionTransition" in styles
    assert "export const actionPalette" in styles
    assert "selectedBorderLeft: \"rgba(213,154,62,0.72)\"" in styles
    assert "primaryBackground: \"linear-gradient(180deg, rgba(176,126,48,0.92), rgba(108,76,33,0.96))\"" in styles
    assert "ivoryText: \"rgba(246,239,222,0.96)\"" in styles
    assert "actionPalette.primaryPendingGlow" in panels
    assert "rgba(20,117,130,0.96)" not in styles
    assert "rgba(75,238,246,0.78)" not in styles
    assert "rgba(146,33,43,0.96)" not in styles
    assert "whileHover" in panels
    assert "whileTap" in panels
    assert "ask_friend_inline" not in panels
    assert "onOpenAdvisor" not in panels
    assert "ask_friend_inline" not in selected_confirm
    assert "onOpenAdvisor" not in selected_confirm
    assert "option_change_cta" not in selected_confirm
    assert "change choice" not in strings
    assert '"play.selected_move_kicker": "Selected move"' in strings
    assert '"play.selected_move_commit_cta": "Take this action"' in strings
    assert '"play.inner_motive_cta": "Use inner motive"' in strings
    assert '"play.inner_motive_submit_cta": "Take action with motive"' in strings
    assert '"play.advisor_card_name": "Dana Vale"' in strings
    assert '"play.move_receipt_title": "Your move"' in strings
    assert '"play.room_reacting_title": "The room is reacting"' in strings
    assert '"play.option_expand_cta": "View move"' in strings
    assert '"play.option_expanded_detail_label": "Consequence"' in strings


def test_play_retry_banner_separates_signal_label_from_body_for_accessibility() -> None:
    recovery = (ROOT / "frontend2/src/pages/play/components/play-retry-recovery.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()

    assert 'aria-live="assertive"' in recovery
    assert 'aria-atomic="true"' in recovery
    assert "const alertSummary" in recovery
    assert "aria-label={alertSummary}" in recovery
    assert "aria-label={`${signalLabel}: ${error}`}" in recovery
    assert "{signalLabel}:" in recovery
    assert '{" "}' in recovery
    assert "errorInlineSignalBody" in recovery
    assert "errorInlineSignalBody" in styles


def test_compact_play_has_jump_to_action_affordance_without_desktop_clutter() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    action_jump = (ROOT / "frontend2/src/pages/play/components/play-action-jump.tsx").read_text()
    action_jump_utils = (ROOT / "frontend2/src/pages/play/components/play-action-jump-utils.ts").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "const [showActionJump, setShowActionJump] = useState(false)" in play_page
    assert "!story || !compactPlayChrome || busy || advisorOpen || ending" in play_page
    assert "currentActionAreaVisible" in play_page
    assert "isPlayActionAreaAwayFromViewport(actionArea)" in play_page
    assert "<PlayActionJumpButton />" in play_page
    assert 'data-play-action-jump="true"' in action_jump
    assert "onPointerDown={onClick}" in action_jump
    assert "scrollToPlayActionArea" in action_jump_utils
    assert "[data-play-action-area='true']" in action_jump_utils
    assert "actionJumpButton" in styles
    assert 'position: "fixed"' in styles[styles.index("actionJumpButton") : styles.index("actionJumpKicker")]
    assert '"play.action_jump_label": "Continue your next move"' in strings


def test_play_long_history_fixture_exercises_action_jump_with_real_action_area() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    action_state = (ROOT / "frontend2/src/pages/play/components/play-action-state-fixture.tsx").read_text()
    fixture = (ROOT / "frontend2/src/pages/play/components/play-long-history-fixture.tsx").read_text()
    action_jump = (ROOT / "frontend2/src/pages/play/components/play-action-jump.tsx").read_text()
    action_jump_utils = (ROOT / "frontend2/src/pages/play/components/play-action-jump-utils.ts").read_text()

    assert 'segments[1] === "play-action"' in routes
    assert 'params.get("scenario") === "long-history"' in routes
    assert '"#/qa/play-action?scenario=long-history"' in routes
    assert 'case "playActionFixture"' in app
    assert "scenario={route.scenario}" in app
    assert 'case "playLongHistoryFixture"' not in app
    assert 'segments[1] === "play-long-history"' not in routes
    assert 'scenario === "long-history"' in action_state
    assert "PlayLongHistoryFixture" in action_state
    assert 'data-play-long-history-fixture="true"' in fixture
    assert "<ActionArea" in fixture
    assert "<PlayActionJumpButton" in fixture
    assert "scrollToPlayActionArea()" in fixture
    assert "isPlayActionAreaAwayFromViewport(actionArea)" in fixture
    assert 'data-play-action-jump="true"' in action_jump
    assert "window.scrollTo" in action_jump_utils
    for forbidden in ("provider", "model", "schema", "token", "fallback", "deterministic"):
        assert forbidden not in fixture.casefold()
