from __future__ import annotations

from rpg_backend.narrative.contracts import StoryGuideCompressedContext
from rpg_backend.research_runtime.contracts import (
    RpgEvaluationBundleV1,
    RpgEvaluationScenarioV1,
    RpgMemoryEventV1,
    RpgStateDeltaV1,
    RpgTurnObservationV1,
)
from rpg_backend.research_runtime.evaluator import evaluate_rpg_bundle
from rpg_backend.research_runtime.memory import project_story_guide_memory, reduce_memory_events


def _event(event_id: str, turn_index: int, kind: str, **kwargs: object) -> RpgMemoryEventV1:
    return RpgMemoryEventV1(event_id=event_id, turn_index=turn_index, kind=kind, **kwargs)


def test_memory_reducer_supersedes_corrections_and_bounds_recent_events() -> None:
    events = [
        _event("e0", 0, "objective_set", value="Find the singer before air."),
        _event("e1", 1, "fact_asserted", key="player_role", value="Backup dancer", source="user"),
        _event("e2", 2, "fact_corrected", key="player_role", value="Publicist", source="user"),
        _event("e3", 2, "non_story_input", value="who are you", source="user"),
        *[
            _event(f"e{index + 4}", index + 3, "world_consequence", value=f"Beat {index}")
            for index in range(12)
        ],
    ]

    snapshot = reduce_memory_events("run-1", events)

    assert snapshot.objective == "Find the singer before air."
    assert [(fact.key, fact.value) for fact in snapshot.active_facts] == [("player_role", "Publicist")]
    assert snapshot.superseded_facts[0].value == "Backup dancer"
    assert snapshot.superseded_facts[0].superseded_by == snapshot.active_facts[0].fact_id
    assert snapshot.diagnostics.non_story_event_count == 1
    assert len(snapshot.recent_events) == 8
    assert snapshot.diagnostics.dropped_recent_event_count > 0


def test_story_guide_projection_keeps_non_story_intent_out_of_active_facts() -> None:
    context = StoryGuideCompressedContext(
        scene_summary="Awards livestream with the singer missing.",
        player_role="Publicist",
        cast_or_factions=["Producer Han", "Sponsor team"],
        pressure="Three minutes until air.",
        constraints=["No violence"],
        tone="high_drama",
        open_questions=["Who last saw the singer?"],
        confirmed_facts=["Awards livestream"],
        rejected_or_changed_facts=["superseded player_role: Backup dancer"],
        non_story_user_intents=["meta_assistant: who are you"],
        last_user_intent="story_seed",
        readiness_score=0.67,
        planner_skill="cast_focus",
        planner_job="clarify the person closest to the pressure",
    )

    snapshot = project_story_guide_memory(context, run_id="guide-1", turn_index=4)

    assert any(fact.key == "player_role" and fact.value == "Publicist" for fact in snapshot.active_facts)
    assert any(fact.value == "Backup dancer" for fact in snapshot.superseded_facts)
    assert all("who are you" not in fact.value for fact in snapshot.active_facts)
    assert snapshot.diagnostics.non_story_event_count == 1
    assert snapshot.open_threads == ["Who last saw the singer?"]


def test_portable_evaluator_scores_specific_stateful_run() -> None:
    events = [
        _event("objective", 0, "objective_set", value="Find the singer before air."),
        _event("role", 0, "fact_asserted", key="player_role", value="Publicist"),
        _event("clue", 1, "clue_unlocked", value="Green-room badge"),
    ]
    memory_one = reduce_memory_events("run-eval", events)
    memory_two = reduce_memory_events(
        "run-eval",
        [
            *events,
            _event("pressure", 2, "fact_asserted", key="pressure", value="Sponsor feed frozen"),
        ],
    )
    bundle = RpgEvaluationBundleV1(
        run_id="run-eval",
        system_label="Candidate runtime",
        scenario=RpgEvaluationScenarioV1(
            scenario_id="awards",
            title="Awards livestream",
            objective="Find the singer before air.",
            entity_ids=["producer_han", "lena"],
        ),
        turns=[
            RpgTurnObservationV1(
                turn_index=1,
                player_action="Freeze the sponsor feed and show Lena the badge.",
                world_response="Lena verifies the badge while Producer Han loses control of the room.",
                options=["Question Producer Han", "Check the corridor", "Protect the witness"],
                state_deltas=[
                    RpgStateDeltaV1(
                        target="lena",
                        kind="increase",
                        label="Lena trust +1",
                        evidence="She verifies the badge.",
                    )
                ],
                clue_unlocks=["Green-room badge"],
                referenced_entity_ids=["producer_han", "lena"],
                objective_progress=0.35,
                memory=memory_one,
            ),
            RpgTurnObservationV1(
                turn_index=2,
                player_action="Use the badge log to confront Producer Han.",
                world_response="The log exposes a corridor handoff and narrows the search.",
                options=["Search the corridor", "Ask Lena for cover", "Call the stage manager"],
                state_deltas=[
                    RpgStateDeltaV1(
                        target="objective",
                        kind="increase",
                        label="Search narrowed",
                        evidence="The badge log identifies the corridor.",
                    )
                ],
                opportunity_unlocks=["Corridor search"],
                referenced_entity_ids=["producer_han", "lena"],
                objective_progress=0.9,
                memory=memory_two,
            ),
        ],
    )

    report = evaluate_rpg_bundle(bundle)

    assert report.status == "pass"
    assert report.score >= 80
    assert len(report.criteria) == 8
    assert all(item.status == "pass" for item in report.criteria)


def test_terminal_options_do_not_overcount_choice_diversity() -> None:
    memory = reduce_memory_events(
        "terminal-options",
        [_event("objective", 0, "objective_set", value="Resolve the gala reveal.")],
    )
    bundle = RpgEvaluationBundleV1(
        run_id="terminal-options",
        system_label="Terminal option compatibility",
        scenario=RpgEvaluationScenarioV1(
            scenario_id="gala",
            title="Gala",
            objective="Resolve the gala reveal.",
        ),
        turns=[
            RpgTurnObservationV1(
                turn_index=1,
                player_action="Show the timestamp.",
                world_response="The room accepts the evidence.",
                options=["Question the sponsor", "Protect the singer"],
                state_deltas=[RpgStateDeltaV1(target="pressure", kind="decrease", label="Pressure eased")],
                objective_progress=0.5,
                memory=memory,
            ),
            RpgTurnObservationV1(
                turn_index=2,
                player_action="Close the broadcast.",
                world_response="The gala ends with the truth on record.",
                options=["Replay", "Go home"],
                terminal=True,
                state_deltas=[RpgStateDeltaV1(target="objective", kind="increase", label="Truth recorded")],
                objective_progress=1.0,
                memory=memory,
            ),
        ],
    )

    report = evaluate_rpg_bundle(bundle)
    choice = next(item for item in report.criteria if item.criterion == "choice_diversity")

    assert choice.score == 100
    assert choice.evidence == ["1 distinct action sets across 1 non-terminal turns."]


def test_portable_evaluator_warns_for_prose_only_repeated_choices() -> None:
    memory = reduce_memory_events(
        "weak-run",
        [_event("objective", 0, "objective_set", value="Escape the tower.")],
    )
    repeated = ["Wait", "Wait"]
    bundle = RpgEvaluationBundleV1(
        run_id="weak-run",
        system_label="Prose-only baseline",
        scenario=RpgEvaluationScenarioV1(
            scenario_id="tower",
            title="Tower",
            objective="Escape the tower.",
        ),
        turns=[
            RpgTurnObservationV1(
                turn_index=1,
                player_action="Wait.",
                world_response="The room remains tense.",
                options=repeated,
                objective_progress=0.0,
                memory=memory,
            )
        ],
    )

    report = evaluate_rpg_bundle(bundle)
    by_name = {item.criterion: item for item in report.criteria}

    assert report.status != "pass"
    assert by_name["consequence_visibility"].status == "fail"
    assert by_name["player_agency"].status == "fail"
    assert by_name["trajectory_progress"].status == "fail"
