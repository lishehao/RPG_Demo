from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MemoryEventKind = Literal[
    "objective_set",
    "fact_asserted",
    "fact_corrected",
    "non_story_input",
    "thread_opened",
    "thread_resolved",
    "entity_changed",
    "player_action",
    "world_consequence",
    "clue_unlocked",
]
MemoryFactStatus = Literal["active", "superseded"]
EvaluationStatus = Literal["pass", "warn", "fail"]


class RpgMemoryEventV1(BaseModel):
    """One bounded state-changing observation from any RPG runtime."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=120)
    turn_index: int = Field(ge=0, le=500)
    kind: MemoryEventKind
    namespace: str = Field(default="story", min_length=1, max_length=40)
    key: str = Field(default="", max_length=80)
    value: str = Field(default="", max_length=600)
    entity_id: str | None = Field(default=None, max_length=80)
    entity_name: str | None = Field(default=None, max_length=120)
    state: dict[str, str] = Field(default_factory=dict, max_length=12)
    source: Literal["user", "runtime", "system", "imported"] = "runtime"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("event_id", "namespace", "key", "value", "entity_id", "entity_name", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RpgMemoryFactV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str = Field(min_length=1, max_length=160)
    namespace: str = Field(min_length=1, max_length=40)
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=600)
    status: MemoryFactStatus = "active"
    source_turn: int = Field(ge=0, le=500)
    source: Literal["user", "runtime", "system", "imported"] = "runtime"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    superseded_by: str | None = Field(default=None, max_length=160)


class RpgMemoryEntityV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    state: dict[str, str] = Field(default_factory=dict, max_length=12)
    last_updated_turn: int = Field(ge=0, le=500)


class RpgMemoryDiagnosticsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_count: int = Field(ge=0)
    active_fact_count: int = Field(ge=0)
    superseded_fact_count: int = Field(ge=0)
    non_story_event_count: int = Field(ge=0)
    dropped_recent_event_count: int = Field(ge=0)
    last_compacted_turn: int = Field(ge=0)


class RpgMemorySnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rpg_memory.v1"] = "rpg_memory.v1"
    run_id: str = Field(min_length=1, max_length=120)
    turn_index: int = Field(ge=0, le=500)
    objective: str = Field(default="", max_length=600)
    active_facts: list[RpgMemoryFactV1] = Field(default_factory=list, max_length=32)
    superseded_facts: list[RpgMemoryFactV1] = Field(default_factory=list, max_length=32)
    open_threads: list[str] = Field(default_factory=list, max_length=16)
    entities: list[RpgMemoryEntityV1] = Field(default_factory=list, max_length=16)
    recent_events: list[str] = Field(default_factory=list, max_length=10)
    episodic_summary: str = Field(default="", max_length=1200)
    diagnostics: RpgMemoryDiagnosticsV1


class RpgStateDeltaV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1, max_length=100)
    kind: Literal["increase", "decrease", "set", "unlock", "spend", "shift"]
    label: str = Field(min_length=1, max_length=160)
    value: str = Field(default="", max_length=120)
    evidence: str = Field(default="", max_length=300)


class RpgTurnObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_index: int = Field(ge=1, le=500)
    player_action: str = Field(min_length=1, max_length=800)
    world_response: str = Field(min_length=1, max_length=2400)
    options: list[str] = Field(default_factory=list, min_length=1, max_length=6)
    state_deltas: list[RpgStateDeltaV1] = Field(default_factory=list, max_length=8)
    clue_unlocks: list[str] = Field(default_factory=list, max_length=4)
    opportunity_unlocks: list[str] = Field(default_factory=list, max_length=4)
    referenced_entity_ids: list[str] = Field(default_factory=list, max_length=12)
    objective_progress: float = Field(default=0.0, ge=0.0, le=1.0)
    memory: RpgMemorySnapshotV1


class RpgEvaluationScenarioV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=160)
    genre: str = Field(default="interactive_rpg", max_length=80)
    objective: str = Field(min_length=1, max_length=600)
    turn_budget: int = Field(default=12, ge=1, le=80)
    entity_ids: list[str] = Field(default_factory=list, max_length=24)
    boundaries: list[str] = Field(default_factory=list, max_length=16)


class RpgEvaluationBundleV1(BaseModel):
    """Portable adapter input for deterministic RPG runtime evaluation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rpg_evaluation_bundle.v1"] = "rpg_evaluation_bundle.v1"
    run_id: str = Field(min_length=1, max_length=120)
    system_label: str = Field(min_length=1, max_length=120)
    locale: Literal["en", "zh", "mixed"] = "en"
    scenario: RpgEvaluationScenarioV1
    turns: list[RpgTurnObservationV1] = Field(default_factory=list, min_length=1, max_length=80)


class RpgCriterionResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: Literal[
        "memory_continuity",
        "memory_boundedness",
        "consequence_visibility",
        "player_agency",
        "trajectory_progress",
        "entity_coherence",
        "choice_diversity",
        "boundary_hygiene",
    ]
    status: EvaluationStatus
    score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=240)
    evidence: list[str] = Field(default_factory=list, max_length=6)


class RpgEvaluationReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rpg_evaluation_report.v1"] = "rpg_evaluation_report.v1"
    run_id: str
    system_label: str
    status: EvaluationStatus
    score: int = Field(ge=0, le=100)
    criteria: list[RpgCriterionResultV1] = Field(min_length=8, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8)
