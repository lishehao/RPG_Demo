from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rpg_backend.domain.conflict_tags import NPCConflictTag
from rpg_backend.domain.pack_schema import Move, Scene, StoryPack, StrategyStyle
from rpg_backend.generator.author_shared_types import EndingShape, MoveBiasTag


class OverviewNPC(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    motivation: str = Field(min_length=1)
    red_line: str = Field(min_length=1, max_length=160)
    conflict_tags: list[NPCConflictTag] = Field(min_length=1, max_length=3)
    pressure_signature: str = Field(min_length=1, max_length=220)


class StoryOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=400)
    tone: str = Field(min_length=1, max_length=120)
    stakes: str = Field(min_length=1, max_length=300)
    target_minutes: int = Field(ge=8, le=12)
    npc_count: int = Field(ge=3, le=5)
    ending_shape: EndingShape
    ending_shape_note: str = Field(min_length=1, max_length=220)
    npc_roster: list[OverviewNPC] = Field(min_length=3, max_length=5)
    move_bias: list[MoveBiasTag] = Field(min_length=1, max_length=6)
    move_bias_note: str = Field(min_length=1, max_length=220)
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


class BeatOverviewNPCContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    red_line: str = Field(min_length=1, max_length=160)
    conflict_tags: list[NPCConflictTag] = Field(min_length=1, max_length=3)
    pressure_signature: str = Field(min_length=1, max_length=220)


class BeatOverviewContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=400)
    tone: str = Field(min_length=1, max_length=120)
    stakes: str = Field(min_length=1, max_length=300)
    ending_shape: EndingShape
    ending_shape_note: str = Field(min_length=1, max_length=220)
    move_bias: list[MoveBiasTag] = Field(min_length=1, max_length=6)
    move_bias_note: str = Field(min_length=1, max_length=220)
    npc_roster: list[BeatOverviewNPCContext] = Field(min_length=3, max_length=5)
    scene_constraints: list[str] = Field(min_length=1)


class BeatPrefixBeatSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    title: str = Field(min_length=1)


class BeatPrefixSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_beats: list[BeatPrefixBeatSummary] = Field(default_factory=list)


class AuthorMemoryBeatSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    present_npcs: list[str] = Field(default_factory=list)
    events_produced: list[str] = Field(default_factory=list)
    closing_hook: str | None = None


class AuthorMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_count: int = Field(default=0, ge=0)
    active_npcs: list[str] = Field(default_factory=list)
    unresolved_threads: list[str] = Field(default_factory=list)
    recent_beats: list[AuthorMemoryBeatSummary] = Field(default_factory=list, max_length=2)


class BeatScenePlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str | None = Field(default=None)
    purpose: str = Field(min_length=1, max_length=220)
    pressure: str = Field(min_length=1, max_length=220)
    handoff_intent: str = Field(min_length=1, max_length=220)
    present_npcs: list[str] = Field(min_length=1, max_length=5)
    is_terminal: bool = False
    transition_style: str = Field(min_length=1, max_length=120)


class BeatScenePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    scenes: list[BeatScenePlanItem] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def normalize_scene_ids(self) -> "BeatScenePlan":
        scene_ids: list[str] = []
        for index, item in enumerate(self.scenes, start=1):
            scene_id = f"{self.beat_id}.sc{index}"
            item.scene_id = scene_id
            scene_ids.append(scene_id)
        if len(scene_ids) != len(set(scene_ids)):
            raise ValueError("scene plan scene_ids must be unique")
        return self


class GeneratedSceneNarrationSlots(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_reaction: str = Field(min_length=1, max_length=220)
    world_shift: str = Field(min_length=1, max_length=220)
    clue_delta: str = Field(min_length=1, max_length=220)
    cost_delta: str = Field(min_length=1, max_length=220)
    next_hook: str = Field(min_length=1, max_length=220)


class GeneratedSceneMoveOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["success", "partial", "fail_forward"]
    narration_slots: GeneratedSceneNarrationSlots


class GeneratedSceneMove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    strategy_style: StrategyStyle
    intents: list[str] = Field(min_length=1, max_length=3)
    synonyms: list[str] = Field(default_factory=list, max_length=4)
    resolution_policy: Literal["prefer_success", "prefer_partial", "always_fail_forward"] = "prefer_success"
    outcomes: list[GeneratedSceneMoveOutcome] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_outcomes(self) -> "GeneratedSceneMove":
        outcome_results = [item.result for item in self.outcomes]
        if set(outcome_results) != {"success", "partial", "fail_forward"}:
            raise ValueError("generated move outcomes must include success, partial, and fail_forward exactly once")
        return self


class GeneratedBeatScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_seed: str = Field(min_length=1, max_length=320)
    present_npcs: list[str] = Field(min_length=1, max_length=5)
    local_moves: list[GeneratedSceneMove] = Field(min_length=3, max_length=3)
    events_produced: list[str] = Field(default_factory=list)
    transition_hint: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_generated_scene(self) -> "GeneratedBeatScene":
        move_labels = [move.label.strip().casefold() for move in self.local_moves]
        if len(move_labels) != len(set(move_labels)):
            raise ValueError("generated local move labels must be unique")
        return self


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
