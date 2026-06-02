from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from rpg_backend.config import Settings, get_settings
from rpg_backend.narrative.gateway import get_narrative_gateway
from rpg_backend.responses_transport import ResponsesJSONResponse
from tools.rpg_eval.narrative_mock_user import (
    LiveHTTPNarrativeAdapter,
    MockUserConfig,
    MockUserEpisodeResult,
    build_fixture_adapter,
    run_mock_user_episode,
    write_episode_summary,
    write_episode_trace,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_SET = Path(__file__).resolve().parent / "gold_sets" / "narrative_agent_smoke.json"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "narrative_llm_judge_report.json"
SCORE_DIMENSIONS = (
    "agency",
    "role_consistency",
    "objective_progress",
    "consequence_continuity",
    "leverage_payoff",
    "safety_contract",
    "trajectory_quality",
    "narrative_coherence",
    "hidden_info_safety",
)
LLM_JUDGE_BENIGN_METADATA_FIELDS = frozenset({"case_id"})
StatusText = Literal["pass", "warn", "fail"]
RunReportStatus = Literal["pass", "warn", "fail", "validation_failed"]
RunMode = Literal["case", "fixture", "live"]
JudgeMode = Literal["fake", "live"]


class GoldCaseRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixture", "live"] = "fixture"
    fixture: Literal["merger_audit", "none"] = "merger_audit"
    seed: str | None = Field(default=None, max_length=2000)
    session_id: str | None = Field(default=None, max_length=120)
    template_id: str | None = Field(default=None, max_length=120)


class GoldCaseExpectations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_turns: int = Field(default=1, ge=0, le=80)
    required_stage_progression: list[str] = Field(default_factory=list, max_length=12)
    expected_role_behavior: str = Field(default="", max_length=500)
    leverage_usage_required: bool = False
    leverage_payoff_required: bool = False
    hidden_info_must_not_leak: bool = True
    allowed_violation_codes: list[str] = Field(default_factory=list, max_length=32)
    forbidden_violation_codes: list[str] = Field(default_factory=list, max_length=32)
    trajectory_status_allowed: list[StatusText] = Field(default_factory=lambda: ["pass", "warn"])
    ending_required: bool = False


class GoldJudgeRubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weights: dict[str, float] = Field(default_factory=dict)
    pass_threshold: float = Field(default=0.78, ge=0, le=1)
    warn_threshold: float = Field(default=0.58, ge=0, le=1)


class GoldMockUserSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: str | None = Field(default=None, max_length=64)
    role_selection: str = "first_available"
    policy: str = "option_selector"
    turn_budget: int = Field(default=6, ge=1, le=40)
    freeform_rate: float = Field(default=0.0, ge=0, le=1)
    leverage_policy: str = "never"
    objective: str = Field(min_length=1, max_length=300)
    risk_tolerance: str = "medium"
    seed: int = 7


class GoldCaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    runtime: GoldCaseRuntime
    mock_user: GoldMockUserSpec
    expected: GoldCaseExpectations
    rubric: GoldJudgeRubric = Field(default_factory=GoldJudgeRubric)
    run_mode: Literal["ci_stub", "live_gateway"] = "ci_stub"


class NarrativeAgentGoldSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["narrative_agent_gold_set.v1"] = "narrative_agent_gold_set.v1"
    gold_set_id: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    cases: list[GoldCaseSpec] = Field(min_length=1, max_length=100)


class LLMJudgeScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agency: float = Field(ge=0, le=1)
    role_consistency: float = Field(ge=0, le=1)
    objective_progress: float = Field(ge=0, le=1)
    consequence_continuity: float = Field(ge=0, le=1)
    leverage_payoff: float = Field(ge=0, le=1)
    safety_contract: float = Field(ge=0, le=1)
    trajectory_quality: float = Field(ge=0, le=1)
    narrative_coherence: float = Field(ge=0, le=1)
    hidden_info_safety: float = Field(ge=0, le=1)

    def weighted_average(self, weights: dict[str, float]) -> float:
        weighted_total = 0.0
        weight_total = 0.0
        for dimension in SCORE_DIMENSIONS:
            weight = float(weights.get(dimension, 1.0))
            weighted_total += float(getattr(self, dimension)) * weight
            weight_total += weight
        return weighted_total / weight_total if weight_total else 0.0


class LLMJudgeViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    severity: Literal["warn", "error"]
    rationale: str = Field(min_length=1, max_length=320)
    evidence: list[str] = Field(default_factory=list, max_length=8)


class LLMJudgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["llm_judge.v1"] = "llm_judge.v1"
    source: Literal["deepseek_v4_flash_gateway", "fake_gateway"] = "fake_gateway"
    model: str = Field(min_length=1, max_length=120)
    gateway: str = Field(min_length=1, max_length=240)
    status: StatusText
    scores: LLMJudgeScores
    violations: list[LLMJudgeViolation] = Field(default_factory=list, max_length=16)
    expectation_matches: list[str] = Field(default_factory=list, max_length=16)
    expectation_misses: list[str] = Field(default_factory=list, max_length=16)
    reviewer_summary: str = Field(min_length=1, max_length=600)
    confidence: float = Field(ge=0, le=1)
    deterministic_disagreement: bool = False


class LLMJudgeConsistencyCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["llm_judge_consistency.v1"] = "llm_judge_consistency.v1"
    source: Literal["deterministic_runner_v1"] = "deterministic_runner_v1"
    status: StatusText
    weighted_score: float = Field(ge=0, le=1)
    pass_floor: float = Field(ge=0, le=1)
    fail_floor: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=320)
    evidence: list[str] = Field(default_factory=list, max_length=8)


class LLMJudgeErrorArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["llm_judge_error.v1"] = "llm_judge_error.v1"
    source: Literal["deepseek_v4_flash_gateway", "fake_gateway"]
    model: str = Field(min_length=1, max_length=120)
    gateway: str = Field(min_length=1, max_length=240)
    status: Literal["validation_failed"] = "validation_failed"
    error_type: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1200)
    deterministic_status: StatusText
    deterministic_summary: dict[str, Any]
    safe_payload_summary: dict[str, Any] = Field(default_factory=dict)
    normalized_payload_summary: dict[str, Any] = Field(default_factory=dict)


class LLMJudgeInputPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["llm_judge_input.v1"] = "llm_judge_input.v1"
    case_id: str
    gold_case: dict[str, Any]
    mock_user_config: dict[str, Any]
    deterministic_summary: dict[str, Any]
    turn_evidence: list[dict[str, Any]]
    trajectory_judge: dict[str, Any]
    hidden_info_indicators: dict[str, Any]


class NarrativeCaseJudgeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    name: str
    run_mode: Literal["fixture", "live"]
    deterministic_status: StatusText
    llm_status: StatusText
    status: StatusText
    disagreement: bool
    trace_path: str
    summary_path: str
    llm_input_path: str
    llm_result_path: str
    deterministic_summary: dict[str, Any]
    llm_judge: LLMJudgeResult | None = None
    llm_judge_error: LLMJudgeErrorArtifact | None = None
    llm_consistency: LLMJudgeConsistencyCheck | None = None


class NarrativeJudgeAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_count: int = Field(ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    deterministic_status_counts: dict[str, int] = Field(default_factory=dict)
    llm_status_counts: dict[str, int] = Field(default_factory=dict)
    repeated_violation_codes: dict[str, int] = Field(default_factory=dict)
    disagreement_count: int = Field(ge=0)
    gates: dict[str, bool] = Field(default_factory=dict)


class NarrativeLLMJudgeRunReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["narrative_llm_judge_report.v1"] = "narrative_llm_judge_report.v1"
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: RunReportStatus
    git_sha: str | None = None
    gold_set_id: str
    gold_set_path: str
    mode: RunMode
    llm_judge_mode: JudgeMode
    gateway: dict[str, Any]
    cases: list[NarrativeCaseJudgeReport]
    aggregate: NarrativeJudgeAggregate


class JudgeGateway(Protocol):
    model: str

    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        operation_name: str,
        max_output_tokens: int | None = None,
    ) -> ResponsesJSONResponse:
        ...


class FakeLLMJudgeGateway:
    model = "fake-llm-judge"

    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        operation_name: str,
        max_output_tokens: int | None = None,
    ) -> ResponsesJSONResponse:
        del system_prompt, operation_name, max_output_tokens
        return ResponsesJSONResponse(
            payload=_fake_llm_judge_payload(user_payload),
            response_id="fake-llm-judge",
            usage={},
            input_characters=len(json.dumps(user_payload, ensure_ascii=False)),
        )


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n")


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None


def load_gold_set(path: Path) -> NarrativeAgentGoldSet:
    return NarrativeAgentGoldSet.model_validate(json.loads(path.read_text(encoding="utf-8")))


def gateway_snapshot(settings: Settings | None = None) -> dict[str, Any]:
    resolved = settings or get_settings()
    return {
        "responses_base_url": resolved.resolved_responses_base_url(),
        "responses_model": resolved.resolved_responses_model(),
        "author_base_url": resolved.resolved_author_responses_base_url(),
        "author_model": resolved.resolved_author_responses_model(),
        "play_base_url": resolved.resolved_play_responses_base_url(),
        "play_model": resolved.resolved_play_responses_model(),
        "play_key_pool_count": len(resolved.play_responses_api_key_pool()),
        "thinking_play": bool(resolved.responses_enable_thinking_play),
        "chat_json_stream_mode": resolved.responses_chat_json_stream_mode,
    }


def mock_config_for_case(
    case: GoldCaseSpec,
    *,
    mode: Literal["fixture", "live"],
    trace_path: Path,
    summary_path: Path,
    base_url: str,
    session_override: str | None = None,
    template_override: str | None = None,
) -> MockUserConfig:
    runtime = case.runtime
    return MockUserConfig(
        session_id=session_override or runtime.session_id,
        template_id=template_override or runtime.template_id,
        mode=mode,
        fixture=runtime.fixture,
        role_id=case.mock_user.role_id,
        role_selection=case.mock_user.role_selection,  # type: ignore[arg-type]
        policy=case.mock_user.policy,  # type: ignore[arg-type]
        turn_budget=case.mock_user.turn_budget,
        freeform_rate=case.mock_user.freeform_rate,
        leverage_policy=case.mock_user.leverage_policy,  # type: ignore[arg-type]
        objective=case.mock_user.objective,
        risk_tolerance=case.mock_user.risk_tolerance,  # type: ignore[arg-type]
        seed=case.mock_user.seed,
        base_url=base_url,
        trace_output_path=str(trace_path),
        summary_output_path=str(summary_path),
    )


def _status_rank(status: str) -> int:
    return {"pass": 0, "warn": 1, "fail": 2, "missing": 2}.get(status, 2)


def _combine_statuses(statuses: list[str]) -> StatusText:
    worst = max((_status_rank(status) for status in statuses), default=0)
    if worst >= 2:
        return "fail"
    if worst == 1:
        return "warn"
    return "pass"


def deterministic_status(result: MockUserEpisodeResult, case: GoldCaseSpec) -> StatusText:
    statuses: list[str] = [result.trajectory_judge.status]
    for turn in result.turns:
        statuses.extend([turn.step_judge_status, turn.contract_judge_status])
    if len(result.turns) < case.expected.min_turns:
        statuses.append("fail")
    if result.trajectory_judge.status not in case.expected.trajectory_status_allowed:
        statuses.append("fail")
    violation_codes = {
        code
        for turn in result.turns
        for code in turn.step_judge_violation_codes + turn.contract_judge_violation_codes
    }
    if violation_codes.intersection(case.expected.forbidden_violation_codes):
        statuses.append("fail")
    if case.expected.leverage_usage_required and not result.episode_memory.played_leverage_cards:
        statuses.append("warn")
    return _combine_statuses(statuses)


def _clip(value: Any, limit: int = 420) -> Any:
    if isinstance(value, str):
        return value[:limit]
    return value


class LLMJudgeEvaluationError(RuntimeError):
    def __init__(
        self,
        *,
        error_type: str,
        message: str,
        response_payload: Any = None,
        normalized_payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.response_payload = response_payload
        self.normalized_payload = normalized_payload


def _payload_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    summary: dict[str, Any] = {
        "keys": sorted(str(key) for key in payload.keys()),
    }
    for key in ("schema_version", "source", "model", "gateway", "status", "confidence"):
        if key in payload:
            summary[key] = _clip(payload.get(key), limit=160)
    if "scores" in payload:
        summary["scores_type"] = type(payload.get("scores")).__name__
    if "violations" in payload:
        violations = payload.get("violations")
        summary["violation_count"] = len(violations) if isinstance(violations, list) else None
    return summary


def _compact_expectation_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "null"
    if isinstance(value, str):
        return _clip(value, limit=180)
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        compact_values = [_compact_expectation_value(item) for item in value[:4]]
        suffix = ",..." if len(value) > 4 else ""
        return "[" + ",".join(compact_values) + suffix + "]"
    if isinstance(value, dict):
        preferred_keys = (
            "status",
            "outcome",
            "match",
            "matched",
            "passed",
            "reason",
            "rationale",
            "evidence",
            "value",
        )
        parts: list[str] = []
        for key in preferred_keys:
            if key in value:
                parts.append(f"{key}={_compact_expectation_value(value[key])}")
        if not parts:
            for key, nested_value in list(value.items())[:4]:
                parts.append(f"{key}={_compact_expectation_value(nested_value)}")
        return "; ".join(parts)
    return _clip(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str), limit=180)


def _normalize_expectation_entries(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    entries: list[str] = []
    for key, item in value.items():
        entries.append(f"{key}:{_compact_expectation_value(item)}")
    return entries[:16]


def _normalize_llm_judge_payload(
    payload: Any,
    *,
    gateway: JudgeGateway,
    source: Literal["deepseek_v4_flash_gateway", "fake_gateway"],
    gateway_label: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LLMJudgeEvaluationError(
            error_type="llm_judge_payload_type_error",
            message=f"LLM judge response payload must be an object, got {type(payload).__name__}.",
            response_payload=payload,
        )
    normalized = dict(payload)
    for field_name in LLM_JUDGE_BENIGN_METADATA_FIELDS:
        normalized.pop(field_name, None)
    for field_name in ("expectation_matches", "expectation_misses"):
        if field_name in normalized:
            normalized[field_name] = _normalize_expectation_entries(normalized[field_name])
    normalized["source"] = source
    normalized["model"] = str(getattr(gateway, "model", "configured_gateway"))
    normalized["gateway"] = str(gateway_label)
    return normalized


def _llm_judge_error_artifact(
    *,
    error: LLMJudgeEvaluationError,
    source: Literal["deepseek_v4_flash_gateway", "fake_gateway"],
    gateway: JudgeGateway,
    gateway_label: str,
    deterministic_status_value: StatusText,
    deterministic_summary: dict[str, Any],
) -> LLMJudgeErrorArtifact:
    return LLMJudgeErrorArtifact(
        source=source,
        model=str(getattr(gateway, "model", "configured_gateway")),
        gateway=gateway_label,
        error_type=error.error_type,
        message=_clip(str(error), limit=1200),
        deterministic_status=deterministic_status_value,
        deterministic_summary=deterministic_summary,
        safe_payload_summary=_payload_summary(error.response_payload),
        normalized_payload_summary=_payload_summary(error.normalized_payload),
    )


def build_llm_judge_input(
    *,
    case: GoldCaseSpec,
    result: MockUserEpisodeResult,
) -> LLMJudgeInputPackage:
    turn_evidence: list[dict[str, Any]] = []
    hidden_codes: list[str] = []
    all_codes: list[str] = []
    for turn in result.turns:
        codes = turn.step_judge_violation_codes + turn.contract_judge_violation_codes
        all_codes.extend(codes)
        hidden_codes.extend(code for code in codes if "hidden" in code or "leak" in code)
        runtime_summary = dict(turn.runtime_output_summary)
        if "passage" in runtime_summary:
            runtime_summary["passage"] = _clip(runtime_summary["passage"])
        turn_evidence.append(
            {
                "turn_index": turn.turn_index,
                "narrator_ord": turn.narrator_ord,
                "observation_summary": turn.observation_summary,
                "memory_summary": turn.memory_summary,
                "selected_action": turn.selected_action,
                "runtime_output_summary": runtime_summary,
                "agent_plan_summary": turn.agent_plan_summary,
                "step_judge": {
                    "status": turn.step_judge_status,
                    "violation_codes": turn.step_judge_violation_codes,
                },
                "contract_judge": {
                    "status": turn.contract_judge_status,
                    "violation_codes": turn.contract_judge_violation_codes,
                },
            }
        )
    return LLMJudgeInputPackage(
        case_id=case.case_id,
        gold_case={
            "case_id": case.case_id,
            "name": case.name,
            "runtime": case.runtime.model_dump(mode="json"),
            "expected": case.expected.model_dump(mode="json"),
            "rubric": case.rubric.model_dump(mode="json"),
        },
        mock_user_config={
            "role_id": result.config.role_id,
            "role_selection": result.config.role_selection,
            "policy": result.config.policy,
            "turn_budget": result.config.turn_budget,
            "freeform_rate": result.config.freeform_rate,
            "leverage_policy": result.config.leverage_policy,
            "objective": result.config.objective,
            "risk_tolerance": result.config.risk_tolerance,
            "seed": result.config.seed,
        },
        deterministic_summary={
            "turn_count": result.summary.turn_count,
            "completed_turn_budget": result.summary.completed_turn_budget,
            "ending_detected": result.summary.ending_detected,
            "step_status_counts": result.summary.step_status_counts,
            "contract_status_counts": result.summary.contract_status_counts,
            "trajectory_status": result.summary.trajectory_status,
            "trajectory_check_counts": result.summary.trajectory_check_counts,
            "repeated_violation_codes": result.summary.repeated_violation_codes,
            "recommendations": result.summary.recommendations,
        },
        turn_evidence=turn_evidence,
        trajectory_judge=result.trajectory_judge.model_dump(mode="json"),
        hidden_info_indicators={
            "hidden_or_leak_codes": hidden_codes,
            "forbidden_code_hits": sorted(set(all_codes).intersection(case.expected.forbidden_violation_codes)),
            "stores_hidden_leverage_text": False,
        },
    )


def _fake_llm_judge_payload(user_payload: dict[str, Any]) -> dict[str, Any]:
    deterministic = user_payload.get("deterministic_summary") or {}
    trajectory_status = str(deterministic.get("trajectory_status") or "missing")
    repeated = deterministic.get("repeated_violation_codes") or {}
    hidden = user_payload.get("hidden_info_indicators") or {}
    hidden_hits = hidden.get("hidden_or_leak_codes") or []
    forbidden_hits = hidden.get("forbidden_code_hits") or []
    has_fail = trajectory_status == "fail" or bool(forbidden_hits)
    has_warn = trajectory_status == "warn" or bool(repeated) or bool(hidden_hits)
    status: StatusText = "fail" if has_fail else "warn" if has_warn else "pass"
    base_score = 0.38 if status == "fail" else 0.68 if status == "warn" else 0.86
    violations: list[dict[str, Any]] = []
    if forbidden_hits:
        violations.append(
            {
                "code": "gold_forbidden_violation_hit",
                "severity": "error",
                "rationale": "The run hit a violation code forbidden by the gold case.",
                "evidence": [str(code) for code in forbidden_hits[:8]],
            }
        )
    if hidden_hits:
        violations.append(
            {
                "code": "hidden_info_safety_signal",
                "severity": "warn",
                "rationale": "The deterministic evidence reported hidden-info or leak signals.",
                "evidence": [str(code) for code in hidden_hits[:8]],
            }
        )
    return {
        "schema_version": "llm_judge.v1",
        "source": "fake_gateway",
        "model": "fake-llm-judge",
        "gateway": "fake",
        "status": status,
        "scores": {dimension: base_score for dimension in SCORE_DIMENSIONS},
        "violations": violations,
        "expectation_matches": ["deterministic evidence package parsed", "trajectory evidence included"],
        "expectation_misses": [str(code) for code in forbidden_hits],
        "reviewer_summary": f"Fake judge classified the run as {status} from deterministic evidence.",
        "confidence": 0.72,
        "deterministic_disagreement": False,
    }


def _llm_judge_system_prompt() -> str:
    return (
        "You are an LLM-as-judge evaluator for Tiny Stories, an AI narrative runtime. "
        "Use the gold case rubric and structured evidence only. Do not infer hidden "
        "objectives or hidden leverage text beyond the supplied summaries. Return strict "
        "JSON matching schema llm_judge.v1 with status, scores, violations, expectation "
        "matches/misses, reviewer_summary, confidence, and deterministic_disagreement."
    )


def evaluate_with_llm_judge(
    *,
    package: LLMJudgeInputPackage,
    gateway: JudgeGateway,
    source: Literal["deepseek_v4_flash_gateway", "fake_gateway"],
    gateway_label: str,
    deterministic_status_value: StatusText,
) -> LLMJudgeResult:
    try:
        response = gateway.invoke_json(
            system_prompt=_llm_judge_system_prompt(),
            user_payload=package.model_dump(mode="json"),
            operation_name="rpg_eval.narrative_llm_judge",
            max_output_tokens=1400,
        )
    except Exception as exc:
        raise LLMJudgeEvaluationError(
            error_type=type(exc).__name__,
            message=f"LLM judge gateway call failed: {exc}",
        ) from exc

    normalized_payload: dict[str, Any] | None = None
    try:
        normalized_payload = _normalize_llm_judge_payload(
            response.payload,
            gateway=gateway,
            source=source,
            gateway_label=gateway_label,
        )
        parsed = LLMJudgeResult.model_validate(normalized_payload)
    except LLMJudgeEvaluationError:
        raise
    except Exception as exc:
        raise LLMJudgeEvaluationError(
            error_type=type(exc).__name__,
            message=f"LLM judge response validation failed: {exc}",
            response_payload=response.payload,
            normalized_payload=normalized_payload,
        ) from exc

    return parsed.model_copy(
        update={
            "deterministic_disagreement": parsed.status != deterministic_status_value,
        }
    )


def _adapter_for_case(config: MockUserConfig, mode: Literal["fixture", "live"]):
    if mode == "fixture":
        return build_fixture_adapter(config)
    if config.session_id is None and config.template_id is None:
        raise ValueError("live gold case requires session_id or template_id")
    return (
        LiveHTTPNarrativeAdapter(
            config.base_url or "http://127.0.0.1:8000",
            reviewer_username=config.reviewer_username,
        ),
        config,
    )


def _case_run_mode(case: GoldCaseSpec, override: RunMode) -> Literal["fixture", "live"]:
    if override != "case":
        return override
    return case.runtime.mode


def _case_status(det_status: StatusText, llm_status: StatusText) -> StatusText:
    return _combine_statuses([det_status, llm_status])


def _llm_score_consistency(
    *,
    case: GoldCaseSpec,
    result: LLMJudgeResult,
) -> LLMJudgeConsistencyCheck:
    weighted_score = result.scores.weighted_average(case.rubric.weights)
    pass_floor = float(case.rubric.pass_threshold)
    fail_floor = float(case.rubric.warn_threshold)
    evidence = [
        f"llm_status:{result.status}",
        f"weighted_score:{weighted_score:.3f}",
        f"pass_floor:{pass_floor:.3f}",
        f"fail_floor:{fail_floor:.3f}",
    ]
    if weighted_score < fail_floor:
        return LLMJudgeConsistencyCheck(
            status="fail",
            weighted_score=weighted_score,
            pass_floor=pass_floor,
            fail_floor=fail_floor,
            rationale=(
                "LLM judge numeric scores are below the fail floor, so the "
                "case cannot pass regardless of the textual status."
            ),
            evidence=evidence,
        )
    if result.status == "pass" and weighted_score < pass_floor:
        return LLMJudgeConsistencyCheck(
            status="warn",
            weighted_score=weighted_score,
            pass_floor=pass_floor,
            fail_floor=fail_floor,
            rationale=(
                "LLM judge returned pass, but numeric scores are below the "
                "configured pass floor."
            ),
            evidence=evidence,
        )
    return LLMJudgeConsistencyCheck(
        status="pass",
        weighted_score=weighted_score,
        pass_floor=pass_floor,
        fail_floor=fail_floor,
        rationale="LLM judge status is consistent with numeric scores.",
        evidence=evidence,
    )


def _report_status(cases: list[NarrativeCaseJudgeReport]) -> RunReportStatus:
    if any(case.llm_judge_error is not None for case in cases):
        return "validation_failed"
    return _combine_statuses([case.status for case in cases])


def _aggregate(cases: list[NarrativeCaseJudgeReport]) -> NarrativeJudgeAggregate:
    status_counts = Counter(case.status for case in cases)
    deterministic_counts = Counter(case.deterministic_status for case in cases)
    llm_counts = Counter(case.llm_status for case in cases)
    violation_counts = Counter(
        violation.code
        for case in cases
        for violation in (case.llm_judge.violations if case.llm_judge else [])
    )
    hidden_info_codes = (
        {violation.code for violation in case.llm_judge.violations}
        if case.llm_judge
        else {"llm_judge_missing"}
        for case in cases
    )
    return NarrativeJudgeAggregate(
        case_count=len(cases),
        status_counts=dict(status_counts),
        deterministic_status_counts=dict(deterministic_counts),
        llm_status_counts=dict(llm_counts),
        repeated_violation_codes={code: count for code, count in violation_counts.items() if count > 1},
        disagreement_count=sum(1 for case in cases if case.disagreement),
        gates={
            "gold_set_loaded": bool(cases),
            "mock_user_runs_completed": all(case.deterministic_summary.get("turn_count", 0) > 0 for case in cases),
            "deterministic_evidence_present": all(case.deterministic_status in {"pass", "warn", "fail"} for case in cases),
            "llm_judge_present": all(
                case.llm_judge is not None and case.llm_judge.schema_version == "llm_judge.v1"
                for case in cases
            ),
            "llm_score_consistency": all(
                case.llm_consistency is not None and case.llm_consistency.status == "pass"
                for case in cases
            ),
            "hidden_info_safety": all(
                "hidden_info_safety_signal" not in codes for codes in hidden_info_codes
            ),
        },
    )


def run_gold_set_evaluation(
    *,
    gold_set_path: Path,
    output_path: Path,
    mode: RunMode = "case",
    llm_judge_mode: JudgeMode = "fake",
    allow_live_llm: bool = False,
    base_url: str = "http://127.0.0.1:8000",
    case_limit: int | None = None,
    session_override: str | None = None,
    template_override: str | None = None,
    gateway: JudgeGateway | None = None,
) -> NarrativeLLMJudgeRunReport:
    gold_set = load_gold_set(gold_set_path)
    selected_cases = gold_set.cases[:case_limit] if case_limit else gold_set.cases
    if not selected_cases:
        raise ValueError("gold set selected zero cases")
    selected_modes = [_case_run_mode(case, mode) for case in selected_cases]
    if (any(selected_mode == "live" for selected_mode in selected_modes) or llm_judge_mode == "live") and not allow_live_llm:
        raise ValueError("live runtime or live LLM judge requires --allow-live-llm")

    artifacts_dir = output_path.with_suffix("").parent / f"{output_path.stem}_artifacts"
    settings = get_settings()
    gateway_info = gateway_snapshot(settings)
    if llm_judge_mode == "live":
        resolved_gateway = gateway or get_narrative_gateway(settings)
        if resolved_gateway is None:
            raise ValueError("live LLM judge requested but narrative gateway is not configured")
        judge_gateway = resolved_gateway
        judge_source: Literal["deepseek_v4_flash_gateway", "fake_gateway"] = "deepseek_v4_flash_gateway"
        gateway_label = str(gateway_info.get("play_base_url") or "configured_play_gateway")
    else:
        judge_gateway = gateway or FakeLLMJudgeGateway()
        judge_source = "fake_gateway"
        gateway_label = "fake"

    case_reports: list[NarrativeCaseJudgeReport] = []
    for case in selected_cases:
        resolved_mode = _case_run_mode(case, mode)
        case_dir = artifacts_dir / case.case_id
        trace_path = case_dir / "episode_trace.jsonl"
        summary_path = case_dir / "episode_summary.json"
        llm_input_path = case_dir / "llm_judge_input.json"
        llm_result_path = case_dir / "llm_judge_result.json"
        config = mock_config_for_case(
            case,
            mode=resolved_mode,
            trace_path=trace_path,
            summary_path=summary_path,
            base_url=base_url,
            session_override=session_override,
            template_override=template_override,
        )
        adapter, config = _adapter_for_case(config, resolved_mode)
        episode = run_mock_user_episode(config, adapter)
        write_episode_trace(episode, trace_path)
        write_episode_summary(episode, summary_path)
        package = build_llm_judge_input(case=case, result=episode)
        _write_json(llm_input_path, package)
        det_status = deterministic_status(episode, case)
        llm_result: LLMJudgeResult | None = None
        llm_error: LLMJudgeErrorArtifact | None = None
        llm_consistency: LLMJudgeConsistencyCheck | None = None
        try:
            llm_result = evaluate_with_llm_judge(
                package=package,
                gateway=judge_gateway,
                source=judge_source,
                gateway_label=gateway_label,
                deterministic_status_value=det_status,
            )
            llm_consistency = _llm_score_consistency(case=case, result=llm_result)
            _write_json(llm_result_path, llm_result)
        except LLMJudgeEvaluationError as exc:
            llm_error = _llm_judge_error_artifact(
                error=exc,
                source=judge_source,
                gateway=judge_gateway,
                gateway_label=gateway_label,
                deterministic_status_value=det_status,
                deterministic_summary=package.deterministic_summary,
            )
            _write_json(llm_result_path, llm_error)
        llm_status: StatusText = (
            _combine_statuses([llm_result.status, llm_consistency.status])
            if llm_result and llm_consistency
            else "fail"
        )
        case_status = _case_status(det_status, llm_status)
        case_reports.append(
            NarrativeCaseJudgeReport(
                case_id=case.case_id,
                name=case.name,
                run_mode=resolved_mode,
                deterministic_status=det_status,
                llm_status=llm_status,
                status=case_status,
                disagreement=(
                    (llm_result.deterministic_disagreement if llm_result else False)
                    or det_status != llm_status
                ),
                trace_path=str(trace_path),
                summary_path=str(summary_path),
                llm_input_path=str(llm_input_path),
                llm_result_path=str(llm_result_path),
                deterministic_summary=package.deterministic_summary,
                llm_judge=llm_result,
                llm_judge_error=llm_error,
                llm_consistency=llm_consistency,
            )
        )

    report = NarrativeLLMJudgeRunReport(
        run_id=datetime.now(timezone.utc).strftime("narrative_llm_judge_%Y%m%d_%H%M%S"),
        status=_report_status(case_reports),
        git_sha=_git_sha(),
        gold_set_id=gold_set.gold_set_id,
        gold_set_path=str(gold_set_path),
        mode=mode,
        llm_judge_mode=llm_judge_mode,
        gateway=gateway_info,
        cases=case_reports,
        aggregate=_aggregate(case_reports),
    )
    _write_json(output_path, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Tiny Stories gold-set evaluation: gold case -> mock user -> "
            "runtime trace -> deterministic judges -> LLM judge -> report gates."
        )
    )
    parser.add_argument("--gold-set", default=str(DEFAULT_GOLD_SET))
    parser.add_argument("--mode", choices=("case", "fixture", "live"), default="case")
    parser.add_argument("--llm-judge", choices=("fake", "live"), default="fake")
    parser.add_argument("--allow-live-llm", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--session", dest="session_override", default=None)
    parser.add_argument("--template", dest="template_override", default=None)
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_gold_set_evaluation(
        gold_set_path=Path(args.gold_set).expanduser().resolve(),
        output_path=Path(args.output).expanduser().resolve(),
        mode=args.mode,
        llm_judge_mode=args.llm_judge,
        allow_live_llm=bool(args.allow_live_llm),
        base_url=str(args.base_url),
        case_limit=args.case_limit,
        session_override=args.session_override,
        template_override=args.template_override,
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
