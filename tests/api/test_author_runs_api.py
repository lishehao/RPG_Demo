from __future__ import annotations

import asyncio

import rpg_backend.application.author_runs.workflow_nodes as author_workflow_nodes_module
from rpg_backend.application.author_runs.service import author_workflow_service
from rpg_backend.application.author_runs.workflow_vocabulary import (
    AuthorWorkflowArtifactType,
    AuthorWorkflowErrorCode,
    AuthorWorkflowEventType,
    AuthorWorkflowNode,
    AuthorWorkflowStatus,
)
from rpg_backend.domain.constants import GLOBAL_CLARIFY_MOVE_ID, GLOBAL_HELP_ME_PROGRESS_MOVE_ID, GLOBAL_LOOK_MOVE_ID
from rpg_backend.domain.linter import LintReport
from rpg_backend.generator.author_workflow_errors import PromptCompileError
from rpg_backend.generator.author_workflow_models import (
    BeatDraft,
    BeatScenePlan,
    GeneratedBeatScene,
    StoryOverview,
)
from rpg_backend.generator.author_workflow_policy import AuthorWorkflowPolicy
from tests.helpers.route_paths import (
    author_run_events_path,
    author_run_path,
    author_runs_path,
    author_story_path,
    author_story_runs_path,
    author_stories_path,
    story_publish_path,
)


def _sample_overview() -> StoryOverview:
    return StoryOverview.model_validate(
        {
            "title": "Signal Rift Protocol",
            "premise": "A city control signal fractures during peak load, forcing an improvised response team into a contested core.",
            "tone": "tense but pragmatic techno-thriller",
            "stakes": "If containment fails, the district grid collapses before dawn.",
            "target_minutes": 10,
            "npc_count": 4,
            "ending_shape": "pyrrhic",
            "ending_shape_note": "The system can be stabilized, but only at a cost that leaves the command structure visibly diminished by dawn.",
            "npc_roster": [
                {
                    "name": "Mara",
                    "role": "field engineer",
                    "motivation": "prevent systemic collapse",
                    "red_line": "Never cut hospital access to stabilize industry.",
                    "conflict_tags": ["anti_noise"],
                    "pressure_signature": "Keeps snapping the team back to exact readings whenever panic turns sloppy.",
                },
                {
                    "name": "Rook",
                    "role": "security lead",
                    "motivation": "protect civilians",
                    "red_line": "No civilian corridor can be abandoned for pace.",
                    "conflict_tags": ["anti_speed"],
                    "pressure_signature": "Reads every rushed shortcut through the lens of preventable civilian harm.",
                },
                {
                    "name": "Sera",
                    "role": "operations analyst",
                    "motivation": "preserve evidence",
                    "red_line": "No telemetry wipe even under command pressure.",
                    "conflict_tags": ["anti_noise"],
                    "pressure_signature": "Refuses to let the crisis erase the forensic trail that explains who failed first.",
                },
                {
                    "name": "Director Vale",
                    "role": "command authority",
                    "motivation": "retain control",
                    "red_line": "Public command legitimacy cannot collapse.",
                    "conflict_tags": ["anti_resource_burn"],
                    "pressure_signature": "Treats every expensive concession as a direct threat to command legitimacy.",
                },
            ],
            "move_bias": ["technical", "investigate", "social"],
            "move_bias_note": "Most progress should come from diagnosis, questioning, and leverage rather than brute escalation.",
            "scene_constraints": [
                "Open with concrete damage and immediate objective framing.",
                "Escalate pressure with checkpoints and contradictory orders.",
                "Force a costly compromise to retain momentum.",
                "Converge to final resolution with one decisive tradeoff.",
            ],
        }
    )


def _make_beat_draft(*, overview: StoryOverview, blueprint, beat_index: int) -> BeatDraft:
    roster = [npc.name for npc in overview.npc_roster]
    npc_pair = [roster[beat_index % len(roster)], roster[(beat_index + 1) % len(roster)]]
    move_ids = [
        f"{blueprint['beat_id']}.move_fast",
        f"{blueprint['beat_id']}.move_steady",
        f"{blueprint['beat_id']}.move_safe",
    ]
    moves = [
        {
            "id": move_ids[0],
            "label": "Move Fast",
            "strategy_style": "fast_dirty",
            "intents": ["rush ahead"],
            "synonyms": ["rush"],
            "args_schema": {},
            "resolution_policy": "prefer_success",
            "outcomes": [
                {
                    "id": f"{move_ids[0]}.success",
                    "result": "success",
                    "preconditions": [],
                    "effects": [{"type": "add_event", "key": None, "value": blueprint["required_event"]}],
                    "next_scene_id": None,
                    "narration_slots": {
                        "npc_reaction": "They react immediately.",
                        "world_shift": "The tempo spikes.",
                        "clue_delta": "You gain a useful clue.",
                        "cost_delta": "Noise increases.",
                        "next_hook": "A harder choice emerges.",
                    },
                },
                {
                    "id": f"{move_ids[0]}.fail_forward",
                    "result": "fail_forward",
                    "preconditions": [],
                    "effects": [{"type": "add_event", "key": None, "value": blueprint["required_event"]}],
                    "next_scene_id": None,
                    "narration_slots": {
                        "npc_reaction": "The team resists the rush.",
                        "world_shift": "The pressure worsens.",
                        "clue_delta": "You still learn something useful.",
                        "cost_delta": "Trust slips.",
                        "next_hook": "You must adapt quickly.",
                    },
                },
            ],
        },
        {
            "id": move_ids[1],
            "label": "Move Steady",
            "strategy_style": "steady_slow",
            "intents": ["move carefully"],
            "synonyms": ["steady"],
            "args_schema": {},
            "resolution_policy": "prefer_success",
            "outcomes": [
                {
                    "id": f"{move_ids[1]}.success",
                    "result": "success",
                    "preconditions": [],
                    "effects": [],
                    "next_scene_id": None,
                    "narration_slots": {
                        "npc_reaction": "They nod and slow down.",
                        "world_shift": "The scene stabilizes.",
                        "clue_delta": "A pattern becomes clear.",
                        "cost_delta": "Time pressure grows.",
                        "next_hook": "A new route opens.",
                    },
                },
                {
                    "id": f"{move_ids[1]}.fail_forward",
                    "result": "fail_forward",
                    "preconditions": [],
                    "effects": [],
                    "next_scene_id": None,
                    "narration_slots": {
                        "npc_reaction": "They hesitate but continue.",
                        "world_shift": "The scene keeps moving.",
                        "clue_delta": "The clue is partial.",
                        "cost_delta": "Momentum slips.",
                        "next_hook": "You need a firmer decision.",
                    },
                },
            ],
        },
        {
            "id": move_ids[2],
            "label": "Move Safe",
            "strategy_style": "political_safe_resource_heavy",
            "intents": ["take the careful official route"],
            "synonyms": ["official"],
            "args_schema": {},
            "resolution_policy": "prefer_success",
            "outcomes": [
                {
                    "id": f"{move_ids[2]}.success",
                    "result": "success",
                    "preconditions": [],
                    "effects": [],
                    "next_scene_id": None,
                    "narration_slots": {
                        "npc_reaction": "They accept the political cover.",
                        "world_shift": "Resources drain to buy safety.",
                        "clue_delta": "You gain institutional backing.",
                        "cost_delta": "Reserves thin out.",
                        "next_hook": "The safe path creates a later bill.",
                    },
                },
                {
                    "id": f"{move_ids[2]}.fail_forward",
                    "result": "fail_forward",
                    "preconditions": [],
                    "effects": [],
                    "next_scene_id": None,
                    "narration_slots": {
                        "npc_reaction": "The safe route still costs heavily.",
                        "world_shift": "The system absorbs the delay badly.",
                        "clue_delta": "You preserve legitimacy but lose slack.",
                        "cost_delta": "Resources burn.",
                        "next_hook": "The next beat inherits the cost.",
                    },
                },
            ],
        },
    ]
    return BeatDraft.model_validate(
        {
            "beat_id": blueprint["beat_id"],
            "title": blueprint["title"],
            "objective": blueprint["objective"],
            "conflict": blueprint["conflict"],
            "required_event": blueprint["required_event"],
            "entry_scene_id": blueprint["entry_scene_id"],
            "present_npcs": npc_pair,
            "events_produced": [blueprint["required_event"]],
            "scenes": [
                {
                    "id": blueprint["entry_scene_id"],
                    "beat_id": blueprint["beat_id"],
                    "scene_seed": f"{blueprint['scene_intent']} Opening move.",
                    "present_npcs": npc_pair,
                    "enabled_moves": move_ids,
                    "always_available_moves": [
                        GLOBAL_CLARIFY_MOVE_ID,
                        GLOBAL_LOOK_MOVE_ID,
                        GLOBAL_HELP_ME_PROGRESS_MOVE_ID,
                    ],
                    "exit_conditions": [
                        {
                            "id": f"{blueprint['beat_id']}.advance",
                            "condition_kind": "event_present",
                            "key": blueprint["required_event"],
                            "next_scene_id": f"{blueprint['beat_id']}.sc2",
                            "end_story": False,
                        }
                    ],
                    "is_terminal": False,
                },
                {
                    "id": f"{blueprint['beat_id']}.sc2",
                    "beat_id": blueprint["beat_id"],
                    "scene_seed": f"{blueprint['scene_intent']} Consequence frame.",
                    "present_npcs": npc_pair,
                    "enabled_moves": move_ids,
                    "always_available_moves": [
                        GLOBAL_CLARIFY_MOVE_ID,
                        GLOBAL_LOOK_MOVE_ID,
                        GLOBAL_HELP_ME_PROGRESS_MOVE_ID,
                    ],
                    "exit_conditions": [],
                    "is_terminal": False,
                },
            ],
            "moves": moves,
        }
    )


def _make_scene_plan(*, blueprint: dict) -> BeatScenePlan:
    beat_id = str(blueprint["beat_id"])
    return BeatScenePlan.model_validate(
        {
            "beat_id": beat_id,
            "scenes": [
                {
                    "scene_id": f"{beat_id}.sc1",
                    "purpose": "Create immediate operational pressure.",
                    "pressure": "Telemetry conflict vs command urgency.",
                    "handoff_intent": "Force a visible compromise by scene end.",
                    "present_npcs": ["Mara", "Rook"],
                    "is_terminal": False,
                    "transition_style": "escalate",
                },
                {
                    "scene_id": f"{beat_id}.sc2",
                    "purpose": "Cash pressure into required event progress.",
                    "pressure": "Resources and legitimacy can no longer both be preserved.",
                    "handoff_intent": "Close the beat with concrete state change.",
                    "present_npcs": ["Mara", "Director Vale"],
                    "is_terminal": True,
                    "transition_style": "converge",
                },
            ],
        }
    )


def _make_generated_scene(
    *,
    blueprint: dict,
    beat_index: int,
    scene_index: int,
    invalid_global_moves: bool = False,
) -> GeneratedBeatScene:
    draft = _make_beat_draft(
        overview=_sample_overview(),
        blueprint=blueprint,
        beat_index=beat_index,
    )
    source_scene = draft.scenes[scene_index]
    present_npcs = list(source_scene.present_npcs)
    if invalid_global_moves:
        present_npcs.append("Unknown NPC")
    local_moves = []
    for move in draft.moves:
        outcomes_by_result = {outcome.result: outcome for outcome in move.outcomes}
        fallback_outcome = (
            outcomes_by_result.get("partial")
            or outcomes_by_result.get("success")
            or outcomes_by_result.get("fail_forward")
            or move.outcomes[0]
        )
        local_moves.append(
            {
                "label": move.label,
                "strategy_style": move.strategy_style,
                "intents": list(move.intents),
                "synonyms": list(move.synonyms),
                "resolution_policy": move.resolution_policy,
                "outcomes": [
                    {
                        "result": result,
                        "narration_slots": outcomes_by_result.get(result, fallback_outcome).narration_slots.model_dump(
                            mode="json"
                        ),
                    }
                    for result in ("success", "partial", "fail_forward")
                ],
            }
        )
    return GeneratedBeatScene.model_validate(
        {
            "scene_seed": source_scene.scene_seed,
            "present_npcs": present_npcs,
            "local_moves": local_moves,
            "events_produced": [blueprint["required_event"]] if scene_index == len(draft.scenes) - 1 else [],
            "transition_hint": "converge" if scene_index == len(draft.scenes) - 1 else "escalate",
        }
    )


class _FakeOverviewChain:
    async def compile(self, *, raw_brief: str, timeout_seconds: float | None = None) -> StoryOverview:
        del raw_brief, timeout_seconds
        return _sample_overview()


class _FakeBeatChain:
    async def compile_beat_scene_plan(self, *, story_id: str, overview_context: dict | object, blueprint: dict, last_accepted_beat: dict | None, prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> BeatScenePlan:
        del story_id, overview_context, last_accepted_beat, prefix_summary, author_memory, lint_feedback, timeout_seconds
        return _make_scene_plan(blueprint=blueprint)

    async def compile_scene(self, *, story_id: str, overview_context: dict | object, blueprint: dict, scene_plan_item: dict[str, object], scene_count: int, scene_index: int, prior_generated_scenes: list[dict[str, object]], prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> GeneratedBeatScene:
        del story_id, overview_context, scene_plan_item, scene_count, prior_generated_scenes, prefix_summary, author_memory, lint_feedback, timeout_seconds
        beat_index = int(str(blueprint["beat_id"])[1:]) - 1
        return _make_generated_scene(
            blueprint=blueprint,
            beat_index=beat_index,
            scene_index=scene_index,
        )


class _InlineScheduler:
    async def schedule(self, run_id: str) -> None:
        await author_workflow_service._execute_run(run_id)


def _install_fake_workflow(monkeypatch, *, policy: AuthorWorkflowPolicy | None = None) -> None:
    monkeypatch.setattr(author_workflow_service, "overview_chain_factory", _FakeOverviewChain)
    monkeypatch.setattr(author_workflow_service, "beat_chain_factory", _FakeBeatChain)
    monkeypatch.setattr(
        author_workflow_service,
        "policy_factory",
        lambda: policy or AuthorWorkflowPolicy(max_attempts=3, timeout_seconds=20.0),
    )
    monkeypatch.setattr(author_workflow_service, "scheduler", _InlineScheduler())


class _FailingBeatChain:
    async def compile_beat_scene_plan(self, *, story_id: str, overview_context: dict | object, blueprint: dict, last_accepted_beat: dict | None, prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> BeatScenePlan:
        del story_id, overview_context, last_accepted_beat, prefix_summary, author_memory, lint_feedback, timeout_seconds
        return _make_scene_plan(blueprint=blueprint)

    async def compile_scene(self, *, story_id: str, overview_context: dict | object, blueprint: dict, scene_plan_item: dict[str, object], scene_count: int, scene_index: int, prior_generated_scenes: list[dict[str, object]], prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> GeneratedBeatScene:
        del story_id, overview_context, blueprint, scene_plan_item, scene_count, scene_index, prior_generated_scenes, prefix_summary, author_memory, lint_feedback, timeout_seconds
        raise RuntimeError("beat generation exploded")


class _InvalidBeatChain:
    async def compile_beat_scene_plan(self, *, story_id: str, overview_context: dict | object, blueprint: dict, last_accepted_beat: dict | None, prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> BeatScenePlan:
        del story_id, overview_context, last_accepted_beat, prefix_summary, author_memory, lint_feedback, timeout_seconds
        return _make_scene_plan(blueprint=blueprint)

    async def compile_scene(self, *, story_id: str, overview_context: dict | object, blueprint: dict, scene_plan_item: dict[str, object], scene_count: int, scene_index: int, prior_generated_scenes: list[dict[str, object]], prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> GeneratedBeatScene:
        del story_id, overview_context, blueprint, scene_plan_item, scene_count, scene_index, prior_generated_scenes, prefix_summary, author_memory, lint_feedback, timeout_seconds
        raise PromptCompileError(
            error_code="beat_invalid",
            errors=["always_available_moves must only contain global move ids"],
            notes=["beat draft generation failed"],
        )


class _RetryingOverviewChain:
    attempts = 0

    async def compile(self, *, raw_brief: str, timeout_seconds: float | None = None) -> StoryOverview:
        del raw_brief
        _RetryingOverviewChain.attempts += 1
        if _RetryingOverviewChain.attempts == 1:
            await asyncio.sleep(float(timeout_seconds or 0.01) * 2)
        return _sample_overview()


class _RetryingBeatChain:
    attempts = 0

    async def compile_beat_scene_plan(self, *, story_id: str, overview_context: dict | object, blueprint: dict, last_accepted_beat: dict | None, prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> BeatScenePlan:
        del story_id, overview_context, last_accepted_beat, prefix_summary, author_memory, lint_feedback, timeout_seconds
        scene_plan = _make_scene_plan(blueprint=blueprint).model_dump(mode="json")
        scene_plan["scenes"] = scene_plan["scenes"][:1]
        return BeatScenePlan.model_validate(scene_plan)

    async def compile_scene(self, *, story_id: str, overview_context: dict | object, blueprint: dict, scene_plan_item: dict[str, object], scene_count: int, scene_index: int, prior_generated_scenes: list[dict[str, object]], prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> GeneratedBeatScene:
        _RetryingBeatChain.attempts += 1
        if _RetryingBeatChain.attempts < 3:
            raise PromptCompileError(
                error_code="prompt_compile_failed",
                errors=["temporary gateway failure"],
                notes=["retry in graph"],
            )
        generated = await _FakeBeatChain().compile_scene(
            story_id=story_id,
            overview_context=overview_context,
            blueprint=blueprint,
            scene_plan_item=scene_plan_item,
            scene_count=scene_count,
            scene_index=scene_index,
            prior_generated_scenes=prior_generated_scenes,
            prefix_summary=prefix_summary,
            author_memory=author_memory,
            lint_feedback=lint_feedback,
            timeout_seconds=timeout_seconds,
        )
        if int(scene_count) == 1:
            payload = generated.model_dump(mode="json")
            payload["transition_hint"] = "converge"
            return GeneratedBeatScene.model_validate(payload)
        return generated


class _BeatLintRetryChain:
    calls: list[dict[str, object]] = []
    attempts_by_beat: dict[str, int] = {}

    async def compile_beat_scene_plan(self, *, story_id: str, overview_context: dict | object, blueprint: dict, last_accepted_beat: dict | None, prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> BeatScenePlan:
        del story_id, overview_context, prefix_summary, author_memory, timeout_seconds
        beat_id = str(blueprint["beat_id"])
        attempt = self.attempts_by_beat.get(beat_id, 0) + 1
        self.attempts_by_beat[beat_id] = attempt
        self.calls.append(
            {
                "beat_id": beat_id,
                "attempt": attempt,
                "last_accepted_beat_id": (
                    str(last_accepted_beat.get("beat_id"))
                    if isinstance(last_accepted_beat, dict) and last_accepted_beat.get("beat_id")
                    else None
                ),
                "lint_feedback": list(lint_feedback or []),
            }
        )
        return _make_scene_plan(blueprint=blueprint)

    async def compile_scene(self, *, story_id: str, overview_context: dict | object, blueprint: dict, scene_plan_item: dict[str, object], scene_count: int, scene_index: int, prior_generated_scenes: list[dict[str, object]], prefix_summary: dict | object, author_memory: dict | object | None = None, lint_feedback: list[str] | None = None, timeout_seconds: float | None = None) -> GeneratedBeatScene:
        del story_id, overview_context, scene_plan_item, scene_count, prior_generated_scenes, prefix_summary, author_memory, lint_feedback, timeout_seconds
        beat_id = str(blueprint["beat_id"])
        beat_index = int(beat_id[1:]) - 1
        invalid = beat_id == "b2" and self.attempts_by_beat.get(beat_id, 0) == 1
        return _make_generated_scene(
            blueprint=blueprint,
            beat_index=beat_index,
            scene_index=scene_index,
            invalid_global_moves=invalid,
        )


def test_create_author_run_and_fetch_review_ready_story(client, monkeypatch) -> None:
    _install_fake_workflow(monkeypatch)

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."})
    assert created.status_code == 202, created.text
    body = created.json()
    run_id = body["run_id"]
    story_id = body["story_id"]

    run_response = client.get(author_run_path(run_id))
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == AuthorWorkflowStatus.REVIEW_READY, (
        run_body.get("error_code"),
        run_body.get("error_message"),
        run_body.get("current_node"),
    )
    artifact_types = {item["artifact_type"] for item in run_body["artifacts"]}
    prefix_summary_artifact = next(
        item for item in run_body["artifacts"] if item["artifact_type"] == AuthorWorkflowArtifactType.PREFIX_SUMMARY
    )
    assert "completed_beats" in prefix_summary_artifact["payload"]
    assert "text" not in prefix_summary_artifact["payload"]
    assert AuthorWorkflowArtifactType.OVERVIEW in artifact_types
    assert AuthorWorkflowArtifactType.BEAT_BLUEPRINTS in artifact_types
    assert AuthorWorkflowArtifactType.BEAT_OVERVIEW_CONTEXT in artifact_types
    assert AuthorWorkflowArtifactType.BEAT_SCENE_PLAN in artifact_types
    assert AuthorWorkflowArtifactType.GENERATED_BEAT_SCENE in artifact_types
    assert AuthorWorkflowArtifactType.CURRENT_BEAT_DRAFT in artifact_types
    assert AuthorWorkflowArtifactType.AUTHOR_MEMORY in artifact_types
    assert AuthorWorkflowArtifactType.STORY_PACK in artifact_types
    assert AuthorWorkflowArtifactType.STORY_PACK_NORMALIZATION in artifact_types
    assert AuthorWorkflowArtifactType.FINAL_LINT in artifact_types
    current_draft = next(
        item for item in run_body["artifacts"] if item["artifact_type"] == AuthorWorkflowArtifactType.CURRENT_BEAT_DRAFT
    )
    assert "scenes" in current_draft["payload"]
    assert "moves" in current_draft["payload"]
    assert sum(1 for item in run_body["artifacts"] if item["artifact_type"] == AuthorWorkflowArtifactType.ACCEPTED_BEAT_DRAFT) == 4

    events_response = client.get(author_run_events_path(run_id))
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert any(event["node_name"] == AuthorWorkflowNode.GENERATE_STORY_OVERVIEW for event in events)
    assert any(event["node_name"] == AuthorWorkflowNode.REVIEW_READY for event in events)

    story_response = client.get(author_story_path(story_id))
    assert story_response.status_code == 200
    story_body = story_response.json()
    assert story_body["latest_run"]["status"] == AuthorWorkflowStatus.REVIEW_READY
    assert story_body["draft_pack"]["title"] == _sample_overview().title

    list_response = client.get(author_stories_path())
    assert list_response.status_code == 200
    stories = list_response.json()["stories"]
    listed = next(item for item in stories if item["story_id"] == story_id)
    assert listed["latest_run_status"] == AuthorWorkflowStatus.REVIEW_READY


def test_rerun_author_story_creates_second_run(client, monkeypatch) -> None:
    _install_fake_workflow(monkeypatch)

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."}).json()
    rerun = client.post(author_story_runs_path(created["story_id"]), json={"raw_brief": "Try a sharper political angle."})
    assert rerun.status_code == 202
    rerun_body = rerun.json()
    assert rerun_body["story_id"] == created["story_id"]
    assert rerun_body["run_id"] != created["run_id"]


def test_publish_requires_review_ready_when_author_run_exists(client, monkeypatch) -> None:
    class _NoopScheduler:
        async def schedule(self, run_id: str) -> None:
            del run_id

    monkeypatch.setattr(author_workflow_service, "scheduler", _NoopScheduler())
    created = client.post(author_runs_path(), json={"raw_brief": "Generate but do not execute."})
    assert created.status_code == 202
    story_id = created.json()["story_id"]

    published = client.post(story_publish_path(story_id), json={})
    assert published.status_code == 409
    err = published.json()["error"]
    assert err["code"] == "author_run_not_review_ready"


def test_failed_author_run_records_actual_failing_node(client, monkeypatch) -> None:
    monkeypatch.setattr(author_workflow_service, "overview_chain_factory", _FakeOverviewChain)
    monkeypatch.setattr(author_workflow_service, "beat_chain_factory", _FailingBeatChain)
    monkeypatch.setattr(author_workflow_service, "policy_factory", lambda: AuthorWorkflowPolicy(max_attempts=3, timeout_seconds=20.0))
    monkeypatch.setattr(author_workflow_service, "scheduler", _InlineScheduler())

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."})
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]

    run_response = client.get(author_run_path(run_id))
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == AuthorWorkflowStatus.FAILED
    assert run_body["current_node"] == AuthorWorkflowNode.GENERATE_SCENE
    events = client.get(author_run_events_path(run_id)).json()["events"]
    assert any(
        event["node_name"] == AuthorWorkflowNode.GENERATE_SCENE
        and event["event_type"] == AuthorWorkflowEventType.NODE_STARTED
        for event in events
    )
    assert any(
        event["node_name"] == AuthorWorkflowNode.GENERATE_SCENE
        and event["event_type"] == AuthorWorkflowEventType.RUN_EXCEPTION
        for event in events
    )


def test_failed_author_run_exposes_prompt_compile_error_code(client, monkeypatch) -> None:
    monkeypatch.setattr(author_workflow_service, "overview_chain_factory", _FakeOverviewChain)
    monkeypatch.setattr(author_workflow_service, "beat_chain_factory", _InvalidBeatChain)
    monkeypatch.setattr(author_workflow_service, "policy_factory", lambda: AuthorWorkflowPolicy(max_attempts=3, timeout_seconds=20.0))
    monkeypatch.setattr(author_workflow_service, "scheduler", _InlineScheduler())

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."})
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]

    run_response = client.get(author_run_path(run_id))
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == AuthorWorkflowStatus.FAILED
    assert run_body["current_node"] == AuthorWorkflowNode.GENERATE_SCENE
    assert run_body["error_code"] == "beat_invalid"
    assert "always_available_moves" in run_body["error_message"]
    workflow_errors = [item for item in run_body["artifacts"] if item["artifact_type"] == AuthorWorkflowArtifactType.WORKFLOW_ERROR]
    assert workflow_errors
    assert workflow_errors[0]["payload"]["error_code"] == "beat_invalid"


def test_author_workflow_retries_timed_out_node_per_attempt(client, monkeypatch) -> None:
    _RetryingOverviewChain.attempts = 0
    monkeypatch.setattr(author_workflow_service, "overview_chain_factory", _RetryingOverviewChain)
    monkeypatch.setattr(author_workflow_service, "beat_chain_factory", _FakeBeatChain)
    monkeypatch.setattr(
        author_workflow_service,
        "policy_factory",
        lambda: AuthorWorkflowPolicy(max_attempts=3, timeout_seconds=0.01),
    )
    monkeypatch.setattr(author_workflow_service, "scheduler", _InlineScheduler())

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."})
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]

    run_response = client.get(author_run_path(run_id))
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == AuthorWorkflowStatus.REVIEW_READY, run_body
    assert _RetryingOverviewChain.attempts == 2

    events = client.get(author_run_events_path(run_id)).json()["events"]
    retry_events = [
        event
        for event in events
        if event["node_name"] == AuthorWorkflowNode.GENERATE_STORY_OVERVIEW
        and event["event_type"] == AuthorWorkflowEventType.NODE_RETRY
    ]
    started_events = [
        event
        for event in events
        if event["node_name"] == AuthorWorkflowNode.GENERATE_STORY_OVERVIEW
        and event["event_type"] == AuthorWorkflowEventType.NODE_STARTED
    ]
    assert len(started_events) == 2
    assert len(retry_events) == 1
    assert retry_events[0]["payload"]["reason"] == "timeout"
    assert retry_events[0]["payload"]["max_attempts"] == 3
    assert retry_events[0]["payload"]["timeout_seconds"] == 0.01


def test_author_workflow_retries_scene_generation_until_third_attempt(client, monkeypatch) -> None:
    _RetryingBeatChain.attempts = 0
    single_blueprint = author_workflow_nodes_module.plan_beat_blueprints_from_overview(_sample_overview())[-1:]
    monkeypatch.setattr(author_workflow_service, "overview_chain_factory", _FakeOverviewChain)
    monkeypatch.setattr(author_workflow_service, "beat_chain_factory", _RetryingBeatChain)
    monkeypatch.setattr(author_workflow_service, "policy_factory", lambda: AuthorWorkflowPolicy(max_attempts=3, timeout_seconds=20.0))
    monkeypatch.setattr(author_workflow_service, "scheduler", _InlineScheduler())
    monkeypatch.setattr(author_workflow_nodes_module, "plan_beat_blueprints_from_overview", lambda overview: single_blueprint)
    monkeypatch.setattr(author_workflow_nodes_module, "check_beat_blueprints", lambda blueprints: [])

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."})
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]

    run_body = client.get(author_run_path(run_id)).json()
    assert run_body["status"] == AuthorWorkflowStatus.REVIEW_READY, run_body
    assert _RetryingBeatChain.attempts == 3

    events = client.get(author_run_events_path(run_id)).json()["events"]
    retry_events = [
        event
        for event in events
        if event["node_name"] == AuthorWorkflowNode.GENERATE_SCENE
        and event["event_type"] == AuthorWorkflowEventType.NODE_RETRY
    ]
    assert len(retry_events) == 2
    assert all(event["payload"]["reason"] == "prompt_compile_failed" for event in retry_events)


def test_author_workflow_retries_only_current_beat_after_lint_failure(client, monkeypatch) -> None:
    _BeatLintRetryChain.calls = []
    _BeatLintRetryChain.attempts_by_beat = {}
    two_blueprints = author_workflow_nodes_module.plan_beat_blueprints_from_overview(_sample_overview())[:2]
    monkeypatch.setattr(author_workflow_service, "overview_chain_factory", _FakeOverviewChain)
    monkeypatch.setattr(author_workflow_service, "beat_chain_factory", _BeatLintRetryChain)
    monkeypatch.setattr(author_workflow_service, "policy_factory", lambda: AuthorWorkflowPolicy(max_attempts=3, timeout_seconds=20.0))
    monkeypatch.setattr(author_workflow_service, "scheduler", _InlineScheduler())
    monkeypatch.setattr(author_workflow_nodes_module, "plan_beat_blueprints_from_overview", lambda overview: two_blueprints)
    monkeypatch.setattr(author_workflow_nodes_module, "check_beat_blueprints", lambda blueprints: [])

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."})
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]

    run_body = client.get(author_run_path(run_id)).json()
    assert run_body["status"] == AuthorWorkflowStatus.REVIEW_READY
    assert [call["beat_id"] for call in _BeatLintRetryChain.calls] == ["b1", "b2", "b2"]
    assert [call["last_accepted_beat_id"] for call in _BeatLintRetryChain.calls] == [None, "b1", "b1"]
    assert _BeatLintRetryChain.calls[1]["lint_feedback"] == []
    assert _BeatLintRetryChain.calls[2]["lint_feedback"]
    assert "unknown npc" in " ".join(_BeatLintRetryChain.calls[2]["lint_feedback"])

    accepted = [item for item in run_body["artifacts"] if item["artifact_type"] == AuthorWorkflowArtifactType.ACCEPTED_BEAT_DRAFT]
    assert len(accepted) == 2
    assert {item["artifact_key"] for item in accepted} == {"b1", "b2"}

    events = client.get(author_run_events_path(run_id)).json()["events"]
    plan_beat_scene_starts = [
        event
        for event in events
        if event["node_name"] == AuthorWorkflowNode.PLAN_BEAT_SCENES
        and event["event_type"] == AuthorWorkflowEventType.NODE_STARTED
    ]
    assert len(plan_beat_scene_starts) == 3


def test_author_workflow_final_lint_failure_does_not_enter_repair(client, monkeypatch) -> None:
    _install_fake_workflow(monkeypatch)
    monkeypatch.setattr(
        author_workflow_nodes_module,
        "lint_story_pack",
        lambda pack: LintReport(errors=["entry scene cannot reach terminal"], warnings=[]),
    )

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."})
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]

    run_body = client.get(author_run_path(run_id)).json()
    assert run_body["status"] == AuthorWorkflowStatus.FAILED
    assert run_body["current_node"] == AuthorWorkflowNode.WORKFLOW_FAILED
    assert run_body["error_code"] == AuthorWorkflowErrorCode.AUTHOR_WORKFLOW_FAILED
    assert run_body["error_message"] == "entry scene cannot reach terminal"

    events = client.get(author_run_events_path(run_id)).json()["events"]
    assert any(event["node_name"] == AuthorWorkflowNode.FINAL_LINT for event in events)
    assert not any(event["node_name"] == "repair_pack" for event in events)
