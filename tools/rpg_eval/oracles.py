from __future__ import annotations

from collections import Counter

from tools.rpg_eval.contracts import (
    EvalCase,
    EvalCaseSummary,
    EvalEvent,
    EvalFailure,
    EvalGateResult,
    EvalGateSummary,
    EvalRunManifest,
)


HARD_GATES = (
    "author_valid",
    "runtime_valid",
    "agency_valid",
    "trajectory_valid",
    "ops_valid",
)


def build_dry_run_case_summary(case: EvalCase) -> EvalCaseSummary:
    gates = [
        EvalGateResult(gate="author_valid", passed=True, evidence_count=1),
        EvalGateResult(gate="runtime_valid", passed=True, evidence_count=1),
        EvalGateResult(gate="agency_valid", passed=True, evidence_count=len(case.required_affordances)),
        EvalGateResult(gate="trajectory_valid", passed=True, evidence_count=len(case.oracle.required_state_keys)),
        EvalGateResult(gate="quality_review_valid", passed=False, evidence_count=0),
        EvalGateResult(gate="ops_valid", passed=True, evidence_count=1),
    ]
    return EvalCaseSummary(case_id=case.case_id, gates=gates)


def summarize_gate_results(
    *,
    manifest: EvalRunManifest,
    case_summaries: list[EvalCaseSummary],
) -> EvalGateSummary:
    gate_pass_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    passed_case_count = 0
    for case_summary in case_summaries:
        if case_summary.passed:
            passed_case_count += 1
        for gate in case_summary.gates:
            if gate.passed:
                gate_pass_counts[gate.gate] += 1
            for failure in gate.failures:
                failure_counts[failure.category] += 1
    return EvalGateSummary(
        manifest=manifest,
        case_summaries=case_summaries,
        passed_case_count=passed_case_count,
        failed_case_count=len(case_summaries) - passed_case_count,
        gate_pass_counts=dict(gate_pass_counts),
        failure_counts=dict(failure_counts),
    )


def validate_episode_trace(case: EvalCase, events: list[EvalEvent]) -> list[EvalFailure]:
    failures: list[EvalFailure] = []
    case_events = [event for event in events if event.case_id == case.case_id]
    if not case_events:
        return [
            EvalFailure(
                category="artifact",
                stage="trace",
                message=f"case {case.case_id} has no trace events",
            )
        ]
    turn_events = [event for event in case_events if event.event_type == "runtime_output"]
    if len(turn_events) < case.oracle.min_turns:
        failures.append(
            EvalFailure(
                category="trajectory_oracle",
                stage="runtime_output",
                message=f"expected at least {case.oracle.min_turns} runtime turns, got {len(turn_events)}",
            )
        )
    observed_keys = {
        key
        for event in case_events
        if event.event_type == "state_delta"
        for key in event.payload.keys()
    }
    missing_keys = [key for key in case.oracle.required_state_keys if key not in observed_keys]
    if missing_keys:
        failures.append(
            EvalFailure(
                category="trajectory_oracle",
                stage="state_delta",
                message="missing required state keys: " + ", ".join(missing_keys),
            )
        )
    return failures


def build_runtime_case_summary(case: EvalCase, events: list[EvalEvent]) -> EvalCaseSummary:
    case_events = [event for event in events if event.case_id == case.case_id]
    author_events = [event for event in case_events if event.event_type == "author_step"]
    session_events = [event for event in case_events if event.event_type == "session_start"]
    runtime_events = [event for event in case_events if event.event_type == "runtime_output"]
    action_events = [event for event in case_events if event.event_type == "player_action"]
    state_events = [event for event in case_events if event.event_type == "state_delta"]
    ending_events = [event for event in case_events if event.event_type == "ending"]
    failure_events = [event for event in case_events if event.event_type == "failure"]

    author_failures: list[EvalFailure] = []
    if not author_events:
        author_failures.append(
            EvalFailure(category="artifact", stage="author_step", message="missing author plan event")
        )
    else:
        plan_payload = author_events[-1].payload
        shell = str(plan_payload.get("story_shell_id") or "")
        if shell not in set(case.expected_shells):
            author_failures.append(
                EvalFailure(
                    category="author_content",
                    stage="author_step",
                    message=f"expected one of {case.expected_shells}, got {shell or '<missing>'}",
                    event_index=author_events[-1].event_index,
                )
            )
        if int(plan_payload.get("segment_count") or 0) < 3:
            author_failures.append(
                EvalFailure(
                    category="schema",
                    stage="author_step",
                    message="compiled plan has fewer than 3 segments",
                    event_index=author_events[-1].event_index,
                )
            )
        if int(plan_payload.get("cast_count") or 0) < 3:
            author_failures.append(
                EvalFailure(
                    category="schema",
                    stage="author_step",
                    message="compiled plan has fewer than 3 cast members",
                    event_index=author_events[-1].event_index,
                )
            )

    runtime_failures = [
        EvalFailure(
            category="runtime_invariant",
            stage=str(event.payload.get("stage") or "runtime"),
            message=str(event.payload.get("message") or "runtime failure"),
            event_index=event.event_index,
        )
        for event in failure_events
    ]
    if not runtime_events:
        runtime_failures.append(
            EvalFailure(category="artifact", stage="runtime_output", message="missing runtime output events")
        )
    if any(not str(event.payload.get("narration") or "").strip() for event in runtime_events):
        runtime_failures.append(
            EvalFailure(
                category="runtime_invariant",
                stage="runtime_output",
                message="one or more runtime outputs have empty narration",
            )
        )

    lanes = {str(event.payload.get("lane_id") or "") for event in action_events if event.payload.get("lane_id")}
    move_families = {
        str(event.payload.get("move_family") or "")
        for event in action_events
        if event.payload.get("move_family")
    }
    agency_failures: list[EvalFailure] = []
    started_policy_ids = {event.policy_id for event in session_events if event.policy_id}
    action_policy_ids = {event.policy_id for event in action_events if event.policy_id}
    missing_action_policy_ids = sorted(started_policy_ids - action_policy_ids)
    if missing_action_policy_ids:
        agency_failures.append(
            EvalFailure(
                category="player_policy",
                stage="player_action",
                message="not every started policy produced a player action: " + ", ".join(missing_action_policy_ids),
            )
        )
    if not started_policy_ids and not action_events:
        agency_failures.append(
            EvalFailure(category="player_policy", stage="player_action", message="no player policies were executed")
        )
    if len(lanes) < 2:
        agency_failures.append(
            EvalFailure(
                category="player_policy",
                stage="player_action",
                message=f"expected at least 2 distinct lanes, got {sorted(lanes)}",
            )
        )
    if len(move_families) < 2:
        agency_failures.append(
            EvalFailure(
                category="player_policy",
                stage="player_action",
                message=f"expected at least 2 distinct move families, got {sorted(move_families)}",
            )
        )

    trajectory_failures = validate_episode_trace(case, case_events)
    final_states_by_policy: dict[str, dict[str, object]] = {}
    for event in state_events:
        if event.policy_id:
            final_states_by_policy[event.policy_id] = event.payload
    if len(final_states_by_policy) >= 2:
        required_keys = case.oracle.required_state_keys or ["turn_index", "segment_index"]
        state_signatures = {
            tuple((key, final_state.get(key)) for key in required_keys)
            for final_state in final_states_by_policy.values()
        }
        divergence = (len(state_signatures) - 1) / max(1, len(final_states_by_policy) - 1)
        if divergence < case.oracle.min_state_divergence:
            trajectory_failures.append(
                EvalFailure(
                    category="trajectory_oracle",
                    stage="state_delta",
                    message=(
                        f"expected state divergence >= {case.oracle.min_state_divergence:.2f}, "
                        f"got {divergence:.2f}"
                    ),
                )
            )
    distinct_endings = {
        str(event.payload.get("ending_id") or "")
        for event in ending_events
        if event.payload.get("ending_id")
    }
    if len(distinct_endings) < case.oracle.min_distinct_endings:
        trajectory_failures.append(
            EvalFailure(
                category="trajectory_oracle",
                stage="ending",
                message=(
                    f"expected at least {case.oracle.min_distinct_endings} distinct endings, "
                    f"got {len(distinct_endings)}"
                ),
            )
        )

    quality_failures: list[EvalFailure] = []
    average_narration_chars = (
        sum(len(str(event.payload.get("narration") or "")) for event in runtime_events) / len(runtime_events)
        if runtime_events
        else 0
    )
    if runtime_events and average_narration_chars < 20:
        quality_failures.append(
            EvalFailure(
                category="author_content",
                stage="quality_review",
                message="average narration is too short for reviewable play output",
            )
        )

    ops_failures: list[EvalFailure] = []
    if not case_events:
        ops_failures.append(EvalFailure(category="artifact", stage="artifact", message="missing case artifacts"))
    if any(event.event_index != index for index, event in enumerate(case_events)):
        # Event indexes are global, so only require monotonic order inside a case.
        ordered = [event.event_index for event in case_events]
        if ordered != sorted(ordered):
            ops_failures.append(
                EvalFailure(category="artifact", stage="artifact", message="case events are not monotonic")
            )

    gates = [
        EvalGateResult(gate="author_valid", passed=not author_failures, evidence_count=len(author_events), failures=author_failures),
        EvalGateResult(gate="runtime_valid", passed=not runtime_failures, evidence_count=len(runtime_events), failures=runtime_failures),
        EvalGateResult(gate="agency_valid", passed=not agency_failures, evidence_count=len(action_events), failures=agency_failures),
        EvalGateResult(gate="trajectory_valid", passed=not trajectory_failures, evidence_count=len(state_events), failures=trajectory_failures),
        EvalGateResult(
            gate="quality_review_valid",
            passed=not quality_failures,
            evidence_count=len(runtime_events),
            failures=quality_failures,
        ),
        EvalGateResult(gate="ops_valid", passed=not ops_failures, evidence_count=len(case_events), failures=ops_failures),
    ]
    primary_failure = next((failure for gate in gates for failure in gate.failures), None)
    return EvalCaseSummary(case_id=case.case_id, gates=gates, primary_failure=primary_failure)
