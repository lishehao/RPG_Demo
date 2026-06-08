from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from tools.rpg_eval.narrative_mock_user import (
    EpisodeMemory,
    MockTurnTrace,
    MockUserConfig,
    judge_episode_trajectory,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_SET_PATH = REPO_ROOT / "tools/rpg_eval/gold_sets/tiny_stories_reliability.json"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts/eval_tiny_stories/reliability_protocol_summary.json"
REQUIRED_CASES = {
    "arbitrary_input_smalltalk",
    "meta_help_input",
    "unsafe_prompt_redirect",
    "laundromat_not_fit_gate",
    "high_drama_awards_supported",
    "multi_turn_correction_supersedes_fact",
    "play_turn_consequence",
}
REQUIRED_FAILURE_CATEGORIES = {
    "environment",
    "provider",
    "schema",
    "unsafe_redirect",
    "not_fit_gate",
    "story_guide_intent",
    "brief_contract",
    "entity_hygiene",
    "opening_recovery",
    "step_judge",
    "trajectory_judge",
    "telemetry_missing",
    "normal_ui_leak",
    "artifact",
}


def _read_protocol(path: Path = GOLD_SET_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _protocol_failures(protocol: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    cases = protocol.get("cases")
    if not isinstance(cases, list):
        return [{"category": "schema", "stage": "load", "message": "cases must be a list"}]
    case_ids = {str(case.get("case_id") or "") for case in cases if isinstance(case, dict)}
    missing = sorted(REQUIRED_CASES.difference(case_ids))
    if missing:
        failures.append({
            "category": "schema",
            "stage": "case_catalog",
            "message": f"missing required cases: {', '.join(missing)}",
        })
    taxonomy = set(str(item) for item in protocol.get("failure_taxonomy") or [])
    missing_taxonomy = sorted(REQUIRED_FAILURE_CATEGORIES.difference(taxonomy))
    if missing_taxonomy:
        failures.append({
            "category": "schema",
            "stage": "failure_taxonomy",
            "message": f"missing failure categories: {', '.join(missing_taxonomy)}",
        })
    for case in cases:
        if not isinstance(case, dict):
            failures.append({"category": "schema", "stage": "case_catalog", "message": "case must be an object"})
            continue
        case_id = str(case.get("case_id") or "")
        if not case.get("surface"):
            failures.append({"category": "schema", "stage": case_id, "message": "surface is required"})
        if not case.get("expected"):
            failures.append({"category": "schema", "stage": case_id, "message": "expected contract is required"})
        if case.get("surface") == "create_story_butler" and not case.get("prompt_sequence"):
            failures.append({"category": "schema", "stage": case_id, "message": "prompt_sequence is required"})
    return failures


def _fixture_trajectory_summary() -> dict[str, Any]:
    trace = MockTurnTrace(
        turn_index=1,
        narrator_ord=2,
        role_id="founder",
        observation_summary={"latest_narrator": "Evan presses the contradiction."},
        selected_action={"chosen_option_index": 0, "selected_option_label": "Show the memo evidence"},
        runtime_output_summary={
            "npc_pulse": [{"npc_id": "evan", "shift": "wary"}],
            "inventory_delta": {"added": ["public contradiction"], "removed": []},
        },
        agent_plan_summary={
            "available": True,
            "stage_phase": "pressure",
            "expected_pressure": "medium",
        },
        step_judge_status="pass",
        step_judge_violation_codes=[],
        contract_judge_status="pass",
        contract_judge_violation_codes=[],
    )
    memory = EpisodeMemory(
        objective="Keep the vote alive while making the contradiction visible.",
        latest_narrator_ord=2,
        narrator_ord_path=[2],
        recent_observations=["Evan presses the contradiction."],
        observed_npc_ids=["evan"],
        npc_pulse_trend={"evan": ["wary"]},
        selected_option_handles=["show"],
        pressure_signal_count=1,
        objective_progress="medium",
    )
    result = judge_episode_trajectory(
        traces=[trace],
        memory=memory,
        config=MockUserConfig(mode="fixture", turn_budget=1, request_agent_trace=True),
        ending_detected=False,
    )
    return result.model_dump(mode="json")


def run_protocol_contract(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    protocol = _read_protocol()
    failures = _protocol_failures(protocol)
    trajectory = _fixture_trajectory_summary()
    case_results = []
    for case in protocol.get("cases") or []:
        case_id = str(case.get("case_id") or "")
        case_failures = [failure for failure in failures if failure["stage"] == case_id]
        status = "fail" if case_failures else "pass"
        evidence = "protocol contract present"
        if case_id == "play_turn_consequence":
            status = "pass" if trajectory["status"] in {"pass", "warn"} else "fail"
            evidence = trajectory["summary"]
        case_results.append({
            "case_id": case_id,
            "surface": case.get("surface"),
            "status": status,
            "evidence": evidence,
            "failure_category_if_bad": (case.get("expected") or {}).get("failure_category_if_bad"),
        })
    payload = {
        "schema_version": "tiny_stories_reliability_protocol_summary.v1",
        "mode": "protocol_contract",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold_set_id": protocol.get("gold_set_id"),
        "status": "fail" if failures or any(case["status"] == "fail" for case in case_results) else "pass",
        "case_count": len(case_results),
        "pass_count": sum(1 for case in case_results if case["status"] == "pass"),
        "failures": failures,
        "cases": case_results,
        "trajectory_judge": trajectory,
        "notes": [
            "This command validates the gold protocol and deterministic trajectory evidence.",
            "Final product preview validation must still use live browser telemetry.",
        ],
    }
    _write_json(output, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tiny Stories reliability protocol checks.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path for summary JSON.")
    args = parser.parse_args()
    payload = run_protocol_contract(Path(args.output))
    print(json.dumps({
        "status": payload["status"],
        "case_count": payload["case_count"],
        "pass_count": payload["pass_count"],
        "output": str(Path(args.output)),
    }, ensure_ascii=False))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
