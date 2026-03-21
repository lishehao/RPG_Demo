from __future__ import annotations

from rpg_backend.play.contracts import PlayPlan, PlayResolutionEffect
from rpg_backend.play.runtime import PlaySessionState, TurnEndingGateContext
from rpg_backend.story_profiles import closeout_preference, closeout_profile_guidance, runtime_policy_guidance


def judge_eligible(
    plan: PlayPlan,
    state: PlaySessionState,
    ending_context: TurnEndingGateContext,
) -> bool:
    if ending_context.turn_cap_reached:
        return True
    if ending_context.final_beat_completed or ending_context.final_beat_handoff:
        return True
    pressure_axes = [axis for axis in plan.axes if axis.kind == "pressure"]
    if not pressure_axes:
        return False
    highest = max(state.axis_values.get(axis.axis_id, axis.starting_value) for axis in pressure_axes)
    threshold = max(axis.max_value for axis in pressure_axes) - 1
    return highest >= threshold


def build_ending_judge_signal_payload(
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    ending_context: TurnEndingGateContext,
) -> dict[str, object]:
    pressure_axes = [axis for axis in plan.axes if axis.kind == "pressure"]
    non_pressure_axes = [axis for axis in plan.axes if axis.kind != "pressure"]
    pressure_max_by_id = {axis.axis_id: axis.max_value for axis in pressure_axes}
    high_pressure_axes = [
        {
            "axis_id": axis.axis_id,
            "label": axis.label,
            "value": state.axis_values.get(axis.axis_id, axis.starting_value),
        }
        for axis in pressure_axes
        if state.axis_values.get(axis.axis_id, axis.starting_value) >= max(axis.max_value - 2, axis.min_value + 1)
    ]
    success_axes = [
        {
            "axis_id": axis.axis_id,
            "label": axis.label,
            "value": state.axis_values.get(axis.axis_id, axis.starting_value),
        }
        for axis in non_pressure_axes
        if state.axis_values.get(axis.axis_id, axis.starting_value) >= max(axis.max_value - 1, axis.min_value + 1)
    ]
    negative_stances = [
        {
            "stance_id": stance.stance_id,
            "label": stance.label,
            "value": state.stance_values.get(stance.stance_id, stance.starting_value),
        }
        for stance in plan.stances
        if state.stance_values.get(stance.stance_id, stance.starting_value) <= -1
    ]
    collapse_signal = state.collapse_pressure_streak >= 2 or any(
        item["value"] >= pressure_max_by_id.get(item["axis_id"], item["value"] + 1)
        for item in high_pressure_axes
    )
    success_signal = bool(success_axes)
    cost_signal = bool(high_pressure_axes or negative_stances or resolution.off_route or resolution.risk_level == "high")
    success_ledger = dict(state.success_ledger)
    cost_ledger = dict(state.cost_ledger)
    preference = closeout_preference(
        plan.closeout_profile,
        collapse_signal=collapse_signal,
        success_signal=success_signal or sum(success_ledger.values()) >= 2,
        cost_signal=cost_signal or sum(cost_ledger.values()) >= 2,
        truth_count=len(state.discovered_truth_ids),
        event_count=len(state.discovered_event_ids),
        high_pressure_count=len(high_pressure_axes),
        negative_stance_count=len(negative_stances),
        turn_cap_reached=ending_context.turn_cap_reached,
    )
    return {
        "closeout_profile": plan.closeout_profile,
        "closeout_router_reason": plan.closeout_router_reason,
        "closeout_guidance": closeout_profile_guidance(plan.closeout_profile),
        "runtime_policy_profile": plan.runtime_policy_profile,
        "runtime_router_reason": plan.runtime_router_reason,
        "runtime_guidance": runtime_policy_guidance(plan.runtime_policy_profile),
        "final_beat_completed": ending_context.final_beat_completed,
        "final_beat_handoff": ending_context.final_beat_handoff,
        "turn_cap_reached": ending_context.turn_cap_reached,
        "collapse_pressure_streak": state.collapse_pressure_streak,
        "high_pressure_axes": high_pressure_axes,
        "success_axes": success_axes,
        "negative_stances": negative_stances,
        "discovered_truth_count": len(state.discovered_truth_ids),
        "discovered_event_count": len(state.discovered_event_ids),
        "success_ledger": success_ledger,
        "cost_ledger": cost_ledger,
        "off_route": resolution.off_route,
        "risk_level": resolution.risk_level,
        "affordance_tag": resolution.affordance_tag,
        "preference": preference,
    }
