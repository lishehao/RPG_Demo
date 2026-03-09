from __future__ import annotations

import json
from pathlib import Path

from rpg_backend.application.author_runs.service import author_workflow_service
from rpg_backend.domain.constants import GLOBAL_CLARIFY_MOVE_ID, GLOBAL_HELP_ME_PROGRESS_MOVE_ID, GLOBAL_LOOK_MOVE_ID
from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.generator.author_workflow_models import BeatDraft, BeatDraftLLM, StoryOverview
from rpg_backend.generator.outcome_materialization import PALETTE_IDS_BY_RESULT
from rpg_backend.generator.author_workflow_errors import PromptCompileError
from tests.helpers.route_paths import (
    author_run_events_path,
    author_run_path,
    author_runs_path,
    author_story_path,
    author_story_runs_path,
    author_stories_path,
    story_publish_path,
)


PACK_PATH = Path("sample_data/story_pack_v1.json")


def _sample_pack() -> dict:
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


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
            "npc_roster": [
                {
                    "name": "Mara",
                    "role": "field engineer",
                    "motivation": "prevent systemic collapse",
                    "red_line": "Never cut hospital access to stabilize industry.",
                    "conflict_tags": ["anti_noise"],
                },
                {
                    "name": "Rook",
                    "role": "security lead",
                    "motivation": "protect civilians",
                    "red_line": "No civilian corridor can be abandoned for pace.",
                    "conflict_tags": ["anti_speed"],
                },
                {
                    "name": "Sera",
                    "role": "operations analyst",
                    "motivation": "preserve evidence",
                    "red_line": "No telemetry wipe even under command pressure.",
                    "conflict_tags": ["anti_noise"],
                },
                {
                    "name": "Director Vale",
                    "role": "command authority",
                    "motivation": "retain control",
                    "red_line": "Public command legitimacy cannot collapse.",
                    "conflict_tags": ["anti_resource_burn"],
                },
            ],
            "move_bias": ["technical", "investigate", "social"],
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
                    "always_available_moves": [GLOBAL_CLARIFY_MOVE_ID, GLOBAL_LOOK_MOVE_ID],
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
                    "always_available_moves": [GLOBAL_CLARIFY_MOVE_ID, GLOBAL_HELP_ME_PROGRESS_MOVE_ID],
                    "exit_conditions": [],
                    "is_terminal": False,
                },
            ],
            "moves": moves,
        }
    )


class _FakeOverviewChain:
    async def compile(self, *, raw_brief: str) -> StoryOverview:
        del raw_brief
        return _sample_overview()


class _FakeBeatChain:
    async def compile(self, *, story_id: str, overview_context: dict | object, blueprint: dict, last_accepted_beat: dict | None, prefix_summary: dict | object, lint_feedback: list[str] | None = None) -> BeatDraft:
        del story_id, last_accepted_beat, prefix_summary, lint_feedback
        beat_index = int(str(blueprint["beat_id"])[1:]) - 1
        overview = _sample_overview()
        self.last_beat_draft_llm = BeatDraftLLM.model_validate(
            {
                "present_npcs": [overview.npc_roster[0].name, overview.npc_roster[1].name],
                "events_produced": [blueprint["required_event"]],
                "scenes": [
                    {
                        "scene_seed": blueprint["scene_intent"],
                        "present_npcs": [overview.npc_roster[0].name, overview.npc_roster[1].name],
                        "enabled_move_indexes": [0, 1, 2],
                        "is_terminal": False,
                    }
                ],
                "moves": [
                    {
                        "label": "A",
                        "strategy_style": "fast_dirty",
                        "intents": ["a"],
                        "synonyms": [],
                        "resolution_policy": "prefer_success",
                        "outcomes": [
                            {"result": "success", "palette_id": PALETTE_IDS_BY_RESULT["success"][0], "next_scene_index": None},
                            {"result": "fail_forward", "palette_id": PALETTE_IDS_BY_RESULT["fail_forward"][0], "next_scene_index": None},
                        ],
                    },
                    {
                        "label": "B",
                        "strategy_style": "steady_slow",
                        "intents": ["b"],
                        "synonyms": [],
                        "resolution_policy": "prefer_success",
                        "outcomes": [
                            {"result": "success", "palette_id": PALETTE_IDS_BY_RESULT["success"][1], "next_scene_index": None},
                            {"result": "fail_forward", "palette_id": PALETTE_IDS_BY_RESULT["fail_forward"][1], "next_scene_index": None},
                        ],
                    },
                    {
                        "label": "C",
                        "strategy_style": "political_safe_resource_heavy",
                        "intents": ["c"],
                        "synonyms": [],
                        "resolution_policy": "prefer_success",
                        "outcomes": [
                            {"result": "success", "palette_id": PALETTE_IDS_BY_RESULT["success"][2], "next_scene_index": None},
                            {"result": "fail_forward", "palette_id": PALETTE_IDS_BY_RESULT["fail_forward"][2], "next_scene_index": None},
                        ],
                    },
                ],
            }
        )
        return _make_beat_draft(overview=overview, blueprint=blueprint, beat_index=beat_index)


class _FakeRepairPackChain:
    async def compile(self, *, story_pack: dict, lint_errors: list[str], lint_warnings: list[str], repair_count: int) -> StoryPack:
        del lint_errors, lint_warnings, repair_count
        return StoryPack.model_validate(story_pack)


class _InlineScheduler:
    async def schedule(self, run_id: str) -> None:
        await author_workflow_service._execute_run(run_id)


def _install_fake_workflow(monkeypatch) -> None:
    monkeypatch.setattr(author_workflow_service, "overview_chain_factory", _FakeOverviewChain)
    monkeypatch.setattr(author_workflow_service, "beat_chain_factory", _FakeBeatChain)
    monkeypatch.setattr(author_workflow_service, "repair_chain_factory", _FakeRepairPackChain)
    monkeypatch.setattr(author_workflow_service, "scheduler", _InlineScheduler())


class _FailingBeatChain:
    async def compile(self, *, story_id: str, overview_context: dict | object, blueprint: dict, last_accepted_beat: dict | None, prefix_summary: dict | object, lint_feedback: list[str] | None = None) -> BeatDraft:
        del story_id, overview_context, blueprint, last_accepted_beat, prefix_summary, lint_feedback
        raise RuntimeError("beat generation exploded")


class _InvalidBeatChain:
    async def compile(self, *, story_id: str, overview_context: dict | object, blueprint: dict, last_accepted_beat: dict | None, prefix_summary: dict | object, lint_feedback: list[str] | None = None) -> BeatDraft:
        del story_id, overview_context, blueprint, last_accepted_beat, prefix_summary, lint_feedback
        raise PromptCompileError(
            error_code="beat_invalid",
            errors=["always_available_moves must only contain global move ids"],
            notes=["beat draft generation failed after schema feedback retry"],
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
    assert run_body["status"] == "review_ready"
    artifact_types = {item["artifact_type"] for item in run_body["artifacts"]}
    prefix_summary_artifact = next(item for item in run_body["artifacts"] if item["artifact_type"] == "prefix_summary")
    assert "completed_beats" in prefix_summary_artifact["payload"]
    assert "text" not in prefix_summary_artifact["payload"]
    assert "overview" in artifact_types
    assert "beat_blueprints" in artifact_types
    assert "beat_overview_context" in artifact_types
    assert "current_beat_llm" in artifact_types
    assert "current_beat_draft" in artifact_types
    assert "story_pack" in artifact_types
    assert "final_lint" in artifact_types
    current_llm = next(item for item in run_body["artifacts"] if item["artifact_type"] == "current_beat_llm")
    first_outcome = current_llm["payload"]["moves"][0]["outcomes"][0]
    assert "palette_id" in first_outcome
    assert "effects" not in first_outcome
    assert "narration_slots" not in first_outcome
    assert sum(1 for item in run_body["artifacts"] if item["artifact_type"] == "accepted_beat_draft") == 4

    events_response = client.get(author_run_events_path(run_id))
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert any(event["node_name"] == "generate_story_overview" for event in events)
    assert any(event["node_name"] == "review_ready" for event in events)

    story_response = client.get(author_story_path(story_id))
    assert story_response.status_code == 200
    story_body = story_response.json()
    assert story_body["latest_run"]["status"] == "review_ready"
    assert story_body["draft_pack"]["title"] == _sample_overview().title

    list_response = client.get(author_stories_path())
    assert list_response.status_code == 200
    stories = list_response.json()["stories"]
    listed = next(item for item in stories if item["story_id"] == story_id)
    assert listed["latest_run_status"] == "review_ready"


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
    monkeypatch.setattr(author_workflow_service, "repair_chain_factory", _FakeRepairPackChain)
    monkeypatch.setattr(author_workflow_service, "scheduler", _InlineScheduler())

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."})
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]

    run_response = client.get(author_run_path(run_id))
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == "failed"
    assert run_body["current_node"] == "generate_next_beat"
    events = client.get(author_run_events_path(run_id)).json()["events"]
    assert any(event["node_name"] == "generate_next_beat" and event["event_type"] == "node_started" for event in events)
    assert any(event["node_name"] == "generate_next_beat" and event["event_type"] == "run_exception" for event in events)


def test_failed_author_run_exposes_prompt_compile_error_code(client, monkeypatch) -> None:
    monkeypatch.setattr(author_workflow_service, "overview_chain_factory", _FakeOverviewChain)
    monkeypatch.setattr(author_workflow_service, "beat_chain_factory", _InvalidBeatChain)
    monkeypatch.setattr(author_workflow_service, "repair_chain_factory", _FakeRepairPackChain)
    monkeypatch.setattr(author_workflow_service, "scheduler", _InlineScheduler())

    created = client.post(author_runs_path(), json={"raw_brief": "Generate a tense reactor incident story."})
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]

    run_response = client.get(author_run_path(run_id))
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == "failed"
    assert run_body["current_node"] == "generate_next_beat"
    assert run_body["error_code"] == "beat_invalid"
    assert "always_available_moves" in run_body["error_message"]
    workflow_errors = [item for item in run_body["artifacts"] if item["artifact_type"] == "workflow_error"]
    assert workflow_errors
    assert workflow_errors[0]["payload"]["error_code"] == "beat_invalid"
