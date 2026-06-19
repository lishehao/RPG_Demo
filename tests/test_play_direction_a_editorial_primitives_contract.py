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
    assert 'data-play-mood-state={isComplete ? "complete" : "active"}' in primitives
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
    assert "play.advisor_card_name" in primitives
    assert "play.advisor_card_background" in primitives
    assert "play.actor_focus_title" in primitives
    assert '"play.actor_focus_cta_none": "No preset move"' in strings
    assert '"play.actor_focus_active_none": "No preset move"' in strings
    assert '"play.actor_focus_cta_count_one": "1 move"' in strings
    assert '"play.actor_focus_cta_count_many": "{count} moves"' in strings
    assert '"play.actor_focus_active_count_one": "Showing 1 move"' in strings
    assert '"play.actor_focus_active_count_many": "Showing {count} moves"' in strings
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
    assert "Action surface rehearsal." in fixture
    assert "Choose a move, confirm it" not in fixture
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
    assert "consultedPersonId" in fixture
    assert "setConsultedPersonId(person.id)" in fixture
    assert 'data-gameplay-person-consulted={consulted ? "true" : undefined}' in fixture
    assert 'data-gameplay-person-advice="true"' in fixture
    assert "Advice from {consultedPerson.name}" in fixture
    assert 'data-gameplay-clue-card={unlockedClue ? "green-room-badge" : "locked"}' in fixture
    assert 'data-gameplay-forecast-chip={hook === "forecast" ? "true" : undefined}' in fixture
    assert 'data-gameplay-delta={hook === "delta" ? "true" : undefined}' in fixture
    assert 'data-gameplay-unlocked-action={unlockedClue ? "true" : undefined}' in fixture
    assert 'data-play-move-receipt="true"' in fixture
    assert 'data-play-room-reacting="true"' in fixture
    assert 'data-gameplay-resolved-title="true"' in fixture
    assert "After your move" in fixture
    assert "What changed now shapes the next choices." in fixture
    assert ">Changed<" not in fixture
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


def test_normal_play_prefers_backend_gameplay_envelope_with_derived_backup() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    envelope = (ROOT / "frontend2/src/pages/play/play-gameplay-envelope.ts").read_text()
    contracts = (ROOT / "frontend2/src/api/contracts.ts").read_text()
    backend_contracts = (ROOT / "rpg_backend/narrative/contracts.py").read_text()
    backend_service = (ROOT / "rpg_backend/narrative/service.py").read_text()
    backend_repository = (ROOT / "rpg_backend/narrative/repository.py").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "buildGameplayEnvelope" in envelope
    assert "deriveActionForecastChips" in envelope
    assert "normalizeBackendEnvelope" in envelope
    assert "buildGameplayEnvelope({" in play_page
    assert "backendEnvelope: story.gameplay_envelope ?? null" in play_page
    assert "gameplay_envelope: response.gameplay_envelope ?? null" in play_page
    assert "const [focusedActorId, setFocusedActorId] = useState<string | null>(null)" in play_page
    assert 'type GameplayResourceFocusId = "time" | "pressure" | "evidence"' in play_page
    assert "function isGameplayResourceFocusId(value: string): value is GameplayResourceFocusId" in play_page
    assert "const [focusedResourceId, setFocusedResourceId] = useState<GameplayResourceFocusId | null>(null)" in play_page
    assert "const actorFocus = focusedActorId && focusedActorName" in play_page
    assert "const focusedResourceTrack = focusedResourceId" in play_page
    assert "useMemo" not in play_page
    assert "const actorActionCounts = lastNarrator" in play_page
    assert "const resourceActionCounts = lastNarrator" in play_page
    assert "resourceActionCountsForOptions" in play_page
    assert 't("play.resource_focus_cta_none")' in play_page
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
    assert "focusedResourceId={focusedResourceId}" in play_page
    assert "resourceActionCounts={resourceActionCounts}" in play_page
    assert "onFocusResource={focusGameplayResource}" in play_page
    assert 'behavior: prefersReducedMotion ? "auto" : "smooth"' in play_page
    assert "<GameplayStatePanel" in play_page
    assert "envelope={gameplayEnvelope}" in play_page
    assert 'data-gameplay-objective-text="normal-play"' in play_page
    assert "WebkitLineClamp: 2" in styles
    assert 'whiteSpace: "nowrap" as const' not in styles[styles.index("gameplayObjectiveText:"):styles.index("gameplayTrackGrid:", styles.index("gameplayObjectiveText:"))]
    assert "<GameplayLoopGuide" in play_page
    assert 'data-gameplay-loop-guide="normal-play"' in play_page
    assert "data-gameplay-loop-stage={stage}" in play_page
    assert "data-gameplay-loop-step={step.id}" in play_page
    assert 'data-gameplay-loop-step-active={isActive ? "true" : "false"}' in play_page
    assert 'data-gameplay-loop-step-done={isDone ? "true" : "false"}' in play_page
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
    assert "actorFocusMatchedMoveLabels" in panels
    assert 'data-play-actor-focus-matches="true"' in panels
    assert 'data-play-actor-focus-match-chip="true"' in panels
    assert "const actorFocusDetail = actorFocus" in panels
    assert "play.actor_focus_match_detail_one" in panels
    assert "play.actor_focus_match_detail_many" in panels
    assert "function isResourceFocusAction(" in panels
    assert "export function isResourceFocusAction" in panels
    assert "resourceId === \"time\"" in panels
    assert "resourceId === \"pressure\"" in panels
    assert "const resourceFocusOptionMatches = useMemo" in panels
    assert "isResourceFocusAction(resourceFocus.id, parsed.body, opt.hint, actionForecasts?.[index] ?? [])" in panels
    assert "resourceFocusMatchedMoveLabels" in panels
    assert "function resourceFocusDetailText(" in panels
    assert "const openFreeActionComposer = () => {" in panels
    assert 'data-play-resource-focus-cue="true"' in panels
    assert 'data-play-resource-focus-id={resourceFocus.id}' in panels
    assert "data-play-resource-focus-match-count={resourceFocusMatchCount}" in panels
    assert 'data-play-resource-focus-cue-head="true"' in panels
    assert 'data-play-resource-focus-matches="true"' in panels
    assert 'data-play-resource-focus-match-chip="true"' in panels
    assert "play.resource_focus_showing_label" in panels
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
    assert 'data-play-action-target-detail="true"' in panels
    assert "data-play-action-target-detail-id={target.id}" in panels
    assert 't("play.action_target_detail_label")' in panels
    assert 't("play.action_target_detail_text", { name: target.name })' in panels
    assert "type ResolvingCommitmentSignal = {" in panels
    assert "const resolvingCommitmentSignals = useMemo<ResolvingCommitmentSignal[]>" in panels
    assert 'data-play-move-receipt-signals="true"' in panels
    assert 'data-play-move-receipt-signal="true"' in panels
    assert "commitmentSignals={resolvingCommitmentSignals}" in panels
    assert 'data-play-actor-focus-cue="true"' in panels
    assert 'data-play-actor-focus-id={actorFocus.id}' in panels
    assert "data-play-actor-focus-match-count={actorFocusMatchCount}" in panels
    assert 'data-play-actor-focus-cue-head="true"' in panels
    assert "play.actor_focus_showing_label" in panels
    assert "onClearActorFocus?: () => void" in panels
    assert 'data-play-actor-focus-clear="true"' in panels
    assert "ppStyles.actorFocusCueClear" in panels
    assert 'aria-label={`${t("play.actor_focus_label")}: ${actorFocus.name}. ${actorFocusDetail}`}' in panels
    assert "actorFocusMatchCount === 0 && showFreeActionToggle" in panels
    assert 'data-play-actor-focus-custom-move="true"' in panels
    assert "const freeActionFocusContext = actorFocus && actorFocusMatchCount === 0" in panels
    assert 'data-play-free-action-context="true"' in panels
    assert "data-play-free-action-context-kind={freeActionFocusContext.kind}" in panels
    assert "data-play-free-action-context-id={freeActionFocusContext.id}" in panels
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
    assert 'data-gameplay-forecast-detail="normal-play"' in panels
    assert '"play.gameplay_forecast_detail_label": "Why now"' in strings
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
    assert 'data-gameplay-objective="normal-play"' in play_page
    assert "data-gameplay-pressure-track={track.id}" in play_page
    assert 'data-gameplay-action-forecast="true"' in panels
    assert 'data-gameplay-forecast-chip="normal-play"' in panels
    assert 'data-gameplay-decision-forecast="true"' in panels
    assert 'data-gameplay-decision-group={group.id}' in panels
    assert 'type DecisionForecastGroup = "cost" | "upside" | "shift"' in panels
    assert 'data-gameplay-impact-summary="true"' in play_page
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
    assert 'data-gameplay-next-choice-signals="true"' in play_page
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
    assert "gameplayNextChoiceTargetButton" in styles
    assert "gameplayNextChoiceTargetFocused" in styles
    assert "resolvingCommitmentSignals" in styles
    assert "resolvingCommitmentSignalChip" in styles
    assert "freeActionContext" in styles
    assert "freeActionContextName" in styles
    assert "freeActionContextDetail" in styles
    assert "optionBtnResourceFocusMatch" in styles
    assert "gameplayNextChoiceChip" in styles
    assert "optionBtnActorFocusMatch" in styles
    assert "optionBtnActorFocusDimmed" in styles
    assert "actorFocusCue" in styles
    assert "actorFocusCueHead" in styles
    assert "actorFocusMatches" in styles
    assert "actorFocusMatchChip" in styles
    assert "actorFocusCueClear" in styles
    assert "gameplayDecisionForecast" in styles
    assert "gameplayDecisionGroupCost" in styles
    assert "gameplayDecisionGroupUpside" in styles
    assert "gameplayDecisionGroupShift" in styles
    assert "gameplayImpactPanel" in styles
    assert "gameplayImpactSourceMove" in styles
    assert "gameplayImpactSourceLabel" in styles
    assert "gameplayImpactSourceText" in styles
    assert "gameplayImpactSpotlight" in styles
    assert "gameplayImpactSpotlightValue" in styles
    assert "gameplayRelationshipDelta" in styles
    assert "gameplayRelationshipDeltaButton" in styles
    assert "gameplayRelationshipDeltaButtonFocused" in styles
    assert "gameplayRelationshipDeltaShift" in styles
    assert "gameplayImpactGroups" in styles
    assert "outcomeReceiptHeader" in styles
    assert "outcomeReceiptHint" in styles
    assert "feedbackPendingTimeline" in styles
    assert "feedbackPendingStepActive" in styles
    assert '"play.gameplay_loop_label": "Action loop"' in strings
    assert '"play.gameplay_loop_choose_label": "Choose move"' in strings
    assert '"play.gameplay_loop_choose_detail": "Costs and opportunities"' in strings
    assert '"play.gameplay_loop_choose_detail": "预判代价和机会"' in strings
    assert '"play.gameplay_loop_react_label": "Room reacts"' in strings
    assert '"play.gameplay_loop_update_label": "See changes"' in strings
    assert '"play.gameplay_objective_label": "Goal"' in strings
    assert '"play.feedback_source_move_label": "From your move"' in strings
    assert '"play.gameplay_decision_forecast_label": "What this changes"' in strings
    assert '"play.actor_focus_label": "Character focus"' in strings
    assert '"play.actor_focus_showing_label": "Showing moves for {name}"' in strings
    assert '"play.actor_focus_cta_none": "No preset move"' in strings
    assert '"play.actor_focus_active_none": "No preset move"' in strings
    assert '"play.actor_focus_match_detail_one": "1 current move directly involves this character."' in strings
    assert '"play.actor_focus_match_detail_many": "{count} current moves directly involve this character."' in strings
    assert '"play.actor_focus_matches_label": "Matching moves"' in strings
    assert '"play.actor_focus_no_match": "No current move names this character directly; use a custom move to test them."' in strings
    assert '"play.actor_focus_clear": "Clear"' in strings
    assert '"play.free_context_actor_label": "Custom move target"' in strings
    assert '"play.free_context_actor_detail": "Write how you test {name}; the current options do not name them directly."' in strings
    assert '"play.action_open_free_actor": "Write move for {name}"' in strings
    assert '"play.action_free_actor_placeholder": "Write how you pull {name} into this move..."' in strings
    assert '"play.free_action_boundary_hint": "Write what others can see or hear here; put your real purpose in inner motive."' in strings
    assert '"play.action_target_label": "Target"' in strings
    assert '"play.action_target_title": "This move primarily points at {name}"' in strings
    assert '"play.action_target_detail_label": "Who reacts"' in strings
    assert '"play.action_target_detail_text": "This move mainly tests {name}\'s reaction."' in strings
    assert '"play.move_receipt_signals_label": "Target and impact committed by this move"' in strings
    assert '"play.resource_focus_cta": "Show moves"' in strings
    assert '"play.resource_focus_active": "Showing moves"' in strings
    assert '"play.resource_focus_cta_count_one": "1 move"' in strings
    assert '"play.resource_focus_cta_count_many": "{count} moves"' in strings
    assert '"play.resource_focus_active_count": "Showing {count}"' in strings
    assert '"play.resource_focus_label": "Resource focus"' in strings
    assert '"play.resource_focus_showing_label": "Showing {name} moves"' in strings
    assert '"play.resource_focus_clear": "Clear"' in strings
    assert '"play.resource_focus_evidence_label": "Evidence"' in strings
    assert '"play.resource_focus_time_title": "Highlight moves that spend, buy, or change time pressure"' in strings
    assert '"play.resource_focus_pressure_title": "Highlight moves that change public pressure, danger, or tension"' in strings
    assert '"play.resource_focus_cta_none": "No preset move"' in strings
    assert '"play.resource_focus_active_none": "No preset move"' in strings
    assert '"play.resource_focus_time_match_detail_one": "1 current move affects time pressure."' in strings
    assert '"play.resource_focus_time_match_detail_many": "{count} current moves affect time pressure."' in strings
    assert '"play.resource_focus_pressure_match_detail_one": "1 current move affects pressure."' in strings
    assert '"play.resource_focus_pressure_match_detail_many": "{count} current moves affect pressure."' in strings
    assert '"play.resource_focus_evidence_match_detail_one": "1 current move can push a clue or proof forward."' in strings
    assert '"play.resource_focus_evidence_match_detail_many": "{count} current moves can push a clue or proof forward."' in strings
    assert '"play.resource_focus_matches_label": "Matching moves"' in strings
    assert '"play.gameplay_decision_cost_label": "Costs"' in strings
    assert '"play.gameplay_decision_upside_label": "Opens"' in strings
    assert '"play.gameplay_decision_shift_label": "Shifts"' in strings
    assert '"play.option_forecast_kicker": "影响"' in strings
    assert '"play.gameplay_decision_forecast_label": "这个选择的影响"' in strings
    assert '"play.gameplay_decision_upside_label": "机会"' in strings
    assert '"play.gameplay_decision_shift_label": "变化"' in strings
    assert '"play.gameplay_impact_label": "After your move"' in strings
    assert '"play.outcome_next_hint": "Shapes the next choices"' in strings
    assert '"play.feedback_impact_cost_label": "Cost / risk"' in strings
    assert '"play.feedback_impact_opened_label": "Opened"' in strings
    assert '"play.feedback_key_consequence_label": "Main result"' in strings
    assert '"play.feedback_next_choice_label": "Why next moves changed"' in strings
    assert '"play.feedback_next_choice_changed_label": "Next moves changed"' in strings
    assert '"play.feedback_next_choice_changed_detail": "New actions are refocused by who reacted, what changed, and any clues you opened."' in strings
    assert '"play.gameplay_impact_label": "行动之后"' in strings
    assert '"play.feedback_key_consequence_label": "主要结果"' in strings
    assert '"play.feedback_next_choice_label": "下一步为什么变了"' in strings
    assert '"play.feedback_next_choice_changed_label": "下一组行动已改变"' in strings
    assert '"play.impact_focus_actor_title": "Focus moves involving {name}"' in strings
    assert '"play.feedback_pending_reaction_label": "Room reacting"' in strings
    assert 'data-play-outcome-receipt="true"' in panels
    assert 'data-play-outcome-receipt-mode={compact ? "compact" : "summary"}' in panels
    assert 'data-play-outcome-receipt-item="true"' in panels
    assert "data-play-outcome-receipt-tone={item.tone ?? \"neutral\"}" in panels
    assert "const outcomeReceiptA11yItems" in panels
    assert "aria-label={outcomeReceiptA11yLabel}" in panels
    assert "fetch(" not in envelope
    for forbidden in ("provider", "model", "schema", "token", "fallback", "debug"):
        assert forbidden not in envelope.casefold()


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
    assert 'data-play-action-card-title="true"' in panels
    assert 'data-play-action-card-body="true"' in panels
    assert 'data-play-action-card-detail-section="result"' in panels
    assert 'data-play-action-card-detail-section="forecast"' in panels
    assert 'data-play-action-card-detail-section="why-now"' in panels
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
    assert 'data-play-feedback-timeline="true"' in panels
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
    assert "renderCollapsedForecast(optionForecasts)" in panels
    assert 'data-gameplay-action-forecast-summary="true"' in panels
    assert "gameplayForecastInline" in styles
    assert "gameplayForecastInlineLabel" in styles
    assert '"play.option_forecast_kicker": "Changes"' in strings
    assert "change choice" not in strings
    assert '"play.selected_move_kicker": "Selected move"' in strings
    assert '"play.selected_move_commit_cta": "Take this action"' in strings
    assert '"play.inner_motive_cta": "Use inner motive"' in strings
    assert '"play.inner_motive_submit_cta": "Take action with motive"' in strings
    assert '"play.advisor_card_name": "Dana Vale"' in strings
    assert 'data-play-advisor-empty-primer="true"' in panels
    assert "const [draftSuggestion, setDraftSuggestion] = useState<string | null>(null)" in panels
    assert "setDraftSuggestion(suggestion)" in panels
    assert 'data-play-advisor-draft-hint="true"' in panels
    assert "advisorEmptyPrimer" in styles
    assert "advisorEmptyPrimerTitle" in styles
    assert "advisorDraftHint" in styles
    assert '"play.advisor_empty_primer_title": "Ask for one read first"' in strings
    assert '"play.advisor_empty_primer_body": "Your friend can flag risk, wording, and who may push back, but you still choose the move."' in strings
    assert '"play.advisor_draft_hint": "Suggested question inserted. Edit it, then ask."' in strings
    assert '"play.advisor_draft_hint": "已插入建议问题，可以改一句再问朋友。"' in strings
    assert '"play.advisor_send": "Ask friend"' in strings
    assert '"play.advisor_send": "问朋友"' in strings
    assert '"play.move_receipt_title": "Your move"' in strings
    assert '"play.room_reacting_title": "The room is reacting"' in strings
    assert '"play.option_expand_cta": "View move"' in strings
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
    assert "const actionJumpDetail =" in play_page
    assert "const handleActionJump = useCallback" in play_page
    assert "setShowActionJump(false)" in play_page
    assert "scrollToPlayActionArea()" in play_page
    assert "onClick={handleActionJump}" in play_page
    assert "stage={gameplayLoopStage}" in play_page
    assert "detail={actionJumpDetail}" in play_page
    assert 'data-play-action-jump="true"' in action_jump
    assert "data-play-action-jump-stage={stage}" in action_jump
    assert 'data-play-action-jump-detail="true"' in action_jump
    assert "onPointerDown={onClick}" in action_jump
    assert "scrollToPlayActionArea" in action_jump_utils
    assert "[data-play-action-area='true']" in action_jump_utils
    assert "actionJumpButton" in styles
    assert "actionJumpDetail" in styles
    assert "actionJumpArrow" in styles
    assert 'position: "fixed"' in styles[styles.index("actionJumpButton") : styles.index("actionJumpKicker")]
    assert "maxWidth: 430" in styles[styles.index("actionJumpButton") : styles.index("actionJumpKicker")]
    assert '"play.action_jump_kicker": "Your move"' in strings
    assert '"play.action_jump_label": "Continue to choices"' in strings
    assert '"play.action_jump_detail_choose": "Goal, pressure, and choices are ready."' in strings
    assert '"play.action_jump_detail_update": "Review what changed, then choose next."' in strings


def test_empty_trump_card_resource_stays_out_of_main_action_surface() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()

    assert "const showLeverageRail = leverageCards.length > 0 && !commitmentSurfaceOpen" in panels
    assert "roleHasNoLeverage) && !commitmentSurfaceOpen" not in panels
    assert "roleHasNoLeverage ||" not in panels


def test_ending_screen_prioritizes_result_text_before_illustration() -> None:
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    ending_screen = panels[panels.index("export function EndingScreen") : panels.index("function displayEndingLabel")]

    assert "Illustrated banner is secondary to the result text" in ending_screen
    assert 'data-play-ending-actions="true"' in ending_screen
    assert 'data-play-ending-next-step-label="true"' in ending_screen
    assert 'data-play-ending-illustration="true"' in ending_screen
    assert ending_screen.index("style={ppStyles.endingPassage}") < ending_screen.index('data-play-ending-actions="true"')
    assert ending_screen.index('data-play-ending-next-step-label="true"') < ending_screen.index("style={ppStyles.endingActionsRow}")
    assert ending_screen.index('data-play-ending-actions="true"') < ending_screen.index('data-play-ending-illustration="true"')
    assert ending_screen.index('data-play-ending-illustration="true"') < ending_screen.index("...ppStyles.endingHero")
    assert "const fallbackRecap = mergedHighlights.length === 0" in ending_screen
    assert 'data-play-ending-recap="fallback"' in ending_screen
    assert "buildFallbackEndingRecap(messages)" in ending_screen
    assert "parseOptionLabel(message.content)" in panels
    assert 'height: 150' in styles[styles.index("endingHero") : styles.index("endingSplashOverlay")]
    assert 'padding: "10px 0 28px"' in styles[styles.index("endingCardInner") : styles.index("endingLabelChip")]
    assert 'marginBottom: 22' in styles[styles.index("endingActions") : styles.index("endingActionsRow")]
    assert "endingActionsLabel" in styles
    assert "endingRecapSection" in styles
    assert '"play.ending_recap_title": "How this run got here"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    assert '"play.ending_next_steps": "Next steps"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()


def test_latest_narrator_beat_has_lightweight_digest_before_next_action() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/play/play-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    story_beat = panels[panels.index("export function StoryBeat") : panels.index("  // player move (echoed action)")]

    assert "const showGameplayImpactSummary =" in play_page
    assert "suppressLatestFeedbackDigest={" in play_page
    assert "showGameplayImpactSummary" in play_page
    assert "suppressLatestFeedbackDigest?: boolean" in story_beat
    assert "const latestDigestPulses" in story_beat
    assert "const showLatestBeatDigest" in story_beat
    assert "!suppressLatestFeedbackDigest" in story_beat
    assert "const latestDigestA11yItems" in story_beat
    assert "const latestDigestA11yLabel" in story_beat
    assert 'aria-label={latestDigestA11yLabel}' in story_beat
    assert "latestDigestPulses.length > 0 || hasDelta || latestOptionCount > 0" in story_beat
    assert "hasDelta && latestDigestPulses.length === 0" in story_beat
    assert "outcomeItems.length > 0 && !suppressLatestFeedbackDigest" in story_beat
    assert 'data-play-latest-beat-digest="true"' in story_beat
    assert "data-play-latest-beat-digest-pulse={pulse.npc_id}" in story_beat
    assert 'data-play-latest-beat-digest-options="true"' in story_beat
    assert "latestBeatDigest" in styles
    assert "latestBeatDigestItems" in styles
    assert '"play.latest_beat_digest_label": "Current beat"' in strings
    assert '"play.latest_beat_digest_options": "{count} moves ready"' in strings


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
    assert 'stage="choose"' in fixture
    assert 'detail={t("play.action_jump_detail_choose")}' in fixture
    assert "scrollToPlayActionArea()" in fixture
    assert "isPlayActionAreaAwayFromViewport(actionArea)" in fixture
    assert 'data-play-action-jump="true"' in action_jump
    assert "data-play-action-jump-stage={stage}" in action_jump
    assert "window.scrollTo" in action_jump_utils
    for forbidden in ("provider", "model", "schema", "token", "fallback", "deterministic"):
        assert forbidden not in fixture.casefold()
