"""Portable, reviewer-facing contracts for RPG runtime research."""

from rpg_backend.research_runtime.contracts import (
    RpgEvaluationBundleV1,
    RpgEvaluationReportV1,
    RpgMemoryEventV1,
    RpgMemorySnapshotV1,
)
from rpg_backend.research_runtime.evaluator import evaluate_rpg_bundle
from rpg_backend.research_runtime.memory import project_story_guide_memory, reduce_memory_events

__all__ = [
    "RpgEvaluationBundleV1",
    "RpgEvaluationReportV1",
    "RpgMemoryEventV1",
    "RpgMemorySnapshotV1",
    "evaluate_rpg_bundle",
    "project_story_guide_memory",
    "reduce_memory_events",
]
