from __future__ import annotations

import json
import secrets
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any

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
    LocalizedText,
    GameplayChip,
    GameplayChipTone,
    GameplayEnvelope,
    GameplayPressureTrack,
    LLMCallSourceLabel,
    LLMCallStatus,
    LLMCallEventListResponse,
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
    StoryGuideCompressedContext,
    StoryHistoryResponse,
    StoryGuideTurnRequest,
    StoryGuideTurnResponse,
    StoryMessage,
    StoryOption,
    TemplateListResponse,
    TurnGameplayMetadata,
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
    EndingResult,
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
from rpg_backend.narrative.home_story_library import DEFAULT_HOME_STORY_OWNER_ID
from rpg_backend.narrative.judges import judge_contract, judge_step
from rpg_backend.narrative.repository import NarrativeNotFoundError, NarrativeRepository
from rpg_backend.narrative.story_guide import advance_story_guide_loop, story_butler_voice_policy


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
    "opening_live_timeout",
}
_STORY_BRIEF_LIVE_OPENING_TIMEOUT_SECONDS = 45.0
_TURN_RUNTIME_FALLBACK_CODES = {
    "llm_unavailable",
    "llm_provider_failed",
    "llm_invalid_response",
    "llm_invalid_json",
}
_STORY_GUIDE_SYSTEM_PROMPT = """
You are Tiny Stories' Story Butler for a Korean-webtoon style interactive story creator.
Return strict JSON only.

Write one concise assistant reply for the player. You are a sharp, warm Korean webtoon story editor/butler.
Use the supplied compressed_context, deterministic slot state, and selected voice_skill as the contract:
- Use only details the user supplied or the current draft already contains.
- Treat compressed_context.last_user_intent as intent routing. If it is meta_assistant, interaction_help, greeting_smalltalk, or unclear_noise, answer that intent first and do not treat the user's wording as story material.
- Treat compressed_context.confirmed_facts as the current truth and compressed_context.rejected_or_changed_facts as superseded.
- Follow voice_skill.job and voice_skill.response_shape. Use voice_skill.examples as illustrative shapes, not exact text to copy.
- Anchor to current scene nouns from voice_skill.grounding_terms or the user's input when possible.
- If the input is tiny or unclear, use the opening_scene_prompt skill and ask for a grounded scene spark; do not invent genre, cast, setting, or protagonist.
- Ask exactly one focused next question when status is needs_field.
- Acknowledge corrections naturally when status is ready_to_brief.
- If voice_skill.previous_assistant_reply is present, vary the wording and avoid repeating its sentence shape.
- Do not mention provider, model, API, JSON, schema, backend, or deterministic fallback.
- Do not override safety/unsupported decisions from the deterministic contract.
- Keep the reply under 45 words in English or 90 Chinese characters where practical.
- Do not ask multiple questions. One reply, one job, one question.

JSON shape:
{"reply":"player-facing assistant row"}
"""
_STORY_GUIDE_CONTEXT_SYSTEM_PROMPT = """
You are Tiny Stories' Story Butler context compressor and planner.
Return strict JSON only.

Update a compact story-context object for a guided Korean webtoon story-creation chat.
Do not write the user-visible assistant reply here. Preserve the latest corrected facts and mark older conflicting facts as superseded.
Keep only concise, player-safe story facts. Do not mention provider, model, API, JSON, schema, tokens, debug, fallback, or internal prompts.
Use the deterministic slot state as hard guardrails for safety, readiness, and next missing field.

JSON shape:
{
  "scene_summary": "current opening scene/world in one concise phrase",
  "player_role": "current player role if known",
  "cast_or_factions": ["2-8 people/groups/factions"],
  "pressure": "current contested object, decision, or pressure",
  "constraints": ["boundaries or must-avoid items"],
  "tone": "tone/run feel",
  "open_questions": ["current useful missing questions"],
  "confirmed_facts": ["compact facts that are still true"],
  "rejected_or_changed_facts": ["superseded facts only"],
  "non_story_user_intents": ["smalltalk, meta, help, or noise that should not become story facts"],
  "last_user_intent": "one of greeting_smalltalk, meta_assistant, interaction_help, story_seed, correction_update, direct_answer, delegation, unsafe_out_of_policy, ambiguous_who, unclear_noise",
  "last_question_answered": "question answered by the latest story-material input, or empty",
  "latest_input_updates_story_facts": false,
  "last_question": "the next question the Butler should ask",
  "readiness_score": 0.0,
  "planner_skill": "one of opening_scene_prompt, role_focus, cast_focus, pressure_focus, tone_focus, boundary_redirect, brief_readiness, meta_assistant, interaction_help, clarify_input",
  "planner_job": "the next internal job in one phrase"
}
"""
_STORY_BRIEF_SYSTEM_PROMPT = """
You are Tiny Stories' live Story Brief editor.
Return strict JSON only.

You receive a deterministic Story Brief candidate that already protects entity hygiene, not-fit gates, and safety boundaries.
Refine only the readable top-level copy without changing the cast plan, fit status, safety boundaries, or ability to generate.
Keep entities clean. Do not promote negated constraints into cast.
Do not mention provider, model, API, JSON, schema, backend, or fallback.

JSON shape:
{
  "display_title": "story directory title, 2-6 English words or concise Chinese title, <=52 chars",
  "display_intro": "one complete sentence for Home story tiles, <=118 English chars or concise Chinese equivalent; do not end on a clipped clause",
  "premise_summary": "1 sentence, <=220 chars",
  "genre_tone": "short tone line, <=140 chars",
  "story_kernel": "playable promise, <=190 chars",
  "adaptation_note": "short note, <=180 chars",
  "next_step": "player-facing next step, <=180 chars"
}
"""


def _is_content_moderation_failure(exc: NarrativeGatewayError) -> bool:
    if exc.status_code != 400:
        return False
    msg_lower = (exc.message or "").lower()
    return any(marker.lower() in msg_lower for marker in _CONTENT_MODERATION_MARKERS)


def _generate_template_id() -> str:
    return f"tmpl_{secrets.token_hex(6)}"


def _generate_session_id() -> str:
    return f"sess_{secrets.token_hex(6)}"


_NEGATIVE_NPC_SHIFTS = {"colder", "wary", "broken"}
_POSITIVE_NPC_SHIFTS = {"warmer"}


def _gameplay_label(value: str | None, *, max_length: int = 64) -> str:
    compact = normalize_whitespace(value or "")
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max(0, max_length - 1)].strip()}…"


def _add_gameplay_chip(
    chips: list[GameplayChip],
    label: str,
    tone: GameplayChipTone,
    *,
    max_length: int = 64,
) -> bool:
    compact = _gameplay_label(label, max_length=max_length)
    if not compact or any(chip.label == compact for chip in chips):
        return False
    chips.append(GameplayChip(label=compact, tone=tone))
    return True


def _prepend_gameplay_chip(
    chips: list[GameplayChip],
    label: str,
    tone: GameplayChipTone,
    *,
    detail: str | None = None,
    max_length: int = 64,
) -> bool:
    compact = _gameplay_label(label, max_length=max_length)
    if not compact or any(chip.label == compact for chip in chips):
        return False
    compact_detail = _gameplay_label(detail or "", max_length=140) if detail else None
    chips.insert(0, GameplayChip(label=compact, tone=tone, detail=compact_detail))
    return True


def _gameplay_forecast_for_option(option: StoryOption) -> list[GameplayChip]:
    haystack = normalize_whitespace(
        f"{option.label} {option.hint} {option.handle}"
    ).casefold()
    chips: list[GameplayChip] = []
    if re.search(
        r"\b(wait|watch|stall|delay|countdown|time|minute|clock|search|check|look|scan|follow|trail|quiet)\b",
        haystack,
    ):
        _add_gameplay_chip(chips, "Time -1", "cost")
    if re.search(
        r"\b(confront|challenge|accuse|expose|reveal|public|announce|pressure|push|force|demand|call out|interrupt)\b",
        haystack,
    ):
        _add_gameplay_chip(chips, "Pressure +1", "cost")
    if re.search(
        r"\b(ask|probe|question|interview|witness|account|source|handled|last seen|saw)\b",
        haystack,
    ):
        _add_gameplay_chip(chips, "May reveal proof", "unlock")
    if re.search(
        r"\b(trust|calm|cover|protect|help|ally|promise|reassure|soften|support|invite|speak|explain|give room)\b",
        haystack,
    ):
        _add_gameplay_chip(chips, "Trust +1", "gain")
    if re.search(
        r"\b(clue|evidence|proof|recording|footage|badge|phone|message|lead|find|discover|document|receipt)\b",
        haystack,
    ):
        _add_gameplay_chip(chips, "May reveal proof", "unlock")
    if re.search(
        r"\b(leverage|trump|blackmail|secret|threat|trade|bargain|deal)\b",
        haystack,
    ):
        _add_gameplay_chip(chips, "Use leverage", "unlock")
    if re.search(
        r"\b(risk|danger|escalate|reckless|storm|break|shatter|corner|trap)\b",
        haystack,
    ):
        _add_gameplay_chip(chips, "Risk +1", "cost")
    if not chips:
        _add_gameplay_chip(chips, "Read the room", "shift")
    return chips[:3]


def _gameplay_objective(
    template: NarrativeTemplate,
    active_role: PlayerRole | None,
) -> str | None:
    if template.player_goals:
        return _gameplay_label(template.player_goals[0].goal, max_length=120)
    if active_role is not None:
        return _gameplay_label(active_role.hidden_objective, max_length=120)
    return _gameplay_label(template.seed or template.title, max_length=120)


def _gameplay_pressure_track(pulses: list[NPCPulse]) -> GameplayPressureTrack:
    negative_count = sum(1 for pulse in pulses if pulse.shift in _NEGATIVE_NPC_SHIFTS)
    positive_count = sum(1 for pulse in pulses if pulse.shift in _POSITIVE_NPC_SHIFTS)
    if negative_count:
        return GameplayPressureTrack(id="pressure", label="Pressure", value="rising", tone="cost")
    if positive_count:
        return GameplayPressureTrack(id="pressure", label="Pressure", value="opening", tone="gain")
    return GameplayPressureTrack(id="pressure", label="Pressure", value="held", tone="shift")


def _gameplay_people_track(
    pulses: list[NPCPulse],
    cast_name_by_id: dict[str, str],
) -> GameplayPressureTrack:
    names = [
        cast_name_by_id[pulse.npc_id]
        for pulse in pulses
        if pulse.npc_id in cast_name_by_id
    ]
    if names:
        return GameplayPressureTrack(
            id="people",
            label="People",
            value=_gameplay_label(" / ".join(names[:2]), max_length=34),
            tone="shift",
        )
    return GameplayPressureTrack(id="people", label="People", value="watching", tone="shift")


def _build_gameplay_envelope(
    *,
    template: NarrativeTemplate,
    session: NarrativeSession,
    history: list[StoryMessage],
    active_role: PlayerRole | None,
    current_inventory: list[str],
    live_metadata: TurnGameplayMetadata | None = None,
) -> GameplayEnvelope:
    last_narrator = next((m for m in reversed(history) if m.role == "narrator"), None)
    previous_player = None
    if last_narrator is not None:
        narrator_index = next(
            (
                index
                for index, message in enumerate(history)
                if message.role == "narrator" and message.ord == last_narrator.ord
            ),
            -1,
        )
        if narrator_index > 0 and history[narrator_index - 1].role == "player":
            previous_player = history[narrator_index - 1]

    cast_name_by_id = {member.character_id: member.display_name for member in template.cast}
    pulses = last_narrator.npc_pulse if last_narrator is not None else []
    playable_leverage_count = len(active_role.leverages_over_npcs) if active_role is not None else 0
    evidence_value = (
        f"{len(current_inventory)} held"
        if current_inventory
        else f"{playable_leverage_count} card{'s' if playable_leverage_count != 1 else ''}"
        if playable_leverage_count
        else "none"
    )
    turns_remaining = max(0, session.turn_budget - session.turn_count)

    tracks = [
        GameplayPressureTrack(
            id="time",
            label="Time",
            value=f"{turns_remaining}/{max(1, session.turn_budget)}",
            tone="cost" if turns_remaining <= 2 and session.turn_count > 0 else "shift",
        ),
        _gameplay_pressure_track(pulses),
        _gameplay_people_track(pulses, cast_name_by_id),
        GameplayPressureTrack(
            id="evidence",
            label="Evidence",
            value=evidence_value,
            tone="unlock" if current_inventory or playable_leverage_count else "shift",
        ),
    ]

    impact: list[GameplayChip] = []
    opportunities: list[GameplayChip] = []
    if last_narrator is not None:
        for pulse in last_narrator.npc_pulse:
            tone: GameplayChipTone = (
                "gain"
                if pulse.shift in _POSITIVE_NPC_SHIFTS
                else "cost"
                if pulse.shift in _NEGATIVE_NPC_SHIFTS
                else "shift"
            )
            _add_gameplay_chip(
                impact,
                f"{cast_name_by_id.get(pulse.npc_id, 'Someone')}: {pulse.shift}",
                tone,
            )
        for item in (
            last_narrator.inventory_delta.added if last_narrator.inventory_delta else []
        ):
            _add_gameplay_chip(impact, f"Evidence: {item}", "unlock", max_length=44)
            _add_gameplay_chip(opportunities, f"Clue: {item}", "unlock", max_length=44)
        for item in (
            last_narrator.inventory_delta.removed if last_narrator.inventory_delta else []
        ):
            _add_gameplay_chip(impact, f"Spent: {item}", "cost", max_length=44)
    if previous_player is not None and previous_player.played_leverage is not None:
        _add_gameplay_chip(impact, "Leverage played", "unlock")

    metadata_to_merge = live_metadata
    if metadata_to_merge is None and last_narrator is not None:
        metadata_to_merge = last_narrator.gameplay_metadata

    action_forecasts = [
        _gameplay_forecast_for_option(option)
        for option in (last_narrator.options if last_narrator is not None else [])
    ]

    live_enriched = False
    if metadata_to_merge is not None:
        for chip in metadata_to_merge.state_deltas:
            live_enriched = _add_gameplay_chip(
                impact,
                chip.label,
                chip.tone,
            ) or live_enriched
        if metadata_to_merge.motive_effect is not None:
            live_enriched = _add_gameplay_chip(
                impact,
                metadata_to_merge.motive_effect.label,
                metadata_to_merge.motive_effect.tone,
            ) or live_enriched
        for chip in metadata_to_merge.clue_unlocks:
            live_enriched = _add_gameplay_chip(
                impact,
                chip.label,
                chip.tone,
                max_length=44,
            ) or live_enriched
            live_enriched = _add_gameplay_chip(
                opportunities,
                chip.label,
                chip.tone,
                max_length=44,
            ) or live_enriched
        for chip in metadata_to_merge.opportunity_unlocks:
            live_enriched = _add_gameplay_chip(
                impact,
                chip.label,
                chip.tone,
                max_length=44,
            ) or live_enriched
            live_enriched = _add_gameplay_chip(
                opportunities,
                chip.label,
                chip.tone,
                max_length=44,
            ) or live_enriched
        for context in metadata_to_merge.next_action_context:
            if 0 <= context.option_index < len(action_forecasts):
                live_enriched = _prepend_gameplay_chip(
                    action_forecasts[context.option_index],
                    "Why now",
                    "shift",
                    detail=context.reason,
                    max_length=24,
                ) or live_enriched

    if not impact and last_narrator is not None and last_narrator.options:
        _add_gameplay_chip(impact, "Next moves shifted", "shift")
    if not impact and current_inventory:
        _add_gameplay_chip(impact, f"Holding: {current_inventory[0]}", "shift", max_length=44)

    return GameplayEnvelope(
        source="live_enriched" if live_enriched else "backend",
        objective=_gameplay_objective(template, active_role),
        tracks=tracks,
        action_forecasts=[row[:3] for row in action_forecasts],
        impact=impact[:6],
        opportunities=opportunities[:6],
    )


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

    def _trace_start(self) -> int:
        if self._gateway is None:
            return 0
        trace_length = getattr(self._gateway, "trace_length", None)
        if callable(trace_length):
            try:
                return int(trace_length())
            except Exception:  # noqa: BLE001
                return 0
        call_trace = getattr(self._gateway, "call_trace", None)
        if isinstance(call_trace, list):
            return len(call_trace)
        return 0

    def _gateway_trace_since(self, start_index: int) -> list[dict[str, Any]]:
        if self._gateway is None:
            return []
        trace_since = getattr(self._gateway, "trace_since", None)
        if callable(trace_since):
            try:
                return list(trace_since(start_index))
            except Exception:  # noqa: BLE001
                return []
        call_trace = getattr(self._gateway, "call_trace", None)
        if isinstance(call_trace, list):
            return [entry for entry in call_trace[max(0, int(start_index)) :] if isinstance(entry, dict)]
        return []

    def _persist_gateway_trace(
        self,
        start_index: int,
        *,
        operation_latency_ms: int | None = None,
        user_id: str | None = None,
        template_id: str | None = None,
        session_id: str | None = None,
        fallback_reason: str | None = None,
    ) -> None:
        for entry in self._gateway_trace_since(start_index):
            usage = entry.get("usage") if isinstance(entry.get("usage"), dict) else {}
            status = _coerce_llm_call_status(entry.get("status"), entry.get("failure_message_bucket"))
            source_label: LLMCallSourceLabel = "live_repaired" if status == "repaired" else "live"
            self._repo.append_llm_call_event(
                operation=str(entry.get("operation") or "unknown"),
                status=status,
                source_label=source_label,
                latency_ms=_safe_int_or_none(entry.get("latency_ms")),
                operation_latency_ms=operation_latency_ms,
                input_tokens=_safe_int_or_none(usage.get("input_tokens")),
                cached_input_tokens=_safe_int_or_none(usage.get("cached_input_tokens")),
                output_tokens=_safe_int_or_none(usage.get("output_tokens")),
                total_tokens=_safe_int_or_none(usage.get("total_tokens")),
                retry_count=max(
                    _safe_int_or_none(entry.get("retry_count")) or 0,
                    max(0, (_safe_int_or_none(entry.get("attempt_index")) or 1) - 1),
                ),
                repair_count=_safe_int_or_none(entry.get("repair_count")) or 0,
                fallback_reason=fallback_reason,
                response_id=str(entry.get("response_id")) if entry.get("response_id") else None,
                user_id=user_id,
                template_id=template_id,
                session_id=session_id,
            )

    def _record_llm_fallback_event(
        self,
        *,
        operation: str,
        user_id: str | None,
        source_label: LLMCallSourceLabel,
        fallback_reason: str,
        template_id: str | None = None,
        session_id: str | None = None,
        operation_latency_ms: int | None = None,
    ) -> None:
        self._repo.append_llm_call_event(
            operation=operation,
            status="fallback_used",
            source_label=source_label,
            operation_latency_ms=operation_latency_ms,
            fallback_reason=fallback_reason[:160],
            user_id=user_id,
            template_id=template_id,
            session_id=session_id,
        )

    def _record_llm_policy_event(
        self,
        *,
        operation: str,
        user_id: str | None,
        template_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self._repo.append_llm_call_event(
            operation=operation,
            status="success",
            source_label="policy_control",
            operation_latency_ms=0,
            user_id=user_id,
            template_id=template_id,
            session_id=session_id,
        )

    def _compress_story_guide_context_live(
        self,
        deterministic: StoryGuideTurnResponse,
        *,
        request: StoryGuideTurnRequest,
        owner_user_id: str,
    ) -> StoryGuideTurnResponse:
        started_at = time.monotonic()
        trace_start = self._trace_start()
        try:
            result = self.gateway.invoke_json(
                system_prompt=_STORY_GUIDE_CONTEXT_SYSTEM_PROMPT,
                user_payload={
                    "message": request.message,
                    "language": request.language,
                    "current_seed": request.current_seed,
                    "previous_assistant_reply": request.previous_assistant_reply,
                    "previous_context": (request.state.context.model_dump(mode="json") if request.state else None),
                    "deterministic_state": deterministic.state.model_dump(mode="json"),
                    "deterministic_reply": deterministic.reply,
                },
                operation_name="create.story_butler_context",
                max_output_tokens=620,
            )
            operation_latency_ms = _elapsed_ms(started_at)
            self._persist_gateway_trace(
                trace_start,
                operation_latency_ms=operation_latency_ms,
                user_id=owner_user_id,
            )
            source: LLMCallSourceLabel = "live_repaired" if _trace_had_repair(self._gateway_trace_since(trace_start)) else "live"
            context = _safe_story_guide_context(result.payload, deterministic.state.context, source=source)
            return deterministic.model_copy(
                update={
                    "state": deterministic.state.model_copy(update={"context": context}),
                }
            )
        except Exception as exc:  # noqa: BLE001
            operation_latency_ms = _elapsed_ms(started_at)
            fallback_reason = _fallback_reason_for_exception(exc)
            self._persist_gateway_trace(
                trace_start,
                operation_latency_ms=operation_latency_ms,
                user_id=owner_user_id,
                fallback_reason=fallback_reason,
            )
            self._record_llm_fallback_event(
                operation="create.story_butler_context",
                user_id=owner_user_id,
                source_label="deterministic_fallback",
                fallback_reason=fallback_reason,
                operation_latency_ms=operation_latency_ms,
            )
            return deterministic

    # ------------------------------------------------------------------
    # Template authoring
    # ------------------------------------------------------------------

    def create_story_guide_turn(
        self,
        request: StoryGuideTurnRequest,
        *,
        owner_user_id: str,
    ) -> StoryGuideTurnResponse:
        deterministic = advance_story_guide_loop(request.state, request.message, request.language)
        # Safety and privacy redirects are already product decisions; do not
        # spend live provider calls on text we deliberately refuse or do not
        # want to silently mutate. Vague chat such as "hi" or "who" can still
        # use the live voice layer while keeping acceptedText=false.
        if deterministic.blocked or (
            deterministic.acceptedText is False
            and deterministic.settings is not None
            and deterministic.settings.privacyIntent is not None
        ):
            self._record_llm_policy_event(
                operation="create.story_butler_turn",
                user_id=owner_user_id,
            )
            return deterministic.model_copy(update={"source": "policy_control"})
        if self._gateway is None:
            self._record_llm_fallback_event(
                operation="create.story_butler_turn",
                user_id=owner_user_id,
                source_label="no_gateway_fallback",
                fallback_reason="text_gateway_not_configured",
            )
            return deterministic.model_copy(update={"source": "no_gateway_fallback"})

        deterministic = self._compress_story_guide_context_live(
            deterministic,
            request=request,
            owner_user_id=owner_user_id,
        )
        started_at = time.monotonic()
        trace_start = self._trace_start()
        try:
            voice_policy = story_butler_voice_policy(
                deterministic,
                message=request.message,
                current_seed=request.current_seed,
                previous_assistant_reply=request.previous_assistant_reply,
            )
            result = self.gateway.invoke_json(
                system_prompt=_STORY_GUIDE_SYSTEM_PROMPT,
                user_payload={
                    "message": request.message,
                    "language": request.language,
                    "current_seed": request.current_seed,
                    "previous_assistant_reply": request.previous_assistant_reply,
                    "voice_skill": voice_policy,
                    "compressed_context": deterministic.state.context.model_dump(mode="json"),
                    "deterministic_contract": deterministic.model_dump(mode="json"),
                },
                operation_name="create.story_butler_turn",
                max_output_tokens=420,
                plaintext_fallback_key="reply",
            )
            operation_latency_ms = _elapsed_ms(started_at)
            self._persist_gateway_trace(
                trace_start,
                operation_latency_ms=operation_latency_ms,
                user_id=owner_user_id,
            )
            live_reply = _safe_live_reply(
                result.payload.get("reply"),
                deterministic.reply,
                previous_assistant_reply=request.previous_assistant_reply,
                voice_skill=voice_policy,
            )
            source: LLMCallSourceLabel = "live_repaired" if _trace_had_repair(self._gateway_trace_since(trace_start)) else "live"
            return deterministic.model_copy(update={"reply": live_reply, "source": source})
        except Exception as exc:  # noqa: BLE001
            operation_latency_ms = _elapsed_ms(started_at)
            self._persist_gateway_trace(
                trace_start,
                operation_latency_ms=operation_latency_ms,
                user_id=owner_user_id,
                fallback_reason=_fallback_reason_for_exception(exc),
            )
            self._record_llm_fallback_event(
                operation="create.story_butler_turn",
                user_id=owner_user_id,
                source_label="deterministic_fallback",
                fallback_reason=_fallback_reason_for_exception(exc),
                operation_latency_ms=operation_latency_ms,
            )
            return deterministic

    def create_story_brief(
        self,
        request: StoryBriefAdvisorRequest,
        *,
        owner_user_id: str,
    ) -> StoryBriefAdvisorResponse:
        seed = request.seed.strip()
        if not seed:
            raise NarrativeServiceError(
                code="seed_required", message="Seed must not be empty.", status_code=422
            )
        deterministic = build_story_brief(
            seed=seed,
            language=request.language,
            desired_tension_profile=request.desired_tension_profile,
        )
        deterministic = deterministic.model_copy(
            update={
                "brief": _with_story_brief_display_metadata(
                    deterministic.brief,
                    language=request.language,
                )
            }
        )
        if self._gateway is None:
            self._record_llm_fallback_event(
                operation="narrative.story_brief",
                user_id=owner_user_id,
                source_label="no_gateway_fallback",
                fallback_reason="text_gateway_not_configured",
            )
            return deterministic.model_copy(update={"runtime_source": "no_gateway_fallback"})

        started_at = time.monotonic()
        trace_start = self._trace_start()
        try:
            result = self.gateway.invoke_json(
                system_prompt=_STORY_BRIEF_SYSTEM_PROMPT,
                user_payload={
                    "seed": seed,
                    "language": request.language,
                    "desired_tension_profile": request.desired_tension_profile,
                    "deterministic_brief": deterministic.brief.model_dump(mode="json"),
                    "can_generate": deterministic.can_generate,
                    "next_step": deterministic.next_step,
                },
                operation_name="narrative.story_brief",
                max_output_tokens=700,
                plaintext_fallback_key="next_step",
            )
            operation_latency_ms = _elapsed_ms(started_at)
            self._persist_gateway_trace(
                trace_start,
                operation_latency_ms=operation_latency_ms,
                user_id=owner_user_id,
            )
            brief = _apply_live_story_brief_copy(
                deterministic.brief,
                result.payload,
                language=request.language,
            )
            runtime_source: LLMCallSourceLabel = "live_repaired" if _trace_had_repair(self._gateway_trace_since(trace_start)) else "live"
            next_step = _safe_short_text(result.payload.get("next_step"), deterministic.next_step, max_len=180)
            return deterministic.model_copy(
                update={
                    "brief": brief,
                    "next_step": next_step,
                    "source": "live_hybrid_v1",
                    "runtime_source": runtime_source,
                }
            )
        except Exception as exc:  # noqa: BLE001
            operation_latency_ms = _elapsed_ms(started_at)
            fallback_reason = _fallback_reason_for_exception(exc)
            self._persist_gateway_trace(
                trace_start,
                operation_latency_ms=operation_latency_ms,
                user_id=owner_user_id,
                fallback_reason=fallback_reason,
            )
            self._record_llm_fallback_event(
                operation="narrative.story_brief",
                user_id=owner_user_id,
                source_label="deterministic_fallback",
                fallback_reason=fallback_reason,
                operation_latency_ms=operation_latency_ms,
            )
            return deterministic

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
        opening_recovery: str | None = None
        opening_fallback_reason: str | None = None
        operation_started_at = time.monotonic()
        trace_start = self._trace_start()
        if request.story_brief is not None and _story_brief_prefers_reliable_opening(request.story_brief):
            opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
            opening_fallback_reason = "story_brief_prefers_reliable_opening"
        else:
            try:
                if request.story_brief is not None:
                    opening = _generate_story_brief_live_opening_with_cap(
                        gateway=self.gateway,
                        seed=seed,
                        language=request.language,
                        story_brief=request.story_brief,
                    )
                else:
                    opening = generate_opening(
                        gateway=self.gateway,
                        seed=seed,
                        language=request.language,
                        story_brief=request.story_brief,
                        max_attempts=3,
                    )
            except NarrativeServiceError as exc:
                if request.story_brief is not None and _should_use_reliable_opening_fallback(exc):
                    opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                    opening_recovery = "tightened_from_brief"
                    opening_fallback_reason = _fallback_reason_for_exception(exc)
                else:
                    raise
            except NarrativeGatewayError as exc:
                if request.story_brief is not None and _should_use_reliable_opening_fallback(exc):
                    opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                    opening_recovery = "tightened_from_brief"
                    opening_fallback_reason = _fallback_reason_for_exception(exc)
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
                    opening_recovery = "tightened_from_brief"
                    opening_fallback_reason = _fallback_reason_for_exception(exc)
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
                opening = _story_brief_fallback_opening(request.story_brief, language=request.language)
                opening_recovery = "tightened_from_brief"
                opening_fallback_reason = "story_brief_consistency_retry"
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
                if fallback_check.status != "fail" or request.story_brief.runtime_fit_status != "not_fit":
                    opening = fallback_opening
                    opening_recovery = "tightened_from_brief"
                    opening_fallback_reason = "story_brief_consistency_failed"
                    story_brief_consistency = _story_brief_recovered_opening_check(
                        fallback_check,
                        brief=request.story_brief,
                    )
                else:
                    raise NarrativeServiceError(
                        code="opening_brief_consistency_failed",
                        message=_story_brief_consistency_failure_message(story_brief_consistency),
                        status_code=422,
                    )

        template_id = _generate_template_id()
        display_title, display_intro = _template_display_metadata(
            seed=seed,
            language=request.language,
            opening=opening,
            story_brief=request.story_brief,
        )
        template = self._repo.create_template(
            template_id=template_id,
            owner_user_id=owner_user_id,
            seed=seed,
            title=display_title,
            cast=opening.cast,
            advisor_persona=opening.advisor_persona,
            opening_passage=opening.opening_message.content,
            opening_options=opening.opening_message.options,
            player_goals=opening.player_goals,
            failure_conditions=opening.failure_conditions,
            player_role_options=opening.player_role_options,
            visibility=request.visibility,
            language=request.language,
            title_i18n=_localized_text_for_language(display_title, request.language),
            summary_i18n=_localized_text_for_language(display_intro, request.language),
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
        operation_latency_ms = _elapsed_ms(operation_started_at)
        self._persist_gateway_trace(
            trace_start,
            operation_latency_ms=operation_latency_ms,
            user_id=owner_user_id,
            template_id=template.template_id,
            session_id=session.session_id,
            fallback_reason=opening_fallback_reason,
        )
        if opening_fallback_reason is not None:
            self._record_llm_fallback_event(
                operation="narrative.opening",
                user_id=owner_user_id,
                template_id=template.template_id,
                session_id=session.session_id,
                source_label="no_gateway_fallback" if opening_fallback_reason == "llm_unavailable" else "deterministic_fallback",
                fallback_reason=opening_fallback_reason,
                operation_latency_ms=operation_latency_ms,
            )
        return CreateTemplateResponse(
            template=_summarize_template(template, viewer_user_id=owner_user_id),
            session=_summarize_session(session, template),
            opening=opening_message,
            story_brief_consistency=story_brief_consistency,
            opening_recovery=opening_recovery,
        )

    def list_public_templates(self, *, viewer_user_id: str) -> TemplateListResponse:
        templates = _prioritize_home_library_templates(self._repo.list_public_templates())
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
        active_role = _resolve_player_role(template, session.selected_player_role_id)
        if self._finalize_if_budget_exhausted(session, template, player_role=active_role):
            session = self._repo.get_session(session_id)
        messages = self._repo.list_story_messages(session_id)
        agent_events = (
            self._repo.list_agent_events(session_id) if include_agent_trace else []
        )
        starting_assets = active_role.starting_assets if active_role else []
        current_inventory = compute_current_inventory(starting_assets, messages)
        # turn_count derived from message stream (narrator/player pairs)
        return StoryHistoryResponse(
            template=_summarize_template(template, viewer_user_id=player_user_id),
            session=_summarize_session(session, template),
            messages=messages,
            agent_events=agent_events,
            gameplay_envelope=_build_gameplay_envelope(
                template=template,
                session=session,
                history=messages,
                active_role=active_role,
                current_inventory=current_inventory,
            ),
        )

    def list_llm_call_events(
        self,
        session_id: str,
        *,
        player_user_id: str,
    ) -> LLMCallEventListResponse:
        self._load_session_for_player(session_id, player_user_id)
        return LLMCallEventListResponse(items=self._repo.list_llm_call_events_for_session(session_id))

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
        active_role = _resolve_player_role(template, session.selected_player_role_id)
        if self._finalize_if_budget_exhausted(session, template, player_role=active_role):
            raise NarrativeServiceError(
                code="session_complete",
                message="这一局故事已经走完了——刷新后可以看你的结局。",
                status_code=409,
            )
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

        turn_operation_started_at = time.monotonic()
        turn_trace_start = self._trace_start()
        turn_fallback_reason: str | None = None
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
                turn_fallback_reason = _fallback_reason_for_exception(exc)
            else:
                self._persist_gateway_trace(
                    turn_trace_start,
                    operation_latency_ms=_elapsed_ms(turn_operation_started_at),
                    user_id=player_user_id,
                    template_id=template.template_id,
                    session_id=session_id,
                    fallback_reason=_fallback_reason_for_exception(exc),
                )
                raise
        except NarrativeGatewayError as exc:
            if _should_use_turn_runtime_fallback(exc):
                turn = build_deterministic_turn()
                turn_fallback_reason = _fallback_reason_for_exception(exc)
            else:
                self._persist_gateway_trace(
                    turn_trace_start,
                    operation_latency_ms=_elapsed_ms(turn_operation_started_at),
                    user_id=player_user_id,
                    template_id=template.template_id,
                    session_id=session_id,
                    fallback_reason=_fallback_reason_for_exception(exc),
                )
                raise NarrativeServiceError(
                    code=exc.code, message=exc.message, status_code=exc.status_code
                ) from exc
        except ValueError:
            turn = build_deterministic_turn()
            turn_fallback_reason = "turn_value_error"

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
            except (NarrativeServiceError, NarrativeGatewayError, ValueError) as exc:
                # Failure judge errors are non-fatal — log and proceed.
                print(
                    f"[narrative.service] judge_failure errored for session={session_id}: {_safe_exception_label(exc)}",
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

        turn_operation_latency_ms = _elapsed_ms(turn_operation_started_at)
        self._persist_gateway_trace(
            turn_trace_start,
            operation_latency_ms=turn_operation_latency_ms,
            user_id=player_user_id,
            template_id=template.template_id,
            session_id=session_id,
            fallback_reason=turn_fallback_reason,
        )
        if turn_fallback_reason is not None:
            self._record_llm_fallback_event(
                operation="narrative.advance_turn",
                user_id=player_user_id,
                template_id=template.template_id,
                session_id=session_id,
                source_label="deterministic_fallback",
                fallback_reason=turn_fallback_reason,
                operation_latency_ms=turn_operation_latency_ms,
            )

        history_after_turn = history + [player_message, turn.narrator_message]
        session_after_turn = session.model_copy(update={"turn_count": upcoming_turn_index})
        current_inventory_after_turn = compute_current_inventory(
            starting_assets,
            history_after_turn,
        )

        return AdvanceTurnResponse(
            player_message=player_message,
            narrator_message=turn.narrator_message,
            agent_plan=turn.agent_plan if include_agent_trace else None,
            agent_events=turn_agent_events if include_agent_trace else [],
            gameplay_envelope=_build_gameplay_envelope(
                template=template,
                session=session_after_turn,
                history=history_after_turn,
                active_role=active_role,
                current_inventory=current_inventory_after_turn,
                live_metadata=turn.gameplay_metadata,
            ),
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
        active_role = _resolve_player_role(template, session.selected_player_role_id)
        if self._finalize_if_budget_exhausted(session, template, player_role=active_role):
            raise NarrativeServiceError(
                code="session_complete",
                message="这一局故事已经走完了——刷新后可以看你的结局。",
                status_code=409,
            )
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
        active_role = _resolve_player_role(template, session.selected_player_role_id)
        if self._finalize_if_budget_exhausted(session, template, player_role=active_role):
            raise NarrativeServiceError(
                code="session_complete",
                message="这一局故事已经走完了——刷新后可以看你的结局。",
                status_code=409,
            )
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

    def _finalize_if_budget_exhausted(
        self,
        session: NarrativeSession,
        template: NarrativeTemplate,
        *,
        player_role: PlayerRole | None = None,
    ) -> bool:
        """Repair sessions that reached the turn budget without a saved ending.

        This can happen when a final live ending call fails. The player should
        never be able to keep advancing past the budget, so reads and preflight
        validation force a local closeout before exposing the session again.
        """
        if session.ending_label is not None or session.turn_count < session.turn_budget:
            return False
        return self._finalize_session(
            session.session_id,
            template,
            player_role=player_role,
        ) is not None

    def _synthesize_postgame_artifacts(
        self,
        *,
        session_id: str,
        template: NarrativeTemplate,
        full_history: list[StoryMessage],
        result: EndingResult,
        tier: str,
        player_role: PlayerRole | None = None,
        log_prefix: str = "ending",
    ) -> tuple[list, list]:
        if self._gateway is None:
            return [], []
        with ThreadPoolExecutor(max_workers=2) as pool:
            hl_future = pool.submit(
                synthesize_highlights,
                gateway=self._gateway,
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
                gateway=self._gateway,
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
            try:
                highlights = hl_future.result()
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[narrative.service] {log_prefix} highlights failed for session={session_id}: {_safe_exception_label(exc)}",
                    flush=True,
                )
                highlights = []
            try:
                branches = br_future.result()
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[narrative.service] {log_prefix} branches failed for session={session_id}: {_safe_exception_label(exc)}",
                    flush=True,
                )
                branches = []
        return highlights, branches

    def _finalize_session(
        self,
        session_id: str,
        template: NarrativeTemplate,
        *,
        player_role: PlayerRole | None = None,
    ) -> NarrativeEnding | None:
        """Synthesize and persist an ending.

        LLM ending generation is preferred, but final turn completion must not
        depend on provider health. If the live ending fails, a conservative
        local closeout is persisted so the session cannot advance beyond its
        budget.
        """
        full_history = self._repo.list_story_messages(session_id)
        try:
            if self._gateway is None:
                raise NarrativeServiceError(
                    code="llm_unavailable",
                    message="Narrative LLM gateway is not configured.",
                    status_code=500,
                )
            result = synthesize_ending(
                gateway=self._gateway,
                seed=template.seed,
                title=template.title,
                cast=template.cast,
                history=full_history,
                turn_count=len([m for m in full_history if m.role == "narrator"]) - 1,
                player_role=player_role,
                language=template.language,
            )
        except (NarrativeGatewayError, NarrativeServiceError, ValueError, AttributeError) as exc:
            print(
                f"[narrative.service] ending synthesis failed for session={session_id}; using local closeout: {_safe_exception_label(exc)}",
                flush=True,
            )
            result = _deterministic_ending_fallback(
                template=template,
                history=full_history,
                player_role=player_role,
            )
        tier = tier_for_label(result.label)
        # Synthesize highlights + branches AFTER ending exists. Both
        # non-fatal — return [] on any failure. Run in parallel since
        # they're independent LLM calls — cuts post-game wait from
        # ~9s sequential to ~5s.
        highlights, branches = self._synthesize_postgame_artifacts(
            session_id=session_id,
            template=template,
            full_history=full_history,
            result=result,
            tier=tier,
            player_role=player_role,
        )
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
            if self._gateway is None:
                raise NarrativeServiceError(
                    code="llm_unavailable",
                    message="Narrative LLM gateway is not configured.",
                    status_code=500,
                )
            result = synthesize_early_ending(
                gateway=self._gateway,
                seed=template.seed,
                title=template.title,
                cast=template.cast,
                history=full_history,
                failure_trigger=failure_trigger,
                failure_reason=failure_reason,
                player_role=player_role,
                language=template.language,
            )
        except (NarrativeGatewayError, NarrativeServiceError, ValueError, AttributeError) as exc:
            print(
                f"[narrative.service] early-ending synthesis failed for session={session_id}; using local closeout: {_safe_exception_label(exc)}",
                flush=True,
            )
            result = _deterministic_ending_fallback(
                template=template,
                history=full_history,
                player_role=player_role,
                early=True,
                failure_reason=failure_reason,
            )
        # Early endings are always tier=collapsed by design.
        tier = "collapsed"
        # Highlights + branches for the early collapse. Branches
        # especially valuable here — "you'd have hit a non-collapse
        # ending if you'd done X earlier" is core replay incentive.
        # Parallelize for the same latency win as the full ending path.
        highlights, branches = self._synthesize_postgame_artifacts(
            session_id=session_id,
            template=template,
            full_history=full_history,
            result=result,
            tier=tier,
            player_role=player_role,
            log_prefix="early-ending",
        )
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
            template_title_i18n=template.title_i18n if is_shareable_template else None,
            template_summary_i18n=template.summary_i18n if is_shareable_template else None,
            cast=_public_replay_cast(template.cast) if is_shareable_template else [],
            advisor_persona=template.advisor_persona if is_shareable_template else "",
            cover_image_url=template.cover_image_url if is_shareable_template else None,
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
            options=_playable_opening_options(template),
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


def _deterministic_ending_fallback(
    *,
    template: NarrativeTemplate,
    history: list[StoryMessage],
    player_role: PlayerRole | None = None,
    early: bool = False,
    failure_reason: str | None = None,
) -> EndingResult:
    """Local, player-safe closeout used only when live ending generation fails."""
    last_player = next((m for m in reversed(history) if m.role == "player"), None)
    last_narrator = next((m for m in reversed(history) if m.role == "narrator"), None)
    cast_names = [member.display_name for member in template.cast[:3] if member.display_name]
    cast_line = _fallback_names_text(cast_names) if cast_names else "the room"
    title = normalize_whitespace(template.title or "this run")
    action = _ending_action_clause(last_player.content if last_player else "")
    objective = _sentence_mid_clause(normalize_whitespace(
        (player_role.hidden_objective if player_role else "")
        or (template.player_goals[0].goal if template.player_goals else "")
        or "keep the truth visible"
    ))
    latest_pressure = normalize_whitespace(last_narrator.content if last_narrator else "")
    if template.language == "zh":
        if early:
            reason = normalize_whitespace(failure_reason or "局面已经越过安全线")
            passage = (
                f"最后，{title}没能再被拖回原来的秩序。"
                f"你选择了{action or '最后一步'}，但{cast_line}之间的裂缝已经公开，{reason}。"
                f"这一局没有给任何人漂亮的退场，只留下必须被承认的代价。"
                f"你带着{objective}走出房间，知道下一次选择不能再假装没有发生。"
            )
            return EndingResult(passage=passage, label="失控", subtitle="我没能把局面拉回安全线")
        pressure_sentence = f"最后一幕仍压着你：{_ending_excerpt(latest_pressure, 110)}。" if latest_pressure else ""
        passage = (
            f"{title}在你的最后选择后落定。"
            f"你选择了{action or '最后一步'}，让{cast_line}必须面对公开的版本。"
            f"{pressure_sentence}"
            f"局面并不干净，也不轻松，但最后的目标终于可见：{objective}。"
            "你离开时知道，这段关系已经不可能回到原点。"
        )
        return EndingResult(passage=passage, label="决裂", subtitle="我把最后的版本留在桌上")

    if early:
        reason = normalize_whitespace(failure_reason or "the room crossed the line")
        passage = (
            f"{title} can no longer be pulled back into order. "
            f"After you chose to {action}, {cast_line} have to face the break in public, and {reason}. "
            "No one gets a clean exit; the cost is simply too visible now. "
            f"You leave with one thing still intact: {objective}."
        )
        return EndingResult(
            passage=passage,
            label="失控",
            subtitle="I could not pull the room back",
        )
    pressure_sentence = (
        f"The last pressure still hangs in the room: {_ending_excerpt(latest_pressure, 180)}. "
        if latest_pressure
        else ""
    )
    passage = (
        f"{title} settles around your final choice. "
        f"You chose to {action}, and {cast_line} can no longer hide inside another delay. "
        f"{pressure_sentence}"
        f"The outcome is not clean, but the objective is finally visible: {objective}. "
        "You walk out knowing the next version of this story will have to include what happened here."
    )
    return EndingResult(
        passage=passage,
        label="决裂",
        subtitle="I leave the final version on the table",
    )


def _ending_action_clause(raw: str) -> str:
    text = normalize_whitespace(re.sub(r"^\[[^\]]+\]\s*", "", raw or ""))
    if "—" in text:
        text = normalize_whitespace(text.split("—", 1)[1])
    if not text:
        return "make the final choice"
    return text[:1].lower() + text[1:]


def _ending_excerpt(raw: str, limit: int) -> str:
    text = normalize_whitespace(raw)[:limit].strip()
    return text.rstrip(" .。!！?？,，;；:：—–-")


def _sentence_mid_clause(raw: str) -> str:
    text = normalize_whitespace(raw)
    if not text:
        return "keep the truth visible"
    text = text.rstrip(" .。!！?？,，;；:：")
    return text[:1].lower() + text[1:]


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


def _generate_story_brief_live_opening_with_cap(
    *,
    gateway: NarrativeLLMGateway,
    seed: str,
    language: str,
    story_brief: StoryBrief,
) -> OpeningResult:
    """Run the live opening attempt only until the demo handoff cap.

    The opening result is not persisted until after this function returns, so
    timing out here cannot create a duplicate template/session. The underlying
    HTTP call may finish later, but its result is intentionally discarded.
    """
    timeout_seconds = _STORY_BRIEF_LIVE_OPENING_TIMEOUT_SECONDS
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="story-brief-live-opening")
    future = executor.submit(
        generate_opening,
        gateway=gateway,
        seed=seed,
        language=language,
        story_brief=story_brief,
        max_attempts=1,
    )
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        print(
            f"[narrative.recovery] operation=opening story_brief_live_timeout seconds={timeout_seconds:g}",
            flush=True,
        )
        raise NarrativeServiceError(
            code="opening_live_timeout",
            message="Live opening attempt exceeded the Story Brief demo handoff cap.",
            status_code=504,
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


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
        player_action=player_action,
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
            options=_fallback_turn_options(template, profile, pulses),
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


def _playable_opening_options(template: NarrativeTemplate) -> list[StoryOption]:
    options = list(template.opening_options or [])
    if len(options) >= 3:
        return options

    seen = {normalize_whitespace(option.label).casefold() for option in options}
    for fallback_option in _fallback_turn_options(
        template,
        _template_tension_profile(template),
        pulses=[],
    ):
        key = normalize_whitespace(fallback_option.label).casefold()
        if key in seen:
            continue
        options.append(fallback_option)
        seen.add(key)
        if len(options) >= 3:
            break
    return options


def _prioritize_home_library_templates(
    templates: list[NarrativeTemplate],
) -> list[NarrativeTemplate]:
    return [
        template
        for _, template in sorted(
            enumerate(templates),
            key=lambda item: (
                0 if item[1].owner_user_id == DEFAULT_HOME_STORY_OWNER_ID else 1,
                item[0],
            ),
        )
    ]


def _fallback_turn_pulses(
    *,
    template: NarrativeTemplate,
    agent_plan: AgentPlan,
    played_leverage: PlayedLeverageCard | None,
    profile: str,
    player_action: str = "",
) -> list[NPCPulse]:
    cast_by_id = {member.character_id: member for member in template.cast}
    candidate_ids: list[str] = []
    if played_leverage is not None and played_leverage.npc_id in cast_by_id:
        candidate_ids.append(played_leverage.npc_id)
    candidate_ids.extend(_fallback_turn_action_target_ids(template, player_action))
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


def _fallback_turn_action_target_ids(
    template: NarrativeTemplate,
    player_action: str,
) -> list[str]:
    action = normalize_whitespace(player_action or "").casefold()
    if not action:
        return []
    matches: list[tuple[int, str]] = []
    for member in template.cast:
        name = normalize_whitespace(member.display_name).casefold()
        if not name:
            continue
        position = action.find(name)
        if position >= 0:
            matches.append((position, member.character_id))
    return [npc_id for _, npc_id in sorted(matches, key=lambda item: item[0])]


def _fallback_turn_pulse_state(profile: str, *, played: bool) -> str:
    if played:
        return "reacting to the shown card"
    if profile in {"cozy_mystery", "comedy"}:
        return "tracking the social cue"
    if profile == "fantasy_sci_fi":
        return "watching the rule shift"
    if profile == "family_social":
        return "weighing the loyalty test"
    return "recalculating their public stance"


def _fallback_turn_pulse_shift(profile: str) -> str:
    if profile in {"cozy_mystery", "comedy"}:
        return "warmer"
    return "wary"


def _fallback_turn_pulse_reason(profile: str) -> str:
    if profile in {"cozy_mystery", "comedy"}:
        return "Your move kept the room curious."
    if profile == "fantasy_sci_fi":
        return "Your move made the rule visible."
    if profile == "family_social":
        return "Your move tested the shared bond."
    return "Your move changed the public account."


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
    stage_line = _fallback_turn_stage_line(agent_plan.director.stage_phase, profile)
    turn_variant = agent_plan.turn_index % 3
    object_label = _fallback_turn_object_label(template)
    if profile in {"cozy_mystery", "comedy"}:
        if turn_variant == 1:
            text = (
                f"After {action}, the {scene} pauses around the {object_label}. "
                f"{first_subject} {_fallback_verb(first, 'points', 'point')} to a small timing detail, and "
                f"{second} {_fallback_verb(second, 'keeps', 'keep')} the explanation light enough for repair. "
                f"{stage_line} The next move can check the handoff, invite a quieter voice, or turn the mix-up into a payoff."
            )
        elif turn_variant == 2:
            object_verb = _fallback_verb(object_label, "becomes", "become")
            text = (
                f"The {object_label} {object_verb} easier to read once {action}. "
                f"{first_subject} {_fallback_verb(first, 'softens', 'soften')} first, while {second} "
                f"{_fallback_verb(second, 'notices', 'notice')} who is still hesitating. "
                f"{stage_line} The next beat can compare versions gently or let the room laugh before blame settles."
            )
        else:
            text = (
                f"The {scene} shifts after {action}. {first_subject} {_fallback_verb(first, 'catches', 'catch')} the detail first, "
                f"and {second} {_fallback_verb(second, 'leaves', 'leave')} room for a less dramatic explanation instead of "
                f"turning the moment into a pile-on. {stage_line} The next beat can test "
                f"the {object_label}, invite the quiet party in, or let the callback land before "
                f"anyone chooses a version of events."
            )
    elif profile == "fantasy_sci_fi":
        if turn_variant == 1:
            text = (
                f"After {action}, the {object_label} draws the {scene} inward. "
                f"{first_subject} {_fallback_verb(first, 'reads', 'read')} the first change, while {second} "
                f"{_fallback_verb(second, 'tests', 'test')} which old rule still holds. "
                f"{stage_line} The next beat can ask the quieter faction to interpret the sign."
            )
        elif turn_variant == 2:
            text = (
                f"The {scene} gives back a clearer sign once {action}. "
                f"{first_subject} {_fallback_verb(first, 'moves', 'move')} toward the {object_label}, and {second} "
                f"{_fallback_verb(second, 'tracks', 'track')} the faction claim behind it. "
                f"{stage_line} The next beat can place the artifact where everyone can answer."
            )
        else:
            text = (
                f"The {scene} answers after {action}. {first_subject} {_fallback_verb(first, 'turns', 'turn')} toward the visible "
                f"sign, while {second} {_fallback_verb(second, 'notices', 'notice')} which rule, artifact, or faction has "
                f"moved. {stage_line} The next beat can question the change, share the "
                f"sign with a quieter party, or hold the {object_label} where everyone can read it."
            )
    elif profile == "family_social":
        text = (
            f"The {scene} quiets after {action}. {first_subject} {_fallback_verb(first, 'reacts', 'react')} first, and {second} "
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
    stripped = name.strip()
    lower = stripped.casefold()
    if not lower or lower in {"the room", "the boardroom", "the family table"}:
        return False
    if lower in {"hydroponics", "communications", "finance", "transit", "medical", "education", "security"}:
        return False
    if any(token in lower for token in (" and ", ",", "&")):
        return True
    name_tokens = [token for token in re.split(r"\s+", stripped) if token]
    if (
        len(name_tokens) >= 2
        and name_tokens[0].casefold() not in {"a", "an", "the"}
        and all(token[:1].isupper() for token in name_tokens[:2])
    ):
        return False
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
    if " — " in text[:80]:
        return f"your move toward {text}" if not text.startswith("your ") else text
    if text[:1].isupper() and " " in text[:40]:
        text = text[:1].lower() + text[1:]
    return f"your move to {text}" if not text.startswith("your ") else text


def _fallback_turn_stage_line(stage_phase: str, profile: str) -> str:
    if profile in {"cozy_mystery", "comedy"}:
        if stage_phase in {"reversal", "climax", "pre_finale", "pre_finale_open"}:
            return "The social stakes rise, but they stay tied to embarrassment, timing, and repair."
        return "The tension stays public and playful enough to keep moving."
    if profile == "fantasy_sci_fi":
        return "The pressure comes from the old rule in view, not from sudden blame."
    if profile == "family_social":
        return "The pressure stays personal, but nobody has to turn it into spectacle yet."
    return "The pressure stays visible enough that the room has to answer."


def _fallback_turn_options(
    template: NarrativeTemplate,
    profile: str,
    pulses: list[NPCPulse] | None = None,
) -> list[StoryOption]:
    object_label = _fallback_turn_object_label(template)
    names = _fallback_turn_names(template, pulses or [])
    first = names[0] if names else "the closest witness"
    second = names[1] if len(names) > 1 else "the room"
    if profile == "cozy_mystery":
        return [
            StoryOption(label=f"[Ally] Let {first} describe the {object_label}", hint=f"Keeps {first}'s answer gentle", handle="ask witness"),
            StoryOption(label=f"[Probe] Check the {object_label} with {first}", hint="Tests the clue first", handle="check clue"),
            StoryOption(label=f"[Watch] Let {second} soften the room", hint="Buys a calmer beat", handle="soft reset"),
        ]
    if profile == "comedy":
        return [
            StoryOption(label=f"[Ally] Invite {first} into the joke", hint="Keeps the joke shared", handle="invite group"),
            StoryOption(label=f"[Probe] Ask {first} who noticed the {object_label} change", hint="Turns timing into evidence", handle="ask prop"),
            StoryOption(label=f"[Watch] Let {second} catch the callback", hint="Waits for the room to react", handle="let land"),
        ]
    if profile == "fantasy_sci_fi":
        return [
            StoryOption(label=f"[Probe] Ask {first} which old rule changed", hint="Turns the sign into a clue", handle="ask rule"),
            StoryOption(label=f"[Ally] Let {second} interpret the sign", hint="Gives background pressure a voice", handle="quiet voice"),
            StoryOption(label=f"[Watch] Hold the {object_label} where everyone can see it", hint="Keeps the room honest", handle="show object"),
        ]
    if profile == "family_social":
        return [
            StoryOption(label=f"[Ally] Give {first} room to explain", hint="Protects repair before rupture", handle="give room"),
            StoryOption(label=f"[Probe] Ask {first} what was misunderstood first", hint="Looks for the old wound", handle="ask wound"),
            StoryOption(label=f"[Watch] Let {second} name the cost", hint="Tests who still cares", handle="wait cost"),
        ]
    return [
        StoryOption(label=f"[Probe] Ask {first} who benefits from this version", hint=f"Tests {first}'s account", handle="ask benefit"),
        StoryOption(label=f"[Counter] Put one concrete fact to {first}", hint=f"Makes {first} answer", handle="show fact"),
        StoryOption(label=f"[Watch] Let {second} react to {first}", hint="Checks who moves next", handle="watch stake"),
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
    if brief.tension_profile == "high_drama":
        if "publicist" in seed or "awards livestream" in seed or "singer" in seed:
            return ["Publicist under pressure", "Witness handler", "Sponsor-room liaison"]
        if "board" in seed or "merger" in seed or "contract" in seed:
            return ["Deal-room advocate", "Evidence handler", "Public-account keeper"]
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
    pressure_labels: list[str],
) -> str:
    cast_text = _fallback_names_text(cast_names)
    cast_text_mid_sentence = _fallback_names_text(cast_names, sentence_start=False)
    seed = brief.original_seed
    scene = _fallback_scene_label(brief, pressure_labels)
    contested = _fallback_contested_object(seed)
    secondary_event = _fallback_secondary_event_clause(pressure_labels, scene)
    background_text = _fallback_background_sentence(background_names, brief=brief)
    profile_clause = _fallback_profile_clause(brief, contested=contested)
    first_move = _fallback_first_move_clause(brief)
    if _fallback_uses_fantasy_scene(brief):
        return (
            f"In {scene}, {_fallback_contested_status(contested)} just as {_fallback_event_phrase(pressure_labels)} starts to matter{secondary_event}. "
            f"{cast_text} {_fallback_verb(cast_text, 'is', 'are')} trying to read what the old rule means now.{background_text} "
            f"{profile_clause} {first_move}"
        )
    if brief.tension_profile in {"comedy", "cozy_mystery"}:
        return (
            f"At {scene}, the {contested} {_fallback_verb(contested, 'has', 'have')} pulled {cast_text_mid_sentence} into the same public moment while the room is still deciding "
            f"whether this is a mix-up, a performance note, or a public embarrassment{secondary_event}.{background_text} "
            f"{profile_clause} {first_move}"
        )
    return (
        f"At {scene}, {cast_text} are already circling the {contested}, each trying to make the first public account stick{secondary_event}."
        f"{background_text} {profile_clause} {first_move}"
    )


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
    if "disappearance" in lower or "disappears" in lower:
        return "disappearance"
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
        "are trapped",
        "is trapped",
        "were trapped",
        "was trapped",
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
    if brief.tension_profile == "comedy":
        return "Your first move can name a handoff, invite the quiet voice in, or set up the joke before blame takes over."
    if brief.tension_profile == "cozy_mystery":
        return "Your first move can follow a concrete clue, lower the room's worry, or give the nervous witness room to speak."
    if _fallback_uses_fantasy_scene(brief):
        return "Your first move can test the rule, ask the overlooked faction in, or inspect the artifact everyone is avoiding."
    return "Your first move can bring in the quiet party before the loudest version hardens."


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
            StoryOption(label=f"Let the {volunteer} explain the handoff", hint="Lower worry", handle="witness"),
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
        "The first draft did not honor the Brief strongly enough. "
        "The Brief is still saved; build a tighter opening or revise the plan. "
        f"Mismatch signals: {codes or 'brief consistency failed'}."
    )[:500]


def _story_brief_recovered_opening_check(
    check: StoryBriefConsistencyCheck,
    *,
    brief: StoryBrief,
) -> StoryBriefConsistencyCheck:
    if check.status != "fail" or brief.runtime_fit_status == "not_fit":
        return check
    return check.model_copy(
        update={
            "status": "warn",
            "should_retry": False,
            "summary": "The live draft missed required details, so the opening was staged from the saved Story Brief.",
        }
    )


def _elapsed_ms(started_at: float) -> int:
    return max(0, int(round((time.monotonic() - started_at) * 1000)))


def _safe_int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    return None


def _coerce_llm_call_status(raw_status: object, raw_bucket: object) -> LLMCallStatus:
    status = str(raw_status or "").strip()
    if status in {
        "success",
        "timeout",
        "rate_limited",
        "invalid_response",
        "provider_unavailable",
        "fallback_used",
        "repaired",
        "failed",
    }:
        return status  # type: ignore[return-value]
    bucket = str(raw_bucket or "").strip()
    if bucket == "timeout":
        return "timeout"
    if bucket == "rate_limit":
        return "rate_limited"
    if bucket in {"dns", "connection", "auth", "service"}:
        return "provider_unavailable"
    return "success" if not bucket else "failed"


def _fallback_reason_for_exception(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.strip():
        return code.strip()[:160]
    return exc.__class__.__name__[:160]


def _safe_exception_label(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    status_code = getattr(exc, "status_code", None)
    if isinstance(code, str) and code.strip():
        cleaned = code.strip()[:80]
        if isinstance(status_code, int):
            return f"{cleaned}:{status_code}"
        return cleaned
    return exc.__class__.__name__[:80]


def _trace_had_repair(entries: list[dict[str, Any]]) -> bool:
    return any(str(entry.get("status") or "") == "repaired" or int(entry.get("repair_count") or 0) > 0 for entry in entries)


def _safe_short_text(raw: object, fallback: str, *, max_len: int) -> str:
    if isinstance(raw, str):
        cleaned = normalize_whitespace(raw)
        if cleaned:
            return cleaned[:max_len]
    return fallback[:max_len]


def _safe_story_guide_context(
    raw: object,
    fallback: StoryGuideCompressedContext,
    *,
    source: LLMCallSourceLabel,
) -> StoryGuideCompressedContext:
    payload = raw.get("context") if isinstance(raw, dict) and isinstance(raw.get("context"), dict) else raw
    if not isinstance(payload, dict):
        return fallback
    text_fields = (
        "scene_summary",
        "player_role",
        "pressure",
        "tone",
        "last_user_intent",
        "last_question_answered",
        "last_question",
        "planner_skill",
        "planner_job",
    )
    non_story_intent = fallback.last_user_intent in {
        "greeting_smalltalk",
        "meta_assistant",
        "interaction_help",
        "ambiguous_who",
        "unclear_noise",
    }
    preserve_story_facts = non_story_intent and fallback.latest_input_updates_story_facts is False
    story_text_fields = {"scene_summary", "player_role", "pressure", "tone"}
    updates: dict[str, object] = {}
    for field in text_fields:
        raw_value = getattr(fallback, field) if preserve_story_facts and field in story_text_fields else payload.get(field)
        value = _safe_context_text(raw_value, getattr(fallback, field), max_len=260)
        if value:
            updates[field] = value
    for field, limit in (
        ("cast_or_factions", 8),
        ("constraints", 8),
        ("open_questions", 6),
        ("confirmed_facts", 12),
        ("non_story_user_intents", 8),
    ):
        raw_value = getattr(fallback, field) if preserve_story_facts and field in {"cast_or_factions", "constraints", "confirmed_facts"} else payload.get(field)
        value = _safe_context_list(raw_value, getattr(fallback, field), limit=limit)
        updates[field] = value
    raw_changed = payload.get("rejected_or_changed_facts")
    live_changed = raw_changed if isinstance(raw_changed, list) else []
    updates["rejected_or_changed_facts"] = _safe_context_list(
        [*fallback.rejected_or_changed_facts, *live_changed],
        fallback.rejected_or_changed_facts,
        limit=8,
    )
    readiness = payload.get("readiness_score")
    if isinstance(readiness, int | float):
        updates["readiness_score"] = max(0.0, min(1.0, float(readiness)))
    latest_updates = payload.get("latest_input_updates_story_facts")
    if isinstance(latest_updates, bool):
        updates["latest_input_updates_story_facts"] = latest_updates
    updates["compression_source"] = source
    try:
        return fallback.model_copy(update=updates)
    except Exception:  # noqa: BLE001
        return fallback.model_copy(update={"compression_source": "deterministic_fallback"})


def _safe_context_text(raw: object, fallback: str, *, max_len: int) -> str:
    if not isinstance(raw, str):
        return fallback[:max_len]
    cleaned = normalize_whitespace(raw)
    if not cleaned or _contains_player_debug_terms(cleaned):
        return fallback[:max_len]
    return cleaned[:max_len]


def _safe_context_list(raw: object, fallback: list[str], *, limit: int) -> list[str]:
    values = raw if isinstance(raw, list) else fallback
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        value = normalize_whitespace(item)[:220]
        key = value.casefold()
        if not value or key in seen or _contains_player_debug_terms(value):
            continue
        seen.add(key)
        cleaned.append(value)
        if len(cleaned) >= limit:
            break
    return cleaned


def _contains_player_debug_terms(value: str) -> bool:
    lowered = value.casefold()
    return any(
        term in lowered
        for term in (
            "provider",
            "model",
            "api",
            "json",
            "schema",
            "backend",
            "deterministic",
            "fallback",
        )
    )


def _asks_multiple_questions(value: str) -> bool:
    return value.count("?") + value.count("？") > 1


def _is_exact_repeat(value: str, previous: str) -> bool:
    if not previous.strip():
        return False
    return normalize_whitespace(value).casefold() == normalize_whitespace(previous).casefold()


def _repeat_safe_fallback(fallback: str, previous: str) -> str:
    if not _is_exact_repeat(fallback, previous):
        return fallback
    return "Same thread. What one new detail should I lock next?"


def _safe_live_reply(
    raw: object,
    fallback: str,
    *,
    previous_assistant_reply: str = "",
    voice_skill: dict[str, object] | None = None,
) -> str:
    safe_fallback = _repeat_safe_fallback(fallback, previous_assistant_reply)
    reply = _safe_short_text(_unwrap_story_guide_reply(raw), fallback, max_len=420)
    if _contains_player_debug_terms(reply):
        return safe_fallback
    if _asks_multiple_questions(reply):
        return safe_fallback
    if _is_exact_repeat(reply, previous_assistant_reply):
        return safe_fallback
    if not _reply_matches_voice_skill(reply, voice_skill):
        return safe_fallback
    if _looks_like_protocol_wrapper(reply):
        return safe_fallback
    return reply


def _reply_matches_voice_skill(reply: str, voice_skill: dict[str, object] | None) -> bool:
    if not isinstance(voice_skill, dict):
        return True
    skill_id = str(voice_skill.get("id") or "")
    lowered = reply.casefold()
    semantic_markers = {
        "opening_scene_prompt": ("scene", "where", "trouble", "open", "start", "first", "writing desk", "camera"),
        "role_focus": ("who", "you", "player", "closest", "role"),
        "cast_focus": ("who", "else", "people", "group", "faction", "cast", "room", "present"),
        "pressure_focus": ("pressure", "stake", "wrong", "decision", "secret", "object", "handled", "happen"),
        "tone_focus": ("drama", "comedy", "mystery", "tone", "feel", "cut", "social"),
        "boundary_redirect": ("cannot", "can't", "redirect", "instead", "safer", "avoid", "boundary", "pressure"),
        "brief_readiness": ("brief", "enough", "shape", "ready", "lock", "story"),
        "meta_assistant": ("story butler", "i help", "playable", "scene", "rough idea", "open"),
        "interaction_help": ("type", "rough", "scene", "role", "what goes wrong", "one question", "first scene"),
        "clarify_input": ("can't turn", "cannot turn", "story material", "scene spark", "where", "what just went wrong"),
    }
    markers = semantic_markers.get(skill_id)
    if not markers:
        return True
    return any(marker in lowered for marker in markers)


def _unwrap_story_guide_reply(raw: object, *, depth: int = 0) -> object:
    if depth > 3:
        return raw
    if isinstance(raw, dict):
        return _unwrap_story_guide_reply(raw.get("reply"), depth=depth + 1)
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if not text:
        return raw
    decoded = _decode_json_object(text)
    if decoded is not None:
        return _unwrap_story_guide_reply(decoded, depth=depth + 1)
    recovered = _extract_reply_from_json_like_text(text)
    if recovered:
        return recovered
    return raw


def _decode_json_object(value: str) -> dict[str, Any] | None:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            decoded = json.loads(value[start : end + 1])
        except json.JSONDecodeError:
            return None
    return decoded if isinstance(decoded, dict) else None


def _extract_reply_from_json_like_text(value: str) -> str | None:
    match = re.search(r'"reply"\s*:\s*("(?:(?:\\.)|[^"\\])*")', value, re.S)
    if not match:
        return None
    quoted = match.group(1)
    try:
        decoded = json.loads(quoted)
    except json.JSONDecodeError:
        decoded = quoted.strip('"')
    cleaned = normalize_whitespace(str(decoded))
    return cleaned or None


def _looks_like_protocol_wrapper(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if stripped.startswith("{") or stripped.endswith("}"):
        return True
    lowered = stripped.casefold()
    return '"reply"' in lowered or "'reply'" in lowered


def _apply_live_story_brief_copy(
    brief: StoryBrief,
    payload: dict[str, Any],
    *,
    language: str,
) -> StoryBrief:
    updates: dict[str, object] = {"source": "live_hybrid_v1"}
    for key, max_len in (
        ("premise_summary", 260),
        ("genre_tone", 160),
        ("story_kernel", 220),
        ("adaptation_note", 220),
    ):
        value = payload.get(key)
        if isinstance(value, str):
            cleaned = normalize_whitespace(value)
            if cleaned and not _contains_player_debug_terms(cleaned):
                updates[key] = cleaned[:max_len]
    try:
        updated = brief.model_copy(update=updates)
    except Exception:  # noqa: BLE001
        updated = brief.model_copy(update={"source": "live_hybrid_v1"})
    return _with_story_brief_display_metadata(
        updated,
        language=language,
        live_payload=payload,
    )


def _with_story_brief_display_metadata(
    brief: StoryBrief,
    *,
    language: str,
    live_payload: dict[str, Any] | None = None,
) -> StoryBrief:
    title_candidate = None
    intro_candidate = None
    if isinstance(live_payload, dict):
        title_candidate = live_payload.get("display_title")
        intro_candidate = live_payload.get("display_intro")
    title, intro = _concise_story_display_metadata(
        language=language,
        title_candidates=[
            title_candidate,
            brief.display_title,
            _fallback_title(brief, _fallback_pressure_labels(brief)),
            brief.genre_tone,
        ],
        intro_candidates=[
            intro_candidate,
            brief.display_intro,
            brief.premise_summary,
            brief.story_kernel,
            brief.original_seed,
        ],
    )
    return brief.model_copy(update={"display_title": title, "display_intro": intro})


def _template_display_metadata(
    *,
    seed: str,
    language: str,
    opening: OpeningResult,
    story_brief: StoryBrief | None,
) -> tuple[str, str]:
    title_candidates: list[object] = []
    intro_candidates: list[object] = []
    if story_brief is not None:
        title_candidates.extend(
            [
                story_brief.display_title,
                _fallback_title(story_brief, _fallback_pressure_labels(story_brief)),
                story_brief.genre_tone,
            ]
        )
        intro_candidates.extend(
            [
                story_brief.display_intro,
                story_brief.premise_summary,
                story_brief.story_kernel,
            ]
        )
    title_candidates.extend([opening.title, seed])
    intro_candidates.extend([seed, opening.opening_message.content])
    return _concise_story_display_metadata(
        language=language,
        title_candidates=title_candidates,
        intro_candidates=intro_candidates,
    )


def _concise_story_display_metadata(
    *,
    language: str,
    title_candidates: list[object],
    intro_candidates: list[object],
) -> tuple[str, str]:
    title = ""
    for candidate in title_candidates:
        title = _clean_display_title(candidate, language=language)
        if title:
            break
    intro = ""
    for candidate in intro_candidates:
        intro = _clean_display_intro(candidate, language=language)
        if intro:
            break
    if not title:
        title = "First Scene" if language != "zh" else "第一幕"
    if not intro:
        intro = "A tense first scene waits for your choice." if language != "zh" else "第一幕等待你的选择。"
    return title, intro


def _clean_display_title(raw: object, *, language: str) -> str:
    text = _clean_display_fragment(raw)
    if not text or _contains_player_debug_terms(text):
        return ""
    text = re.split(r"[。.!?]\s*", text, maxsplit=1)[0].strip()
    text = re.split(r"\s+[—–-]\s+|[:：]|·", text, maxsplit=1)[0].strip()
    if language == "zh":
        return _limit_cjk_display(text, 18)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’]*", text)
    if not words:
        return ""
    words = words[:6]
    if len(words) == 1:
        words.append("Story")
    title = " ".join(words)
    if raw and str(raw).strip().istitle():
        return _limit_english_display(title, 52)
    return _limit_english_display(_title_case_english_display(title), 52)


def _title_case_english_display(text: str) -> str:
    title = text.title()
    return re.sub(r"(['’])S\b", r"\1s", title)


def _clean_display_intro(raw: object, *, language: str) -> str:
    text = _clean_display_fragment(raw)
    if not text or _contains_player_debug_terms(text):
        return ""
    if _contains_internal_display_intro_terms(text):
        return ""
    text = re.split(r"(?:#|\btags?:|\bmetadata:)", text, flags=re.IGNORECASE)[0].strip()
    if language == "zh":
        sentence = re.split(r"[。！？]", text, maxsplit=1)[0].strip()
        return _limit_cjk_display(sentence, 56)
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
    sentence = _limit_english_intro_display(sentence, 118)
    if _english_intro_has_incomplete_shape(sentence):
        return ""
    if sentence and sentence[-1] not in ".!?":
        sentence = f"{sentence.rstrip(' ,;:')}."
    return sentence


def _clean_display_fragment(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    text = normalize_whitespace(raw)
    text = text.replace("…", " ").replace("...", " ")
    text = re.sub(r"[#*_`]+", "", text)
    text = re.sub(r"\s*(?:->|→)\s*", " ", text)
    return normalize_whitespace(text).strip(" -–—·|")


def _limit_english_display(text: str, limit: int) -> str:
    text = normalize_whitespace(text)
    if len(text) <= limit:
        return text.strip()
    clipped = text[:limit].rsplit(" ", 1)[0].strip(" ,;:-–—")
    return clipped or text[:limit].strip(" ,;:-–—")


def _limit_english_intro_display(text: str, limit: int) -> str:
    text = normalize_whitespace(text)
    weak_tail_pattern = (
        r"\b(a|an|the|to|of|for|with|without|in|on|at|by|from|into|onto|inside|outside|around|under|over|between|among|or|just|before|after|while|that|which|who|whose|could|would|must|can|will|might|prove|reveal|hide|expose|change|care)$"
    )
    if re.search(weak_tail_pattern, text.rstrip(".!?").casefold()):
        return ""
    if len(text) <= limit:
        return text.strip()
    clipped = text[:limit].rsplit(" ", 1)[0].strip(" ,;:-–—")
    lower = clipped.casefold()
    weak_tail = re.search(weak_tail_pattern, lower)
    if weak_tail:
        best_clause = ""
        for marker in (", but ", ", and ", " that ", " which ", " who ", " whose ", " while ", " before ", " after ", " just "):
            idx = clipped.lower().rfind(marker)
            if idx >= 48:
                best_clause = clipped[:idx].strip(" ,;:-–—")
                break
        if best_clause:
            return best_clause
        clipped = re.sub(r"\s+" + weak_tail_pattern, "", clipped, flags=re.IGNORECASE).strip(" ,;:-–—")
        if not clipped or len(clipped) < 48:
            return ""
        if re.search(r"\b(puts?|places?|forces?|leaves?|sends?|throws?|turns?)\s+[^.!?]{0,80}$", clipped, re.IGNORECASE):
            return ""
    return clipped or text[:limit].strip(" ,;:-–—")


def _english_intro_has_incomplete_shape(text: str) -> bool:
    lower = normalize_whitespace(text).strip().rstrip(".!?").casefold()
    if not lower:
        return True
    if re.search(
        r"\b(a|an|the|to|of|for|with|without|in|on|at|by|from|into|onto|inside|outside|around|under|over|between|among|or|just|before|after|while|that|which|who|whose|could|would|must|can|will|might|prove|reveal|hide|expose|change|care)$",
        lower,
    ):
        return True
    incomplete_patterns = (
        r"\b(sends?|puts?|places?|forces?|leaves?|throws?)\s+[^.!?]{24,}$",
        r"\bdecide\s+whether\s+to\s+[^.!?]{8,}\s+or\s+let\s+the\s+[^.!?]{3,}$",
        r"\bcould\s+prove\s+a\s+[a-z][a-z'’_-]{2,}$",
        r"\b(?:among|between)\s+[^.!?]+,\s+a\s+[a-z][a-z'’_-]{2,}(?:\s+[a-z][a-z'’_-]{2,}){0,3}$",
    )
    return any(re.search(pattern, lower) for pattern in incomplete_patterns)


def _contains_internal_display_intro_terms(text: str) -> bool:
    lowered = text.casefold()
    if "; pressure:" in lowered:
        return True
    if "relationship shift" in lowered or re.search(r"\b(leverage|confrontation)\b", lowered):
        return True
    return bool(
        re.search(
            r"\b(high drama|cozy mystery|family social|comedy|fantasy sci[- ]?fi)\s+scene\s+with\b",
            lowered,
        )
    )


def _limit_cjk_display(text: str, limit: int) -> str:
    text = normalize_whitespace(text)
    if len(text) <= limit:
        return text.strip()
    return text[:limit].strip(" ，、；：。！？-–—")


def _localized_text_for_language(value: str, language: str) -> LocalizedText | None:
    text = value.strip()
    if not text:
        return None
    if language == "zh":
        return LocalizedText(zh=text)
    return LocalizedText(en=text)


def _summarize_template(
    template: NarrativeTemplate, *, viewer_user_id: str
) -> NarrativeTemplateSummary:
    return NarrativeTemplateSummary(
        template_id=template.template_id,
        owner_user_id=template.owner_user_id,
        seed=template.seed,
        title=template.title,
        title_i18n=template.title_i18n,
        summary_i18n=template.summary_i18n,
        cast=template.cast,
        advisor_persona=template.advisor_persona,
        cover_image_url=template.cover_image_url,
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
    display_turn_count = min(session.turn_count, session.turn_budget)
    return NarrativeSessionSummary(
        session_id=session.session_id,
        template_id=session.template_id,
        template_title=template.title,
        template_seed=template.seed,
        template_title_i18n=template.title_i18n,
        template_summary_i18n=template.summary_i18n,
        player_user_id=session.player_user_id,
        turn_count=display_turn_count,
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
