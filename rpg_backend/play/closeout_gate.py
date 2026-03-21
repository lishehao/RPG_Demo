from __future__ import annotations

from rpg_backend.play.contracts import PlayEnding, PlayPlan, PlayResolutionEffect
from rpg_backend.play.runtime import (
    PlaySessionState,
    TurnEndingGateContext,
    _conditions_match,
    _ending_by_id,
    _highest_pressure_axis_value,
)
from rpg_backend.story_profiles import profile_prefers_pyrrhic_fallback


def determine_ending(
    plan: PlayPlan,
    state: PlaySessionState,
    *,
    resolution: PlayResolutionEffect,
    final_beat_completed: bool,
    final_beat_handoff: bool = False,
    turn_cap_reached: bool = False,
    use_tuned_ending_policy: bool = True,
    proposed_ending_id: str | None = None,
    enable_pyrrhic_judge_relaxation: bool = True,
) -> tuple[PlayEnding | None, str | None]:
    current_on_final_beat = state.beat_index >= len(plan.beats) - 1
    closeout_reached = final_beat_completed or final_beat_handoff or turn_cap_reached
    runtime_profile = plan.runtime_policy_profile
    collapse_ready = current_on_final_beat or state.collapse_pressure_streak >= (2 if use_tuned_ending_policy else 1)
    collapse_rule = next((rule for rule in plan.ending_rules if rule.ending_id == "collapse"), None)
    pyrrhic_rule = next((rule for rule in plan.ending_rules if rule.ending_id == "pyrrhic"), None)
    pressure_axes = [axis for axis in plan.axes if axis.kind == "pressure"]
    non_pressure_axes = [axis for axis in plan.axes if axis.kind != "pressure"]
    pressure_axis_ids = {axis.axis_id for axis in pressure_axes}
    last_turn_pressure_increases = {
        axis_id: delta
        for axis_id, delta in state.last_turn_axis_deltas.items()
        if axis_id in pressure_axis_ids and delta > 0
    }
    last_turn_pressure_relief = {
        axis_id: delta
        for axis_id, delta in state.last_turn_axis_deltas.items()
        if axis_id in pressure_axis_ids and delta < 0
    }
    last_turn_negative_stances = {
        stance_id: delta
        for stance_id, delta in state.last_turn_stance_deltas.items()
        if delta < 0
    }
    last_turn_binding_progress = "The crisis moved closer to a binding outcome." in state.last_turn_consequences
    last_turn_coalition_room = "You gained room to maneuver inside the coalition." in state.last_turn_consequences
    last_turn_public_pressure_eased = "Visible public pressure eased." in state.last_turn_consequences
    last_turn_leverage_gain = state.last_turn_axis_deltas.get("political_leverage", 0) > 0
    last_turn_recovery_signal = bool(last_turn_pressure_relief) or last_turn_public_pressure_eased
    last_turn_stabilizing_success = last_turn_binding_progress and (last_turn_leverage_gain or last_turn_recovery_signal or last_turn_coalition_room)
    last_turn_breakdown_signal = (
        len(last_turn_pressure_increases) >= 2
        or len(last_turn_negative_stances) >= 2
        or (
            state.last_turn_axis_deltas.get("public_panic", 0) >= 2
            and len(last_turn_negative_stances) >= 1
            and not last_turn_stabilizing_success
        )
    )
    last_turn_mandate_preserved_signal = (
        last_turn_binding_progress
        and not last_turn_breakdown_signal
        and (
            not last_turn_pressure_increases
            or state.last_turn_axis_deltas.get("public_panic", 0) <= 1
        )
    )

    strong_success_signal = any(
        state.axis_values.get(axis.axis_id, axis.starting_value) >= max(axis.max_value - 1, axis.min_value + 1)
        for axis in non_pressure_axes
    ) or any(
        state.stance_values.get(stance.stance_id, stance.starting_value) >= 1
        for stance in plan.stances
    )
    success_ledger_total = sum(state.success_ledger.values())
    cost_ledger_total = sum(state.cost_ledger.values())
    public_cost = state.cost_ledger.get("public_cost", 0)
    relationship_cost = state.cost_ledger.get("relationship_cost", 0)
    procedural_cost = state.cost_ledger.get("procedural_cost", 0)
    coercion_cost = state.cost_ledger.get("coercion_cost", 0)
    public_pressure_value = state.axis_values.get("public_panic", 0)
    resource_pressure_value = state.axis_values.get("resource_strain", 0)
    institutional_pressure_value = state.axis_values.get("system_integrity", 0)
    positive_stances = [stance for stance in plan.stances if state.stance_values.get(stance.stance_id, stance.starting_value) >= 1]
    pressure_axis_max_hits = sum(
        1
        for axis in pressure_axes
        if state.axis_values.get(axis.axis_id, axis.starting_value) >= axis.max_value
    )
    pressure_axis_near_max_hits = sum(
        1
        for axis in pressure_axes
        if state.axis_values.get(axis.axis_id, axis.starting_value) >= max(axis.max_value - 1, axis.min_value + 1)
    )
    success_ledger_high = success_ledger_total >= 4 or state.success_ledger.get("settlement_progress", 0) >= 1
    success_ledger_medium = success_ledger_total >= 2
    cost_ledger_high = cost_ledger_total >= 3 or state.cost_ledger.get("coercion_cost", 0) >= 1 or state.cost_ledger.get("relationship_cost", 0) >= 2
    cost_ledger_medium = cost_ledger_total >= 1
    strong_cost_signal = any(
        state.axis_values.get(axis.axis_id, axis.starting_value) >= min(3, axis.max_value)
        for axis in pressure_axes
    ) or any(
        state.stance_values.get(stance.stance_id, stance.starting_value) <= -1
        for stance in plan.stances
    ) or state.collapse_pressure_streak >= 1
    moderate_cost_signal = any(
        state.axis_values.get(axis.axis_id, axis.starting_value) >= max(axis.min_value + 1, min(2, axis.max_value))
        for axis in pressure_axes
    ) or any(
        state.stance_values.get(stance.stance_id, stance.starting_value) <= -1
        for stance in plan.stances
    ) or state.collapse_pressure_streak >= 1
    severe_pressure_signal = any(
        state.axis_values.get(axis.axis_id, axis.starting_value) >= max(axis.max_value - 1, axis.min_value + 1)
        for axis in pressure_axes
    )
    pressure_safe = all(
        state.axis_values.get(axis.axis_id, axis.starting_value) <= max(axis.max_value - 2, axis.min_value)
        for axis in pressure_axes
    )
    truth_signal = len(state.discovered_truth_ids) >= 2 or (
        pyrrhic_rule is not None and any(item in state.discovered_truth_ids for item in pyrrhic_rule.conditions.required_truths)
    )
    negative_stances = [
        stance
        for stance in plan.stances
        if state.stance_values.get(stance.stance_id, stance.starting_value) <= -1
    ]
    relationship_recovered = len(positive_stances) >= max(len(negative_stances), 1)
    binding_success_signal = (
        state.success_ledger.get("settlement_progress", 0) >= 2
        or (
            state.success_ledger.get("order_progress", 0) >= 1
            and (strong_success_signal or success_ledger_medium)
        )
        or (
            truth_signal
            and state.success_ledger.get("proof_progress", 0) >= 2
            and (
                state.axis_values.get("political_leverage", 0) >= 3
                or len(positive_stances) >= 1
            )
        )
    )
    successful_costly_resolution_signal = (
        closeout_reached
        and truth_signal
        and (
            strong_success_signal
            or success_ledger_high
            or success_ledger_medium
            or len(positive_stances) >= 1
        )
        and (
            moderate_cost_signal
            or cost_ledger_medium
            or public_cost >= 1
            or relationship_cost >= 1
            or procedural_cost >= 1
            or coercion_cost >= 1
        )
    )
    collapse_lock_signal = (
        pressure_axis_max_hits >= 2
        or (pressure_axis_near_max_hits >= 2 and state.collapse_pressure_streak >= 2)
        or len(negative_stances) >= 2
        or (resource_pressure_value >= 4 and public_pressure_value >= 3)
        or (institutional_pressure_value >= 4 and public_pressure_value >= 3)
    )
    collapse_reframed_pyrrhic_signal = (
        current_on_final_beat
        and closeout_reached
        and successful_costly_resolution_signal
        and binding_success_signal
        and last_turn_stabilizing_success
        and (strong_cost_signal or cost_ledger_high or pressure_axis_max_hits >= 1)
        and not pressure_safe
        and (pressure_axis_max_hits >= 1 or severe_pressure_signal or state.collapse_pressure_streak >= 1)
        and pressure_axis_max_hits <= 1
        and not last_turn_breakdown_signal
        and not collapse_lock_signal
    )
    mandate_preserved_pyrrhic_signal = (
        current_on_final_beat
        and closeout_reached
        and binding_success_signal
        and last_turn_mandate_preserved_signal
        and (
            public_cost >= 2
            or relationship_cost >= 1
            or coercion_cost >= 1
            or public_pressure_value >= 3
        )
        and not collapse_lock_signal
    )
    recovered_binding_mixed_signal = (
        current_on_final_beat
        and closeout_reached
        and last_turn_binding_progress
        and last_turn_recovery_signal
        and (
            not last_turn_pressure_increases
            or set(last_turn_pressure_increases) <= {"exposure_risk", "system_integrity"}
        )
        and len(last_turn_negative_stances) == 0
        and pressure_axis_max_hits == 0
        and public_pressure_value <= 1
        and relationship_cost <= 1
        and coercion_cost == 0
    )
    recovered_stable_mixed_signal = (
        current_on_final_beat
        and closeout_reached
        and truth_signal
        and (strong_success_signal or success_ledger_high or len(positive_stances) >= 2)
        and not severe_pressure_signal
        and pressure_safe
        and public_pressure_value <= 1
        and resource_pressure_value <= 1
        and institutional_pressure_value <= 1
        and coercion_cost == 0
        and (relationship_cost <= 1 or relationship_recovered)
    )

    def collapse_allowed() -> bool:
        if collapse_reframed_pyrrhic_signal or mandate_preserved_pyrrhic_signal:
            return False
        if runtime_profile in {"blackout_council_play", "warning_record_play"} and closeout_reached:
            if public_pressure_value >= 3 and (state.collapse_pressure_streak >= 1 or relationship_cost >= 1):
                return True
        if collapse_rule is not None and _conditions_match(collapse_rule.conditions, plan, state) and collapse_ready:
            return True
        pressure_axis_id, pressure_value = _highest_pressure_axis_value(plan, state)
        pressure_axis = next(axis for axis in plan.axes if axis.axis_id == pressure_axis_id)
        return pressure_value >= pressure_axis.max_value and collapse_ready

    def pyrrhic_allowed() -> bool:
        strict_match = (
            current_on_final_beat
            and pyrrhic_rule is not None
            and _conditions_match(pyrrhic_rule.conditions, plan, state)
        )
        if strict_match:
            return True
        if runtime_profile in {"archive_vote_play", "bridge_ration_play", "harbor_quarantine_play", "warning_record_play"} and recovered_stable_mixed_signal:
            return False
        if not (enable_pyrrhic_judge_relaxation and proposed_ending_id == "pyrrhic" and closeout_reached):
            return False
        has_success_signal = any(
            state.axis_values.get(axis.axis_id, axis.starting_value) >= max(axis.max_value - 2, axis.min_value + 1)
            for axis in non_pressure_axes
        ) or bool(positive_stances)
        relaxed_cost_threshold = min(2, max((axis.max_value for axis in pressure_axes), default=2))
        has_cost_signal = any(
            state.axis_values.get(axis.axis_id, axis.starting_value) >= min(3, axis.max_value)
            for axis in pressure_axes
        ) or any(
            state.axis_values.get(axis.axis_id, axis.starting_value) >= relaxed_cost_threshold
            for axis in pressure_axes
        ) or any(
            state.stance_values.get(stance.stance_id, stance.starting_value) <= -1
            for stance in plan.stances
        ) or state.collapse_pressure_streak >= 1
        event_signal = closeout_reached or (
            pyrrhic_rule is not None and any(item in state.discovered_event_ids for item in pyrrhic_rule.conditions.required_events)
        )
        profile_relaxed_signal = profile_prefers_pyrrhic_fallback(
            plan.closeout_profile,
            success_signal=has_success_signal or success_ledger_medium,
            truth_signal=truth_signal,
            moderate_cost_signal=moderate_cost_signal or cost_ledger_medium,
            strong_cost_signal=has_cost_signal or cost_ledger_high,
            severe_pressure_signal=severe_pressure_signal,
        )
        if runtime_profile == "archive_vote_play":
            profile_relaxed_signal = False
        runtime_relaxed_signal = False
        if runtime_profile == "bridge_ration_play":
            runtime_relaxed_signal = truth_signal and event_signal and (
                resource_pressure_value >= 2
                or public_cost >= 1
                or relationship_cost >= 1
                or procedural_cost >= 1
            )
        elif runtime_profile == "harbor_quarantine_play":
            runtime_relaxed_signal = truth_signal and event_signal and (
                resource_pressure_value >= 2
                or public_cost >= 1
                or relationship_cost >= 1
                or coercion_cost >= 1
            )
        elif runtime_profile == "blackout_council_play":
            runtime_relaxed_signal = truth_signal and event_signal and (
                public_pressure_value >= 2
                or public_cost >= 1
                or relationship_cost >= 1
            )
        elif runtime_profile == "warning_record_play":
            runtime_relaxed_signal = truth_signal and event_signal and (
                public_pressure_value >= 2
                or public_cost >= 1
                or procedural_cost >= 1
                or institutional_pressure_value >= 2
            )
        semantic_profile_relaxed_signal = (
            plan.closeout_profile in {"record_exposure_closeout", "logistics_cost_closeout"}
            and truth_signal
            and event_signal
            and moderate_cost_signal
        )
        if runtime_profile == "archive_vote_play":
            semantic_profile_relaxed_signal = False
        return truth_signal and event_signal and (
            ((has_success_signal or success_ledger_medium) and ((has_cost_signal or cost_ledger_medium) or profile_relaxed_signal or runtime_relaxed_signal))
            or semantic_profile_relaxed_signal
        )

    def mixed_allowed() -> bool:
        if not current_on_final_beat or not closeout_reached:
            return False
        if recovered_binding_mixed_signal:
            return True
        if runtime_profile in {"archive_vote_play", "bridge_ration_play", "harbor_quarantine_play", "warning_record_play"} and recovered_stable_mixed_signal:
            return True
        if runtime_profile == "archive_vote_play":
            return truth_signal and (strong_success_signal or success_ledger_medium) and pressure_safe and public_cost == 0 and coercion_cost == 0 and relationship_cost <= 1
        if runtime_profile in {"bridge_ration_play", "harbor_quarantine_play"}:
            return pressure_safe and truth_signal and state.success_ledger.get("order_progress", 0) >= 1 and public_cost == 0 and coercion_cost == 0 and not (strong_cost_signal or cost_ledger_high)
        if runtime_profile == "blackout_council_play":
            return public_pressure_value <= 1 and pressure_safe and truth_signal and (strong_success_signal or success_ledger_high) and not (strong_cost_signal or cost_ledger_high)
        if runtime_profile == "warning_record_play":
            return public_pressure_value <= 1 and pressure_safe and truth_signal and (strong_success_signal or success_ledger_high) and public_cost <= 1 and not cost_ledger_high
        return pressure_safe and (strong_success_signal or success_ledger_high) and truth_signal and not (strong_cost_signal or cost_ledger_high)

    if proposed_ending_id == "collapse" and (collapse_reframed_pyrrhic_signal or mandate_preserved_pyrrhic_signal):
        return _ending_by_id(plan, "pyrrhic"), "collapse_reframed:pyrrhic"
    if proposed_ending_id == "collapse" and collapse_allowed():
        return _ending_by_id(plan, "collapse"), "judge:collapse"
    if proposed_ending_id == "pyrrhic" and pyrrhic_allowed():
        reason = "judge:pyrrhic"
        if pyrrhic_rule is None or not _conditions_match(pyrrhic_rule.conditions, plan, state):
            reason = "judge_relaxed:pyrrhic"
        return _ending_by_id(plan, "pyrrhic"), reason
    if proposed_ending_id == "mixed" and mixed_allowed():
        return _ending_by_id(plan, "mixed"), "judge:mixed"
    if recovered_binding_mixed_signal:
        reason = "final_beat_handoff:mixed" if final_beat_handoff else "turn_cap:mixed" if turn_cap_reached else "final_beat_default:mixed"
        return _ending_by_id(plan, "mixed"), reason

    for rule in sorted(plan.ending_rules, key=lambda item: (item.priority, item.ending_id)):
        if rule.ending_id == "mixed":
            continue
        if rule.ending_id == "collapse":
            if collapse_reframed_pyrrhic_signal or mandate_preserved_pyrrhic_signal:
                continue
            if _conditions_match(rule.conditions, plan, state) and collapse_ready:
                return _ending_by_id(plan, "collapse"), "ending_rule:collapse"
            continue
        if not current_on_final_beat:
            continue
        if _conditions_match(rule.conditions, plan, state):
            return _ending_by_id(plan, rule.ending_id), f"ending_rule:{rule.ending_id}"
    pressure_axis_id, pressure_value = _highest_pressure_axis_value(plan, state)
    pressure_axis = next(axis for axis in plan.axes if axis.axis_id == pressure_axis_id)
    if pressure_value >= pressure_axis.max_value and collapse_ready and not (collapse_reframed_pyrrhic_signal or mandate_preserved_pyrrhic_signal):
        reason = "pressure_streak:collapse" if use_tuned_ending_policy else "pressure_overflow:collapse"
        return _ending_by_id(plan, "collapse"), reason
    if final_beat_completed:
        if collapse_reframed_pyrrhic_signal or mandate_preserved_pyrrhic_signal:
            return _ending_by_id(plan, "pyrrhic"), "collapse_reframed:pyrrhic"
        if recovered_binding_mixed_signal:
            reason = "final_beat_handoff:mixed" if final_beat_handoff else "final_beat_default:mixed"
            return _ending_by_id(plan, "mixed"), reason
        for rule in plan.ending_rules:
            if rule.ending_id == "pyrrhic" and _conditions_match(rule.conditions, plan, state):
                return _ending_by_id(plan, "pyrrhic"), "ending_rule:pyrrhic"
        if runtime_profile == "archive_vote_play" and mixed_allowed():
            reason = "final_beat_handoff:mixed" if final_beat_handoff else "final_beat_default:mixed"
            return _ending_by_id(plan, "mixed"), reason
        if mixed_allowed():
            reason = "final_beat_handoff:mixed" if final_beat_handoff else "final_beat_default:mixed"
            return _ending_by_id(plan, "mixed"), reason
        if profile_prefers_pyrrhic_fallback(
            plan.closeout_profile,
            success_signal=strong_success_signal or success_ledger_medium,
            truth_signal=truth_signal,
            moderate_cost_signal=moderate_cost_signal or cost_ledger_medium,
            strong_cost_signal=strong_cost_signal or cost_ledger_high,
            severe_pressure_signal=severe_pressure_signal,
        ):
            return _ending_by_id(plan, "pyrrhic"), "profile_closeout:pyrrhic"
        if (strong_success_signal or success_ledger_high) and (strong_cost_signal or cost_ledger_high) and truth_signal:
            return _ending_by_id(plan, "pyrrhic"), "final_beat_cost:pyrrhic"
        if severe_pressure_signal or collapse_allowed():
            return _ending_by_id(plan, "collapse"), "final_beat_pressure:collapse"
    if turn_cap_reached:
        if collapse_reframed_pyrrhic_signal or mandate_preserved_pyrrhic_signal:
            return _ending_by_id(plan, "pyrrhic"), "collapse_reframed:pyrrhic"
        if severe_pressure_signal or collapse_allowed():
            return _ending_by_id(plan, "collapse"), "turn_cap_pressure:collapse"
        if recovered_binding_mixed_signal:
            return _ending_by_id(plan, "mixed"), "turn_cap:mixed"
        if mixed_allowed():
            return _ending_by_id(plan, "mixed"), "turn_cap:mixed"
        if proposed_ending_id == "pyrrhic" and not collapse_allowed() and ((success_ledger_medium and cost_ledger_medium) or (truth_signal and cost_ledger_medium)):
            return _ending_by_id(plan, "pyrrhic"), "turn_cap_judge:pyrrhic"
        if current_on_final_beat and (strong_success_signal or success_ledger_high) and (strong_cost_signal or cost_ledger_high) and truth_signal:
            return _ending_by_id(plan, "pyrrhic"), "turn_cap_cost:pyrrhic"
        ending_id = "collapse" if not current_on_final_beat else "pyrrhic"
        reason = "turn_cap_force:collapse" if not current_on_final_beat else "turn_cap_force:pyrrhic"
        return _ending_by_id(plan, ending_id), reason
    return None, None


def finalize_turn_ending(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    ending_context: TurnEndingGateContext,
    proposed_ending_id: str | None = None,
    use_tuned_ending_policy: bool = True,
    enable_pyrrhic_judge_relaxation: bool = True,
) -> PlayResolutionEffect:
    ending, ending_trigger_reason = determine_ending(
        plan,
        state,
        resolution=resolution,
        final_beat_completed=ending_context.final_beat_completed,
        final_beat_handoff=ending_context.final_beat_handoff,
        turn_cap_reached=ending_context.turn_cap_reached,
        use_tuned_ending_policy=use_tuned_ending_policy,
        proposed_ending_id=proposed_ending_id,
        enable_pyrrhic_judge_relaxation=enable_pyrrhic_judge_relaxation,
    )
    if ending is not None:
        state.status = "completed"
        state.ending = ending
        state.suggested_actions = []
    return resolution.model_copy(
        update={
            "ending_id": ending.ending_id if ending else None,
            "ending_trigger_reason": ending_trigger_reason,
        }
    )
