from __future__ import annotations

import asyncio

import pytest

from rpg_backend.generator.author_workflow_chains import BeatGenerationChain
from rpg_backend.generator.author_workflow_models import BeatBlueprint, BeatDraftLLM, StoryOverview
from rpg_backend.generator.author_workflow_validators import build_structured_prefix_summary, project_overview_for_beat_generation
from rpg_backend.generator.author_workflow_normalizer import normalize_beat_draft
from rpg_backend.generator.outcome_materialization import PALETTE_IDS_BY_RESULT, build_outcome_from_palette_id
from rpg_backend.generator.author_workflow_errors import PromptCompileError
from rpg_backend.domain.constants import GLOBAL_CLARIFY_MOVE_ID, GLOBAL_HELP_ME_PROGRESS_MOVE_ID, GLOBAL_LOOK_MOVE_ID


def _overview() -> StoryOverview:
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
                {"name": "Mara", "role": "engineer", "motivation": "stabilize", "red_line": "No false telemetry.", "conflict_tags": ["anti_noise"]},
                {"name": "Rook", "role": "security", "motivation": "protect", "red_line": "No civilian abandonment.", "conflict_tags": ["anti_speed"]},
                {"name": "Sera", "role": "analyst", "motivation": "preserve evidence", "red_line": "No telemetry wipe.", "conflict_tags": ["anti_noise"]},
                {"name": "Vale", "role": "director", "motivation": "retain control", "red_line": "No legitimacy collapse.", "conflict_tags": ["anti_resource_burn"]},
            ],
            "move_bias": ["technical", "investigate", "social"],
            "scene_constraints": ["One", "Two", "Three", "Four"],
        }
    )


def _blueprint() -> BeatBlueprint:
    return BeatBlueprint.model_validate(
        {
            "beat_id": "b1",
            "title": "Opening Pressure",
            "objective": "Advance opening pressure",
            "conflict": "Conflicting telemetry and public pressure.",
            "required_event": "b1.milestone",
            "step_budget": 4,
            "npc_quota": 2,
            "entry_scene_id": "b1.sc1",
            "scene_intent": "Stress the control room under rising uncertainty.",
        }
    )


def _llm_draft(*, bad_index: bool = False, bad_next_scene_index: bool = False) -> BeatDraftLLM:
    return BeatDraftLLM.model_validate(
        {
            "present_npcs": ["Mara", "Rook"],
            "events_produced": ["b1.signal_locked"],
            "scenes": [
                {
                    "scene_seed": "Open in the shaking control room.",
                    "present_npcs": ["Mara", "Rook"],
                    "enabled_move_indexes": [0, 1, 9] if bad_index else [0, 1, 2],
                    "is_terminal": False,
                },
                {
                    "scene_seed": "Shift to a narrower technical corridor.",
                    "present_npcs": ["Mara", "Sera"],
                    "enabled_move_indexes": [0, 1, 2],
                    "is_terminal": False,
                },
            ],
            "moves": [
                {
                    "label": "Force a fast response",
                    "strategy_style": "fast_dirty",
                    "intents": ["rush"],
                    "synonyms": ["rush"],
                    "resolution_policy": "prefer_success",
                    "outcomes": [
                        {
                            "result": "success",
                            "palette_id": PALETTE_IDS_BY_RESULT["success"][0],
                            "next_scene_index": 1,
                        },
                        {
                            "result": "fail_forward",
                            "palette_id": PALETTE_IDS_BY_RESULT["fail_forward"][0],
                            "next_scene_index": 5 if bad_next_scene_index else None,
                        },
                    ],
                },
                {
                    "label": "Hold the line carefully",
                    "strategy_style": "steady_slow",
                    "intents": ["steady"],
                    "synonyms": ["careful"],
                    "resolution_policy": "prefer_success",
                    "outcomes": [
                        {
                            "result": "success",
                            "palette_id": PALETTE_IDS_BY_RESULT["success"][1],
                            "next_scene_index": 1,
                        },
                        {
                            "result": "fail_forward",
                            "palette_id": PALETTE_IDS_BY_RESULT["fail_forward"][1],
                            "next_scene_index": None,
                        },
                    ],
                },
                {
                    "label": "Use the official safe path",
                    "strategy_style": "political_safe_resource_heavy",
                    "intents": ["safe"],
                    "synonyms": ["official"],
                    "resolution_policy": "prefer_success",
                    "outcomes": [
                        {
                            "result": "success",
                            "palette_id": PALETTE_IDS_BY_RESULT["success"][2],
                            "next_scene_index": None,
                        },
                        {
                            "result": "fail_forward",
                            "palette_id": PALETTE_IDS_BY_RESULT["fail_forward"][2],
                            "next_scene_index": None,
                        },
                    ],
                },
            ],
        }
    )


def test_normalize_beat_draft_injects_fixed_fields() -> None:
    draft = normalize_beat_draft(overview=_overview(), blueprint=_blueprint(), llm_draft=_llm_draft())
    assert draft.beat_id == "b1"
    assert draft.entry_scene_id == "b1.sc1"
    assert draft.scenes[0].id == "b1.sc1"
    assert draft.scenes[1].id == "b1.sc2"
    assert draft.moves[0].id == "b1.m1"
    assert draft.moves[0].outcomes[0].id == "b1.m1.o1.success"
    assert draft.scenes[0].always_available_moves == [
        GLOBAL_CLARIFY_MOVE_ID,
        GLOBAL_LOOK_MOVE_ID,
        GLOBAL_HELP_ME_PROGRESS_MOVE_ID,
    ]


def test_normalize_beat_draft_rejects_invalid_move_index() -> None:
    with pytest.raises(ValueError, match="enabled_move_indexes"):
        _ = normalize_beat_draft(overview=_overview(), blueprint=_blueprint(), llm_draft=_llm_draft(bad_index=True))


def test_normalize_beat_draft_rejects_invalid_next_scene_index() -> None:
    with pytest.raises(ValueError, match="next_scene_index"):
        _ = normalize_beat_draft(overview=_overview(), blueprint=_blueprint(), llm_draft=_llm_draft(bad_next_scene_index=True))


def test_normalize_expands_palette_driven_outcome() -> None:
    draft = normalize_beat_draft(blueprint=_blueprint(), llm_draft=_llm_draft())
    outcome = draft.moves[0].outcomes[0]
    assert outcome.preconditions == []
    assert outcome.effects
    assert outcome.narration_slots.npc_reaction


def test_palette_result_mismatch_raises_during_normalize() -> None:
    payload = _llm_draft().model_dump(mode="json")
    payload["moves"][0]["outcomes"][0]["result"] = "success"
    payload["moves"][0]["outcomes"][0]["palette_id"] = PALETTE_IDS_BY_RESULT["partial"][0]
    llm_draft = BeatDraftLLM.model_validate(payload)
    with pytest.raises(ValueError, match="does not match result"):
        _ = normalize_beat_draft(blueprint=_blueprint(), llm_draft=llm_draft)


def test_outcome_builder_matches_shared_palette_logic() -> None:
    built = build_outcome_from_palette_id(
        move_id="b1.m1",
        outcome_index=0,
        result="success",
        palette_id=PALETTE_IDS_BY_RESULT["success"][0],
        strategy_style="fast_dirty",
        next_scene_id=None,
    )
    assert built["effects"]
    assert built["narration_slots"]["cost_delta"]


def test_beat_generation_chain_retries_after_schema_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        {"payload": {"present_npcs": ["Mara"], "events_produced": [], "scenes": [], "moves": []}},
        {"payload": _llm_draft().model_dump(mode="json")},
    ]

    async def _fake_invoke_chain(self, *, system_prompt: str, user_payload: dict[str, object]):  # noqa: ANN001, ANN202
        del system_prompt
        if len(responses) == 1:
            assert user_payload["validation_feedback"]
        return type("R", (), responses.pop(0) | {"attempts": 1})()

    monkeypatch.setattr(BeatGenerationChain, "_invoke_chain", _fake_invoke_chain)
    chain = BeatGenerationChain()
    draft = asyncio.run(
        chain.compile(
            story_id="story-1",
            overview_context=project_overview_for_beat_generation(_overview()),
            blueprint=_blueprint().model_dump(mode="json"),
            last_accepted_beat=None,
            prefix_summary=build_structured_prefix_summary([]),
            lint_feedback=[],
        )
    )
    assert draft.beat_id == "b1"
    assert chain.last_beat_draft_llm is not None


def test_beat_generation_chain_raises_beat_invalid_after_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        {"payload": _llm_draft(bad_index=True).model_dump(mode="json")},
        {"payload": _llm_draft(bad_index=True).model_dump(mode="json")},
    ]

    async def _fake_invoke_chain(self, *, system_prompt: str, user_payload: dict[str, object]):  # noqa: ANN001, ANN202
        del system_prompt, user_payload
        return type("R", (), responses.pop(0) | {"attempts": 1})()

    monkeypatch.setattr(BeatGenerationChain, "_invoke_chain", _fake_invoke_chain)
    chain = BeatGenerationChain()
    with pytest.raises(PromptCompileError) as exc_info:
        asyncio.run(
            chain.compile(
                story_id="story-1",
                overview_context=project_overview_for_beat_generation(_overview()),
                blueprint=_blueprint().model_dump(mode="json"),
                last_accepted_beat=None,
                prefix_summary=build_structured_prefix_summary([]),
                lint_feedback=[],
            )
        )
    assert exc_info.value.error_code == "beat_invalid"


def test_beat_move_llm_requires_success_and_fail_forward() -> None:
    payload = _llm_draft().model_dump(mode="json")
    payload["moves"][0]["outcomes"] = [payload["moves"][0]["outcomes"][0]]
    with pytest.raises(ValueError, match="success and fail_forward"):
        BeatDraftLLM.model_validate(payload)


def test_beat_generation_chain_payload_uses_last_accepted_beat_and_structured_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_invoke_chain(self, *, system_prompt: str, user_payload: dict[str, object]):  # noqa: ANN001, ANN202
        captured["system_prompt"] = system_prompt
        captured["user_payload"] = dict(user_payload)
        return type("R", (), {"payload": _llm_draft().model_dump(mode="json"), "attempts": 1})()

    monkeypatch.setattr(BeatGenerationChain, "_invoke_chain", _fake_invoke_chain)
    chain = BeatGenerationChain()
    prior = normalize_beat_draft(blueprint=_blueprint(), llm_draft=_llm_draft())
    _ = asyncio.run(
        chain.compile(
            story_id="story-1",
            overview_context=project_overview_for_beat_generation(_overview()),
            blueprint=_blueprint().model_dump(mode="json"),
            last_accepted_beat=prior.model_dump(mode="json"),
            prefix_summary=build_structured_prefix_summary([prior]),
            lint_feedback=[],
        )
    )
    payload = captured["user_payload"]
    assert "overview_context" in payload
    assert "prefix_summary" in payload
    assert "last_accepted_beat" in payload
    assert "prior_beats" not in payload
