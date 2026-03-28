from __future__ import annotations

from typing import Literal
from typing_extensions import NotRequired, TypedDict


StageName = Literal["story_frame", "cast_overview", "cast_member", "beat_plan", "beat_runtime_shard", "route_affordance", "ending", "gameplay_semantics"]
SourceName = Literal["generated", "gleaned", "default", "compiled"]
OutcomeName = Literal["accepted", "repaired", "rejected", "fallback"]


class QualityTraceRecord(TypedDict):
    stage: StageName
    source: SourceName
    outcome: OutcomeName
    reasons: list[str]
    slot_index: NotRequired[int]
    subject: NotRequired[str]
    snapshot_id: NotRequired[str]
    snapshot_stage: NotRequired[str]
    elapsed_ms: NotRequired[int]


def append_quality_trace(
    trace: list[QualityTraceRecord] | None,
    *,
    stage: StageName,
    source: SourceName,
    outcome: OutcomeName,
    reasons: list[str] | None = None,
    slot_index: int | None = None,
    subject: str | None = None,
    snapshot_id: str | None = None,
    snapshot_stage: str | None = None,
    elapsed_ms: int | None = None,
) -> list[QualityTraceRecord]:
    updated = list(trace or [])
    record = QualityTraceRecord(
        stage=stage,
        source=source,
        outcome=outcome,
        reasons=list(reasons or []),
    )
    if slot_index is not None:
        record["slot_index"] = slot_index
    if subject is not None:
        record["subject"] = subject
    if snapshot_id is not None:
        record["snapshot_id"] = snapshot_id
    if snapshot_stage is not None:
        record["snapshot_stage"] = snapshot_stage
    if elapsed_ms is not None:
        record["elapsed_ms"] = elapsed_ms
    updated.append(record)
    return updated
