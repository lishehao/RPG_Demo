from __future__ import annotations

from dataclasses import dataclass
import re

from pydantic import ValidationError

from rpg_backend.author.normalize import trim_ellipsis, unique_preserve
from rpg_backend.play.contracts import PlayPlan, PlaySuggestedAction, PlayTurnIntentDraft
from rpg_backend.play.gateway import PlayGatewayError, PlayLLMGateway
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


def _cast_lookup(plan: PlayPlan) -> dict[str, str]:
    return {npc.npc_id: npc.name for npc in plan.cast}


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
    return {
        "story_title": trim_ellipsis(plan.story_title, 80),
        "runtime_policy_profile": plan.runtime_policy_profile,
        "current_beat": {
            "title": trim_ellipsis(beat.title, 64),
            "goal": trim_ellipsis(beat.goal, 120),
            "focus_npcs": _compact_npc_names(plan, beat.focus_npcs),
            "conflict_npcs": _compact_npc_names(plan, beat.conflict_npcs),
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


def _interpret_output_budget(gateway: PlayLLMGateway) -> int | None:
    budget = gateway.max_output_tokens_interpret
    if budget is None:
        return 128
    return min(int(budget), 128)


def _interpret_repair_output_budget(gateway: PlayLLMGateway) -> int | None:
    budget = gateway.max_output_tokens_interpret_repair
    if budget is None:
        return 144
    return min(int(budget), 144)


def repair_interpret_turn(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    input_text: str,
    selected_action: PlaySuggestedAction | None,
    gateway: PlayLLMGateway,
    previous_response_id: str | None,
    failure_reason: str,
) -> InterpretTurnResult | None:
    payload = {
        "failure_reason": failure_reason,
        **_build_interpret_payload(
            plan=plan,
            state=state,
            input_text=input_text,
            selected_prompt=selected_action.prompt if selected_action is not None else None,
        ),
    }
    system_prompt = (
        "Repair the player-intent extraction for a deterministic story game. "
        "Return strict JSON with affordance_tag, target_npc_ids, risk_level, execution_frame, tactic_summary. "
        "Use one provided affordance_tag and npc ids only. "
        "risk_level must be low, medium, or high. "
        "execution_frame must be procedural, coalition, public, or coercive. "
        "Keep tactic_summary under 14 words."
    )
    try:
        response = gateway._invoke_json(
            system_prompt=system_prompt,
            user_payload=payload,
            max_output_tokens=_interpret_repair_output_budget(gateway),
            previous_response_id=previous_response_id,
            operation_name="play_interpret_repair",
        )
        intent = _sanitize_intent(
            plan=plan,
            state=state,
            intent=PlayTurnIntentDraft.model_validate(response.payload),
        )
        return InterpretTurnResult(
            intent=intent,
            source="llm_repair",
            attempts=2,
            failure_reason=failure_reason,
            response_id=response.response_id,
            usage=response.usage,
        )
    except (PlayGatewayError, ValidationError):
        return None


def interpret_turn(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    input_text: str,
    selected_action: PlaySuggestedAction | None,
    gateway: PlayLLMGateway | None,
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
    try:
        response = gateway._invoke_json(
            system_prompt=system_prompt,
            user_payload=payload,
            max_output_tokens=_interpret_output_budget(gateway),
            previous_response_id=previous_response_id,
            operation_name="play_interpret_turn",
        )
        intent = _sanitize_intent(
            plan=plan,
            state=state,
            intent=PlayTurnIntentDraft.model_validate(response.payload),
        )
        return InterpretTurnResult(
            intent=intent,
            source="llm",
            attempts=1,
            response_id=response.response_id,
            usage=response.usage,
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
