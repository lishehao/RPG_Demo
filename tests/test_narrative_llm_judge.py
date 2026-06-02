from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rpg_backend.responses_transport import ResponsesJSONResponse
from tools.rpg_eval import narrative_llm_judge as judge_module
from tools.rpg_eval.narrative_llm_judge import (
    DEFAULT_GOLD_SET,
    LLMJudgeInputPackage,
    evaluate_with_llm_judge,
    load_gold_set,
    run_gold_set_evaluation,
)
from tools.rpg_eval.narrative_mock_user import AgentLoopEvent, MockUserRuntimeError


class _StaticJudgeClient:
    model = "deepseek-v4-flash"

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        operation_name: str,
        max_output_tokens: int | None = None,
    ) -> ResponsesJSONResponse:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_payload": user_payload,
                "operation_name": operation_name,
                "max_output_tokens": max_output_tokens,
            }
        )
        return ResponsesJSONResponse(
            payload=self.payload,
            response_id="judge-static",
            usage={},
            input_characters=len(json.dumps(user_payload)),
        )


def _judge_payload(status: str = "pass") -> dict[str, Any]:
    score = 0.86 if status == "pass" else 0.66 if status == "warn" else 0.3
    return {
        "schema_version": "llm_judge.v1",
        "source": "fake_gateway",
        "model": "placeholder",
        "gateway": "placeholder",
        "status": status,
        "scores": {
            "agency": score,
            "role_consistency": score,
            "objective_progress": score,
            "consequence_continuity": score,
            "leverage_payoff": score,
            "safety_contract": score,
            "trajectory_quality": score,
            "narrative_coherence": score,
            "hidden_info_safety": score,
        },
        "violations": [
            {
                "code": "judge_disagreement_probe",
                "severity": "warn",
                "rationale": "Static judge intentionally disagrees for test coverage.",
                "evidence": ["trajectory_judge.status:pass"],
            }
        ]
        if status == "warn"
        else [],
        "expectation_matches": ["structured evidence parsed"],
        "expectation_misses": [],
        "reviewer_summary": f"Static judge returned {status}.",
        "confidence": 0.81,
        "deterministic_disagreement": False,
    }


def test_gold_set_schema_parses_smoke_catalog() -> None:
    gold_set = load_gold_set(DEFAULT_GOLD_SET)

    assert gold_set.schema_version == "narrative_agent_gold_set.v1"
    assert gold_set.gold_set_id == "narrative_agent_smoke"
    assert gold_set.cases[0].mock_user.policy == "leverage_seeker"
    assert gold_set.cases[0].expected.leverage_payoff_required is True


def test_gold_set_runner_produces_report_and_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "narrative_llm_judge_report.json"
    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=output,
        mode="case",
        llm_judge_mode="fake",
    )

    assert output.exists()
    assert report.aggregate.case_count == 1
    assert report.aggregate.gates["gold_set_loaded"] is True
    assert report.aggregate.gates["mock_user_runs_completed"] is True
    assert report.aggregate.gates["llm_judge_present"] is True
    assert report.aggregate.gates["llm_required_expectations_met"] is True
    case = report.cases[0]
    assert case.status == "pass"
    assert Path(case.trace_path).exists()
    assert Path(case.summary_path).exists()
    assert Path(case.llm_input_path).exists()
    assert Path(case.llm_result_path).exists()
    assert "Proof that Evan signed the side letter first" not in Path(case.llm_input_path).read_text()


def test_gold_set_runner_writes_report_for_runtime_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_runtime_failure(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise MockUserRuntimeError(
            "turn 1 advance failed: POST /turns failed: 502 llm_invalid_json",
            session_id="sess_runtime_fail",
            action_loop=[
                AgentLoopEvent(
                    event_index=0,
                    turn_index=1,
                    action_type="runtime_retry",
                    summary="Retry live turn after transient runtime error.",
                    payload={
                        "attempt": 1,
                        "will_retry": True,
                        "max_retries": 1,
                        "error_type": "RuntimeError",
                        "message": "502 llm_invalid_json",
                    },
                )
            ],
            runtime_retry_count=1,
        )

    monkeypatch.setattr(judge_module, "run_mock_user_episode", _raise_runtime_failure)
    output = tmp_path / "report.json"

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=output,
        mode="fixture",
        llm_judge_mode="fake",
    )

    assert output.exists()
    assert report.status == "validation_failed"
    assert report.aggregate.gates["runtime_completed"] is False
    assert report.aggregate.gates["mock_user_runs_completed"] is False
    case = report.cases[0]
    assert case.runtime_error is not None
    assert case.runtime_error.status == "validation_failed"
    assert case.runtime_error.session_id == "sess_runtime_fail"
    assert case.runtime_error.runtime_retry_count == 1
    assert case.deterministic_summary["runtime_retry_count"] == 1
    assert Path(case.trace_path).exists()
    assert Path(case.summary_path).exists()
    assert Path(case.llm_input_path).exists()
    assert Path(case.llm_result_path).exists()
    trace_rows = [json.loads(line) for line in Path(case.trace_path).read_text().splitlines()]
    assert [row["record_type"] for row in trace_rows] == ["loop_event", "runtime_failure"]
    assert json.loads(Path(case.llm_result_path).read_text())["schema_version"] == "runtime_failure.v1"


def test_gold_set_runner_writes_report_for_adapter_construction_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_adapter_failure(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise RuntimeError("live adapter could not authenticate reviewer")

    monkeypatch.setattr(judge_module, "_adapter_for_case", _raise_adapter_failure)
    output = tmp_path / "report.json"

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=output,
        mode="fixture",
        llm_judge_mode="fake",
    )

    assert output.exists()
    assert report.status == "validation_failed"
    assert report.aggregate.gates["runtime_completed"] is False
    assert report.aggregate.gates["mock_user_runs_completed"] is False
    case = report.cases[0]
    assert case.runtime_error is not None
    assert case.runtime_error.error_type == "RuntimeError"
    assert "could not authenticate reviewer" in case.runtime_error.message
    assert Path(case.trace_path).exists()
    assert Path(case.summary_path).exists()
    assert Path(case.llm_input_path).exists()
    assert Path(case.llm_result_path).exists()


def test_fake_judge_enforces_required_ending_expectation(tmp_path: Path) -> None:
    gold_set_data = json.loads(DEFAULT_GOLD_SET.read_text())
    gold_set_data["cases"][0]["expected"]["ending_required"] = True
    gold_set_path = tmp_path / "ending_required_gold_set.json"
    gold_set_path.write_text(json.dumps(gold_set_data), encoding="utf-8")

    report = run_gold_set_evaluation(
        gold_set_path=gold_set_path,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
    )

    case = report.cases[0]
    assert report.status == "fail"
    assert case.deterministic_status == "fail"
    assert case.llm_status == "fail"
    assert case.llm_judge is not None
    assert "ending_required" in case.llm_judge.expectation_misses
    assert report.aggregate.gates["llm_required_expectations_met"] is False


def test_llm_judge_input_includes_deterministic_evidence(tmp_path: Path) -> None:
    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
    )
    package = LLMJudgeInputPackage.model_validate(
        json.loads(Path(report.cases[0].llm_input_path).read_text())
    )

    assert package.gold_case["expected"]["hidden_info_must_not_leak"] is True
    assert package.deterministic_summary["trajectory_status"] == "pass"
    assert package.trajectory_judge["schema_version"] == "trajectory_judge.v1"
    assert package.turn_evidence
    assert package.turn_evidence[0]["step_judge"]["status"] == "pass"
    assert package.turn_evidence[0]["contract_judge"]["status"] == "pass"
    assert package.turn_evidence[0]["agent_plan_summary"]["available"] is True
    assert package.leverage_payoff_evidence
    leverage_evidence = package.leverage_payoff_evidence[0]
    assert leverage_evidence["status"] == "observed"
    assert "target_npc_pulse_shift" in leverage_evidence["payoff_signals"]
    assert leverage_evidence["target_npc_pulse"][0]["shift"] != "steady"


def test_llm_judge_strict_parser_with_static_gateway(tmp_path: Path) -> None:
    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
    )
    package = LLMJudgeInputPackage.model_validate(
        json.loads(Path(report.cases[0].llm_input_path).read_text())
    )
    gateway = _StaticJudgeClient(_judge_payload(status="warn"))

    result = evaluate_with_llm_judge(
        package=package,
        gateway=gateway,
        source="deepseek_v4_flash_gateway",
        gateway_label="https://api.deepseek.com",
        deterministic_status_value="pass",
    )

    assert result.schema_version == "llm_judge.v1"
    assert result.source == "deepseek_v4_flash_gateway"
    assert result.model == "deepseek-v4-flash"
    assert result.gateway == "https://api.deepseek.com"
    assert result.status == "warn"
    assert result.deterministic_disagreement is True
    assert gateway.calls[0]["operation_name"] == "rpg_eval.narrative_llm_judge"
    assert "trajectory_judge" in gateway.calls[0]["user_payload"]


def test_llm_judge_parser_fills_missing_model_gateway_from_context(tmp_path: Path) -> None:
    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
    )
    package = LLMJudgeInputPackage.model_validate(
        json.loads(Path(report.cases[0].llm_input_path).read_text())
    )
    payload = _judge_payload(status="pass")
    payload.pop("model")
    payload.pop("gateway")
    gateway = _StaticJudgeClient(payload)

    result = evaluate_with_llm_judge(
        package=package,
        gateway=gateway,
        source="deepseek_v4_flash_gateway",
        gateway_label="https://api.deepseek.com",
        deterministic_status_value="pass",
    )

    assert result.status == "pass"
    assert result.model == "deepseek-v4-flash"
    assert result.gateway == "https://api.deepseek.com"
    assert result.source == "deepseek_v4_flash_gateway"


def test_llm_judge_parser_strips_allowlisted_case_id_metadata(tmp_path: Path) -> None:
    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
    )
    package = LLMJudgeInputPackage.model_validate(
        json.loads(Path(report.cases[0].llm_input_path).read_text())
    )
    payload = _judge_payload(status="pass")
    payload["case_id"] = "merger_audit_fixture_smoke"
    gateway = _StaticJudgeClient(payload)

    result = evaluate_with_llm_judge(
        package=package,
        gateway=gateway,
        source="deepseek_v4_flash_gateway",
        gateway_label="https://api.deepseek.com",
        deterministic_status_value="pass",
    )

    assert result.status == "pass"
    assert "case_id" not in result.model_dump()


@pytest.mark.parametrize(
    ("raw_confidence", "expected_confidence"),
    [
        ("high", 0.9),
        (" HIGH confidence ", 0.9),
        ("medium-confidence", 0.6),
        ("LOW", 0.3),
    ],
)
def test_llm_judge_parser_normalizes_confidence_labels(
    tmp_path: Path,
    raw_confidence: str,
    expected_confidence: float,
) -> None:
    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
    )
    package = LLMJudgeInputPackage.model_validate(
        json.loads(Path(report.cases[0].llm_input_path).read_text())
    )
    payload = _judge_payload(status="pass")
    payload["confidence"] = raw_confidence
    gateway = _StaticJudgeClient(payload)

    result = evaluate_with_llm_judge(
        package=package,
        gateway=gateway,
        source="deepseek_v4_flash_gateway",
        gateway_label="https://api.deepseek.com",
        deterministic_status_value="pass",
    )

    assert result.status == "pass"
    assert result.confidence == pytest.approx(expected_confidence)


def test_unknown_confidence_label_still_writes_failure_report(tmp_path: Path) -> None:
    malformed_payload = _judge_payload(status="pass")
    malformed_payload["confidence"] = "certain"
    gateway = _StaticJudgeClient(malformed_payload)

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    case = report.cases[0]
    assert report.status == "validation_failed"
    assert report.aggregate.gates["llm_judge_present"] is False
    assert case.llm_judge is None
    assert case.llm_judge_error is not None
    assert "confidence" in case.llm_judge_error.message
    assert case.llm_judge_error.safe_payload_summary["confidence"] == "certain"
    assert case.llm_judge_error.normalized_payload_summary["confidence"] == "certain"


def test_out_of_range_numeric_confidence_still_writes_failure_report(tmp_path: Path) -> None:
    malformed_payload = _judge_payload(status="pass")
    malformed_payload["confidence"] = 1.2
    gateway = _StaticJudgeClient(malformed_payload)

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    case = report.cases[0]
    assert report.status == "validation_failed"
    assert report.aggregate.gates["llm_judge_present"] is False
    assert case.llm_judge_error is not None
    assert "confidence" in case.llm_judge_error.message
    assert case.llm_judge_error.safe_payload_summary["confidence"] == 1.2
    assert case.llm_judge_error.normalized_payload_summary["confidence"] == 1.2


def test_llm_judge_parser_normalizes_expectation_maps(tmp_path: Path) -> None:
    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
    )
    package = LLMJudgeInputPackage.model_validate(
        json.loads(Path(report.cases[0].llm_input_path).read_text())
    )
    payload = _judge_payload(status="pass")
    payload["expectation_matches"] = {
        "hidden_info_must_not_leak": True,
        "trajectory_status_allowed": {"status": "pass", "evidence": ["trajectory:pass"]},
    }
    payload["expectation_misses"] = {
        "leverage_payoff_required": "not enough payoff evidence",
    }
    gateway = _StaticJudgeClient(payload)

    result = evaluate_with_llm_judge(
        package=package,
        gateway=gateway,
        source="deepseek_v4_flash_gateway",
        gateway_label="https://api.deepseek.com",
        deterministic_status_value="pass",
    )

    assert "hidden_info_must_not_leak:true" in result.expectation_matches
    assert any(entry.startswith("trajectory_status_allowed:") for entry in result.expectation_matches)
    assert result.expectation_misses == [
        "leverage_payoff_required:not enough payoff evidence"
    ]


def test_llm_judge_parser_drops_false_miss_map_entries(tmp_path: Path) -> None:
    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
    )
    package = LLMJudgeInputPackage.model_validate(
        json.loads(Path(report.cases[0].llm_input_path).read_text())
    )
    payload = _judge_payload(status="pass")
    payload["expectation_misses"] = {
        "leverage_payoff_required": False,
        "leverage_usage_required": "pass",
        "hidden_info_must_not_leak": {"status": "satisfied"},
        "objective_progress": {"missed": False},
        "stage_progression": None,
        "real_miss": True,
        "another_miss": {"status": "failed", "reason": "stage was skipped"},
    }
    gateway = _StaticJudgeClient(payload)

    result = evaluate_with_llm_judge(
        package=package,
        gateway=gateway,
        source="deepseek_v4_flash_gateway",
        gateway_label="https://api.deepseek.com",
        deterministic_status_value="pass",
    )

    assert result.expectation_misses == [
        "real_miss:true",
        "another_miss:status=failed; reason=stage was skipped",
    ]


def test_llm_judge_parse_failure_writes_failure_report(tmp_path: Path) -> None:
    malformed_payload = _judge_payload(status="pass")
    malformed_payload.pop("scores")
    gateway = _StaticJudgeClient(malformed_payload)
    output = tmp_path / "report.json"

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=output,
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    assert output.exists()
    assert report.status == "validation_failed"
    assert report.aggregate.gates["mock_user_runs_completed"] is True
    assert report.aggregate.gates["deterministic_evidence_present"] is True
    assert report.aggregate.gates["llm_judge_present"] is False
    case = report.cases[0]
    assert case.deterministic_status == "pass"
    assert case.llm_status == "fail"
    assert case.status == "fail"
    assert case.llm_judge is None
    assert case.llm_judge_error is not None
    assert case.llm_judge_error.status == "validation_failed"
    assert case.llm_judge_error.deterministic_summary["turn_count"] > 0
    assert Path(case.trace_path).exists()
    assert Path(case.summary_path).exists()
    assert Path(case.llm_input_path).exists()
    error_artifact = json.loads(Path(case.llm_result_path).read_text())
    assert error_artifact["schema_version"] == "llm_judge_error.v1"
    assert error_artifact["safe_payload_summary"]["keys"]
    assert "scores" not in error_artifact["safe_payload_summary"]["keys"]


def test_llm_judge_unapproved_extra_field_still_fails_report(tmp_path: Path) -> None:
    malformed_payload = _judge_payload(status="pass")
    malformed_payload["unapproved_semantic_extra"] = "do not silently accept this"
    gateway = _StaticJudgeClient(malformed_payload)

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    case = report.cases[0]
    assert report.status == "validation_failed"
    assert report.aggregate.gates["llm_judge_present"] is False
    assert case.llm_judge is None
    assert case.llm_judge_error is not None
    assert "unapproved_semantic_extra" in case.llm_judge_error.normalized_payload_summary["keys"]
    assert "Extra inputs are not permitted" in case.llm_judge_error.message


def test_low_llm_scores_with_pass_status_cannot_pass_report(tmp_path: Path) -> None:
    payload = _judge_payload(status="pass")
    payload["scores"] = {dimension: 0.12 for dimension in payload["scores"]}
    payload["reviewer_summary"] = "All rubric dimensions scored at or near maximum."
    gateway = _StaticJudgeClient(payload)

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    case = report.cases[0]
    assert report.status == "fail"
    assert report.aggregate.gates["llm_judge_present"] is True
    assert report.aggregate.gates["llm_score_consistency"] is False
    assert report.aggregate.gates["llm_score_shape_consistency"] is True
    assert report.aggregate.gates["llm_expectation_consistency"] is True
    assert report.aggregate.gates["llm_required_expectations_met"] is True
    assert case.llm_judge is not None
    assert case.llm_judge.status == "pass"
    assert case.llm_consistency is not None
    assert case.llm_consistency.status == "fail"
    assert case.llm_consistency.score_status == "fail"
    assert case.llm_status == "fail"
    assert case.status == "fail"


def test_rubric_weight_like_scores_with_pass_status_fail_shape_gate(tmp_path: Path) -> None:
    gold_set = load_gold_set(DEFAULT_GOLD_SET)
    payload = _judge_payload(status="pass")
    payload["scores"] = dict(gold_set.cases[0].rubric.weights)
    payload["expectation_matches"] = [
        "expected_role_behavior",
        "hidden_info_must_not_leak",
        "leverage_payoff_required",
        "leverage_usage_required",
        "min_turns",
        "required_stage_progression",
        "trajectory_status_allowed",
    ]
    payload["reviewer_summary"] = "All required expectations met and the case passes."
    gateway = _StaticJudgeClient(payload)

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    case = report.cases[0]
    assert report.status == "fail"
    assert report.aggregate.gates["llm_judge_present"] is True
    assert report.aggregate.gates["llm_score_consistency"] is False
    assert report.aggregate.gates["llm_score_shape_consistency"] is False
    assert report.aggregate.gates["llm_required_expectations_met"] is True
    assert case.llm_consistency is not None
    assert case.llm_consistency.status == "fail"
    assert case.llm_consistency.score_shape_status == "fail"
    assert case.llm_consistency.suspicious_score_shape == "rubric_weight_copy"
    assert set(case.llm_consistency.suspicious_score_dimensions) == set(payload["scores"])
    assert any("agency:score=0.120;rubric_weight=0.120" in item for item in case.llm_consistency.evidence)
    assert case.llm_status == "fail"


def test_high_quality_scores_with_pass_status_pass_shape_gate(tmp_path: Path) -> None:
    payload = _judge_payload(status="pass")
    payload["scores"] = {dimension: 0.88 for dimension in payload["scores"]}
    gateway = _StaticJudgeClient(payload)

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    case = report.cases[0]
    assert report.status == "pass"
    assert report.aggregate.gates["llm_score_consistency"] is True
    assert report.aggregate.gates["llm_score_shape_consistency"] is True
    assert case.llm_consistency is not None
    assert case.llm_consistency.score_shape_status == "pass"
    assert case.llm_consistency.suspicious_score_dimensions == []


def test_required_expectation_miss_cannot_pass_report(tmp_path: Path) -> None:
    payload = _judge_payload(status="pass")
    payload["expectation_matches"] = ["hidden_info_must_not_leak"]
    payload["expectation_misses"] = ["leverage_payoff_required"]
    payload["reviewer_summary"] = "The run passes overall despite one miss."
    gateway = _StaticJudgeClient(payload)

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    case = report.cases[0]
    assert report.status == "fail"
    assert report.aggregate.gates["llm_score_consistency"] is True
    assert report.aggregate.gates["llm_expectation_consistency"] is True
    assert report.aggregate.gates["llm_required_expectations_met"] is False
    assert case.llm_consistency is not None
    assert case.llm_consistency.status == "fail"
    assert case.llm_consistency.required_expectation_status == "fail"
    assert case.llm_consistency.required_expectation_matches == ["hidden_info_must_not_leak"]
    assert case.llm_consistency.required_expectation_misses == ["leverage_payoff_required"]
    assert case.llm_status == "fail"
    assert case.status == "fail"


def test_non_blocking_expectation_miss_can_pass_report(tmp_path: Path) -> None:
    payload = _judge_payload(status="pass")
    payload["expectation_misses"] = ["optional_tone_polish"]
    gateway = _StaticJudgeClient(payload)

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    case = report.cases[0]
    assert report.status == "pass"
    assert report.aggregate.gates["llm_required_expectations_met"] is True
    assert report.aggregate.gates["llm_expectation_consistency"] is True
    assert case.llm_consistency is not None
    assert case.llm_consistency.status == "pass"
    assert case.llm_consistency.required_expectation_misses == []
    assert case.llm_consistency.non_blocking_expectation_misses == ["optional_tone_polish"]


def test_duplicate_expectation_match_and_miss_fails_consistency_gate(tmp_path: Path) -> None:
    payload = _judge_payload(status="pass")
    payload["expectation_matches"] = {
        "leverage_payoff_required": True,
        "hidden_info_must_not_leak": True,
    }
    payload["expectation_misses"] = {
        "leverage_payoff_required": "payoff was not explicit enough",
    }
    gateway = _StaticJudgeClient(payload)

    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    case = report.cases[0]
    assert report.status == "fail"
    assert report.aggregate.gates["llm_judge_present"] is True
    assert report.aggregate.gates["llm_score_consistency"] is True
    assert report.aggregate.gates["llm_expectation_consistency"] is False
    assert report.aggregate.gates["llm_required_expectations_met"] is False
    assert case.llm_consistency is not None
    assert case.llm_consistency.status == "fail"
    assert case.llm_consistency.expectation_status == "fail"
    assert case.llm_consistency.expectation_conflicts == ["leverage_payoff_required"]
    assert case.llm_consistency.required_expectation_misses == ["leverage_payoff_required"]
    assert case.llm_status == "fail"


def test_report_aggregate_tracks_deterministic_vs_llm_disagreement(tmp_path: Path) -> None:
    gateway = _StaticJudgeClient(_judge_payload(status="warn"))
    report = run_gold_set_evaluation(
        gold_set_path=DEFAULT_GOLD_SET,
        output_path=tmp_path / "report.json",
        mode="fixture",
        llm_judge_mode="fake",
        gateway=gateway,
    )

    assert report.cases[0].deterministic_status == "pass"
    assert report.cases[0].llm_status == "warn"
    assert report.cases[0].disagreement is True
    assert report.aggregate.disagreement_count == 1
    assert report.aggregate.llm_status_counts == {"warn": 1}


def test_live_modes_require_explicit_allow_live_llm(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires --allow-live-llm"):
        run_gold_set_evaluation(
            gold_set_path=DEFAULT_GOLD_SET,
            output_path=tmp_path / "report.json",
            mode="live",
            llm_judge_mode="fake",
        )
