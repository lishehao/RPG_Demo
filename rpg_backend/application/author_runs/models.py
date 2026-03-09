from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CreateAuthorRunCommand:
    raw_brief: str


@dataclass(frozen=True)
class AuthorRunCreateView:
    story_id: str
    run_id: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class AuthorRunArtifactView:
    artifact_type: str
    artifact_key: str
    payload: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True)
class AuthorRunEventView:
    event_id: str
    node_name: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class AuthorRunView:
    run_id: str
    story_id: str
    status: str
    current_node: str | None
    raw_brief: str
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    artifacts: list[AuthorRunArtifactView]


@dataclass(frozen=True)
class AuthorStorySummaryView:
    story_id: str
    title: str
    created_at: datetime
    latest_run_id: str | None
    latest_run_status: str | None
    latest_run_current_node: str | None
    latest_run_updated_at: datetime | None
    latest_published_version: int | None
    latest_published_at: datetime | None


@dataclass(frozen=True)
class AuthorStoryView:
    story_id: str
    title: str
    created_at: datetime
    latest_run: AuthorRunView | None
    latest_published_version: int | None
    latest_published_at: datetime | None
    draft_pack: dict[str, Any]
