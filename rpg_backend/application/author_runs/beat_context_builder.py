from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rpg_backend.generator.author_workflow_models import (
    AuthorMemory,
    GeneratedBeatScene,
    BeatScenePlan,
    BeatDraft,
    BeatOverviewContext,
    BeatPrefixSummary,
    StoryOverview,
)
from rpg_backend.generator.author_workflow_validators import (
    build_author_memory,
    build_structured_prefix_summary,
    project_overview_for_beat_generation,
)


@dataclass(frozen=True)
class BeatGenerationContext:
    prefix_summary: BeatPrefixSummary
    author_memory: AuthorMemory
    overview_context: BeatOverviewContext
    last_accepted_beat: dict[str, Any] | None


@dataclass(frozen=True)
class SceneGenerationContext:
    scene_plan_item: dict[str, Any]
    prior_scene_memory: list[dict[str, Any]]


def build_beat_generation_context(*, overview: StoryOverview, prior_beats: list[BeatDraft]) -> BeatGenerationContext:
    prefix_summary = build_structured_prefix_summary(prior_beats)
    author_memory = build_author_memory(prior_beats)
    overview_context = project_overview_for_beat_generation(overview)
    last_accepted_beat = (
        author_memory.recent_beats[-1].model_dump(mode="json")
        if author_memory.recent_beats
        else None
    )
    return BeatGenerationContext(
        prefix_summary=prefix_summary,
        author_memory=author_memory,
        overview_context=overview_context,
        last_accepted_beat=last_accepted_beat,
    )


def compact_scene_generation_memory(
    generated_scenes: list[GeneratedBeatScene],
    *,
    max_items: int = 1,
) -> list[dict[str, Any]]:
    tail = generated_scenes[-max_items:] if max_items > 0 else []
    compact: list[dict[str, Any]] = []
    for index, generated in enumerate(tail, start=max(1, len(generated_scenes) - len(tail) + 1)):
        compact.append(
            {
                "scene_order": index,
                "scene_seed": generated.scene_seed,
                "present_npcs": list(generated.present_npcs),
                "move_labels": [move.label for move in generated.local_moves],
                "events_produced": list(generated.events_produced),
                "transition_hint": generated.transition_hint,
            }
        )
    return compact


def build_scene_generation_context(
    *,
    scene_plan: BeatScenePlan,
    scene_index: int,
    generated_scenes: list[GeneratedBeatScene],
) -> SceneGenerationContext:
    if scene_index < 0 or scene_index >= len(scene_plan.scenes):
        raise ValueError("scene_index is outside current beat scene plan")
    return SceneGenerationContext(
        scene_plan_item=scene_plan.scenes[scene_index].model_dump(mode="json"),
        prior_scene_memory=compact_scene_generation_memory(generated_scenes, max_items=1),
    )
