from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rpg_backend.content_language import ContentLanguage

AxisKind = Literal["pressure", "resource", "relationship", "exposure", "time"]
StoryFunction = Literal["advance", "reveal", "stabilize", "detour", "pay_cost"]
BeatMilestoneKind = Literal["reveal", "exposure", "fracture", "concession", "containment", "commitment"]
ToneFocus = Literal["character", "relationship", "institution", "public_ethics", "procedural"]
ProseStyle = Literal["restrained", "lyrical", "urgent"]
StoryBranchBudget = Literal["low", "medium", "high"]
PortraitExpression = Literal["positive", "neutral", "negative"]
CharacterGenderLock = Literal["female", "male", "nonbinary", "unspecified"]
AxisTemplateId = Literal[
    "external_pressure",
    "public_panic",
    "political_leverage",
    "resource_strain",
    "system_integrity",
    "ally_trust",
    "exposure_risk",
    "time_window",
]
AffordanceTag = Literal[
    "reveal_truth",
    "build_trust",
    "contain_chaos",
    "shift_public_narrative",
    "protect_civilians",
    "secure_resources",
    "unlock_ally",
    "pay_cost",
]
StoryInstanceMaterializationSource = Literal["generated", "fallback", "copilot", "default"]


class FocusedBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: ContentLanguage = "en"
    story_kernel: str = Field(min_length=1, max_length=220)
    setting_signal: str = Field(min_length=1, max_length=220)
    core_conflict: str = Field(min_length=1, max_length=220)
    tone_signal: str = Field(min_length=1, max_length=120)
    hard_constraints: list[str] = Field(default_factory=list, max_length=4)
    forbidden_tones: list[str] = Field(default_factory=list, max_length=4)


class StoryGenerationControls(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_duration_minutes: int | None = Field(default=None, ge=10, le=25)
    tone_direction: str | None = Field(default=None, max_length=240)
    tone_focus: ToneFocus | None = None
    prose_style: ProseStyle | None = None


class StoryFlowPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_duration_minutes: int = Field(ge=10, le=25)
    target_turn_count: int = Field(ge=4, le=10)
    target_beat_count: int = Field(ge=2, le=5)
    progress_required_by_beat: list[int] = Field(min_length=2, max_length=5)
    branch_budget: StoryBranchBudget
    route_unlock_budget: int = Field(ge=1, le=8)
    detour_budget_total: int = Field(ge=0, le=8)
    recommended_cast_count: int = Field(ge=3, le=5)
    minimum_resolution_turn: int = Field(ge=1, le=10)


class TonePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone_direction: str | None = Field(default=None, max_length=240)
    tone_focus: ToneFocus | None = None
    prose_style: ProseStyle | None = None
    resolved_tone_signal: str = Field(min_length=1, max_length=120)
    style_guard_guidance: str = Field(min_length=1, max_length=220)
    character_emphasis_guidance: str = Field(min_length=1, max_length=220)
    world_texture_guidance: str = Field(min_length=1, max_length=220)
    beat_language_guidance: str = Field(min_length=1, max_length=220)


class PortraitVariants(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positive: str | None = Field(default=None, min_length=1, max_length=260)
    neutral: str | None = Field(default=None, min_length=1, max_length=260)
    negative: str | None = Field(default=None, min_length=1, max_length=260)


class CastStoryInstanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_experience_summary: str = Field(min_length=1, max_length=220)
    instance_personality_delta: str = Field(min_length=1, max_length=180)
    materialization_source: StoryInstanceMaterializationSource
    gender_lock: CharacterGenderLock | None = None


class CastMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    agenda: str = Field(min_length=1, max_length=220)
    red_line: str = Field(min_length=1, max_length=220)
    pressure_signature: str = Field(min_length=1, max_length=220)
    roster_character_id: str | None = None
    roster_public_summary: str | None = Field(default=None, max_length=220)
    portrait_url: str | None = Field(default=None, max_length=260)
    portrait_variants: PortraitVariants | None = None
    template_version: str | None = Field(default=None, max_length=64)
    story_instance: CastStoryInstanceSnapshot | None = None


class TruthItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    truth_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=220)
    importance: Literal["core", "optional"] = "core"


class EndingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=220)


class StoryBible(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=320)
    tone: str = Field(min_length=1, max_length=120)
    stakes: str = Field(min_length=1, max_length=240)
    style_guard: str = Field(min_length=1, max_length=220)
    cast: list[CastMember] = Field(min_length=3, max_length=5)
    world_rules: list[str] = Field(min_length=2, max_length=5)
    truth_catalog: list[TruthItem] = Field(min_length=1, max_length=8)
    ending_catalog: list[EndingItem] = Field(min_length=3, max_length=5)


class AxisDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    axis_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: AxisKind
    min_value: int = 0
    max_value: int = Field(default=5, ge=1)
    starting_value: int = 0


class StanceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stance_id: str = Field(min_length=1)
    npc_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    min_value: int = -2
    max_value: int = 3
    starting_value: int = 0


class FlagDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    starting_value: bool = False


class StateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    axes: list[AxisDefinition] = Field(min_length=2, max_length=6)
    stances: list[StanceDefinition] = Field(default_factory=list, max_length=5)
    flags: list[FlagDefinition] = Field(default_factory=list, max_length=8)


class AffordanceWeight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: AffordanceTag
    weight: int = Field(ge=1, le=3)


class BeatSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=220)
    focus_npcs: list[str] = Field(default_factory=list, max_length=3)
    conflict_npcs: list[str] = Field(default_factory=list, max_length=2)
    pressure_axis_id: str | None = None
    milestone_kind: BeatMilestoneKind = "reveal"
    route_pivot_tag: AffordanceTag | None = None
    required_truths: list[str] = Field(default_factory=list, max_length=4)
    required_events: list[str] = Field(default_factory=list, max_length=4)
    detour_budget: int = Field(default=1, ge=0, le=2)
    progress_required: int = Field(default=2, ge=1, le=3)
    return_hooks: list[str] = Field(min_length=1, max_length=3)
    affordances: list[AffordanceWeight] = Field(min_length=2, max_length=6)
    blocked_affordances: list[AffordanceTag] = Field(default_factory=list, max_length=4)


class BeatRuntimeHintCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: str = Field(min_length=1, max_length=80)
    content: dict[str, object] = Field(default_factory=dict)


class AuthorBeatSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=80)
    snapshot_version: str = Field(min_length=1, max_length=32)
    context_hash: str = Field(min_length=8, max_length=128)
    beat_id: str = Field(min_length=1)
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


class AuthorBundleSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=80)
    snapshot_version: str = Field(min_length=1, max_length=32)
    context_hash: str = Field(min_length=8, max_length=128)
    required_invariants: dict[str, object] = Field(default_factory=dict)


class BeatRuntimeShard(BaseModel):
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
    interpret_hint_cards: list[BeatRuntimeHintCard] = Field(default_factory=list, max_length=8)
    render_hint_cards: list[BeatRuntimeHintCard] = Field(default_factory=list, max_length=8)
    closeout_hint_cards: list[BeatRuntimeHintCard] = Field(default_factory=list, max_length=8)
    fallback_reason: str | None = Field(default=None, max_length=120)


class ConditionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_axes: dict[str, int] = Field(default_factory=dict)
    max_axes: dict[str, int] = Field(default_factory=dict)
    min_stances: dict[str, int] = Field(default_factory=dict)
    required_truths: list[str] = Field(default_factory=list)
    required_events: list[str] = Field(default_factory=list)
    required_flags: list[str] = Field(default_factory=list)


class RouteUnlockRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)
    beat_id: str = Field(min_length=1)
    conditions: ConditionBlock = Field(default_factory=ConditionBlock)
    unlock_route_id: str = Field(min_length=1)
    unlock_affordance_tag: AffordanceTag


class EndingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_id: str = Field(min_length=1)
    priority: int = Field(default=100, ge=1)
    conditions: ConditionBlock = Field(default_factory=ConditionBlock)


class AffordanceEffectProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affordance_tag: AffordanceTag
    default_story_function: StoryFunction
    axis_deltas: dict[str, int] = Field(default_factory=dict)
    stance_deltas: dict[str, int] = Field(default_factory=dict)
    can_add_truth: bool = False
    can_add_event: bool = False


class RulePack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_unlock_rules: list[RouteUnlockRule] = Field(default_factory=list, max_length=8)
    ending_rules: list[EndingRule] = Field(min_length=1, max_length=6)
    affordance_effect_profiles: list[AffordanceEffectProfile] = Field(min_length=2, max_length=12)


class RouteAffordancePackDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_unlock_rules: list[RouteUnlockRule] = Field(default_factory=list, max_length=8)
    affordance_effect_profiles: list[AffordanceEffectProfile] = Field(min_length=2, max_length=12)


class EndingRulesDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_rules: list[EndingRule] = Field(min_length=1, max_length=6)


class EndingIntentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_id: str = Field(min_length=1)
    priority: int = Field(default=100, ge=1)
    axis_ids: list[str] = Field(default_factory=list, max_length=2)
    required_truth_ids: list[str] = Field(default_factory=list, max_length=2)
    required_event_ids: list[str] = Field(default_factory=list, max_length=2)
    required_flag_ids: list[str] = Field(default_factory=list, max_length=2)
    fallback: bool = False


class EndingIntentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_intents: list[EndingIntentSpec] = Field(min_length=1, max_length=6)


class EndingAnchorSuggestionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_id: Literal["collapse", "pyrrhic"]
    axis_ids: list[str] = Field(default_factory=list, max_length=2)
    required_truth_ids: list[str] = Field(default_factory=list, max_length=2)
    required_event_ids: list[str] = Field(default_factory=list, max_length=2)
    required_flag_ids: list[str] = Field(default_factory=list, max_length=2)


class EndingAnchorSuggestionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ending_anchor_suggestions: list[EndingAnchorSuggestionSpec] = Field(default_factory=list, max_length=2)


class RouteOpportunityTriggerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["truth", "axis", "stance", "flag", "event"]
    target_id: str = Field(min_length=1)
    min_value: int | None = None


class RouteOpportunityDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    unlock_route_id: str = Field(min_length=1)
    unlock_affordance_tag: AffordanceTag
    triggers: list[RouteOpportunityTriggerDraft] = Field(min_length=1, max_length=2)


class RouteOpportunityPlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunities: list[RouteOpportunityDraft] = Field(default_factory=list, max_length=8)


class DesignBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focused_brief: FocusedBrief
    generation_controls: StoryGenerationControls | None = None
    story_flow_plan: StoryFlowPlan | None = None
    resolved_tone_plan: TonePlan | None = None
    story_bible: StoryBible
    state_schema: StateSchema
    beat_spine: list[BeatSpec] = Field(min_length=1, max_length=6)
    beat_runtime_shards: list[BeatRuntimeShard] = Field(default_factory=list, max_length=6)
    rule_pack: RulePack


class OverviewCastDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    agenda: str = Field(min_length=1, max_length=220)
    red_line: str = Field(min_length=1, max_length=220)
    pressure_signature: str = Field(min_length=1, max_length=220)
    roster_character_id: str | None = None
    roster_public_summary: str | None = Field(default=None, max_length=220)
    portrait_url: str | None = Field(default=None, max_length=260)
    portrait_variants: PortraitVariants | None = None
    template_version: str | None = Field(default=None, max_length=64)
    story_instance: CastStoryInstanceSnapshot | None = None


class CastMemberSemanticsDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    agenda_detail: str = Field(min_length=1, max_length=180)
    red_line_detail: str = Field(min_length=1, max_length=180)
    pressure_detail: str = Field(min_length=1, max_length=180)


class OverviewTruthDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=220)
    importance: Literal["core", "optional"] = "core"


class OverviewAxisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: AxisTemplateId
    story_label: str = Field(min_length=1, max_length=80)
    starting_value: int = Field(default=0, ge=0, le=3)


class OverviewFlagDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    starting_value: bool = False


class StoryFrameScaffoldDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_seed: str = Field(min_length=1, max_length=80)
    setting_frame: str = Field(min_length=1, max_length=180)
    protagonist_mandate: str = Field(min_length=1, max_length=220)
    opposition_force: str = Field(min_length=1, max_length=220)
    stakes_core: str = Field(min_length=1, max_length=220)
    tone: str = Field(min_length=1, max_length=120)
    world_rules: list[str] = Field(min_length=2, max_length=5)
    truths: list[OverviewTruthDraft] = Field(min_length=2, max_length=6)
    state_axis_choices: list[OverviewAxisDraft] = Field(min_length=2, max_length=5)
    flags: list[OverviewFlagDraft] = Field(default_factory=list, max_length=4)


class BeatDraftSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=220)
    focus_names: list[str] = Field(default_factory=list, max_length=3)
    conflict_pair: list[str] = Field(default_factory=list, max_length=2)
    pressure_axis_id: AxisTemplateId | None = None
    milestone_kind: BeatMilestoneKind = "reveal"
    route_pivot_tag: AffordanceTag | None = None
    required_truth_texts: list[str] = Field(default_factory=list, max_length=3)
    detour_budget: int = Field(default=1, ge=0, le=2)
    progress_required: int = Field(default=2, ge=1, le=3)
    return_hooks: list[str] = Field(min_length=1, max_length=3)
    affordance_tags: list[AffordanceTag] = Field(min_length=2, max_length=6)
    blocked_affordances: list[AffordanceTag] = Field(default_factory=list, max_length=4)


class BeatSkeletonSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_seed: str = Field(min_length=1, max_length=80)
    goal_seed: str = Field(min_length=1, max_length=180)
    focus_names: list[str] = Field(default_factory=list, max_length=3)
    conflict_pair: list[str] = Field(default_factory=list, max_length=2)
    pressure_axis_id: AxisTemplateId | None = None
    milestone_kind: BeatMilestoneKind = "reveal"
    route_pivot_tag: AffordanceTag | None = None
    required_truth_texts: list[str] = Field(default_factory=list, max_length=3)
    detour_budget: int = Field(default=1, ge=0, le=2)
    progress_required: int = Field(default=2, ge=1, le=3)
    affordance_tags: list[AffordanceTag] = Field(min_length=2, max_length=6)
    blocked_affordances: list[AffordanceTag] = Field(default_factory=list, max_length=4)


class BeatPlanSkeletonDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beats: list[BeatSkeletonSpec] = Field(min_length=2, max_length=5)


class StoryFrameDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=320)
    tone: str = Field(min_length=1, max_length=120)
    stakes: str = Field(min_length=1, max_length=240)
    style_guard: str = Field(min_length=1, max_length=220)
    world_rules: list[str] = Field(min_length=2, max_length=5)
    truths: list[OverviewTruthDraft] = Field(min_length=2, max_length=6)
    state_axis_choices: list[OverviewAxisDraft] = Field(min_length=2, max_length=5)
    flags: list[OverviewFlagDraft] = Field(default_factory=list, max_length=4)


class CastOverviewSlotDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_label: str = Field(min_length=1, max_length=80)
    public_role: str = Field(min_length=1, max_length=120)
    relationship_to_protagonist: str = Field(min_length=1, max_length=180)
    agenda_anchor: str = Field(min_length=1, max_length=220)
    red_line_anchor: str = Field(min_length=1, max_length=220)
    pressure_vector: str = Field(min_length=1, max_length=220)
    archetype_id: str | None = None
    relationship_dynamic_id: str | None = None
    counter_trait: str | None = None
    pressure_tell: str | None = None


class CastOverviewDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cast_slots: list[CastOverviewSlotDraft] = Field(min_length=3, max_length=5)
    relationship_summary: list[str] = Field(min_length=2, max_length=6)


class CastDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cast: list[OverviewCastDraft] = Field(min_length=3, max_length=5)


class BeatPlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beats: list[BeatDraftSpec] = Field(min_length=2, max_length=5)


class AuthorBundleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_brief: str = Field(min_length=1, max_length=4000)
    language: ContentLanguage = "en"
    target_duration_minutes: int | None = Field(default=None, ge=10, le=25)
    tone_direction: str | None = Field(default=None, max_length=240)
    tone_focus: ToneFocus | None = None
    prose_style: ProseStyle | None = None


class AuthorPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_seed: str = Field(min_length=1, max_length=4000)
    language: ContentLanguage = "en"
    random_seed: int | None = None
    target_duration_minutes: int | None = Field(default=None, ge=10, le=25)
    tone_direction: str | None = Field(default=None, max_length=240)
    tone_focus: ToneFocus | None = None
    prose_style: ProseStyle | None = None


class AuthorStorySparkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: ContentLanguage = "en"


class AuthorStorySparkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_seed: str = Field(min_length=1, max_length=4000)
    language: ContentLanguage = "en"


class AuthorPreviewFlashcard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: str = Field(min_length=1)
    kind: Literal["stable", "draft"]
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=220)


class AuthorLoadingCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: Literal[
        "theme",
        "tone",
        "structure",
        "story_premise",
        "story_stakes",
        "cast_count",
        "cast_anchor",
        "beat_count",
        "working_title",
        "opening_beat",
        "final_beat",
        "generation_status",
        "token_budget",
    ]
    emphasis: Literal["stable", "draft", "live"]
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=220)


class AuthorPreviewTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_theme: str = Field(min_length=1)
    modifiers: list[str] = Field(default_factory=list, max_length=8)
    router_reason: str = Field(min_length=1)


class AuthorPreviewStrategies(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_frame_strategy: str = Field(min_length=1)
    cast_strategy: str = Field(min_length=1)
    beat_plan_strategy: str = Field(min_length=1)


class AuthorPreviewStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cast_topology: str = Field(min_length=1)
    expected_npc_count: int = Field(ge=1)
    expected_beat_count: int = Field(ge=1)
    target_duration_minutes: int | None = Field(default=None, ge=10, le=25)
    expected_turn_count: int | None = Field(default=None, ge=4, le=10)
    branch_budget: StoryBranchBudget | None = None


class AuthorPreviewStory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=320)
    tone: str = Field(min_length=1, max_length=120)
    stakes: str = Field(min_length=1, max_length=240)


class AuthorPreviewCastSlotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_label: str = Field(min_length=1, max_length=80)
    public_role: str = Field(min_length=1, max_length=120)
    npc_id: str | None = None
    name: str | None = Field(default=None, max_length=80)
    roster_character_id: str | None = None
    roster_public_summary: str | None = Field(default=None, max_length=220)
    portrait_url: str | None = Field(default=None, max_length=260)
    portrait_variants: PortraitVariants | None = None
    template_version: str | None = Field(default=None, max_length=64)


class AuthorPreviewBeatSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=220)
    milestone_kind: str = Field(min_length=1, max_length=32)


class AuthorPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str = Field(min_length=1)
    prompt_seed: str = Field(min_length=1, max_length=4000)
    language: ContentLanguage = "en"
    generation_controls: StoryGenerationControls | None = None
    story_flow_plan: StoryFlowPlan | None = None
    resolved_tone_plan: TonePlan | None = None
    focused_brief: FocusedBrief
    theme: AuthorPreviewTheme
    strategies: AuthorPreviewStrategies
    structure: AuthorPreviewStructure
    story: AuthorPreviewStory
    cast_slots: list[AuthorPreviewCastSlotSummary] = Field(default_factory=list, max_length=5)
    beats: list[AuthorPreviewBeatSummary] = Field(default_factory=list, max_length=5)
    flashcards: list[AuthorPreviewFlashcard] = Field(default_factory=list, max_length=16)
    stage: str = Field(min_length=1, max_length=64)


class AuthorJobProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str = Field(min_length=1, max_length=64)
    stage_index: int = Field(ge=0)
    stage_total: int = Field(ge=1)


class AuthorCacheMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_cache_enabled: bool = False
    cache_path_used: bool = False
    total_call_count: int = Field(ge=0)
    previous_response_call_count: int = Field(ge=0)
    total_input_characters: int = Field(ge=0)
    estimated_input_tokens_from_chars: int = Field(ge=0)
    provider_usage: dict[str, int] = Field(default_factory=dict)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cache_hit_tokens: int | None = Field(default=None, ge=0)
    cache_write_tokens: int | None = Field(default=None, ge=0)
    cache_creation_input_tokens: int | None = Field(default=None, ge=0)
    cache_type: str | None = Field(default=None, max_length=32)
    billing_type: str | None = Field(default=None, max_length=32)
    cache_metrics_source: str = Field(min_length=1, max_length=80)


class AuthorJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_seed: str = Field(min_length=1, max_length=4000)
    language: ContentLanguage = "en"
    random_seed: int | None = None
    preview_id: str | None = None
    target_duration_minutes: int | None = Field(default=None, ge=10, le=25)
    tone_direction: str | None = Field(default=None, max_length=240)
    tone_focus: ToneFocus | None = None
    prose_style: ProseStyle | None = None


class AuthorJobStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    status: Literal["queued", "running", "completed", "failed"]
    prompt_seed: str = Field(min_length=1, max_length=4000)
    preview: AuthorPreviewResponse
    progress: AuthorJobProgress
    progress_snapshot: AuthorJobProgressSnapshot | None = None
    cache_metrics: AuthorCacheMetrics | None = None
    error: dict[str, str] | None = None


class AuthorStorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: ContentLanguage = "en"
    title: str = Field(min_length=1, max_length=120)
    one_liner: str = Field(min_length=1, max_length=220)
    premise: str = Field(min_length=1, max_length=320)
    tone: str = Field(min_length=1, max_length=120)
    theme: str = Field(min_length=1, max_length=80)
    npc_count: int = Field(ge=1)
    beat_count: int = Field(ge=1)
    target_duration_minutes: int | None = Field(default=None, ge=10, le=25)


class AuthorEditorNpcRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)


class AuthorEditorStoryFrameView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=320)
    tone: str = Field(min_length=1, max_length=120)
    stakes: str = Field(min_length=1, max_length=240)
    style_guard: str = Field(min_length=1, max_length=220)
    world_rules: list[str] = Field(min_length=2, max_length=5)
    truths: list[TruthItem] = Field(default_factory=list, max_length=8)
    state_axes: list[AxisDefinition] = Field(default_factory=list, max_length=6)
    flags: list[FlagDefinition] = Field(default_factory=list, max_length=8)


class AuthorEditorCastEntry(BaseModel):
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
    template_version: str | None = Field(default=None, max_length=64)


class AuthorEditorBeatView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=220)
    milestone_kind: BeatMilestoneKind
    pressure_axis_id: str | None = None
    route_pivot_tag: AffordanceTag | None = None
    progress_required: int = Field(ge=1, le=3)
    focus_npcs: list[AuthorEditorNpcRef] = Field(default_factory=list, max_length=3)
    conflict_npcs: list[AuthorEditorNpcRef] = Field(default_factory=list, max_length=2)
    affordance_tags: list[AffordanceTag] = Field(default_factory=list, max_length=6)
    blocked_affordances: list[AffordanceTag] = Field(default_factory=list, max_length=4)


class AuthorEditorRulePackView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_unlock_rules: list[RouteUnlockRule] = Field(default_factory=list, max_length=8)
    ending_rules: list[EndingRule] = Field(default_factory=list, max_length=6)
    affordance_effect_profiles: list[AffordanceEffectProfile] = Field(default_factory=list, max_length=12)


class AuthorEditorPlayProfileView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protagonist: CastMember
    runtime_profile: str = Field(min_length=1, max_length=80)
    runtime_profile_label: str = Field(min_length=1, max_length=120)
    closeout_profile: str = Field(min_length=1, max_length=80)
    closeout_profile_label: str = Field(min_length=1, max_length=120)
    max_turns: int = Field(ge=1)
    target_duration_minutes: int | None = Field(default=None, ge=10, le=25)
    branch_budget: StoryBranchBudget | None = None


class AuthorCopilotSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=240)
    rationale: str = Field(min_length=1, max_length=240)


class AuthorCopilotWorkspaceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["primary"] = "primary"
    headline: str = Field(min_length=1, max_length=160)
    supporting_text: str = Field(min_length=1, max_length=320)
    publish_readiness_text: str = Field(min_length=1, max_length=240)
    active_session_id: str | None = None
    undo_available: bool = False
    undo_proposal_id: str | None = None
    undo_request_summary: str | None = Field(default=None, max_length=400)
    suggested_instructions: list[AuthorCopilotSuggestion] = Field(default_factory=list, min_length=1, max_length=4)


class AuthorCopilotLockedBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: ContentLanguage = "en"
    core_story_kernel: str = Field(min_length=1, max_length=220)
    core_conflict: str = Field(min_length=1, max_length=220)
    runtime_profile: str = Field(min_length=1, max_length=80)
    closeout_profile: str = Field(min_length=1, max_length=80)
    cast_topology: str = Field(min_length=1, max_length=40)
    beat_count: int = Field(ge=1, le=6)
    max_turns: int = Field(ge=1, le=10)


class AuthorCopilotMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    created_at: datetime


class AuthorCopilotRewriteBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=400)
    latest_instruction: str = Field(min_length=1, max_length=2000)
    user_goals: list[str] = Field(default_factory=list, max_length=8)
    preserved_invariants: list[str] = Field(default_factory=list, max_length=8)
    open_questions: list[str] = Field(default_factory=list, max_length=6)


class AuthorCopilotSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hidden: bool = False


class AuthorCopilotSessionMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4000)


class AuthorCopilotSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    status: Literal["active", "proposal_ready", "applied", "stale", "closed"]
    hidden: bool = False
    base_revision: str = Field(min_length=1, max_length=64)
    locked_boundaries: AuthorCopilotLockedBoundaries
    rewrite_brief: AuthorCopilotRewriteBrief
    messages: list[AuthorCopilotMessage] = Field(default_factory=list, max_length=24)
    last_proposal_id: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class AuthorCopilotWorkspaceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focused_brief: FocusedBrief
    story_frame_draft: StoryFrameDraft
    cast_overview_draft: CastOverviewDraft
    cast_member_drafts: list[OverviewCastDraft] = Field(default_factory=list, min_length=1, max_length=5)
    cast_draft: CastDraft
    beat_plan_draft: BeatPlanDraft
    route_opportunity_plan_draft: RouteOpportunityPlanDraft | None = None
    route_affordance_pack_draft: RouteAffordancePackDraft | None = None
    ending_intent_draft: EndingIntentDraft | None = None
    ending_rules_draft: EndingRulesDraft | None = None
    story_frame_strategy: str | None = Field(default=None, max_length=80)
    primary_theme: str = Field(min_length=1)
    theme_modifiers: list[str] = Field(default_factory=list, max_length=6)
    cast_topology: str = Field(min_length=1, max_length=40)
    runtime_profile: str = Field(min_length=1, max_length=80)
    closeout_profile: str = Field(min_length=1, max_length=80)
    max_turns: int = Field(ge=1, le=10)


class AuthorEditorStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    status: Literal["completed"]
    language: ContentLanguage = "en"
    revision: str = Field(min_length=1, max_length=64)
    publishable: bool = True
    focused_brief: FocusedBrief
    summary: AuthorStorySummary
    story_frame_view: AuthorEditorStoryFrameView
    cast_view: list[AuthorEditorCastEntry] = Field(default_factory=list, min_length=1, max_length=5)
    beat_view: list[AuthorEditorBeatView] = Field(default_factory=list, min_length=1, max_length=5)
    rule_pack_view: AuthorEditorRulePackView
    play_profile_view: AuthorEditorPlayProfileView
    copilot_view: AuthorCopilotWorkspaceView


class AuthorCastPortraitPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_ids: list[str] = Field(default_factory=list, max_length=5)
    variants: list[Literal["negative", "neutral", "positive"]] = Field(
        default_factory=lambda: ["negative", "neutral", "positive"],
        min_length=1,
        max_length=3,
    )
    candidates_per_variant: int = Field(default=1, ge=1, le=4)
    prompt_version: str = Field(default="v1_editorial_dossier", min_length=1, max_length=64)


class AuthorCastPortraitArtDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_label: str = Field(min_length=1, max_length=160)
    generation_aspect_ratio: str = Field(min_length=1, max_length=16)
    generation_resolution: str = Field(min_length=1, max_length=16)
    display_ratios: list[str] = Field(default_factory=list, min_length=1, max_length=4)
    crop_guidance: str = Field(min_length=1, max_length=320)
    style_lock: str = Field(min_length=1, max_length=400)
    negative_guidance: str = Field(min_length=1, max_length=500)
    ui_grade_notes: str = Field(min_length=1, max_length=220)


class AuthorCastPortraitSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(min_length=1, max_length=160)
    source_kind: Literal["roster", "author_cast"]
    source_ref: str = Field(min_length=1, max_length=240)
    npc_id: str = Field(min_length=1, max_length=120)
    roster_character_id: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    secondary_name: str | None = Field(default=None, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    public_summary: str | None = Field(default=None, max_length=220)
    agenda: str = Field(min_length=1, max_length=220)
    red_line: str = Field(min_length=1, max_length=220)
    pressure_signature: str = Field(min_length=1, max_length=220)
    story_title: str = Field(min_length=1, max_length=120)
    story_premise: str = Field(min_length=1, max_length=320)
    story_tone: str = Field(min_length=1, max_length=120)
    story_style_guard: str = Field(min_length=1, max_length=220)
    world_rules: list[str] = Field(default_factory=list, max_length=3)
    visual_tags: list[str] = Field(default_factory=list, max_length=6)


class AuthorCastPortraitTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=200)
    character_id: str = Field(min_length=1, max_length=160)
    npc_id: str = Field(min_length=1, max_length=120)
    variant_key: Literal["negative", "neutral", "positive"]
    candidate_index: int = Field(ge=1, le=8)
    prompt_text: str = Field(min_length=1, max_length=4000)
    prompt_hash: str = Field(min_length=8, max_length=128)
    relative_output_path: str = Field(min_length=1, max_length=320)


class AuthorCastPortraitPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    revision: str = Field(min_length=1, max_length=64)
    language: ContentLanguage = "en"
    batch_id: str = Field(min_length=1, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=64)
    image_model: str = Field(min_length=1, max_length=120)
    image_api_base_url: str = Field(min_length=1, max_length=240)
    output_dir: str = Field(min_length=1, max_length=320)
    art_direction: AuthorCastPortraitArtDirection
    subjects: list[AuthorCastPortraitSubject] = Field(default_factory=list, min_length=1, max_length=5)
    jobs: list[AuthorCastPortraitTask] = Field(default_factory=list, min_length=1)


class AuthorCopilotProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=2000)
    retry_from_proposal_id: str | None = None


class AuthorCopilotStateAxisRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: AxisTemplateId
    story_label: str | None = Field(default=None, min_length=1, max_length=80)
    starting_value: int | None = Field(default=None, ge=0, le=3)


class AuthorCopilotStoryFrameRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=120)
    premise: str | None = Field(default=None, max_length=320)
    tone: str | None = Field(default=None, max_length=120)
    stakes: str | None = Field(default=None, max_length=240)
    style_guard: str | None = Field(default=None, max_length=220)
    world_rules: list[str] | None = Field(default=None, min_length=2, max_length=5)
    truths: list[OverviewTruthDraft] | None = Field(default=None, min_length=2, max_length=6)
    state_axis_choices: list[AuthorCopilotStateAxisRewrite] | None = Field(default=None, min_length=1, max_length=5)
    flags: list[OverviewFlagDraft] | None = Field(default=None, max_length=4)


class AuthorCopilotCastRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=80)
    role: str | None = Field(default=None, max_length=120)
    agenda: str | None = Field(default=None, max_length=220)
    red_line: str | None = Field(default=None, max_length=220)
    pressure_signature: str | None = Field(default=None, max_length=220)
    roster_character_id: str | None = Field(default=None, max_length=120)


class AuthorCopilotBeatRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    title: str | None = Field(default=None, max_length=120)
    goal: str | None = Field(default=None, max_length=220)
    focus_names: list[str] | None = Field(default=None, max_length=3)
    conflict_pair: list[str] | None = Field(default=None, max_length=2)
    milestone_kind: str | None = Field(default=None, max_length=40)
    pressure_axis_id: str | None = Field(default=None, max_length=80)
    route_pivot_tag: str | None = Field(default=None, max_length=80)
    required_truth_texts: list[str] | None = Field(default=None, max_length=3)
    detour_budget: int | None = Field(default=None, ge=0, le=2)
    progress_required: int | None = Field(default=None, ge=1, le=6)
    return_hooks: list[str] | None = Field(default=None, min_length=1, max_length=3)
    affordance_tags: list[AffordanceTag] | None = Field(default=None, min_length=2, max_length=6)
    blocked_affordances: list[AffordanceTag] | None = Field(default=None, max_length=4)


class AuthorCopilotRulePackRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    toward: Literal["mixed", "pyrrhic", "collapse"] | None = None
    intensity: Literal["light", "medium", "strong"] | None = None
    route_unlock_rules: list[RouteUnlockRule] | None = Field(default=None, max_length=8)
    affordance_effect_profiles: list[AffordanceEffectProfile] | None = Field(default=None, min_length=2, max_length=12)
    ending_rules: list[EndingRule] | None = Field(default=None, min_length=1, max_length=6)


class AuthorCopilotRewritePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_frame: AuthorCopilotStoryFrameRewrite | None = None
    cast: list[AuthorCopilotCastRewrite] = Field(default_factory=list, max_length=5)
    beats: list[AuthorCopilotBeatRewrite] = Field(default_factory=list, max_length=6)
    rule_pack: AuthorCopilotRulePackRewrite | None = None


class AuthorCopilotOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["update_story_frame", "update_cast_member", "update_beat", "adjust_ending_tilt"]
    target: str = Field(min_length=1, max_length=120)
    changes: dict[str, str | int] = Field(default_factory=dict)
    toward: Literal["mixed", "pyrrhic", "collapse"] | None = None
    intensity: Literal["light", "medium", "strong"] | None = None


class AuthorCopilotProposalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=1)
    proposal_group_id: str = Field(min_length=1)
    session_id: str | None = None
    job_id: str = Field(min_length=1)
    status: Literal["draft", "applied", "superseded"]
    source: Literal["heuristic", "llm"] = "heuristic"
    mode: Literal["bundle_rewrite"] = "bundle_rewrite"
    instruction: str = Field(min_length=1, max_length=2000)
    base_revision: str = Field(min_length=1, max_length=64)
    variant_index: int = Field(ge=1)
    variant_label: str = Field(min_length=1, max_length=120)
    supersedes_proposal_id: str | None = None
    created_at: datetime
    updated_at: datetime
    applied_at: datetime | None = None
    request_summary: str = Field(min_length=1, max_length=400)
    rewrite_scope: str = Field(min_length=1, max_length=80)
    rewrite_brief: str = Field(min_length=1, max_length=800)
    affected_sections: list[Literal["story_frame", "cast", "beats", "rule_pack"]] = Field(default_factory=list, max_length=4)
    stability_guards: list[str] = Field(default_factory=list, max_length=8)
    rewrite_plan: AuthorCopilotRewritePlan
    patch_targets: list[Literal["story_frame", "cast", "beats", "rule_pack"]] = Field(default_factory=list, max_length=4)
    operations: list[AuthorCopilotOperation] = Field(default_factory=list, max_length=12)
    impact_summary: list[str] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)


class AuthorCopilotPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: AuthorCopilotProposalResponse
    editor_state: AuthorEditorStateResponse


class AuthorCopilotApplyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: AuthorCopilotProposalResponse
    editor_state: AuthorEditorStateResponse


class AuthorCopilotUndoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: AuthorCopilotProposalResponse
    editor_state: AuthorEditorStateResponse


class AuthorJobResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    status: Literal["queued", "running", "completed", "failed"]
    summary: AuthorStorySummary | None = None
    publishable: bool = False
    progress_snapshot: AuthorJobProgressSnapshot | None = None
    cache_metrics: AuthorCacheMetrics | None = None


class AuthorLoadingCastPoolEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    roster_character_id: str | None = None
    roster_public_summary: str | None = Field(default=None, max_length=220)
    portrait_url: str | None = Field(default=None, max_length=260)
    portrait_variants: PortraitVariants | None = None
    template_version: str | None = Field(default=None, max_length=64)


class AuthorJobProgressSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str = Field(min_length=1, max_length=64)
    stage_label: str = Field(min_length=1, max_length=120)
    stage_message: str | None = Field(default=None, max_length=240)
    stage_index: int = Field(ge=0)
    stage_total: int = Field(ge=1)
    completion_ratio: float = Field(ge=0, le=1)
    primary_theme: str = Field(min_length=1)
    cast_topology: str = Field(min_length=1)
    expected_npc_count: int = Field(ge=1)
    expected_beat_count: int = Field(ge=1)
    preview_title: str = Field(min_length=1, max_length=120)
    preview_premise: str = Field(min_length=1, max_length=320)
    flashcards: list[AuthorPreviewFlashcard] = Field(default_factory=list, max_length=16)
    loading_cards: list[AuthorLoadingCard] = Field(default_factory=list, max_length=16)
    cast_pool: list[AuthorLoadingCastPoolEntry] = Field(default_factory=list, max_length=5)
    running_node: str | None = Field(default=None, max_length=64)
    running_substage: str | None = Field(default=None, max_length=64)
    running_slot_index: int | None = Field(default=None, ge=1)
    running_slot_total: int | None = Field(default=None, ge=1)
    running_slot_label: str | None = Field(default=None, max_length=120)
    running_capability: str | None = Field(default=None, max_length=120)
    running_elapsed_ms: int | None = Field(default=None, ge=0)


class AuthorTokenCostEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str | None = Field(default=None, max_length=120)
    currency: Literal["RMB"] = "RMB"
    input_price_per_million_tokens_rmb: float = Field(ge=0)
    output_price_per_million_tokens_rmb: float = Field(ge=0)
    session_cache_hit_multiplier: float = Field(ge=0)
    session_cache_creation_multiplier: float = Field(ge=0)
    uncached_input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    cache_creation_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_input_cost_rmb: float = Field(ge=0)
    estimated_output_cost_rmb: float = Field(ge=0)
    estimated_total_cost_rmb: float = Field(ge=0)
    notes: str | None = Field(default=None, max_length=240)


CastStoryInstanceSnapshot.model_rebuild()
CastMember.model_rebuild()
OverviewCastDraft.model_rebuild()
