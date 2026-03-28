from __future__ import annotations

from dataclasses import dataclass
import re

from pydantic import ValidationError

from rpg_backend.author.normalize import trim_ellipsis
from rpg_backend.generation_skill import ContextCard, GenerationSkillPacket
from rpg_backend.llm_gateway import CapabilityGatewayCore, GatewayCapabilityError, TextCapabilityRequest
from rpg_backend.responses_transport import strip_model_meta_wrapper_text
from rpg_backend.play.closeout_signals import build_ending_judge_signal_payload, judge_eligible
from rpg_backend.play.contracts import (
    PlayEndingIntentJudgeDraft,
    PlayPlan,
    PlayPyrrhicCriticDraft,
    PlayResolutionEffect,
    PlaySuggestedAction,
)
from rpg_backend.play.gateway import PlayGatewayError
from rpg_backend.play.runtime import PlaySessionState, TurnEndingGateContext


@dataclass(frozen=True)
class EndingJudgeResult:
    proposed_ending_id: str | None
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
    skill_id: str | None = None
    skill_version: str | None = None
    contract_mode: str | None = None
    context_card_ids: list[str] | None = None
    context_packet_characters: int | None = None
    repair_mode: str | None = None


@dataclass(frozen=True)
class PyrrhicCriticResult:
    proposed_ending_id: str | None
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


def _ending_judge_output_budget(gateway: CapabilityGatewayCore) -> int | None:
    budget = gateway.text_policy("play.ending_judge").max_output_tokens
    if budget is None:
        return 80
    return min(int(budget), 80)


def _ending_judge_repair_output_budget(gateway: CapabilityGatewayCore) -> int | None:
    budget = gateway.text_policy("play.ending_judge").max_output_tokens
    if budget is None:
        return 60
    return min(int(budget), 60)


def _pyrrhic_critic_output_budget(gateway: CapabilityGatewayCore) -> int | None:
    budget = gateway.text_policy("play.pyrrhic_critic").max_output_tokens
    if budget is None:
        return 60
    return min(int(budget), 60)


def _play_provider_mode(_gateway: CapabilityGatewayCore | None) -> str:
    return "compact_prompt_only"


def _salvage_ending_id_from_text(raw_text: str | None, *, allowed_values: tuple[str, ...]) -> str | None:
    cleaned = strip_model_meta_wrapper_text(str(raw_text or "")).casefold()
    if not cleaned:
        return None
    explicit = re.search(r"\b(collapse|pyrrhic|mixed)\b", cleaned)
    if explicit and explicit.group(1) in allowed_values:
        return explicit.group(1)
    matches = [value for value in allowed_values if re.search(rf"\b{re.escape(value)}\b", cleaned)]
    if len(matches) == 1:
        return matches[0]
    return None


def _compact_ending_output_budget(gateway: CapabilityGatewayCore, *, repair: bool) -> int | None:
    base = _ending_judge_repair_output_budget(gateway) if repair else _ending_judge_output_budget(gateway)
    if base is None:
        return 80 if not repair else 60
    return min(int(base) + (20 if repair else 0), 120 if repair else 100)


def _compact_pyrrhic_output_budget(gateway: CapabilityGatewayCore, *, repair: bool) -> int | None:
    base = _pyrrhic_critic_output_budget(gateway)
    if base is None:
        return 60 if not repair else 80
    return min(int(base) + (20 if repair else 0), 100 if repair else 80)


def _closeout_skill_packet(
    *,
    capability: str,
    skill_id: str,
    task_brief: str,
    payload: dict[str, object],
    repair_mode: str = "none",
) -> GenerationSkillPacket:
    return GenerationSkillPacket(
        skill_id=skill_id,
        skill_version="v1",
        capability=capability,
        contract_mode="compact_contract",
        role_style="plain",
        required_output_contract="Return one compact ENDING line only.",
        context_cards=(
            ContextCard("closeout_signal_card", {"signal_payload": payload.get("signal_payload")}, priority=10),
            ContextCard("current_beat_card", {"current_beat": payload.get("current_beat")}, priority=20),
        ),
        task_brief=task_brief,
        repair_mode=repair_mode,
        repair_note="Repair the invalid closeout output while preserving the same ENDING line contract." if repair_mode != "none" else None,
        final_contract_note="Return only one ENDING line. No JSON. No markdown." if repair_mode != "none" else None,
        extra_payload=payload,
    )


def repair_ending_intent_judge(
    *,
    gateway: CapabilityGatewayCore,
    previous_response_id: str | None,
    failure_reason: str,
    payload: dict[str, object],
) -> EndingJudgeResult | None:
    repair_payload = {
        "failure_reason": failure_reason,
        "current_beat": payload["current_beat"],
        "signal_payload": payload["signal_payload"],
    }
    system_prompt = (
        "Repair the ending_intent_judge output. "
        "Do not return JSON. Return exactly one line in this format: ENDING: <collapse|pyrrhic|mixed>. "
        "Allowed values: collapse, pyrrhic, mixed. "
        "Use signal_payload.preference as the tie-breaker when the state is ambiguous."
    )
    skill_packet = _closeout_skill_packet(
        capability="play.ending_judge",
        skill_id="play.ending_judge.repair",
        task_brief=system_prompt,
        payload=repair_payload,
        repair_mode="schema_repair",
    )
    try:
        response = gateway.invoke_text_capability(
            "play.ending_judge",
            TextCapabilityRequest(
                system_prompt=skill_packet.build_system_prompt(variant="repair"),
                user_payload=skill_packet.context_payload(),
                max_output_tokens=_compact_ending_output_budget(gateway, repair=True),
                previous_response_id=previous_response_id,
                operation_name="play_ending_intent_judge_repair",
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
            salvaged = _salvage_ending_id_from_text(response.raw_text, allowed_values=("collapse", "pyrrhic", "mixed"))
            if salvaged is not None:
                return EndingJudgeResult(
                    proposed_ending_id=salvaged,
                    source="llm",
                    attempts=2,
                    stage2_rescue=True,
                    failure_reason=failure_reason,
                    response_id=response.response_id,
                    usage=response.usage,
                    capability=response.capability,
                    provider=response.provider,
                    model=response.model,
                    transport_style=response.transport_style,
                    **_response_skill_kwargs(response),
                )
            return None
        try:
            draft = PlayEndingIntentJudgeDraft.model_validate(response.payload)
        except ValidationError:
            salvaged = _salvage_ending_id_from_text(response.raw_text, allowed_values=("collapse", "pyrrhic", "mixed"))
            if salvaged is None:
                return None
            return EndingJudgeResult(
                proposed_ending_id=salvaged,
                source="llm",
                attempts=2,
                stage2_rescue=True,
                failure_reason=failure_reason,
                response_id=response.response_id,
                usage=response.usage,
                capability=response.capability,
                provider=response.provider,
                model=response.model,
                transport_style=response.transport_style,
                **_response_skill_kwargs(response),
            )
        return EndingJudgeResult(
            proposed_ending_id=draft.ending_id,
            source="llm",
            attempts=2,
            stage2_rescue=True,
            failure_reason=failure_reason,
            response_id=response.response_id,
            usage=response.usage,
            capability=response.capability,
            provider=response.provider,
            model=response.model,
            transport_style=response.transport_style,
            **_response_skill_kwargs(response),
        )
    except GatewayCapabilityError:
        return None
    except (PlayGatewayError, ValidationError):
        return None


def judge_ending_intent(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    ending_context: TurnEndingGateContext,
    input_text: str,
    selected_action: PlaySuggestedAction | None,
    gateway: CapabilityGatewayCore | None,
    previous_response_id: str | None,
    enable_ending_intent_judge: bool,
) -> EndingJudgeResult:
    if state.ending is not None:
        return EndingJudgeResult(proposed_ending_id=state.ending.ending_id, source="skipped")
    if not enable_ending_intent_judge or gateway is None:
        return EndingJudgeResult(proposed_ending_id=None, source="skipped")
    if not judge_eligible(plan, state, ending_context):
        return EndingJudgeResult(proposed_ending_id=None, source="skipped")
    beat = plan.beats[state.beat_index]
    signal_payload = build_ending_judge_signal_payload(plan, state, resolution, ending_context)
    payload = {
        "story_title": plan.story_title,
        "current_beat": {
            "beat_index": state.beat_index + 1,
            "title": beat.title,
            "goal": beat.goal,
            "is_final_beat": state.beat_index >= len(plan.beats) - 1,
        },
        "player_input": trim_ellipsis(input_text, 180),
        "selected_suggestion_prompt": trim_ellipsis(selected_action.prompt, 180) if selected_action is not None else None,
        "signal_payload": signal_payload,
    }
    system_prompt = (
        "You are ending_intent_judge for a dramatic short-form story game. "
        "Choose the single best ending intent for the current post-turn state. "
        "Allowed values are collapse, pyrrhic, mixed only. "
        "collapse means civic failure overwhelms coordination. "
        "pyrrhic means the scene stabilizes or succeeds, but only through obvious civic or relational cost. "
        "mixed means the scene stabilizes without decisive failure and without a strong paid-cost signature. "
        "If the player secured truth, leverage, or settlement progress but paid visible civic cost, prefer pyrrhic over collapse unless loss of control clearly dominates the state. "
        "If the player already secured a binding protocol, corrected record, voided bad vote, or emergency settlement, do not choose collapse unless multiple pressure channels are clearly broken or the city has obviously slipped beyond coordinated control. "
        "Use signal_payload.closeout_profile and signal_payload.closeout_guidance as a deterministic genre-specific tie-breaker. "
        "Also use signal_payload.runtime_policy_profile and signal_payload.runtime_guidance to understand which kinds of pressure count most in this story. "
        "If signal_payload.turn_cap_reached is true, treat this as a forced closeout window and avoid mixed unless the state is genuinely stable and low-cost. "
        "If final beat is reached and signal_payload.preference is prefer_pyrrhic, choose pyrrhic over mixed unless collapse clearly dominates. "
        "Do not return JSON. Return exactly one line in this format: ENDING: <collapse|pyrrhic|mixed>. "
        "Optional second line: REASON: <short note>."
    )
    skill_packet = _closeout_skill_packet(
        capability="play.ending_judge",
        skill_id="play.ending_judge.primary",
        task_brief=system_prompt,
        payload=payload,
    )
    try:
        response = gateway.invoke_text_capability(
            "play.ending_judge",
            TextCapabilityRequest(
                system_prompt=skill_packet.build_system_prompt(variant="normal"),
                user_payload=skill_packet.context_payload(),
                max_output_tokens=_compact_ending_output_budget(gateway, repair=False),
                previous_response_id=previous_response_id,
                operation_name="play_ending_intent_judge",
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
            salvaged = _salvage_ending_id_from_text(response.raw_text, allowed_values=("collapse", "pyrrhic", "mixed"))
            if salvaged is not None:
                return EndingJudgeResult(
                    proposed_ending_id=salvaged,
                    source="llm",
                    attempts=1,
                    stage1_success=True,
                    response_id=response.response_id,
                    usage=response.usage,
                    capability=response.capability,
                    provider=response.provider,
                    model=response.model,
                    transport_style=response.transport_style,
                    **_response_skill_kwargs(response),
                )
            return EndingJudgeResult(
                proposed_ending_id=None,
                source="failed",
                attempts=1,
                failure_reason="play_llm_invalid_json",
                response_id=response.response_id,
                usage=response.usage,
                capability=response.capability,
                provider=response.provider,
                model=response.model,
                transport_style=response.transport_style,
            )
        try:
            draft = PlayEndingIntentJudgeDraft.model_validate(response.payload)
        except ValidationError:
            salvaged = _salvage_ending_id_from_text(response.raw_text, allowed_values=("collapse", "pyrrhic", "mixed"))
            if salvaged is None:
                raise
            return EndingJudgeResult(
                proposed_ending_id=salvaged,
                source="llm",
                attempts=1,
                stage1_success=True,
                response_id=response.response_id,
                usage=response.usage,
                capability=response.capability,
                provider=response.provider,
                model=response.model,
                transport_style=response.transport_style,
                    **_response_skill_kwargs(response),
            )
        return EndingJudgeResult(
            proposed_ending_id=draft.ending_id,
            source="llm",
            attempts=1,
            stage1_success=True,
            response_id=response.response_id,
            usage=response.usage,
            capability=response.capability,
            provider=response.provider,
            model=response.model,
            transport_style=response.transport_style,
            **_response_skill_kwargs(response),
        )
    except GatewayCapabilityError as exc:
        reason = {
            "gateway_text_provider_failed": "play_llm_provider_failed",
            "gateway_text_invalid_response": "play_llm_invalid_response",
            "gateway_text_invalid_json": "play_llm_invalid_json",
            "gateway_text_model_missing": "play_llm_config_missing",
            "gateway_text_config_missing": "play_llm_config_missing",
        }.get(exc.code, exc.code)
        repair = repair_ending_intent_judge(
            gateway=gateway,
            previous_response_id=previous_response_id,
            failure_reason=reason,
            payload=payload,
        )
        if repair is not None:
            return repair
        return EndingJudgeResult(
            proposed_ending_id=None,
            source="failed",
            attempts=2,
            failure_reason=reason,
        )
    except (PlayGatewayError, ValidationError) as exc:
        reason = exc.code if isinstance(exc, PlayGatewayError) else "play_ending_judge_schema_invalid"
        repair = repair_ending_intent_judge(
            gateway=gateway,
            previous_response_id=previous_response_id,
            failure_reason=reason,
            payload=payload,
        )
        if repair is not None:
            return repair
        return EndingJudgeResult(
            proposed_ending_id=None,
            source="failed",
            attempts=2,
            failure_reason=reason,
        )


def run_pyrrhic_critic(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    ending_context: TurnEndingGateContext,
    judge_result: EndingJudgeResult,
    gateway: CapabilityGatewayCore | None,
    previous_response_id: str | None,
) -> PyrrhicCriticResult:
    if gateway is None or judge_result.proposed_ending_id != "mixed":
        return PyrrhicCriticResult(proposed_ending_id=None, source="skipped")
    signal_payload = build_ending_judge_signal_payload(plan, state, resolution, ending_context)
    if signal_payload["preference"] != "prefer_pyrrhic":
        return PyrrhicCriticResult(proposed_ending_id=None, source="skipped")
    beat = plan.beats[state.beat_index]
    payload = {
        "current_beat": {
            "beat_index": state.beat_index + 1,
            "title": beat.title,
            "goal": beat.goal,
        },
        "signal_payload": signal_payload,
        "current_judge_choice": "mixed",
    }
    system_prompt = (
        "You are mixed_vs_pyrrhic_critic for a short-form story game. "
        "Only choose between pyrrhic and mixed. "
        "Choose pyrrhic when the story has clearly stabilized or succeeded but visible civic or relational cost is still high. "
        "Choose mixed when stabilization happened without a strong paid-cost signature. "
        "Use signal_payload.closeout_guidance as a deterministic tie-breaker. "
        "Do not return JSON. Return exactly one line in this format: ENDING: <pyrrhic|mixed>."
    )
    skill_packet = _closeout_skill_packet(
        capability="play.pyrrhic_critic",
        skill_id="play.pyrrhic_critic.primary",
        task_brief=system_prompt,
        payload=payload,
    )
    try:
        response = gateway.invoke_text_capability(
            "play.pyrrhic_critic",
            TextCapabilityRequest(
                system_prompt=skill_packet.build_system_prompt(variant="normal"),
                user_payload=skill_packet.context_payload(),
                max_output_tokens=_compact_pyrrhic_output_budget(gateway, repair=False),
                previous_response_id=previous_response_id,
                operation_name="play_pyrrhic_critic",
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
            salvaged = _salvage_ending_id_from_text(response.raw_text, allowed_values=("pyrrhic", "mixed"))
            if salvaged is not None:
                return PyrrhicCriticResult(
                    proposed_ending_id=salvaged,
                    source="llm",
                    attempts=1,
                    stage1_success=True,
                    response_id=response.response_id,
                    usage=response.usage,
                    capability=response.capability,
                    provider=response.provider,
                    model=response.model,
                    transport_style=response.transport_style,
                    **_response_skill_kwargs(response),
                )
            return PyrrhicCriticResult(
                proposed_ending_id=None,
                source="failed",
                attempts=1,
                failure_reason="play_llm_invalid_json",
                response_id=response.response_id,
                usage=response.usage,
                capability=response.capability,
                provider=response.provider,
                model=response.model,
                transport_style=response.transport_style,
            )
        try:
            draft = PlayPyrrhicCriticDraft.model_validate(response.payload)
        except ValidationError:
            salvaged = _salvage_ending_id_from_text(response.raw_text, allowed_values=("pyrrhic", "mixed"))
            if salvaged is None:
                raise
            return PyrrhicCriticResult(
                proposed_ending_id=salvaged,
                source="llm",
                attempts=1,
                stage1_success=True,
                response_id=response.response_id,
                usage=response.usage,
                capability=response.capability,
                provider=response.provider,
                model=response.model,
                transport_style=response.transport_style,
                **_response_skill_kwargs(response),
            )
        return PyrrhicCriticResult(
            proposed_ending_id=draft.ending_id,
            source="llm",
            attempts=1,
            stage1_success=True,
            response_id=response.response_id,
            usage=response.usage,
            capability=response.capability,
            provider=response.provider,
            model=response.model,
            transport_style=response.transport_style,
            **_response_skill_kwargs(response),
        )
    except GatewayCapabilityError as exc:
        reason = {
            "gateway_text_provider_failed": "play_llm_provider_failed",
            "gateway_text_invalid_response": "play_llm_invalid_response",
            "gateway_text_invalid_json": "play_llm_invalid_json",
            "gateway_text_model_missing": "play_llm_config_missing",
            "gateway_text_config_missing": "play_llm_config_missing",
        }.get(exc.code, exc.code)
        return PyrrhicCriticResult(
            proposed_ending_id=None,
            source="failed",
            attempts=1,
            failure_reason=reason,
        )
    except (PlayGatewayError, ValidationError) as exc:
        reason = exc.code if isinstance(exc, PlayGatewayError) else "play_pyrrhic_critic_schema_invalid"
        return PyrrhicCriticResult(
            proposed_ending_id=None,
            source="failed",
            attempts=1,
            failure_reason=reason,
        )
