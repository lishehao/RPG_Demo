from __future__ import annotations

import json

from tools.rpg_eval.catalog import default_case_catalog, default_player_policies
from tools.rpg_eval.contracts import EvalEvent
from tools.rpg_eval.oracles import validate_episode_trace
from tools.rpg_eval.runner import run_dry_eval, run_unified_runtime_eval


def test_default_eval_v3_catalog_is_small_and_explicit() -> None:
    cases = default_case_catalog()
    policies = default_player_policies()

    assert len(cases) == 3
    assert len(policies) == 5
    assert all(case.expected_shells for case in cases)
    assert all(case.oracle.required_state_keys for case in cases)


def test_eval_v3_oracle_reports_missing_trace() -> None:
    case = default_case_catalog()[0]

    failures = validate_episode_trace(case, [])

    assert failures
    assert failures[0].category == "artifact"


def test_eval_v3_oracle_checks_turn_count_and_state_keys() -> None:
    case = default_case_catalog()[0]
    events = [
        EvalEvent(
            event_index=0,
            event_type="runtime_output",
            case_id=case.case_id,
            payload={"narration": "A valid turn."},
        ),
        EvalEvent(
            event_index=1,
            event_type="state_delta",
            case_id=case.case_id,
            payload={"public_pressure": 1},
        ),
    ]

    failures = validate_episode_trace(case, events)

    assert {failure.category for failure in failures} == {"trajectory_oracle"}
    assert any("runtime turns" in failure.message for failure in failures)
    assert any("missing required state keys" in failure.message for failure in failures)


def test_eval_v3_dry_run_writes_core_artifacts(tmp_path) -> None:
    paths = run_dry_eval(tmp_path)

    assert set(paths) == {
        "run_manifest",
        "cases",
        "player_policies",
        "case_summary",
        "gate_summary",
    }
    for path in paths.values():
        assert path.exists()

    gate_summary = json.loads(paths["gate_summary"].read_text())
    assert gate_summary["manifest"]["eval_version"] == "v3"
    assert gate_summary["passed_case_count"] == 3
    assert gate_summary["gate_pass_counts"]["author_valid"] == 3


def test_eval_v3_runtime_run_writes_unified_episode_artifacts(tmp_path) -> None:
    paths = run_unified_runtime_eval(tmp_path, case_limit=1, policy_limit=3, max_turns=6)

    assert set(paths) == {
        "run_manifest",
        "cases",
        "player_policies",
        "episode_events",
        "episode_trace",
        "case_summary",
        "gate_summary",
    }
    for path in paths.values():
        assert path.exists()

    events = json.loads(paths["episode_events"].read_text())
    event_types = {event["event_type"] for event in events}
    assert {
        "author_step",
        "publish_step",
        "session_start",
        "player_action",
        "runtime_output",
        "state_delta",
    } <= event_types

    trace_lines = [line for line in paths["episode_trace"].read_text().splitlines() if line.strip()]
    assert len(trace_lines) == len(events)
    assert {json.loads(line)["event_type"] for line in trace_lines} == event_types

    runtime_events = [event for event in events if event["event_type"] == "runtime_output"]
    assert runtime_events
    assert all(event["payload"]["post_submit_llm_calls"] == 0 for event in runtime_events)

    gate_summary = json.loads(paths["gate_summary"].read_text())
    assert gate_summary["manifest"]["mode"] == "runtime"
    assert gate_summary["manifest"]["case_count"] == 1
    assert gate_summary["manifest"]["policy_count"] == 3
    assert gate_summary["passed_case_count"] == 1
    assert gate_summary["gate_pass_counts"]["author_valid"] == 1
    assert gate_summary["gate_pass_counts"]["runtime_valid"] == 1
    assert gate_summary["gate_pass_counts"]["agency_valid"] == 1
    assert gate_summary["gate_pass_counts"]["trajectory_valid"] == 1
