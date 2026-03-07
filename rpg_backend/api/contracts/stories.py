from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class OpeningGuidancePayload(BaseModel):
    intro_text: str
    goal_hint: str
    starter_prompts: list[str] = Field(min_length=3, max_length=3)


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


class StoryListItem(BaseModel):
    story_id: str
    title: str
    created_at: datetime
    has_draft: bool
    latest_published_version: int | None = None
    latest_published_at: datetime | None = None


class StoryListResponse(BaseModel):
    stories: list[StoryListItem] = Field(default_factory=list)


class StoryDraftGetResponse(BaseModel):
    story_id: str
    title: str
    created_at: datetime
    draft_pack: dict[str, Any]
    latest_published_version: int | None = None
    latest_published_at: datetime | None = None


class StoryDraftPatchChange(BaseModel):
    target_type: Literal["story", "beat", "scene", "npc", "opening_guidance"]
    field: Literal[
        "title",
        "description",
        "style_guard",
        "input_hint",
        "scene_seed",
        "red_line",
        "intro_text",
        "goal_hint",
        "starter_prompt_1",
        "starter_prompt_2",
        "starter_prompt_3",
    ]
    target_id: str | None = None
    value: str

    @model_validator(mode="after")
    def validate_target_and_field(self) -> "StoryDraftPatchChange":
        if self.target_type in {"story", "opening_guidance"}:
            if self.target_id not in {None, ""}:
                raise ValueError(f"{self.target_type} target_type must not include target_id")
            allowed_story_fields = {"title", "description", "style_guard", "input_hint"}
            allowed_opening_fields = {"intro_text", "goal_hint", "starter_prompt_1", "starter_prompt_2", "starter_prompt_3"}
            allowed = allowed_story_fields if self.target_type == "story" else allowed_opening_fields
            if self.field not in allowed:
                allowed_text = ", ".join(sorted(allowed))
                raise ValueError(f"{self.target_type} target_type only supports {allowed_text}")
            return self

        normalized_target_id = (self.target_id or "").strip()
        if not normalized_target_id:
            raise ValueError(f"{self.target_type} target_type requires target_id")
        self.target_id = normalized_target_id

        allowed_fields = {
            "beat": {"title"},
            "scene": {"scene_seed"},
            "npc": {"red_line"},
        }
        if self.field not in allowed_fields[self.target_type]:
            allowed = ", ".join(sorted(allowed_fields[self.target_type]))
            raise ValueError(f"{self.target_type} target_type only supports {allowed}")
        return self


class StoryDraftPatchRequest(BaseModel):
    changes: list[StoryDraftPatchChange] = Field(min_length=1, max_length=64)


class StoryGenerateRequest(BaseModel):
    seed_text: str | None = None
    prompt_text: str | None = None
    target_minutes: int = Field(default=10, ge=8, le=12)
    npc_count: int = Field(default=4, ge=3, le=5)
    style: str | None = None
    variant_seed: str | int | None = None
    candidate_parallelism: int | None = Field(default=None, ge=1, le=8)
    generator_version: str | None = None
    palette_policy: Literal["random", "balanced", "fixed"] = "random"
    publish: bool = False

    @model_validator(mode="after")
    def validate_prompt_or_seed(self) -> "StoryGenerateRequest":
        seed = (self.seed_text or "").strip()
        prompt = (self.prompt_text or "").strip()
        if not seed and not prompt:
            raise ValueError("either prompt_text or seed_text must be provided")
        return self


class LintReportPayload(BaseModel):
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GenerationCompilePayload(BaseModel):
    spec_hash: str | None = None
    spec_summary: dict[str, Any] | None = None


class GenerationAttemptRecord(BaseModel):
    attempt_index: int = Field(ge=1, le=4)
    variant_seed: str
    winner_candidate_index: int | None = Field(default=None, ge=0)
    winner_candidate_seed: str | None = None
    best_candidate_index: int | None = Field(default=None, ge=0)
    best_candidate_seed: str | None = None
    lint_ok: bool
    candidate_count: int = Field(ge=1, le=8)


class GenerationDiagnostics(BaseModel):
    mode: Literal["prompt", "seed"]
    generator_version: str
    variant_seed: str
    palette_policy: Literal["random", "balanced", "fixed"]
    attempts: int = Field(default=1, ge=1, le=4)
    regenerate_count: int = Field(default=0, ge=0, le=3)
    candidate_parallelism: int = Field(default=1, ge=1, le=8)
    compile: GenerationCompilePayload = Field(default_factory=GenerationCompilePayload)
    lint: LintReportPayload = Field(default_factory=LintReportPayload)
    attempt_history: list[GenerationAttemptRecord] = Field(default_factory=list)


class StoryGenerateResponse(BaseModel):
    status: Literal["ok"]
    story_id: str
    version: int | None = None
    pack: dict[str, Any] = Field(default_factory=dict)
    pack_hash: str
    generation: GenerationDiagnostics
