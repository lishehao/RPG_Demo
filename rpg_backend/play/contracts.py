from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rpg_backend.author.contracts import (
    AffordanceEffectProfile,
    AffordanceTag,
    AxisDefinition,
    BeatSpec,
    CastMember,
    EndingItem,
    EndingRule,
    FlagDefinition,
    StanceDefinition,
    StoryFunction,
    TruthItem,
)

ExecutionFrame = Literal["procedural", "coalition", "public", "coercive"]


class PlaySessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: str = Field(min_length=1)


class PlayTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_text: str = Field(min_length=1, max_length=2000)
    selected_suggestion_id: str | None = None


class PlayStateBar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bar_id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    category: Literal["axis", "stance"]
    current_value: int
    min_value: int
    max_value: int


class PlaySuggestedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion_id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=220)


class PlayEnding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=220)


class PlayProtagonist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    mandate: str = Field(min_length=1, max_length=220)
    identity_summary: str = Field(min_length=1, max_length=320)


class PlaySuccessLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proof_progress: int = Field(ge=0)
    coalition_progress: int = Field(ge=0)
    order_progress: int = Field(ge=0)
    settlement_progress: int = Field(ge=0)


class PlayCostLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_cost: int = Field(ge=0)
    relationship_cost: int = Field(ge=0)
    procedural_cost: int = Field(ge=0)
    coercion_cost: int = Field(ge=0)


class PlayLedgerSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: PlaySuccessLedger
    cost: PlayCostLedger


class PlayFeedbackSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ledgers: PlayLedgerSnapshot
    last_turn_axis_deltas: dict[str, int] = Field(default_factory=dict)
    last_turn_stance_deltas: dict[str, int] = Field(default_factory=dict)
    last_turn_tags: list[str] = Field(default_factory=list, max_length=8)
    last_turn_consequences: list[str] = Field(default_factory=list, max_length=8)


class PlaySessionHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["gm", "player"]
    text: str = Field(min_length=1, max_length=4000)
    created_at: datetime
    turn_index: int = Field(ge=0)


class PlaySessionHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    story_id: str = Field(min_length=1)
    entries: list[PlaySessionHistoryEntry] = Field(default_factory=list)


class PlaySessionProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_beats: int = Field(ge=0)
    total_beats: int = Field(ge=1)
    current_beat_progress: int = Field(ge=0)
    current_beat_goal: int = Field(ge=1)
    turn_index: int = Field(ge=0)
    max_turns: int = Field(ge=1)
    completion_ratio: float = Field(ge=0, le=1)
    display_percent: int = Field(ge=0, le=100)


class PlaySupportSurface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    disabled_reason: str | None = Field(default=None, max_length=220)


class PlaySupportSurfaces(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory: PlaySupportSurface = Field(default_factory=PlaySupportSurface)
    map: PlaySupportSurface = Field(default_factory=PlaySupportSurface)


class PlaySessionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    story_id: str = Field(min_length=1)
    status: Literal["active", "completed", "expired"]
    turn_index: int = Field(ge=0)
    beat_index: int = Field(ge=1)
    beat_title: str = Field(min_length=1, max_length=120)
    story_title: str = Field(min_length=1, max_length=120)
    narration: str = Field(min_length=1, max_length=4000)
    protagonist: PlayProtagonist | None = None
    feedback: PlayFeedbackSnapshot | None = None
    progress: PlaySessionProgress | None = None
    support_surfaces: PlaySupportSurfaces | None = None
    state_bars: list[PlayStateBar] = Field(default_factory=list, max_length=16)
    suggested_actions: list[PlaySuggestedAction] = Field(default_factory=list, max_length=3)
    ending: PlayEnding | None = None


class PlayTurnIntentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affordance_tag: AffordanceTag
    target_npc_ids: list[str] = Field(default_factory=list, max_length=3)
    risk_level: Literal["low", "medium", "high"] = "medium"
    execution_frame: ExecutionFrame = "procedural"
    tactic_summary: str = Field(min_length=1, max_length=220)


class PlayRenderActionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=220)


class PlayRenderDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narration: str = Field(min_length=1, max_length=4000)
    suggested_actions: list[PlayRenderActionDraft] = Field(min_length=3, max_length=3)


class PlayEndingIntentJudgeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_id: Literal["collapse", "pyrrhic", "mixed"]


class PlayPyrrhicCriticDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_id: Literal["pyrrhic", "mixed"]


class PlayPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: str = Field(min_length=1)
    story_title: str = Field(min_length=1, max_length=120)
    protagonist: PlayProtagonist
    protagonist_name: str | None = None
    protagonist_npc_id: str | None = None
    closeout_profile: str = Field(min_length=1, max_length=80)
    closeout_router_reason: str = Field(min_length=1, max_length=120)
    runtime_policy_profile: str = Field(min_length=1, max_length=80)
    runtime_router_reason: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=320)
    tone: str = Field(min_length=1, max_length=120)
    style_guard: str = Field(min_length=1, max_length=220)
    cast: list[CastMember] = Field(min_length=3, max_length=5)
    truths: list[TruthItem] = Field(min_length=1, max_length=8)
    endings: list[EndingItem] = Field(min_length=3, max_length=5)
    axes: list[AxisDefinition] = Field(min_length=2, max_length=6)
    stances: list[StanceDefinition] = Field(default_factory=list, max_length=5)
    flags: list[FlagDefinition] = Field(default_factory=list, max_length=8)
    beats: list[BeatSpec] = Field(min_length=1, max_length=6)
    route_unlock_rules: list = Field(default_factory=list)
    ending_rules: list[EndingRule] = Field(min_length=1, max_length=6)
    affordance_effect_profiles: list[AffordanceEffectProfile] = Field(min_length=2, max_length=12)
    available_affordance_tags: list[AffordanceTag] = Field(min_length=2, max_length=12)
    max_turns: int = Field(ge=1)
    opening_narration: str = Field(min_length=1, max_length=4000)


class PlayResolutionEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affordance_tag: AffordanceTag
    risk_level: Literal["low", "medium", "high"]
    execution_frame: ExecutionFrame = "procedural"
    target_npc_ids: list[str] = Field(default_factory=list, max_length=3)
    tactic_summary: str = Field(min_length=1, max_length=220)
    off_route: bool = False
    axis_changes: dict[str, int] = Field(default_factory=dict)
    stance_changes: dict[str, int] = Field(default_factory=dict)
    flag_changes: dict[str, bool] = Field(default_factory=dict)
    revealed_truth_ids: list[str] = Field(default_factory=list, max_length=4)
    added_event_ids: list[str] = Field(default_factory=list, max_length=4)
    beat_completed: bool = False
    advanced_to_next_beat: bool = False
    ending_id: str | None = None
    ending_trigger_reason: str | None = Field(default=None, max_length=120)
    pressure_note: str = Field(min_length=1, max_length=220)


class PlayTurnTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_index: int = Field(ge=1)
    created_at: datetime
    player_input: str = Field(min_length=1, max_length=2000)
    selected_suggestion_id: str | None = None
    interpret_source: Literal["llm", "llm_repair", "heuristic"]
    render_source: Literal["llm", "llm_repair", "fallback"]
    execution_frame: ExecutionFrame = "procedural"
    interpret_attempts: int = Field(ge=0)
    ending_judge_source: Literal["llm", "failed", "skipped"]
    pyrrhic_critic_source: Literal["llm", "failed", "skipped"]
    ending_judge_attempts: int = Field(ge=0)
    pyrrhic_critic_attempts: int = Field(ge=0)
    ending_judge_proposed_id: Literal["collapse", "pyrrhic", "mixed"] | None = None
    pyrrhic_critic_proposed_id: Literal["pyrrhic", "mixed"] | None = None
    ending_judge_failure_reason: str | None = Field(default=None, max_length=120)
    pyrrhic_critic_failure_reason: str | None = Field(default=None, max_length=120)
    ending_judge_response_id: str | None = None
    pyrrhic_critic_response_id: str | None = None
    ending_judge_usage: dict[str, int | str] = Field(default_factory=dict)
    pyrrhic_critic_usage: dict[str, int | str] = Field(default_factory=dict)
    render_attempts: int = Field(ge=0)
    interpret_failure_reason: str | None = Field(default=None, max_length=120)
    render_failure_reason: str | None = Field(default=None, max_length=120)
    interpret_response_id: str | None = None
    render_response_id: str | None = None
    interpret_usage: dict[str, int | str] = Field(default_factory=dict)
    render_usage: dict[str, int | str] = Field(default_factory=dict)
    turn_elapsed_ms: int = Field(default=0, ge=0)
    interpret_elapsed_ms: int = Field(default=0, ge=0)
    ending_judge_elapsed_ms: int = Field(default=0, ge=0)
    pyrrhic_critic_elapsed_ms: int = Field(default=0, ge=0)
    render_elapsed_ms: int = Field(default=0, ge=0)
    session_cache_enabled: bool = False
    used_previous_response_id: bool = False
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cache_creation_input_tokens: int | None = Field(default=None, ge=0)
    beat_index_before: int = Field(ge=1)
    beat_title_before: str = Field(min_length=1, max_length=120)
    beat_index_after: int = Field(ge=1)
    beat_title_after: str = Field(min_length=1, max_length=120)
    status_after: Literal["active", "completed", "expired"]
    resolution: PlayResolutionEffect
