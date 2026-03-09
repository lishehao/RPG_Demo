from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkerTaskErrorPayload(BaseModel):
    error_code: str
    message: str
    retryable: bool = False
    provider_status: int | None = None
    model: str | None = None
    attempts: int = Field(default=1, ge=1)


class WorkerTaskJsonObjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    model: str = Field(min_length=1)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_retries: int = Field(default=3, ge=1, le=3)
    timeout_seconds: float | None = Field(default=None, gt=0)


class WorkerTaskJsonObjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any] = Field(default_factory=dict)
    model: str
    attempts: int = Field(ge=1, le=3)
    retry_count: int = Field(ge=0, le=2)
    duration_ms: int = Field(ge=0)


class WorkerReadyCheckPayload(BaseModel):
    ok: bool
    checked_at: datetime
    latency_ms: int | None = None
    error_code: str | None = None
    message: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class WorkerReadyResponse(BaseModel):
    status: str
    checked_at: datetime
    checks: dict[str, WorkerReadyCheckPayload]
