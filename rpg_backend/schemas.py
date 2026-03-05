from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ErrorPayload(BaseModel):
    code: str
    message: str
    retryable: bool = False
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorPayload


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AdminLoginResponse(BaseModel):
    token: str
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class StoryGenerateRequest(BaseModel):
    theme: str = Field(min_length=1, max_length=120)
    difficulty: str = Field(min_length=1, max_length=40)


class StoryGenerateResponse(BaseModel):
    story_id: str
    title: str
    published: bool


class StoryListItem(BaseModel):
    story_id: str
    title: str


class StoryListResponse(BaseModel):
    stories: list[StoryListItem] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    story_id: str = Field(min_length=1)


class SessionCreateResponse(BaseModel):
    session_id: str


class SessionGetResponse(BaseModel):
    session_id: str
    story_id: str
    created_at: datetime
    state: Literal["active", "completed"]


class SessionAction(BaseModel):
    id: str
    label: str


class SessionHistoryTurn(BaseModel):
    turn: int = Field(ge=1)
    narration: str
    actions: list[SessionAction] = Field(default_factory=list)


class SessionHistoryResponse(BaseModel):
    history: list[SessionHistoryTurn] = Field(default_factory=list)


class SessionStepRequest(BaseModel):
    move_id: str | None = None
    free_text: str | None = None

    @model_validator(mode="after")
    def validate_one_input(self) -> "SessionStepRequest":
        move = (self.move_id or "").strip()
        text = (self.free_text or "").strip()
        if bool(move) == bool(text):
            raise ValueError("provide exactly one of move_id or free_text")
        self.move_id = move or None
        self.free_text = text or None
        return self


class SessionStepResponse(BaseModel):
    turn: int = Field(ge=1)
    narration: str
    actions: list[SessionAction] = Field(default_factory=list)
    risk_hint: Literal["low", "medium", "high"]

