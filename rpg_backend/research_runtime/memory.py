from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from rpg_backend.narrative.contracts import StoryGuideCompressedContext
from rpg_backend.research_runtime.contracts import (
    RpgMemoryDiagnosticsV1,
    RpgMemoryEntityV1,
    RpgMemoryEventV1,
    RpgMemoryFactV1,
    RpgMemorySnapshotV1,
)


def _fact_id(namespace: str, key: str, value: str, turn_index: int) -> str:
    digest = hashlib.sha1(f"{namespace}:{key}:{value}:{turn_index}".encode("utf-8")).hexdigest()[:12]
    return f"fact_{digest}"


def _clean(value: str, *, limit: int) -> str:
    return " ".join(value.split())[:limit].strip()


def reduce_memory_events(
    run_id: str,
    events: Iterable[RpgMemoryEventV1],
    *,
    max_active_facts: int = 24,
    max_recent_events: int = 8,
) -> RpgMemorySnapshotV1:
    """Reduce portable events into a bounded, auditable memory snapshot."""

    ordered = sorted(events, key=lambda event: (event.turn_index, event.event_id))
    objective = ""
    active: dict[tuple[str, str], RpgMemoryFactV1] = {}
    superseded: list[RpgMemoryFactV1] = []
    open_threads: list[str] = []
    entities: dict[str, RpgMemoryEntityV1] = {}
    recent: list[str] = []
    non_story_count = 0

    for event in ordered:
        if event.kind == "objective_set":
            objective = _clean(event.value, limit=600)
            recent.append(f"Objective: {objective}")
            continue
        if event.kind in {"fact_asserted", "fact_corrected"}:
            key = _clean(event.key, limit=80)
            value = _clean(event.value, limit=600)
            if not key or not value:
                continue
            lookup = (event.namespace, key)
            fact_id = _fact_id(event.namespace, key, value, event.turn_index)
            previous = active.get(lookup)
            if previous and previous.value.casefold() != value.casefold():
                superseded.append(previous.model_copy(update={"status": "superseded", "superseded_by": fact_id}))
            active[lookup] = RpgMemoryFactV1(
                fact_id=fact_id,
                namespace=event.namespace,
                key=key,
                value=value,
                source_turn=event.turn_index,
                source=event.source,
                confidence=event.confidence,
            )
            recent.append(f"{key}: {value}")
            continue
        if event.kind == "non_story_input":
            non_story_count += 1
            recent.append(f"Conversation only: {_clean(event.value, limit=180)}")
            continue
        if event.kind == "thread_opened":
            thread = _clean(event.value or event.key, limit=180)
            if thread and thread.casefold() not in {item.casefold() for item in open_threads}:
                open_threads.append(thread)
            continue
        if event.kind == "thread_resolved":
            target = _clean(event.value or event.key, limit=180).casefold()
            open_threads = [item for item in open_threads if item.casefold() != target]
            continue
        if event.kind == "entity_changed" and event.entity_id:
            current = entities.get(event.entity_id)
            state = dict(current.state) if current else {}
            state.update({_clean(key, limit=60): _clean(value, limit=160) for key, value in event.state.items()})
            entities[event.entity_id] = RpgMemoryEntityV1(
                entity_id=event.entity_id,
                name=event.entity_name or (current.name if current else event.entity_id),
                state=state,
                last_updated_turn=event.turn_index,
            )
            recent.append(f"{entities[event.entity_id].name}: {', '.join(state.values())}")
            continue
        label = {
            "player_action": "Player",
            "world_consequence": "World",
            "clue_unlocked": "Clue",
        }.get(event.kind, "Event")
        recent.append(f"{label}: {_clean(event.value, limit=240)}")

    active_facts = sorted(active.values(), key=lambda fact: (fact.source_turn, fact.fact_id))[-max_active_facts:]
    superseded_facts = superseded[-32:]
    dropped = max(0, len(recent) - max_recent_events)
    recent_events = recent[-max_recent_events:]
    last_turn = max((event.turn_index for event in ordered), default=0)
    summary_parts = [objective] if objective else []
    summary_parts.extend(f"{fact.key}: {fact.value}" for fact in active_facts[-6:])
    if open_threads:
        summary_parts.append(f"Open: {'; '.join(open_threads[:4])}")
    return RpgMemorySnapshotV1(
        run_id=run_id,
        turn_index=last_turn,
        objective=objective,
        active_facts=active_facts,
        superseded_facts=superseded_facts,
        open_threads=open_threads[-16:],
        entities=sorted(entities.values(), key=lambda entity: entity.entity_id),
        recent_events=recent_events,
        episodic_summary=_clean(" | ".join(summary_parts), limit=1200),
        diagnostics=RpgMemoryDiagnosticsV1(
            event_count=len(ordered),
            active_fact_count=len(active_facts),
            superseded_fact_count=len(superseded_facts),
            non_story_event_count=non_story_count,
            dropped_recent_event_count=dropped,
            last_compacted_turn=last_turn,
        ),
    )


def project_story_guide_memory(
    context: StoryGuideCompressedContext,
    *,
    run_id: str,
    turn_index: int,
) -> RpgMemorySnapshotV1:
    """Project the existing Story Butler memory into the portable contract."""

    events: list[RpgMemoryEventV1] = []
    sequence = 0

    def add(kind: str, *, key: str = "", value: str = "", namespace: str = "story") -> None:
        nonlocal sequence
        sequence += 1
        events.append(
            RpgMemoryEventV1(
                event_id=f"guide_{turn_index}_{sequence}",
                turn_index=turn_index,
                kind=kind,
                namespace=namespace,
                key=key,
                value=value,
                source="runtime",
            )
        )

    for key, value in (
        ("scene_summary", context.scene_summary),
        ("player_role", context.player_role),
        ("pressure", context.pressure),
        ("tone", context.tone),
    ):
        if value:
            add("fact_asserted", key=key, value=value)
    for index, value in enumerate(context.cast_or_factions):
        add("fact_asserted", key=f"cast_{index + 1}", value=value, namespace="cast")
    for index, value in enumerate(context.constraints):
        add("fact_asserted", key=f"constraint_{index + 1}", value=value, namespace="boundary")
    for item in context.rejected_or_changed_facts:
        match = re.match(r"superseded\s+([^:]+):\s*(.+)", item, re.I)
        if not match:
            continue
        key, value = match.groups()
        add("fact_asserted", key=key.strip(), value=value.strip(), namespace="superseded")
    for item in context.non_story_user_intents:
        add("non_story_input", value=item, namespace="conversation")
    for item in context.open_questions:
        add("thread_opened", value=item, namespace="question")
    if context.planner_job:
        add("world_consequence", value=f"Planner focus: {context.planner_job}", namespace="planner")

    snapshot = reduce_memory_events(run_id, events)
    superseded = [
        fact.model_copy(update={"status": "superseded"})
        for fact in snapshot.active_facts
        if fact.namespace == "superseded"
    ]
    active = [fact for fact in snapshot.active_facts if fact.namespace != "superseded"]
    return snapshot.model_copy(
        update={
            "turn_index": turn_index,
            "objective": context.scene_summary,
            "active_facts": active,
            "superseded_facts": [*snapshot.superseded_facts, *superseded][-32:],
            "diagnostics": snapshot.diagnostics.model_copy(
                update={
                    "active_fact_count": len(active),
                    "superseded_fact_count": len(snapshot.superseded_facts) + len(superseded),
                    "last_compacted_turn": turn_index,
                }
            ),
        }
    )
