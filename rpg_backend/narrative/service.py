from __future__ import annotations

import secrets
import re
from concurrent.futures import ThreadPoolExecutor

from rpg_backend.author.normalize import normalize_whitespace
from rpg_backend.config import Settings, get_settings
from rpg_backend.narrative.contracts import (
    AgentPlan,
    AdvanceTurnRequest,
    AdvanceTurnResponse,
    AdvisorAskRequest,
    AdvisorAskResponse,
    AdvisorHistoryResponse,
    AdvisorMessage,
    CastMember,
    CreateTemplateRequest,
    CreateTemplateResponse,
    EndingDistributionEntry,
    EndingDistributionResponse,
    NarrativeEnding,
    NarrativeSession,
    NarrativeSessionSummary,
    NarrativeTemplate,
    NarrativeTemplateSummary,
    FailureCondition,
    NPCPulse,
    NPCLeverageOverNPC,
    PlayedLeverageCard,
    PlayerGoal,
    PlayerLeverageOverNPC,
    PlayerRole,
    PublicReplayResponse,
    SessionListResponse,
    StartSessionResponse,
    StoryBrief,
    StoryBriefAdvisorRequest,
    StoryBriefAdvisorResponse,
    StoryBriefConsistencyCheck,
    StoryHistoryResponse,
    StoryMessage,
    StoryOption,
    TemplateListResponse,
    UpdateTemplateVisibilityRequest,
)
from rpg_backend.narrative.brief import (
    build_story_brief,
    check_story_brief_opening_consistency,
    has_explicit_small_cast_mismatch,
)
from rpg_backend.narrative.engine import (
    advance_turn,
    ask_advisor,
    ask_advisor_oracle,
    build_agent_plan,
    compute_current_inventory,
    generate_opening,
    judge_failure,
    OpeningResult,
    synthesize_branches,
    synthesize_early_ending,
    synthesize_ending,
    synthesize_highlights,
    tier_for_label,
    TurnResult,
)
from rpg_backend.narrative.gateway import (
    NarrativeGatewayError,
    NarrativeLLMGateway,
    get_narrative_gateway,
)
from rpg_backend.narrative.judges import judge_contract, judge_step
from rpg_backend.narrative.profile_vocabulary import reliable_profile_vocabulary
from rpg_backend.narrative.repository import NarrativeNotFoundError, NarrativeRepository


PRIVATE_REPLAY_TITLE = "Shared private story"


def _emit_metric(event: str, **fields: object) -> None:
    """Tag-only metric emission. Format is grep-friendly and parses as
    one event per line:
        [narrative.metric] event=template_created template_id=tmpl_xxx ...

    No external dependency — production deployment can pipe these
    through stdout to a log shipper (cloudwatch / loki / fluent) and
    aggregate later. We don't try to maintain a counter in-process
    (multi-worker would lie); just emit one line per event."""
    parts = [f"{k}={v}" for k, v in fields.items()]
    print(f"[narrative.metric] event={event} {' '.join(parts)}", flush=True)


class NarrativeServiceError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


_CONTENT_MODERATION_FALLBACK = (
    "唉，刚才那段我没法接——咱俩说的事好像踩到红线了。换个角度问我？"
    "或者你想跟我聊点别的，我都在。"
)
_CONTENT_MODERATION_MARKERS = (
    "DataInspectionFailed",
    "inappropriate content",
    "data inspection failed",
)
_RELIABLE_OPENING_FALLBACK_CODES = {
    "llm_unavailable",
    "llm_provider_failed",
    "llm_invalid_response",
    "llm_invalid_json",
}
_TURN_RUNTIME_FALLBACK_CODES = {
    "llm_unavailable",
    "llm_provider_failed",
    "llm_invalid_response",
    "llm_invalid_json",
}


def _is_content_moderation_failure(exc: NarrativeGatewayError) -> bool:
    if exc.status_code != 400:
        return False
    msg_lower = (exc.message or "").lower()
    return any(marker.lower() in msg_lower for marker in _CONTENT_MODERATION_MARKERS)


def _generate_template_id() -> str:
    return f"tmpl_{secrets.token_hex(6)}"


def _generate_session_id() -> str:
    return f"sess_{secrets.token_hex(6)}"


class NarrativeService:
    def __init__(
        self,
        *,
        repository: NarrativeRepository,
        gateway: NarrativeLLMGateway | None,
    ) -> None:
        self._repo = repository
        self._gateway = gateway

    @property
    def gateway(self) -> NarrativeLLMGateway:
        if self._gateway is None:
            raise NarrativeServiceError(
                code="llm_unavailable",
                message="Narrative LLM gateway is not configured.",
                status_code=500,
            )
        return self._gateway

    # ------------------------------------------------------------------
    # Template authoring
    # ------------------------------------------------------------------

    def create_story_brief(
        self,
        request: StoryBriefAdvisorRequest,
        *,
        owner_user_id: str,
    ) -> StoryBriefAdvisorResponse:
        del owner_user_id
        seed = request.seed.strip()
        if not seed:
            raise NarrativeServiceError(
                code="seed_required", message="Seed must not be empty.", status_code=422
            )
        return build_story_brief(
            seed=seed,
            language=request.language,
            desired_tension_profile=request.desired_tension_profile,
        )

    def create_template(
        self,
        request: CreateTemplateRequest,
        *,
        owner_user_id: str,
    ) -> CreateTemplateResponse:
        seed = request.seed.strip()
        if not seed:
            raise NarrativeServiceError(
                code="seed_required", message="Seed must not be empty.", status_code=422
            )
        if has_explicit_small_cast_mismatch(seed):
            raise NarrativeServiceError(
                code="opening_prompt_shape_mismatch",
                message=(
                    "This premise needs a clearer playable shape: try 3+ people, "
                    "one public conflict, one secret or contested object, and time pressure."
                ),
                status_code=422,
            )
        if request.story_brief is not None and _story_brief_prefers_reliable_opening(request.story_brief):
            opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
        else:
            try:
                opening = generate_opening(
                    gateway=self.gateway,
                    seed=seed,
                    language=request.language,
                    story_brief=request.story_brief,
                    max_attempts=2 if request.story_brief is not None else 3,
                )
            except NarrativeServiceError as exc:
                if request.story_brief is not None and _should_use_reliable_opening_fallback(exc):
                    opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                else:
                    raise
            except NarrativeGatewayError as exc:
                if request.story_brief is not None and _should_use_reliable_opening_fallback(exc):
                    opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                else:
                    raise NarrativeServiceError(
                        code=exc.code, message=exc.message, status_code=exc.status_code
                    ) from exc
            except ValueError as exc:
                message = str(exc)
                if "cast too small after sanitization" in message:
                    raise NarrativeServiceError(
                        code="opening_prompt_shape_mismatch",
                        message=(
                            "This premise needs a clearer playable shape: try 3+ people, "
                            "one public conflict, one secret or contested object, and time pressure."
                        ),
                        status_code=422,
                    ) from exc
                if request.story_brief is not None:
                    opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                else:
                    raise NarrativeServiceError(
                        code="opening_invalid",
                        message=f"LLM returned an unusable opening: {exc}",
                        status_code=502,
                    ) from exc
        story_brief_consistency = None
        if request.story_brief is not None:
            story_brief_consistency = check_story_brief_opening_consistency(
                brief=request.story_brief,
                opening=opening,
                language=request.language,
            )
            if story_brief_consistency.should_retry and not _story_brief_prefers_reliable_opening(request.story_brief):
                retry_feedback = _story_brief_consistency_feedback(story_brief_consistency)
                try:
                    opening = generate_opening(
                        gateway=self.gateway,
                        seed=seed,
                        language=request.language,
                        story_brief=request.story_brief,
                        brief_consistency_feedback=retry_feedback,
                        max_attempts=1,
                    )
                except NarrativeServiceError as exc:
                    if _should_use_reliable_opening_fallback(exc):
                        opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                    else:
                        raise
                except NarrativeGatewayError as exc:
                    if _should_use_reliable_opening_fallback(exc):
                        opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                    else:
                        raise NarrativeServiceError(
                            code=exc.code, message=exc.message, status_code=exc.status_code
                        ) from exc
                except ValueError:
                    opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                story_brief_consistency = check_story_brief_opening_consistency(
                    brief=request.story_brief,
                    opening=opening,
                    language=request.language,
                )
            if story_brief_consistency.status == "fail":
                fallback_opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                fallback_check = check_story_brief_opening_consistency(
                    brief=request.story_brief,
                    opening=fallback_opening,
                    language=request.language,
                )
                if fallback_check.status != "fail":
                    opening = fallback_opening
                    story_brief_consistency = fallback_check
                else:
                    raise NarrativeServiceError(
                        code="opening_brief_consistency_failed",
                        message=_story_brief_consistency_failure_message(story_brief_consistency),
                        status_code=422,
                    )

        template_id = _generate_template_id()
        template = self._repo.create_template(
            template_id=template_id,
            owner_user_id=owner_user_id,
            seed=seed,
            title=opening.title,
            cast=opening.cast,
            advisor_persona=opening.advisor_persona,
            opening_passage=opening.opening_message.content,
            opening_options=opening.opening_message.options,
            player_goals=opening.player_goals,
            failure_conditions=opening.failure_conditions,
            player_role_options=opening.player_role_options,
            visibility=request.visibility,
            language=request.language,
        )

        # Auto-create the creator's session with the requested difficulty.
        # First role becomes the default — the create page doesn't pick yet.
        session, opening_message = self._spawn_session(
            template, owner_user_id, request.turn_budget, request.difficulty,
            player_role_index=0 if template.player_role_options else None,
        )

        _emit_metric(
            "template_created",
            template_id=template_id,
            owner=owner_user_id,
            visibility=request.visibility,
            language=request.language,
            turn_budget=request.turn_budget,
            difficulty=request.difficulty,
            seed_chars=len(seed),
            num_goals=len(opening.player_goals),
            num_failure_conds=len(opening.failure_conditions),
            num_player_roles=len(opening.player_role_options),
        )
        return CreateTemplateResponse(
            template=_summarize_template(template, viewer_user_id=owner_user_id),
            session=_summarize_session(session, template),
            opening=opening_message,
            story_brief_consistency=story_brief_consistency,
        )

    def list_public_templates(self, *, viewer_user_id: str) -> TemplateListResponse:
        templates = self._repo.list_public_templates()
        return TemplateListResponse(
            items=[_summarize_template(t, viewer_user_id=viewer_user_id) for t in templates]
        )

    def list_my_templates(self, *, owner_user_id: str) -> TemplateListResponse:
        templates = self._repo.list_templates_for_owner(owner_user_id)
        return TemplateListResponse(
            items=[_summarize_template(t, viewer_user_id=owner_user_id) for t in templates]
        )

    def get_template(
        self, template_id: str, *, viewer_user_id: str
    ) -> NarrativeTemplateSummary:
        template = self._load_template_for_viewer(template_id, viewer_user_id)
        return _summarize_template(template, viewer_user_id=viewer_user_id)

    def update_visibility(
        self,
        template_id: str,
        request: UpdateTemplateVisibilityRequest,
        *,
        owner_user_id: str,
    ) -> NarrativeTemplateSummary:
        template = self._load_template_for_owner(template_id, owner_user_id)
        self._repo.update_template_visibility(template_id, request.visibility)
        updated = self._repo.get_template(template_id)
        return _summarize_template(updated, viewer_user_id=owner_user_id)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(
        self,
        template_id: str,
        *,
        player_user_id: str,
        turn_budget: int = 12,
        difficulty: str = "story",
        player_role_index: int | None = None,
    ) -> StartSessionResponse:
        template = self._load_template_for_viewer(template_id, player_user_id)
        # Resolve the picked role index against template options. If the
        # template has roles but the caller didn't pick, default to 0
        # (preserves the legacy "everyone is the same default" behavior
        # while letting clients opt in per call).
        resolved_index: int | None
        if template.player_role_options:
            resolved_index = (
                player_role_index
                if player_role_index is not None
                and 0 <= player_role_index < len(template.player_role_options)
                else 0
            )
        else:
            resolved_index = None
        session, opening_message = self._spawn_session(
            template, player_user_id, turn_budget, difficulty,
            player_role_index=resolved_index,
        )
        _emit_metric(
            "session_started",
            template_id=template_id,
            session_id=session.session_id,
            player=player_user_id,
            is_owner=int(template.owner_user_id == player_user_id),
            turn_budget=turn_budget,
            difficulty=difficulty,
            player_role_index=resolved_index if resolved_index is not None else -1,
        )
        return StartSessionResponse(
            template=_summarize_template(template, viewer_user_id=player_user_id),
            session=_summarize_session(session, template),
            opening=opening_message,
        )

    def list_my_sessions(self, *, player_user_id: str) -> SessionListResponse:
        sessions = self._repo.list_sessions_for_player(player_user_id)
        # Pull templates in batch (small N expected; keep it simple).
        items: list[NarrativeSessionSummary] = []
        for s in sessions:
            try:
                template = self._repo.get_template(s.template_id)
            except NarrativeNotFoundError:
                continue
            items.append(_summarize_session(s, template))
        return SessionListResponse(items=items)

    def get_story_history(
        self,
        session_id: str,
        *,
        player_user_id: str,
        include_agent_trace: bool = False,
    ) -> StoryHistoryResponse:
        session = self._load_session_for_player(session_id, player_user_id)
        template = self._repo.get_template(session.template_id)
        messages = self._repo.list_story_messages(session_id)
        agent_events = (
            self._repo.list_agent_events(session_id) if include_agent_trace else []
        )
        # turn_count derived from message stream (narrator/player pairs)
        return StoryHistoryResponse(
            template=_summarize_template(template, viewer_user_id=player_user_id),
            session=_summarize_session(session, template),
            messages=messages,
            agent_events=agent_events,
        )

    # ------------------------------------------------------------------
    # Advance a turn
    # ------------------------------------------------------------------

    def advance(
        self,
        session_id: str,
        request: AdvanceTurnRequest,
        *,
        player_user_id: str,
        include_agent_trace: bool = False,
    ) -> AdvanceTurnResponse:
        session = self._load_session_for_player(session_id, player_user_id)
        if session.ending_label is not None:
            raise NarrativeServiceError(
                code="session_complete",
                message="这一局故事已经走完了——去看你的结局吧。",
                status_code=409,
            )
        template = self._repo.get_template(session.template_id)
        history = self._repo.list_story_messages(session_id)
        if not history:
            raise NarrativeServiceError(
                code="no_opening", message="Story has no opening yet.", status_code=409
            )
        last_narrator = next((m for m in reversed(history) if m.role == "narrator"), None)
        if last_narrator is None:
            raise NarrativeServiceError(
                code="no_narrator", message="No narrator message in history.", status_code=409
            )
        if last_narrator.chosen_option_index is not None and history[-1].role == "player":
            raise NarrativeServiceError(
                code="turn_already_advanced",
                message="The last narrator beat already has a player choice; refresh and continue.",
                status_code=409,
            )
        active_role = _resolve_player_role(template, session.selected_player_role_id)
        played_leverage = self._resolve_played_leverage(request, active_role)
        player_action_text, chosen_index = self._resolve_player_action(
            request, last_narrator
        )
        # Optional inner monologue. Trimmed by the contract's max_length;
        # we still defensively strip whitespace and skip empty.
        diary_text: str | None = None
        if request.diary and request.diary.strip():
            diary_text = request.diary.strip()[:600]

        # Build the player message in memory; do NOT persist until the
        # narrator beat succeeds. Avoids orphan player messages.
        next_ord = self._repo.next_story_ord(session_id)
        player_message = StoryMessage(
            ord=next_ord,
            role="player",
            content=player_action_text,
            options=[],
            chosen_option_index=chosen_index,
            diary=diary_text,
            played_leverage=played_leverage,
        )

        # turn_index = the index of the new narrator beat we're about to write.
        # turn_count is the number of completed narrator/player pairs so far.
        # The opening counts as turn 0; this advance produces turn_count+1.
        upcoming_turn_index = session.turn_count + 1
        is_final_turn = upcoming_turn_index >= session.turn_budget

        # Walk history to derive the sticky inventory the LLM should see
        # this turn. Source of truth = role.starting_assets + Σ(narrator
        # inventory deltas). Walk-on-read so we never desync from the
        # persisted message stream.
        starting_assets = active_role.starting_assets if active_role else []
        current_inventory = compute_current_inventory(starting_assets, history)

        def build_deterministic_turn() -> TurnResult:
            return _deterministic_turn_fallback(
                template=template,
                history=history + [player_message],
                player_action=player_action_text,
                next_ord=next_ord + 1,
                turn_index=upcoming_turn_index,
                turn_budget=session.turn_budget,
                difficulty=session.difficulty,
                player_role=active_role,
                current_inventory=current_inventory or None,
                played_leverage=played_leverage,
            )

        try:
            turn = advance_turn(
                gateway=self.gateway,
                seed=template.seed,
                title=template.title,
                cast=template.cast,
                history=history + [player_message],
                player_action=player_action_text,
                next_ord=next_ord + 1,
                turn_index=upcoming_turn_index,
                turn_budget=session.turn_budget,
                difficulty=session.difficulty,
                player_goals=template.player_goals or None,
                player_role=active_role,
                current_inventory=current_inventory or None,
                player_diary=diary_text,
                played_leverage=played_leverage,
                language=template.language,
            )
        except NarrativeServiceError as exc:
            if _should_use_turn_runtime_fallback(exc):
                turn = build_deterministic_turn()
            else:
                raise
        except NarrativeGatewayError as exc:
            if _should_use_turn_runtime_fallback(exc):
                turn = build_deterministic_turn()
            else:
                raise NarrativeServiceError(
                    code=exc.code, message=exc.message, status_code=exc.status_code
                ) from exc
        except ValueError:
            turn = build_deterministic_turn()

        # Atomic-ish persistence: player message + chosen-option update + narrator.
        self._repo.append_story_message(session_id, player_message)
        if chosen_index is not None and last_narrator.chosen_option_index is None:
            self._repo.update_story_message_choice(
                session_id, last_narrator.ord, chosen_index
            )
        self._repo.append_story_message(session_id, turn.narrator_message)
        turn_agent_events = []
        turn_agent_events.append(self._repo.append_agent_event(
            session_id,
            ord_value=turn.narrator_message.ord,
            event_type="agent_plan",
            payload=turn.agent_plan,
        ))
        step_judge = judge_step(
            agent_plan=turn.agent_plan,
            player_message=player_message,
            narrator_message=turn.narrator_message,
            cast=template.cast,
        )
        turn_agent_events.append(self._repo.append_agent_event(
            session_id,
            ord_value=turn.narrator_message.ord,
            event_type="step_judge",
            payload=step_judge,
        ))
        contract_judge = judge_contract(
            agent_plan=turn.agent_plan,
            player_message=player_message,
            narrator_message=turn.narrator_message,
            cast=template.cast,
            player_role=active_role,
        )
        turn_agent_events.append(self._repo.append_agent_event(
            session_id,
            ord_value=turn.narrator_message.ord,
            event_type="contract_judge",
            payload=contract_judge,
        ))
        self._repo.touch_session(session_id, increment_turns=1)

        ending_payload: NarrativeEnding | None = None

        # Gauntlet mode: judge whether the player just tripped a failure
        # condition. If so, skip the standard finale and synthesize an
        # early collapse instead. We only run this BEFORE the natural
        # final turn — if we're already at the budget, the regular
        # finalize will handle it (and tier may end up collapsed anyway
        # via the label-tier table).
        if (
            session.difficulty == "gauntlet"
            and not is_final_turn
            and template.failure_conditions
        ):
            try:
                full_history = self._repo.list_story_messages(session_id)
                judgement = judge_failure(
                    gateway=self.gateway,
                    failure_conditions=template.failure_conditions,
                    history=full_history,
                )
            except (NarrativeGatewayError, ValueError) as exc:
                # Failure judge errors are non-fatal — log and proceed.
                print(
                    f"[narrative.service] judge_failure errored for session={session_id}: {exc}",
                    flush=True,
                )
                judgement = None
            if judgement is not None and judgement.triggered:
                ending_payload = self._finalize_session_early(
                    session_id,
                    template,
                    failure_trigger=judgement.matched_condition_label,
                    failure_reason=judgement.reason,
                    player_role=active_role,
                )

        if ending_payload is None and is_final_turn:
            ending_payload = self._finalize_session(session_id, template, player_role=active_role)

        return AdvanceTurnResponse(
            player_message=player_message,
            narrator_message=turn.narrator_message,
            agent_plan=turn.agent_plan if include_agent_trace else None,
            agent_events=turn_agent_events if include_agent_trace else [],
            ending=ending_payload,
            is_complete=ending_payload is not None,
        )

    def validate_advance_request(
        self,
        session_id: str,
        request: AdvanceTurnRequest,
        *,
        player_user_id: str,
    ) -> None:
        """Validate non-LLM turn semantics before public quota is debited."""
        session = self._load_session_for_player(session_id, player_user_id)
        if session.ending_label is not None:
            raise NarrativeServiceError(
                code="session_complete",
                message="这一局故事已经走完了——去看你的结局吧。",
                status_code=409,
            )
        template = self._repo.get_template(session.template_id)
        history = self._repo.list_story_messages(session_id)
        if not history:
            raise NarrativeServiceError(
                code="no_opening", message="Story has no opening yet.", status_code=409
            )
        last_narrator = next((m for m in reversed(history) if m.role == "narrator"), None)
        if last_narrator is None:
            raise NarrativeServiceError(
                code="no_narrator", message="No narrator message in history.", status_code=409
            )
        if last_narrator.chosen_option_index is not None and history[-1].role == "player":
            raise NarrativeServiceError(
                code="turn_already_advanced",
                message="The last narrator beat already has a player choice; refresh and continue.",
                status_code=409,
            )
        self._resolve_player_action(request, last_narrator)
        self._resolve_played_leverage(
            request,
            _resolve_player_role(template, session.selected_player_role_id),
        )

    def estimate_advance_llm_operation_cost(
        self,
        session_id: str,
        *,
        player_user_id: str,
    ) -> int:
        """Conservative quota reservation for one advance request.

        The actual LLM calls happen below the HTTP route, inside the narrative
        engine. Public demo quota therefore reserves the maximum plausible
        calls before invoking the service so finalization cannot bypass the
        daily cap.
        """
        session = self._load_session_for_player(session_id, player_user_id)
        if session.ending_label is not None:
            raise NarrativeServiceError(
                code="session_complete",
                message="这一局故事已经走完了——去看你的结局吧。",
                status_code=409,
            )
        template = self._repo.get_template(session.template_id)
        upcoming_turn_index = session.turn_count + 1
        is_final_turn = upcoming_turn_index >= session.turn_budget
        if is_final_turn:
            # advance_turn can retry once, ending can retry once, highlights
            # runs once, and branches can retry once: 2 + 2 + 1 + 2.
            return 7
        if session.difficulty == "gauntlet" and template.failure_conditions:
            # Non-final gauntlet turns may advance with one retry, judge
            # failure, then synthesize an early ending, highlights, and up to
            # two branch attempts: 2 + 1 + 1 + 1 + 2.
            return 7
        # Regular turns still reserve the advance_turn retry path.
        return 2

    def _finalize_session(
        self,
        session_id: str,
        template: NarrativeTemplate,
        *,
        player_role: PlayerRole | None = None,
    ) -> NarrativeEnding | None:
        """Synthesize the ending and persist it. Logs and silently no-ops on
        LLM failure — the player can still read the final narrator beat;
        the frontend will show 'ending generation failed, refresh' if it
        sees is_complete=False on a budget-reached turn."""
        full_history = self._repo.list_story_messages(session_id)
        try:
            result = synthesize_ending(
                gateway=self.gateway,
                seed=template.seed,
                title=template.title,
                cast=template.cast,
                history=full_history,
                turn_count=len([m for m in full_history if m.role == "narrator"]) - 1,
                player_role=player_role,
                language=template.language,
            )
        except (NarrativeGatewayError, ValueError) as exc:
            print(
                f"[narrative.service] ending synthesis failed for session={session_id}: {exc}",
                flush=True,
            )
            return None
        tier = tier_for_label(result.label)
        # Synthesize highlights + branches AFTER ending exists. Both
        # non-fatal — return [] on any failure. Run in parallel since
        # they're independent LLM calls — cuts post-game wait from
        # ~9s sequential to ~5s.
        with ThreadPoolExecutor(max_workers=2) as pool:
            hl_future = pool.submit(
                synthesize_highlights,
                gateway=self.gateway,
                seed=template.seed,
                title=template.title,
                cast=template.cast,
                history=full_history,
                ending_label=result.label,
                ending_subtitle=result.subtitle,
                player_role=player_role,
                language=template.language,
            )
            br_future = pool.submit(
                synthesize_branches,
                gateway=self.gateway,
                seed=template.seed,
                title=template.title,
                cast=template.cast,
                history=full_history,
                ending_label=result.label,
                ending_tier=tier,
                ending_passage=result.passage,
                player_role=player_role,
                language=template.language,
            )
            highlights = hl_future.result()
            branches = br_future.result()
        self._repo.record_session_ending(
            session_id,
            label=result.label,
            subtitle=result.subtitle,
            passage=result.passage,
            tier=tier,  # type: ignore[arg-type]
            early_terminated=False,
            failure_trigger=None,
            highlights=highlights or None,
            branches=branches or None,
        )
        completed_session = self._repo.get_session(session_id)
        _emit_metric(
            "session_completed",
            session_id=session_id,
            template_id=template.template_id,
            ending_label=result.label,
            tier=tier,
            early=0,
            turn_count=completed_session.turn_count,
            turn_budget=completed_session.turn_budget,
            num_highlights=len(highlights),
            num_branches=len(branches),
        )
        return NarrativeEnding(
            label=result.label,
            subtitle=result.subtitle,
            passage=result.passage,
            tier=tier,  # type: ignore[arg-type]
            early_terminated=False,
            failure_trigger=None,
            highlights=highlights,
            branches=branches,
        )

    def _finalize_session_early(
        self,
        session_id: str,
        template: NarrativeTemplate,
        *,
        failure_trigger: str,
        failure_reason: str,
        player_role: PlayerRole | None = None,
    ) -> NarrativeEnding | None:
        """Gauntlet-mode collapse: judge_failure flagged a trigger this
        turn. Generate a 'collapsed' ending right now, regardless of
        turn_budget."""
        full_history = self._repo.list_story_messages(session_id)
        try:
            result = synthesize_early_ending(
                gateway=self.gateway,
                seed=template.seed,
                title=template.title,
                cast=template.cast,
                history=full_history,
                failure_trigger=failure_trigger,
                failure_reason=failure_reason,
                player_role=player_role,
                language=template.language,
            )
        except (NarrativeGatewayError, ValueError) as exc:
            print(
                f"[narrative.service] early-ending synthesis failed for session={session_id}: {exc}",
                flush=True,
            )
            return None
        # Early endings are always tier=collapsed by design.
        tier = "collapsed"
        # Highlights + branches for the early collapse. Branches
        # especially valuable here — "you'd have hit a non-collapse
        # ending if you'd done X earlier" is core replay incentive.
        # Parallelize for the same latency win as the full ending path.
        with ThreadPoolExecutor(max_workers=2) as pool:
            hl_future = pool.submit(
                synthesize_highlights,
                gateway=self.gateway,
                seed=template.seed,
                title=template.title,
                cast=template.cast,
                history=full_history,
                ending_label=result.label,
                ending_subtitle=result.subtitle,
                player_role=player_role,
                language=template.language,
            )
            br_future = pool.submit(
                synthesize_branches,
                gateway=self.gateway,
                seed=template.seed,
                title=template.title,
                cast=template.cast,
                history=full_history,
                ending_label=result.label,
                ending_tier=tier,
                ending_passage=result.passage,
                player_role=player_role,
                language=template.language,
            )
            highlights = hl_future.result()
            branches = br_future.result()
        self._repo.record_session_ending(
            session_id,
            label=result.label,
            subtitle=result.subtitle,
            passage=result.passage,
            tier=tier,  # type: ignore[arg-type]
            early_terminated=True,
            failure_trigger=failure_trigger,
            highlights=highlights or None,
            branches=branches or None,
        )
        completed_session = self._repo.get_session(session_id)
        _emit_metric(
            "session_completed",
            session_id=session_id,
            template_id=template.template_id,
            ending_label=result.label,
            tier=tier,
            early=1,
            trigger=failure_trigger,
            turn_count=completed_session.turn_count,
            turn_budget=completed_session.turn_budget,
            num_highlights=len(highlights),
            num_branches=len(branches),
        )
        return NarrativeEnding(
            label=result.label,
            subtitle=result.subtitle,
            passage=result.passage,
            tier=tier,  # type: ignore[arg-type]
            early_terminated=True,
            failure_trigger=failure_trigger,
            highlights=highlights,
            branches=branches,
        )

    # ------------------------------------------------------------------
    # Ending / replay / distribution reads
    # ------------------------------------------------------------------

    def get_session_ending(
        self, session_id: str, *, player_user_id: str
    ) -> NarrativeEnding | None:
        session = self._load_session_for_player(session_id, player_user_id)
        if session.ending_label is None:
            return None
        tier = session.ending_tier or tier_for_label(session.ending_label)
        highlights = self._repo.get_session_highlights(session_id)
        branches = self._repo.get_session_branches(session_id)
        return NarrativeEnding(
            label=session.ending_label,
            subtitle=session.ending_subtitle or "",
            passage=session.ending_passage or "",
            tier=tier,  # type: ignore[arg-type]
            early_terminated=session.early_terminated,
            failure_trigger=session.failure_trigger,
            highlights=highlights,
            branches=branches,
        )

    def get_ending_distribution(
        self, template_id: str, *, viewer_user_id: str
    ) -> EndingDistributionResponse:
        # Distribution is readable for any viewer who can see the template.
        self._load_template_for_viewer(template_id, viewer_user_id)
        rows = self._repo.list_completed_endings_for_template(template_id)
        total = sum(n for _, n in rows)
        return EndingDistributionResponse(
            template_id=template_id,
            total_completed=total,
            entries=[EndingDistributionEntry(label=lbl, count=n) for lbl, n in rows],
        )

    def get_public_replay(self, session_id: str) -> PublicReplayResponse:
        """Public, auth-free read of a completed (or in-progress) session.

        Anyone with the session_id URL can see the full playthrough — that's
        the point: shareable replay URLs."""
        try:
            session = self._repo.get_session(session_id)
        except NarrativeNotFoundError as exc:
            raise NarrativeServiceError(
                code="session_not_found",
                message=f"Narrative session not found: {session_id}",
                status_code=404,
            ) from exc
        _emit_metric(
            "replay_viewed",
            session_id=session_id,
            template_id=session.template_id,
            completed=int(session.ending_label is not None),
        )
        try:
            template = self._repo.get_template(session.template_id)
        except NarrativeNotFoundError as exc:
            raise NarrativeServiceError(
                code="template_not_found",
                message=f"Template not found: {session.template_id}",
                status_code=404,
            ) from exc
        messages = self._repo.list_story_messages(session_id)
        advisor_messages = self._repo.list_advisor_messages(session_id)
        ending_payload: NarrativeEnding | None = None
        if session.ending_label is not None:
            tier = session.ending_tier or tier_for_label(session.ending_label)
            highlights = self._repo.get_session_highlights(session_id)
            branches = self._repo.get_session_branches(session_id)
            ending_payload = NarrativeEnding(
                label=session.ending_label,
                subtitle=session.ending_subtitle or "",
                passage=session.ending_passage or "",
                tier=tier,  # type: ignore[arg-type]
                early_terminated=session.early_terminated,
                failure_trigger=session.failure_trigger,
                highlights=highlights,
                branches=branches,
            )
        is_shareable_template = template.visibility != "private"
        return PublicReplayResponse(
            session_id=session.session_id,
            template_id=session.template_id,
            template_forkable=is_shareable_template,
            template_title=template.title if is_shareable_template else PRIVATE_REPLAY_TITLE,
            template_seed=template.seed if is_shareable_template else "",
            cast=_public_replay_cast(template.cast) if is_shareable_template else [],
            advisor_persona=template.advisor_persona if is_shareable_template else "",
            player_goals=template.player_goals if is_shareable_template else [],
            player_role=None,
            turn_budget=session.turn_budget,
            turn_count=session.turn_count,
            difficulty=session.difficulty,
            completed=ending_payload is not None,
            ending=ending_payload,
            messages=messages,
            advisor_messages=advisor_messages,
            created_at=session.created_at,
        )

    # ------------------------------------------------------------------
    # Advisor side-chat
    # ------------------------------------------------------------------

    def ask_advisor(
        self,
        session_id: str,
        request: AdvisorAskRequest,
        *,
        player_user_id: str,
    ) -> AdvisorAskResponse:
        session = self._load_session_for_player(session_id, player_user_id)
        template = self._repo.get_template(session.template_id)
        question = request.question.strip()
        if not question:
            raise NarrativeServiceError(
                code="question_required",
                message="Question must not be empty.",
                status_code=422,
            )
        story_history = self._repo.list_story_messages(session_id)
        advisor_history = self._repo.list_advisor_messages(session_id)

        # Oracle mode: charge 1 turn from session.turn_budget, then call
        # the privileged-info variant of advisor. Cap-floor at 1 inside
        # the repo so we don't bottom out a session mid-asking.
        # If session is already complete, oracle is rejected.
        is_oracle = bool(request.oracle_mode)
        if is_oracle and session.ending_label is not None:
            raise NarrativeServiceError(
                code="session_complete",
                message="这一局已经走完了，不能再消耗回合换情报。",
                status_code=409,
            )

        reply_text: str | None = None
        try:
            if is_oracle:
                # Resolve the active player_role for privileged context.
                active_role = _resolve_player_role(template, session.selected_player_role_id)
                starting_assets = active_role.starting_assets if active_role else []
                current_inventory = compute_current_inventory(starting_assets, story_history)
                reply = ask_advisor_oracle(
                    gateway=self.gateway,
                    seed=template.seed,
                    title=template.title,
                    cast=template.cast,
                    advisor_persona=template.advisor_persona,
                    story_history=story_history,
                    advisor_history=advisor_history,
                    question=question,
                    player_role=active_role,
                    failure_conditions=template.failure_conditions or None,
                    current_inventory=current_inventory or None,
                    language=template.language,
                )
            else:
                reply = ask_advisor(
                    gateway=self.gateway,
                    seed=template.seed,
                    title=template.title,
                    cast=template.cast,
                    advisor_persona=template.advisor_persona,
                    story_history=story_history,
                    advisor_history=advisor_history,
                    question=question,
                    language=template.language,
                )
            reply_text = reply.reply_text
        except NarrativeGatewayError as exc:
            if _is_content_moderation_failure(exc):
                reply_text = _CONTENT_MODERATION_FALLBACK
            else:
                raise NarrativeServiceError(
                    code=exc.code, message=exc.message, status_code=exc.status_code
                ) from exc
        except ValueError as exc:
            raise NarrativeServiceError(
                code="advisor_invalid",
                message=f"LLM returned an unusable advisor reply: {exc}",
                status_code=502,
            ) from exc

        assert reply_text is not None
        next_ord = self._repo.next_advisor_ord(session_id)
        player_message = AdvisorMessage(ord=next_ord, role="player", content=question)
        advisor_message = AdvisorMessage(
            ord=next_ord + 1, role="advisor", content=reply_text
        )
        self._repo.append_advisor_message(session_id, player_message)
        self._repo.append_advisor_message(session_id, advisor_message)
        self._repo.touch_session(session_id)

        # Charge the oracle cost AFTER the LLM call succeeds — don't
        # decrement budget if the call failed.
        new_budget: int | None = None
        if is_oracle:
            new_budget = self._repo.decrement_turn_budget(session_id, by=1)
            _emit_metric(
                "advisor_oracle_used",
                session_id=session_id,
                template_id=template.template_id,
                new_budget=new_budget,
            )
        _emit_metric(
            "advisor_used",
            session_id=session_id,
            template_id=template.template_id,
            oracle=int(is_oracle),
        )

        return AdvisorAskResponse(
            player_message=player_message,
            advisor_message=advisor_message,
            turn_budget_after=new_budget,
            oracle_used=is_oracle,
        )

    def get_advisor_history(
        self, session_id: str, *, player_user_id: str
    ) -> AdvisorHistoryResponse:
        session = self._load_session_for_player(session_id, player_user_id)
        template = self._repo.get_template(session.template_id)
        messages = self._repo.list_advisor_messages(session_id)
        return AdvisorHistoryResponse(
            persona=template.advisor_persona,
            messages=messages,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _spawn_session(
        self,
        template: NarrativeTemplate,
        player_user_id: str,
        turn_budget: int = 12,
        difficulty: str = "story",
        *,
        player_role_index: int | None = None,
    ) -> tuple[NarrativeSession, StoryMessage]:
        session_id = _generate_session_id()
        # Cast difficulty into the typed Literal — defensive; service-layer
        # callers may pass anything, but only the two values are valid.
        norm_difficulty: str = "gauntlet" if difficulty == "gauntlet" else "story"
        # Resolve which role_id this session is locked to. None when the
        # template was created before player roles existed (legacy).
        selected_role_id: str | None = None
        if (
            player_role_index is not None
            and 0 <= player_role_index < len(template.player_role_options)
        ):
            selected_role_id = template.player_role_options[player_role_index].role_id
        session = self._repo.create_session(
            session_id=session_id,
            template_id=template.template_id,
            player_user_id=player_user_id,
            turn_budget=turn_budget,
            difficulty=norm_difficulty,  # type: ignore[arg-type]
            selected_player_role_id=selected_role_id,
        )
        opening_message = StoryMessage(
            ord=0,
            role="narrator",
            content=template.opening_passage,
            options=template.opening_options,
            chosen_option_index=None,
        )
        self._repo.append_story_message(session_id, opening_message)
        self._repo.increment_play_count(template.template_id)
        return session, opening_message

    def _load_template_for_viewer(
        self, template_id: str, viewer_user_id: str
    ) -> NarrativeTemplate:
        try:
            template = self._repo.get_template(template_id)
        except NarrativeNotFoundError as exc:
            raise NarrativeServiceError(
                code="template_not_found",
                message=f"Narrative template not found: {template_id}",
                status_code=404,
            ) from exc
        if template.visibility == "private" and template.owner_user_id != viewer_user_id:
            raise NarrativeServiceError(
                code="template_forbidden",
                message="This template is private.",
                status_code=403,
            )
        return template

    def _load_template_for_owner(
        self, template_id: str, owner_user_id: str
    ) -> NarrativeTemplate:
        template = self._load_template_for_viewer(template_id, owner_user_id)
        if template.owner_user_id != owner_user_id:
            raise NarrativeServiceError(
                code="template_forbidden",
                message="Only the template creator can do this.",
                status_code=403,
            )
        return template

    def _load_session_for_player(
        self, session_id: str, player_user_id: str
    ) -> NarrativeSession:
        try:
            session = self._repo.get_session(session_id)
        except NarrativeNotFoundError as exc:
            raise NarrativeServiceError(
                code="session_not_found",
                message=f"Narrative session not found: {session_id}",
                status_code=404,
            ) from exc
        if session.player_user_id != player_user_id:
            raise NarrativeServiceError(
                code="session_forbidden",
                message="You do not own this play session.",
                status_code=403,
            )
        return session

    @staticmethod
    def _resolve_player_action(
        request: AdvanceTurnRequest, last_narrator: StoryMessage
    ) -> tuple[str, int | None]:
        if request.free_input and request.free_input.strip():
            return request.free_input.strip(), None
        idx = request.chosen_option_index
        if idx is None:
            raise NarrativeServiceError(
                code="action_required",
                message="Provide either chosen_option_index or free_input.",
                status_code=422,
            )
        if idx < 0 or idx >= len(last_narrator.options):
            raise NarrativeServiceError(
                code="option_out_of_range",
                message=f"chosen_option_index {idx} is out of range.",
                status_code=422,
            )
        option = last_narrator.options[idx]
        return option.label, idx

    @staticmethod
    def _resolve_played_leverage(
        request: AdvanceTurnRequest, active_role: PlayerRole | None
    ) -> PlayedLeverageCard | None:
        if request.played_leverage is None:
            return None
        if active_role is None:
            raise NarrativeServiceError(
                code="leverage_not_available",
                message="This session has no player role leverage cards.",
                status_code=422,
            )
        card = request.played_leverage
        owned = any(
            item.npc_id == card.npc_id and item.leverage == card.leverage
            for item in active_role.leverages_over_npcs
        )
        if not owned:
            raise NarrativeServiceError(
                code="leverage_not_available",
                message="That leverage card is not available to this player role.",
                status_code=422,
            )
        return card


def _resolve_player_role(
    template: NarrativeTemplate, role_id: str | None
) -> PlayerRole | None:
    """Find the PlayerRole for a session's selected_player_role_id.

    Returns None if the session has no role pinned (legacy) or the role
    no longer exists on the template (defensive — shouldn't happen in
    practice).
    """
    if role_id is None or not template.player_role_options:
        return None
    for role in template.player_role_options:
        if role.role_id == role_id:
            return role
    return None


def _public_replay_cast(cast: list[CastMember]) -> list[CastMember]:
    return [
        member.model_copy(
            update={
                "hidden_objective": None,
                "leverage_over_player": None,
                "leverages_over_other_npcs": [],
            }
        )
        for member in cast
    ]


def _story_brief_prefers_reliable_opening(brief: StoryBrief) -> bool:
    """Use deterministic opening first for briefs likely to burn retry budget.

    The live generator is still preferred for ordinary briefs. This gate is for
    heavily adapted prompts where the planner already had to cap or compress a
    large cast, especially comedy/cozy briefs with explicitly preserved
    background parties. Those are the cases that have been reliable only after
    a long retry tail.
    """
    plan = brief.cast_plan
    has_cap_pressure = plan.input_entity_count > 10 or bool(plan.omitted_entities)
    has_heavy_window = plan.input_entity_count >= 10 and len(plan.secondary_background_entities) >= 5
    has_explicit_representation = any(
        marker in brief.original_seed.lower()
        for marker in ("represent ", "must include", "should include", "focus on", "preserve ")
    )
    lower_stakes_profile = brief.tension_profile in {"comedy", "cozy_mystery"}
    return has_cap_pressure or (
        lower_stakes_profile
        and has_heavy_window
        and (has_explicit_representation or bool(brief.compressed_constraints))
    )


def _should_use_reliable_opening_fallback(
    exc: NarrativeGatewayError | NarrativeServiceError,
) -> bool:
    return exc.code in _RELIABLE_OPENING_FALLBACK_CODES


def _should_use_turn_runtime_fallback(
    exc: NarrativeGatewayError | NarrativeServiceError,
) -> bool:
    return exc.code in _TURN_RUNTIME_FALLBACK_CODES


def _deterministic_turn_fallback(
    *,
    template: NarrativeTemplate,
    history: list[StoryMessage],
    player_action: str,
    next_ord: int,
    turn_index: int,
    turn_budget: int,
    difficulty: str,
    player_role: PlayerRole | None,
    current_inventory: list[str] | None,
    played_leverage: PlayedLeverageCard | None,
) -> TurnResult:
    """Small deterministic narrator beat for beta/reviewer continuity.

    This only runs when the live narrator gateway cannot be called or returns
    unusable data. It keeps the scene playable without presenting itself as a
    full model-authored turn.
    """
    agent_plan = build_agent_plan(
        cast=template.cast,
        history=history,
        turn_index=turn_index,
        turn_budget=turn_budget,
        difficulty=difficulty,
        player_role=player_role,
        current_inventory=current_inventory,
        played_leverage=played_leverage,
        narrator_ord=next_ord,
    )
    profile = _template_tension_profile(template)
    pulses = _fallback_turn_pulses(
        template=template,
        agent_plan=agent_plan,
        played_leverage=played_leverage,
        profile=profile,
    )
    passage = _fallback_turn_passage(
        template=template,
        player_action=player_action,
        agent_plan=agent_plan,
        pulses=pulses,
        profile=profile,
    )
    return TurnResult(
        narrator_message=StoryMessage(
            ord=next_ord,
            role="narrator",
            content=passage,
            options=_fallback_turn_options(template, profile),
            chosen_option_index=None,
            npc_pulse=pulses,
            inventory_delta=None,
        ),
        agent_plan=agent_plan,
    )


def _template_tension_profile(template: NarrativeTemplate) -> str:
    text = " ".join([template.seed, template.title, template.opening_passage]).casefold()
    if any(term in text for term in ("cozy", "bake sale", "cupcake", "recipe", "gentle mystery")):
        return "cozy_mystery"
    if any(term in text for term in ("comedy", "talent show", "callback", "misunderstanding", "playful")):
        return "comedy"
    if any(term in text for term in ("fantasy", "sci-fi", "science fiction", "dragon", "eclipse", "library", "mars", "colony")):
        return "fantasy_sci_fi"
    if any(term in text for term in ("family", "wedding", "parents", "dinner")):
        return "family_social"
    return "high_drama"


def _fallback_turn_pulses(
    *,
    template: NarrativeTemplate,
    agent_plan: AgentPlan,
    played_leverage: PlayedLeverageCard | None,
    profile: str,
) -> list[NPCPulse]:
    cast_by_id = {member.character_id: member for member in template.cast}
    candidate_ids: list[str] = []
    if played_leverage is not None and played_leverage.npc_id in cast_by_id:
        candidate_ids.append(played_leverage.npc_id)
    candidate_ids.extend(
        npc_id for npc_id in agent_plan.director.active_npc_ids if npc_id in cast_by_id
    )
    candidate_ids.extend(
        npc_id for npc_id in agent_plan.director.focus_window_npc_ids if npc_id in cast_by_id
    )
    if not candidate_ids:
        candidate_ids = [member.character_id for member in template.cast[:2]]

    seen: set[str] = set()
    pulses: list[NPCPulse] = []
    for npc_id in candidate_ids:
        if npc_id in seen:
            continue
        seen.add(npc_id)
        member = cast_by_id[npc_id]
        pulses.append(
            NPCPulse(
                npc_id=npc_id,
                state=_fallback_turn_pulse_state(profile, played=played_leverage is not None and npc_id == played_leverage.npc_id),
                shift=_fallback_turn_pulse_shift(profile),
                reason=_fallback_turn_pulse_reason(profile),
            )
        )
        if len(pulses) >= 2:
            break
    return pulses


def _fallback_turn_pulse_state(profile: str, *, played: bool) -> str:
    if played:
        return "reacting to the shown card"
    return reliable_profile_vocabulary(profile).pulse_state


def _fallback_turn_pulse_shift(profile: str) -> str:
    return reliable_profile_vocabulary(profile).pulse_shift


def _fallback_turn_pulse_reason(profile: str) -> str:
    return reliable_profile_vocabulary(profile).pulse_reason


def _fallback_turn_passage(
    *,
    template: NarrativeTemplate,
    player_action: str,
    agent_plan: AgentPlan,
    pulses: list[NPCPulse],
    profile: str,
) -> str:
    scene = _fallback_turn_scene_label(template)
    names = _fallback_turn_names(template, pulses)
    first = names[0] if names else "the closest witness"
    second = names[1] if len(names) > 1 else "the room"
    first_subject = _fallback_sentence_start(first)
    action = _fallback_turn_action_phrase(player_action)
    after_action = _fallback_turn_after_phrase(action)
    stage_line = _fallback_turn_stage_line(agent_plan.director.stage_phase, profile)
    turn_variant = agent_plan.turn_index % 3
    object_label = _fallback_turn_object_label(template)
    if profile in {"cozy_mystery", "comedy"}:
        if turn_variant == 1:
            text = (
                f"After {after_action}, the {scene} pauses around the {object_label}. "
                f"{first_subject} {_fallback_verb(first, 'points', 'point')} to a small timing detail, and "
                f"{second} {_fallback_verb(second, 'keeps', 'keep')} the explanation light enough for repair. "
                f"{stage_line} The next move can check the timing trail, invite a quieter voice, or turn the table mistake into a payoff."
            )
        elif turn_variant == 2:
            object_verb = _fallback_verb(object_label, "becomes", "become")
            text = (
                f"The {object_label} {object_verb} easier to read after {after_action}. "
                f"{first_subject} {_fallback_verb(first, 'softens', 'soften')} first, while {second} "
                f"{_fallback_verb(second, 'notices', 'notice')} who is still hesitating. "
                f"{stage_line} The next beat can compare versions gently or let the room laugh before blame settles."
            )
        else:
            text = (
                f"The {scene} shifts after {after_action}. {first_subject} {_fallback_verb(first, 'catches', 'catch')} the detail first, "
                f"and {second} {_fallback_verb(second, 'leaves', 'leave')} room for a less dramatic explanation instead of "
                f"turning the moment into a pile-on. {stage_line} The next beat can test "
                f"the {object_label}, invite the quiet party in, or let the callback land before "
                f"anyone chooses a version of events."
            )
    elif profile == "fantasy_sci_fi":
        if turn_variant == 1:
            text = (
                f"After {after_action}, the {object_label} draws the {scene} inward. "
                f"{first_subject} {_fallback_verb(first, 'reads', 'read')} the first change, while {second} "
                f"{_fallback_verb(second, 'tests', 'test')} which old rule still holds. "
                f"{stage_line} The next beat can ask the quieter faction to interpret the sign."
            )
        elif turn_variant == 2:
            text = (
                f"The {scene} gives back a clearer sign after {after_action}. "
                f"{first_subject} {_fallback_verb(first, 'moves', 'move')} toward the {object_label}, and {second} "
                f"{_fallback_verb(second, 'tracks', 'track')} the faction claim behind it. "
                f"{stage_line} The next beat can place the artifact where everyone can answer."
            )
        else:
            text = (
                f"The {scene} answers after {after_action}. {first_subject} {_fallback_verb(first, 'turns', 'turn')} toward the visible "
                f"sign, while {second} {_fallback_verb(second, 'notices', 'notice')} which rule, artifact, or faction has "
                f"moved. {stage_line} The next beat can question the change, share the "
                f"sign with a quieter party, or hold the {object_label} where everyone can read it."
            )
    elif profile == "family_social":
        text = (
            f"The {scene} quiets after {after_action}. {first_subject} {_fallback_verb(first, 'reacts', 'react')} first, and {second} "
            f"{_fallback_verb(second, 'starts', 'start')} weighing whether this is an old wound or a repairable mistake. "
            f"{stage_line} The next beat can ask for the missing context, protect a "
            f"fragile bond, or let someone else speak before the room hardens."
        )
    else:
        text = (
            f"The {scene} absorbs {action}. {first_subject} {_fallback_verb(first, 'recalculates', 'recalculate')} in public, and "
            f"{second} {_fallback_verb(second, 'watches', 'watch')} who benefits from the new version of events. "
            f"{stage_line} The next beat can press for a concrete answer, place one "
            f"fact on the table, or wait for the next stakeholder to reveal their stake."
        )
    return normalize_whitespace(text)


def _fallback_turn_object_label(template: NarrativeTemplate) -> str:
    seed = template.seed.casefold()
    if "cupcake labels" in seed:
        return "cupcake labels"
    if "recipe card" in seed:
        return "recipe card"
    if "star map" in seed:
        return "star map"
    if "cursed index" in seed:
        return "cursed index"
    if "oxygen" in seed:
        return "oxygen rumor"
    if "talent show" in seed:
        return "talent-show cue"
    if "cupcake" in seed:
        return "cupcake clue"
    if "prop" in seed:
        return "shared prop"
    if "artifact" in seed:
        return "artifact"
    return "visible detail"


def _fallback_turn_scene_label(template: NarrativeTemplate) -> str:
    text = " ".join([template.seed, template.title, template.opening_passage]).casefold()
    if "mars" in text and "talent show" in text:
        return "Mars colony talent-show floor"
    if "bake sale" in text or "cupcake" in text:
        return "neighborhood bake-sale table"
    if "eclipse" in text and "library" in text:
        return "eclipse-lit library"
    if "library" in text:
        return "library hall"
    if "board" in text or "vote" in text:
        return "boardroom"
    if "dinner" in text:
        return "family table"
    return "room"


def _fallback_turn_names(template: NarrativeTemplate, pulses: list[NPCPulse]) -> list[str]:
    cast_by_id = {member.character_id: member for member in template.cast}
    names = [
        cast_by_id[pulse.npc_id].display_name
        for pulse in pulses
        if pulse.npc_id in cast_by_id
    ]
    if len(names) < 2:
        for member in template.cast:
            if member.display_name not in names:
                names.append(member.display_name)
            if len(names) >= 2:
                break
    return names


def _fallback_name_is_plural(name: str) -> bool:
    lower = name.strip().casefold()
    if not lower or lower in {"the room", "the boardroom", "the family table"}:
        return False
    if lower in {"hydroponics", "communications", "finance", "transit", "medical", "education", "security"}:
        return False
    if any(token in lower for token in (" and ", ",", "&")):
        return True
    last = re.sub(r"[^a-z]+", "", lower.split()[-1]) if lower.split() else lower
    if last.endswith(("ss", "us")):
        return False
    return last.endswith("s")


def _fallback_verb(name: str, singular: str, plural: str) -> str:
    return plural if _fallback_name_is_plural(name) else singular


def _fallback_turn_action_phrase(player_action: str) -> str:
    text = normalize_whitespace(re.sub(r"^\[[^\]]+\]\s*", "", player_action or "your move"))
    if not text:
        return "your move"
    if len(text) > 120:
        text = f"{text[:117].rstrip()}..."
    if text[:1].isupper() and " " in text[:40]:
        text = text[:1].lower() + text[1:]
    return f"your move to {text}" if not text.startswith("your ") else text


def _fallback_turn_after_phrase(action_phrase: str) -> str:
    if action_phrase.startswith("your move to "):
        return f"you {action_phrase.removeprefix('your move to ')}"
    if action_phrase.startswith("your move"):
        return "your move"
    return action_phrase


def _fallback_turn_stage_line(stage_phase: str, profile: str) -> str:
    return reliable_profile_vocabulary(profile).stage_line(stage_phase)


def _fallback_turn_options(template: NarrativeTemplate, profile: str) -> list[StoryOption]:
    object_label = _fallback_turn_object_label(template)
    if profile == "cozy_mystery":
        return [
            StoryOption(label=f"[Ally] Let the shy witness describe the {object_label}", hint="Keeps the mystery gentle", handle="ask witness"),
            StoryOption(label=f"[Probe] Check the {object_label} without blaming anyone", hint="Tests the clue first", handle="check clue"),
            StoryOption(label="[Watch] Give the room a softer reset", hint="Buys a calmer beat", handle="soft reset"),
        ]
    if profile == "comedy":
        return [
            StoryOption(label="[Ally] Invite the overlooked group into the test", hint="Keeps the joke shared", handle="invite group"),
            StoryOption(label=f"[Probe] Ask who noticed the {object_label} change", hint="Turns timing into evidence", handle="ask prop"),
            StoryOption(label="[Watch] Let the callback settle before moving", hint="Waits for the room to react", handle="let land"),
        ]
    if profile == "fantasy_sci_fi":
        return [
            StoryOption(label="[Probe] Ask which old rule changed", hint="Turns the sign into a clue", handle="ask rule"),
            StoryOption(label="[Ally] Let the quieter faction interpret the sign", hint="Gives background pressure a voice", handle="quiet voice"),
            StoryOption(label=f"[Watch] Hold the {object_label} where everyone can see it", hint="Keeps the room honest", handle="show object"),
        ]
    if profile == "family_social":
        return [
            StoryOption(label="[Ally] Give the hurt party room to explain", hint="Protects repair before rupture", handle="give room"),
            StoryOption(label="[Probe] Ask what was misunderstood first", hint="Looks for the old wound", handle="ask wound"),
            StoryOption(label="[Watch] Let someone else name the cost", hint="Tests who still cares", handle="wait cost"),
        ]
    return [
        StoryOption(label="[Probe] Ask who benefits from this version", hint="Tests the public account", handle="ask benefit"),
        StoryOption(label="[Counter] Put one concrete fact on the table", hint="Makes the room answer", handle="show fact"),
        StoryOption(label="[Watch] Let the next speaker expose their stake", hint="Delays without yielding", handle="watch stake"),
    ]


def _story_brief_fallback_opening(brief: StoryBrief, *, language: str) -> OpeningResult:
    """Deterministic repair opening used only after LLM brief generation fails.

    It preserves the reviewed brief contract instead of silently relaxing user
    constraints. The result is intentionally plain but playable.
    """
    del language
    primary_entities = [
        entity
        for entity in brief.cast_plan.primary_active_entities
        if entity.kind in {"character", "faction", "object"}
    ]
    if len(primary_entities) < 3:
        primary_entities = [
            entity
            for entity in [*brief.cast_plan.primary_active_entities, *brief.cast_plan.secondary_background_entities]
            if entity.kind in {"character", "faction", "object"}
        ]
    cast_names = [entity.display_name for entity in primary_entities[:5]]
    if len(cast_names) < 3:
        cast_names = ["Organizer", "Concerned witness", "Deadline holder", "Outside voice"]
    background_names = [
        entity.display_name
        for entity in brief.cast_plan.secondary_background_entities
        if entity.display_name not in cast_names
    ]
    protected_background_names = {
        entity.display_name
        for entity in brief.cast_plan.secondary_background_entities
        if "explicitly emphasized" in entity.rationale.casefold()
    }
    cast = _fallback_cast_members(
        cast_names,
        background_names=background_names,
        protected_background_names=protected_background_names,
    )
    pressure_labels = _fallback_pressure_labels(brief)
    opening_text = _fallback_opening_passage(
        brief=brief,
        cast_names=_fallback_opening_focus_names(cast_names),
        background_names=background_names,
        protected_background_names=protected_background_names,
        pressure_labels=pressure_labels,
    )
    options = _fallback_opening_options(brief)
    player_roles = _fallback_player_roles(brief, cast[: len(cast_names)])
    return OpeningResult(
        title=_fallback_title(brief, pressure_labels),
        advisor_persona="A careful advisor watches who is heard, what pressure is visible, and how the tone stays on track.",
        cast=cast,
        opening_message=StoryMessage(ord=0, role="narrator", content=opening_text, options=options),
        player_goals=[
            PlayerGoal(
                goal="Keep the key parties in the room before one side controls the first decision.",
                stakes="If a quiet party disappears, the opening turns into a generic argument.",
            ),
            PlayerGoal(
                goal="Create one concrete payoff that matches the selected profile.",
                stakes="The first exchange needs a clue, prop, decision, or callback that the next turn can use.",
            ),
        ],
        failure_conditions=[
            FailureCondition(
                label="One-sided room",
                description="Several turns pass while important parties remain invisible or unheard.",
            ),
            FailureCondition(
                label="No payoff",
                description="The room circles the premise without a visible clue, prop, decision, or callback.",
            ),
        ],
        player_role_options=player_roles,
    )


def _fallback_cast_members(
    names: list[str],
    *,
    background_names: list[str] | None = None,
    protected_background_names: set[str] | None = None,
) -> list[CastMember]:
    all_names = [*names, *(background_names or [])[: max(0, 10 - len(names))]]
    ids = [_fallback_slug(name) or f"party_{idx + 1}" for idx, name in enumerate(all_names)]
    protected = protected_background_names or set()
    cast: list[CastMember] = []
    for idx, name in enumerate(all_names):
        target_ids = [target_id for target_id in ids if target_id != ids[idx]][:2]
        is_background = idx >= len(names)
        is_protected_background = is_background and name in protected
        cast.append(
            CastMember(
                character_id=ids[idx],
                display_name=_fallback_label(name, limit=40),
                role=(
                    "Protected background stakeholder"
                    if is_protected_background
                    else "Background stakeholder"
                    if is_background
                    else "Involved party"
                ),
                relation_to_protagonist=(
                    "Protected context the prompt emphasized; kept visible outside the active focus window."
                    if is_protected_background
                    else
                    "Visible context kept in the room for later turns."
                    if is_background
                    else "A party whose reaction can shift the next choice."
                ),
                hidden_objective=(
                    None
                    if is_background
                    else f"Make sure {name[:70]} is heard before the decision lands."
                ),
                leverage_over_player=None if is_background else "Knows which detail the room keeps avoiding.",
                leverages_over_other_npcs=[] if is_background else [
                    NPCLeverageOverNPC(
                        target_npc_id=target_id,
                        leverage="Can point to the missing detail that changes who gets heard.",
                    )
                    for target_id in target_ids
                ],
            )
        )
    return cast


def _fallback_player_roles(brief: StoryBrief, cast: list[CastMember]) -> list[PlayerRole]:
    role_names = _fallback_role_names(brief)
    object_label = _fallback_contested_object(brief.original_seed)
    roles: list[PlayerRole] = []
    for idx, role_name in enumerate(role_names):
        target = cast[idx % len(cast)]
        roles.append(
            PlayerRole(
                role_id=_fallback_slug(role_name)[:32] or f"role_{idx + 1}",
                label=_fallback_label(role_name, limit=24),
                public_persona=_fallback_role_persona(role_name, brief, object_label),
                hidden_objective=_fallback_role_objective(brief, object_label),
                leverages_over_npcs=[
                    PlayerLeverageOverNPC(
                        npc_id=target.character_id,
                        leverage=_fallback_role_leverage(target.display_name, brief, object_label),
                    )
                ],
                starting_assets=[_fallback_label(_fallback_starting_asset(brief, object_label), limit=80)],
            )
        )
    return roles


def _fallback_role_names(brief: StoryBrief) -> list[str]:
    seed = brief.original_seed.casefold()
    if "bake sale" in seed or "cupcake" in seed:
        return ["Label checker", "Bake-sale host", "Volunteer ally"]
    if "mars" in seed and "talent show" in seed:
        return ["Talent-show liaison", "Rumor handler", "Audience mediator"]
    if "eclipse" in seed and "library" in seed:
        return ["Star-map witness", "Eclipse steward", "Spellbook ally"]
    if brief.tension_profile == "cozy_mystery":
        return ["Clue keeper", "Gentle witness", "Calm host"]
    if brief.tension_profile == "comedy":
        return ["Callback keeper", "Timing witness", "Audience ally"]
    if brief.tension_profile == "fantasy_sci_fi":
        return ["Artifact witness", "Faction go-between", "Rule steward"]
    return ["Room mediator", "Scene witness", "Pressure holder"]


def _fallback_role_persona(role_name: str, brief: StoryBrief, object_label: str) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return f"You are the {role_name.lower()} watching how the {object_label} changes the room's old rules."
    if brief.tension_profile in {"cozy_mystery", "comedy"}:
        return f"You are the {role_name.lower()} keeping the {object_label} concrete without turning the room against anyone."
    return f"You are the {role_name.lower()} trying to keep the exchange concrete and fair."


def _fallback_role_objective(brief: StoryBrief, object_label: str) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return f"Use the {object_label} to make the artifact, faction, or old rule visible before the room hardens."
    if brief.tension_profile in {"cozy_mystery", "comedy"}:
        return f"Use the {object_label} to create a payoff without blame taking over."
    return "Bring the quiet parties, pressure, and payoff into view before one side controls the room."


def _fallback_role_leverage(target_name: str, brief: StoryBrief, object_label: str) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return f"You noticed how the {object_label} points back to {target_name}'s faction or old rule."
    if brief.tension_profile in {"cozy_mystery", "comedy"}:
        return f"You noticed a harmless detail about the {object_label} that gives {target_name} a way to explain."
    return f"You know why {target_name} needs to be heard before the choice lands."


def _fallback_starting_asset(brief: StoryBrief, object_label: str) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return f"{brief.intervention_card_label}: {object_label} sign"
    if brief.tension_profile in {"cozy_mystery", "comedy"}:
        return f"{brief.intervention_card_label}: {object_label} note"
    return brief.intervention_card_label


def _fallback_opening_passage(
    *,
    brief: StoryBrief,
    cast_names: list[str],
    background_names: list[str],
    protected_background_names: set[str] | None = None,
    pressure_labels: list[str],
) -> str:
    active_cast_names, context_names = _fallback_opening_name_groups(
        cast_names,
        background_names,
        protected_background_names=protected_background_names or set(),
    )
    cast_text = _fallback_names_text(active_cast_names)
    cast_text_mid_sentence = _fallback_names_text(active_cast_names, sentence_start=False)
    seed = brief.original_seed
    scene = _fallback_scene_label(brief, pressure_labels)
    contested = _fallback_contested_object(seed)
    secondary_event = _fallback_secondary_event_clause(pressure_labels, scene)
    background_text = _fallback_background_sentence(context_names, brief=brief)
    profile_clause = _fallback_profile_clause(brief, contested=contested)
    first_move = _fallback_first_move_clause(brief)
    if _fallback_uses_fantasy_scene(brief):
        return (
            f"In {scene}, {_fallback_contested_status(contested)} just as {_fallback_event_phrase(pressure_labels)} starts to matter{secondary_event}. "
            f"{cast_text} {_fallback_verb(cast_text, 'is', 'are')} trying to read what the old rule means now.{background_text} "
            f"{profile_clause} {first_move}"
        )
    if brief.tension_profile in {"comedy", "cozy_mystery"}:
        uncertainty = reliable_profile_vocabulary(brief.tension_profile).opening_uncertainty
        return (
            f"At {scene}, the {contested} {_fallback_verb(contested, 'has', 'have')} pulled {cast_text_mid_sentence} into the same public moment while the room is still deciding "
            f"{uncertainty}{secondary_event}.{background_text} "
            f"{profile_clause} {first_move}"
        )
    return (
        f"At {scene}, {cast_text} are already circling the {contested}, each trying to make the first public account stick{secondary_event}."
        f"{background_text} {profile_clause} {first_move}"
    )


def _fallback_opening_name_groups(
    cast_names: list[str],
    background_names: list[str],
    *,
    protected_background_names: set[str],
) -> tuple[list[str], list[str]]:
    active_limit = 3 if len(cast_names) > 4 else 5
    active = cast_names[:active_limit]
    ordered_background_names = sorted(
        [*cast_names[active_limit:], *background_names],
        key=lambda name: (0 if name in protected_background_names else 1, name.casefold()),
    )
    seen: set[str] = set()
    background: list[str] = []
    for name in ordered_background_names:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        background.append(name)
    return active or cast_names[:5] or ["the key parties"], background


def _fallback_scene_label(brief: StoryBrief, pressure_labels: list[str]) -> str:
    seed = brief.original_seed.lower()
    event = _fallback_event_label(pressure_labels)
    setting = _fallback_setting_label(brief, pressure_labels)
    if "mars" in seed and event and "talent show" in event.lower():
        return "the Mars colony talent show"
    if "bake sale" in seed:
        return "the neighborhood bake sale" if "neighborhood" in seed else "the bake sale"
    if "floating dragon library" in seed:
        return "the floating dragon library"
    if "library" in seed:
        return "the library"
    if setting and event and setting.lower() not in event.lower():
        return f"the {setting} {event}"
    if event:
        return f"the {event}"
    if setting:
        return f"the {setting}"
    return "the public room"


def _fallback_setting_label(brief: StoryBrief, pressure_labels: list[str]) -> str:
    labels = [
        label
        for label in [*[item.label for item in brief.world_setting_pressure], *pressure_labels]
        if any(token in label.lower() for token in ("mars", "colony", "library", "school", "sale", "setting"))
    ]
    if not labels:
        return ""
    label = labels[0]
    if label.lower() == "library setting":
        return "library"
    return label


def _fallback_event_label(pressure_labels: list[str]) -> str:
    setting_terms = ("mars", "colony", "library", "school", "setting")
    for label in pressure_labels:
        lower = label.lower()
        if not any(token in lower for token in setting_terms):
            return label
    return ""


def _fallback_event_phrase(pressure_labels: list[str]) -> str:
    event = _fallback_event_label(pressure_labels)
    if event:
        return f"the {event}"
    return "the deadline"


def _fallback_secondary_event_clause(pressure_labels: list[str], scene: str) -> str:
    scene_lower = scene.lower()
    primary = _fallback_event_label(pressure_labels).lower()
    setting_terms = ("mars", "colony", "library", "school", "sale", "setting")
    for label in pressure_labels:
        lower = label.lower()
        if any(token in lower for token in setting_terms):
            continue
        if lower and lower not in scene_lower and lower != primary:
            return f" before the {label}"
    return ""


def _fallback_contested_object(seed: str) -> str:
    lower = seed.lower()
    if "recipe card" in lower:
        return "missing recipe card"
    if "star map" in lower:
        return "missing star map"
    if "stealing oxygen" in lower or "stolen oxygen" in lower:
        return "oxygen rumor"
    if "missing cupcake" in lower:
        return "missing cupcake"
    if "prop" in lower:
        return "shared prop"
    phrase_patterns = [
        r"\bmissing\s+([a-z][a-z\s-]{2,60}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
        r"\bstolen\s+([a-z][a-z\s-]{2,60}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
        r"\bstealing\s+([a-z][a-z\s-]{2,60}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
        r"\bswapped\s+([a-z][a-z\s-]{2,60}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
        r"\bsame\s+([a-z][a-z\s-]{2,40}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
    ]
    for pattern in phrase_patterns:
        match = re.search(pattern, lower)
        if match:
            return _fallback_object_label(match.group(1))
    if "oxygen" in lower:
        return "oxygen rumor"
    if "cupcake" in lower:
        return "cupcake mix-up"
    return "contested detail"


def _fallback_object_label(value: str) -> str:
    text = normalize_whitespace(value).strip(" -—:;,.!?")
    stop_phrases = (
        "with no",
        "with lower",
        "only misunderstandings",
        "keep it",
        "no violence",
        "no blackmail",
        "no betrayal",
    )
    lower = text.lower()
    for stop in stop_phrases:
        idx = lower.find(stop)
        if idx > 0:
            text = text[:idx].strip()
            lower = text.lower()
    text = re.sub(r"^(?:a|an|the)\s+", "", text, flags=re.I)
    lower = text.lower()
    words = text.split()
    if len(words) > 6:
        text = " ".join(words[:6])
    return text or "contested detail"


def _fallback_contested_status(contested: str) -> str:
    lower = contested.lower()
    if lower.startswith("missing "):
        return f"the {contested} is still unaccounted for"
    if lower.endswith("rumor"):
        return f"the {contested} is spreading"
    return f"the {contested} has become the room's hinge"


def _fallback_uses_fantasy_scene(brief: StoryBrief) -> bool:
    lower = " ".join(
        [
            brief.original_seed,
            brief.genre_tone,
            brief.story_kernel,
            *[item.label for item in brief.world_setting_pressure],
        ]
    ).lower()
    return any(token in lower for token in ("fantasy", "dragon", "spell", "magic", "library", "eclipse", "star map"))


def _fallback_background_sentence(background_names: list[str], *, brief: StoryBrief) -> str:
    visible_background_names = [
        name
        for name in background_names
        if not _fallback_is_scaffold_party_name(name)
    ]
    if not visible_background_names:
        return ""
    names = visible_background_names[:5]
    visible = _fallback_names_text(names)
    if brief.tension_profile == "comedy":
        return f" {visible} {_fallback_verb(visible, 'stays', 'stay')} close enough to react, heckle gently, or turn the next beat into a callback."
    if _fallback_uses_fantasy_scene(brief):
        return f" {visible} {_fallback_verb(visible, 'remains', 'remain')} at the edge of the stacks, close enough for one old rule or faction claim to matter."
    return f" {visible} {_fallback_verb(visible, 'stays', 'stay')} close enough to object, react, or pull one missing detail back into view."


def _fallback_names_text(names: list[str], *, sentence_start: bool = True) -> str:
    if not names:
        return ""
    display_names = [
        _fallback_sentence_start(name) if index == 0 and sentence_start else name
        for index, name in enumerate(names)
    ]
    if len(display_names) == 1:
        return display_names[0]
    if len(display_names) == 2:
        return f"{display_names[0]} and {display_names[1]}"
    return f"{', '.join(display_names[:-1])}, and {display_names[-1]}"


def _fallback_opening_focus_names(cast_names: list[str]) -> list[str]:
    focused = [
        name
        for name in cast_names
        if not _fallback_is_scaffold_party_name(name)
    ]
    if len(focused) >= 2:
        return focused[:5]
    return cast_names[:5] or ["the key parties"]


def _fallback_is_scaffold_party_name(name: str) -> bool:
    return name.strip().casefold() in {
        "player",
        "mix-up witness",
        "embarrassed helper",
        "deadline host",
        "deadline holder",
        "concerned witness",
        "outside voice",
        "organizer",
    }


def _fallback_sentence_start(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    return text[0].upper() + text[1:] if text[0].islower() else text


def _fallback_profile_clause(brief: StoryBrief, *, contested: str) -> str:
    if brief.tension_profile == "comedy":
        callback_verb = _fallback_verb(contested, "becomes", "become")
        return (
            f"The trouble stays social: timing, embarrassment, and whether the {contested} {callback_verb} a harmless callback "
            "instead of a culprit hunt."
        )
    if brief.tension_profile == "cozy_mystery":
        return (
            f"The trouble stays gentle and concrete: the {contested}, mixed signals, and a reveal that can repair trust "
            "instead of breaking it."
        )
    if brief.tension_profile == "fantasy_sci_fi":
        return (
            "A rule of the world is under strain, and the next choice will show whether the artifact, faction, or setting bends first."
        )
    if brief.tension_profile == "family_social":
        return "Old loyalties and misread intentions press against the room, but the first choice can still steer toward repair."
    return "The first choice will turn hidden pressure into a public shift."


def _fallback_first_move_clause(brief: StoryBrief) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return reliable_profile_vocabulary("fantasy_sci_fi").first_move_clause
    return reliable_profile_vocabulary(brief.tension_profile).first_move_clause


def _fallback_opening_options(brief: StoryBrief) -> list[StoryOption]:
    seed = brief.original_seed.casefold()
    contested = _fallback_contested_object(brief.original_seed)
    background = _fallback_background_label(brief)
    fantasy_party = (
        _fallback_named_party(brief, "clan")
        or _fallback_named_party(brief, "sprites")
        or _fallback_named_party(brief, "spellbook")
        or background
    )
    volunteer = _fallback_named_party(brief, "volunteer") or "quiet witness"
    if _fallback_uses_fantasy_scene(brief):
        if "eclipse" in seed and "library" in seed:
            return [
                StoryOption(label=f"Ask what changed when the eclipse touched the {contested}", hint="Name the old rule", handle="rule"),
                StoryOption(label=f"Invite {fantasy_party} to interpret the sign", hint="Broaden the room", handle="faction"),
                StoryOption(label=f"Hold the {contested} where every faction can read it", hint="Find the hinge", handle="artifact"),
            ]
        return [
            StoryOption(label="Ask which old rule changed first", hint="Name the world pressure", handle="rule"),
            StoryOption(label=f"Invite {fantasy_party} to answer", hint="Broaden the room", handle="faction"),
            StoryOption(label=f"Inspect the {contested} everyone keeps avoiding", hint="Find the hinge", handle="artifact"),
        ]
    if brief.tension_profile == "comedy":
        if "mars" in seed and "talent show" in seed:
            return [
                StoryOption(label="Ask who last handled the talent-show cue", hint="Keep the comedy concrete", handle="ask_cue"),
                StoryOption(label=f"Invite {background} to answer from the side", hint="Keep background concerns visible", handle="invite_bg"),
                StoryOption(label="Turn the oxygen rumor into a shared callback", hint="Lower the stakes", handle="callback"),
            ]
        return [
            StoryOption(label=f"Ask what actually happened to the {contested}", hint="Keep it concrete", handle="ask_prop"),
            StoryOption(label="Give the quiet party a harmless way in", hint="Soften the room", handle="invite"),
            StoryOption(label="Turn the mistake into a callback", hint="Aim for payoff", handle="callback"),
        ]
    if brief.tension_profile == "cozy_mystery":
        return [
            StoryOption(label=f"Ask where the {contested} was last seen", hint="Follow the object", handle="ask_clue"),
            StoryOption(label=f"Let the {volunteer} explain the clue trail", hint="Lower worry", handle="witness"),
            StoryOption(label="Compare the table versions gently", hint="Repair trust", handle="compare"),
        ]
    return [
        StoryOption(label="Ask who is being left out", hint="Bring in a quiet party", handle="ask"),
        StoryOption(label="Name the pressure everyone is avoiding", hint="Focus the room", handle="name"),
        StoryOption(label="Invite the quiet party to speak", hint="Shift attention", handle="invite"),
    ]


def _fallback_background_label(brief: StoryBrief) -> str:
    for entity in brief.cast_plan.secondary_background_entities:
        if "explicitly emphasized" in entity.rationale.casefold() and entity.display_name:
            return entity.display_name
    for entity in brief.cast_plan.secondary_background_entities:
        if entity.display_name:
            return entity.display_name
    return "background group"


def _fallback_named_party(brief: StoryBrief, token: str) -> str:
    token_lower = token.casefold()
    for entity in [*brief.cast_plan.primary_active_entities, *brief.cast_plan.secondary_background_entities]:
        if token_lower in entity.display_name.casefold():
            return entity.display_name
    return ""


def _fallback_pressure_labels(brief: StoryBrief) -> list[str]:
    labels = [
        item.label
        for item in [*brief.time_event_anchors, *brief.world_setting_pressure]
        if item.label.lower() != "core premise"
    ]
    return labels[:5]


def _fallback_title(brief: StoryBrief, pressure_labels: list[str]) -> str:
    if pressure_labels:
        return _fallback_label(pressure_labels[0].title(), limit=120)
    return _fallback_label(f"{brief.tension_profile.replace('_', ' ').title()} First Scene", limit=120)


def _fallback_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:64]


def _fallback_label(value: str, *, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _story_brief_consistency_feedback(check: StoryBriefConsistencyCheck) -> str:
    rows = []
    for violation in check.violations[:6]:
        evidence = ", ".join(violation.evidence[:3]) if violation.evidence else "no safe excerpt"
        rows.append(f"{violation.code}: {violation.rationale} Evidence: {evidence}")
    return (
        "Repair the generated opening so it matches the confirmed story plan. "
        "Keep the same JSON schema. Explicitly mention required/emphasized entities in cast or passage. "
        "For comedy/cozy briefs, keep stakes in social pressure, props, embarrassment, clues, or representation unless the brief preserved high stakes. "
        "Fix these issues: "
        + " | ".join(rows)
    )[:1200]


def _story_brief_consistency_failure_message(check: StoryBriefConsistencyCheck) -> str:
    codes = ", ".join(violation.code for violation in check.violations[:4])
    return (
        "The generated opening still could not satisfy the confirmed plan. "
        "Try to reduce required entities, relax which factions must be represented, "
        "lower stakes for comedy/cozy prompts, or revise the brief before generating again. "
        f"Mismatch signals: {codes or 'brief consistency failed'}."
    )[:500]


def _summarize_template(
    template: NarrativeTemplate, *, viewer_user_id: str
) -> NarrativeTemplateSummary:
    return NarrativeTemplateSummary(
        template_id=template.template_id,
        owner_user_id=template.owner_user_id,
        seed=template.seed,
        title=template.title,
        cast=template.cast,
        advisor_persona=template.advisor_persona,
        player_goals=template.player_goals,
        failure_conditions=template.failure_conditions,
        player_role_options=template.player_role_options,
        visibility=template.visibility,
        language=template.language,
        play_count=template.play_count,
        created_at=template.created_at,
        is_owner=(template.owner_user_id == viewer_user_id),
    )


def _summarize_session(
    session: NarrativeSession, template: NarrativeTemplate
) -> NarrativeSessionSummary:
    return NarrativeSessionSummary(
        session_id=session.session_id,
        template_id=session.template_id,
        template_title=template.title,
        template_seed=template.seed,
        player_user_id=session.player_user_id,
        turn_count=session.turn_count,
        turn_budget=session.turn_budget,
        difficulty=session.difficulty,
        player_role=_resolve_player_role(template, session.selected_player_role_id),
        ending_label=session.ending_label,
        ending_subtitle=session.ending_subtitle,
        ending_tier=session.ending_tier,
        early_terminated=session.early_terminated,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
    )


def get_narrative_service(settings: Settings | None = None) -> NarrativeService:
    resolved = settings or get_settings()
    repo = NarrativeRepository(resolved.runtime_state_db_path)
    gateway = get_narrative_gateway(resolved)
    return NarrativeService(repository=repo, gateway=gateway)
