from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RuntimeErrorBucketPayload(BaseModel):
    error_code: str
    stage: str
    model: str
    failed_count: int = Field(ge=0)
    error_share: float = Field(ge=0.0, le=1.0)
    last_seen_at: datetime | None = None
    sample_session_ids: list[str] = Field(default_factory=list)
    sample_request_ids: list[str] = Field(default_factory=list)


class RuntimeErrorsAggregateResponse(BaseModel):
    generated_at: datetime
    window_seconds: int = Field(ge=60, le=3600)
    started_total: int = Field(ge=0)
    failed_total: int = Field(ge=0)
    step_error_rate: float = Field(ge=0.0, le=1.0)
    buckets: list[RuntimeErrorBucketPayload] = Field(default_factory=list)


class Http5xxPathBucketPayload(BaseModel):
    path: str
    failed_count: int = Field(ge=0)
    sample_request_ids: list[str] = Field(default_factory=list)


class ObservabilityWindowPayload(BaseModel):
    generated_at: datetime
    window_started_at: datetime
    window_ended_at: datetime
    window_seconds: int = Field(ge=60, le=3600)


class HttpHealthAggregateResponse(ObservabilityWindowPayload):
    service: Literal["backend", "worker"]
    total_requests: int = Field(ge=0)
    failed_5xx: int = Field(ge=0)
    error_rate: float = Field(ge=0.0, le=1.0)
    p95_ms: int | None = Field(default=None, ge=0)
    top_5xx_paths: list[Http5xxPathBucketPayload] = Field(default_factory=list)


class LLMCallGroupHealthPayload(BaseModel):
    total_calls: int = Field(default=0, ge=0)
    failed_calls: int = Field(default=0, ge=0)
    failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    p95_ms: int | None = Field(default=None, ge=0)


class LLMCallByStagePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    route: LLMCallGroupHealthPayload = Field(default_factory=LLMCallGroupHealthPayload)
    narration: LLMCallGroupHealthPayload = Field(default_factory=LLMCallGroupHealthPayload)
    json_stage: LLMCallGroupHealthPayload = Field(default_factory=LLMCallGroupHealthPayload, alias="json")
    unknown: LLMCallGroupHealthPayload = Field(default_factory=LLMCallGroupHealthPayload)


class LLMCallByGatewayModePayload(BaseModel):
    worker: LLMCallGroupHealthPayload = Field(default_factory=LLMCallGroupHealthPayload)
    unknown: LLMCallGroupHealthPayload = Field(default_factory=LLMCallGroupHealthPayload)


class LLMCallHealthAggregateResponse(ObservabilityWindowPayload):
    total_calls: int = Field(ge=0)
    failed_calls: int = Field(ge=0)
    failure_rate: float = Field(ge=0.0, le=1.0)
    p95_ms: int | None = Field(default=None, ge=0)
    by_stage: LLMCallByStagePayload = Field(default_factory=LLMCallByStagePayload)
    by_gateway_mode: LLMCallByGatewayModePayload = Field(default_factory=LLMCallByGatewayModePayload)


class ReadinessFailurePayload(BaseModel):
    service: Literal["backend", "worker"]
    error_code: str | None = None
    request_id: str | None = None
    created_at: datetime


class ReadinessHealthAggregateResponse(ObservabilityWindowPayload):
    backend_ready_fail_count: int = Field(ge=0)
    worker_ready_fail_count: int = Field(ge=0)
    backend_fail_streak: int = Field(ge=0)
    worker_fail_streak: int = Field(ge=0)
    last_failures: list[ReadinessFailurePayload] = Field(default_factory=list)


class ReadinessCheckPayload(BaseModel):
    ok: bool
    latency_ms: int | None = None
    checked_at: datetime | None = None
    error_code: str | None = None
    message: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ReadinessChecksPayload(BaseModel):
    db: ReadinessCheckPayload
    llm_config: ReadinessCheckPayload
    llm_probe: ReadinessCheckPayload


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checked_at: datetime
    checks: ReadinessChecksPayload
