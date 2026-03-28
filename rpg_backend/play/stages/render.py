from __future__ import annotations

import json
from dataclasses import dataclass, replace
import re

from pydantic import ValidationError

from rpg_backend.author.normalize import trim_ellipsis
from rpg_backend.content_language import is_chinese_language, output_language_instruction, prompt_role_instruction
from rpg_backend.generation_skill import ContextCard, GenerationSkillPacket, build_role_style_context
from rpg_backend.llm_gateway import CapabilityGatewayCore, GatewayCapabilityError, TextCapabilityRequest
from rpg_backend.responses_transport import strip_model_meta_wrapper_text
from rpg_backend.play.contracts import PlayPlan, PlayRenderPlanDraft, PlayResolutionEffect, PlaySuggestedAction
from rpg_backend.play.gateway import PlayGatewayError
from rpg_backend.play.runtime import (
    PlaySessionState,
    build_session_snapshot,
    build_suggested_actions,
    deterministic_narration,
)
from rpg_backend.play.text_quality import (
    contains_play_meta_wrapper_text,
    has_language_contamination,
    has_second_person_reference,
    narration_sentence_count,
    sanitize_persisted_narration,
    visible_story_length,
)


_PROTAGONIST_ALIAS_STOPWORDS = {
    "the",
    "high",
    "steward",
    "councilor",
    "councillor",
    "archivist",
    "harbor",
    "inspector",
    "bridge",
    "engineer",
    "ombudsman",
    "envoy",
    "captain",
    "warden",
}

_PROTAGONIST_HONORIFIC_TOKENS = {
    "captain",
    "chancellor",
    "councilor",
    "councillor",
    "doctor",
    "dr",
    "inspector",
    "keeper",
    "lord",
    "lady",
    "mayor",
}


@dataclass(frozen=True)
class RenderTurnResult:
    narration: str
    suggestions: list[PlaySuggestedAction]
    source: str
    primary_path_mode: str = "fallback"
    attempts: int = 0
    render_plan_stage1_success: bool = False
    render_plan_stage2_rescue: bool = False
    render_narration_stage1_success: bool = False
    render_narration_stage2_rescue: bool = False
    failure_reason: str | None = None
    response_id: str | None = None
    usage: dict[str, int | str] | None = None
    capability: str | None = None
    provider: str | None = None
    model: str | None = None
    transport_style: str | None = None
    render_primary_failure_reason: str | None = None
    render_primary_fallback_source: str | None = None
    render_primary_raw_excerpt: str | None = None
    render_quality_reason_before_repair: str | None = None
    render_repair_failure_reason: str | None = None
    render_repair_raw_excerpt: str | None = None
    skill_id: str | None = None
    skill_version: str | None = None
    contract_mode: str | None = None
    context_card_ids: list[str] | None = None
    context_packet_characters: int | None = None
    repair_mode: str | None = None


@dataclass(frozen=True)
class RenderPlanResult:
    plan: PlayRenderPlanDraft
    source: str
    attempts: int = 0
    stage1_success: bool = False
    stage2_rescue: bool = False
    failure_reason: str | None = None
    response_id: str | None = None
    usage: dict[str, int | str] | None = None
    capability: str | None = None
    provider: str | None = None
    model: str | None = None
    transport_style: str | None = None


def _response_skill_kwargs(response: object) -> dict[str, object]:
    return {
        "skill_id": getattr(response, "skill_id", None),
        "skill_version": getattr(response, "skill_version", None),
        "contract_mode": getattr(response, "contract_mode", None),
        "context_card_ids": list(getattr(response, "context_card_ids", []) or []),
        "context_packet_characters": getattr(response, "context_packet_characters", None),
        "repair_mode": getattr(response, "repair_mode", None),
    }


@dataclass
class RenderAttemptDiagnostics:
    render_primary_failure_reason: str | None = None
    render_primary_fallback_source: str | None = None
    render_primary_raw_excerpt: str | None = None
    render_quality_reason_before_repair: str | None = None
    render_repair_failure_reason: str | None = None
    render_repair_raw_excerpt: str | None = None


def _invoke_render_json(
    gateway: CapabilityGatewayCore,
    *,
    system_prompt: str,
    user_payload: dict[str, object],
    max_output_tokens: int | None,
    previous_response_id: str | None,
    operation_name: str,
    plaintext_fallback_key: str | None = None,
    override_plaintext_fallback_key: bool = False,
    allow_raw_text_passthrough: bool = False,
    skill_packet: GenerationSkillPacket | None = None,
):
    capability = "play.render_repair" if "repair" in operation_name else "play.render"
    return gateway.invoke_text_capability(
        capability,
        TextCapabilityRequest(
            system_prompt=system_prompt,
            user_payload=user_payload,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
            operation_name=operation_name,
            plaintext_fallback_key=plaintext_fallback_key,
            override_plaintext_fallback_key=override_plaintext_fallback_key,
            allow_raw_text_passthrough=allow_raw_text_passthrough,
            skill_id=skill_packet.skill_id if skill_packet is not None else None,
            skill_version=skill_packet.skill_version if skill_packet is not None else None,
            contract_mode=skill_packet.contract_mode if skill_packet is not None else None,
            context_card_ids=skill_packet.context_card_ids() if skill_packet is not None else [],
            context_packet_characters=skill_packet.context_packet_characters() if skill_packet is not None else len(json.dumps(user_payload, ensure_ascii=False, sort_keys=True)),
            repair_mode=skill_packet.repair_mode if skill_packet is not None else None,
        ),
    )


def _trace_excerpt(value: object | None, *, limit: int = 240) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return None
    return trim_ellipsis(normalized, limit)


def _response_trace_excerpt(response: object) -> str | None:
    raw_text = getattr(response, "raw_text", None)
    if raw_text:
        return _trace_excerpt(raw_text)
    payload = getattr(response, "payload", None)
    if isinstance(payload, dict) and isinstance(payload.get("narration"), str):
        return _trace_excerpt(payload.get("narration"))
    return _trace_excerpt(payload)


def _attach_render_attempt_diagnostics(
    result: RenderTurnResult,
    diagnostics: RenderAttemptDiagnostics,
) -> RenderTurnResult:
    return replace(
        result,
        render_primary_failure_reason=diagnostics.render_primary_failure_reason,
        render_primary_fallback_source=diagnostics.render_primary_fallback_source,
        render_primary_raw_excerpt=diagnostics.render_primary_raw_excerpt,
        render_quality_reason_before_repair=(
            diagnostics.render_quality_reason_before_repair
            if diagnostics.render_quality_reason_before_repair is not None
            else result.render_quality_reason_before_repair
        ),
        render_repair_failure_reason=diagnostics.render_repair_failure_reason,
        render_repair_raw_excerpt=diagnostics.render_repair_raw_excerpt,
    )


def _map_render_gateway_error_code(code: str) -> str:
    return {
        "gateway_text_provider_failed": "play_llm_provider_failed",
        "gateway_text_invalid_response": "play_llm_invalid_response",
        "gateway_text_invalid_json": "play_llm_invalid_json",
        "gateway_text_model_missing": "play_llm_config_missing",
        "gateway_text_config_missing": "play_llm_config_missing",
    }.get(code, code)


def _extract_render_plan_from_text(raw_text: str | None) -> PlayRenderPlanDraft | None:
    cleaned = strip_model_meta_wrapper_text(str(raw_text or "")).strip()
    if not cleaned:
        return None

    def _extract(patterns: tuple[str, ...]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, cleaned, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                return strip_model_meta_wrapper_text(match.group(1)).strip()
        return None

    scene_reaction = _extract((r'"?scene_reaction"?\s*[:=：]\s*"?(.*?)"?$', r"\bSCENE_REACTION\b\s*[:=：]\s*(.+)"))
    axis_payoff = _extract((r'"?axis_payoff"?\s*[:=：]\s*"?(.*?)"?$', r"\bAXIS_PAYOFF\b\s*[:=：]\s*(.+)"))
    stance_payoff = _extract((r'"?stance_payoff"?\s*[:=：]\s*"?(.*?)"?$', r"\bSTANCE_PAYOFF\b\s*[:=：]\s*(.+)"))
    immediate_consequence = _extract((r'"?immediate_consequence"?\s*[:=：]\s*"?(.*?)"?$', r"\bIMMEDIATE_CONSEQUENCE\b\s*[:=：]\s*(.+)"))
    closing_pressure = _extract((r'"?closing_pressure"?\s*[:=：]\s*"?(.*?)"?$', r"\bCLOSING_PRESSURE\b\s*[:=：]\s*(.+)"))
    if not all((scene_reaction, axis_payoff, immediate_consequence, closing_pressure)):
        return None
    return PlayRenderPlanDraft(
        scene_reaction=scene_reaction,
        axis_payoff=axis_payoff,
        stance_payoff=stance_payoff,
        immediate_consequence=immediate_consequence,
        closing_pressure=closing_pressure,
    )


def _deterministic_render_plan(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> PlayRenderPlanDraft:
    target_names = _render_target_summary(plan, resolution)
    if is_chinese_language(plan.language):
        target_clause = f"，并直接压向{'、'.join(target_names[:2])}" if target_names else ""
        scene_reaction = f"你把局面往前推进{target_clause}，会场当场有了反应。"
        axis_payoff = next(
            (
                f"你能感觉到{axis.label}{'上升' if delta > 0 else '缓和'}，众人的判断开始重新摆位。"
                for axis in plan.axes
                for axis_id, delta in resolution.axis_changes.items()
                if axis.axis_id == axis_id and delta != 0
            ),
            state.last_turn_consequences[0] if state.last_turn_consequences else "压力开始明显转向你刚刚逼出来的事实。",
        )
        stance_payoff = next(
            (
                f"{npc.name}{'对你更为强硬' if delta < 0 else '明显向你靠拢'}，这个变化当场就被所有人看见。"
                for stance_id, delta in resolution.stance_changes.items()
                if delta != 0
                for stance in plan.stances
                if stance.stance_id == stance_id
                for npc in plan.cast
                if npc.npc_id == stance.npc_id
            ),
            None,
        )
        immediate_consequence = state.last_turn_consequences[0] if state.last_turn_consequences else "后果立刻落地。"
        closing_pressure = (
            f"故事推进到“{plan.beats[state.beat_index].title}”，新的压力点已经浮出。"
            if state.status == "active"
            else f"结局被锁定为“{(state.ending.label if state.ending is not None else '最终定局')}”。"
        )
    else:
        target_clause = f" with {', '.join(target_names[:2])}" if target_names else ""
        scene_reaction = f"You keep the scene moving{target_clause} as the room reacts in real time."
        axis_payoff = next(
            (
                f"You can feel {axis.label.lower()} {'rise' if delta > 0 else 'ease'} as the room recalculates around your move."
                for axis in plan.axes
                for axis_id, delta in resolution.axis_changes.items()
                if axis.axis_id == axis_id and delta != 0
            ),
            state.last_turn_consequences[0] if state.last_turn_consequences else "The pressure visibly shifts around what you just forced into the open.",
        )
        stance_payoff = next(
            (
                f"{npc.name} {'hardens against you' if delta < 0 else 'edges closer to your side'}, and that shift is visible to everyone watching."
                for stance_id, delta in resolution.stance_changes.items()
                if delta != 0
                for stance in plan.stances
                if stance.stance_id == stance_id
                for npc in plan.cast
                if npc.npc_id == stance.npc_id
            ),
            None,
        )
        immediate_consequence = state.last_turn_consequences[0] if state.last_turn_consequences else "The consequence lands immediately."
        closing_pressure = (
            f"The story shifts into {plan.beats[state.beat_index].title.lower()}, and the next pressure point comes into focus."
            if state.status == "active"
            else f"The ending locks into {(state.ending.label if state.ending is not None else 'a hard conclusion').lower()}."
        )
    return PlayRenderPlanDraft(
        scene_reaction=trim_ellipsis(scene_reaction, 240),
        axis_payoff=trim_ellipsis(axis_payoff, 240),
        stance_payoff=trim_ellipsis(stance_payoff, 240) if stance_payoff else None,
        immediate_consequence=trim_ellipsis(immediate_consequence, 240),
        closing_pressure=trim_ellipsis(closing_pressure, 240),
    )


def _narration_from_response_payload(payload: object) -> str:
    if isinstance(payload, dict):
        return strip_model_meta_wrapper_text(str(payload.get("narration") or ""))
    if isinstance(payload, str):
        return strip_model_meta_wrapper_text(payload)
    return ""


def _sanitize_user_visible_narration(plan: PlayPlan, narration: str) -> str:
    return sanitize_persisted_narration(_sanitize_narration(plan, narration), language=plan.language)


def _coerce_wrapper_narration_to_scene_text(plan: PlayPlan, narration: str | None) -> str:
    candidate = str(narration or "")
    if not contains_play_meta_wrapper_text(candidate):
        return candidate
    render_plan = _extract_render_plan_from_text(candidate)
    if render_plan is None:
        return candidate
    return _render_plan_to_narration(plan, render_plan)


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def _contains_meta_wrapper_text(text: str | None) -> bool:
    return contains_play_meta_wrapper_text(text)


def _looks_like_consequence_slogan(text: str, state: PlaySessionState) -> bool:
    cleaned = strip_model_meta_wrapper_text(text)
    if _word_count(cleaned) >= 18:
        return False
    lowered = cleaned.casefold().strip().strip(".。！？!?")
    if not lowered:
        return True
    if state.last_turn_consequences and any(
        lowered == consequence.casefold().strip().strip(".。！？!?")
        for consequence in state.last_turn_consequences
        if consequence
    ):
        return True
    generic_stubs = {
        "proof moved into the open",
        "visible public pressure rose",
        "institutional strain rose",
        "the move came with procedural slippage",
        "at least one relationship took damage",
    }
    return lowered in generic_stubs


def _render_output_budget(
    *,
    gateway: CapabilityGatewayCore,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> int | None:
    budget = gateway.text_policy("play.render").max_output_tokens
    if state.status != "active" or resolution.ending_id is not None:
        cap = 220
    elif resolution.execution_frame in {"public", "coercive"} or len(state.last_turn_consequences) >= 3:
        cap = 220
    else:
        cap = 180
    if budget is None:
        return cap
    return min(int(budget), cap)


def _render_plan_output_budget(
    *,
    gateway: CapabilityGatewayCore,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> int | None:
    budget = gateway.text_policy("play.render").max_output_tokens
    cap = 220 if state.status != "active" or resolution.ending_id is not None else 180
    if budget is None:
        return cap
    return min(int(budget), cap)


def _render_repair_output_budget(
    *,
    gateway: CapabilityGatewayCore,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> int | None:
    budget = gateway.text_policy("play.render_repair").max_output_tokens
    if state.status != "active" or resolution.ending_id is not None:
        cap = 240
    elif resolution.execution_frame in {"public", "coercive"} or len(state.last_turn_consequences) >= 3:
        cap = 240
    else:
        cap = 200
    if budget is None:
        return cap
    return min(int(budget), cap)


def _render_plan_repair_output_budget(
    *,
    gateway: CapabilityGatewayCore,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> int | None:
    budget = gateway.text_policy("play.render_repair").max_output_tokens
    cap = 260 if state.status != "active" or resolution.ending_id is not None else 220
    if budget is None:
        return cap
    return min(int(budget), cap)


def _compact_consequence_lines(state: PlaySessionState) -> list[str]:
    return [trim_ellipsis(item, 96) for item in state.last_turn_consequences[:2] if item]


def _anchor_matches_language(value: str | None, *, language: str) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return False
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", cleaned))
    if is_chinese_language(language):
        return has_cjk
    return not has_cjk


def _required_payoff_anchors(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> list[str]:
    anchors: list[str] = []

    def _push(value: str | None, *, force: bool = False) -> None:
        cleaned = str(value or "").strip().strip("。.!?！？")
        if not cleaned:
            return
        if not force and not _anchor_matches_language(cleaned, language=plan.language):
            return
        if cleaned not in anchors:
            anchors.append(cleaned)

    for consequence in state.last_turn_consequences[:2]:
        _push(consequence)
    _push(resolution.pressure_note)
    for axis_id, delta in resolution.axis_changes.items():
        if delta == 0:
            continue
        axis = next((item for item in plan.axes if item.axis_id == axis_id), None)
        if axis is not None:
            _push(axis.label)
    for npc in plan.cast:
        if npc.npc_id in resolution.target_npc_ids and npc.npc_id != plan.protagonist_npc_id:
            _push(npc.name, force=True)
    return anchors[:6]


def _compact_resolution_payload(resolution: PlayResolutionEffect) -> dict[str, object]:
    return {
        "affordance_tag": resolution.affordance_tag,
        "risk_level": resolution.risk_level,
        "execution_frame": resolution.execution_frame,
        "tactic_summary": trim_ellipsis(resolution.tactic_summary, 120),
        "axis_changes": {key: value for key, value in resolution.axis_changes.items() if value},
        "stance_changes": {key: value for key, value in resolution.stance_changes.items() if value},
        "flag_changes": {key: value for key, value in resolution.flag_changes.items() if value},
        "revealed_truth_ids": list(resolution.revealed_truth_ids[:2]),
        "added_event_ids": list(resolution.added_event_ids[:2]),
        "beat_completed": resolution.beat_completed,
        "advanced_to_next_beat": resolution.advanced_to_next_beat,
        "ending_id": resolution.ending_id,
        "pressure_note": trim_ellipsis(resolution.pressure_note, 96),
    }


def _current_beat_runtime_shard(plan: PlayPlan, state: PlaySessionState):
    current_beat_id = plan.beats[state.beat_index].beat_id
    return next((item for item in list(plan.beat_runtime_shards or []) if item.beat_id == current_beat_id), None)


def _hint_card_content(cards: list[object], card_id: str) -> dict[str, object]:
    for item in cards:
        if getattr(item, "card_id", None) == card_id:
            return dict(getattr(item, "content", {}) or {})
    return {}


def _build_render_payload(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_prompt: str | None,
) -> dict[str, object]:
    beat = plan.beats[state.beat_index]
    payload: dict[str, object] = {
        "story_title": trim_ellipsis(plan.story_title, 80),
        "tone": trim_ellipsis(plan.tone, 80),
        "runtime_policy_profile": plan.runtime_policy_profile,
        "current_beat": {
            "title": trim_ellipsis(beat.title, 64),
            "goal": trim_ellipsis(beat.goal, 96),
        },
        "player_input": trim_ellipsis(input_text, 360),
        "selected_suggestion_prompt": trim_ellipsis(selected_prompt, 180) if selected_prompt else None,
        "resolution": _compact_resolution_payload(resolution),
        "last_turn_consequences": _compact_consequence_lines(state),
        "required_payoff_anchors": _required_payoff_anchors(
            plan=plan,
            state=state,
            resolution=resolution,
        ),
        "target_npcs": _render_target_summary(plan, resolution),
        "state_bars": _render_state_bar_summary(plan, state)[:4],
        "session_status": state.status,
    }
    return payload


def _direct_render_context_cards(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_prompt: str | None,
) -> tuple[ContextCard, ...]:
    beat = plan.beats[state.beat_index]
    shard = _current_beat_runtime_shard(plan, state)
    cards: list[ContextCard] = []
    if shard is not None:
        cards.append(
            ContextCard(
                "beat_runtime_shard_card",
                {
                    "beat_id": shard.beat_id,
                    "route_pivot_tag": shard.route_pivot_tag,
                    "required_truth_ids": list(shard.required_truth_ids),
                    "required_event_ids": list(shard.required_event_ids),
                    "affordance_tags": list(shard.affordance_tags),
                    "blocked_affordances": list(shard.blocked_affordances),
                    "render_hint_cards": [card.model_dump(mode="json") for card in shard.render_hint_cards],
                },
                priority=5,
            )
        )
    cards.extend(
        (
            ContextCard(
                "beat_card",
                {
                    "story_title": trim_ellipsis(plan.story_title, 80),
                    "tone": trim_ellipsis(plan.tone, 80),
                    "current_beat": {
                        "title": trim_ellipsis(beat.title, 64),
                        "goal": trim_ellipsis(beat.goal, 96),
                    },
                },
                priority=10,
            ),
            ContextCard(
                "resolution_card",
                {
                    "player_input": trim_ellipsis(input_text, 360),
                    "selected_suggestion_prompt": trim_ellipsis(selected_prompt, 180) if selected_prompt else None,
                    "resolution": _compact_resolution_payload(resolution),
                    "last_turn_consequences": _compact_consequence_lines(state),
                },
                priority=20,
            ),
            ContextCard(
                "required_payoff_anchor_card",
                {
                    "required_payoff_anchors": _required_payoff_anchors(
                        plan=plan,
                        state=state,
                        resolution=resolution,
                    )
                },
                priority=30,
            ),
            ContextCard(
                "target_npc_card",
                {"target_npcs": _render_target_summary(plan, resolution)},
                priority=40,
            ),
        )
    )
    return tuple(cards)


def _render_context_cards(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_prompt: str | None,
) -> tuple[ContextCard, ...]:
    beat = plan.beats[state.beat_index]
    shard = _current_beat_runtime_shard(plan, state)
    shard_render_card = _hint_card_content(list(getattr(shard, "render_hint_cards", []) or []), "anchor_card") if shard is not None else {}
    return (
        *(
            (
                ContextCard(
                    "beat_runtime_shard_card",
                    {
                        "beat_id": shard.beat_id,
                        "pressure_axis_id": shard.pressure_axis_id,
                        "required_truth_ids": list(shard.required_truth_ids),
                        "required_event_ids": list(shard.required_event_ids),
                        "route_pivot_tag": shard.route_pivot_tag,
                        "affordance_tags": list(shard.affordance_tags),
                        "blocked_affordances": list(shard.blocked_affordances),
                        "render_hint_cards": [card.model_dump(mode="json") for card in shard.render_hint_cards],
                    },
                    priority=5,
                ),
            )
            if shard is not None
            else ()
        ),
        ContextCard(
            "beat_card",
            {
                "story_title": trim_ellipsis(plan.story_title, 80),
                "tone": trim_ellipsis(plan.tone, 80),
                "runtime_policy_profile": plan.runtime_policy_profile,
                "current_beat": {
                    "title": trim_ellipsis(beat.title, 64),
                    "goal": trim_ellipsis(beat.goal, 96),
                },
            },
            priority=10,
        ),
        ContextCard(
            "resolution_card",
            {
                "player_input": trim_ellipsis(input_text, 360),
                "selected_suggestion_prompt": trim_ellipsis(selected_prompt, 180) if selected_prompt else None,
                "resolution": _compact_resolution_payload(resolution),
                "last_turn_consequences": _compact_consequence_lines(state),
            },
            priority=20,
        ),
        ContextCard(
            "required_payoff_anchor_card",
            {
                "required_payoff_anchors": _required_payoff_anchors(
                    plan=plan,
                    state=state,
                    resolution=resolution,
                )
            },
            priority=30,
        ),
        ContextCard(
            "target_npc_card",
            {"target_npcs": _render_target_summary(plan, resolution), **({"route_pivot_tag": shard_render_card.get("route_pivot_tag")} if shard_render_card.get("route_pivot_tag") else {})},
            priority=40,
        ),
        ContextCard(
            "state_bar_card",
            {"state_bars": _render_state_bar_summary(plan, state)[:4], "session_status": state.status},
            priority=50,
        ),
        ContextCard(
            "deterministic_fallback_plan_card",
            {
                "deterministic_render_plan": _deterministic_render_plan(
                    plan=plan,
                    state=state,
                    resolution=resolution,
                ).model_dump(mode="json")
            },
            priority=60,
        ),
    )


def _build_direct_render_skill_packet(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_prompt: str | None,
) -> GenerationSkillPacket:
    return _render_skill_packet(
        plan=plan,
        capability="play.render",
        skill_id="play.render.direct_narration",
        contract_mode="narration_prose",
        required_output_contract="Write clean second-person user-facing narration only.",
        task_brief=_render_narration_system_prompt(plan),
        context_cards=_direct_render_context_cards(
            plan=plan,
            state=state,
            resolution=resolution,
            input_text=input_text,
            selected_prompt=selected_prompt,
        ),
    )


def _render_skill_packet(
    *,
    plan: PlayPlan,
    capability: str,
    skill_id: str,
    contract_mode: str,
    required_output_contract: str,
    task_brief: str,
    context_cards: tuple[ContextCard, ...],
    repair_mode: str = "none",
    repair_note: str | None = None,
    final_contract_note: str | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> GenerationSkillPacket:
    role_style, _role_context = build_role_style_context(
        language=plan.language,
        en_role="a sharp interactive fiction GM",
        zh_role="擅长政治惊悚与程序性危机的中文互动小说主持人",
        include_ids_note=False,
    )
    return GenerationSkillPacket(
        skill_id=skill_id,
        skill_version="v1",
        capability=capability,
        contract_mode=contract_mode,  # type: ignore[arg-type]
        role_style=role_style,
        required_output_contract=required_output_contract,
        context_cards=context_cards,
        task_brief=task_brief,
        repair_mode=repair_mode,
        repair_note=repair_note,
        final_contract_note=final_contract_note,
        extra_payload=dict(extra_payload or {}),
    )


def _build_render_plan_payload(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_prompt: str | None,
) -> dict[str, object]:
    payload = _build_render_payload(
        plan=plan,
        state=state,
        resolution=resolution,
        input_text=input_text,
        selected_prompt=selected_prompt,
    )
    payload["deterministic_render_plan"] = _deterministic_render_plan(
        plan=plan,
        state=state,
        resolution=resolution,
    ).model_dump(mode="json")
    return payload


def _build_render_narration_payload(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_prompt: str | None,
    render_plan: PlayRenderPlanDraft,
) -> dict[str, object]:
    payload = _build_render_payload(
        plan=plan,
        state=state,
        resolution=resolution,
        input_text=input_text,
        selected_prompt=selected_prompt,
    )
    payload["render_plan"] = render_plan.model_dump(mode="json")
    return payload


def _build_render_plan_skill_packet(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_prompt: str | None,
    capability: str,
    skill_id: str,
    repair_mode: str = "none",
    failure_reason: str | None = None,
    draft_narration: str | None = None,
    draft_suggestions: list[PlaySuggestedAction] | None = None,
) -> GenerationSkillPacket:
    cards = list(
        _render_context_cards(
            plan=plan,
            state=state,
            resolution=resolution,
            input_text=input_text,
            selected_prompt=selected_prompt,
        )
    )
    if failure_reason is not None:
        cards.append(ContextCard("repair_note_card", {"failure_reason": failure_reason}, priority=70))
    if draft_narration:
        cards.append(ContextCard("draft_narration_card", {"draft_narration": draft_narration}, priority=80))
    if draft_suggestions:
        cards.append(
            ContextCard(
                "draft_suggestion_card",
                {"draft_suggestions": [item.model_dump(mode="json") for item in draft_suggestions]},
                priority=90,
            )
        )
    return _render_skill_packet(
        plan=plan,
        capability=capability,
        skill_id=skill_id,
        contract_mode="strict_json_schema",
        required_output_contract="Return exactly one PlayRenderPlanDraft JSON object.",
        task_brief=_render_plan_system_prompt(plan),
        context_cards=tuple(cards),
        repair_mode=repair_mode,
        repair_note="Repair the previous invalid plan while preserving the same strict JSON contract." if repair_mode != "none" else None,
        final_contract_note="Return raw JSON only. Exactly one PlayRenderPlanDraft object. No markdown. No labels outside JSON." if repair_mode != "none" else None,
        extra_payload=_build_render_plan_payload(
            plan=plan,
            state=state,
            resolution=resolution,
            input_text=input_text,
            selected_prompt=selected_prompt,
        ) if repair_mode == "none" else {
            "failure_reason": failure_reason,
            **_build_render_plan_payload(
                plan=plan,
                state=state,
                resolution=resolution,
                input_text=input_text,
                selected_prompt=selected_prompt,
            ),
            "draft_narration": draft_narration,
            "draft_suggestions": [item.model_dump(mode="json") for item in (draft_suggestions or [])],
        },
    )


def _build_render_narration_skill_packet(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_prompt: str | None,
    render_plan: PlayRenderPlanDraft,
    capability: str,
    skill_id: str,
    repair_mode: str = "none",
    failure_reason: str | None = None,
) -> GenerationSkillPacket:
    cards = list(
        _render_context_cards(
            plan=plan,
            state=state,
            resolution=resolution,
            input_text=input_text,
            selected_prompt=selected_prompt,
        )
    )
    cards.append(ContextCard("render_plan_card", render_plan.model_dump(mode="json"), priority=70))
    if failure_reason is not None:
        cards.append(ContextCard("repair_note_card", {"failure_reason": failure_reason}, priority=80))
    return _render_skill_packet(
        plan=plan,
        capability=capability,
        skill_id=skill_id,
        contract_mode="narration_prose",
        required_output_contract="Write clean second-person user-facing narration only.",
        task_brief=_render_narration_system_prompt(plan),
        context_cards=tuple(cards),
        repair_mode=repair_mode,
        repair_note="Repair the narration while preserving the same scene payoff and at least one required anchor." if repair_mode != "none" else None,
        final_contract_note="Return narration only. No JSON, no labels, no markdown." if repair_mode != "none" else None,
        extra_payload=_build_render_narration_payload(
            plan=plan,
            state=state,
            resolution=resolution,
            input_text=input_text,
            selected_prompt=selected_prompt,
            render_plan=render_plan,
        ),
    )


def _build_render_glean_skill_packet(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    failure_reason: str,
    bad_narration: str | None,
) -> GenerationSkillPacket:
    cards = [
        ContextCard(
            "deterministic_fallback_plan_card",
            {
                "deterministic_render_plan": _deterministic_render_plan(
                    plan=plan,
                    state=state,
                    resolution=resolution,
                ).model_dump(mode="json")
            },
            priority=10,
        ),
        ContextCard("required_payoff_anchor_card", {"required_payoff_anchors": _required_payoff_anchors(plan=plan, state=state, resolution=resolution)}, priority=20),
        ContextCard("target_npc_card", {"target_npcs": _render_target_summary(plan, resolution)}, priority=30),
        ContextCard("bad_narration_card", {"failure_reason": failure_reason, "bad_narration": bad_narration}, priority=40),
    ]
    return _render_skill_packet(
        plan=plan,
        capability="play.render_repair",
        skill_id="play.render.glean",
        contract_mode="narration_prose",
        required_output_contract="Write clean second-person salvage narration only.",
        task_brief=_render_glean_system_prompt(plan),
        context_cards=tuple(cards),
        repair_mode="bounded_salvage",
        extra_payload={
            "failure_reason": failure_reason,
            "bad_narration": bad_narration,
            "deterministic_render_plan": _deterministic_render_plan(
                plan=plan,
                state=state,
                resolution=resolution,
            ).model_dump(mode="json"),
            "last_turn_consequences": _compact_consequence_lines(state),
            "required_payoff_anchors": _required_payoff_anchors(
                plan=plan,
                state=state,
                resolution=resolution,
            ),
            "target_npcs": _render_target_summary(plan, resolution),
        },
    )

def _render_state_bar_summary(plan: PlayPlan, state: PlaySessionState) -> list[dict[str, int | str]]:
    summary = []
    for bar in build_session_snapshot(plan, state).state_bars:
        if bar.category == "axis" and bar.current_value != 0:
            summary.append({"label": bar.label, "value": bar.current_value})
        elif bar.category == "stance" and abs(bar.current_value) >= 1:
            summary.append({"label": bar.label, "value": bar.current_value})
    return summary[:6]


def _render_target_summary(plan: PlayPlan, resolution: PlayResolutionEffect) -> list[str]:
    if not resolution.target_npc_ids:
        return []
    return [
        npc.name
        for npc in plan.cast
        if npc.npc_id in resolution.target_npc_ids and npc.npc_id != plan.protagonist_npc_id
    ][:3]


def _render_plan_system_prompt(plan: PlayPlan) -> str:
    _role_style, role_context = build_role_style_context(
        language=plan.language,
        en_role="a sharp interactive fiction GM",
        zh_role="擅长政治惊悚与程序性危机的中文互动小说主持人",
        include_ids_note=False,
    )
    return (
        "You are planning the visible scene payoff for a second-person dramatic GM turn. "
        "Return one strict JSON object matching PlayRenderPlanDraft with keys "
        "scene_reaction, axis_payoff, stance_payoff, immediate_consequence, closing_pressure. "
        "Do not output markdown. Do not output labels outside JSON. "
        "Each field should be one short concrete line. "
        "Use at least one item from required_payoff_anchors explicitly in the plan when anchors are provided. "
        "Do not replace the anchors with generic payoff language. "
        f"{role_context}"
    )


def _render_narration_system_prompt(plan: PlayPlan) -> str:
    _role_style, role_context = build_role_style_context(
        language=plan.language,
        en_role="a sharp interactive fiction GM",
        zh_role="擅长政治惊悚与程序性危机的中文互动小说主持人",
        include_ids_note=False,
    )
    return (
        "You are a second-person GM for a dramatic short-form story game. "
        "Do not return JSON. Write 3-4 sentences of narration using the provided render plan. "
        "Narration must be second person, vivid, and must realize the scene reaction, axis payoff, immediate consequence, and closing pressure. "
        "If required_payoff_anchors is non-empty, the narration must explicitly realize at least one anchor in user-facing prose. "
        "If stance_payoff is present, include it naturally. "
        "Never refer to the protagonist by proper name or third-person pronouns. "
        f"{role_context}"
    )


def _protagonist_aliases(plan: PlayPlan) -> list[str]:
    protagonist_name = (plan.protagonist_name or "").strip()
    if not protagonist_name:
        aliases: list[str] = []
    else:
        aliases = [protagonist_name]
    name_tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", protagonist_name)
    if len(name_tokens) >= 2:
        aliases.append(" ".join(name_tokens[-2:]))
    if len(name_tokens) >= 3:
        aliases.append(" ".join(name_tokens[1:]))
    surname = name_tokens[-1] if name_tokens else ""
    if surname:
        aliases.append(surname)
    if len(name_tokens) >= 3 and name_tokens[0].casefold().rstrip(".") in _PROTAGONIST_HONORIFIC_TOKENS:
        aliases.append(f"{name_tokens[0]} {surname}")
    title = (plan.protagonist.title or "").strip()
    other_name_tokens = {
        token.casefold()
        for npc in plan.cast
        if npc.npc_id != plan.protagonist_npc_id
        for token in re.findall(r"[A-Za-z][A-Za-z'-]+", npc.name)
    }
    title_phrase = f"the {title.lower()}" if title else ""
    title_in_other_roles = any(
        title
        and npc.npc_id != plan.protagonist_npc_id
        and title.casefold() in (npc.role or "").casefold()
        for npc in plan.cast
    )
    if title_phrase and not title_in_other_roles:
        aliases.append(title_phrase)
    if title and surname and title.casefold() not in _PROTAGONIST_ALIAS_STOPWORDS:
        aliases.append(f"{title} {surname}")
    for token in name_tokens:
        lowered = token.casefold()
        if len(token) < 4 or lowered in _PROTAGONIST_ALIAS_STOPWORDS:
            continue
        if lowered in other_name_tokens and token != surname:
            continue
        aliases.append(token)
    seen: set[str] = set()
    ordered: list[str] = []
    for alias in sorted(aliases, key=len, reverse=True):
        lowered = alias.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(alias)
    return ordered


def _text_mentions_protagonist(plan: PlayPlan, text: str) -> bool:
    if not text.strip():
        return False
    for alias in _protagonist_aliases(plan):
        if re.search(rf"\b{re.escape(alias)}(?:'s)?\b", text, flags=re.IGNORECASE):
            return True
    return False


def _sanitize_narration(plan: PlayPlan, narration: str) -> str:
    text = trim_ellipsis(narration, 4000)
    aliases = _protagonist_aliases(plan)
    if aliases:
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        sentence_pattern = re.compile(
            rf"([^.!?]*\b(?:{alias_pattern})(?:'s)?\b[^.!?]*[.!?]?)",
            flags=re.IGNORECASE,
        )

        def _rewrite_sentence(match: re.Match[str]) -> str:
            updated = match.group(0)
            for alias in aliases:
                updated = re.sub(rf"\b{re.escape(alias)}'s\b", "your", updated, flags=re.IGNORECASE)
                updated = re.sub(rf"\b{re.escape(alias)}\b", "you", updated, flags=re.IGNORECASE)
            updated = re.sub(
                r"\b(?:his|her)\s+(voice|hand|hands|gaze|eyes|mouth|jaw|face|shoulder|shoulders)\b",
                r"your \1",
                updated,
                flags=re.IGNORECASE,
            )
            verb_map = {
                "is": "are",
                "was": "were",
                "has": "have",
                "does": "do",
                "steps": "step",
                "turns": "turn",
                "moves": "move",
                "forces": "force",
                "orders": "order",
                "brings": "bring",
                "takes": "take",
                "holds": "hold",
                "keeps": "keep",
                "speaks": "speak",
                "asks": "ask",
                "tries": "try",
                "works": "work",
                "leans": "lean",
                "watches": "watch",
                "stands": "stand",
                "stares": "stare",
                "knows": "know",
                "realizes": "realize",
                "narrows": "narrow",
                "seethes": "seethe",
                "glances": "glance",
            }
            for singular, base in verb_map.items():
                updated = re.sub(rf"\byou\s+{singular}\b", f"you {base}", updated, flags=re.IGNORECASE)
            updated = re.sub(r"\b(?:the|a|an)\s+you\b", "you", updated, flags=re.IGNORECASE)
            updated = re.sub(
                r"\b(?:councilor|councillor|high steward|steward|captain|warden)\s+you\b",
                "you",
                updated,
                flags=re.IGNORECASE,
            )
            return updated

        text = sentence_pattern.sub(_rewrite_sentence, text)
    text = re.sub(r"\byou's\b", "your", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(^|[.!?]\s+)(you|your)\b",
        lambda match: f"{match.group(1)}{match.group(2).capitalize()}",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _has_protagonist_grammar_issue(narration: str) -> bool:
    lowered = narration.casefold()
    grammar_patterns = (
        r"\byou\s+(?:is|was|has|does|steps|turns|moves|forces|orders|brings|takes|holds|keeps|speaks|asks|tries|works|leans|watches|stands|stares|knows|realizes|narrows|seethes|glances)\b",
        r"\byou\b[^.!?]{0,40}\b(?:his|her)\s+(?:voice|hand|hands|gaze|eyes|mouth|jaw|face|shoulder|shoulders)\b",
        r"\byour\s+(?:voice|hand|hands|gaze|eyes|mouth|jaw|face|shoulder|shoulders)\b[^.!?]{0,60}\b(?:as|while)\s+(?:he|she|they)\s+\w+\b",
    )
    return any(re.search(pattern, lowered) for pattern in grammar_patterns)


def _suggestions_target_protagonist(plan: PlayPlan, suggestions: list[PlaySuggestedAction]) -> bool:
    for item in suggestions:
        if _text_mentions_protagonist(plan, f"{item.label} {item.prompt}"):
            return True
    return False


def _sanitize_suggestions_or_fallback(
    plan: PlayPlan,
    state: PlaySessionState,
    suggestions: list[PlaySuggestedAction],
) -> list[PlaySuggestedAction]:
    if state.status != "active":
        return []
    if _suggestions_target_protagonist(plan, suggestions):
        return build_suggested_actions(plan, state)
    labels = [item.label.casefold().strip() for item in suggestions]
    prompts = [item.prompt.casefold().strip() for item in suggestions]
    if len(set(labels)) != len(labels) or len(set(prompts)) != len(prompts):
        return build_suggested_actions(plan, state)
    return suggestions


def deterministic_render(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> RenderTurnResult:
    narration = _sanitize_user_visible_narration(
        plan,
        deterministic_narration(plan=plan, state=state, resolution=resolution),
    )
    suggestions = [] if state.status != "active" else build_suggested_actions(plan, state)
    return RenderTurnResult(
        narration=narration,
        suggestions=suggestions,
        source="fallback",
        primary_path_mode="fallback",
        attempts=0,
    )


def render_quality_reason(
    plan: PlayPlan,
    narration: str,
    suggestions: list[PlaySuggestedAction],
) -> str | None:
    normalized = sanitize_persisted_narration(narration, language=plan.language)
    lowered = normalized.casefold()
    if has_language_contamination(normalized, plan.language):
        return "language_contamination"
    if not has_second_person_reference(normalized, plan.language):
        return "missing_second_person"
    if not is_chinese_language(plan.language) and normalized.startswith("You act through"):
        return "deterministic_fallback_style"
    if is_chinese_language(plan.language):
        if visible_story_length(normalized, plan.language) < 36 and narration_sentence_count(normalized) < 2:
            return "narration_too_short"
    elif len(normalized.strip()) < 100:
        return "narration_too_short"
    labels = [item.label.casefold().strip() for item in suggestions]
    prompts = [item.prompt.casefold().strip() for item in suggestions]
    if len(set(labels)) != len(labels) or len(set(prompts)) != len(prompts):
        return "duplicate_suggestions"
    return None


def _render_failure_reason(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    narration: str,
    suggestions: list[PlaySuggestedAction],
    raw_text: str | None,
) -> str | None:
    if _contains_meta_wrapper_text(raw_text):
        wrapper_followup_reason = render_quality_reason(plan, narration, suggestions)
        if _looks_like_consequence_slogan(narration, state) or wrapper_followup_reason in {"missing_second_person", "narration_too_short", "language_contamination"}:
            return "meta_wrapper_echo"
    if _contains_meta_wrapper_text(narration):
        return "meta_wrapper_echo"
    if has_language_contamination(narration, plan.language):
        return "language_contamination"
    if _text_mentions_protagonist(plan, narration):
        return "named_protagonist_narration"
    if _has_protagonist_grammar_issue(narration):
        return "third_person_protagonist_grammar"
    payoff_reason = state_payoff_quality_reason(
        plan=plan,
        state=state,
        resolution=resolution,
        narration=narration,
    )
    if payoff_reason is not None:
        return payoff_reason
    if _looks_like_consequence_slogan(narration, state):
        return "slogan_only_payoff"
    return render_quality_reason(plan, narration, suggestions)


def _state_payoff_terms(plan: PlayPlan, state: PlaySessionState, resolution: PlayResolutionEffect) -> set[str]:
    if is_chinese_language(plan.language):
        return _state_payoff_terms_zh(plan, state, resolution)
    terms: set[str] = set()
    if resolution.affordance_tag == "reveal_truth":
        terms.update({"truth", "fact", "evidence", "proof", "ledger", "record", "open"})
    elif resolution.affordance_tag == "secure_resources":
        terms.update({"supply", "grain", "shipment", "ration", "dock", "harbor", "bridge"})
    elif resolution.affordance_tag in {"build_trust", "unlock_ally"}:
        terms.update({"ally", "coalition", "trust", "agreement", "backs"})
    elif resolution.affordance_tag == "shift_public_narrative":
        terms.update({"public", "speech", "mandate", "authority", "story"})
    for axis_id, delta in resolution.axis_changes.items():
        if delta == 0:
            continue
        axis = next((item for item in plan.axes if item.axis_id == axis_id), None)
        if axis is not None:
            for token in re.findall(r"[a-z]{4,}", axis.label.casefold()):
                terms.add(token)
        if axis_id == "public_panic":
            terms.update({"public", "panic", "crowd", "street"})
        elif axis_id == "political_leverage":
            terms.update({"vote", "mandate", "authority", "council", "leverage"})
        elif axis_id == "system_integrity":
            terms.update({"record", "archive", "seal", "procedure", "charter"})
        elif axis_id == "resource_strain":
            terms.update({"grain", "supply", "shipment", "ration", "dock", "bridge", "harbor"})
        elif axis_id == "exposure_risk":
            terms.update({"evidence", "proof", "ledger", "witness", "exposed"})
    if any(delta != 0 for delta in resolution.stance_changes.values()):
        terms.update({"ally", "coalition", "trust", "backs", "turns"})
    for consequence in state.last_turn_consequences:
        for token in re.findall(r"[a-z]{5,}", consequence.casefold()):
            terms.add(token)
    for token in re.findall(r"[a-z]{5,}", resolution.pressure_note.casefold()):
        terms.add(token)
    for npc in plan.cast:
        if npc.npc_id not in resolution.target_npc_ids:
            continue
        for token in re.findall(r"[a-z]{3,}", npc.name.casefold()):
            terms.add(token)
    return terms


def _state_payoff_terms_zh(plan: PlayPlan, state: PlaySessionState, resolution: PlayResolutionEffect) -> set[str]:
    terms: set[str] = set()
    for consequence in state.last_turn_consequences:
        cleaned = str(consequence or "").strip().strip("。！？.!?")
        if len(cleaned) >= 2:
            terms.add(cleaned)
        for fragment in re.split(r"[，、；：,\s]+", cleaned):
            normalized = fragment.strip().strip("。！？.!?")
            if len(normalized) >= 2:
                terms.add(normalized)
    pressure_note = str(resolution.pressure_note or "").strip().strip("。！？.!?")
    if len(pressure_note) >= 2 and _anchor_matches_language(pressure_note, language=plan.language):
        terms.add(pressure_note)
        for fragment in re.split(r"[，、；：,\s]+", pressure_note):
            normalized = fragment.strip().strip("。！？.!?")
            if len(normalized) >= 2:
                terms.add(normalized)
    for axis_id, delta in resolution.axis_changes.items():
        if delta == 0:
            continue
        axis = next((item for item in plan.axes if item.axis_id == axis_id), None)
        if axis is None:
            continue
        cleaned_label = str(axis.label or "").strip()
        if len(cleaned_label) >= 2:
            terms.add(cleaned_label)
        for fragment in re.split(r"[，、；：,\s]+", cleaned_label):
            normalized = fragment.strip().strip("。！？.!?")
            if len(normalized) >= 2:
                terms.add(normalized)
    for npc in plan.cast:
        if npc.npc_id in resolution.target_npc_ids and npc.name.strip():
            terms.add(npc.name.strip())
    return terms


def state_payoff_quality_reason(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    narration: str,
) -> str | None:
    if not (resolution.axis_changes or resolution.stance_changes or state.last_turn_consequences):
        return None
    lowered = narration.casefold()
    payoff_terms = _state_payoff_terms(plan, state, resolution)
    if is_chinese_language(plan.language):
        if payoff_terms and not any(term in narration for term in payoff_terms):
            return "missing_state_payoff"
        generic_markers = (
            "局面继续向前推进",
            "新的压力点已经浮出",
            "压力开始明显转向",
        )
        if any(marker in narration for marker in generic_markers) and visible_story_length(narration, plan.language) < 80:
            return "generic_feedback_echo"
        return None
    if payoff_terms and not any(term in lowered for term in payoff_terms):
        return "missing_state_payoff"
    generic_markers = (
        "the situation bends, but it does not stall",
        "you force the issue and raise the temperature",
        "the next pressure point comes into focus",
    )
    if any(marker in lowered for marker in generic_markers) and len(narration.strip()) < 180:
        return "generic_feedback_echo"
    return None


def _auto_repair_narration(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    narration: str,
    failure_reason: str,
) -> str | None:
    candidate = _sanitize_user_visible_narration(plan, narration)
    if failure_reason in {"missing_second_person", "third_person_protagonist_grammar", "language_contamination"}:
        if is_chinese_language(plan.language):
            if not has_second_person_reference(candidate, plan.language):
                stitched = candidate.strip().lstrip("，。！？.!? ")
                if stitched:
                    candidate = trim_ellipsis(f"你当场把局势往前推了一步。{stitched}", 4000)
            candidate = sanitize_persisted_narration(candidate, language=plan.language)
            if has_second_person_reference(candidate, plan.language) and not has_language_contamination(candidate, plan.language):
                return candidate
        else:
            lowered = candidate.casefold()
            if " you " not in f" {lowered} " and not lowered.startswith("you "):
                stitched = candidate[0].lower() + candidate[1:] if candidate else ""
                candidate = trim_ellipsis(f"You feel the room change as {stitched}", 4000)
                lowered = candidate.casefold()
            if " you " in f" {lowered} " or lowered.startswith("you "):
                return candidate
    if failure_reason in {"missing_state_payoff", "generic_feedback_echo", "meta_wrapper_echo", "narration_too_short", "slogan_only_payoff", "scene_plan_missing"}:
        if state.last_turn_consequences:
            payoff_line = state.last_turn_consequences[0].rstrip(".。！？!?")
            if payoff_line and payoff_line.casefold() not in candidate.casefold():
                sentence_end = "。" if is_chinese_language(plan.language) else "."
                candidate = trim_ellipsis(f"{candidate.rstrip('。.!?！？')} {payoff_line}{sentence_end}", 4000)
        if (
            (is_chinese_language(plan.language) and visible_story_length(candidate, plan.language) < 48)
            or (not is_chinese_language(plan.language) and _word_count(candidate) < 30)
        ):
            target_names = _render_target_summary(plan, resolution)
            if is_chinese_language(plan.language):
                target_clause = f"，并直接压向{'、'.join(target_names)}" if target_names else ""
                candidate = trim_ellipsis(
                    f"你逼着场面继续向前推进{target_clause}。{candidate.rstrip('。.!?')}。压力已经顺着你刚刚撬开的裂口扩散开来。",
                    4000,
                )
            else:
                target_clause = f" with {', '.join(target_names)}" if target_names else ""
                candidate = trim_ellipsis(
                    f"You keep the scene moving{target_clause} as the room reacts in real time. {candidate.rstrip('.')}."
                    f" The pressure visibly shifts around what you just forced into the open.",
                    4000,
                )
        candidate = sanitize_persisted_narration(candidate, language=plan.language)
        if state_payoff_quality_reason(
            plan=plan,
            state=state,
            resolution=resolution,
            narration=candidate,
        ) is None and not _looks_like_consequence_slogan(candidate, state) and not has_language_contamination(candidate, plan.language):
            return candidate
    return None


def _render_plan_to_narration(plan: PlayPlan, render_plan: PlayRenderPlanDraft) -> str:
    lines = [render_plan.scene_reaction, render_plan.axis_payoff]
    if render_plan.stance_payoff:
        lines.append(render_plan.stance_payoff)
    lines.append(render_plan.immediate_consequence)
    lines.append(render_plan.closing_pressure)
    sentence_end = "。" if is_chinese_language(plan.language) else "."
    return trim_ellipsis(" ".join(line.rstrip("。.!?！？") + sentence_end for line in lines if line), 4000)


def _render_glean_system_prompt(plan: PlayPlan) -> str:
    _role_style, role_context = build_role_style_context(
        language=plan.language,
        en_role="a sharp interactive fiction GM",
        zh_role="擅长政治惊悚与程序性危机的中文互动小说主持人",
        include_ids_note=False,
    )
    return (
        "You are salvaging a failed GM narration for an interactive story game. "
        "Do not return JSON. Do not return labels. Do not echo SCENE_REACTION, AXIS_PAYOFF, STANCE_PAYOFF, IMMEDIATE_CONSEQUENCE, or CLOSING_PRESSURE. "
        "Write 3-5 sentences of clean second-person narration that preserve the visible state change and immediate consequence. "
        "If required_payoff_anchors is non-empty, explicitly realize at least one anchor in the salvage narration. "
        "It is acceptable to be plain and functional as long as the narration is user-facing and readable. "
        f"{role_context}"
    )


def glean_render_turn(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    gateway: CapabilityGatewayCore,
    previous_response_id: str | None,
    failure_reason: str,
    bad_narration: str | None,
    active_suggestions: list[PlaySuggestedAction],
    attempts: int,
) -> RenderTurnResult | None:
    skill_packet = _build_render_glean_skill_packet(
        plan=plan,
        state=state,
        resolution=resolution,
        failure_reason=failure_reason,
        bad_narration=bad_narration,
    )
    try:
        response = _invoke_render_json(
            gateway,
            system_prompt=skill_packet.build_system_prompt(variant="normal"),
            user_payload=skill_packet.context_payload(),
            max_output_tokens=_render_repair_output_budget(
                gateway=gateway,
                state=state,
                resolution=resolution,
            ),
            previous_response_id=previous_response_id,
            operation_name="play_render_glean_repair",
            plaintext_fallback_key="narration",
            override_plaintext_fallback_key=True,
            skill_packet=skill_packet,
        )
    except (GatewayCapabilityError, PlayGatewayError, ValidationError):
        return None

    narration_text = _narration_from_response_payload(response.payload) or getattr(response, "raw_text", None) or ""
    narration_text = _coerce_wrapper_narration_to_scene_text(plan, narration_text)
    narration = _sanitize_user_visible_narration(plan, narration_text)
    if not narration:
        return None
    quality_reason = _render_failure_reason(
        plan=plan,
        state=state,
        resolution=resolution,
        narration=narration,
        suggestions=active_suggestions,
        raw_text=getattr(response, "raw_text", None),
    )
    if quality_reason:
        auto_repaired = _auto_repair_narration(
            plan=plan,
            state=state,
            resolution=resolution,
            narration=narration,
            failure_reason=quality_reason,
        )
        if auto_repaired is None:
            return None
        repaired_reason = _render_failure_reason(
            plan=plan,
            state=state,
            resolution=resolution,
            narration=auto_repaired,
            suggestions=active_suggestions,
            raw_text=auto_repaired,
        )
        if repaired_reason is not None:
            return None
        narration = auto_repaired
    return RenderTurnResult(
        narration=narration,
        suggestions=active_suggestions,
        source="llm_repair",
        primary_path_mode="plan_repair",
        attempts=attempts,
        render_plan_stage2_rescue=True,
        render_narration_stage2_rescue=True,
        failure_reason=failure_reason,
        response_id=response.response_id,
        usage=response.usage,
        capability=response.capability,
        provider=response.provider,
        model=response.model,
        transport_style=response.transport_style,
        **_response_skill_kwargs(response),
    )


def _render_direct_narration_result(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    response,
    attempts: int,
    source: str,
    failure_reason: str | None,
    active_suggestions: list[PlaySuggestedAction],
) -> RenderTurnResult | None:
    raw_narration = getattr(response, "raw_text", None) or _narration_from_response_payload(response.payload)
    narration_text = _narration_from_response_payload(response.payload) or strip_model_meta_wrapper_text(raw_narration)
    narration_text = _coerce_wrapper_narration_to_scene_text(plan, narration_text)
    narration = _sanitize_user_visible_narration(plan, narration_text)
    if not narration:
        return None
    quality_reason = _render_failure_reason(
        plan=plan,
        state=state,
        resolution=resolution,
        narration=narration,
        suggestions=active_suggestions,
        raw_text=raw_narration,
    )
    if quality_reason:
        auto_repaired = _auto_repair_narration(
            plan=plan,
            state=state,
            resolution=resolution,
            narration=narration,
            failure_reason=quality_reason,
        )
        if auto_repaired is not None:
            return RenderTurnResult(
                narration=auto_repaired,
                suggestions=active_suggestions,
                source="llm_repair",
                primary_path_mode="direct_repair",
                attempts=attempts,
                render_plan_stage1_success=False,
                render_plan_stage2_rescue=False,
                render_narration_stage1_success=True,
                render_narration_stage2_rescue=source == "llm_repair",
                failure_reason=quality_reason if source == "llm" else failure_reason,
                render_quality_reason_before_repair=quality_reason,
                response_id=response.response_id,
                usage=response.usage,
                capability=response.capability,
                provider=response.provider,
                model=response.model,
                transport_style=response.transport_style,
                **_response_skill_kwargs(response),
            )
        return None
    return RenderTurnResult(
        narration=narration,
        suggestions=active_suggestions,
        source=source,
        primary_path_mode="direct_narration" if source == "llm" else "direct_repair",
        attempts=attempts,
        render_plan_stage1_success=False,
        render_plan_stage2_rescue=False,
        render_narration_stage1_success=True,
        render_narration_stage2_rescue=source == "llm_repair",
        failure_reason=failure_reason,
        response_id=response.response_id,
        usage=response.usage,
        capability=response.capability,
        provider=response.provider,
        model=response.model,
        transport_style=response.transport_style,
        **_response_skill_kwargs(response),
    )


def _direct_narration_failure_reason(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    response,
    active_suggestions: list[PlaySuggestedAction],
) -> str | None:
    raw_narration = getattr(response, "raw_text", None) or _narration_from_response_payload(response.payload)
    narration_text = _narration_from_response_payload(response.payload) or strip_model_meta_wrapper_text(raw_narration)
    narration_text = _coerce_wrapper_narration_to_scene_text(plan, narration_text)
    narration = _sanitize_user_visible_narration(plan, narration_text)
    if not narration:
        return None
    return _render_failure_reason(
        plan=plan,
        state=state,
        resolution=resolution,
        narration=narration,
        suggestions=active_suggestions,
        raw_text=raw_narration,
    )


def repair_render_turn(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_action: PlaySuggestedAction | None,
    gateway: CapabilityGatewayCore,
    previous_response_id: str | None,
    failure_reason: str,
    draft_narration: str | None,
    draft_suggestions: list[PlaySuggestedAction] | None,
    diagnostics: RenderAttemptDiagnostics | None = None,
) -> RenderTurnResult | None:
    diagnostics = diagnostics or RenderAttemptDiagnostics()
    selected_prompt = selected_action.prompt if selected_action is not None else None
    narration_repair_packet = _render_skill_packet(
        plan=plan,
        capability="play.render_repair",
        skill_id="play.render.repair.direct_narration",
        contract_mode="narration_prose",
        required_output_contract="Write clean second-person narration only.",
        task_brief=_render_narration_system_prompt(plan),
        context_cards=_render_context_cards(
            plan=plan,
            state=state,
            resolution=resolution,
            input_text=input_text,
            selected_prompt=selected_prompt,
        ),
        repair_mode="anchor_repair",
        repair_note="Repair the failed narration and explicitly realize at least one required payoff anchor.",
        final_contract_note="Return narration only. No JSON, no labels, no markdown.",
        extra_payload={
            "failure_reason": failure_reason,
            **_build_render_plan_payload(
                plan=plan,
                state=state,
                resolution=resolution,
                input_text=input_text,
                selected_prompt=selected_prompt,
            ),
            "draft_narration": draft_narration,
            "draft_suggestions": [item.model_dump(mode="json") for item in (draft_suggestions or [])],
        },
    )
    try:
        response = _invoke_render_json(
            gateway,
            system_prompt=narration_repair_packet.build_system_prompt(variant="repair"),
            user_payload=narration_repair_packet.context_payload(),
            max_output_tokens=_render_repair_output_budget(
                gateway=gateway,
                state=state,
                resolution=resolution,
            ),
            previous_response_id=previous_response_id,
            operation_name="play_render_repair",
            plaintext_fallback_key="narration",
            override_plaintext_fallback_key=True,
            skill_packet=narration_repair_packet,
        )
        diagnostics.render_repair_raw_excerpt = _response_trace_excerpt(response)
        active_suggestions = [] if state.status != "active" else build_suggested_actions(plan, state)
        direct = _render_direct_narration_result(
            plan=plan,
            state=state,
            resolution=resolution,
            response=response,
            attempts=2,
            source="llm_repair",
            failure_reason=failure_reason,
            active_suggestions=active_suggestions,
        )
        if direct is not None:
            return _attach_render_attempt_diagnostics(direct, diagnostics)
        direct_failure_reason = _direct_narration_failure_reason(
            plan=plan,
            state=state,
            resolution=resolution,
            response=response,
            active_suggestions=active_suggestions,
        )
        if direct_failure_reason is not None:
            diagnostics.render_repair_failure_reason = direct_failure_reason
        plan_repair_packet = _build_render_plan_skill_packet(
            plan=plan,
            state=state,
            resolution=resolution,
            input_text=input_text,
            selected_prompt=selected_prompt,
            capability="play.render_repair",
            skill_id="play.render.repair.plan",
            repair_mode="contract_repair",
            failure_reason=failure_reason,
            draft_narration=draft_narration,
            draft_suggestions=draft_suggestions,
        )
        plan_response = _invoke_render_json(
            gateway,
            system_prompt=plan_repair_packet.build_system_prompt(variant="repair"),
            user_payload=plan_repair_packet.context_payload(),
            max_output_tokens=_render_plan_repair_output_budget(
                gateway=gateway,
                state=state,
                resolution=resolution,
            ),
            previous_response_id=getattr(response, "response_id", None) or previous_response_id,
            operation_name="play_render_plan_repair",
            override_plaintext_fallback_key=True,
            plaintext_fallback_key=None,
            skill_packet=plan_repair_packet,
        )
        diagnostics.render_repair_raw_excerpt = _response_trace_excerpt(plan_response) or diagnostics.render_repair_raw_excerpt
        render_plan = None
        plan_failure_reason = direct_failure_reason or failure_reason
        try:
            render_plan = PlayRenderPlanDraft.model_validate(plan_response.payload)
        except ValidationError:
            render_plan = None
        if render_plan is None:
            diagnostics.render_repair_failure_reason = plan_failure_reason
            gleaned = glean_render_turn(
                plan=plan,
                state=state,
                resolution=resolution,
                gateway=gateway,
                previous_response_id=getattr(plan_response, "response_id", None) or getattr(response, "response_id", None) or previous_response_id,
                failure_reason=plan_failure_reason,
                bad_narration=draft_narration or getattr(response, "raw_text", None),
                active_suggestions=active_suggestions,
                attempts=3,
            )
            if gleaned is not None:
                return _attach_render_attempt_diagnostics(gleaned, diagnostics)
            return None
        narration_packet = _build_render_narration_skill_packet(
            plan=plan,
            state=state,
            resolution=resolution,
            input_text=input_text,
            selected_prompt=selected_prompt,
            render_plan=render_plan,
            capability="play.render_repair",
            skill_id="play.render.repair.narration",
            repair_mode="anchor_repair",
            failure_reason=failure_reason,
        )
        narration_response = _invoke_render_json(
            gateway,
            system_prompt=narration_packet.build_system_prompt(variant="repair"),
            user_payload=narration_packet.context_payload(),
            max_output_tokens=_render_repair_output_budget(
                gateway=gateway,
                state=state,
                resolution=resolution,
            ),
            previous_response_id=getattr(plan_response, "response_id", None) or getattr(response, "response_id", None) or previous_response_id,
            operation_name="play_render_narration_repair",
            plaintext_fallback_key="narration",
            override_plaintext_fallback_key=True,
            skill_packet=narration_packet,
        )
        diagnostics.render_repair_raw_excerpt = _response_trace_excerpt(narration_response) or diagnostics.render_repair_raw_excerpt
        raw_narration = narration_response.raw_text or _narration_from_response_payload(narration_response.payload)
        narration_text = _narration_from_response_payload(narration_response.payload) or _render_plan_to_narration(plan, render_plan)
        narration_text = _coerce_wrapper_narration_to_scene_text(plan, narration_text)
        sanitized_narration = _sanitize_user_visible_narration(plan, narration_text)
        quality_reason = _render_failure_reason(
            plan=plan,
            state=state,
            resolution=resolution,
            narration=sanitized_narration,
            suggestions=active_suggestions,
            raw_text=raw_narration,
        )
        if quality_reason:
            auto_repaired = _auto_repair_narration(
                plan=plan,
                state=state,
                resolution=resolution,
                narration=sanitized_narration,
                failure_reason=quality_reason,
            )
            if auto_repaired is not None:
                diagnostics.render_repair_failure_reason = quality_reason
                return _attach_render_attempt_diagnostics(
                    RenderTurnResult(
                        narration=auto_repaired,
                        suggestions=active_suggestions,
                        source="llm_repair",
                        primary_path_mode="plan_repair",
                        attempts=2,
                        render_plan_stage2_rescue=True,
                        render_narration_stage2_rescue=True,
                        failure_reason=plan_failure_reason,
                        response_id=narration_response.response_id,
                        usage=narration_response.usage,
                        capability=narration_response.capability,
                        provider=narration_response.provider,
                        model=narration_response.model,
                        transport_style=narration_response.transport_style,
                        **_response_skill_kwargs(narration_response),
                    ),
                    diagnostics,
                )
            diagnostics.render_repair_failure_reason = quality_reason
            gleaned = glean_render_turn(
                plan=plan,
                state=state,
                resolution=resolution,
                gateway=gateway,
                previous_response_id=narration_response.response_id or getattr(plan_response, "response_id", None) or getattr(response, "response_id", None) or previous_response_id,
                failure_reason=quality_reason,
                bad_narration=sanitized_narration,
                active_suggestions=active_suggestions,
                attempts=3,
            )
            if gleaned is not None:
                return _attach_render_attempt_diagnostics(gleaned, diagnostics)
            return None
        return _attach_render_attempt_diagnostics(
            RenderTurnResult(
                narration=sanitized_narration,
                suggestions=active_suggestions,
                source="llm_repair",
                primary_path_mode="plan_repair",
                attempts=2,
                render_plan_stage2_rescue=True,
                render_narration_stage2_rescue=True,
                failure_reason=plan_failure_reason,
                response_id=narration_response.response_id,
                usage=narration_response.usage,
                capability=narration_response.capability,
                provider=narration_response.provider,
                model=narration_response.model,
                        transport_style=narration_response.transport_style,
                        **_response_skill_kwargs(narration_response),
                    ),
            diagnostics,
        )
    except GatewayCapabilityError as exc:
        diagnostics.render_repair_failure_reason = _map_render_gateway_error_code(exc.code)
        return None
    except (PlayGatewayError, ValidationError) as exc:
        diagnostics.render_repair_failure_reason = exc.code if isinstance(exc, PlayGatewayError) else "play_render_schema_invalid"
        return None


def render_turn(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_action: PlaySuggestedAction | None,
    gateway: CapabilityGatewayCore | None,
    previous_response_id: str | None,
    enable_render_repair: bool,
) -> RenderTurnResult:
    diagnostics = RenderAttemptDiagnostics()
    if gateway is None:
        fallback = deterministic_render(plan=plan, state=state, resolution=resolution)
        return _attach_render_attempt_diagnostics(
            RenderTurnResult(
                narration=fallback.narration,
                suggestions=fallback.suggestions,
                source="fallback",
                primary_path_mode="fallback",
                attempts=0,
                render_plan_stage1_success=False,
                render_plan_stage2_rescue=False,
                render_narration_stage1_success=False,
                render_narration_stage2_rescue=False,
            ),
            diagnostics,
        )
    selected_prompt = selected_action.prompt if selected_action is not None else None
    direct_packet = _build_direct_render_skill_packet(
        plan=plan,
        state=state,
        resolution=resolution,
        input_text=input_text,
        selected_prompt=selected_prompt,
    )
    render_stage = "primary_narration"
    try:
        response = _invoke_render_json(
            gateway,
            system_prompt=direct_packet.build_system_prompt(variant="normal"),
            user_payload=direct_packet.context_payload(),
            max_output_tokens=_render_output_budget(
                gateway=gateway,
                state=state,
                resolution=resolution,
            ),
            previous_response_id=previous_response_id,
            operation_name="play_render_turn",
            plaintext_fallback_key="narration",
            override_plaintext_fallback_key=True,
            skill_packet=direct_packet,
        )
        diagnostics.render_primary_fallback_source = getattr(response, "fallback_source", None)
        diagnostics.render_primary_raw_excerpt = _response_trace_excerpt(response)
        active_suggestions = [] if state.status != "active" else build_suggested_actions(plan, state)
        direct = _render_direct_narration_result(
            plan=plan,
            state=state,
            resolution=resolution,
            response=response,
            attempts=1,
            source="llm",
            failure_reason=None,
            active_suggestions=active_suggestions,
        )
        if direct is not None:
            return _attach_render_attempt_diagnostics(direct, diagnostics)
        direct_failure_reason = _direct_narration_failure_reason(
            plan=plan,
            state=state,
            resolution=resolution,
            response=response,
            active_suggestions=active_suggestions,
        )
        diagnostics.render_primary_failure_reason = direct_failure_reason
        if direct_failure_reason is not None:
            diagnostics.render_quality_reason_before_repair = direct_failure_reason
        raw_narration = getattr(response, "raw_text", None) or _narration_from_response_payload(response.payload)
        narration_text = _narration_from_response_payload(response.payload) or strip_model_meta_wrapper_text(raw_narration)
        narration_text = _coerce_wrapper_narration_to_scene_text(plan, narration_text)
        draft_narration = _sanitize_user_visible_narration(plan, narration_text) if narration_text else None
        if enable_render_repair:
            repaired = repair_render_turn(
                plan=plan,
                state=state,
                resolution=resolution,
                input_text=input_text,
                selected_action=selected_action,
                gateway=gateway,
                previous_response_id=response.response_id or previous_response_id,
                failure_reason=direct_failure_reason or "scene_plan_missing",
                draft_narration=draft_narration,
                draft_suggestions=active_suggestions,
                diagnostics=diagnostics,
            )
            if repaired is not None:
                return repaired
        gleaned = glean_render_turn(
            plan=plan,
            state=state,
            resolution=resolution,
            gateway=gateway,
            previous_response_id=response.response_id or previous_response_id,
            failure_reason=direct_failure_reason or "scene_plan_missing",
            bad_narration=draft_narration,
            active_suggestions=active_suggestions,
            attempts=2 if enable_render_repair else 1,
        )
        if gleaned is not None:
            return _attach_render_attempt_diagnostics(gleaned, diagnostics)
        fallback = deterministic_render(plan=plan, state=state, resolution=resolution)
        return _attach_render_attempt_diagnostics(
            RenderTurnResult(
                narration=fallback.narration,
                suggestions=fallback.suggestions,
                source="fallback",
                primary_path_mode="fallback",
                attempts=2 if enable_render_repair else 1,
                failure_reason=direct_failure_reason or "scene_plan_missing",
            ),
            diagnostics,
        )
    except GatewayCapabilityError as exc:
        failure_reason = _map_render_gateway_error_code(exc.code)
        if render_stage == "primary_narration" and diagnostics.render_primary_failure_reason is None:
            diagnostics.render_primary_failure_reason = failure_reason
        if enable_render_repair and gateway is not None:
            repaired = repair_render_turn(
                plan=plan,
                state=state,
                resolution=resolution,
                input_text=input_text,
                selected_action=selected_action,
                gateway=gateway,
                previous_response_id=previous_response_id,
                failure_reason=failure_reason,
                draft_narration=None,
                draft_suggestions=None,
                diagnostics=diagnostics,
            )
            if repaired is not None:
                return repaired
        fallback = deterministic_render(plan=plan, state=state, resolution=resolution)
        return _attach_render_attempt_diagnostics(
            RenderTurnResult(
                narration=fallback.narration,
                suggestions=fallback.suggestions,
                source="fallback",
                primary_path_mode="fallback",
                attempts=2 if enable_render_repair else 1,
                failure_reason=failure_reason,
            ),
            diagnostics,
        )
    except (PlayGatewayError, ValidationError) as exc:
        failure_reason = exc.code if isinstance(exc, PlayGatewayError) else "play_render_schema_invalid"
        if render_stage == "primary_narration" and diagnostics.render_primary_failure_reason is None:
            diagnostics.render_primary_failure_reason = failure_reason
        if enable_render_repair and gateway is not None:
            repaired = repair_render_turn(
                plan=plan,
                state=state,
                resolution=resolution,
                input_text=input_text,
                selected_action=selected_action,
                gateway=gateway,
                previous_response_id=previous_response_id,
                failure_reason=failure_reason,
                draft_narration=None,
                draft_suggestions=None,
                diagnostics=diagnostics,
            )
            if repaired is not None:
                return repaired
        fallback = deterministic_render(plan=plan, state=state, resolution=resolution)
        return _attach_render_attempt_diagnostics(
            RenderTurnResult(
                narration=fallback.narration,
                suggestions=fallback.suggestions,
                source="fallback",
                primary_path_mode="fallback",
                attempts=2 if enable_render_repair else 1,
                failure_reason=failure_reason,
            ),
            diagnostics,
        )
