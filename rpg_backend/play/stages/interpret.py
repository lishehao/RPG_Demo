from __future__ import annotations

from dataclasses import dataclass
import re

from pydantic import ValidationError

from rpg_backend.author.normalize import trim_ellipsis, unique_preserve
from rpg_backend.generation_skill import ContextCard, GenerationSkillPacket
from rpg_backend.llm_gateway import CapabilityGatewayCore, GatewayCapabilityError, TextCapabilityRequest
from rpg_backend.responses_transport import strip_model_meta_wrapper_text
from rpg_backend.play.contracts import PlayPlan, PlaySuggestedAction, PlayTurnIntentDraft
from rpg_backend.play.gateway import PlayGatewayError
from rpg_backend.play.runtime import (
    PlaySessionState,
    available_affordance_tags,
    heuristic_first_turn_fast_path_intent,
    heuristic_turn_intent,
)


@dataclass(frozen=True)
class InterpretTurnResult:
    intent: PlayTurnIntentDraft
    source: str
    attempts: int = 0
    failure_reason: str | None = None
    response_id: str | None = None
    usage: dict[str, int | str] | None = None
    capability: str | None = None
    provider: str | None = None
    model: str | None = None
    transport_style: str | None = None
    skill_id: str | None = None
    skill_version: str | None = None
    contract_mode: str | None = None
    context_card_ids: list[str] | None = None
    context_packet_characters: int | None = None
    repair_mode: str | None = None


def _response_skill_kwargs(response: object) -> dict[str, object]:
    return {
        "skill_id": getattr(response, "skill_id", None),
        "skill_version": getattr(response, "skill_version", None),
        "contract_mode": getattr(response, "contract_mode", None),
        "context_card_ids": list(getattr(response, "context_card_ids", []) or []),
        "context_packet_characters": getattr(response, "context_packet_characters", None),
        "repair_mode": getattr(response, "repair_mode", None),
    }


def _cast_lookup(plan: PlayPlan) -> dict[str, str]:
    return {npc.npc_id: npc.name for npc in plan.cast}


def _current_beat_runtime_shard(plan: PlayPlan, state: PlaySessionState):
    current_beat_id = plan.beats[state.beat_index].beat_id
    return next((item for item in list(plan.beat_runtime_shards or []) if item.beat_id == current_beat_id), None)


def _hint_card_content(cards: list[object], card_id: str) -> dict[str, object]:
    for item in cards:
        if getattr(item, "card_id", None) == card_id:
            return dict(getattr(item, "content", {}) or {})
    return {}


def _non_player_npcs(plan: PlayPlan):
    return [npc for npc in plan.cast if npc.npc_id != plan.protagonist_npc_id]


def _compact_npc_catalog(plan: PlayPlan) -> list[dict[str, str]]:
    return [
        {
            "npc_id": npc.npc_id,
            "name": trim_ellipsis(npc.name, 36),
        }
        for npc in _non_player_npcs(plan)
    ]


def _compact_npc_names(plan: PlayPlan, npc_ids: list[str]) -> list[str]:
    cast_lookup = _cast_lookup(plan)
    return [trim_ellipsis(cast_lookup.get(npc_id, npc_id), 36) for npc_id in npc_ids[:2]]


def _build_interpret_payload(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    input_text: str,
    selected_prompt: str | None,
) -> dict[str, object]:
    beat = plan.beats[state.beat_index]
    shard = _current_beat_runtime_shard(plan, state)
    shard_beat_card = _hint_card_content(list(getattr(shard, "interpret_hint_cards", []) or []), "beat_card") if shard is not None else {}
    return {
        "story_title": trim_ellipsis(plan.story_title, 80),
        "runtime_policy_profile": plan.runtime_policy_profile,
        "current_beat": {
            "title": trim_ellipsis(beat.title, 64),
            "goal": trim_ellipsis(beat.goal, 120),
            "focus_npcs": _compact_npc_names(plan, list(shard_beat_card.get("focus_npc_ids") or beat.focus_npcs)),
            "conflict_npcs": _compact_npc_names(plan, list(shard_beat_card.get("conflict_npc_ids") or beat.conflict_npcs)),
            "available_affordance_tags": available_affordance_tags(plan, state),
        },
        "player_input": trim_ellipsis(input_text, 360),
        "selected_suggestion_prompt": trim_ellipsis(selected_prompt, 180) if selected_prompt else None,
        "npc_catalog": _compact_npc_catalog(plan),
    }


def _infer_execution_frame(*, input_text: str, selected_prompt: str | None = None) -> str:
    text = " ".join(part for part in (selected_prompt or "", input_text) if part).casefold()
    coercive_markers = (
        "force",
        "threaten",
        "command",
        "order",
        "seize",
        "ultimatum",
        "drag",
        "lock down",
        "guards",
        "broadcast it now",
    )
    public_markers = (
        "public",
        "crowd",
        "gallery",
        "hearing",
        "council floor",
        "loudspeaker",
        "broadcast",
        "address system",
        "warning bells",
        "podium",
        "shout",
        "declare",
        "read aloud",
    )
    coalition_markers = (
        "joint",
        "together",
        "co-author",
        "invite",
        "convene",
        "shared",
        "unified",
        "truce",
        "accord",
        "compact",
        "pact",
        "witnesses present",
        "with me",
    )
    procedural_markers = (
        "audit",
        "verify",
        "compare",
        "inspect",
        "review",
        "line by line",
        "records hall",
        "chain-of-custody",
        "sealed archive",
        "ledger",
        "manifest",
        "evidence",
    )
    hard_coercive_markers = ("threaten", "seize", "ultimatum", "guards", "lock down")
    if any(marker in text for marker in public_markers) and not any(marker in text for marker in hard_coercive_markers):
        return "public"
    if any(marker in text for marker in coercive_markers):
        return "coercive"
    if any(marker in text for marker in coalition_markers):
        return "coalition"
    if any(marker in text for marker in procedural_markers):
        return "procedural"
    if re.search(r"\b(we|together|jointly|shared)\b", text):
        return "coalition"
    return "procedural"


def _sanitize_intent(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    intent: PlayTurnIntentDraft,
) -> PlayTurnIntentDraft:
    beat = plan.beats[state.beat_index]
    ordered_non_player_ids = [npc.npc_id for npc in _non_player_npcs(plan)]
    allowed_ids = set(ordered_non_player_ids)
    target_npc_ids = unique_preserve(
        [
            npc_id
            for npc_id in intent.target_npc_ids
            if npc_id and npc_id in allowed_ids
        ]
    )[:3]
    if not target_npc_ids:
        target_npc_ids = [
            npc_id
            for npc_id in [*beat.focus_npcs, *beat.conflict_npcs]
            if npc_id in allowed_ids
        ][:2]
    if not target_npc_ids:
        target_npc_ids = ordered_non_player_ids[:2]
    execution_frame = intent.execution_frame
    if execution_frame not in {"procedural", "coalition", "public", "coercive"}:
        execution_frame = _infer_execution_frame(input_text=intent.tactic_summary)
    return intent.model_copy(update={"target_npc_ids": target_npc_ids, "execution_frame": execution_frame})


def _interpret_output_budget(gateway: CapabilityGatewayCore) -> int | None:
    budget = gateway.text_policy("play.interpret").max_output_tokens
    if budget is None:
        return 128
    return min(int(budget), 128)


def _interpret_repair_output_budget(gateway: CapabilityGatewayCore) -> int | None:
    budget = gateway.text_policy("play.interpret_repair").max_output_tokens
    if budget is None:
        return 144
    return min(int(budget), 144)


def _interpret_skill_packet(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    input_text: str,
    selected_prompt: str | None,
    capability: str,
    skill_id: str,
    task_brief: str,
    repair_mode: str = "none",
    failure_reason: str | None = None,
) -> GenerationSkillPacket:
    payload = _build_interpret_payload(
        plan=plan,
        state=state,
        input_text=input_text,
        selected_prompt=selected_prompt,
    )
    shard = _current_beat_runtime_shard(plan, state)
    cards = (
        *(
            (
                ContextCard(
                    "beat_runtime_shard_card",
                    {
                        "beat_id": shard.beat_id,
                        "pressure_axis_id": shard.pressure_axis_id,
                        "required_truth_ids": list(shard.required_truth_ids),
                        "required_event_ids": list(shard.required_event_ids),
                        "affordance_tags": list(shard.affordance_tags),
                        "blocked_affordances": list(shard.blocked_affordances),
                    },
                    priority=5,
                ),
            )
            if shard is not None
            else ()
        ),
        ContextCard("beat_card", payload["current_beat"], priority=10),
        ContextCard(
            "input_card",
            {
                "player_input": payload["player_input"],
                "selected_suggestion_prompt": payload["selected_suggestion_prompt"],
            },
            priority=20,
        ),
        ContextCard("npc_catalog_card", {"npc_catalog": payload["npc_catalog"]}, priority=30),
    )
    extra_payload = dict(payload)
    if failure_reason is not None:
        extra_payload["failure_reason"] = failure_reason
    return GenerationSkillPacket(
        skill_id=skill_id,
        skill_version="v1",
        capability=capability,
        contract_mode="strict_json_schema",
        role_style="plain",
        required_output_contract="Return exactly one PlayTurnIntentDraft JSON object.",
        context_cards=cards,
        task_brief=task_brief,
        repair_mode=repair_mode,
        repair_note="Repair the invalid intent extraction while keeping the same strict JSON contract." if repair_mode != "none" else None,
        final_contract_note="Return raw JSON only. Exactly one PlayTurnIntentDraft object." if repair_mode != "none" else None,
        extra_payload=extra_payload,
    )


def _extract_salvaged_target_ids(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    raw_text: str,
) -> list[str]:
    lowered = raw_text.casefold()
    matched = [
        npc.npc_id
        for npc in _non_player_npcs(plan)
        if npc.npc_id.casefold() in lowered
        or npc.name.casefold() in lowered
        or npc.name.casefold().split()[0] in lowered
    ][:3]
    if matched:
        return matched
    beat = plan.beats[state.beat_index]
    return [
        npc_id
        for npc_id in [*beat.focus_npcs, *beat.conflict_npcs]
        if npc_id != plan.protagonist_npc_id
    ][:2]


def _extract_salvaged_risk_level(raw_text: str, *, default: str) -> str:
    lowered = raw_text.casefold()
    explicit = re.search(r"\b(low|medium|high)\b", lowered)
    if explicit:
        return explicit.group(1)
    if any(token in lowered for token in ("threat", "force", "seize", "ultimatum", "publicly corner")):
        return "high"
    if any(token in lowered for token in ("carefully", "quietly", "gently", "privately")):
        return "low"
    return default


def _extract_salvaged_affordance_tag(
    *,
    available_tags: list[str],
    raw_text: str,
    default: str,
) -> str:
    lowered = raw_text.casefold()
    for tag in available_tags:
        normalized = tag.replace("_", " ")
        if tag.casefold() in lowered or normalized.casefold() in lowered:
            return tag
    return default


def _salvage_interpret_intent(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    input_text: str,
    selected_prompt: str | None,
    raw_text: str | None,
) -> PlayTurnIntentDraft | None:
    cleaned = strip_model_meta_wrapper_text(str(raw_text or ""))
    if not cleaned:
        return None
    base = heuristic_turn_intent(
        input_text=input_text,
        plan=plan,
        state=state,
        selected_prompt=selected_prompt,
    )
    available_tags = list(available_affordance_tags(plan, state))
    intent = PlayTurnIntentDraft(
        affordance_tag=_extract_salvaged_affordance_tag(
            available_tags=available_tags,
            raw_text=cleaned,
            default=base.affordance_tag,
        ),  # type: ignore[arg-type]
        target_npc_ids=_extract_salvaged_target_ids(plan=plan, state=state, raw_text=cleaned),
        risk_level=_extract_salvaged_risk_level(cleaned, default=base.risk_level),  # type: ignore[arg-type]
        execution_frame=_infer_execution_frame(input_text=cleaned, selected_prompt=selected_prompt),  # type: ignore[arg-type]
        tactic_summary=trim_ellipsis(cleaned.replace("\n", " "), 220) or base.tactic_summary,
    )
    return _sanitize_intent(plan=plan, state=state, intent=intent)


def repair_interpret_turn(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    input_text: str,
    selected_action: PlaySuggestedAction | None,
    gateway: CapabilityGatewayCore,
    previous_response_id: str | None,
    failure_reason: str,
) -> InterpretTurnResult | None:
    selected_prompt = selected_action.prompt if selected_action is not None else None
    system_prompt = (
        "Repair the player-intent extraction for a deterministic story game. "
        "Return strict JSON with affordance_tag, target_npc_ids, risk_level, execution_frame, tactic_summary. "
        "Use one provided affordance_tag and npc ids only. "
        "risk_level must be low, medium, or high. "
        "execution_frame must be procedural, coalition, public, or coercive. "
        "Keep tactic_summary under 14 words."
    )
    skill_packet = _interpret_skill_packet(
        plan=plan,
        state=state,
        input_text=input_text,
        selected_prompt=selected_prompt,
        capability="play.interpret_repair",
        skill_id="play.interpret.repair",
        task_brief=system_prompt,
        repair_mode="schema_repair",
        failure_reason=failure_reason,
    )
    try:
        response = gateway.invoke_text_capability(
            "play.interpret_repair",
            TextCapabilityRequest(
                system_prompt=skill_packet.build_system_prompt(variant="repair"),
                user_payload=skill_packet.context_payload(),
                max_output_tokens=_interpret_repair_output_budget(gateway),
                previous_response_id=previous_response_id,
                operation_name="play_interpret_repair",
                allow_raw_text_passthrough=True,
                skill_id=skill_packet.skill_id,
                skill_version=skill_packet.skill_version,
                contract_mode=skill_packet.contract_mode,
                context_card_ids=skill_packet.context_card_ids(),
                context_packet_characters=skill_packet.context_packet_characters(),
                repair_mode=skill_packet.repair_mode,
            ),
        )
        if response.fallback_source == "raw_text_passthrough":
            salvaged = _salvage_interpret_intent(
                plan=plan,
                state=state,
                input_text=input_text,
                selected_prompt=selected_prompt,
                raw_text=response.raw_text,
            )
            if salvaged is not None:
                return InterpretTurnResult(
                    intent=salvaged,
                    source="llm_salvage",
                    attempts=2,
                    failure_reason=failure_reason,
                    response_id=response.response_id,
                    usage=response.usage,
                    capability=response.capability,
                    provider=response.provider,
                    model=response.model,
                    transport_style=response.transport_style,
                    **_response_skill_kwargs(response),
                )
        try:
            parsed_intent = PlayTurnIntentDraft.model_validate(response.payload)
        except ValidationError:
            salvaged = _salvage_interpret_intent(
                plan=plan,
                state=state,
                input_text=input_text,
                selected_prompt=selected_prompt,
                raw_text=response.raw_text,
            )
            if salvaged is None:
                raise
            return InterpretTurnResult(
                intent=salvaged,
                source="llm_salvage",
                attempts=2,
                failure_reason=failure_reason,
                response_id=response.response_id,
                usage=response.usage,
                capability=response.capability,
                provider=response.provider,
                model=response.model,
                transport_style=response.transport_style,
                **_response_skill_kwargs(response),
            )
        intent = _sanitize_intent(
            plan=plan,
            state=state,
            intent=parsed_intent,
        )
        return InterpretTurnResult(
            intent=intent,
            source="llm_repair",
            attempts=2,
            failure_reason=failure_reason,
            response_id=response.response_id,
            usage=response.usage,
            capability="play.interpret_repair",
            provider="openai_compatible",
            model=getattr(gateway, "model", None),
            transport_style=getattr(gateway, "transport_style", None),
            **_response_skill_kwargs(response),
        )
    except (GatewayCapabilityError, PlayGatewayError, ValidationError):
        return None


def interpret_turn(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    input_text: str,
    selected_action: PlaySuggestedAction | None,
    gateway: CapabilityGatewayCore | None,
    previous_response_id: str | None,
    enable_interpret_repair: bool,
) -> InterpretTurnResult:
    selected_prompt = selected_action.prompt if selected_action is not None else None
    selected_tag = None
    if selected_action is not None and selected_action.suggestion_id:
        selected_tag = re.sub(r"_\d+$", "", selected_action.suggestion_id)
    if gateway is None:
        intent = _sanitize_intent(
            plan=plan,
            state=state,
            intent=heuristic_turn_intent(
                input_text=input_text,
                plan=plan,
                state=state,
                selected_prompt=selected_prompt,
            ),
        )
        return InterpretTurnResult(
            intent=intent,
            source="heuristic",
            attempts=0,
        )
    fast_path_intent = heuristic_first_turn_fast_path_intent(
        input_text=input_text,
        plan=plan,
        state=state,
        selected_prompt=selected_prompt,
        selected_tag=selected_tag,
    )
    if fast_path_intent is not None:
        intent = _sanitize_intent(
            plan=plan,
            state=state,
            intent=fast_path_intent,
        )
        return InterpretTurnResult(
            intent=intent,
            source="heuristic",
            attempts=0,
        )
    payload = _build_interpret_payload(
        plan=plan,
        state=state,
        input_text=input_text,
        selected_prompt=selected_prompt,
    )
    system_prompt = (
        "Interpret the player's move for a deterministic story game. "
        "Return strict JSON with affordance_tag, target_npc_ids, risk_level, execution_frame, tactic_summary. "
        "Use one provided affordance_tag and npc ids only. "
        "risk_level must be low, medium, or high. "
        "execution_frame must be procedural, coalition, public, or coercive. "
        "Use procedural for audits or verification, coalition for shared bargaining, public for crowd-facing moves, coercive for threats or hard force. "
        "Keep tactic_summary under 14 words."
    )
    skill_packet = _interpret_skill_packet(
        plan=plan,
        state=state,
        input_text=input_text,
        selected_prompt=selected_prompt,
        capability="play.interpret",
        skill_id="play.interpret.primary",
        task_brief=system_prompt,
    )
    try:
        response = gateway.invoke_text_capability(
            "play.interpret",
            TextCapabilityRequest(
                system_prompt=skill_packet.build_system_prompt(variant="normal"),
                user_payload=skill_packet.context_payload(),
                max_output_tokens=_interpret_output_budget(gateway),
                previous_response_id=previous_response_id,
                operation_name="play_interpret_turn",
                allow_raw_text_passthrough=True,
                skill_id=skill_packet.skill_id,
                skill_version=skill_packet.skill_version,
                contract_mode=skill_packet.contract_mode,
                context_card_ids=skill_packet.context_card_ids(),
                context_packet_characters=skill_packet.context_packet_characters(),
                repair_mode=skill_packet.repair_mode,
            ),
        )
        if response.fallback_source == "raw_text_passthrough":
            salvaged = _salvage_interpret_intent(
                plan=plan,
                state=state,
                input_text=input_text,
                selected_prompt=selected_prompt,
                raw_text=response.raw_text,
            )
            if salvaged is not None:
                return InterpretTurnResult(
                    intent=salvaged,
                    source="llm_salvage",
                    attempts=1,
                    failure_reason="play_llm_invalid_json",
                    response_id=response.response_id,
                    usage=response.usage,
                    capability=response.capability,
                    provider=response.provider,
                    model=response.model,
                    transport_style=response.transport_style,
                    **_response_skill_kwargs(response),
                )
        try:
            parsed_intent = PlayTurnIntentDraft.model_validate(response.payload)
        except ValidationError:
            salvaged = _salvage_interpret_intent(
                plan=plan,
                state=state,
                input_text=input_text,
                selected_prompt=selected_prompt,
                raw_text=response.raw_text,
            )
            if salvaged is None:
                raise
            return InterpretTurnResult(
                intent=salvaged,
                source="llm_salvage",
                attempts=1,
                failure_reason="play_llm_schema_invalid",
                response_id=response.response_id,
                usage=response.usage,
                capability=response.capability,
                provider=response.provider,
                model=response.model,
                transport_style=response.transport_style,
                **_response_skill_kwargs(response),
            )
        intent = _sanitize_intent(
            plan=plan,
            state=state,
            intent=parsed_intent,
        )
        return InterpretTurnResult(
            intent=intent,
            source="llm",
            attempts=1,
            response_id=response.response_id,
            usage=response.usage,
            capability=response.capability,
            provider=response.provider,
            model=response.model,
            transport_style=response.transport_style,
            **_response_skill_kwargs(response),
        )
    except GatewayCapabilityError as exc:
        mapped = PlayGatewayError(
            code={
                "gateway_text_provider_failed": "play_llm_provider_failed",
                "gateway_text_invalid_response": "play_llm_invalid_response",
                "gateway_text_invalid_json": "play_llm_invalid_json",
                "gateway_text_model_missing": "play_llm_config_missing",
                "gateway_text_config_missing": "play_llm_config_missing",
            }.get(exc.code, exc.code),
            message=exc.message,
            status_code=exc.status_code,
        )
        failure_reason = mapped.code
        exc = mapped
        if enable_interpret_repair:
            repair = repair_interpret_turn(
                plan=plan,
                state=state,
                input_text=input_text,
                selected_action=selected_action,
                gateway=gateway,
                previous_response_id=previous_response_id,
                failure_reason=failure_reason,
            )
            if repair is not None:
                return repair
        intent = _sanitize_intent(
            plan=plan,
            state=state,
            intent=heuristic_turn_intent(
                input_text=input_text,
                plan=plan,
                state=state,
                selected_prompt=selected_prompt,
            ),
        )
        return InterpretTurnResult(
            intent=intent,
            source="heuristic",
            attempts=2 if enable_interpret_repair else 1,
            failure_reason=failure_reason,
        )
    except (PlayGatewayError, ValidationError) as exc:
        failure_reason = exc.code if isinstance(exc, PlayGatewayError) else "play_llm_schema_invalid"
        if enable_interpret_repair:
            repair = repair_interpret_turn(
                plan=plan,
                state=state,
                input_text=input_text,
                selected_action=selected_action,
                gateway=gateway,
                previous_response_id=previous_response_id,
                failure_reason=failure_reason,
            )
            if repair is not None:
                return repair
        intent = _sanitize_intent(
            plan=plan,
            state=state,
            intent=heuristic_turn_intent(
                input_text=input_text,
                plan=plan,
                state=state,
                selected_prompt=selected_prompt,
            ),
        )
        return InterpretTurnResult(
            intent=intent,
            source="heuristic",
            attempts=2 if enable_interpret_repair else 1,
            failure_reason=failure_reason,
        )
