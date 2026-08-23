from __future__ import annotations

from collections.abc import Iterable

from rpg_backend.narrative.contracts import (
    GameplayChip,
    NarrativeSession,
    NarrativeTemplate,
    NPCPulse,
    PlayerRole,
    StoryBrief,
    StoryGuideCompressedContext,
    StoryMessage,
)
from rpg_backend.research_runtime.contracts import (
    RpgEvaluationBundleV1,
    RpgEvaluationScenarioV1,
    RpgMemoryEventV1,
    RpgStateDeltaV1,
    RpgTurnObservationV1,
)
from rpg_backend.research_runtime.memory import reduce_memory_events, story_guide_memory_events


class SessionEvaluationNotReadyError(ValueError):
    """Raised only when a session has no completed player/world turn."""


def _clean(value: str, limit: int) -> str:
    return " ".join(value.split())[:limit].strip()


def _active_role(template: NarrativeTemplate, session: NarrativeSession) -> PlayerRole | None:
    if not template.player_role_options:
        return None
    if session.selected_player_role_id:
        for role in template.player_role_options:
            if role.role_id == session.selected_player_role_id:
                return role
    return template.player_role_options[0]


def _objective(
    template: NarrativeTemplate,
    session: NarrativeSession,
    story_brief: StoryBrief | None,
) -> str:
    if template.player_goals:
        return _clean(template.player_goals[0].goal, 600)
    role = _active_role(template, session)
    if role is not None:
        return _clean(role.hidden_objective, 600)
    if story_brief is not None:
        return _clean(story_brief.story_kernel or story_brief.premise_summary, 600)
    return _clean(template.seed or template.title, 600)


def _append_event(
    events: list[RpgMemoryEventV1],
    *,
    turn_index: int,
    kind: str,
    value: str = "",
    key: str = "",
    namespace: str = "story",
    entity_id: str | None = None,
    entity_name: str | None = None,
    state: dict[str, str] | None = None,
) -> None:
    events.append(
        RpgMemoryEventV1(
            event_id=f"session_{turn_index}_{len(events) + 1}",
            turn_index=turn_index,
            kind=kind,
            value=_clean(value, 600),
            key=_clean(key, 80),
            namespace=_clean(namespace, 40),
            entity_id=_clean(entity_id, 80) if entity_id else None,
            entity_name=_clean(entity_name, 120) if entity_name else None,
            state={_clean(k, 80): _clean(v, 600) for k, v in (state or {}).items()},
            source="runtime",
        )
    )


def _seed_memory_events(
    *,
    template: NarrativeTemplate,
    session: NarrativeSession,
    story_brief: StoryBrief | None,
    story_guide_context: StoryGuideCompressedContext | None,
) -> list[RpgMemoryEventV1]:
    events = (
        story_guide_memory_events(story_guide_context, turn_index=0)
        if story_guide_context is not None
        else []
    )
    _append_event(events, turn_index=0, kind="objective_set", value=_objective(template, session, story_brief))
    if story_brief is not None:
        for key, value in (
            ("premise", story_brief.premise_summary),
            ("player_role", story_brief.player_role or ""),
            ("tone", story_brief.genre_tone),
            ("story_kernel", story_brief.story_kernel),
        ):
            if value:
                _append_event(events, turn_index=0, kind="fact_asserted", key=key, value=value)
        for index, constraint in enumerate(story_brief.preserved_constraints[:8]):
            _append_event(
                events,
                turn_index=0,
                kind="fact_asserted",
                namespace="boundary",
                key=f"constraint_{index + 1}",
                value=constraint,
            )
    role = _active_role(template, session)
    if role is not None:
        _append_event(events, turn_index=0, kind="fact_asserted", key="play_role", value=role.label)
    return events


def _pulse_delta(pulse: NPCPulse, names: dict[str, str]) -> RpgStateDeltaV1:
    kind = {
        "warmer": "increase",
        "colder": "decrease",
        "steady": "set",
        "wary": "shift",
        "broken": "decrease",
    }[pulse.shift]
    name = names.get(pulse.npc_id, pulse.npc_id)
    return RpgStateDeltaV1(
        target=pulse.npc_id,
        kind=kind,
        label=_clean(f"{name}: {pulse.shift}", 160),
        value=_clean(pulse.state, 120),
        evidence=_clean(pulse.reason or pulse.state, 300),
    )


def _chip_delta(chip: GameplayChip, *, target: str = "scene") -> RpgStateDeltaV1:
    kind = {
        "gain": "increase",
        "cost": "decrease",
        "unlock": "unlock",
        "shift": "shift",
    }[chip.tone]
    return RpgStateDeltaV1(
        target=target,
        kind=kind,
        label=_clean(chip.label, 160),
        evidence=_clean(chip.detail or chip.label, 300),
    )


def _dedupe(values: Iterable[str], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean(value, 160)
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def build_session_evaluation_bundle(
    *,
    template: NarrativeTemplate,
    session: NarrativeSession,
    messages: list[StoryMessage],
    story_brief: StoryBrief | None = None,
    story_guide_context: StoryGuideCompressedContext | None = None,
) -> RpgEvaluationBundleV1:
    """Export one persisted Tiny Stories session into the portable contract.

    The adapter uses accepted structured metadata when present and conservative
    persisted-state derivation otherwise. It never invokes an LLM.
    """

    ordered = sorted(messages, key=lambda message: message.ord)
    player_messages = [message for message in ordered if message.role == "player"]
    names = {member.character_id: member.display_name for member in template.cast}
    objective = _objective(template, session, story_brief)
    memory_events = _seed_memory_events(
        template=template,
        session=session,
        story_brief=story_brief,
        story_guide_context=story_guide_context,
    )
    observations: list[RpgTurnObservationV1] = []

    for turn_index, player in enumerate(player_messages, start=1):
        narrator = next(
            (
                message
                for message in ordered
                if message.role == "narrator" and message.ord > player.ord
            ),
            None,
        )
        if narrator is None:
            continue

        _append_event(
            memory_events,
            turn_index=turn_index,
            kind="player_action",
            value=player.content,
            namespace="episode",
        )
        _append_event(
            memory_events,
            turn_index=turn_index,
            kind="world_consequence",
            value=narrator.content,
            namespace="episode",
        )

        state_deltas = [_pulse_delta(pulse, names) for pulse in narrator.npc_pulse]
        referenced_entities = [pulse.npc_id for pulse in narrator.npc_pulse if pulse.npc_id in names]
        for pulse in narrator.npc_pulse:
            _append_event(
                memory_events,
                turn_index=turn_index,
                kind="entity_changed",
                namespace="entity",
                entity_id=pulse.npc_id,
                entity_name=names.get(pulse.npc_id, pulse.npc_id),
                state={"state": pulse.state, "shift": pulse.shift},
            )

        inventory_added = narrator.inventory_delta.added if narrator.inventory_delta else []
        inventory_removed = narrator.inventory_delta.removed if narrator.inventory_delta else []
        for item in inventory_added:
            state_deltas.append(
                RpgStateDeltaV1(
                    target="inventory",
                    kind="unlock",
                    label=_clean(f"Evidence: {item}", 160),
                    evidence=_clean(narrator.inventory_delta.reason if narrator.inventory_delta else item, 300),
                )
            )
            _append_event(memory_events, turn_index=turn_index, kind="clue_unlocked", value=item)
        for item in inventory_removed:
            state_deltas.append(
                RpgStateDeltaV1(
                    target="inventory",
                    kind="spend",
                    label=_clean(f"Spent: {item}", 160),
                    evidence=_clean(narrator.inventory_delta.reason if narrator.inventory_delta else item, 300),
                )
            )

        metadata = narrator.gameplay_metadata
        clue_unlocks = list(inventory_added)
        opportunity_unlocks: list[str] = []
        if metadata is not None:
            state_deltas.extend(_chip_delta(chip) for chip in metadata.state_deltas)
            if metadata.motive_effect is not None:
                state_deltas.append(_chip_delta(metadata.motive_effect, target="motive"))
            clue_unlocks.extend(chip.label for chip in metadata.clue_unlocks)
            opportunity_unlocks.extend(chip.label for chip in metadata.opportunity_unlocks)
            state_deltas.extend(_chip_delta(chip, target="clue") for chip in metadata.clue_unlocks)
            state_deltas.extend(
                _chip_delta(chip, target="opportunity") for chip in metadata.opportunity_unlocks
            )
            for clue in metadata.clue_unlocks:
                _append_event(memory_events, turn_index=turn_index, kind="clue_unlocked", value=clue.label)

        unique_deltas: list[RpgStateDeltaV1] = []
        delta_labels: set[str] = set()
        for delta in state_deltas:
            key = delta.label.casefold()
            if key not in delta_labels:
                delta_labels.add(key)
                unique_deltas.append(delta)

        terminal = bool(session.ending_label) and turn_index == len(player_messages)
        progress = 1.0 if terminal else min(0.95, turn_index / max(1, session.turn_budget))
        observations.append(
            RpgTurnObservationV1(
                turn_index=turn_index,
                player_action=_clean(player.content, 800),
                world_response=_clean(narrator.content, 2400),
                options=[_clean(option.label, 800) for option in narrator.options[:6]],
                state_deltas=unique_deltas[:8],
                clue_unlocks=_dedupe(clue_unlocks, limit=4),
                opportunity_unlocks=_dedupe(opportunity_unlocks, limit=4),
                referenced_entity_ids=_dedupe(referenced_entities, limit=12),
                terminal=terminal,
                objective_progress=progress,
                progress_basis="turn_budget_proxy",
                memory=reduce_memory_events(session.session_id, memory_events),
            )
        )

    if not observations:
        raise SessionEvaluationNotReadyError(
            "Session has no completed player/narrator turn to evaluate."
        )

    boundaries: list[str] = []
    if story_guide_context is not None:
        boundaries.extend(story_guide_context.constraints)
    if story_brief is not None:
        boundaries.extend(story_brief.preserved_constraints)

    return RpgEvaluationBundleV1(
        run_id=session.session_id,
        system_label="Tiny Stories runtime",
        locale=template.language,
        scenario=RpgEvaluationScenarioV1(
            scenario_id=template.template_id,
            title=template.title,
            genre=story_brief.genre_tone if story_brief is not None else "interactive_rpg",
            objective=objective,
            turn_budget=session.turn_budget,
            entity_ids=[member.character_id for member in template.cast],
            boundaries=_dedupe(boundaries, limit=16),
        ),
        turns=observations,
    )
