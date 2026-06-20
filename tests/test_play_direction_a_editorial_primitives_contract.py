from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_play_route_mounts_direction_a_editorial_primitives() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    story_beat = (ROOT / "frontend2/src/pages/play/components/story-beat.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

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
    assert 'data-play-mood-state={isComplete ? "complete" : "active"}' in primitives
    assert 'data-play-primitive="StoryTimeline"' in primitives
    assert 'data-play-primitive="SceneSupportRail"' in primitives
    assert 'data-play-story-beat="true"' in story_beat
    assert 'data-play-story-beat-role="narrator"' in story_beat
    assert 'data-play-story-beat-role="player"' in story_beat
    assert 'data-play-story-beat-stack="true"' in play_page
    assert "function CurrentScenePreview" in play_page
    assert 'data-play-current-scene-preview="true"' in play_page
    assert 'data-play-current-scene-next-cue="true"' in play_page
    assert "cleanNarrativeDisplayText(message.content)" in play_page
    assert '"play.current_scene_label": "Current scene"' in strings
    assert '"play.current_scene_next_cue": "Then use the choices below to answer this moment."' in strings
    assert '"play.current_scene_next_cue": "再用下方选择回应这一刻。"' in strings
    assert "currentScenePreviewNextCue" in styles
    story_timeline_block = play_page[play_page.index("<StoryTimeline innerRef={scrollerRef}>"):]
    assert "<RunContextPanel" in story_timeline_block
    assert story_timeline_block.index("<RunContextPanel") < story_timeline_block.index("<GameplayStatePanel")


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


def test_advisor_panel_module_owns_fab_sidechat_and_player_hooks() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    advisor_panel = (ROOT / "frontend2/src/pages/play/components/advisor-panel.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./components/advisor-panel"' in play_page
    assert "AdvisorFab" in play_page
    assert "AdvisorSidechat" in play_page
    assert "buildAdvisorSuggestions" in play_page
    assert "export function AdvisorFab" in advisor_panel
    assert "export function AdvisorSidechat" in advisor_panel
    assert "export function buildAdvisorSuggestions" in advisor_panel
    assert "export type AdvisorSidechatApiClient" in advisor_panel
    assert "apiClient?: AdvisorSidechatApiClient" in advisor_panel
    assert "const defaultApi = useApi()" in advisor_panel
    assert "const api = apiClient ?? defaultApi" in advisor_panel
    assert "getNarrativeAdvisorHistory" in advisor_panel
    assert "askNarrativeAdvisor" in advisor_panel
    assert 'data-play-advisor-empty-primer="true"' in advisor_panel
    assert 'data-play-advisor-draft-hint="true"' in advisor_panel
    assert 'data-play-advisor-suggestion-instruction="true"' in advisor_panel
    assert "const [draftSuggestion, setDraftSuggestion] = useState<string | null>(null)" in advisor_panel
    assert "setDraftSuggestion(suggestion)" in advisor_panel
    assert "export function AdvisorFab" not in panels
    assert "export function AdvisorSidechat" not in panels
    assert "export function buildAdvisorSuggestions" not in panels
    assert "NarrativeAdvisorMessage" not in panels
    assert 'data-play-advisor-empty-primer="true"' not in panels
    assert 'data-play-advisor-draft-hint="true"' not in panels
    assert 'data-play-advisor-suggestion-instruction="true"' not in panels
    assert "components/advisor-panel.tsx" in readme


def test_story_beat_module_owns_receipts_digest_and_player_hooks() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    story_beat = (ROOT / "frontend2/src/pages/play/components/story-beat.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./components/story-beat"' in play_page
    assert "StoryBeat" in play_page
    assert "computeBeatIntensity" in play_page
    assert "export function StoryBeat" in story_beat
    assert "export function computeBeatIntensity" in story_beat
    assert 'data-play-story-beat="true"' in story_beat
    assert 'data-play-story-beat-role="narrator"' in story_beat
    assert 'data-play-story-beat-role="player"' in story_beat
    assert 'data-play-outcome-receipt="true"' in story_beat
    assert 'data-play-latest-beat-digest="true"' in story_beat
    assert 'data-play-segment-parallax="true"' in story_beat
    assert "buildOutcomeReceiptItems" in story_beat
    assert "buildIntentReadReceipt" in story_beat
    assert "LeveragePayoff" in story_beat
    assert "from \"./play-flow-panels\"" not in story_beat
    assert "from \"../components/play-flow-panels\"" not in story_beat
    assert "export function StoryBeat" not in panels
    assert "export function computeBeatIntensity" not in panels
    assert 'data-play-story-beat="true"' not in panels
    assert 'data-play-outcome-receipt="true"' not in panels
    assert 'data-play-latest-beat-digest="true"' not in panels
    assert "buildOutcomeReceiptItems" not in panels
    assert "components/story-beat.tsx" in readme


def test_action_option_card_module_owns_forecast_and_detail_display_hooks() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    action_option = (ROOT / "frontend2/src/pages/play/components/action-option-card.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./action-option-card"' in panels
    assert "ActionCollapsedForecast" in panels
    assert "ActionSelectedOptionDetail" in panels
    assert "export function ActionDecisionForecast" in action_option
    assert "export function ActionCollapsedForecast" in action_option
    assert "export function ActionSelectedOptionDetail" in action_option
    assert 'data-gameplay-decision-forecast="true"' in action_option
    assert 'data-gameplay-action-forecast-summary="true"' in action_option
    assert 'data-play-action-card-detail="true"' in action_option
    assert 'data-play-action-card-detail-section="forecast"' in action_option
    assert 'data-play-action-card-detail-section="why-now"' in action_option
    assert 'data-play-action-card-detail-section="result"' in action_option
    assert 'data-play-action-card-detail-section="intent"' in action_option
    assert "function hintEchoesForecastChips" in action_option
    assert "renderDecisionForecast" not in panels
    assert "renderCollapsedForecast" not in panels
    assert "renderSelectedOptionDetail" not in panels
    assert 'data-gameplay-action-forecast-summary="true"' not in panels
    assert 'data-play-action-card-detail="true"' not in panels
    assert "handleOptionCommit" not in action_option
    assert "onSubmitFree" not in action_option
    assert "setShowDiary" not in action_option
    assert "components/action-option-card.tsx" in readme


def test_free_action_prompts_module_owns_context_and_starter_display_hooks() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    free_prompts = (ROOT / "frontend2/src/pages/play/components/free-action-prompts.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./free-action-prompts"' in panels
    assert "buildFreeActionStarterMoves" in panels
    assert "FreeActionContextBanner" in panels
    assert "FreeActionStarterRows" in panels
    assert "export function buildFreeActionStarterMoves" in free_prompts
    assert "export function FreeActionContextBanner" in free_prompts
    assert "export function FreeActionStarterRows" in free_prompts
    assert 'data-play-free-action-context="true"' in free_prompts
    assert "data-play-free-action-context-kind={context.kind}" in free_prompts
    assert "data-play-free-action-context-id={context.id}" in free_prompts
    assert 'data-play-free-action-starters="true"' in free_prompts
    assert 'data-play-free-action-starter="true"' in free_prompts
    assert 'data-play-free-action-input="true"' not in free_prompts
    assert 'data-play-free-action-submit="true"' not in free_prompts
    assert "handleSubmitFreeWithReflect" not in free_prompts
    assert "onSubmitFree" not in free_prompts
    assert "setFreeInput" not in free_prompts
    assert 'data-play-free-action-context="true"' not in panels
    assert 'data-play-free-action-starters="true"' not in panels
    assert "components/free-action-prompts.tsx" in readme


def test_leverage_summary_module_owns_summary_readout_display_hooks() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    leverage_summary = (ROOT / "frontend2/src/pages/play/components/leverage-summary.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./leverage-summary"' in panels
    assert "LeverageEmptySummary" in panels
    assert "LeverageSummaryButton" in panels
    assert "export function LeverageEmptySummary" in leverage_summary
    assert "export function LeverageSummaryButton" in leverage_summary
    assert 'data-play-leverage-summary="true"' in leverage_summary
    assert 'data-play-leverage-summary-chips="true"' in leverage_summary
    assert 'data-play-leverage-card="true"' not in leverage_summary
    assert 'data-play-leverage-reveal="true"' not in leverage_summary
    assert 'data-play-leverage-reveal-cta="true"' not in leverage_summary
    assert "handleLeverageReveal" not in leverage_summary
    assert "renderDiaryAttachPreview" not in leverage_summary
    assert "renderDiaryEditor" not in leverage_summary
    assert "setArmedCardId" not in leverage_summary
    assert 'data-play-leverage-summary="true"' not in panels
    assert 'data-play-leverage-summary-chips="true"' not in panels
    assert "components/leverage-summary.tsx" in readme


def test_scene_read_strip_module_owns_passive_scene_read_display_hooks() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    scene_read = (ROOT / "frontend2/src/pages/play/components/scene-read-strip.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./scene-read-strip"' in panels
    assert "buildSceneClocks" in panels
    assert "SceneReadStrip" in panels
    assert "export function buildSceneClocks" in scene_read
    assert "export function SceneReadStrip" in scene_read
    assert 'data-play-scene-read-strip="true"' in scene_read
    assert 't("play.clock_time_label")' in scene_read
    assert 't("play.clock_heat_label")' in scene_read
    assert 't("play.clock_leverage_label")' in scene_read
    assert "function pulseDeltaLabel" in scene_read
    assert "function outcomePriority" in scene_read
    assert 'data-play-scene-read-strip="true"' not in panels
    assert "function pulseDeltaLabel" not in panels
    assert "function outcomePriority" not in panels
    assert "handleOptionCommit" not in scene_read
    assert "handleLeverageReveal" not in scene_read
    assert "handleSubmitFreeWithReflect" not in scene_read
    assert "setShowDiary" not in scene_read
    assert "setFreeInput" not in scene_read
    assert "onPickOption" not in scene_read
    assert "onSubmitFree" not in scene_read
    assert "data-play-leverage-card=" not in scene_read
    assert "data-play-leverage-reveal" not in scene_read
    assert "components/scene-read-strip.tsx" in readme


def test_run_context_objective_module_owns_passive_objective_display_hooks() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    objective = (ROOT / "frontend2/src/pages/play/components/run-context-objective.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./run-context-objective"' in panels
    assert "RunContextObjective" in panels
    assert "export function RunContextObjective" in objective
    assert 'data-play-run-objective="true"' in objective
    assert 'data-play-run-context-lens="true"' in objective
    assert 't("play.run_context_lens_hint")' in objective
    assert 'data-play-run-objective="true"' not in panels
    assert 'data-play-run-context-lens="true"' not in panels
    assert "onUseInventoryItem" not in objective
    assert "data-play-run-inventory-use" not in objective
    assert "data-play-run-inventory-item" not in objective
    assert "onBackHome" not in objective
    assert "handleOptionCommit" not in objective
    assert "handleLeverageReveal" not in objective
    assert "setShowDiary" not in objective
    assert "setFreeInput" not in objective
    assert "components/run-context-objective.tsx" in readme


def test_failed_action_recovery_module_owns_passive_retry_copy_helper() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    recovery_helper = (ROOT / "frontend2/src/pages/play/components/failed-action-recovery.ts").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./components/failed-action-recovery"' in play_page
    assert "buildFailedActionRecovery({" in play_page
    assert "export function buildFailedActionRecovery" in recovery_helper
    assert "type { PlayRetryRecovery }" in recovery_helper
    assert 't("play.recovery_kicker")' in recovery_helper
    assert 't("play.recovery_chip_target", { target })' in recovery_helper
    assert 't("play.recovery_chip_evidence"' in recovery_helper
    assert 't("play.recovery_chip_move"' in recovery_helper
    assert 't("play.recovery_chip_choice"' in recovery_helper
    assert "buildFailedActionRecovery" not in panels
    assert "type FailedActionRecovery" not in panels
    assert "onRetry" not in recovery_helper
    assert "setBusy" not in recovery_helper
    assert "lastFailedActionRef" not in recovery_helper
    assert "onUseInventoryItem" not in recovery_helper
    assert "onBackHome" not in recovery_helper
    assert "handleOptionCommit" not in recovery_helper
    assert "handleLeverageReveal" not in recovery_helper
    assert "setShowDiary" not in recovery_helper
    assert "setFreeInput" not in recovery_helper
    assert "fetch(" not in recovery_helper
    for forbidden in ("provider", "model", "schema", "token"):
        assert forbidden not in recovery_helper.casefold()
    assert "components/failed-action-recovery.ts" in readme


def test_run_context_progress_module_owns_passive_progress_readout() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    progress = (ROOT / "frontend2/src/pages/play/components/run-context-progress.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./run-context-progress"' in panels
    assert "RunContextProgressMeter" in panels
    assert "export function RunContextProgressMeter" in progress
    assert 'role="progressbar"' in progress
    assert 'data-play-run-progress="true"' in progress
    assert 't("stage_bar.aria"' in progress
    assert "runProgressTrack" in progress
    assert "runProgressFill" in progress
    assert 'role="progressbar"' not in panels
    assert 'data-play-run-progress="true"' not in panels
    assert "onUseInventoryItem" not in progress
    assert "data-play-run-inventory-use" not in progress
    assert "onBackHome" not in progress
    assert "onRetry" not in progress
    assert "lastFailedActionRef" not in progress
    assert "handleOptionCommit" not in progress
    assert "handleLeverageReveal" not in progress
    assert "setShowDiary" not in progress
    assert "setFreeInput" not in progress
    assert "fetch(" not in progress
    for forbidden in ("provider", "model", "schema", "token"):
        assert forbidden not in progress.casefold()
    assert "components/run-context-progress.tsx" in readme


def test_run_context_stage_label_module_owns_passive_fallback_stage_copy() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    stage_label = (ROOT / "frontend2/src/pages/play/components/run-context-stage-label.ts").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./run-context-stage-label"' in panels
    assert "stageDisplayName(stageKey)" in panels
    assert "function stageForLocal" in panels
    assert "export function stageDisplayName" in stage_label
    assert 'return "Prelude"' in stage_label
    assert 'return "Coda"' in stage_label
    assert 'return stage.replace(/_/g, " ")' in stage_label
    assert "function stageDisplayName" not in panels
    assert "stageForLocal" not in stage_label
    assert "useT" not in stage_label
    assert "ppStyles" not in stage_label
    assert "onUseInventoryItem" not in stage_label
    assert "onBackHome" not in stage_label
    assert "onRetry" not in stage_label
    assert "lastFailedActionRef" not in stage_label
    assert "handleOptionCommit" not in stage_label
    assert "handleLeverageReveal" not in stage_label
    assert "setShowDiary" not in stage_label
    assert "setFreeInput" not in stage_label
    assert "fetch(" not in stage_label
    for forbidden in ("provider", "model", "schema", "token"):
        assert forbidden not in stage_label.casefold()
    assert "components/run-context-stage-label.ts" in readme


def test_selected_move_confirmation_module_owns_readout_display_hooks() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    confirmation = (ROOT / "frontend2/src/pages/play/components/selected-move-confirmation.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert 'from "./selected-move-confirmation"' in panels
    assert "SelectedMoveConfirmationReadout" in panels
    assert "export function SelectedMoveConfirmationReadout" in confirmation
    assert 'data-play-selected-move-submit-summary="true"' in confirmation
    assert 't("play.selected_move_number", { index: moveNumber })' in confirmation
    assert 't("play.selected_move_ready_label")' in confirmation
    assert 't("play.selected_move_target_chip", { target: targetName })' in confirmation
    assert 't("play.selected_move_room_chip")' in confirmation
    assert "data-play-action-card-confirm=" not in confirmation
    assert "data-play-primary-commit" not in confirmation
    assert "data-play-inner-motive-primary" not in confirmation
    assert "handleOptionCommit" not in confirmation
    assert "setShowDiary" not in confirmation
    assert "onPickOption" not in confirmation
    assert "onSubmitFree" not in confirmation
    assert "data-play-pending-reaction-panel" not in confirmation
    assert 'data-play-selected-move-submit-summary="true"' not in panels
    assert "components/selected-move-confirmation.tsx" in readme


def test_remaining_action_area_behavior_chrome_stays_action_area_owned() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()
    display_modules = [
        (ROOT / "frontend2/src/pages/play/components/action-option-card.tsx").read_text(),
        (ROOT / "frontend2/src/pages/play/components/free-action-prompts.tsx").read_text(),
        (ROOT / "frontend2/src/pages/play/components/leverage-summary.tsx").read_text(),
        (ROOT / "frontend2/src/pages/play/components/selected-move-confirmation.tsx").read_text(),
    ]

    assert "Keep the confirm button, motive button, diary preview/editor, free-input textarea" in readme
    assert "pending/resolved ceremony ownership, and leverage reveal behavior inside `ActionArea`" in readme
    assert "until a behavior-level redesign is explicitly scoped" in readme

    action_area = panels[panels.index("export function ActionArea") :]
    resolving_panel = panels[panels.index("function ResolvingTurnPanel") : panels.index("export function findActionTarget")]
    assert 'data-play-pending-reaction-panel="true"' in resolving_panel
    for required in (
        "const handleOptionCommit =",
        "const handleLeverageReveal =",
        "const handleSubmitFreeWithReflect =",
        "const renderDiaryAttachPreview =",
        "const renderDiaryEditor =",
        "const renderSelectedOptionConfirm =",
        "<ResolvingTurnPanel",
        "commitmentSignals={resolvingCommitmentSignals}",
        'data-play-action-card-confirm="true"',
        'data-play-primary-commit="true"',
        'data-play-inner-motive-primary="true"',
        'data-play-support-actions="true"',
        'data-play-free-action-input="true"',
        'data-play-free-action-submit="true"',
        'data-play-leverage-reveal="true"',
        'data-play-leverage-reveal-cta="true"',
        "value={diary}",
        "onChange={(e) => setDiary(e.target.value)}",
        "value={freeInput}",
        "onChange={(e) => setFreeInput(e.target.value)}",
        "fitTextareaToContent(diaryTextareaRef.current)",
        "fitTextareaToContent(freeTextareaRef.current)",
    ):
        assert required in action_area

    for module in display_modules:
        for forbidden in (
            "handleOptionCommit",
            "handleLeverageReveal",
            "handleSubmitFreeWithReflect",
            "ResolvingTurnPanel",
            "renderDiaryAttachPreview",
            "renderDiaryEditor",
            "setShowDiary",
            "setDiary",
            "setFreeInput",
            "data-play-primary-commit",
            "data-play-inner-motive-primary",
            "data-play-free-action-submit",
            "data-play-leverage-reveal-cta",
            "data-play-pending-reaction-panel",
        ):
            assert forbidden not in module


def test_remaining_play_flow_panel_candidates_are_wait_boundaries() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    for phrase in (
        "should not keep being split by default",
        "Header progress/navigation stays with `Header`",
        "Run inventory controls stay in `RunContextPanel`",
        "Failed-action retry ownership stays in `play-page.tsx`",
        "Resolving/pending ceremony stays in `play-flow-panels.tsx`",
        "Option tag display helpers stay with `ActionArea`",
        "Resource focus/action helpers stay with the play route and `ActionArea`",
        "Backend/provider/live LLM paths stay outside these display modules",
    ):
        assert phrase in readme

    header = panels[panels.index("export function Header") : panels.index("export function computeLiveInventory")]
    run_context = panels[panels.index("export function RunContextPanel") : panels.index("// ---------------------------------------------------------------------------\n// Header")]
    action_area = panels[panels.index("export function ActionArea") :]
    resolving_panel = panels[panels.index("function ResolvingTurnPanel") : panels.index("export function findActionTarget")]

    assert "onBackHome: () => void" in header
    assert "onClick={onBackHome}" in header
    assert "const showProgress =" in header
    assert "width: `${pct}%`" in header
    assert "coverUrl" in header

    assert "onUseInventoryItem?: (item: string) => void" in run_context
    assert "onClick={() => onUseInventoryItem(item)}" in run_context
    assert 'data-play-run-inventory-use="true"' in run_context
    assert 'data-play-run-inventory-item={item}' in run_context
    assert 't("play.run_assets_use_title", { item })' in run_context

    assert 'from "./components/failed-action-recovery"' in play_page
    assert "lastFailedActionRef.current = action" in play_page
    assert "lastFailedActionRef.current = null" in play_page
    assert "PlayRetryRecoveryBanner" in play_page
    assert "onRetry={lastFailedActionRef.current ? () =>" in play_page
    assert "lastFailedActionRef" not in panels
    assert "buildFailedActionRecovery" not in panels

    assert "const [elapsedSeconds, setElapsedSeconds] = useState(0)" in resolving_panel
    assert "window.setInterval" in resolving_panel
    assert 'role="status"' in resolving_panel
    assert 'aria-live="polite"' in resolving_panel
    assert 'data-play-pending-reaction-panel="true"' in resolving_panel
    assert 'data-play-feedback-timeline="true"' in resolving_panel
    assert "commitmentSignals.map" in resolving_panel
    assert "<ResolvingTurnPanel" in action_area

    assert "function optionTagStyle" in panels
    assert "function optionTagGuide" in panels
    assert "optionTagGuide(parsed.tag, t)" in action_area
    assert "...optionTagStyle(parsed.tag)" in action_area
    assert "parseOptionLabel" in panels
    assert "ActionSelectedOptionDetail" in action_area

    assert "export function findActionTarget" in panels
    assert "export function isResourceFocusAction" in panels
    assert "function resourceFocusDetailText" in panels
    assert "findActionTarget(parsed.body, opt.hint, castNameById, latestNpcPulses)" in action_area
    assert "isResourceFocusAction(resourceFocus.id, parsed.body, opt.hint" in action_area
    assert "resourceFocusDetailText(t, resourceFocus.id, resourceFocusMatchCount)" in action_area
    assert "onClearResourceFocus" in action_area
    assert "onClearInventoryFocus" in action_area


def test_play_leverage_fixture_mounts_real_action_area_without_backend() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    fixture = (ROOT / "frontend2/src/pages/play/components/play-leverage-fixture.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert '| { name: "playLeverageFixture" }' in routes
    assert 'segments[1] === "play-leverage"' in routes
    assert 'return "#/qa/play-leverage"' in routes
    assert 'import { PlayLeverageFixture } from "../pages/play/components/play-leverage-fixture"' in app
    assert 'case "playLeverageFixture"' in app
    assert "<PlayLeverageFixture" in app
    assert 'data-play-leverage-fixture="true"' in fixture
    assert "INITIAL_LEVERAGE_CARDS" in fixture
    assert "<ActionArea" in fixture
    assert "leverageCards={leverageCards}" in fixture
    assert "onPlayLeverage={(card) => resolveLeverage(card)}" in fixture
    assert "setLeverageCards((cards) =>" in fixture
    assert 'data-play-leverage-fixture-result="true"' in fixture
    assert 'data-play-leverage-summary="true"' not in fixture
    assert 'data-play-leverage-card="true"' not in fixture
    assert 'data-play-leverage-reveal="true"' not in fixture
    assert "handleLeverageReveal" not in fixture
    assert "getNarrative" not in fixture
    assert "fetch(" not in fixture
    assert "components/play-leverage-fixture.tsx" in readme
    assert "#/qa/play-leverage" in readme
    for forbidden in ("provider", "model", "schema", "token", "fallback", "deterministic"):
        assert forbidden not in fixture.casefold()


def test_play_advisor_fixture_mounts_real_advisor_surface_without_backend() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    fixture = (ROOT / "frontend2/src/pages/play/components/play-advisor-fixture.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert '| { name: "playAdvisorFixture" }' in routes
    assert 'segments[1] === "play-advisor"' in routes
    assert 'return "#/qa/play-advisor"' in routes
    assert 'import { PlayAdvisorFixture } from "../pages/play/components/play-advisor-fixture"' in app
    assert 'case "playAdvisorFixture"' in app
    assert "<PlayAdvisorFixture" in app
    assert 'data-play-advisor-fixture="true"' in fixture
    assert 'data-play-advisor-fixture-state={advisorOpen ? "open" : "closed"}' in fixture
    assert "AdvisorFab" in fixture
    assert "AdvisorSidechat" in fixture
    assert "type AdvisorSidechatApiClient" in fixture
    assert "apiClient={localAdvisorApi}" in fixture
    assert "createLocalAdvisorApi" in fixture
    assert "getNarrativeAdvisorHistory" in fixture
    assert "askNarrativeAdvisor" in fixture
    assert "INITIAL_MESSAGES" in fixture
    assert "ADVISOR_SUGGESTIONS" in fixture
    assert "COMMITMENT_SUMMARY" in fixture
    assert "oracle_used: request.oracle_mode === true" in fixture
    assert "onOracleConsumed" in fixture
    assert 'data-play-advisor-empty-primer="true"' not in fixture
    assert 'data-play-advisor-draft-hint="true"' not in fixture
    assert 'data-play-advisor-suggestion-instruction="true"' not in fixture
    assert "advisorTranscriptLine" not in fixture
    assert "components/play-advisor-fixture.tsx" in readme
    assert "#/qa/play-advisor" in readme


def test_scene_support_rail_uses_webtoon_portrait_images() -> None:
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    assets = (ROOT / "frontend2/src/shared/lib/webtoon-assets.ts").read_text()
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "getAvatarForCastMember" in primitives
    assert "getDefaultAvatar" in primitives
    assert 'data-play-player-portrait="true"' in primitives
    assert 'data-play-cast-portrait="true"' in primitives
    assert 'data-play-cast-resource="true"' in primitives
    assert 'data-play-cast-resource-id={actor.id}' in primitives
    assert 'data-play-cast-focus={focused ? "true" : undefined}' in primitives
    assert "actorActionCounts?: Record<string, number>" in primitives
    assert "const actionCount = actorActionCounts?.[actor.id] ?? 0" in primitives
    assert 'data-play-cast-action-count={actionCount}' in primitives
    assert 'data-play-cast-focus-cue="true"' in primitives
    assert 'aria-label={`${actor.name}. ${actor.role}. ${focusCue}. ${t("play.actor_focus_title", { name: actor.name })}`}' in primitives
    assert "play.actor_focus_cta_none" in primitives
    assert "play.actor_focus_active_none" in primitives
    assert "play.actor_focus_cta_count_one" in primitives
    assert "play.actor_focus_cta_count_many" in primitives
    assert "play.actor_focus_active_count_one" in primitives
    assert "play.actor_focus_active_count_many" in primitives
    assert "aria-pressed={focused}" in primitives
    assert "focusedActorId?: string | null" in primitives
    assert "onFocusActor?: (actor: { id: string; name: string }) => void" in primitives
    assert "onClick={() => onFocusActor?.({ id: actor.id, name: actor.name })}" in primitives
    assert "actorRowButton" in primitives
    assert "actorRowFocused" in primitives
    assert "actorFocusCue" in primitives
    assert 'data-play-advisor-card="true"' in primitives
    assert 'data-play-advisor-ask="true"' in primitives
    assert 'data-play-advisor-portrait="true"' in primitives
    assert "advisorAvatarUrl={advisorAvatar}" in play_page
    assert "focusedActorId={focusedActorId}" in play_page
    assert "actionTargetCountsForOptions" in play_page
    assert "actorActionCounts={actorActionCounts}" in play_page
    assert "onFocusActor={focusSceneActor}" in play_page
    assert "onClearActorFocus={() => setFocusedActorId(null)}" in play_page
    assert "onAskAdvisor={openAdvisor}" in play_page
    assert 'title="People you can involve"' in primitives
    assert "play.advisor_card_name" in primitives
    assert "play.advisor_card_background" in primitives
    assert "advisorAskTitle" in primitives
    assert "advisorAskDetail" in primitives
    assert 'title={`${advisorAskTitle} · ${advisorAskDetail}`}' in primitives
    assert 'aria-label={`${advisorAskTitle}: ${advisorAskDetail}. ${advisorPersona}`}' in primitives
    assert "play.actor_focus_title" in primitives
    assert '"play.actor_focus_cta_none": "Write own move"' in strings
    assert '"play.actor_focus_active_none": "Ready to write"' in strings
    assert '"play.actor_focus_cta_count_one": "1 relevant move"' in strings
    assert '"play.actor_focus_cta_count_many": "{count} relevant moves"' in strings
    assert '"play.actor_focus_active_count_one": "Showing 1 relevant move"' in strings
    assert '"play.actor_focus_active_count_many": "Showing {count} relevant moves"' in strings
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
    runtime_inspector = (ROOT / "frontend2/src/pages/play/components/runtime-inspector.tsx").read_text()
    route_map = (ROOT / "frontend2/src/api/route-map.ts").read_text()
    client = (ROOT / "frontend2/src/api/client.ts").read_text()

    assert "canRequestAgentTrace" in play_page
    assert "api.getNarrativeLLMEvents(sessionId)" in play_page
    assert "llmEvents={llmEvents}" in play_page
    assert 'from "./components/runtime-inspector"' in play_page
    assert "export function RuntimeInspector" not in panels
    assert 'data-play-primitive="EvaluationDrawer"' in runtime_inspector
    assert 'data-reviewer-evidence="true"' in runtime_inspector
    assert "evaluationCriteria" in runtime_inspector
    assert "trajectoryEvidence" in runtime_inspector
    assert "NarrativeLLMCallEvent" in runtime_inspector
    assert "getNarrativeLLMEvents" in client
    assert "/narrative/sessions/:session_id/llm-events" in route_map


def test_normal_play_keeps_evaluation_terms_outside_default_surface() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    runtime_inspector = (ROOT / "frontend2/src/pages/play/components/runtime-inspector.tsx").read_text()

    assert "reviewerMode ? (" in play_page
    assert "<RuntimeInspector" in play_page
    assert "Evaluation evidence" in runtime_inspector
    assert "data-reviewer-evidence" in runtime_inspector
    assert "token" not in (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text().casefold()


def test_finish_mode_normal_play_reduces_top_metadata_density() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    story_beat_module = (ROOT / "frontend2/src/pages/play/components/story-beat.tsx").read_text()

    mood_plate = primitives[primitives.index("export function MoodPlate") : primitives.index("export function SceneSupportRail")]
    scene_rail = primitives[primitives.index("export function SceneSupportRail") : primitives.index("function PrimitiveSection")]
    story_beat = story_beat_module[
        story_beat_module.index("export function StoryBeat") : story_beat_module.index("// Mirror of backend _stage_for")
    ]

    assert "isComplete={isComplete}" in play_page
    assert "isComplete?: boolean" in mood_plate
    assert "moodPlateComplete" in mood_plate
    assert "moodPlateCopyComplete" in mood_plate
    assert "moodTitleComplete" in mood_plate
    assert "This run is finished. Review the ending, then replay or share it." in mood_plate
    assert "{!isComplete ? (" in mood_plate
    assert "cast={story.template.cast.map" not in play_page
    assert "const castLine" not in mood_plate
    assert "story.template.seed" not in mood_plate
    assert "First shot is live" in mood_plate
    assert "The room is waiting." in mood_plate
    assert "The latest beat is ready for your next move." not in mood_plate
    assert '<PrimitiveSection title="Progress">' not in scene_rail
    assert ".slice(0, 3)" in primitives[primitives.index("function sceneActors") : primitives.index("function playerPortraitForStory")]
    assert "return items.slice(0, 3)" in story_beat_module
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
    assert "Action surface rehearsal." in fixture
    assert "Choose a move, confirm it" not in fixture
    assert "<ActionArea" in fixture
    assert "setBusy(true)" in fixture
    assert "setTurn((value) => value + 1)" in fixture
    assert "showNextOptions ? NEXT_OPTIONS : FIRST_OPTIONS" in fixture
    assert "setShowNextOptions(true)" in fixture
    assert "hasRecentImpact={!!outcome}" in fixture
    assert "turn % 2 === 0 ? FIRST_OPTIONS : NEXT_OPTIONS" not in fixture
    assert "type RehearsalOutcome" in fixture
    assert "rehearsalOutcomeForMove(submittedMove)" in fixture
    assert "!outcome ? (" in fixture
    assert 'data-play-action-result-feedback="true"' in fixture
    assert 'data-play-action-result-item="true"' in fixture
    assert "Use this before choosing the next move." in fixture
    assert "Result landed. The next action set is ready." not in fixture
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
    assert 'data-gameplay-layout-priority="action-first"' in fixture
    assert 'data-gameplay-objective="true"' in fixture
    assert "Your goal" in fixture
    assert 'data-gameplay-stakes-header="true"' in fixture
    assert "What is at stake" in fixture
    assert "Each move trades time, pressure, trust, or proof." in fixture
    assert "Watch these while choosing a move." not in fixture
    assert "data-gameplay-pressure-track={track.id}" in fixture
    assert 'gridTemplateColumns: "repeat(auto-fit, minmax(118px, 1fr))"' in fixture
    assert 'gridTemplateColumns: "repeat(auto-fit, minmax(142px, 1fr))"' not in fixture
    assert "Review selected move" in fixture
    assert "Submit it, or add what you secretly mean." in fixture
    assert 'data-gameplay-motive-frame="true"' in fixture
    assert "Public move" in fixture
    assert "Private motive" in fixture
    assert "NPCs only see the move; this tells the story what you are trying to achieve." in fixture
    assert "motiveFrame" in fixture
    assert 'data-gameplay-selected-review={selectedAction ? "true" : undefined}' in fixture
    assert 'data-gameplay-action-card="true"' in fixture
    assert 'role="button"' in fixture
    assert "tabIndex={isPending ? -1 : 0}" in fixture
    assert "aria-pressed={selected}" in fixture
    assert 'aria-label={`Choose move ${action.number}: ${action.title}`}' in fixture
    assert 'onKeyDown={(event) => handleActionCardKeyDown(event, action)}' in fixture
    assert 'event.key !== "Enter" && event.key !== " "' in fixture
    assert 'data-gameplay-selected-submit-summary="true"' in fixture
    assert "Ready to submit" in fixture
    assert "Your move: {action.title}" in fixture
    assert "Next, the room reacts and updates pressure, trust, clues, and next moves." in fixture
    assert "selectedSubmitSummary" in fixture
    assert "function impactSummary(action: FixtureAction)" in fixture
    assert 'data-gameplay-selected-check="true"' in fixture
    assert "Before you submit" in fixture
    assert 'data-gameplay-selected-check-group={group.label.toLowerCase()}' in fixture
    assert "Costs" in fixture
    assert "Upside" in fixture
    assert "Opens" in fixture
    assert "No direct cost" in fixture
    assert "No direct gain" in fixture
    assert "No new path" in fixture
    assert "Compare likely impact before you submit." in fixture
    assert "Compare likely impact before you commit." not in fixture
    assert "Badge clue opened new moves." in fixture
    assert 'label: "Uses badge clue"' in fixture
    assert 'label: "Use badge clue"' not in fixture
    assert "function isResourceUseDelta(delta: FixtureDelta): boolean" in fixture
    assert '{ label: "Uses", values: resourceUses, emptyLabel: "No clue used" }' in fixture
    assert '!isResourceUseDelta(delta) && (delta.tone === "unlock" || delta.tone === "shift")' in fixture
    assert "You can use the badge clue in the next move." in fixture
    assert "Green-room badge clue is attached to this move" in fixture
    assert "Attach green-room badge clue to its opened move" in fixture
    assert "aria-pressed={clueArmed}" in fixture
    assert "function resolvedTracksForAction(action: FixtureAction, clueWasUnlocked: boolean): Track[]" in fixture
    assert "function resolvedSummaryForAction(action: FixtureAction | null): string" in fixture
    assert "const resolvedPanelRef = useRef<HTMLElement | null>(null)" in fixture
    assert "panel.scrollIntoView({ behavior: prefersReducedMotion ? \"auto\" : \"smooth\", block: \"start\" })" in fixture
    assert "scrollMarginTop: 18" in fixture
    assert 'data-gameplay-resolved-receipt="true"' in fixture
    assert "Move resolved" in fixture
    assert "{committed?.action.title ?? \"Your last move\"}" in fixture
    assert "resolvedReceipt" in fixture
    assert "function nextActionBridgeForAction(action: FixtureAction | null): string" in fixture
    assert "function nextActionBridgeLabelForAction(action: FixtureAction | null): string" in fixture
    assert 'return "How to use this change"' in fixture
    assert "action?.unlocksClue || action?.availableBecause" in fixture
    assert 'data-gameplay-next-actions-bridge="true"' in fixture
    assert "{nextActionBridgeLabelForAction(committed?.action ?? null)}" in fixture
    assert "Why the next moves changed" in fixture
    assert "The badge clue changed the menu" in fixture
    assert "you can now use proof directly or turn it into public leverage" in fixture
    assert "return SHOW_BADGE_TRACKS" in fixture
    assert "return TRAP_ANSWER_TRACKS" in fixture
    assert "setTracks(resolvedTracksForAction(committed.action, clueWasUnlocked))" in fixture
    assert 'data-gameplay-resolved-summary="true"' in fixture
    assert fixture.index('data-gameplay-resolved="true"') < fixture.index('data-gameplay-action-area="true"')
    assert "Arthur is publicly tied to the missing badge" in fixture
    assert "The badge becomes a usable route" in fixture
    assert "The badge clue becomes a path to the control door." in fixture
    assert "The room tightens as two stories collide." in fixture
    assert "Badge clue has changed the action set." not in fixture
    assert 'aria-label="Likely impact"' in fixture
    assert 'aria-label="Forecast"' not in fixture
    assert "Badge clue found" in fixture
    assert "Arthur must answer" in fixture
    assert "Arthur attention locked" not in fixture
    assert "Hallway opens" in fixture
    assert "Evidence unlocked" not in fixture
    assert "Hallway opportunity" not in fixture
    assert "availableBecause?: string" in fixture
    assert 'data-gameplay-action-why-now="true"' in fixture
    assert "Why now" in fixture
    assert "The green-room badge turns a vague suspicion into a route Lena can act on." in fixture
    assert 'role: "Sponsor representative"' in fixture
    assert 'role: "Show producer"' in fixture
    assert "Marcus and Arthur now have competing public stories the room can compare." in fixture
    assert 'data-gameplay-person-action="true"' in fixture
    assert "shift?: string" in fixture
    assert 'data-gameplay-person-shift="true"' in fixture
    assert "Badge proof gives Lena a concrete route to manage." in fixture
    assert "Marcus can now answer a public contradiction, not a vague suspicion." in fixture
    assert "Arthur's timeline can be tested against the badge trail." in fixture
    assert "Dana can compare proof-first moves instead of guessing." in fixture
    assert 'data-gameplay-people-usage-note="true"' in fixture
    assert "People you can involve" in fixture
    assert "Ask them to open paths, block pressure, or reveal clues." in fixture
    assert "function firstName(name: string)" in fixture
    assert 'consulted ? `Asked ${actionName}` : `Ask ${actionName}`' in fixture
    assert '{consulted ? "Asked" : "Ask"}' not in fixture
    assert "People are resources." not in fixture
    assert "Clues you can use" in fixture
    assert "0 usable yet" in fixture
    assert "Need proof" in fixture
    assert "Find the green-room clue" in fixture
    assert "Find concrete proof to unlock a sharper next move." in fixture
    assert "Not found yet" not in fixture
    assert "consultedPersonId" in fixture
    assert "setConsultedPersonId(person.id)" in fixture
    assert 'data-gameplay-person-consulted={consulted ? "true" : undefined}' in fixture
    assert 'data-gameplay-person-inline-advice="true"' in fixture
    assert "`Use ${firstName(consultedPerson.name)}'s move`" in fixture
    assert "`${firstName(consultedPerson.name)}'s move selected`" in fixture
    assert "Select this move" not in fixture
    assert "Suggestion selected" not in fixture
    assert "personInlineAdvice" in fixture
    assert "personInlineAdviceBody" not in fixture
    assert "Suggested move" in fixture
    assert "Tradeoff frame" in fixture
    assert 'data-gameplay-person-advice="true"' in fixture
    assert 'suggestionKind: "action" | "judgment"' in fixture
    assert 'data-gameplay-person-advice-mode={adviceMode}' in fixture
    assert 'data-gameplay-person-advice-hint="true"' in fixture
    assert 'consultedPerson.suggestionKind === "action"' in fixture
    assert '`${consultedPerson.name} suggests a move`' in fixture
    assert '`${consultedPerson.name} helps weigh the tradeoff`' in fixture
    assert "You can select this move directly." in fixture
    assert "Use this frame to compare the current moves; Dana does not choose for you." in fixture
    assert "This suggested move is selected." in fixture
    assert "Choose the move whose cost you can defend." in fixture
    assert "Choose the unlocked move whose cost you can defend." in fixture
    assert "can help frame this" not in fixture
    assert '`${consultedPerson.name}\'s advice is attached`' in fixture
    assert "const INITIAL_PEOPLE: PersonResource[]" in fixture
    assert "const UNLOCKED_PEOPLE: PersonResource[]" in fixture
    assert "const people = useMemo(() => (unlockedClue ? UNLOCKED_PEOPLE : INITIAL_PEOPLE), [unlockedClue])" in fixture
    assert "Show Lena the green-room badge" in fixture
    assert "Let Marcus contradict Arthur" in fixture
    assert "Ask Lena how the badge changes the route." in fixture
    assert "Ask Marcus to respond after Arthur speaks." in fixture
    assert "const consultedSuggestedAction = consultedPerson" in fixture
    assert "const adviceArmed = !!consultedSuggestedAction && selectedId === consultedSuggestedAction.id" in fixture
    assert "const actionAreaRef = useRef<HTMLElement | null>(null)" in fixture
    assert "const selectSuggestedAction = (action: FixtureAction)" in fixture
    assert 'actionAreaRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })' in fixture
    assert 'data-gameplay-person-advice-select="true"' in fixture
    assert 'data-gameplay-person-advice-armed={adviceArmed ? "true" : undefined}' in fixture
    assert 'data-gameplay-person-advice-select-active={adviceArmed ? "true" : undefined}' in fixture
    assert "advice is attached" in fixture
    assert "selectSuggestedAction(consultedSuggestedAction)" in fixture
    assert 'const unlockedClueAction = unlockedClue' in fixture
    assert 'actions.find((action) => action.id === "show-badge")' in fixture
    assert "const clueArmed = !!unlockedClueAction && selectedId === unlockedClueAction.id" in fixture
    assert 'data-gameplay-clue-link="green-room-badge"' in fixture
    assert 'data-gameplay-clue-why="green-room-badge"' in fixture
    assert "Why this opens" in fixture
    assert "clueLinkWhy" in fixture
    assert 'data-gameplay-clue-impact="green-room-badge"' in fixture
    assert "Opens move" in fixture
    assert "A proof-backed path, not another vague public challenge." in fixture
    assert "Clue action impact" in fixture
    assert 'data-gameplay-clue-use="green-room-badge"' in fixture
    assert 'data-gameplay-clue-armed={clueArmed ? "true" : undefined}' in fixture
    assert 'data-gameplay-clue-use-active={clueArmed ? "true" : undefined}' in fixture
    assert "Attach badge clue" in fixture
    assert "Badge clue attached" in fixture
    assert "Use clue" not in fixture
    assert "Using clue" not in fixture
    assert "This clue is attached to the selected move." in fixture
    assert "selectSuggestedAction(unlockedClueAction)" in fixture
    assert "borderColor" not in fixture
    assert 'data-gameplay-clue-card={unlockedClue ? "green-room-badge" : "locked"}' in fixture
    assert 'data-gameplay-forecast-chip={hook === "forecast" ? "true" : undefined}' in fixture
    assert 'data-gameplay-delta={hook === "delta" ? "true" : undefined}' in fixture
    assert 'data-gameplay-unlocked-action={unlockedClue ? "true" : undefined}' in fixture
    assert 'data-play-move-receipt="true"' in fixture
    assert 'data-gameplay-pending-impact="true"' in fixture
    assert "Effects in motion" in fixture
    assert "Queued impact" not in fixture
    assert 'data-play-room-reacting="true"' in fixture
    assert "function pendingReactionCopyForAction(action: FixtureAction): string" in fixture
    assert 'data-gameplay-pending-reaction-copy="true"' in fixture
    assert "Arthur stiffens as the badge gap becomes public" in fixture
    assert "Lena turns toward Arthur. The sponsor smiles for the camera" not in fixture
    assert 'data-gameplay-pending-steps="true"' in fixture
    assert 'data-gameplay-pending-step="room"' in fixture
    assert 'data-gameplay-pending-step="state"' in fixture
    assert 'data-gameplay-pending-step="moves"' in fixture
    assert "Room reacts" in fixture
    assert "Pressure and trust shift" in fixture
    assert "Next moves form" in fixture
    assert 'data-gameplay-resolved-title="true"' in fixture
    assert "What changed" in fixture
    assert "Use these changes to pick your next move." in fixture
    assert ">Changed<" not in fixture
    assert "setPhase(\"pending\")" in fixture
    assert "setPhase(\"resolved\")" in fixture
    assert "setUnlockedClue(true)" in fixture
    assert "setConsultedPersonId(null)" in fixture
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


def test_normal_play_prefers_backend_gameplay_envelope_with_derived_backup() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    story_beat = (ROOT / "frontend2/src/pages/play/components/story-beat.tsx").read_text()
    action_option = (ROOT / "frontend2/src/pages/play/components/action-option-card.tsx").read_text()
    free_prompts = (ROOT / "frontend2/src/pages/play/components/free-action-prompts.tsx").read_text()
    run_context_objective = (ROOT / "frontend2/src/pages/play/components/run-context-objective.tsx").read_text()
    envelope = (ROOT / "frontend2/src/pages/play/play-gameplay-envelope.ts").read_text()
    contracts = (ROOT / "frontend2/src/api/contracts.ts").read_text()
    backend_contracts = (ROOT / "rpg_backend/narrative/contracts.py").read_text()
    backend_service = (ROOT / "rpg_backend/narrative/service.py").read_text()
    backend_repository = (ROOT / "rpg_backend/narrative/repository.py").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    resource_focus_match_styles = styles.split("resourceFocusMatchChip: {", 1)[1].split(
        "resourceFocusCueAction:",
        1,
    )[0]

    assert "buildGameplayEnvelope" in envelope
    assert "deriveActionForecastChips" in envelope
    assert "normalizeBackendEnvelope" in envelope
    assert '"May reveal proof"' in envelope
    assert '"Read the room"' in envelope
    assert '"Use leverage"' in envelope
    assert '"Evidence lead"' not in envelope
    assert '"Room read"' not in envelope
    assert '"May reveal proof"' in backend_service
    assert '"Read the room"' in backend_service
    assert '"Use leverage"' in backend_service
    assert '"Evidence lead"' not in backend_service
    assert '"Room read"' not in backend_service
    assert "buildGameplayEnvelope({" in play_page
    assert "backendEnvelope: story.gameplay_envelope ?? null" in play_page
    assert "gameplay_envelope: response.gameplay_envelope ?? null" in play_page
    assert "RunContextPanel" in play_page
    assert "<RunContextPanel" in play_page
    assert "liveInventory={liveInventory}" in play_page
    assert "leverageCards={leverageCards}" in play_page
    assert "onUseInventoryItem={handleUseInventoryItem}" in play_page
    assert 'data-play-run-context="true"' in panels
    assert 't("play.run_assets_hint")' in panels
    assert 'data-play-run-inventory-use="true"' in panels
    assert 'data-play-run-inventory-item={item}' in panels
    assert 't("play.run_assets_use_title", { item })' in panels
    assert "runInventoryHint" in styles
    assert "runInventoryItemButton" in styles
    assert "runContextObjectiveText" in styles
    assert 'fontSize: 16' in styles
    assert "runRoleTitle" in styles
    assert 'fontSize: 18' in styles
    assert '"play.run_assets_hint": "Mention in your own move"' in strings
    assert '"play.run_assets_hint": "可写进自定义行动"' in strings
    assert '"play.run_assets_use_title": "Use {item} in your own move"' in strings
    assert '"play.run_assets_use_title": "用 {item} 写一个自定义行动"' in strings
    assert "const [focusedActorId, setFocusedActorId] = useState<string | null>(null)" in play_page
    assert 'type GameplayResourceFocusId = "time" | "pressure" | "evidence"' in play_page
    assert "function isGameplayResourceFocusId(value: string): value is GameplayResourceFocusId" in play_page
    assert "const [focusedResourceId, setFocusedResourceId] = useState<GameplayResourceFocusId | null>(null)" in play_page
    assert "const [focusedInventoryItem, setFocusedInventoryItem] = useState<string | null>(null)" in play_page
    assert "const handleUseInventoryItem = useCallback((item: string)" in play_page
    assert "setFocusedInventoryItem(item)" in play_page
    assert "setShowFreeInput(true)" in play_page
    assert "const actorFocus = focusedActorId && focusedActorName" in play_page
    assert "const focusedResourceTrack = focusedResourceId" in play_page
    assert "useMemo" not in play_page
    assert "const actorActionCounts = lastNarrator" in play_page
    assert "const resourceActionCounts = lastNarrator" in play_page
    assert "resourceActionCountsForOptions" in play_page
    assert 't("play.resource_focus_cta_none")' not in play_page
    assert 't("play.resource_focus_active_none")' in play_page
    assert "isResourceFocusAction(resourceId, parsed.body, option.hint, actionForecasts[index] ?? [])" in play_page
    assert "const focusSceneActor = (actor: { id: string; name: string }) => {" in play_page
    assert "setFocusedResourceId(null)" in play_page
    assert "setFocusedActorId(wasFocused ? null : actor.id)" in play_page
    assert "const focusGameplayResource = (resourceId: GameplayResourceFocusId) => {" in play_page
    assert "setFocusedResourceId(wasFocused ? null : resourceId)" in play_page
    assert "data-gameplay-resource-track={focusableTrackId}" in play_page
    assert 'data-gameplay-evidence-resource={focusableTrackId === "evidence" ? "true" : undefined}' in play_page
    assert "data-gameplay-resource-focus={isFocused ? \"true\" : undefined}" in play_page
    assert "data-gameplay-resource-action-count={resourceMatchCount}" in play_page
    assert 'aria-label={`${track.label}: ${track.value}. ${resourceActionLabel ? `${resourceActionLabel}. ` : ""}${focusTitle}`}' in play_page
    assert 'aria-label={`${track.label}: ${track.value}. ${focusTitle}`}' not in play_page
    assert 't("play.resource_focus_active_count_one")' in play_page
    assert 't("play.resource_focus_active_count_many", { count: resourceMatchCount })' in play_page
    assert "focusedResourceId={focusedResourceId}" in play_page
    assert "resourceActionCounts={resourceActionCounts}" in play_page
    assert "onFocusResource={focusGameplayResource}" in play_page
    assert 'behavior: prefersReducedMotion ? "auto" : "smooth"' in play_page
    assert 'data-play-run-context-lens="true"' in run_context_objective
    assert 'data-play-run-objective="true"' in run_context_objective
    assert 't("play.run_context_lens_hint")' in run_context_objective
    assert "runContextObjectiveHint" in styles
    assert '"play.run_context_lens_hint": "Use this goal as the lens for reading the scene."' in strings
    assert '"play.run_context_lens_hint": "用这个目标去读场景，再决定下一步。"' in strings
    assert "<GameplayStatePanel" in play_page
    assert "envelope={gameplayEnvelope}" in play_page
    assert 'data-gameplay-objective-text="normal-play"' not in play_page
    assert 'data-gameplay-objective="normal-play"' not in play_page
    assert "WebkitLineClamp: 2" in styles
    assert 'whiteSpace: "nowrap" as const' not in styles[styles.index("gameplayObjectiveText:"):styles.index("gameplayTrackGrid:", styles.index("gameplayObjectiveText:"))]
    assert "<GameplayLoopGuide" in play_page
    assert 'data-gameplay-loop-guide="normal-play"' in play_page
    assert "data-gameplay-loop-stage={stage}" in play_page
    assert "data-gameplay-loop-step={step.id}" in play_page
    assert 'data-gameplay-loop-step-active={isActive ? "true" : "false"}' in play_page
    assert 'data-gameplay-loop-step-done={isDone ? "true" : "false"}' in play_page
    assert "const compactLoop = useCompactLayout(\"(max-width: 680px)\")" in play_page
    assert "ppStyles.gameplayLoopPanelCompact" in play_page
    assert "data-gameplay-loop-steps-compact={compactLoop ? \"true\" : \"false\"}" in play_page
    assert "gameplayLoopPanelCompact" in styles
    assert "gameplayLoopStepsCompact" in styles
    assert "gameplayLoopStepLabelCompact" in styles
    loop_styles = styles[styles.index("gameplayLoopPanel:"):styles.index("gameplayToneGain:", styles.index("gameplayLoopPanel:"))]
    assert "borderRadius: 999" in loop_styles
    assert 'gridTemplateColumns: "minmax(150px, auto) minmax(0, 1fr)"' in loop_styles
    assert 'display: "flex"' in loop_styles
    assert 'display: "none"' in loop_styles
    assert 'busy\n      ? "react"' in play_page
    assert "const showGameplayImpactSummary =" in play_page
    assert 'showGameplayImpactSummary\n        ? "update"' in play_page
    assert "<GameplayImpactSummary" in play_page
    assert "envelope={gameplayEnvelope}" in play_page
    assert "castNameById={castNameById}" in play_page
    assert "nextChoiceTargets={nextChoiceTargets}" in play_page
    assert "function impactSourceMoveText(" in play_page
    assert "const impactSourceMove = impactSourceMoveText(previousPlayerForLastNarrator)" in play_page
    assert "sourceMoveText={impactSourceMove}" in play_page
    assert 'data-gameplay-impact-source-move="true"' in play_page
    assert "function uniqueActionTargetsForOptions(" in play_page
    assert "findActionTarget(parsed.body, option.hint, castNameById, latestNpcPulses)" in play_page
    assert "const nextChoiceTargets = lastNarrator" in play_page
    assert "data-gameplay-next-choice-target-id={targetSignal.targetId}" in play_page
    assert "data-gameplay-next-choice-target-id={targetSignal?.targetId}" in play_page
    assert 'data-gameplay-next-choice-target-focus="true"' in play_page
    assert 'onClick={() => onFocusActor({ id: targetSignal.targetId, name: targetSignal.targetName })}' in play_page
    assert 'aria-pressed={focusedActorId === targetSignal.targetId}' in play_page
    assert "focusedActorId={focusedActorId}" in play_page
    assert "onFocusActor={focusSceneActor}" in play_page
    assert "!isComplete && !busy && turnsCompleted > 0" in play_page
    assert "actionForecasts={gameplayEnvelope.actionForecasts}" in play_page
    assert "actorFocus={actorFocus}" in play_page
    assert "resourceFocus={focusedResourceId && focusedResourceTrack" in play_page
    assert "const compactTracks = useCompactLayout(\"(max-width: 680px)\")" in play_page
    assert "data-gameplay-track-grid-compact={compactTracks ? \"true\" : \"false\"}" in play_page
    assert "gameplayTrackGridCompact" in styles
    assert "gridTemplateColumns: \"repeat(2, minmax(0, 1fr))\"" in styles
    assert "gameplayTrackCompact" in styles
    assert "onClearResourceFocus={() => setFocusedResourceId(null)}" in play_page
    assert "actionForecasts?: GameplayActionForecast[][]" in panels
    assert "actorFocus?: { id: string; name: string } | null" in panels
    assert 'type GameplayResourceFocusId = "time" | "pressure" | "evidence"' in panels
    assert "resourceFocus?: { id: GameplayResourceFocusId; label: string } | null" in panels
    assert "onClearResourceFocus?: () => void" in panels
    assert "export function findActionTarget(" in panels
    assert "const optionTargets = useMemo(() => options.map" in panels
    assert "const actorFocusOptionMatches = useMemo" in panels
    assert "target?.id === actorFocus.id" in panels
    assert "actorFocusMatchedMoves" in panels
    assert 'data-play-actor-focus-matches="true"' in panels
    assert 'data-play-actor-focus-instruction="true"' in panels
    assert 'data-play-actor-focus-match-chip="true"' in panels
    assert "data-play-actor-focus-match-option-index={index}" in panels
    assert 'aria-label={t("play.actor_focus_select_match", { move: label })}' in panels
    assert "onClick={() => handleOptionSelect(index)}" in panels
    assert "const actorFocusDetail = actorFocus" in panels
    assert "play.actor_focus_match_detail_one" in panels
    assert "play.actor_focus_match_detail_many" in panels
    assert "function isResourceFocusAction(" in panels
    assert "export function isResourceFocusAction" in panels
    assert "resourceId === \"time\"" in panels
    assert "resourceId === \"pressure\"" in panels
    assert "const resourceFocusOptionMatches = useMemo" in panels
    assert "isResourceFocusAction(resourceFocus.id, parsed.body, opt.hint, actionForecasts?.[index] ?? [])" in panels
    assert "resourceFocusMatchedMoves" in panels
    assert 'data-play-resource-focus-instruction="true"' in panels
    assert "data-play-resource-focus-match-option-index={index}" in panels
    assert 'aria-label={t("play.resource_focus_select_match", { move: label })}' in panels
    assert "resourceFocusMatchedMoveLabels" not in panels
    assert "function resourceFocusDetailText(" in panels
    assert "const openFreeActionComposer = () => {" in panels
    assert 'data-play-resource-focus-cue="true"' in panels
    assert 'data-play-resource-focus-id={resourceFocus.id}' in panels
    assert "data-play-resource-focus-match-count={resourceFocusMatchCount}" in panels
    assert 'data-play-resource-focus-filter-note="true"' in panels
    assert 'data-play-resource-focus-cue-head="true"' in panels
    assert 'data-play-resource-focus-matches="true"' in panels
    assert 'data-play-resource-focus-match-chip="true"' in panels
    assert "play.resource_focus_showing_label" in panels
    assert 'fontFamily: "inherit"' in resource_focus_match_styles
    assert 'cursor: "pointer"' in resource_focus_match_styles
    assert 'textAlign: "left" as const' in resource_focus_match_styles
    assert "ppStyles.resourceFocusCueClear" in panels
    assert 'data-play-resource-focus-clear="true"' in panels
    assert "resourceFocusMatchCount === 0 && showFreeActionToggle" in panels
    assert 'data-play-resource-focus-custom-move="true"' in panels
    assert "onClick={openFreeActionComposer}" in panels
    assert 'data-play-action-resource-focus-match={isResourceFocusMatch ? "true" : undefined}' in panels
    assert 'data-play-action-resource-focus-dimmed={isResourceFocusDimmed ? "true" : undefined}' in panels
    assert 'data-play-action-target-chip="true"' in panels
    assert 'data-play-action-target-id={actionTarget.id}' in panels
    assert 'aria-label={t("play.action_target_title", { name: actionTarget.name })}' in panels
    assert 't("play.action_target_label")' in panels
    assert 't("play.action_target_title", { name: actionTarget.name })' in panels
    assert 'data-play-action-target-detail="true"' in action_option
    assert "data-play-action-target-detail-id={target.id}" in action_option
    assert 't("play.action_target_detail_label")' in action_option
    assert 't("play.action_target_detail_text", { name: target.name })' in action_option
    assert "type ResolvingCommitmentSignal = {" in panels
    assert "const resolvingCommitmentSignals = useMemo<ResolvingCommitmentSignal[]>" in panels
    assert 'data-play-move-receipt-signals="true"' in panels
    assert 'data-play-move-receipt-signals-label="true"' in panels
    assert 'data-play-move-receipt-signal="true"' in panels
    assert "commitmentSignals={resolvingCommitmentSignals}" in panels
    assert 'data-play-actor-focus-cue="true"' in panels
    assert 'data-play-actor-focus-id={actorFocus.id}' in panels
    assert "data-play-actor-focus-match-count={actorFocusMatchCount}" in panels
    assert "const actorFocusLeverageCard = useMemo(() => {" in panels
    assert 'data-play-actor-focus-leverage={actorFocusLeverageCard ? "true" : undefined}' in panels
    assert 'data-play-actor-focus-cue-head="true"' in panels
    assert "play.actor_focus_showing_label" in panels
    assert "play.actor_focus_leverage_label" in panels
    assert "play.actor_focus_leverage_detail" in panels
    assert "play.actor_focus_filter_note" in panels
    assert "onClearActorFocus?: () => void" in panels
    assert 'data-play-actor-focus-clear="true"' in panels
    assert 'data-play-actor-focus-filter-note="true"' in panels
    assert "ppStyles.actorFocusCueClear" in panels
    assert 'aria-label={`${t("play.actor_focus_label")}: ${actorFocus.name}. ${actorFocusDetail}`}' in panels
    assert "actorFocusMatchCount === 0 && showFreeActionToggle" in panels
    assert 'data-play-actor-focus-custom-move="true"' in panels
    assert "const freeActionFocusContext = actorFocus && actorFocusMatchCount === 0" in panels
    assert "inventoryFocusItem?: string | null" in panels
    assert "onClearInventoryFocus?: () => void" in panels
    assert "play.free_context_inventory_label" in free_prompts
    assert "play.free_context_inventory_detail" in panels
    assert "play.action_free_inventory_placeholder" in panels
    assert "play.action_open_free_inventory" in panels
    assert "const freeActionStarterMoves = !freeActionDraft" in panels
    assert "buildFreeActionStarterMoves({ context: freeActionFocusContext, t })" in panels
    assert 'context?.kind === "inventory"' in free_prompts
    assert 'context?.kind === "resource"' in free_prompts
    assert "play.free_starter_inventory_show_label" in free_prompts
    assert "play.free_starter_inventory_ask_text" in free_prompts
    assert "play.free_starter_time_buy_text" in free_prompts
    assert "play.free_starter_pressure_raise_label" in free_prompts
    assert "play.free_starter_evidence_trace_text" in free_prompts
    assert "play.free_starter_general_ask_label" in free_prompts
    assert "play.free_starter_general_pressure_text" in free_prompts
    assert "play.free_starter_general_time_text" in free_prompts
    assert 'data-play-free-action-starters="true"' in free_prompts
    assert 'data-play-free-action-starter="true"' in free_prompts
    assert 'data-play-free-action-input="true"' in panels
    assert 'data-play-free-action-submit="true"' in panels
    assert "ppStyles.freeSubmitButton" in panels
    assert "freeSubmitButton" in styles
    assert "minHeight: 42" in styles[styles.index("freeSubmitButton") : styles.index("freeSubmitButtonDisabled")]
    assert "actionPalette.primaryBackground" in styles[styles.index("freeSubmitButton") : styles.index("freeSubmitButtonDisabled")]
    assert "const freeActionToggleShownInFocusCue =" in panels
    assert "const showAlternateFreeActionToggle = showFreeActionToggle && !freeActionToggleShownInFocusCue" in panels
    assert "{showAlternateFreeActionToggle ? (" in panels
    assert 'data-play-free-action-toggle="true"' in panels
    assert "alternateActionButton" in styles
    assert "minHeight: 48" in styles[styles.index("alternateActionButton") : styles.index("alternateActionLabel")]
    assert 'borderRadius: 6' in styles[styles.index("alternateActionButton") : styles.index("alternateActionLabel")]
    assert "onUseStarter={setFreeInput}" in panels
    assert "onUseStarter(starter.text)" in free_prompts
    assert 'data-play-free-action-context="true"' in free_prompts
    assert "data-play-free-action-context-kind={context.kind}" in free_prompts
    assert "data-play-free-action-context-id={context.id}" in free_prompts
    assert "freeActionFocusContext?.placeholder ?? t(\"play.action_free_placeholder\")" in panels
    assert "freeActionFocusContext?.toggleText ?? t(\"play.action_open_free\")" in panels
    assert "freeActionFocusContext?.toggleHint ?? t(\"play.action_open_free_hint\")" in panels
    assert "freeActionFocusContext?.toggleTitle ?? t(\"play.action_open_free_title\")" in panels
    assert 'data-play-free-action-boundary="true"' in panels
    assert 't("play.free_action_boundary_hint")' in panels
    assert "const freeActionContextTargetName =" in panels
    assert "const freeActionTargetNameForFeedback = freeActionContextTargetName || freeActionTargetName" in panels
    assert "const freeActionSubmittedText =" in panels
    assert "freeActionTargetName !== freeActionContextTargetName" in panels
    assert "`${freeActionContextTargetName} — ${freeActionDraft}`" in panels
    assert "onSubmitFree(diaryOverride, freeActionSubmittedText)" in panels
    assert ": freeActionTargetNameForFeedback || undefined" in panels
    assert "title: freeActionSubmittedText" in panels
    assert "onSubmitFree: (diaryOverride?: string, freeInputOverride?: string) => void" in panels
    assert "const publicMove = (freeInputOverride ?? freeInput).trim()" in play_page
    assert "free_input: publicMove" in play_page
    assert 'data-play-action-actor-focus-match={isActorFocusMatch ? "true" : undefined}' in panels
    assert 'data-play-action-actor-focus-dimmed={isActorFocusDimmed ? "true" : undefined}' in panels
    assert 't("play.actor_focus_custom_label", { name: actorFocus.name })' in panels
    assert '"play.actor_focus_cta_none": "Write own move"' in strings
    assert '"play.actor_focus_active_none": "Ready to write"' in strings
    assert '"play.actor_focus_custom_label": "Write {name} into a move"' in strings
    assert "const visibleChips = chips.filter((chip) => !chip.detail)" in action_option
    assert "visibleChips.filter((chip) => decisionForecastGroupForChip(chip) === \"cost\")" in action_option
    assert "{visibleChips.map((chip) => (" in action_option
    assert 'data-gameplay-forecast-detail-chip="normal-play"' not in action_option
    assert "optionExpandedDetailBody" in styles
    assert "optionExpandedDetailChip" in styles
    assert "optionExpandedDetailHeader" in styles
    assert 'data-play-action-card-detail-heading="true"' in action_option
    assert 't("play.action_decision_check_label")' in action_option
    assert action_option.index('data-play-action-card-detail-section="forecast"') < action_option.index('data-play-action-card-detail-section="result"')
    assert action_option.index('data-play-action-card-detail-section="why-now"') < action_option.index('data-play-action-target-detail="true"')
    assert action_option.index('data-play-action-target-detail="true"') < action_option.index('data-play-action-card-detail-section="intent"')
    assert 'data-gameplay-forecast-detail="normal-play"' in action_option
    assert 'data-gameplay-forecast-reason-preview="normal-play"' in action_option
    assert 'data-gameplay-forecast-reason-text="normal-play"' in action_option
    assert 't("play.gameplay_forecast_detail_preview")' in action_option
    assert 'aria-label={`${t("play.gameplay_forecast_detail_label")}: ${reasonChip.detail}`}' in action_option
    assert "gameplayForecastInlineWithReason" in styles
    assert "gameplayForecastReasonPreview" in styles
    assert '"play.gameplay_forecast_detail_label": "Why now"' in strings
    assert '"play.action_decision_check_label": "Decision check"' in strings
    assert '"play.action_decision_check_label": "决策检查"' in strings
    assert '"play.gameplay_forecast_detail_preview": "Open to see why this move fits now."' in strings
    assert '"play.gameplay_forecast_detail_preview": "展开后看为什么这步现在可用。"' in strings
    assert 'data-gameplay-envelope="true"' in play_page
    assert "data-gameplay-envelope-source={envelope.source}" in play_page
    assert 'source: "backend" | "live_enriched" | "ui-derived"' in envelope
    assert 'source: "ui-derived"' in envelope
    assert 'source: "backend"' in envelope
    assert 'source: raw.source' in envelope
    assert "export type NarrativeGameplayEnvelope" in contracts
    assert "detail?: string | null" in contracts
    assert 'source: "backend" | "live_enriched"' in contracts
    assert "gameplay_envelope?: NarrativeGameplayEnvelope | null" in contracts
    assert "class GameplayEnvelope" in backend_contracts
    assert "detail: str | None = Field(default=None, max_length=140)" in backend_contracts
    assert 'GameplayEnvelopeSource = Literal["backend", "live_enriched"]' in backend_contracts
    assert "class TurnGameplayMetadata" in backend_contracts
    assert "gameplay_metadata: TurnGameplayMetadata | None = Field(default=None, exclude=True)" in backend_contracts
    assert "gameplay_envelope: GameplayEnvelope | None = None" in backend_contracts
    assert "_build_gameplay_envelope" in backend_service
    assert "live_metadata: TurnGameplayMetadata | None = None" in backend_service
    assert "metadata_to_merge = live_metadata" in backend_service
    assert "metadata_to_merge = last_narrator.gameplay_metadata" in backend_service
    assert "for context in metadata_to_merge.next_action_context" in backend_service
    assert "_prepend_gameplay_chip(" in backend_service
    assert "action_forecasts[context.option_index]" in backend_service
    assert "action_forecasts=[row[:3] for row in action_forecasts]" in backend_service
    assert 'detail=context.reason' in backend_service
    assert "gameplay_metadata_json" in backend_repository
    assert "TurnGameplayMetadata.model_validate" in backend_repository
    assert 'data-gameplay-objective="normal-play"' not in play_page
    assert 'data-gameplay-stakes-header="normal-play"' in play_page
    assert "data-gameplay-pressure-track={track.id}" in play_page
    assert 'data-gameplay-action-forecast="true"' in panels
    assert 'data-gameplay-forecast-chip="normal-play"' in action_option
    assert 'data-gameplay-decision-forecast="true"' in action_option
    assert 'data-gameplay-decision-group={group.id}' in action_option
    assert 'type DecisionForecastGroup = "cost" | "upside" | "shift"' in action_option
    assert 'data-gameplay-impact-summary="true"' in play_page
    assert 'data-gameplay-impact-result-layer="true"' in play_page
    assert 'aria-label={t("play.feedback_result_layer_label")}' in play_page
    assert 'data-gameplay-impact-result-label="true"' in play_page
    assert 'data-gameplay-impact-spotlight="true"' in play_page
    assert "data-gameplay-impact-spotlight-tone={primaryImpact.tone}" in play_page
    assert "const primaryImpact =" in play_page
    assert "function impactDeltaKey(" in play_page
    assert "const secondaryImpacts = envelope.impact.filter(" in play_page
    assert "function isLowSignalForecastLabel(" in play_page
    assert "chip.detail || !isLowSignalForecastLabel(chip.label)" in play_page
    assert "play.feedback_next_choice_changed_label" in play_page
    assert "function parseRelationshipDeltaLabel(" in play_page
    assert "function relationshipShiftCopy(" in play_page
    assert "function actorFromDisplayName(" in play_page
    assert 'data-gameplay-relationship-delta="true"' in play_page
    assert 'data-gameplay-impact-actor-focus="true"' in play_page
    assert "data-gameplay-impact-actor-id={actor.id}" in play_page
    assert 'data-gameplay-impact-actor-focused={isFocused ? "true" : undefined}' in play_page
    assert "onClick={() => onFocusActor(actor)}" in play_page
    assert "aria-label={`${parsed.name} ${shiftCopy}. ${t(\"play.impact_focus_actor_title\", { name: actor.name })}`}" in play_page
    assert "aria-label={`${parsed.name} ${shiftCopy}`}" in play_page
    assert 'data-gameplay-impact-group={group.id}' in play_page
    assert 'data-gameplay-impact-group="next"' in play_page
    assert "style={ppStyles.gameplayImpactNextBridge}" in play_page
    assert "style={ppStyles.gameplayImpactNextGroupLabel}" in play_page
    assert 'data-gameplay-next-choice-signals="true"' in play_page
    assert 'data-gameplay-next-choice-bridge="normal-play"' in play_page
    assert 'aria-label={t("play.feedback_next_choice_label")}' in play_page
    assert 'data-gameplay-next-choice-signal="normal-play"' in play_page
    assert "nextChoiceSignals" in play_page
    assert 'data-gameplay-delta="normal-play"' in play_page
    assert "gameplayEnvelopePanel" in styles
    assert "gameplayLoopPanel" in styles
    assert "gameplayLoopStepActive" in styles
    assert "gameplayLoopStepDone" in styles
    assert "gameplayForecastChip" in styles
    assert "optionTargetChip" in styles
    assert "optionTargetLabel" in styles
    assert "optionTargetName" in styles
    assert "gameplayTrackButton" in styles
    assert "gameplayTrackFocused" in styles
    assert "gameplayTrackAction" in styles
    assert "resourceFocusCue" in styles
    assert "resourceFocusCueHead" in styles
    assert "resourceFocusMatches" in styles
    assert "resourceFocusMatchChip" in styles
    assert "resourceFocusCueClear" in styles
    assert "resourceFocusCueAction" in styles
    assert "resourceFocusCueFilterNote" in styles
    assert "gameplayNextChoiceTargetButton" in styles
    assert "gameplayNextChoiceTargetFocused" in styles
    assert "resolvingCommitmentSignals" in styles
    assert "resolvingCommitmentSignalChip" in styles
    assert "freeActionContext" in styles
    assert "freeActionContextName" in styles
    assert "freeActionContextDetail" in styles
    assert "freeActionStarters" in styles
    assert "freeActionStarterButton" in styles
    assert "optionBtnResourceFocusMatch" in styles
    assert "gameplayNextChoiceChip" in styles
    assert "optionBtnActorFocusMatch" in styles
    assert "optionBtnActorFocusDimmed" in styles
    assert "actorFocusCue" in styles
    assert "actorFocusCueHead" in styles
    assert "actorFocusMatches" in styles
    assert "actorFocusMatchChip" in styles
    assert "actorFocusCueClear" in styles
    assert "actorFocusCueFilterNote" in styles
    assert "gameplayDecisionForecast" in styles
    assert "gameplayDecisionGroupCost" in styles
    assert "gameplayDecisionGroupUpside" in styles
    assert "gameplayDecisionGroupShift" in styles
    assert "gameplayImpactPanel" in styles
    assert "gameplayImpactSourceMove" in styles
    assert "gameplayImpactSourceLabel" in styles
    assert "gameplayImpactSourceText" in styles
    source_text_block = styles[styles.index("gameplayImpactSourceText: {"):styles.index("gameplayImpactSpotlight: {")]
    assert 'whiteSpace: "normal" as const' in source_text_block
    assert 'overflowWrap: "anywhere" as const' in source_text_block
    assert 'textOverflow: "ellipsis"' not in source_text_block
    assert "gameplayImpactSpotlight" in styles
    assert "gameplayImpactSpotlightValue" in styles
    assert "gameplayRelationshipDelta" in styles
    assert "gameplayRelationshipDeltaButton" in styles
    assert "gameplayRelationshipDeltaButtonFocused" in styles
    assert "gameplayRelationshipDeltaShift" in styles
    assert "gameplayImpactGroups" in styles
    assert "gameplayImpactResultLayer" in styles
    assert "gameplayImpactLayerLabel" in styles
    assert "gameplayImpactNextGroup" in styles
    assert "gameplayImpactNextBridge" in styles
    assert "gameplayImpactNextGroupLabel" in styles
    assert "outcomeReceiptHeader" in styles
    assert "outcomeReceiptHint" in styles
    outcome_hint_block = styles[styles.index("outcomeReceiptHint: {"):styles.index("outcomeReceiptInlineLabel: {")]
    assert 'whiteSpace: "normal" as const' in outcome_hint_block
    assert 'textOverflow: "ellipsis"' not in outcome_hint_block
    assert "feedbackPendingTimeline" in styles
    assert "feedbackPendingStepActive" in styles
    assert "roomReactingCues" in styles
    assert "roomReactingCue" in styles
    assert "optionOpenedByChange" in styles
    assert "optionOpenedByChangeLabel" in styles
    assert '"play.gameplay_loop_label": "How turns work"' in strings
    assert '"play.gameplay_loop_kicker": "This turn"' in strings
    assert '"play.gameplay_loop_read_label": "Read the room"' in strings
    assert '"play.gameplay_loop_choose_label": "Choose a move"' in strings
    assert '"play.gameplay_loop_choose_detail": "Costs, openings, target"' in strings
    assert '"play.gameplay_loop_choose_detail": "代价、机会、目标"' in strings
    assert '"play.gameplay_loop_react_label": "Watch reaction"' in strings
    assert '"play.gameplay_loop_update_label": "Use changes"' in strings
    assert '"play.gameplay_objective_label": "Your goal"' in strings
    assert '"play.gameplay_objective_label": "你的目标"' in strings
    assert '"play.gameplay_tracks_label": "What is at stake"' in strings
    assert '"play.gameplay_tracks_hint": "Each move trades time, pressure, trust, or proof"' in strings
    assert '"play.gameplay_tracks_hint": "Watch these while choosing a move"' not in strings
    assert '"play.gameplay_tracks_label": "风险与资源"' in strings
    assert '"play.gameplay_tracks_hint": "每次行动都在交换时间、压力、信任或证据"' in strings
    assert '"play.gameplay_tracks_hint": "选择行动时盯住这些变化"' not in strings
    assert "gameplayStakesHeader" in styles
    assert '"play.feedback_source_move_label": "From your move"' in strings
    assert '"play.gameplay_decision_forecast_label": "Likely impact"' in strings
    assert '"play.actor_focus_label": "Focus on person"' in strings
    assert '"play.actor_focus_showing_label": "Moves involving {name}"' in strings
    assert '"play.actor_focus_custom_label": "Write {name} into a move"' in strings
    assert '"play.actor_focus_leverage_label": "Leverage ready for {name}"' in strings
    assert '"play.actor_focus_title": "Pull {name} into this move"' in strings
    assert '"play.actor_focus_cta_none": "Write own move"' in strings
    assert '"play.actor_focus_active_none": "Ready to write"' in strings
    assert '"play.actor_focus_match_detail_one": "1 current move makes this person react."' in strings
    assert '"play.actor_focus_match_detail_many": "{count} current moves make this person react."' in strings
    assert '"play.actor_focus_leverage_detail": "A leverage card is ready for {name}; reveal it above, or write your own move."' in strings
    assert '"play.actor_focus_instruction": "Choose a matching move, or write your own."' in strings
    assert '"play.actor_focus_filter_note": "This only filters the current choices; no move is submitted yet."' in strings
    assert '"play.actor_focus_matches_label": "Matching moves"' in strings
    assert '"play.actor_focus_select_match": "Review move: {move}"' in strings
    assert '"play.actor_focus_select_match": "Select move: {move}"' not in strings
    assert '"play.actor_focus_no_match": "No current move names them; write your own move if you want to pull them in."' in strings
    assert '"play.actor_focus_clear": "Show all moves"' in strings
    assert '"play.actor_focus_clear": "Clear"' not in strings
    assert '"play.free_context_actor_label": "Own move target"' in strings
    assert '"play.free_context_resource_label": "Own move focus"' in strings
    assert '"play.free_context_actor_detail": "Write how you test {name}; the current options do not name them directly."' in strings
    assert '"play.free_context_actor_leverage_detail": "You can reveal the leverage above, or write another way to test {name}."' in strings
    assert '"play.action_open_free_actor": "Write your own move for {name}"' in strings
    assert '"play.free_starters_label": "Starter lines"' in strings
    assert '"play.free_starter_actor_ask_label": "Ask directly"' in strings
    assert '"play.free_starter_actor_pressure_label": "Apply pressure"' in strings
    assert '"play.free_starter_inventory_show_label": "Show it"' in strings
    assert '"play.free_starter_inventory_ask_label": "Ask who fears it"' in strings
    assert '"play.free_starter_time_buy_label": "Buy time"' in strings
    assert '"play.free_starter_pressure_calm_label": "Calm first"' in strings
    assert '"play.free_starter_evidence_trace_label": "Trace the clue"' in strings
    assert '"play.free_starter_general_ask_label": "Ask a direct question"' in strings
    assert '"play.free_starter_general_pressure_label": "Name the risk"' in strings
    assert '"play.free_starter_general_time_label": "Hold the room"' in strings
    assert '"play.free_starter_general_ask_label": "直接问一句"' in strings
    assert '"play.free_starter_apply_title": "Use starter: {move}"' in strings
    assert '"play.action_open_free_resource": "Write your own move around {label}"' in strings
    assert '"play.action_free_actor_placeholder": "Write how you pull {name} into this move..."' in strings
    assert '"play.free_action_boundary_hint": "Write what others can see or hear here; put your real purpose in inner motive."' in strings
    assert '"play.action_target_label": "Who reacts"' in strings
    assert '"play.action_target_title": "This move tests {name}"' in strings
    assert '"play.action_target_detail_label": "Who reacts"' in strings
    assert '"play.action_target_detail_text": "This move tests {name} and shows how they react."' in strings
    assert '"play.move_receipt_signals_label": "What this move puts in play"' in strings
    assert '"play.move_receipt_signals_label": "这步行动正在推动什么"' in strings
    assert '"play.move_receipt_signals_label": "Who reacted and what changed"' not in strings
    assert '"play.resource_focus_cta": "Use this"' in strings
    assert '"play.resource_focus_active": "Using this"' in strings
    assert '"play.resource_focus_cta_count_one": "1 move uses this"' in strings
    assert '"play.resource_focus_cta_count_many": "{count} moves use this"' in strings
    assert '"play.resource_focus_active_count_one": "Showing 1 move"' in strings
    assert '"play.resource_focus_active_count_many": "Showing {count} moves"' in strings
    assert '"play.resource_focus_active_count": "Showing: {count}"' in strings
    assert '"play.resource_focus_cta_count_one": "1 usable move"' not in strings
    assert '"play.resource_focus_active_count": "Usable moves: {count}"' not in strings
    assert '"play.resource_focus_cta_count_one": "1 个行动会用到它"' in strings
    assert '"play.resource_focus_active_count_one": "正在显示 1 个行动"' in strings
    assert '"play.resource_focus_label": "Focus on resource"' in strings
    assert '"play.resource_focus_showing_label": "Moves about {name}"' in strings
    assert '"play.resource_focus_clear": "Show all moves"' in strings
    assert '"play.resource_focus_clear": "Clear"' not in strings
    assert '"play.resource_focus_evidence_label": "Evidence"' in strings
    assert '"play.resource_focus_time_title": "Show moves that buy, spend, or squeeze time"' in strings
    assert '"play.resource_focus_pressure_title": "Show moves that calm, raise, or redirect pressure"' in strings
    assert '"play.resource_focus_cta_none": "No preset move"' in strings
    assert '"play.resource_focus_active_none": "Write own move"' in strings
    assert '"play.resource_focus_active_none": "自写一步"' in strings
    assert '"play.resource_focus_time_match_detail_one": "1 current move can buy, spend, or squeeze time."' in strings
    assert '"play.resource_focus_time_match_detail_many": "{count} current moves can buy, spend, or squeeze time."' in strings
    assert '"play.resource_focus_pressure_match_detail_one": "1 current move can calm, raise, or redirect pressure."' in strings
    assert '"play.resource_focus_pressure_match_detail_many": "{count} current moves can calm, raise, or redirect pressure."' in strings
    assert '"play.resource_focus_evidence_match_detail_one": "1 current move can turn a clue or proof into leverage."' in strings
    assert '"play.resource_focus_evidence_match_detail_many": "{count} current moves can turn clues or proof into leverage."' in strings
    assert '"play.resource_focus_instruction": "Choose a matching move, or write your own."' in strings
    assert '"play.resource_focus_filter_note": "This only filters the current choices; no move is submitted yet."' in strings
    assert '"play.resource_focus_matches_label": "Matching moves"' in strings
    assert '"play.resource_focus_select_match": "Review move: {move}"' in strings
    assert '"play.resource_focus_select_match": "Select move: {move}"' not in strings
    assert '"play.gameplay_decision_cost_label": "Costs"' in strings
    assert '"play.gameplay_decision_upside_label": "Opens"' in strings
    assert '"play.gameplay_decision_shift_label": "Shifts"' in strings
    assert '"play.option_forecast_kicker": "预计影响"' in strings
    assert '"play.gameplay_decision_forecast_label": "预计影响"' in strings
    assert '"play.gameplay_decision_upside_label": "机会"' in strings
    assert '"play.gameplay_decision_shift_label": "变化"' in strings
    assert '"play.gameplay_impact_label": "What changed"' in strings
    assert '"play.feedback_impact_hint": "Read the result first, then choose from what it opened."' in strings
    assert '"play.outcome_next_hint": "Use this to choose the next move"' in strings
    assert '"play.feedback_impact_cost_label": "Cost / risk"' in strings
    assert '"play.feedback_impact_opened_label": "Opened"' in strings
    assert '"play.feedback_result_layer_label": "Result from your last move"' in strings
    assert '"play.feedback_key_consequence_label": "Main result"' in strings
    assert '"play.feedback_next_choice_label": "Next moves opened by it"' in strings
    assert '"play.feedback_next_choice_changed_label": "Action menu changed"' in strings
    assert '"play.feedback_next_choice_changed_detail": "The people, clues, or pressure that changed now shape these choices."' in strings
    assert "Why these moves are here" not in strings
    assert "New moves opened" not in strings
    assert '"play.gameplay_impact_label": "发生了什么"' in strings
    assert '"play.feedback_impact_hint": "先看已发生的结果，再用它打开的行动继续。"' in strings
    assert '"play.feedback_result_layer_label": "上一步造成的结果"' in strings
    assert '"play.feedback_key_consequence_label": "主要结果"' in strings
    assert '"play.outcome_next_hint": "用它决定下一步"' in strings
    assert '"play.feedback_next_choice_label": "因此出现的下一步"' in strings
    assert '"play.feedback_next_choice_changed_label": "行动菜单已变化"' in strings
    assert '"play.feedback_next_choice_changed_detail": "刚变化的人物、线索或压力正在影响这些选择。"' in strings
    assert '"play.impact_wary": "starts watching you"' in strings
    assert '"play.impact_broken": "turns against you"' in strings
    assert '"play.impact_wary": "gets wary"' not in strings
    assert '"play.impact_focus_actor_title": "Show moves that test {name}"' in strings
    assert '"play.feedback_pending_receipt_label": "Move sent"' in strings
    assert '"play.feedback_pending_reaction_label": "Room reacting"' in strings
    assert '"play.feedback_pending_update_label": "Next moves forming"' in strings
    assert '"play.feedback_pending_cue_people": "Reading people"' in strings
    assert '"play.feedback_pending_cue_target": "Reading {target}"' in strings
    assert '"play.feedback_pending_cue_state": "Checking clues and pressure"' in strings
    assert '"play.feedback_pending_cue_next": "Shaping next moves"' in strings
    assert '"play.feedback_pending_cue_people": "观察人物反应"' in strings
    assert '"play.feedback_pending_cue_state": "检查线索和压力"' in strings
    assert '"play.feedback_pending_next_hint": "The next moves come from the people, clues, and pressure this move changes."' in strings
    assert '"play.feedback_pending_next_hint": "下一组行动会从刚刚被改变的人物、线索和压力里长出来。"' in strings
    assert '"play.option_opened_by_change_label": "From last change"' in strings
    assert '"play.option_opened_by_change_label": "来自刚才变化"' in strings
    assert 'data-play-room-reacting-cues="true"' in panels
    assert 'data-play-room-reacting-cue="true"' in panels
    assert 'data-play-option-opened-by-change="true"' in panels
    assert 'data-play-outcome-receipt="true"' in story_beat
    assert 'data-play-outcome-receipt-mode={compact ? "compact" : "summary"}' in story_beat
    assert 'data-play-outcome-receipt-item="true"' in story_beat
    assert "data-play-outcome-receipt-tone={item.tone ?? \"neutral\"}" in story_beat
    assert "const outcomeReceiptA11yItems" in story_beat
    assert "aria-label={outcomeReceiptA11yLabel}" in story_beat
    assert "fetch(" not in envelope
    for forbidden in ("provider", "model", "schema", "token", "fallback", "debug"):
        assert forbidden not in envelope.casefold()


def test_play_selected_action_expands_card_in_place_with_explicit_confirm() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    action_option = (ROOT / "frontend2/src/pages/play/components/action-option-card.tsx").read_text()
    confirmation = (ROOT / "frontend2/src/pages/play/components/selected-move-confirmation.tsx").read_text()
    advisor_panel = (ROOT / "frontend2/src/pages/play/components/advisor-panel.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    selected_confirm_start = panels.index("const renderSelectedOptionConfirm")
    selected_confirm = panels[
        selected_confirm_start : panels.index("\n\n  return (", selected_confirm_start)
    ]
    selected_confirm_styles = styles[
        styles.index("optionCardConfirmPanel") : styles.index("optionCardSecondaryRow")
    ]
    selected_button_styles = styles[
        styles.index("optionPrimaryCommitButton") : styles.index("optionQuietChangeButton")
    ]

    assert 'data-play-decision-tray="true"' not in panels
    assert 'data-play-action-card-expanded={isSelected ? "true" : undefined}' in panels
    assert 'data-play-action-card-select-cue="true"' in panels
    assert 'data-play-action-card-detail="true"' in action_option
    assert 'data-play-action-card-title="true"' in panels
    assert 'data-play-action-card-body="true"' in panels
    assert "function optionTagGuide" in panels
    assert 'data-play-action-card-intent="true"' in panels
    assert 'data-play-action-card-detail-section="intent"' in action_option
    assert 'data-play-action-intent-chip="true"' in action_option
    assert 'data-play-action-intent-detail="true"' in action_option
    assert 'data-play-turn-guide="true"' in panels
    assert 'title={optionIntentGuide?.description}' in panels
    assert 'aria-label={optionIntentGuide?.description}' in panels
    assert 'data-play-action-card-detail-section="result"' in action_option
    assert 'data-play-action-card-detail-section="forecast"' in action_option
    assert 'data-play-action-card-detail-section="why-now"' in action_option
    assert 'data-play-action-card-confirm="true"' in panels
    assert 'data-play-action-card-confirm-panel="true"' in panels
    assert 'data-play-selected-move-submit-summary="true"' in confirmation
    assert 'data-play-action-option-card="true"' in panels
    assert 'data-play-action-collapse-zone="true"' in panels
    assert 'data-play-inner-motive-primary="true"' in panels
    assert 'data-play-inner-motive-panel={context === "option" ? "true" : undefined}' in panels
    assert 'data-play-inner-motive-frame={context === "option" ? "true" : undefined}' in panels
    assert 'data-play-inner-motive-writing-hint={context === "option" ? "true" : undefined}' in panels
    assert "isWritingOptionDiary ? null : (" in selected_confirm
    assert 'block: "nearest"' in panels
    assert 'block: "center",\n        behavior: prefersReducedMotion ? "auto" : "smooth",' not in panels[
        panels.index("const focusDiaryTextarea") : panels.index("const renderDiaryAttachPreview")
    ]
    assert 'data-play-selected-move={isSelected ? "true" : undefined}' in panels
    assert "pickedOptionForecasts.filter((forecast) => !forecast.detail).slice(0, 3)" in panels
    assert "const selectedOptionSubmitForecasts = selectedOptionForecasts.filter((chip) => !chip.detail)" in panels
    assert "selectedOptionSubmitForecasts.slice(0, 2).map((chip) => chip.label).join(\" · \")" in panels
    assert 'document.querySelector<HTMLElement>("[data-play-selected-move=\'true\']")' in panels
    assert "headerHeight - 12" in panels
    assert "window.scrollTo({ top, left: 0, behavior })" in panels
    assert "selectedOptionIndex])" in panels
    assert 'data-play-primary-commit="true"' in panels
    assert 'data-play-support-actions="true"' in panels
    assert 'data-play-move-receipt="true"' in panels
    assert 'data-play-room-reacting="true"' in panels
    assert 'data-play-feedback-timeline="true"' in panels
    assert 'data-play-feedback-timeline-hint="true"' in panels
    assert 'data-play-feedback-step={step.id}' in panels
    assert 'data-play-feedback-step-state={step.state}' in panels
    assert 'data-play-pending-reaction-panel="true"' in panels
    assert "const showStandardOptions = !armedCard && !showFreeComposer && !showPickedReflection" in panels
    assert ".filter(({ i }) => focusedOptionIndex" not in panels
    assert "handleActionAreaPointerDownCapture" in panels
    assert "target.closest(" in panels
    assert 'setSelectedOptionIndex(i)' in panels
    assert 'setSelectedOptionIndex(null)' in panels
    assert "optionCardConfirmPanel" in styles
    assert "optionCardConfirmRail" in styles
    assert "optionCardSubmitSummary" in styles
    assert "optionCardSubmitSummaryTarget" in styles
    assert "optionCardPrimaryActionGrid" in styles
    assert "optionTitleLine" in styles
    assert "optionActionText" in styles
    assert "optionExpandedDetailSection" in styles
    assert "optionExpandedDetailSectionCompact" in styles
    assert 'gridTemplateColumns: "auto minmax(0, 1fr)"' not in selected_confirm_styles
    assert "borderRadius: 999" in selected_confirm_styles
    assert "minHeight: 40" in selected_button_styles
    assert "optionExpandedDetail" in styles
    assert "optionPrimaryCommitButton" in styles
    assert "optionMotiveCommitButton" in styles
    assert "diarySubmitButton" in styles
    assert "diaryIntentFrame" in styles
    assert "diaryIntentRow" in styles
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
    assert "optionForecasts.length && !isSelected" in panels
    assert "<ActionCollapsedForecast chips={optionForecasts} />" in panels
    assert 'data-gameplay-action-forecast-summary="true"' in action_option
    assert "actionTarget && !isSelected" in panels
    option_expand_cue = styles[styles.index("optionExpandCue:") : styles.index("optionExpandCueActive:")]
    assert 'borderRadius: 5' in option_expand_cue
    assert 'background: "rgba(213,154,62,0.10)"' in option_expand_cue
    assert 'borderBottomStyle: "solid"' in option_expand_cue
    assert "function hintEchoesForecastChips" in action_option
    assert "const showNarrativeResult = hint.trim().length > 0 && !hintEchoesForecastChips(hint, forecasts)" in action_option
    assert 'hint || t("play.preview_action_risk_default")' not in action_option
    assert "gameplayForecastInline" in styles
    assert "gameplayForecastInlineLabel" in styles
    assert '"play.option_forecast_kicker": "Likely impact"' in strings
    assert '"play.option_intent_label": "Move type"' in strings
    assert '"play.option_intent_probe": "Test the room first. Use it when you need information or a reaction."' in strings
    assert '"play.option_intent_confront": "Apply direct pressure. Use it when delay would make things worse."' in strings
    assert '"play.option_intent_stabilize": "Stabilize or redirect the room. Use it when you need time, calm, or cover for someone."' in strings
    assert '"play.option_intent_label": "行动意图"' in strings
    assert '"play.option_intent_probe": "先试探局面，适合在需要信息或确认对方反应时使用。"' in strings
    assert '"play.option_intent_stabilize": "稳住或转移局面，适合在需要争取时间、降温或保护某人时使用。"' in strings
    assert '"play.turn_guide_idle_title": "Choose one move"' in strings
    assert '"play.turn_guide_idle_detail": "Read the goal and pressure above, then open a card to review it before submitting."' in strings
    assert '"play.turn_guide_idle_detail": "Read the goal and pressure above, then select a card to submit."' not in strings
    assert '"play.turn_guide_idle_detail_with_leverage": "Read the goal and pressure; review a card, prepare leverage, or write your own."' in strings
    assert '"play.turn_guide_idle_detail_with_leverage": "Read the goal and pressure; select a card, prepare leverage, or write your own."' not in strings
    assert '"play.turn_guide_after_impact_title": "Choose from what changed"' in strings
    assert '"play.turn_guide_after_impact_detail": "These moves come from the people, clues, and pressure you just changed."' in strings
    assert "hasRecentImpact?: boolean" in panels
    assert "hasRecentImpact\n                    ? t(\"play.turn_guide_after_impact_title\")" in panels
    assert "hasRecentImpact={showGameplayImpactSummary}" in play_page
    assert 'data-play-turn-guide-detail="true"' in panels
    assert '"play.action_status_ready": "Move controls ready."' in strings
    assert '"play.turn_guide_idle_title": "选择一个行动"' in strings
    assert '"play.turn_guide_idle_detail": "先看上方目标和压力，再打开卡片复核；展开后再提交。"' in strings
    assert '"play.turn_guide_idle_detail": "先看上方目标和压力，再选中卡片提交。"' not in strings
    assert '"play.turn_guide_idle_detail_with_leverage": "先看目标和压力；打开卡片复核、准备反将牌，或自己写一句。"' in strings
    assert '"play.turn_guide_idle_detail_with_leverage": "先看目标和压力；选中卡片、准备反将牌，或自己写一句。"' not in strings
    assert '"play.turn_guide_after_impact_title": "根据变化选下一步"' in strings
    assert '"play.turn_guide_after_impact_detail": "这些行动来自刚刚改变的人物、线索和压力。"' in strings
    assert '"play.option_shortcut_title": "Press {key} to review; submit after opening"' in strings
    assert '"play.option_shortcut_title": "Press {key} to select; then submit"' not in strings
    assert '"play.option_shortcut_title": "按 {key} 查看；展开后再提交"' in strings
    assert '"play.option_shortcut_title": "按 {key} 选择；然后提交"' not in strings
    assert '"play.selected_move_ready_label": "Ready to submit"' in strings
    assert '"play.selected_move_ready_label": "准备提交"' in strings
    assert '"play.selected_move_room_chip": "Affects the room"' in strings
    assert '"play.selected_move_room_chip": "影响全场"' in strings
    assert '"play.action_open_free": "Write your own move"' in strings
    assert '"play.action_open_free_hint": "Write a public line or action."' in strings
    assert '"play.action_open_free_hint": "Say or do something else."' not in strings
    assert '"play.action_open_free_hint": "写别人能看见或听见的一步。"' in strings
    assert '"play.action_open_free_hint": "不用预设，直接写一句。"' not in strings
    assert '"play.action_open_free_title": "Open your own move input"' in strings
    assert (
        '"play.turn_guide_free_ready_detail": '
        '"Review this public move. Submit it, or add what you secretly mean."' in strings
    )
    assert '"play.turn_guide_free_ready_detail": "先复核这句公开行动，再提交或补一句真实动机。"' in strings
    assert "Commit it, or add what you secretly mean." not in strings
    assert "Write custom move" not in strings
    assert "write a custom move" not in strings
    assert "Custom move target" not in strings
    assert "Free action under review" not in strings
    assert "Pick a line" not in strings
    assert "Change choice" not in strings
    assert "change choice" not in strings
    assert '"play.selected_move_kicker": "Selected move"' in strings
    assert '"play.selected_move_commit_cta": "Submit this move"' in strings
    assert '"play.selected_move_commit_cta": "提交这个行动"' in strings
    assert '"play.selected_move_commit_hint": "Room reacts next"' in strings
    assert '"play.selected_move_commit_hint": "接着看房间反应"' in strings
    assert "optionPrimaryButtonLabel" in styles
    assert "optionPrimaryButtonHint" in styles
    assert 't("play.selected_move_commit_hint")' in panels
    assert '"play.turn_guide_selected_detail": "Review this move. Submit it, or add what you secretly mean."' in strings
    assert '"play.turn_guide_selected_named_detail": "Review this move. Submit it, or add inner motive."' in strings
    assert '"play.turn_guide_inner_motive_title": "Add private motive"' in strings
    assert (
        '"play.turn_guide_inner_motive_detail": '
        '"Write what you privately want. NPCs will not hear it; submit with motive or go back."' in strings
    )
    assert '"play.turn_guide_selected_detail": "先复核这一步，再提交或补一句真实动机。"' in strings
    assert '"play.turn_guide_inner_motive_title": "补内心动机"' in strings
    assert '"play.turn_guide_inner_motive_detail": "写下你私下想达成什么；NPC 不会听见。可以带着动机提交或返回行动。"' in strings
    assert 'const optionMotiveNeedsText = context === "option" && !diary.trim()' in panels
    assert 'data-play-inner-motive-disabled-reason="true"' in panels
    assert "inner_motive_submit_disabled_hint" in panels
    assert "diaryDisabledReason" in styles
    assert 'isWritingOptionDiary\n      ? t("play.turn_guide_inner_motive_title")' in panels
    assert 'isWritingOptionDiary\n      ? t("play.turn_guide_inner_motive_detail")' in panels
    assert '"play.option_change_cta": "Choose another move"' in strings
    assert '"play.option_change_cta": "换一个行动"' in strings
    assert '"play.action_submit": "Submit this move →"' in strings
    assert '"play.action_submit": "提交这个行动 →"' in strings
    assert '"play.leverage_resource_label": "Leverage card"' in strings
    assert '"play.leverage_summary_chip_risk": "Risk"' in strings
    assert '"play.leverage_card_risk": "Everyone will remember"' in strings
    assert '"play.leverage_summary_chip_risk": "Memory risk"' not in strings
    assert '"play.leverage_card_risk": "Room remembers"' not in strings
    assert '"play.leverage_summary_action": "Reveal against {target}"' in strings
    assert '"play.leverage_summary_choose": "Choose a leverage card"' in strings
    assert '"play.turn_guide_leverage_title": "Leverage ready: {target}"' in strings
    assert 't("play.action_status_ready")' in panels
    assert "Trump card" not in strings
    assert "trump card" not in strings
    assert "Not submitted yet" not in strings
    assert '"play.inner_motive_cta": "Add inner motive"' in strings
    assert '"play.inner_motive_button_hint": "Say what you secretly mean"' in strings
    assert '"play.inner_motive_attached_hint": "Will submit with this move"' in strings
    assert '"play.diary_skip": "Back to move"' in strings
    assert '"play.diary_skip": "返回行动"' in strings
    assert '"play.diary_public_move_label": "Public move"' in strings
    assert '"play.diary_public_move_label": "公开行动"' in strings
    assert '"play.diary_private_motive_label": "Private motive"' in strings
    assert '"play.diary_private_motive_label": "真实意图"' in strings
    assert '"play.private_intent_hint": "What you secretly mean; NPCs do not hear it"' in strings
    assert '"play.diary_label_hint": "What you secretly mean; others do not hear it."' in strings
    assert '"play.diary_writing_hint": "Write the goal, suspicion, or person you are protecting; do not repeat the public move."' in strings
    assert '"play.diary_writing_hint": "写目标、怀疑或你要保护的人；不要重复公开行动。"' in strings
    assert '"play.diary_attach_empty": "Add inner motive"' in strings
    assert '"play.diary_attach_empty": "补内心动机"' in strings
    assert '"play.diary_attach_empty_hint": "Say what you secretly mean."' in strings
    assert "Use inner motive" not in strings
    assert '"play.inner_motive_submit_cta": "Submit with motive"' in strings
    assert '"play.inner_motive_submit_cta": "带着动机提交"' in strings
    assert '"play.inner_motive_submit_disabled_hint": "Write a private motive first to submit with motive."' in strings
    assert '"play.inner_motive_submit_disabled_hint": "先写一句真实动机，才能带着动机提交。"' in strings
    assert '"play.advisor_card_name": "Dana Vale"' in strings
    assert '"play.advisor_card_ask_detail": "Get a low-risk read; you still choose the move"' in strings
    assert '"play.advisor_card_ask_detail": "低风险读局；最后行动仍由你决定"' in strings
    assert 'data-play-advisor-empty-primer="true"' in advisor_panel
    assert "const [draftSuggestion, setDraftSuggestion] = useState<string | null>(null)" in advisor_panel
    assert "setDraftSuggestion(suggestion)" in advisor_panel
    assert 'data-play-advisor-draft-hint="true"' in advisor_panel
    assert 'data-play-advisor-suggestion-instruction="true"' in advisor_panel
    assert "advisorEmptyPrimer" in styles
    assert "advisorEmptyPrimerTitle" in styles
    assert "advisorSuggestionInstruction" in styles
    assert "advisorDraftHint" in styles
    assert '"play.advisor_title": "Ask for a second read"' in strings
    assert '"play.advisor_empty_primer_title": "Pick a question first"' in strings
    assert '"play.advisor_empty_primer_body": "Your friend can flag risk, wording, and pushback; you still choose the move."' in strings
    assert '"play.advisor_suggestions_label": "Quick questions"' in strings
    assert '"play.advisor_suggestions_instruction": "Tap one to draft it, then edit before asking."' in strings
    assert '"play.advisor_suggestion_apply_title": "Draft suggested question: {question}"' in strings
    assert '"play.advisor_suggestion_insert": "Draft this"' in strings
    assert '"play.advisor_title": "Your outsider friend"' not in strings
    assert '"play.advisor_draft_hint": "Suggested question inserted. Edit it, then ask; your move stays unsubmitted."' in strings
    assert '"play.advisor_draft_hint": "Suggested question inserted. Edit it, then ask."' not in strings
    assert '"play.advisor_draft_hint": "已插入建议问题，可以改一句再问朋友；这不会提交你的行动。"' in strings
    assert '"play.advisor_draft_hint": "已插入建议问题，可以改一句再问朋友。"' not in strings
    assert '"play.advisor_send": "Ask friend"' in strings
    assert '"play.advisor_send": "问朋友"' in strings
    assert '"play.oracle_button": "Deep read"' in strings
    assert '"play.oracle_button_with_cost": "Deep read · spends 1 turn"' in strings
    assert '"play.oracle_inline_summary": "Deep read spends 1 turn: {before} → {after} turns left"' in strings
    assert '"play.oracle_tip_active": "Spend 1 turn for a deeper read from your friend ({turns} turns left)"' in strings
    assert '"play.oracle_button": "Oracle read"' not in strings
    assert '"play.oracle_button_with_cost": "Oracle read · costs 1 turn"' not in strings
    assert '"play.oracle_button": "深度读局"' in strings
    assert '"play.oracle_button_with_cost": "深度读局 · 消耗 1 回合"' in strings
    assert '"play.oracle_inline_summary": "深度读局会消耗 1 回合：{before} → {after} 回合"' in strings
    assert '"play.oracle_button": "看穿模式"' not in strings
    assert '"play.move_receipt_title": "Your move"' in strings
    assert '"play.room_reacting_title": "The room is reacting"' in strings
    assert '"play.resolve_status_room": "Reading the room"' in strings
    assert '"play.resolve_status_room": "The room is reacting"' not in strings
    assert '"play.option_expand_cta": "Review move"' in strings
    assert '"play.option_expand_cta": "Select move"' not in strings
    assert '"play.option_expand_cta": "查看行动"' in strings
    assert '"play.option_expand_cta": "选择行动"' not in strings
    assert '"play.option_expanded_detail_label": "Consequence"' in strings
    assert '"play.option_expanded_result_label": "Likely result"' in strings


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


def test_play_has_jump_to_action_affordance_when_choices_are_below_viewport() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    action_jump = (ROOT / "frontend2/src/pages/play/components/play-action-jump.tsx").read_text()
    action_jump_utils = (ROOT / "frontend2/src/pages/play/components/play-action-jump-utils.ts").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "const [showActionJump, setShowActionJump] = useState(false)" in play_page
    assert "!story || busy || advisorOpen || ending" in play_page
    assert "!story || !compactPlayChrome || busy || advisorOpen || ending" not in play_page
    assert "currentActionAreaVisible" in play_page
    assert "isPlayActionAreaAwayFromViewport(actionArea)" in play_page
    assert "isPlayElementAwayFromViewport(impactSummary)" in play_page
    assert "impactSummaryVisible" in play_page
    assert "&& !impactSummaryVisible" in play_page
    assert "const actionJumpDetail =" in play_page
    assert "const handleActionJump = useCallback" in play_page
    assert "setShowActionJump(false)" in play_page
    assert "scrollToPlayImpactSummaryOrAction()" in play_page
    assert "scrollToPlayActionArea()" in play_page
    assert "onClick={handleActionJump}" in play_page
    assert "stage={gameplayLoopStage}" in play_page
    assert "detail={actionJumpDetail}" in play_page
    assert "useCompactLayout(\"(max-width: 680px)\")" in action_jump
    assert "compactDetail?: string" in action_jump
    assert "const detailCopy = compactJump ? compactDetail?.trim() : detail?.trim()" in action_jump
    assert 'data-play-action-jump="true"' in action_jump
    assert "data-play-action-jump-stage={stage}" in action_jump
    assert 'data-play-action-jump-compact={compactJump ? "true" : "false"}' in action_jump
    assert 'data-play-action-jump-detail="true"' in action_jump
    assert "onPointerDown={onClick}" in action_jump
    assert "isPlayElementAwayFromViewport" in action_jump_utils
    assert "scrollToPlayActionArea" in action_jump_utils
    assert "scrollToPlayImpactSummaryOrAction" in action_jump_utils
    assert "[data-play-action-area='true']" in action_jump_utils
    assert "[data-gameplay-impact-summary='true']" in action_jump_utils
    assert "scrollToPlayActionArea()" in action_jump_utils
    assert "const upperComfortEdge = headerHeight + 64" in action_jump_utils
    assert "const lowerComfortEdge = window.innerHeight - 24" in action_jump_utils
    assert "rect.bottom < upperComfortEdge" in action_jump_utils
    assert "rect.bottom > window.innerHeight" not in action_jump_utils
    assert "actionJumpButton" in styles
    assert "actionJumpButtonCompact" in styles
    assert "actionJumpCopyCompact" in styles
    assert "actionJumpDetail" in styles
    assert "actionJumpArrow" in styles
    assert "actionJumpArrowCompact" in styles
    assert 'position: "fixed"' in styles[styles.index("actionJumpButton") : styles.index("actionJumpKicker")]
    assert "maxWidth: 430" in styles[styles.index("actionJumpButton") : styles.index("actionJumpKicker")]
    assert '"play.action_jump_kicker": "Choices ready"' in strings
    assert '"play.action_jump_label": "Choose your move"' in strings
    assert '"play.action_jump_label": "Jump to your move"' not in strings
    assert '"play.action_jump_detail_choose": "Playable choices are ready below the story."' in strings
    assert '"play.action_jump_detail_update": "Review this turn\'s changes before choosing."' in strings


def test_empty_trump_card_resource_stays_out_of_main_action_surface() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()

    assert "const showLeverageRail = leverageCards.length > 0 && !commitmentSurfaceOpen" in panels
    assert "roleHasNoLeverage) && !commitmentSurfaceOpen" not in panels
    assert "roleHasNoLeverage ||" not in panels


def test_leverage_resource_reads_as_actionable_player_resource() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    leverage_summary = (ROOT / "frontend2/src/pages/play/components/leverage-summary.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()

    assert 'data-play-leverage-rail="true"' in panels
    assert 'data-play-leverage-state={playableLeverageCards.length > 0 ? "playable" : "empty"}' in panels
    assert 'data-play-leverage-summary="true"' in leverage_summary
    assert 'data-play-leverage-summary-chips="true"' in leverage_summary
    assert 'data-play-leverage-card="true"' in panels
    assert 'data-play-leverage-reveal="true"' in panels
    assert 'data-play-leverage-reveal-cta="true"' in panels
    assert "leverageSummaryChips" in styles
    assert "leverageSummaryChipLabel" in styles
    assert "leverageSummaryChipValue" in styles
    assert 'background: "linear-gradient(135deg, rgba(245,200,120,0.13)' in styles


def test_ending_screen_prioritizes_result_text_before_illustration() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    ending_module = (ROOT / "frontend2/src/pages/play/components/ending-screen.tsx").read_text()
    option_label = (ROOT / "frontend2/src/pages/play/play-option-label.ts").read_text()
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    ending_screen = ending_module[ending_module.index("export function EndingScreen") : ending_module.index("function displayEndingLabel")]

    assert 'from "./components/ending-screen"' in play_page
    assert 'from "./play-option-label"' in play_page
    assert 'from "../play-option-label"' in panels
    assert "export function parseOptionLabel" in option_label
    assert "export function EndingScreen" not in panels
    assert "buildFallbackEndingRecap" not in panels
    assert "function displayEndingLabel" not in panels
    assert "Illustrated banner is secondary to the result text" in ending_screen
    assert 'data-play-ending-actions="true"' in ending_screen
    assert 'data-play-ending-next-step-label="true"' in ending_screen
    assert 'data-play-ending-next-step-hint="true"' in ending_screen
    assert 'data-play-ending-illustration="true"' in ending_screen
    assert ending_screen.index("style={ppStyles.endingPassage}") < ending_screen.index('data-play-ending-actions="true"')
    assert ending_screen.index('data-play-ending-next-step-label="true"') < ending_screen.index("style={ppStyles.endingActionsRow}")
    assert ending_screen.index('data-play-ending-next-step-hint="true"') < ending_screen.index("style={ppStyles.endingActionsRow}")
    assert ending_screen.index('data-play-ending-actions="true"') < ending_screen.index('data-play-ending-illustration="true"')
    assert ending_screen.index('data-play-ending-illustration="true"') < ending_screen.index("...ppStyles.endingHero")
    assert "const fallbackRecap = mergedHighlights.length === 0" in ending_screen
    assert 'data-play-ending-recap="fallback"' in ending_screen
    assert "buildFallbackEndingRecap(messages)" in ending_screen
    assert "parseOptionLabel(message.content)" in ending_module
    assert 'height: 150' in styles[styles.index("endingHero") : styles.index("endingSplashOverlay")]
    assert 'padding: "10px 0 28px"' in styles[styles.index("endingCardInner") : styles.index("endingLabelChip")]
    assert 'marginBottom: 22' in styles[styles.index("endingActions") : styles.index("endingActionsRow")]
    assert "endingActionsLabel" in styles
    assert "endingActionsHint" in styles
    assert "endingRecapSection" in styles
    assert '"play.ending_recap_title": "How this run got here"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    assert '"play.ending_next_steps": "Next steps"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    assert '"play.ending_next_steps_hint": "Share the ending you reached, or replay from the same opening."' in (
        ROOT / "frontend2/src/shared/lib/i18n.ts"
    ).read_text()


def test_play_ending_fixture_mounts_real_ending_screen() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    fixture = (ROOT / "frontend2/src/pages/play/components/play-ending-fixture.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert '| { name: "playEndingFixture" }' in routes
    assert 'segments[1] === "play-ending"' in routes
    assert 'return "#/qa/play-ending"' in routes
    assert 'import { PlayEndingFixture } from "../pages/play/components/play-ending-fixture"' in app
    assert 'case "playEndingFixture"' in app
    assert "<PlayEndingFixture" in app
    assert 'data-play-ending-fixture="true"' in fixture
    assert 'data-play-ending-fixture-case="highlight"' in fixture
    assert 'data-play-ending-fixture-case="recap"' in fixture
    assert 'import { EndingScreen } from "./ending-screen"' in fixture
    assert fixture.count("<EndingScreen") == 2
    assert "const HIGHLIGHT_ENDING: NarrativeEnding" in fixture
    assert "const RECAP_ENDING: NarrativeEnding" in fixture
    assert "highlights: []" in fixture
    assert "branches: [" in fixture
    assert "new Set([4, 6])" in fixture
    assert 'shareCopied={copiedCase === "highlight"}' in fixture
    assert 'shareCopied={copiedCase === "recap"}' in fixture
    assert 'data-play-ending-actions="true"' not in fixture
    assert 'data-play-ending-illustration="true"' not in fixture
    assert 'components/play-ending-fixture.tsx' in readme
    assert "#/qa/play-ending" in readme


def test_latest_narrator_beat_has_lightweight_digest_before_next_action() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    story_beat_module = (ROOT / "frontend2/src/pages/play/components/story-beat.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    story_beat = story_beat_module[
        story_beat_module.index("export function StoryBeat") : story_beat_module.index("  // player move (echoed action)")
    ]

    assert "const showGameplayImpactSummary =" in play_page
    assert "suppressLatestFeedbackDigest={" in play_page
    assert "showGameplayImpactSummary" in play_page
    assert "suppressLatestFeedbackDigest?: boolean" in story_beat
    assert "const latestDigestPulses" in story_beat
    assert "const shouldCompactSceneBanner =" in story_beat
    assert "latestOptionCount > 0" in story_beat
    assert "intensity !== \"peak\"" in story_beat
    assert "const showLatestBeatDigest" in story_beat
    assert "!suppressLatestFeedbackDigest" in story_beat
    assert "const latestDigestA11yItems" in story_beat
    assert "const latestDigestA11yLabel" in story_beat
    assert "const isLatestActionableBeat =" in story_beat
    assert "ppStyles.narratorBeatActionable" in story_beat
    assert "ppStyles.latestBeatDigestActionable" in story_beat
    assert 'aria-label={latestDigestA11yLabel}' in story_beat
    assert 'data-play-latest-beat-digest-hint="true"' in story_beat
    assert "latestDigestPulses.length > 0 || hasDelta || latestOptionCount > 0" in story_beat
    assert "hasDelta && latestDigestPulses.length === 0" in story_beat
    assert "outcomeItems.length > 0 && !suppressLatestFeedbackDigest" in story_beat
    assert 'data-play-latest-beat-digest="true"' in story_beat
    assert "data-play-latest-beat-digest-pulse={pulse.npc_id}" in story_beat
    assert 'data-play-latest-beat-digest-options="true"' in story_beat
    assert 'data-play-segment-banner-density={compact ? "compact" : "full"}' in story_beat_module
    assert "compact={shouldCompactSceneBanner}" in story_beat
    assert "narratorBeatActionable" in styles
    assert "beatSceneBannerCompact" in styles
    assert "latestBeatDigest" in styles
    assert "latestBeatDigestActionable" in styles
    assert "latestBeatDigestHint" in styles
    assert "latestBeatDigestItems" in styles
    assert '"play.latest_beat_digest_label": "Current scene"' in strings
    assert '"play.latest_beat_digest_hint": "Read this before choosing."' in strings
    assert '"play.latest_beat_digest_next": "Next"' in strings
    assert '"play.latest_beat_digest_options": "{count} choices ready"' in strings


def test_play_long_history_fixture_exercises_action_jump_with_real_action_area() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    action_state = (ROOT / "frontend2/src/pages/play/components/play-action-state-fixture.tsx").read_text()
    fixture = (ROOT / "frontend2/src/pages/play/components/play-long-history-fixture.tsx").read_text()
    action_jump = (ROOT / "frontend2/src/pages/play/components/play-action-jump.tsx").read_text()
    action_jump_utils = (ROOT / "frontend2/src/pages/play/components/play-action-jump-utils.ts").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

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
    assert "type LongHistoryOutcome" in fixture
    assert "function splitHistoryBeat(beat: string): { label: string; body: string }" in fixture
    assert 'return { label: "You chose", body: beat.replace(/^You chose\\s+/, "") }' in fixture
    assert 'normalizedLabel === "Opening beat"' in fixture
    assert '? "Opening"' in fixture
    assert 'normalizedLabel === "Changed"' in fixture
    assert '? "After your move"' in fixture
    assert 'normalizedLabel === "Next beat"' in fixture
    assert '? "Next scene"' in fixture
    assert 'data-play-long-history-beat="true"' in fixture
    assert "data-play-long-history-beat-kind={parsedBeat.label.toLowerCase().replace(/\\s+/g, \"-\")}" in fixture
    assert "longHistoryBeatLabel" in fixture
    assert "longHistoryBeatBody" in fixture
    assert "longHistoryBeatLabel" in styles
    assert "longHistoryBeatBody" in styles
    assert "nextFocus: string" in fixture
    assert "longHistoryOutcomeForMove(submittedMove)" in fixture
    assert "hasRecentImpact={!!outcome}" in fixture
    assert "data-play-long-history-result-feedback=\"true\"" in fixture
    assert "data-play-long-history-result-item=\"true\"" in fixture
    assert 'data-play-long-history-next-focus="true"' in fixture
    assert "Next choice:" in fixture
    assert "Use the fixed timestamp to pressure the door story instead of asking broad questions." in fixture
    assert "Use the control-door clue while the sponsor is still answering in public." in fixture
    assert "Return to proof now that the hallway is watched." in fixture
    assert "outcomeReceiptNextFocus" in styles
    assert "outcomeReceiptNextValue" in styles
    assert "scrollIntoView({ block: \"start\", behavior: \"smooth\" })" in fixture
    assert "Result landed. The next action set is ready." not in fixture
    assert "<ActionArea" in fixture
    assert "<PlayActionJumpButton" in fixture
    assert 'stage={outcome ? "update" : "choose"}' in fixture
    assert 'detail={outcome ? t("play.action_jump_detail_update") : t("play.action_jump_detail_choose")}' in fixture
    assert (
        'compactDetail={outcome ? t("play.action_jump_detail_update_compact") '
        ': t("play.action_jump_detail_choose_compact")}' in fixture
    )
    assert "scrollToPlayActionArea()" in fixture
    assert "isPlayActionAreaAwayFromViewport(actionArea)" in fixture
    assert 'data-play-action-jump="true"' in action_jump
    assert "data-play-action-jump-stage={stage}" in action_jump
    assert "compactDetail?: string" in action_jump
    assert "compactJump ? compactDetail?.trim() : detail?.trim()" in action_jump
    assert "window.scrollTo" in action_jump_utils
    assert '"play.action_jump_detail_choose_compact": "Tap to choose now."' in strings
    assert '"play.action_jump_detail_update_compact": "Tap to review, then choose."' in strings
    for forbidden in ("provider", "model", "schema", "token", "fallback", "deterministic"):
        assert forbidden not in fixture.casefold()


def test_narrative_display_text_cleanup_is_shared_by_play_and_replay() -> None:
    cleanup = (ROOT / "frontend2/src/shared/lib/narrative-display-text.ts").read_text()
    story_beat = (ROOT / "frontend2/src/pages/play/components/story-beat.tsx").read_text()
    replay = (ROOT / "frontend2/src/pages/replay/replay-page.tsx").read_text()

    assert "export function cleanNarrativeDisplayText(text: string): string" in cleanup
    assert 'replace(/([.!?])\\.+(?=\\s|[A-Z])/g, "$1")' in cleanup
    assert 'replace(/([!?])\\.(?=\\s|[A-Z])/g, "$1")' in cleanup
    assert 'replace(/([.!?])([A-Z][a-z])/g, "$1 $2")' in cleanup
    assert 'import { cleanNarrativeDisplayText } from "../../../shared/lib/narrative-display-text"' in story_beat
    assert "{cleanNarrativeDisplayText(message.content)}</div>" in story_beat
    assert 'import { cleanNarrativeDisplayText } from "../../shared/lib/narrative-display-text"' in replay
    assert "{cleanNarrativeDisplayText(m.content)}" in replay
