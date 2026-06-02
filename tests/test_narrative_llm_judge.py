from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rpg_backend.responses_transport import ResponsesJSONResponse
from tools.rpg_eval.narrative_llm_judge import (
    DEFAULT_GOLD_SET,
    LLMJudgeInputPackage,
    evaluate_with_llm_judge,
    load_gold_set,
    run_gold_set_evaluation,
)


class _StaticJudgeGateway:
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
    case = report.cases[0]
    assert case.status == "pass"
    assert Path(case.trace_path).exists()
    assert Path(case.summary_path).exists()
    assert Path(case.llm_input_path).exists()
    assert Path(case.llm_result_path).exists()
    assert "Proof that Evan signed the side letter first" not in Path(case.llm_input_path).read_text()


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
    gateway = _StaticJudgeGateway(_judge_payload(status="warn"))

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
    gateway = _StaticJudgeGateway(payload)

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


def test_llm_judge_parse_failure_writes_failure_report(tmp_path: Path) -> None:
    malformed_payload = _judge_payload(status="pass")
    malformed_payload.pop("scores")
    gateway = _StaticJudgeGateway(malformed_payload)
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


def test_report_aggregate_tracks_deterministic_vs_llm_disagreement(tmp_path: Path) -> None:
    gateway = _StaticJudgeGateway(_judge_payload(status="warn"))
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
