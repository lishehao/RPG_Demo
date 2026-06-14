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
LLM_JUDGE_CONFIDENCE_LABELS = {
    "high": 0.9,
    "high confidence": 0.9,
    "very high": 0.9,
    "medium": 0.6,
    "medium confidence": 0.6,
    "moderate": 0.6,
    "moderate confidence": 0.6,
    "mid": 0.6,
    "low": 0.3,
    "low confidence": 0.3,
    "very low": 0.3,
}
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
    score_status: StatusText = "pass"
    score_shape_status: StatusText = "pass"
    suspicious_score_shape: str | None = Field(default=None, max_length=120)
    suspicious_score_dimensions: list[str] = Field(default_factory=list, max_length=16)
    expectation_status: StatusText = "pass"
    expectation_conflicts: list[str] = Field(default_factory=list, max_length=16)
    required_expectation_status: StatusText = "pass"
    required_expectation_matches: list[str] = Field(default_factory=list, max_length=32)
    required_expectation_misses: list[str] = Field(default_factory=list, max_length=32)
    non_blocking_expectation_misses: list[str] = Field(default_factory=list, max_length=32)
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


class RuntimeFailureArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["runtime_failure.v1"] = "runtime_failure.v1"
    status: Literal["validation_failed"] = "validation_failed"
    case_id: str
    run_mode: Literal["fixture", "live"]
    session_id: str | None = None
    error_type: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1200)
    runtime_retry_count: int = Field(default=0, ge=0)
    trace_path: str
    summary_path: str
    llm_input_path: str
    llm_result_path: str
    deterministic_summary: dict[str, Any]
    safe_context: dict[str, Any] = Field(default_factory=dict)


class LLMJudgeInputPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["llm_judge_input.v1"] = "llm_judge_input.v1"
    case_id: str
    gold_case: dict[str, Any]
    mock_user_config: dict[str, Any]
    deterministic_summary: dict[str, Any]
    turn_evidence: list[dict[str, Any]]
    trajectory_judge: dict[str, Any]
    leverage_payoff_evidence: list[dict[str, Any]] = Field(default_factory=list)
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
    runtime_error: RuntimeFailureArtifact | None = None


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


_NO_MISS_STRINGS = frozenset(
    {
        "",
        "false",
        "no",
        "none",
        "null",
        "pass",
        "passed",
        "satisfied",
        "met",
        "ok",
        "okay",
        "success",
        "not applicable",
        "n/a",
    }
)
_NO_MATCH_STRINGS = frozenset(
    {
        "",
        "false",
        "no",
        "none",
        "null",
        "fail",
        "failed",
        "missing",
        "miss",
        "missed",
        "unmet",
        "not met",
    }
)


def _normalized_token(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())


def _is_no_miss_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return _normalized_token(value) in _NO_MISS_STRINGS
    if isinstance(value, int | float):
        return value == 0
    if isinstance(value, list):
        return not value or all(_is_no_miss_value(item) for item in value)
    if isinstance(value, dict):
        miss_flags = ("miss", "missed", "unmet", "failed")
        pass_flags = ("match", "matched", "passed", "satisfied", "met")
        for key in miss_flags:
            if key in value:
                return _is_no_miss_value(value[key])
        for key in pass_flags:
            if key in value and value[key] is True:
                return True
        for key in ("status", "outcome", "result", "value"):
            if key in value:
                return _is_no_miss_value(value[key])
        return bool(value) and all(_is_no_miss_value(item) for item in value.values())
    return False


def _is_no_match_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return _normalized_token(value) in _NO_MATCH_STRINGS
    if isinstance(value, int | float):
        return value == 0
    if isinstance(value, list):
        return not value or all(_is_no_match_value(item) for item in value)
    if isinstance(value, dict):
        for key in ("match", "matched", "passed", "satisfied", "met"):
            if key in value:
                return _is_no_match_value(value[key])
        for key in ("status", "outcome", "result", "value"):
            if key in value:
                return _is_no_match_value(value[key])
    return False


def _normalize_expectation_entries(value: Any, *, field_name: str) -> Any:
    if not isinstance(value, dict):
        return value
    entries: list[str] = []
    for key, item in value.items():
        if field_name == "expectation_misses" and _is_no_miss_value(item):
            continue
        if field_name == "expectation_matches" and _is_no_match_value(item):
            continue
        entries.append(f"{key}:{_compact_expectation_value(item)}")
    return entries[:16]


def _normalize_confidence(value: Any) -> Any:
    if isinstance(value, str):
        return LLM_JUDGE_CONFIDENCE_LABELS.get(_normalized_token(value), value)
    return value


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
            normalized[field_name] = _normalize_expectation_entries(
                normalized[field_name],
                field_name=field_name,
            )
    if "confidence" in normalized:
        normalized["confidence"] = _normalize_confidence(normalized["confidence"])
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


def _default_runtime_failure_summary(runtime_retry_count: int) -> dict[str, Any]:
    return {
        "turn_count": 0,
        "completed_turn_budget": False,
        "ending_detected": False,
        "step_status_counts": {},
        "contract_status_counts": {},
        "trajectory_status": "missing",
        "trajectory_check_counts": {},
        "repeated_violation_codes": {},
        "runtime_retry_count": runtime_retry_count,
        "recommendations": ["runtime failure prevented complete mock-user episode"],
    }


def _runtime_failure_artifact(
    *,
    case: GoldCaseSpec,
    run_mode: Literal["fixture", "live"],
    error: BaseException,
    trace_path: Path,
    summary_path: Path,
    llm_input_path: Path,
    llm_result_path: Path,
) -> RuntimeFailureArtifact:
    session_id = getattr(error, "session_id", None)
    runtime_retry_count = int(getattr(error, "runtime_retry_count", 0) or 0)
    return RuntimeFailureArtifact(
        case_id=case.case_id,
        run_mode=run_mode,
        session_id=session_id,
        error_type=type(error).__name__,
        message=_clip(str(error), limit=1200),
        runtime_retry_count=runtime_retry_count,
        trace_path=str(trace_path),
        summary_path=str(summary_path),
        llm_input_path=str(llm_input_path),
        llm_result_path=str(llm_result_path),
        deterministic_summary=_default_runtime_failure_summary(runtime_retry_count),
        safe_context={
            "template_id": case.runtime.template_id,
            "configured_session_id": case.runtime.session_id,
            "policy": case.mock_user.policy,
            "turn_budget": case.mock_user.turn_budget,
        },
    )


def _write_runtime_failure_artifacts(
    *,
    failure: RuntimeFailureArtifact,
    error: BaseException,
    trace_path: Path,
    summary_path: Path,
    llm_input_path: Path,
    llm_result_path: Path,
) -> None:
    loop_events = list(getattr(error, "action_loop", []) or [])
    trace_rows: list[dict[str, Any]] = []
    for event in loop_events:
        if hasattr(event, "model_dump"):
            trace_rows.append(
                {
                    "record_type": "loop_event",
                    "schema_version": event.schema_version,
                    "session_id": failure.session_id,
                    "payload": event.model_dump(mode="json"),
                }
            )
    trace_rows.append(
        {
            "record_type": "runtime_failure",
            "schema_version": failure.schema_version,
            "session_id": failure.session_id,
            "payload": failure.model_dump(mode="json"),
        }
    )
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in trace_rows) + "\n",
        encoding="utf-8",
    )
    _write_json(summary_path, failure)
    _write_json(
        llm_input_path,
        {
            "schema_version": "llm_judge_input_unavailable.v1",
            "reason": "runtime_failure",
            "runtime_failure": failure.model_dump(mode="json"),
        },
    )
    _write_json(llm_result_path, failure)


def _turn_leverage_payoff_evidence(turn: Any) -> dict[str, Any] | None:
    selected_action = turn.selected_action
    played = selected_action.get("played_leverage")
    if not isinstance(played, dict):
        return None

    runtime_summary = turn.runtime_output_summary
    target_npc_id = str(played.get("target_npc_id") or played.get("npc_id") or "")
    target_pulses: list[dict[str, str]] = []
    room_pulses: list[dict[str, str]] = []
    for pulse in runtime_summary.get("npc_pulse") or []:
        if not isinstance(pulse, dict):
            continue
        shift = str(pulse.get("shift") or "steady")
        if shift == "steady":
            continue
        item = {
            "npc_id": str(pulse.get("npc_id") or ""),
            "shift": shift,
            "state": str(_clip(pulse.get("state") or "", limit=120)),
        }
        room_pulses.append(item)
        if item["npc_id"] == target_npc_id:
            target_pulses.append(item)

    delta = runtime_summary.get("inventory_delta") or {}
    inventory_delta = {
        "added_count": int(delta.get("added_count") or 0) if isinstance(delta, dict) else 0,
        "removed_count": int(delta.get("removed_count") or 0) if isinstance(delta, dict) else 0,
        "has_reason": bool(delta.get("has_reason")) if isinstance(delta, dict) else False,
    }
    payoff_signals: list[str] = []
    if target_pulses:
        payoff_signals.append("target_npc_pulse_shift")
    elif room_pulses:
        payoff_signals.append("room_pulse_shift")
    if inventory_delta["added_count"] or inventory_delta["removed_count"]:
        payoff_signals.append("inventory_delta")

    return {
        "turn_index": turn.turn_index,
        "narrator_ord": turn.narrator_ord,
        "card_id": str(played.get("card_id") or ""),
        "target_npc_id": target_npc_id,
        "action": str(played.get("action") or ""),
        "selected_option_handle": _clip(
            selected_action.get("selected_option_handle") or "",
            limit=80,
        ),
        "status": "observed" if payoff_signals else "missing",
        "payoff_signals": payoff_signals,
        "target_npc_pulse": target_pulses[:3],
        "room_pulse": room_pulses[:4],
        "inventory_delta": inventory_delta,
    }


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
            "runtime_retry_count": result.summary.runtime_retry_count,
            "recommendations": result.summary.recommendations,
        },
        turn_evidence=turn_evidence,
        trajectory_judge=result.trajectory_judge.model_dump(mode="json"),
        leverage_payoff_evidence=[
            item
            for turn in result.turns
            if (item := _turn_leverage_payoff_evidence(turn)) is not None
        ],
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
        "matches/misses, reviewer_summary, confidence, and deterministic_disagreement. "
        "Use arrays of short strings for expectation_matches and expectation_misses. "
        "Only include genuinely unmet expectations in expectation_misses; do not include "
        "false-valued or pass/satisfied/met map entries as misses. A required gold "
        "expectation miss cannot coexist with status=pass unless the expectation is "
        "explicitly non-blocking and the rationale names why. Use the gold rubric "
        "thresholds: pass status requires numeric scores consistent with the pass threshold. "
        "The scores object must contain quality scores in [0, 1] for each dimension; "
        "rubric weights are for aggregation only and must never be copied into scores. "
        "If status is pass, dimension quality scores should be consistent with pass-level quality. "
        "For leverage_payoff_required, use the leverage_payoff_evidence field: "
        "target_npc_pulse_shift, inventory_delta, or room_pulse_shift are observable payoff signals. "
        "Return confidence as a numeric value in [0, 1], not a label such as high or medium."
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


def _expectation_key(entry: str) -> str:
    text = " ".join(str(entry).strip().split())
    if not text:
        return ""
    if ":" in text:
        return text.split(":", 1)[0].strip()
    return text


def _expectation_conflicts(result: LLMJudgeResult) -> list[str]:
    match_keys = {
        key
        for key in (_expectation_key(entry) for entry in result.expectation_matches)
        if key
    }
    miss_keys = {
        key
        for key in (_expectation_key(entry) for entry in result.expectation_misses)
        if key
    }
    return sorted(match_keys.intersection(miss_keys))[:16]


def _expectation_keys(entries: list[str]) -> set[str]:
    return {key for key in (_expectation_key(entry) for entry in entries) if key}


def _required_expectation_keys(case: GoldCaseSpec) -> set[str]:
    expected = case.expected
    keys = {"min_turns", "trajectory_status_allowed"}
    if expected.required_stage_progression:
        keys.add("required_stage_progression")
    if expected.expected_role_behavior.strip():
        keys.add("expected_role_behavior")
    if expected.leverage_usage_required:
        keys.add("leverage_usage_required")
    if expected.leverage_payoff_required:
        keys.add("leverage_payoff_required")
    if expected.hidden_info_must_not_leak:
        keys.add("hidden_info_must_not_leak")
    if expected.forbidden_violation_codes:
        keys.add("forbidden_violation_codes")
        keys.update(expected.forbidden_violation_codes)
    if expected.ending_required:
        keys.add("ending_required")
    return keys


def _rubric_weight_like_score_dimensions(
    *,
    case: GoldCaseSpec,
    result: LLMJudgeResult,
    tolerance: float = 0.015,
) -> list[str]:
    suspicious: list[str] = []
    for dimension in SCORE_DIMENSIONS:
        if dimension not in case.rubric.weights:
            continue
        score = float(getattr(result.scores, dimension))
        weight = float(case.rubric.weights[dimension])
        if abs(score - weight) <= tolerance:
            suspicious.append(dimension)
    return suspicious


def _score_shape_dimension_evidence(
    *,
    case: GoldCaseSpec,
    result: LLMJudgeResult,
    dimensions: list[str],
) -> list[str]:
    return [
        (
            f"{dimension}:score={float(getattr(result.scores, dimension)):.3f};"
            f"rubric_weight={float(case.rubric.weights.get(dimension, 0.0)):.3f}"
        )
        for dimension in dimensions[:8]
    ]


def _consistency_evidence(
    *,
    base: list[str],
    expectation: list[str],
    score_shape: list[str],
    extra: list[str] | None = None,
    prioritize_score_shape: bool = False,
) -> list[str]:
    if prioritize_score_shape:
        items = [*base, *score_shape[:4], *expectation, *(extra or [])]
    else:
        items = [*base, *expectation, *(extra or []), *score_shape[:2]]
    return items[:8]


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
    suspicious_score_dimensions = _rubric_weight_like_score_dimensions(
        case=case,
        result=result,
    )
    score_shape_status: StatusText = (
        "fail" if len(suspicious_score_dimensions) >= len(SCORE_DIMENSIONS) - 1 else "pass"
    )
    score_shape_evidence = [
        "score_shape:rubric_weight_copy"
        if score_shape_status == "fail"
        else "score_shape:quality_scores",
        (
            "score_shape_dimensions:"
            + (
                ",".join(suspicious_score_dimensions[:8])
                if suspicious_score_dimensions
                else "none"
            )
        ),
        *_score_shape_dimension_evidence(
            case=case,
            result=result,
            dimensions=suspicious_score_dimensions,
        ),
    ]
    match_keys = _expectation_keys(result.expectation_matches)
    miss_keys = _expectation_keys(result.expectation_misses)
    required_keys = _required_expectation_keys(case)
    required_matches = sorted(match_keys.intersection(required_keys))[:32]
    required_misses = sorted(miss_keys.intersection(required_keys))[:32]
    non_blocking_misses = sorted(miss_keys.difference(required_keys))[:32]
    expectation_evidence = [
        f"required_misses:{','.join(required_misses[:6]) if required_misses else 'none'}",
        f"non_blocking_misses:{','.join(non_blocking_misses[:6]) if non_blocking_misses else 'none'}",
    ]
    conflicts = _expectation_conflicts(result)
    if conflicts:
        return LLMJudgeConsistencyCheck(
            status="fail",
            weighted_score=weighted_score,
            pass_floor=pass_floor,
            fail_floor=fail_floor,
            score_status="pass",
            score_shape_status=score_shape_status,
            suspicious_score_shape="rubric_weight_copy"
            if score_shape_status == "fail"
            else None,
            suspicious_score_dimensions=suspicious_score_dimensions,
            expectation_status="fail",
            expectation_conflicts=conflicts,
            required_expectation_status="fail" if required_misses else "pass",
            required_expectation_matches=required_matches,
            required_expectation_misses=required_misses,
            non_blocking_expectation_misses=non_blocking_misses,
            rationale=(
                "LLM judge placed the same expectation key in both matches "
                "and misses."
            ),
            evidence=[
                *_consistency_evidence(
                    base=evidence,
                    expectation=expectation_evidence,
                    score_shape=score_shape_evidence,
                    extra=[f"conflicts:{','.join(conflicts[:6])}"],
                )
            ],
        )
    if required_misses:
        return LLMJudgeConsistencyCheck(
            status="fail",
            weighted_score=weighted_score,
            pass_floor=pass_floor,
            fail_floor=fail_floor,
            score_status="pass",
            score_shape_status=score_shape_status,
            suspicious_score_shape="rubric_weight_copy"
            if score_shape_status == "fail"
            else None,
            suspicious_score_dimensions=suspicious_score_dimensions,
            expectation_status="pass",
            required_expectation_status="fail",
            required_expectation_matches=required_matches,
            required_expectation_misses=required_misses,
            non_blocking_expectation_misses=non_blocking_misses,
            rationale=(
                "LLM judge missed required gold expectations, so the case "
                "cannot pass regardless of the textual status or numeric score."
            ),
            evidence=_consistency_evidence(
                base=evidence,
                expectation=expectation_evidence,
                score_shape=score_shape_evidence,
            ),
        )
    if score_shape_status == "fail":
        return LLMJudgeConsistencyCheck(
            status="fail",
            weighted_score=weighted_score,
            pass_floor=pass_floor,
            fail_floor=fail_floor,
            score_status="fail",
            score_shape_status="fail",
            suspicious_score_shape="rubric_weight_copy",
            suspicious_score_dimensions=suspicious_score_dimensions,
            required_expectation_matches=required_matches,
            required_expectation_misses=required_misses,
            non_blocking_expectation_misses=non_blocking_misses,
            rationale=(
                "LLM judge dimension scores look copied from rubric weights "
                "instead of assigned as quality scores."
            ),
            evidence=_consistency_evidence(
                base=evidence,
                expectation=expectation_evidence,
                score_shape=score_shape_evidence,
                prioritize_score_shape=True,
            ),
        )
    if weighted_score < fail_floor:
        return LLMJudgeConsistencyCheck(
            status="fail",
            weighted_score=weighted_score,
            pass_floor=pass_floor,
            fail_floor=fail_floor,
            score_status="fail",
            score_shape_status=score_shape_status,
            suspicious_score_shape="rubric_weight_copy"
            if score_shape_status == "fail"
            else None,
            suspicious_score_dimensions=suspicious_score_dimensions,
            required_expectation_matches=required_matches,
            required_expectation_misses=required_misses,
            non_blocking_expectation_misses=non_blocking_misses,
            rationale=(
                "LLM judge numeric scores are below the fail floor, so the "
                "case cannot pass regardless of the textual status."
            ),
            evidence=_consistency_evidence(
                base=evidence,
                expectation=expectation_evidence,
                score_shape=score_shape_evidence,
            ),
        )
    if result.status == "pass" and weighted_score < pass_floor:
        return LLMJudgeConsistencyCheck(
            status="warn",
            weighted_score=weighted_score,
            pass_floor=pass_floor,
            fail_floor=fail_floor,
            score_status="warn",
            score_shape_status=score_shape_status,
            suspicious_score_shape="rubric_weight_copy"
            if score_shape_status == "fail"
            else None,
            suspicious_score_dimensions=suspicious_score_dimensions,
            required_expectation_matches=required_matches,
            required_expectation_misses=required_misses,
            non_blocking_expectation_misses=non_blocking_misses,
            rationale=(
                "LLM judge returned pass, but numeric scores are below the "
                "configured pass floor."
            ),
            evidence=_consistency_evidence(
                base=evidence,
                expectation=expectation_evidence,
                score_shape=score_shape_evidence,
            ),
        )
    return LLMJudgeConsistencyCheck(
        status="pass",
        weighted_score=weighted_score,
        pass_floor=pass_floor,
        fail_floor=fail_floor,
        score_status="pass",
        score_shape_status=score_shape_status,
        suspicious_score_shape="rubric_weight_copy"
        if score_shape_status == "fail"
        else None,
        suspicious_score_dimensions=suspicious_score_dimensions,
        required_expectation_matches=required_matches,
        required_expectation_misses=required_misses,
        non_blocking_expectation_misses=non_blocking_misses,
        rationale="LLM judge status is consistent with numeric scores.",
        evidence=_consistency_evidence(
            base=evidence,
            expectation=expectation_evidence,
            score_shape=score_shape_evidence,
        ),
    )


def _report_status(cases: list[NarrativeCaseJudgeReport]) -> RunReportStatus:
    if any(case.runtime_error is not None for case in cases):
        return "validation_failed"
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
            "runtime_completed": all(case.runtime_error is None for case in cases),
            "mock_user_runs_completed": all(
                case.runtime_error is None
                and case.deterministic_summary.get("turn_count", 0) > 0
                for case in cases
            ),
            "deterministic_evidence_present": all(case.deterministic_status in {"pass", "warn", "fail"} for case in cases),
            "llm_judge_present": all(
                case.llm_judge is not None and case.llm_judge.schema_version == "llm_judge.v1"
                for case in cases
            ),
            "llm_score_consistency": all(
                case.llm_consistency is not None and case.llm_consistency.score_status == "pass"
                for case in cases
            ),
            "llm_score_shape_consistency": all(
                case.llm_consistency is not None
                and case.llm_consistency.score_shape_status == "pass"
                for case in cases
            ),
            "llm_expectation_consistency": all(
                case.llm_consistency is not None
                and case.llm_consistency.expectation_status == "pass"
                for case in cases
            ),
            "llm_required_expectations_met": all(
                case.llm_consistency is not None
                and case.llm_consistency.required_expectation_status == "pass"
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
        try:
            episode = run_mock_user_episode(config, adapter)
        except Exception as exc:
            runtime_failure = _runtime_failure_artifact(
                case=case,
                run_mode=resolved_mode,
                error=exc,
                trace_path=trace_path,
                summary_path=summary_path,
                llm_input_path=llm_input_path,
                llm_result_path=llm_result_path,
            )
            _write_runtime_failure_artifacts(
                failure=runtime_failure,
                error=exc,
                trace_path=trace_path,
                summary_path=summary_path,
                llm_input_path=llm_input_path,
                llm_result_path=llm_result_path,
            )
            case_reports.append(
                NarrativeCaseJudgeReport(
                    case_id=case.case_id,
                    name=case.name,
                    run_mode=resolved_mode,
                    deterministic_status="fail",
                    llm_status="fail",
                    status="fail",
                    disagreement=True,
                    trace_path=str(trace_path),
                    summary_path=str(summary_path),
                    llm_input_path=str(llm_input_path),
                    llm_result_path=str(llm_result_path),
                    deterministic_summary=runtime_failure.deterministic_summary,
                    runtime_error=runtime_failure,
                )
            )
            continue
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
