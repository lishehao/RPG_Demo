from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EvalFailureCategory = Literal[
    "environment",
    "provider",
    "schema",
    "author_content",
    "runtime_invariant",
    "player_policy",
    "trajectory_oracle",
    "judge_unavailable",
    "judge_disagreement",
    "timeout",
    "artifact",
]

EvalGateName = Literal[
    "author_valid",
    "runtime_valid",
    "agency_valid",
    "trajectory_valid",
    "quality_review_valid",
    "ops_valid",
]

EvalEventType = Literal[
    "author_step",
    "publish_step",
    "session_start",
    "player_action",
    "runtime_output",
    "state_delta",
    "ending",
    "judge_call",
    "failure",
]


class EvalOracleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_turns: int = Field(default=6, ge=1, le=80)
    min_distinct_endings: int = Field(default=1, ge=1, le=8)
    min_state_divergence: float = Field(default=0.25, ge=0, le=1)
    required_state_keys: list[str] = Field(default_factory=list, max_length=16)


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=80)
    seed: str = Field(min_length=1, max_length=2000)
    expected_shells: list[str] = Field(default_factory=list, min_length=1, max_length=8)
    play_length: Literal["short", "standard", "flagship"] = "short"
    required_affordances: list[str] = Field(default_factory=list, max_length=16)
    oracle: EvalOracleConfig = Field(default_factory=EvalOracleConfig)


class EvalPlayerPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=300)
    risk_bias: Literal["low", "medium", "high"] = "medium"


class EvalFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: EvalFailureCategory
    message: str = Field(min_length=1, max_length=1000)
    stage: str = Field(min_length=1, max_length=80)
    event_index: int | None = Field(default=None, ge=0)


class EvalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_index: int = Field(ge=0)
    event_type: EvalEventType
    case_id: str = Field(min_length=1, max_length=80)
    policy_id: str | None = Field(default=None, max_length=64)
    trial_index: int = Field(default=0, ge=0)
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


class EvalGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate: EvalGateName
    passed: bool
    evidence_count: int = Field(ge=0)
    failures: list[EvalFailure] = Field(default_factory=list)


class EvalCaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=80)
    gates: list[EvalGateResult]
    primary_failure: EvalFailure | None = None

    @property
    def passed(self) -> bool:
        hard_gates = {
            "author_valid",
            "runtime_valid",
            "agency_valid",
            "trajectory_valid",
            "ops_valid",
        }
        return all(result.passed for result in self.gates if result.gate in hard_gates)


class EvalRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eval_version: Literal["v3"] = "v3"
    run_id: str = Field(min_length=1, max_length=120)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    git_sha: str | None = Field(default=None, max_length=80)
    mode: Literal["dry_run", "runtime"] = "dry_run"
    case_count: int = Field(ge=0)
    policy_count: int = Field(ge=0)
    notes: list[str] = Field(default_factory=list, max_length=16)


class EvalGateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: EvalRunManifest
    case_summaries: list[EvalCaseSummary]
    passed_case_count: int = Field(ge=0)
    failed_case_count: int = Field(ge=0)
    gate_pass_counts: dict[EvalGateName, int] = Field(default_factory=dict)
    failure_counts: dict[EvalFailureCategory, int] = Field(default_factory=dict)
