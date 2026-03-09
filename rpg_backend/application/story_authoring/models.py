from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from rpg_backend.application.story_draft.models import DraftPatchChange, StoryDraftView


@dataclass(frozen=True)
class CreateStoryCommand:
    title: str
    pack_json: dict[str, Any]


@dataclass(frozen=True)
class StoryCreateView:
    story_id: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class StorySummaryView:
    story_id: str
    title: str
    created_at: datetime
    has_draft: bool
    latest_published_version: int | None = None
    latest_published_at: datetime | None = None


@dataclass(frozen=True)
class StoryPublishView:
    story_id: str
    version: int
    published_at: datetime


@dataclass(frozen=True)
class StoryGetView:
    story_id: str
    version: int
    pack: dict[str, Any]


__all__ = [
    "CreateStoryCommand",
    "DraftPatchChange",
    "StoryCreateView",
    "StoryDraftView",
    "StoryGetView",
    "StoryPublishView",
    "StorySummaryView",
]
