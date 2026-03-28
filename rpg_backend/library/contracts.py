from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rpg_backend.author.contracts import (
    AuthorPreviewResponse,
    AuthorStorySummary,
    DesignBundle,
    PortraitVariants,
    StoryBranchBudget,
)
from rpg_backend.content_language import ContentLanguage
from rpg_backend.play.contracts import PlayProtagonist

StoryVisibility = Literal["private", "public"]


class PublishedStoryCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: str = Field(min_length=1)
    language: ContentLanguage = "en"
    title: str = Field(min_length=1, max_length=120)
    one_liner: str = Field(min_length=1, max_length=220)
    premise: str = Field(min_length=1, max_length=320)
    theme: str = Field(min_length=1, max_length=80)
    tone: str = Field(min_length=1, max_length=120)
    npc_count: int = Field(ge=1)
    beat_count: int = Field(ge=1)
    topology: str = Field(min_length=1, max_length=80)
    visibility: StoryVisibility = "private"
    viewer_can_manage: bool = False
    published_at: datetime


PublishedStoryListSort = Literal["published_at_desc", "relevance"]
PublishedStoryListView = Literal["accessible", "mine", "public"]


class PublishedStoryThemeFacet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: str = Field(min_length=1, max_length=80)
    count: int = Field(ge=0)


class PublishedStoryListFacets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    themes: list[PublishedStoryThemeFacet] = Field(default_factory=list)


class PublishedStoryListMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=200)
    theme: str | None = Field(default=None, max_length=80)
    language: ContentLanguage | None = None
    view: PublishedStoryListView = "accessible"
    sort: PublishedStoryListSort
    limit: int = Field(ge=1)
    next_cursor: str | None = None
    has_more: bool = False
    total: int = Field(ge=0)


class PublishedStoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stories: list[PublishedStoryCard] = Field(default_factory=list)
    meta: PublishedStoryListMeta | None = None
    facets: PublishedStoryListFacets | None = None


class PublishedStoryPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dossier_ref: str = Field(min_length=1, max_length=40)
    status: Literal["open_for_play"]
    status_label: str = Field(min_length=1, max_length=80)
    classification_label: str = Field(min_length=1, max_length=120)
    engine_label: str = Field(min_length=1, max_length=120)
    visibility: StoryVisibility = "private"
    viewer_can_manage: bool = False


class PublishedStoryPlayOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protagonist: PlayProtagonist
    opening_narration: str = Field(min_length=1, max_length=4000)
    runtime_profile: str = Field(min_length=1, max_length=80)
    runtime_profile_label: str = Field(min_length=1, max_length=120)
    max_turns: int = Field(ge=1)
    target_duration_minutes: int | None = Field(default=None, ge=10, le=25)
    branch_budget: StoryBranchBudget | None = None


class PublishedStoryBeatOutline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=220)
    milestone_kind: str = Field(min_length=1, max_length=32)


class PublishedStoryStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topology_label: str = Field(min_length=1, max_length=80)
    beat_outline: list[PublishedStoryBeatOutline] = Field(default_factory=list, max_length=5)


class PublishedStoryCastEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    agenda: str = Field(min_length=1, max_length=220)
    red_line: str = Field(min_length=1, max_length=220)
    pressure_signature: str = Field(min_length=1, max_length=220)
    roster_character_id: str | None = None
    roster_public_summary: str | None = Field(default=None, max_length=220)
    portrait_url: str | None = Field(default=None, max_length=260)
    portrait_variants: PortraitVariants | None = None


class PublishedStoryCastManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[PublishedStoryCastEntry] = Field(default_factory=list, max_length=5)


class PublishedStoryDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story: PublishedStoryCard
    presentation: PublishedStoryPresentation | None = None
    structure: PublishedStoryStructure
    cast_manifest: PublishedStoryCastManifest
    play_overview: PublishedStoryPlayOverview | None = None


class PublishedStoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story: PublishedStoryCard
    owner_user_id: str = Field(min_length=1, max_length=80)
    source_job_id: str = Field(min_length=1)
    prompt_seed: str = Field(min_length=1, max_length=4000)
    visibility: StoryVisibility = "private"
    summary: AuthorStorySummary
    preview: AuthorPreviewResponse
    bundle: DesignBundle


class UpdateStoryVisibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility: StoryVisibility


class DeleteStoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: str = Field(min_length=1)
    deleted: bool = True
