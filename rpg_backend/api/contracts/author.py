from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AuthorRunCreateRequest(BaseModel):
    raw_brief: str = Field(min_length=1, max_length=4000)


class AuthorRunCreateResponse(BaseModel):
    story_id: str
    run_id: str
    status: Literal["pending", "running", "review_ready", "failed"]
    created_at: datetime


class AuthorRunEventPayload(BaseModel):
    event_id: str
    node_name: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuthorRunEventsResponse(BaseModel):
    run_id: str
    events: list[AuthorRunEventPayload] = Field(default_factory=list)


class AuthorRunArtifactSummary(BaseModel):
    artifact_type: str
    artifact_key: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


class AuthorRunGetResponse(BaseModel):
    run_id: str
    story_id: str
    status: Literal["pending", "running", "review_ready", "failed"]
    current_node: str | None = None
    raw_brief: str
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    artifacts: list[AuthorRunArtifactSummary] = Field(default_factory=list)


class AuthorStoryListItem(BaseModel):
    story_id: str
    title: str
    created_at: datetime
    latest_run_id: str | None = None
    latest_run_status: str | None = None
    latest_run_current_node: str | None = None
    latest_run_updated_at: datetime | None = None
    latest_published_version: int | None = None
    latest_published_at: datetime | None = None


class AuthorStoryListResponse(BaseModel):
    stories: list[AuthorStoryListItem] = Field(default_factory=list)


class AuthorStoryGetResponse(BaseModel):
    story_id: str
    title: str
    created_at: datetime
    latest_run: AuthorRunGetResponse | None = None
    latest_published_version: int | None = None
    latest_published_at: datetime | None = None
    draft_pack: dict[str, Any] = Field(default_factory=dict)
