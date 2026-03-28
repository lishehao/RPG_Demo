from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rpg_backend.author.contracts import (
    AffordanceEffectProfile,
    AffordanceTag,
    AxisDefinition,
    BeatSpec,
    CastMember,
    EndingItem,
    EndingRule,
    FlagDefinition,
    PortraitExpression,
    PortraitVariants,
    StoryBranchBudget,
    StanceDefinition,
    StoryFunction,
    TruthItem,
)
from rpg_backend.content_language import ContentLanguage

ExecutionFrame = Literal["procedural", "coalition", "public", "coercive"]


class PlaySessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: str = Field(min_length=1)


class PlayTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_text: str = Field(min_length=1, max_length=2000)
    selected_suggestion_id: str | None = None

    @field_validator("input_text", mode="before")
    @classmethod
    def _normalize_input_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


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
    language: ContentLanguage = "en"
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


class PlayNpcVisualState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    stance_value: int
    current_expression: PortraitExpression
    current_portrait_url: str | None = Field(default=None, max_length=260)
    portrait_variants: PortraitVariants | None = None


class PlayNpcEpilogueReaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    stance_value: int
    current_expression: PortraitExpression
    current_portrait_url: str | None = Field(default=None, max_length=260)
    portrait_variants: PortraitVariants | None = None
    closing_line: str = Field(min_length=1, max_length=240)


class PlaySessionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    story_id: str = Field(min_length=1)
    language: ContentLanguage = "en"
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
    npc_visuals: list[PlayNpcVisualState] = Field(default_factory=list, max_length=8)
    epilogue_reactions: list[PlayNpcEpilogueReaction] | None = None
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


class PlayRenderPlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_reaction: str = Field(min_length=1, max_length=240)
    axis_payoff: str = Field(min_length=1, max_length=240)
    stance_payoff: str | None = Field(default=None, max_length=240)
    immediate_consequence: str = Field(min_length=1, max_length=240)
    closing_pressure: str = Field(min_length=1, max_length=240)


class PlayEndingIntentJudgeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_id: Literal["collapse", "pyrrhic", "mixed"]


class PlayPyrrhicCriticDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_id: Literal["pyrrhic", "mixed"]


class PlayBeatRuntimeHintCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: str = Field(min_length=1, max_length=80)
    content: dict[str, object] = Field(default_factory=dict)


class PlayBeatRuntimeShard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1, max_length=80)
    snapshot_version: str = Field(min_length=1, max_length=32)
    context_hash: str = Field(min_length=8, max_length=128)
    required_invariants: dict[str, object] = Field(default_factory=dict)
    focus_npc_ids: list[str] = Field(default_factory=list, max_length=3)
    conflict_npc_ids: list[str] = Field(default_factory=list, max_length=2)
    pressure_axis_id: str | None = None
    required_truth_ids: list[str] = Field(default_factory=list, max_length=4)
    required_event_ids: list[str] = Field(default_factory=list, max_length=4)
    route_pivot_tag: AffordanceTag | None = None
    affordance_tags: list[AffordanceTag] = Field(default_factory=list, max_length=6)
    blocked_affordances: list[AffordanceTag] = Field(default_factory=list, max_length=4)
    progress_required: int = Field(ge=1, le=3)
    interpret_hint_cards: list[PlayBeatRuntimeHintCard] = Field(default_factory=list, max_length=8)
    render_hint_cards: list[PlayBeatRuntimeHintCard] = Field(default_factory=list, max_length=8)
    closeout_hint_cards: list[PlayBeatRuntimeHintCard] = Field(default_factory=list, max_length=8)
    fallback_reason: str | None = Field(default=None, max_length=120)


class PlayPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: str = Field(min_length=1)
    language: ContentLanguage = "en"
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
    beat_runtime_shards: list[PlayBeatRuntimeShard] = Field(default_factory=list, max_length=6)
    route_unlock_rules: list = Field(default_factory=list)
    ending_rules: list[EndingRule] = Field(min_length=1, max_length=6)
    affordance_effect_profiles: list[AffordanceEffectProfile] = Field(min_length=2, max_length=12)
    available_affordance_tags: list[AffordanceTag] = Field(min_length=2, max_length=12)
    max_turns: int = Field(ge=1)
    target_duration_minutes: int | None = Field(default=None, ge=10, le=25)
    branch_budget: StoryBranchBudget | None = None
    minimum_resolution_turn: int = Field(default=3, ge=1, le=10)
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
    interpret_source: Literal["llm", "llm_repair", "llm_salvage", "heuristic"]
    render_source: Literal["llm", "llm_repair", "fallback"]
    render_primary_path_mode: Literal["direct_narration", "direct_repair", "plan_repair", "fallback"] = "fallback"
    execution_frame: ExecutionFrame = "procedural"
    interpret_attempts: int = Field(ge=0)
    ending_judge_source: Literal["llm", "llm_salvage", "failed", "skipped"]
    pyrrhic_critic_source: Literal["llm", "llm_salvage", "failed", "skipped"]
    ending_judge_attempts: int = Field(ge=0)
    pyrrhic_critic_attempts: int = Field(ge=0)
    ending_judge_stage1_success: bool = False
    ending_judge_stage2_rescue: bool = False
    pyrrhic_critic_stage1_success: bool = False
    pyrrhic_critic_stage2_rescue: bool = False
    ending_judge_proposed_id: Literal["collapse", "pyrrhic", "mixed"] | None = None
    pyrrhic_critic_proposed_id: Literal["pyrrhic", "mixed"] | None = None
    ending_judge_failure_reason: str | None = Field(default=None, max_length=120)
    pyrrhic_critic_failure_reason: str | None = Field(default=None, max_length=120)
    ending_judge_response_id: str | None = None
    pyrrhic_critic_response_id: str | None = None
    ending_judge_usage: dict[str, int | str] = Field(default_factory=dict)
    pyrrhic_critic_usage: dict[str, int | str] = Field(default_factory=dict)
    render_attempts: int = Field(ge=0)
    render_plan_stage1_success: bool = False
    render_plan_stage2_rescue: bool = False
    render_narration_stage1_success: bool = False
    render_narration_stage2_rescue: bool = False
    interpret_failure_reason: str | None = Field(default=None, max_length=120)
    render_failure_reason: str | None = Field(default=None, max_length=120)
    render_primary_failure_reason: str | None = Field(default=None, max_length=120)
    render_primary_fallback_source: str | None = Field(default=None, max_length=80)
    render_primary_raw_excerpt: str | None = Field(default=None, max_length=280)
    render_quality_reason_before_repair: str | None = Field(default=None, max_length=120)
    render_repair_failure_reason: str | None = Field(default=None, max_length=120)
    render_repair_raw_excerpt: str | None = Field(default=None, max_length=280)
    interpret_response_id: str | None = None
    render_response_id: str | None = None
    interpret_capability: str | None = Field(default=None, max_length=80)
    ending_judge_capability: str | None = Field(default=None, max_length=80)
    pyrrhic_critic_capability: str | None = Field(default=None, max_length=80)
    render_capability: str | None = Field(default=None, max_length=80)
    interpret_provider: str | None = Field(default=None, max_length=80)
    ending_judge_provider: str | None = Field(default=None, max_length=80)
    pyrrhic_critic_provider: str | None = Field(default=None, max_length=80)
    render_provider: str | None = Field(default=None, max_length=80)
    interpret_model: str | None = Field(default=None, max_length=120)
    ending_judge_model: str | None = Field(default=None, max_length=120)
    pyrrhic_critic_model: str | None = Field(default=None, max_length=120)
    render_model: str | None = Field(default=None, max_length=120)
    interpret_transport_style: str | None = Field(default=None, max_length=40)
    ending_judge_transport_style: str | None = Field(default=None, max_length=40)
    pyrrhic_critic_transport_style: str | None = Field(default=None, max_length=40)
    render_transport_style: str | None = Field(default=None, max_length=40)
    interpret_skill_id: str | None = Field(default=None, max_length=120)
    interpret_skill_version: str | None = Field(default=None, max_length=32)
    interpret_contract_mode: str | None = Field(default=None, max_length=80)
    interpret_context_card_ids: list[str] = Field(default_factory=list, max_length=16)
    interpret_context_packet_characters: int | None = Field(default=None, ge=0)
    interpret_repair_mode: str | None = Field(default=None, max_length=80)
    ending_judge_skill_id: str | None = Field(default=None, max_length=120)
    ending_judge_skill_version: str | None = Field(default=None, max_length=32)
    ending_judge_contract_mode: str | None = Field(default=None, max_length=80)
    ending_judge_context_card_ids: list[str] = Field(default_factory=list, max_length=16)
    ending_judge_context_packet_characters: int | None = Field(default=None, ge=0)
    ending_judge_repair_mode: str | None = Field(default=None, max_length=80)
    pyrrhic_critic_skill_id: str | None = Field(default=None, max_length=120)
    pyrrhic_critic_skill_version: str | None = Field(default=None, max_length=32)
    pyrrhic_critic_contract_mode: str | None = Field(default=None, max_length=80)
    pyrrhic_critic_context_card_ids: list[str] = Field(default_factory=list, max_length=16)
    pyrrhic_critic_context_packet_characters: int | None = Field(default=None, ge=0)
    pyrrhic_critic_repair_mode: str | None = Field(default=None, max_length=80)
    render_skill_id: str | None = Field(default=None, max_length=120)
    render_skill_version: str | None = Field(default=None, max_length=32)
    render_contract_mode: str | None = Field(default=None, max_length=80)
    render_context_card_ids: list[str] = Field(default_factory=list, max_length=16)
    render_context_packet_characters: int | None = Field(default=None, ge=0)
    render_repair_mode: str | None = Field(default=None, max_length=80)
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
    involved_npc_template_versions: dict[str, str] = Field(default_factory=dict)
    beat_index_before: int = Field(ge=1)
    beat_title_before: str = Field(min_length=1, max_length=120)
    beat_index_after: int = Field(ge=1)
    beat_title_after: str = Field(min_length=1, max_length=120)
    status_after: Literal["active", "completed", "expired"]
    resolution: PlayResolutionEffect
