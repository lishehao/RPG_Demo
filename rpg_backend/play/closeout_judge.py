from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from rpg_backend.author.normalize import trim_ellipsis
from rpg_backend.play.closeout_signals import build_ending_judge_signal_payload, judge_eligible
from rpg_backend.play.contracts import (
    PlayEndingIntentJudgeDraft,
    PlayPlan,
    PlayPyrrhicCriticDraft,
    PlayResolutionEffect,
    PlaySuggestedAction,
)
from rpg_backend.play.gateway import PlayGatewayError, PlayLLMGateway
from rpg_backend.play.runtime import PlaySessionState, TurnEndingGateContext


@dataclass(frozen=True)
class EndingJudgeResult:
    proposed_ending_id: str | None
    source: str
    attempts: int = 0
    failure_reason: str | None = None
    response_id: str | None = None
    usage: dict[str, int | str] | None = None


@dataclass(frozen=True)
class PyrrhicCriticResult:
    proposed_ending_id: str | None
    source: str
    attempts: int = 0
    failure_reason: str | None = None
    response_id: str | None = None
    usage: dict[str, int | str] | None = None


def _ending_judge_output_budget(gateway: PlayLLMGateway) -> int | None:
    budget = gateway.max_output_tokens_ending_judge
    if budget is None:
        return 80
    return min(int(budget), 80)


def _ending_judge_repair_output_budget(gateway: PlayLLMGateway) -> int | None:
    budget = gateway.max_output_tokens_ending_judge_repair
    if budget is None:
        return 60
    return min(int(budget), 60)


def _pyrrhic_critic_output_budget(gateway: PlayLLMGateway) -> int | None:
    budget = gateway.max_output_tokens_pyrrhic_critic
    if budget is None:
        return 60
    return min(int(budget), 60)


def repair_ending_intent_judge(
    *,
    gateway: PlayLLMGateway,
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
        "Return strict JSON with ending_id only. "
        "Allowed values: collapse, pyrrhic, mixed. "
        "Use signal_payload.preference as the tie-breaker when the state is ambiguous."
    )
    try:
        response = gateway._invoke_json(
            system_prompt=system_prompt,
            user_payload=repair_payload,
            max_output_tokens=_ending_judge_repair_output_budget(gateway),
            previous_response_id=previous_response_id,
            operation_name="play_ending_intent_judge_repair",
        )
        draft = PlayEndingIntentJudgeDraft.model_validate(response.payload)
        return EndingJudgeResult(
            proposed_ending_id=draft.ending_id,
            source="llm",
            attempts=2,
            failure_reason=failure_reason,
            response_id=response.response_id,
            usage=response.usage,
        )
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
    gateway: PlayLLMGateway | None,
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
        "Return strict JSON with ending_id only."
    )
    try:
        response = gateway._invoke_json(
            system_prompt=system_prompt,
            user_payload=payload,
            max_output_tokens=_ending_judge_output_budget(gateway),
            previous_response_id=previous_response_id,
            operation_name="play_ending_intent_judge",
        )
        draft = PlayEndingIntentJudgeDraft.model_validate(response.payload)
        return EndingJudgeResult(
            proposed_ending_id=draft.ending_id,
            source="llm",
            attempts=1,
            response_id=response.response_id,
            usage=response.usage,
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
    gateway: PlayLLMGateway | None,
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
        "Return strict JSON with ending_id only."
    )
    try:
        response = gateway._invoke_json(
            system_prompt=system_prompt,
            user_payload=payload,
            max_output_tokens=_pyrrhic_critic_output_budget(gateway),
            previous_response_id=previous_response_id,
            operation_name="play_pyrrhic_critic",
        )
        draft = PlayPyrrhicCriticDraft.model_validate(response.payload)
        return PyrrhicCriticResult(
            proposed_ending_id=draft.ending_id,
            source="llm",
            attempts=1,
            response_id=response.response_id,
            usage=response.usage,
        )
    except (PlayGatewayError, ValidationError) as exc:
        reason = exc.code if isinstance(exc, PlayGatewayError) else "play_pyrrhic_critic_schema_invalid"
        return PyrrhicCriticResult(
            proposed_ending_id=None,
            source="failed",
            attempts=1,
            failure_reason=reason,
        )
