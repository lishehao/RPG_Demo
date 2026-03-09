from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rpg_backend.domain.conflict_tags import NPCConflictTag
from rpg_backend.domain.pack_schema import Condition, Effect, Move, NarrationSlots, Scene, StoryPack, StrategyStyle
from rpg_backend.generator.outcome_materialization import validate_palette_id_exists
from rpg_backend.generator.author_shared_types import EndingShape, MoveBiasTag


class OverviewNPC(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    motivation: str = Field(min_length=1)
    red_line: str = Field(min_length=1, max_length=160)
    conflict_tags: list[NPCConflictTag] = Field(min_length=1, max_length=3)


class StoryOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=400)
    tone: str = Field(min_length=1, max_length=120)
    stakes: str = Field(min_length=1, max_length=300)
    target_minutes: int = Field(ge=8, le=12)
    npc_count: int = Field(ge=3, le=5)
    ending_shape: EndingShape
    npc_roster: list[OverviewNPC] = Field(min_length=3, max_length=5)
    move_bias: list[MoveBiasTag] = Field(min_length=1, max_length=6)
    scene_constraints: list[str] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_npc_count(self) -> "StoryOverview":
        if len(self.npc_roster) != self.npc_count:
            raise ValueError("npc_count must equal npc_roster length")
        seen = [npc.name.strip().casefold() for npc in self.npc_roster]
        if len(set(seen)) != len(seen):
            raise ValueError("npc_roster names must be unique")
        return self


class BeatBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    required_event: str = Field(min_length=1)
    step_budget: int = Field(ge=1)
    npc_quota: int = Field(ge=0)
    entry_scene_id: str = Field(min_length=1)
    scene_intent: str = Field(min_length=1)


class BeatOutcomeLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["success", "partial", "fail_forward"]
    palette_id: str = Field(min_length=1)
    next_scene_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_palette_id(self) -> "BeatOutcomeLLM":
        validate_palette_id_exists(self.palette_id)
        return self


class BeatMoveLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    strategy_style: StrategyStyle
    intents: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    resolution_policy: Literal["prefer_success", "prefer_partial", "always_fail_forward"] = "prefer_success"
    outcomes: list[BeatOutcomeLLM] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_required_outcome_coverage(self) -> "BeatMoveLLM":
        results = {outcome.result for outcome in self.outcomes}
        if "success" not in results or "fail_forward" not in results:
            raise ValueError("moves must include success and fail_forward outcomes")
        return self


class BeatSceneLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_seed: str = Field(min_length=1)
    present_npcs: list[str] = Field(min_length=1)
    enabled_move_indexes: list[int] = Field(min_length=3, max_length=5)
    is_terminal: bool = False

    @model_validator(mode="after")
    def validate_indexes_unique(self) -> "BeatSceneLLM":
        if len(set(self.enabled_move_indexes)) != len(self.enabled_move_indexes):
            raise ValueError("enabled_move_indexes must be unique within a scene")
        return self


class BeatDraftLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenes: list[BeatSceneLLM] = Field(min_length=1)
    moves: list[BeatMoveLLM] = Field(min_length=3)
    present_npcs: list[str] = Field(min_length=1)
    events_produced: list[str] = Field(default_factory=list)


class BeatOverviewNPCContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    red_line: str = Field(min_length=1, max_length=160)
    conflict_tags: list[NPCConflictTag] = Field(min_length=1, max_length=3)


class BeatOverviewContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=400)
    tone: str = Field(min_length=1, max_length=120)
    stakes: str = Field(min_length=1, max_length=300)
    ending_shape: EndingShape
    move_bias: list[MoveBiasTag] = Field(min_length=1, max_length=6)
    npc_roster: list[BeatOverviewNPCContext] = Field(min_length=3, max_length=5)
    scene_constraints: list[str] = Field(min_length=1)


class BeatPrefixBeatSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    title: str = Field(min_length=1)


class BeatPrefixSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_beats: list[BeatPrefixBeatSummary] = Field(default_factory=list)
    events_produced: list[str] = Field(default_factory=list)
    active_npcs: list[str] = Field(default_factory=list)
    unresolved_hooks: list[str] = Field(default_factory=list)


class BeatDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    required_event: str = Field(min_length=1)
    entry_scene_id: str = Field(min_length=1)
    scenes: list[Scene] = Field(min_length=1)
    moves: list[Move] = Field(min_length=1)
    present_npcs: list[str] = Field(min_length=1)
    events_produced: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_local_consistency(self) -> "BeatDraft":
        if self.entry_scene_id not in {scene.id for scene in self.scenes}:
            raise ValueError("entry_scene_id must reference a scene inside the beat draft")
        for scene in self.scenes:
            if scene.beat_id != self.beat_id:
                raise ValueError("all scenes in a beat draft must use the draft beat_id")
            if len(scene.always_available_moves) < 2 or len(scene.always_available_moves) > 3:
                raise ValueError("all scenes must include 2-3 always_available_moves")
        scene_ids = [scene.id for scene in self.scenes]
        if len(scene_ids) != len(set(scene_ids)):
            raise ValueError("scene ids must be unique inside a beat draft")
        move_ids = [move.id for move in self.moves]
        if len(move_ids) != len(set(move_ids)):
            raise ValueError("move ids must be unique inside a beat draft")
        return self


class BeatLintReport(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StoryPackArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack: StoryPack
    final_lint_errors: list[str] = Field(default_factory=list)
    final_lint_warnings: list[str] = Field(default_factory=list)


def model_to_json_payload(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return dict(value)
