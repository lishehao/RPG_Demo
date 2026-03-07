from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AdminSessionTimelineEvent(BaseModel):
    event_id: str
    turn_index: int
    event_type: Literal["step_started", "step_succeeded", "step_failed", "step_replayed", "step_conflicted"]
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AdminSessionTimelineResponse(BaseModel):
    session_id: str
    events: list[AdminSessionTimelineEvent] = Field(default_factory=list)


class AdminAuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=512)


class AdminUserPublic(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class AdminAuthLoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: AdminUserPublic


class AdminUserListResponse(BaseModel):
    items: list[AdminUserPublic] = Field(default_factory=list)
