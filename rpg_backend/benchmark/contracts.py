from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rpg_backend.author.contracts import (
    AuthorCacheMetrics,
    AuthorStorySummary,
    AuthorTokenCostEstimate,
)


class BenchmarkAuthorJobEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    event: str = Field(min_length=1, max_length=64)
    emitted_at: datetime
    status: str | None = Field(default=None, max_length=32)
    stage: str | None = Field(default=None, max_length=64)
    stage_index: int | None = Field(default=None, ge=0)
    stage_total: int | None = Field(default=None, ge=1)


class BenchmarkStageTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str = Field(min_length=1, max_length=64)
    started_at: datetime
    ended_at: datetime | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)


class BenchmarkAuthorJobDiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    content_prompt_profile: str = Field(min_length=1, max_length=32)
    status: Literal["queued", "running", "completed", "failed"]
    prompt_seed: str = Field(min_length=1, max_length=4000)
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    summary: AuthorStorySummary | None = None
    error: dict[str, str] | None = None
    cache_metrics: AuthorCacheMetrics | None = None
    token_cost_estimate: AuthorTokenCostEstimate | None = None
    llm_call_trace: list[dict[str, Any]] = Field(default_factory=list)
    quality_trace: list[dict[str, Any]] = Field(default_factory=list)
    source_summary: dict[str, str] = Field(default_factory=dict)
    context_lock_violation_distribution: dict[str, int] = Field(default_factory=dict)
    snapshot_stage_distribution: dict[str, int] = Field(default_factory=dict)
    drift_repair_entry_count: int = Field(default=0, ge=0)
    beat_runtime_shard_count: int = Field(default=0, ge=0)
    beat_runtime_shard_fallback_count: int = Field(default=0, ge=0)
    beat_runtime_shard_elapsed_ms: int = Field(default=0, ge=0)
    beat_runtime_shard_drift_distribution: dict[str, int] = Field(default_factory=dict)
    roster_catalog_version: str | None = None
    roster_enabled: bool = False
    roster_selection_count: int = Field(default=0, ge=0)
    roster_retrieval_trace: list[dict[str, Any]] = Field(default_factory=list)
    stage_timings: list[BenchmarkStageTiming] = Field(default_factory=list)
    events: list[BenchmarkAuthorJobEvent] = Field(default_factory=list)


class BenchmarkPlayTraceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_count: int = Field(ge=0)
    total_turn_elapsed_ms: int = Field(ge=0)
    total_interpret_elapsed_ms: int = Field(ge=0)
    total_ending_judge_elapsed_ms: int = Field(ge=0)
    total_pyrrhic_critic_elapsed_ms: int = Field(ge=0)
    total_render_elapsed_ms: int = Field(ge=0)
    interpret_source_distribution: dict[str, int] = Field(default_factory=dict)
    ending_judge_source_distribution: dict[str, int] = Field(default_factory=dict)
    pyrrhic_critic_source_distribution: dict[str, int] = Field(default_factory=dict)
    render_source_distribution: dict[str, int] = Field(default_factory=dict)
    render_primary_path_mode_distribution: dict[str, int] = Field(default_factory=dict)
    render_failure_reason_distribution: dict[str, int] = Field(default_factory=dict)
    interpret_failure_reason_distribution: dict[str, int] = Field(default_factory=dict)
    capability_distribution: dict[str, int] = Field(default_factory=dict)
    provider_distribution: dict[str, int] = Field(default_factory=dict)
    heuristic_interpret_turn_count: int = Field(ge=0)
    ending_judge_failed_turn_count: int = Field(default=0, ge=0)
    ending_judge_stage1_success_rate: float = Field(default=0.0, ge=0, le=1)
    ending_judge_stage2_rescue_rate: float = Field(default=0.0, ge=0, le=1)
    pyrrhic_critic_stage1_success_rate: float = Field(default=0.0, ge=0, le=1)
    pyrrhic_critic_stage2_rescue_rate: float = Field(default=0.0, ge=0, le=1)
    render_plan_stage1_success_rate: float = Field(default=0.0, ge=0, le=1)
    render_plan_primary_success_rate: float = Field(default=0.0, ge=0, le=1)
    render_plan_stage2_rescue_rate: float = Field(default=0.0, ge=0, le=1)
    render_narration_stage1_success_rate: float = Field(default=0.0, ge=0, le=1)
    render_narration_stage2_rescue_rate: float = Field(default=0.0, ge=0, le=1)
    render_direct_primary_success_rate: float = Field(default=0.0, ge=0, le=1)
    render_fallback_turn_count: int = Field(ge=0)
    render_repair_entry_rate: float = Field(default=0.0, ge=0, le=1)
    render_stage1_contract_failure_distribution: dict[str, int] = Field(default_factory=dict)
    repair_turn_count: int = Field(ge=0)
    used_previous_response_turn_count: int = Field(ge=0)
    session_cache_enabled: bool = False
    usage_totals: dict[str, int] = Field(default_factory=dict)
    ending_id: str | None = None
    end_reason: str | None = Field(default=None, max_length=120)


class BenchmarkPlaySessionDiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    story_id: str = Field(min_length=1)
    content_prompt_profile: str = Field(min_length=1, max_length=32)
    status: Literal["active", "completed", "expired"]
    created_at: datetime
    expires_at: datetime
    finished_at: datetime | None = None
    turn_traces: list[dict[str, Any]] = Field(default_factory=list)
    summary: BenchmarkPlayTraceSummary
