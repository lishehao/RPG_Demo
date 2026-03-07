from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rpg_backend.api.contracts.stories import OpeningGuidancePayload


class SessionCreateRequest(BaseModel):
    story_id: str
    version: int = Field(ge=1)


class SessionCreateResponse(BaseModel):
    session_id: str
    story_id: str
    version: int
    scene_id: str
    state_summary: dict[str, Any]
    opening_guidance: OpeningGuidancePayload


class StepInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str | None = None
    move_id: str | None = None
    text: str | None = None


class SessionStepRequest(BaseModel):
    client_action_id: str = Field(min_length=1)
    input: StepInput | None = None
    dev_mode: bool = False


class SessionRecognizedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interpreted_intent: str
    move_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    route_source: Literal["button", "button_fallback", "llm"]
    llm_duration_ms: int | None = Field(default=None, ge=0)
    llm_gateway_mode: Literal["worker", "unknown"] | None = None


class SessionResolutionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: str
    costs_summary: str
    consequences_summary: str


class SessionUiMovePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    move_id: str
    label: str
    risk_hint: str


class SessionUiPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moves: list[SessionUiMovePayload] = Field(default_factory=list)
    input_hint: str


class SessionStepDebugStancePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    support: list[str] = Field(default_factory=list)
    oppose: list[str] = Field(default_factory=list)
    contested: list[str] = Field(default_factory=list)
    red_line_hits: list[str] = Field(default_factory=list)


class SessionStepDebugPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_move: str
    selected_outcome: str
    selected_strategy_style: str
    pressure_recoil_triggered: bool
    stance_snapshot: SessionStepDebugStancePayload
    state: dict[str, Any] = Field(default_factory=dict)
    beat_progress: dict[str, int] = Field(default_factory=dict)


class SessionStepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    version: int
    scene_id: str
    narration_text: str
    recognized: SessionRecognizedPayload
    resolution: SessionResolutionPayload
    ui: SessionUiPayload
    debug: SessionStepDebugPayload | None = None


class SessionGetResponse(BaseModel):
    session_id: str
    scene_id: str
    beat_progress: dict[str, Any]
    ended: bool
    state_summary: dict[str, Any]
    opening_guidance: OpeningGuidancePayload
    state: dict[str, Any] | None = None


class SessionHistoryTurn(BaseModel):
    turn_index: int = Field(ge=1)
    scene_id: str
    narration_text: str
    recognized: SessionRecognizedPayload
    resolution: SessionResolutionPayload
    ui: SessionUiPayload
    ended: bool = False


class SessionHistoryResponse(BaseModel):
    session_id: str
    history: list[SessionHistoryTurn] = Field(default_factory=list)


class SessionFeedbackCreateRequest(BaseModel):
    verdict: Literal["good", "bad"]
    reason_tags: list[str] = Field(default_factory=list, max_length=8)
    note: str | None = Field(default=None, max_length=2000)
    turn_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def normalize_fields(self) -> "SessionFeedbackCreateRequest":
        tags: list[str] = []
        for raw in self.reason_tags:
            normalized = raw.strip()
            if normalized:
                tags.append(normalized)
        self.reason_tags = tags

        if self.note is not None:
            trimmed = self.note.strip()
            self.note = trimmed or None
        return self


class SessionFeedbackItem(BaseModel):
    feedback_id: str
    session_id: str
    story_id: str
    version: int
    verdict: Literal["good", "bad"]
    reason_tags: list[str] = Field(default_factory=list)
    note: str | None = None
    turn_index: int | None = None
    created_at: datetime


class SessionFeedbackListResponse(BaseModel):
    session_id: str
    items: list[SessionFeedbackItem] = Field(default_factory=list)
