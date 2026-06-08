from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --------------------------------------------------------------------------
# Cast / story / advisor primitives (unchanged from v1)
# --------------------------------------------------------------------------


class NPCLeverageOverNPC(BaseModel):
    """A leverage card one NPC holds over another NPC.

    Enables N×N political dynamics: NPC A may know something damaging
    about NPC B, which lets the LLM write scenes where A threatens B,
    and lets the player deliberately leak knowledge between NPCs to
    trigger inter-NPC conflict ("挑拨").
    """

    model_config = ConfigDict(extra="forbid")

    target_npc_id: str = Field(min_length=1, max_length=64)
    leverage: str = Field(min_length=1, max_length=200)


class CastMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=40)
    role: str = Field(min_length=1, max_length=80)
    relation_to_protagonist: str = Field(min_length=1, max_length=120)
    # Gauntlet-mode adversarial fields. None for story-mode templates.
    hidden_objective: str | None = Field(default=None, max_length=200)
    leverage_over_player: str | None = Field(default=None, max_length=200)
    # Inter-NPC leverage network. Each NPC may hold 0-3 leverages over
    # *other* NPCs, mirroring the existing leverage_over_player field
    # but pointed at the cast instead of the player. Backwards-compatible
    # default to empty list so legacy templates still parse cleanly.
    leverages_over_other_npcs: list[NPCLeverageOverNPC] = Field(
        default_factory=list, max_length=4,
    )


class PlayerGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=120)
    stakes: str = Field(min_length=1, max_length=160)


# --------------------------------------------------------------------------
# Player as cast — the player isn't a faceless "you" anymore. Every
# template ships 3-5 selectable role cards; picking a different card
# replays the same template as a different person, with their own
# hidden_objective + leverage cards + starting assets.
# --------------------------------------------------------------------------


class PlayerLeverageOverNPC(BaseModel):
    """A counter-card the player holds against a specific NPC.

    Surfaces in the turn prompt so the LLM knows the player has
    something to play back when an NPC threatens with leverage_over_player.
    """

    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1, max_length=64)
    leverage: str = Field(min_length=1, max_length=200)


LeverageCardAction = Literal["reveal", "threaten", "trade"]


class PlayedLeverageCard(BaseModel):
    """A player-chosen role leverage card committed on a turn."""

    model_config = ConfigDict(extra="forbid")

    card_id: str = Field(min_length=1, max_length=120)
    npc_id: str = Field(min_length=1, max_length=64)
    leverage: str = Field(min_length=1, max_length=200)
    action: LeverageCardAction = "reveal"


class PlayerRole(BaseModel):
    """One selectable identity the player can wear in a template.

    A template generates 3-5 roles; the player picks one when starting
    a session. Same template + different role = different story.
    """

    model_config = ConfigDict(extra="forbid")

    role_id: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=24)
    public_persona: str = Field(min_length=1, max_length=200)
    hidden_objective: str = Field(min_length=1, max_length=200)
    leverages_over_npcs: list[PlayerLeverageOverNPC] = Field(default_factory=list, max_length=8)
    starting_assets: list[str] = Field(default_factory=list, max_length=4)


class FailureCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)  # short trigger name
    description: str = Field(min_length=1, max_length=200)  # readable rule


class NPCPulse(BaseModel):
    """Per-turn snapshot of how each NPC is shifting. Generated alongside
    each narrator beat. Front-end shows these as small chips between turns
    so the player feels their choices register."""

    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1, max_length=64)
    state: str = Field(min_length=1, max_length=80)
    shift: Literal["warmer", "colder", "steady", "wary", "broken"] = "steady"
    # Optional 12-30 char causal attribution: WHY did this NPC just shift?
    # References a specific player action or narrative event from this turn.
    # Without it, pulse chips are mystery symbols — players can't connect
    # color change to their own choices.
    reason: str | None = Field(default=None, max_length=80)


STORY_OPTION_LABEL_MAX_LENGTH = 128


class StoryOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=STORY_OPTION_LABEL_MAX_LENGTH)
    hint: str = Field(default="", max_length=120)
    # Short "memory handle" for the option — 2-6 characters in the
    # template's locale, distilling the action to something a player
    # could recall later ("亮录音" / "show the recording" rather than
    # the full intent-tag-prefixed label). Frontend uses this in the
    # picked-state reflection and in the player message echo so the
    # user can later say "I chose 'show the recording' that turn"
    # instead of remembering the whole sentence. Optional for backward
    # compat — older parsers + LLM responses without this field still
    # work; UI falls back to label.
    handle: str = Field(default="", max_length=12)


class InventoryDelta(BaseModel):
    """A narrator turn may emit a delta describing what objects/info the
    player gained or lost in this beat. Walked-on-read: the session's
    current inventory = role.starting_assets + sum(added) - sum(removed)
    over all narrator messages in order."""

    model_config = ConfigDict(extra="forbid")

    added: list[str] = Field(default_factory=list, max_length=4)
    removed: list[str] = Field(default_factory=list, max_length=4)
    reason: str = Field(default="", max_length=120)


AgentPlanSource = Literal["deterministic_v1"]
AgentEventType = Literal["agent_plan", "step_judge", "contract_judge"]
JudgeSource = Literal["deterministic_v1"]
JudgeStatus = Literal["pass", "warn", "fail"]
JudgeSeverity = Literal["info", "warn", "error"]
LLMCallStatus = Literal[
    "success",
    "timeout",
    "rate_limited",
    "invalid_response",
    "provider_unavailable",
    "fallback_used",
    "repaired",
    "failed",
]
LLMCallSourceLabel = Literal[
    "live",
    "live_repaired",
    "deterministic_fallback",
    "no_gateway_fallback",
]


class DirectorDecision(BaseModel):
    """Compact pre-turn orchestration decision used for reviewer audit."""

    model_config = ConfigDict(extra="forbid")

    stage_phase: str = Field(min_length=1, max_length=40)
    difficulty: str = Field(min_length=1, max_length=40)
    active_npc_ids: list[str] = Field(default_factory=list, max_length=5)
    focus_window_npc_ids: list[str] = Field(default_factory=list, max_length=5)
    background_npc_ids: list[str] = Field(default_factory=list, max_length=5)
    twist_kind: str | None = Field(default=None, max_length=80)
    expected_pressure: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=240)


class NPCIntent(BaseModel):
    """One active NPC move selected by the deterministic turn scheduler."""

    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=80)
    intent: str = Field(min_length=1, max_length=40)
    intent_brief: str = Field(default="", max_length=200)
    leverage: str | None = Field(default=None, max_length=200)
    source: Literal["agenda"] = "agenda"


class MemorySnapshot(BaseModel):
    """Small audit snapshot derived from persisted history, not full history."""

    model_config = ConfigDict(extra="forbid")

    last_player_action: dict[str, object] = Field(default_factory=dict)
    npc_pulse_trend: dict[str, list[str]] = Field(default_factory=dict)
    unused_leverage: list[dict[str, str]] = Field(default_factory=list, max_length=8)
    current_inventory_count: int = Field(default=0, ge=0)
    current_inventory_preview: list[str] = Field(default_factory=list, max_length=4)
    played_leverage: dict[str, str] = Field(default_factory=dict)


class AgentPlan(BaseModel):
    """Versioned per-turn trace of the workflow decision before narration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent_plan.v1"] = "agent_plan.v1"
    source: AgentPlanSource = "deterministic_v1"
    turn_index: int = Field(ge=0)
    turn_budget: int = Field(ge=1)
    narrator_ord: int = Field(ge=0)
    director: DirectorDecision
    npc_intents: list[NPCIntent] = Field(default_factory=list, max_length=5)
    memory: MemorySnapshot
    twist_directive: dict[str, str] | None = None


class JudgeViolation(BaseModel):
    """Compact deterministic audit finding for a single narrator turn."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    severity: JudgeSeverity
    rationale: str = Field(min_length=1, max_length=240)
    evidence: list[str] = Field(default_factory=list, max_length=8)


class StepJudgeResult(BaseModel):
    """Does the narrator turn honor the pre-turn AgentPlan intent?"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["step_judge.v1"] = "step_judge.v1"
    source: JudgeSource = "deterministic_v1"
    turn_index: int = Field(ge=0)
    narrator_ord: int = Field(ge=0)
    status: JudgeStatus
    violations: list[JudgeViolation] = Field(default_factory=list, max_length=12)
    summary: str = Field(min_length=1, max_length=240)


class ContractJudgeResult(BaseModel):
    """Runtime contract audit for schema, refs, hidden info, and state deltas."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["contract_judge.v1"] = "contract_judge.v1"
    source: JudgeSource = "deterministic_v1"
    turn_index: int = Field(ge=0)
    narrator_ord: int = Field(ge=0)
    status: JudgeStatus
    violations: list[JudgeViolation] = Field(default_factory=list, max_length=12)
    summary: str = Field(min_length=1, max_length=240)


AgentEventPayload = AgentPlan | StepJudgeResult | ContractJudgeResult


class NarrativeAgentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_index: int = Field(ge=0)
    ord: int = Field(ge=0)
    event_type: AgentEventType
    payload: AgentEventPayload
    created_at: str


class LLMCallEvent(BaseModel):
    """Sanitized text-LLM usage/performance evidence.

    Normal player responses do not expose this model. Reviewer/debug
    endpoints can surface it without provider keys, raw prompts, or headers.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: int = Field(ge=0)
    operation: str = Field(min_length=1, max_length=120)
    status: LLMCallStatus
    source_label: LLMCallSourceLabel
    latency_ms: int | None = Field(default=None, ge=0)
    operation_latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    retry_count: int = Field(default=0, ge=0)
    repair_count: int = Field(default=0, ge=0)
    fallback_reason: str | None = Field(default=None, max_length=160)
    response_id: str | None = Field(default=None, max_length=160)
    user_id: str | None = Field(default=None, max_length=80)
    template_id: str | None = Field(default=None, max_length=80)
    session_id: str | None = Field(default=None, max_length=80)
    created_at: str


class LLMCallEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LLMCallEvent]


class StoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ord: int = Field(ge=0)
    role: Literal["narrator", "player"]
    content: str = Field(min_length=1)
    options: list[StoryOption] = Field(default_factory=list)
    chosen_option_index: int | None = None
    # Optional per-turn NPC pulse — emitted by gauntlet-mode turns and
    # rendered as chips between story beats. None for story-mode runs
    # (or for player messages, which never have a pulse).
    npc_pulse: list[NPCPulse] = Field(default_factory=list)
    # Optional per-turn inventory delta. None on most turns (objects
    # don't change hands every beat); fires on real "物件交接" moments.
    inventory_delta: InventoryDelta | None = None
    # Optional inner monologue the player wrote alongside their action.
    # Only present on player messages. NPCs cannot read this — only
    # the LLM uses it to calibrate the inner-state register of
    # subsequent narration. Empty/missing on most turns.
    diary: str | None = Field(default=None, max_length=600)
    # A leverage card the player explicitly played this turn. This keeps
    # role resources visible in replay/debug surfaces instead of becoming
    # indistinguishable from ordinary free text.
    played_leverage: PlayedLeverageCard | None = None


class AdvisorMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ord: int = Field(ge=0)
    role: Literal["player", "advisor"]
    content: str = Field(min_length=1)


# --------------------------------------------------------------------------
# Template (the shareable story shell)
# --------------------------------------------------------------------------


TemplateVisibility = Literal["private", "unlisted", "public"]
Difficulty = Literal["story", "gauntlet"]
EndingTier = Literal["victory", "compromised", "collapsed"]
TensionProfile = Literal[
    "high_drama",
    "cozy_mystery",
    "comedy",
    "fantasy_sci_fi",
    "family_social",
]
StoryBriefSource = Literal["deterministic_v1", "live_hybrid_v1"]
StoryBriefFitStatus = Literal["fit", "needs_revision", "not_fit"]
ConstraintDispositionKind = Literal["preserved", "compressed", "dropped", "softened"]
CastPlanEntityKind = Literal["character", "faction", "object", "setting"]
StoryBriefConsistencyStatus = Literal["pass", "warn", "fail"]
StoryBriefConsistencySeverity = Literal["info", "warn", "fail"]
# Locale a template's narration / NPC dialogue is generated in. The
# field is set at template creation and is immutable thereafter — every
# session forking the same template inherits the same language. Adding
# a new locale requires extending this Literal AND adding a prompt-
# language branch in `engine.py`.
TemplateLanguage = Literal["zh", "en"]
# OSS default is English — most readers landing on this repo are
# non-Chinese-speaking. New templates created without an explicit
# `language` field generate English narration. The `language` column
# migration in repository._ensure_schema still backfills pre-i18n
# rows with 'zh' so historic templates keep their original locale.
DEFAULT_TEMPLATE_LANGUAGE: TemplateLanguage = "en"


class LocalizedText(BaseModel):
    """Optional display metadata for non-story chrome.

    Story body, cast, options, and turns remain in the template language.
    These strings are only for list/replay display surfaces.
    """

    model_config = ConfigDict(extra="forbid")

    zh: str | None = Field(default=None, max_length=4000)
    en: str | None = Field(default=None, max_length=4000)


class NarrativeTemplate(BaseModel):
    """Full template record (used internally by the service)."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(min_length=1, max_length=80)
    owner_user_id: str = Field(min_length=1, max_length=80)
    seed: str = Field(min_length=1, max_length=4000)
    title: str = Field(min_length=1, max_length=120)
    title_i18n: LocalizedText | None = None
    summary_i18n: LocalizedText | None = None
    cast: list[CastMember] = Field(min_length=2, max_length=10)
    advisor_persona: str = Field(min_length=1, max_length=200)
    opening_passage: str = Field(min_length=1, max_length=4000)
    opening_options: list[StoryOption] = Field(default_factory=list)
    cover_image_url: str | None = Field(default=None, max_length=1000)
    # Gauntlet-mode shared scaffolding (lives on the template so all sessions
    # forking the same template fight the same fight). Always populated by
    # the opening engine; only ENFORCED when session.difficulty == "gauntlet".
    player_goals: list[PlayerGoal] = Field(default_factory=list)
    failure_conditions: list[FailureCondition] = Field(default_factory=list)
    # 3-5 selectable player identities. Each session picks one role at
    # start. Empty list on legacy templates created before this feature.
    player_role_options: list[PlayerRole] = Field(default_factory=list, max_length=6)
    visibility: TemplateVisibility = "private"
    # The locale narration / NPC dialogue is generated in. Pre-i18n
    # templates default to "zh" via the migration backfill.
    language: TemplateLanguage = DEFAULT_TEMPLATE_LANGUAGE
    play_count: int = Field(default=0, ge=0)
    created_at: str = Field(min_length=1)


class NarrativeTemplateSummary(BaseModel):
    """Public-facing template summary (for list pages and details)."""

    model_config = ConfigDict(extra="forbid")

    template_id: str
    owner_user_id: str
    seed: str
    title: str
    title_i18n: LocalizedText | None = None
    summary_i18n: LocalizedText | None = None
    cast: list[CastMember]
    advisor_persona: str
    cover_image_url: str | None = Field(default=None, max_length=1000)
    player_goals: list[PlayerGoal] = Field(default_factory=list)
    failure_conditions: list[FailureCondition] = Field(default_factory=list)
    player_role_options: list[PlayerRole] = Field(default_factory=list)
    visibility: TemplateVisibility
    language: TemplateLanguage = DEFAULT_TEMPLATE_LANGUAGE
    play_count: int
    created_at: str
    is_owner: bool = False


# --------------------------------------------------------------------------
# Story Brief Agent / Cast Planner / Tension Profile v2
# --------------------------------------------------------------------------


class ConstraintDisposition(BaseModel):
    """How the planner will handle a user-provided premise constraint."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    disposition: ConstraintDispositionKind
    rationale: str = Field(min_length=1, max_length=220)


class StoryBriefPlanItem(BaseModel):
    """One visible non-cast planning item on the brief card."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=140)
    rationale: str = Field(min_length=1, max_length=240)


class StoryBriefRevisionAction(BaseModel):
    """Safe one-click revision affordance for the guided brief panel."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=180)
    seed_append: str = Field(min_length=1, max_length=220)


class CastPlanEntity(BaseModel):
    """One planned character, entity, object, or faction in the brief."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=80)
    kind: CastPlanEntityKind = "character"
    role: str = Field(min_length=1, max_length=140)
    rationale: str = Field(min_length=1, max_length=220)


class CastPlan(BaseModel):
    """Global cast plan: up to 10 entities, with 3-5 active at runtime."""

    model_config = ConfigDict(extra="forbid")

    input_entity_count: int = Field(default=0, ge=0)
    primary_active_entities: list[CastPlanEntity] = Field(default_factory=list, max_length=5)
    secondary_background_entities: list[CastPlanEntity] = Field(default_factory=list, max_length=5)
    omitted_entities: list[CastPlanEntity] = Field(default_factory=list, max_length=5)
    active_focus_window: str = Field(min_length=1, max_length=160)


class StoryBrief(BaseModel):
    """Compact pre-generation plan the user reviews before spending LLM budget."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["story_brief.v1"] = "story_brief.v1"
    source: StoryBriefSource = "deterministic_v1"
    original_seed: str = Field(min_length=1, max_length=4000)
    display_title: str | None = Field(default=None, min_length=1, max_length=72)
    display_intro: str | None = Field(default=None, min_length=1, max_length=140)
    premise_summary: str = Field(min_length=1, max_length=260)
    genre_tone: str = Field(min_length=1, max_length=160)
    tension_profile: TensionProfile
    story_kernel: str = Field(min_length=1, max_length=220)
    intervention_card_label: str = Field(min_length=1, max_length=80)
    cast_plan: CastPlan
    constraints: list[StoryBriefPlanItem] = Field(default_factory=list, max_length=10)
    time_event_anchors: list[StoryBriefPlanItem] = Field(default_factory=list, max_length=10)
    tone_constraints: list[StoryBriefPlanItem] = Field(default_factory=list, max_length=10)
    world_setting_pressure: list[StoryBriefPlanItem] = Field(default_factory=list, max_length=10)
    preserved_constraints: list[str] = Field(default_factory=list, max_length=8)
    compressed_constraints: list[str] = Field(default_factory=list, max_length=8)
    dropped_constraints: list[str] = Field(default_factory=list, max_length=8)
    softened_constraints: list[str] = Field(default_factory=list, max_length=8)
    constraint_dispositions: list[ConstraintDisposition] = Field(default_factory=list, max_length=16)
    warnings: list[str] = Field(default_factory=list, max_length=8)
    revision_suggestions: list[str] = Field(default_factory=list, max_length=8)
    revision_actions: list[StoryBriefRevisionAction] = Field(default_factory=list, max_length=8)
    adaptation_note: str = Field(
        default="Beta planner draft: review the adaptation before generation; it is not a fidelity guarantee.",
        min_length=1,
        max_length=220,
    )
    runtime_fit_status: StoryBriefFitStatus = "fit"
    runtime_fit_rationale: str = Field(min_length=1, max_length=260)


class StoryBriefConsistencyViolation(BaseModel):
    """Safe post-generation mismatch evidence for a confirmed brief."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    severity: StoryBriefConsistencySeverity
    rationale: str = Field(min_length=1, max_length=260)
    evidence: list[str] = Field(default_factory=list, max_length=6)


class StoryBriefConsistencyCheck(BaseModel):
    """Conservative brief-vs-opening checker result."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["story_brief_consistency.v1"] = "story_brief_consistency.v1"
    status: StoryBriefConsistencyStatus
    violations: list[StoryBriefConsistencyViolation] = Field(default_factory=list, max_length=12)
    summary: str = Field(min_length=1, max_length=260)
    should_retry: bool = False


class StoryBriefAdvisorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: str = Field(min_length=1, max_length=4000)
    language: TemplateLanguage = DEFAULT_TEMPLATE_LANGUAGE
    desired_tension_profile: TensionProfile | None = None

    @field_validator("seed")
    @classmethod
    def _strip_seed(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Seed must not be empty.")
        return stripped


class StoryBriefAdvisorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: StoryBrief
    can_generate: bool
    next_step: str = Field(min_length=1, max_length=220)
    source: StoryBriefSource = "deterministic_v1"
    runtime_source: LLMCallSourceLabel = "deterministic_fallback"


StoryGuideConversationState = Literal[
    "empty",
    "collecting",
    "needs_field",
    "clarify_conflict",
    "redirect",
    "analyzing",
    "ready_to_brief",
    "brief_ready",
    "brief_not_fit",
]
StoryGuideNodeName = Literal[
    "parse_message",
    "safety_gate",
    "update_slots",
    "ask_missing_slot",
    "clarify_conflict",
    "redirect_out_of_spec",
    "ready_to_shape",
    "shape_story_brief",
    "brief_ready",
    "brief_not_fit",
]
StoryGuideSlotId = Literal[
    "player_role",
    "active_cast",
    "pressure",
    "tone",
    "boundaries",
    "first_scene_hook",
]
StoryGuideMemoryRole = Literal["user", "assistant"]


class StoryGuideSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StoryGuideSlotId
    filled: bool = False
    label: str = Field(min_length=1, max_length=80)
    evidence: str = Field(default="", max_length=220)


class StoryGuideMemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: StoryGuideMemoryRole
    text: str = Field(min_length=1, max_length=420)


class StoryGuideCompressedContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_summary: str = Field(default="", max_length=260)
    player_role: str = Field(default="", max_length=160)
    cast_or_factions: list[str] = Field(default_factory=list, max_length=8)
    pressure: str = Field(default="", max_length=220)
    constraints: list[str] = Field(default_factory=list, max_length=8)
    tone: str = Field(default="", max_length=120)
    open_questions: list[str] = Field(default_factory=list, max_length=6)
    confirmed_facts: list[str] = Field(default_factory=list, max_length=12)
    rejected_or_changed_facts: list[str] = Field(default_factory=list, max_length=8)
    last_question: str = Field(default="", max_length=220)
    readiness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    planner_skill: str = Field(default="", max_length=80)
    planner_job: str = Field(default="", max_length=180)
    recent_turns: list[StoryGuideMemoryEntry] = Field(default_factory=list, max_length=12)
    compression_source: LLMCallSourceLabel = "deterministic_fallback"


class StoryGuideLoopState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StoryGuideConversationState
    lastNode: StoryGuideNodeName
    slots: dict[StoryGuideSlotId, StoryGuideSlot]
    acceptedTurns: list[str] = Field(default_factory=list, max_length=24)
    blockedTurns: list[str] = Field(default_factory=list, max_length=12)
    nextMissing: StoryGuideSlotId | None = None
    context: StoryGuideCompressedContext = Field(default_factory=StoryGuideCompressedContext)


class StoryGuideInlineLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knownLabel: str = Field(min_length=1, max_length=40)
    stillNeedLabel: str = Field(min_length=1, max_length=40)
    nextQuestionLabel: str = Field(min_length=1, max_length=40)
    known: str = Field(min_length=1, max_length=220)
    stillNeed: str = Field(min_length=1, max_length=220)
    nextQuestion: str = Field(min_length=1, max_length=220)


class StoryGuideSettingDeltas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turnBudget: int | None = Field(default=None, ge=4, le=40)
    difficulty: Difficulty | None = None
    language: TemplateLanguage | None = None
    tensionProfile: TensionProfile | None = None
    privacyIntent: TemplateVisibility | None = None


class StoryGuideTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=1000)
    language: TemplateLanguage = DEFAULT_TEMPLATE_LANGUAGE
    current_seed: str = Field(default="", max_length=4000)
    previous_assistant_reply: str = Field(default="", max_length=600)
    state: StoryGuideLoopState | None = None

    @field_validator("message")
    @classmethod
    def _strip_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message must not be empty.")
        return stripped


class StoryGuideTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: StoryGuideLoopState
    node: StoryGuideNodeName
    status: StoryGuideConversationState
    reply: str = Field(min_length=1, max_length=420)
    acceptedText: bool
    blocked: bool
    canShapeBrief: bool
    settings: StoryGuideSettingDeltas | None = None
    ledger: StoryGuideInlineLedger | None = None
    source: LLMCallSourceLabel = "deterministic_fallback"


# --------------------------------------------------------------------------
# Session (one player's playthrough of a template)
# --------------------------------------------------------------------------


class NarrativeSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=80)
    template_id: str = Field(min_length=1, max_length=80)
    player_user_id: str = Field(min_length=1, max_length=80)
    turn_count: int = Field(ge=0)
    turn_budget: int = Field(default=12, ge=4, le=40)
    difficulty: Difficulty = "story"
    # role_id of the PlayerRole picked from template.player_role_options.
    # None for legacy sessions or templates without role options.
    selected_player_role_id: str | None = None
    ending_label: str | None = None
    ending_subtitle: str | None = None
    ending_passage: str | None = None
    ending_tier: EndingTier | None = None
    early_terminated: bool = False
    failure_trigger: str | None = None
    created_at: str
    last_active_at: str


class NarrativeSessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    template_id: str
    template_title: str
    template_seed: str
    template_title_i18n: LocalizedText | None = None
    template_summary_i18n: LocalizedText | None = None
    player_user_id: str
    turn_count: int
    turn_budget: int = 12
    difficulty: Difficulty = "story"
    # The actual PlayerRole the session is using (resolved from role_id),
    # surfaced for UI rendering. None on legacy sessions.
    player_role: PlayerRole | None = None
    ending_label: str | None = None
    ending_subtitle: str | None = None
    ending_tier: EndingTier | None = None
    early_terminated: bool = False
    created_at: str
    last_active_at: str


class Highlight(BaseModel):
    """One pivotal moment in a finished session, surfaced as a card on
    the post-game replay reel. The five highlights together form the
    'shareable summary' of how this run played out — what mattered, why
    it mattered, and where the LLM thinks the player decided their tier.
    """

    model_config = ConfigDict(extra="forbid")

    # Which narrator beat this highlight points at (ord of that message).
    # Always references a narrator beat the player actually saw.
    beat_ord: int = Field(ge=0)
    # Short title of the moment, shown as the card header. ≤30 chars.
    headline: str = Field(min_length=1, max_length=30)
    # The most dramatic 1-3 sentence chunk lifted from that beat's
    # narration, verbatim or near-verbatim. ≤400 chars after truncation.
    body_excerpt: str = Field(min_length=1, max_length=400)
    # The LLM's read on why this moment was pivotal — references the
    # player's choices, hidden_objective, leverage, or inventory in a
    # one-line analysis. ≤200 chars.
    why_pivotal: str = Field(min_length=1, max_length=200)


class BranchHypothetical(BaseModel):
    """One 'what-if' fork point identified by the LLM after a session
    finishes. Anchored to a specific narrator beat, showing what the
    player picked vs an alternate option, and the LLM's plausibility-
    grade prediction of which ending label the alternate path would
    have hit.

    These are not authoritative — the LLM is hypothesizing, not
    simulating. The alternate_ending_label must be in the closed
    ENDING_LABELS pool so the player sees it as "another tier-marked
    outcome they could have collected", not a free-form spoiler.
    """

    model_config = ConfigDict(extra="forbid")

    # Which narrator beat the branch forks from. Always references a
    # real narrator beat from this session.
    pivot_beat_ord: int = Field(ge=0)
    # Short summary of what the player actually did at this turn.
    chosen_path_summary: str = Field(min_length=1, max_length=80)
    # Short summary of the alternate move the player could have made.
    alternate_path_summary: str = Field(min_length=1, max_length=80)
    # The ending label the LLM predicts for the alternate path. Must
    # be one of the closed ENDING_LABELS values (validator drops misses).
    alternate_ending_label: str = Field(min_length=1, max_length=20)
    # Tier of that hypothetical ending — derived server-side from
    # alternate_ending_label so the UI can color-grade the card.
    alternate_ending_tier: EndingTier = "compromised"
    # 1-2 sentence narrative justification — why this alt path likely
    # leads to that label. ≤200 chars.
    rationale: str = Field(min_length=1, max_length=200)


class NarrativeEnding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=40)
    subtitle: str = Field(min_length=1, max_length=80)
    passage: str = Field(min_length=1, max_length=4000)
    tier: EndingTier = "compromised"
    early_terminated: bool = False
    failure_trigger: str | None = None
    # Up to 5 pivotal moments from the run, surfaced as a post-game
    # highlight reel. Empty list on legacy sessions or if the
    # synthesize_highlights call failed (non-fatal).
    highlights: list[Highlight] = Field(default_factory=list, max_length=6)
    # Up to 3 hypothetical fork points showing alternate endings the
    # player could have hit. Drives replay intent: "you didn't take
    # these 2 paths, here's roughly what they'd have looked like."
    branches: list[BranchHypothetical] = Field(default_factory=list, max_length=4)


class EndingDistributionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    count: int


class EndingDistributionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    total_completed: int
    entries: list[EndingDistributionEntry]


class PublicReplayResponse(BaseModel):
    """A public, auth-free read of a completed session for sharing.

    Includes story messages, final ending, and the advisor sidechat (which
    is part of the unique 'how I felt while playing' shareable content).
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    template_id: str
    template_forkable: bool = False
    template_title: str
    template_seed: str
    template_title_i18n: LocalizedText | None = None
    template_summary_i18n: LocalizedText | None = None
    cast: list[CastMember]
    advisor_persona: str
    cover_image_url: str | None = Field(default=None, max_length=1000)
    player_goals: list[PlayerGoal] = Field(default_factory=list)
    player_role: PlayerRole | None = None
    turn_budget: int
    turn_count: int
    difficulty: Difficulty = "story"
    completed: bool
    ending: NarrativeEnding | None
    messages: list[StoryMessage]
    advisor_messages: list[AdvisorMessage]
    created_at: str


# --------------------------------------------------------------------------
# Request / response payloads
# --------------------------------------------------------------------------


class CreateTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: str = Field(min_length=1, max_length=4000)
    visibility: TemplateVisibility = "private"
    turn_budget: int = Field(default=12, ge=4, le=40)
    difficulty: Difficulty = "story"
    # Narration / NPC dialogue locale. Immutable after creation —
    # all sessions forking this template share the same language.
    language: TemplateLanguage = DEFAULT_TEMPLATE_LANGUAGE
    # Optional create-time plan returned by Story Brief Advisor. This is
    # reviewed by the user before generation, then injected into the opening
    # payload so planning and generation use the same facts. It is not
    # persisted on the template in this MVP.
    story_brief: StoryBrief | None = None

    @field_validator("seed")
    @classmethod
    def _strip_seed(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Seed must not be empty.")
        return stripped


class CreateTemplateResponse(BaseModel):
    """Returned when a user creates a new template.

    A session is auto-created so the creator can immediately start playing.
    """

    model_config = ConfigDict(extra="forbid")

    template: NarrativeTemplateSummary
    session: NarrativeSessionSummary
    opening: StoryMessage
    story_brief_consistency: StoryBriefConsistencyCheck | None = None
    opening_recovery: Literal["tightened_from_brief"] | None = None


class StartSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_budget: int = Field(default=12, ge=4, le=40)
    difficulty: Difficulty = "story"
    # Index into template.player_role_options. None or out-of-range
    # falls back to the first option (or no role at all if template
    # was created before player roles existed).
    player_role_index: int | None = Field(default=None, ge=0, le=10)


class StartSessionResponse(BaseModel):
    """Returned when a user starts a fresh session on an existing template."""

    model_config = ConfigDict(extra="forbid")

    template: NarrativeTemplateSummary
    session: NarrativeSessionSummary
    opening: StoryMessage


class TemplateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[NarrativeTemplateSummary]


class SessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[NarrativeSessionSummary]


class UpdateTemplateVisibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility: TemplateVisibility


class StoryHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template: NarrativeTemplateSummary
    session: NarrativeSessionSummary
    messages: list[StoryMessage]
    agent_events: list[NarrativeAgentEvent] = Field(default_factory=list)


class AdvanceTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chosen_option_index: int | None = None
    free_input: str | None = Field(default=None, max_length=400)
    # Optional inner monologue. Stored on the player message and fed to
    # the LLM as private context, never shown to NPC characters in the
    # fiction. Lets the player record what they're really thinking
    # while playing the role.
    diary: str | None = Field(default=None, max_length=600)
    played_leverage: PlayedLeverageCard | None = None


class AdvanceTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_message: StoryMessage
    narrator_message: StoryMessage
    agent_plan: AgentPlan | None = None
    agent_events: list[NarrativeAgentEvent] = Field(default_factory=list)
    # Surfaced when this turn was the last of the budget — the engine has
    # already generated and persisted the ending. Frontend uses this to
    # render the ending screen without a follow-up GET.
    ending: NarrativeEnding | None = None
    is_complete: bool = False


class AdvisorAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=400)
    # Oracle mode: advisor uses privileged info (NPC hidden_objectives,
    # pulse trends, unused leverage) to give the player a mood-appropriate
    # hint. Costs 1 turn from session.turn_budget. Off by default.
    oracle_mode: bool = False

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Question must not be empty.")
        return stripped


class AdvisorAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_message: AdvisorMessage
    advisor_message: AdvisorMessage
    # Filled when oracle_mode was true. Shows the new turn_budget so the
    # frontend can update the budget chip without a refetch.
    turn_budget_after: int | None = None
    # Marks the advisor reply as oracle so the UI can render it
    # differently (e.g. gold-tinted "情报").
    oracle_used: bool = False


class AdvisorHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona: str
    messages: list[AdvisorMessage]
