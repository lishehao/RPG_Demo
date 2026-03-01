from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StoryCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    pack_json: dict[str, Any] = Field(default_factory=dict)


class StoryCreateResponse(BaseModel):
    story_id: str
    status: Literal["draft"]
    created_at: datetime


class StoryPublishResponse(BaseModel):
    story_id: str
    version: int
    published_at: datetime


class StoryGetResponse(BaseModel):
    story_id: str
    version: int
    pack: dict[str, Any]


class StoryGenerateRequest(BaseModel):
    seed_text: str = Field(min_length=1)
    target_minutes: int = Field(default=10, ge=8, le=12)
    npc_count: int = Field(default=4, ge=3, le=5)
    style: str | None = None
    publish: bool = False


class StoryGenerateResponse(BaseModel):
    status: Literal["placeholder"]
    story_id: str | None = None
    version: int | None = None
    pack: dict[str, Any] = Field(default_factory=dict)
    lint_report: dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    notes: list[str] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    story_id: str
    version: int = Field(ge=1)


class SessionCreateResponse(BaseModel):
    session_id: str
    story_id: str
    version: int
    scene_id: str
    state_summary: dict[str, Any]


class StepInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str | None = None
    move_id: str | None = None
    text: str | None = None


class SessionStepRequest(BaseModel):
    client_action_id: str = Field(min_length=1)
    input: StepInput | None = None
    dev_mode: bool = False


class SessionStepResponse(BaseModel):
    session_id: str
    version: int
    scene_id: str
    narration_text: str
    recognized: dict[str, Any]
    resolution: dict[str, Any]
    ui: dict[str, Any]
    debug: dict[str, Any] | None = None


class SessionGetResponse(BaseModel):
    session_id: str
    scene_id: str
    beat_progress: dict[str, Any]
    ended: bool
    state_summary: dict[str, Any]
    state: dict[str, Any] | None = None
