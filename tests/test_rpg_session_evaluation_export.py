from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

import rpg_backend.main as main_module
from rpg_backend.narrative.brief import build_story_brief
from rpg_backend.narrative.contracts import (
    AdvanceTurnRequest,
    CastMember,
    GameplayChip,
    InventoryDelta,
    NPCPulse,
    PlayerGoal,
    PlayerRole,
    StoryGuideCompressedContext,
    StoryMessage,
    StoryOption,
    TurnGameplayMetadata,
)
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService
from rpg_backend.research_runtime.evaluator import evaluate_rpg_bundle
from rpg_backend.responses_transport import ResponsesJSONResponse


class _TurnContractCapture:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, object],
        operation_name: str,
        max_output_tokens: int | None = None,
    ) -> ResponsesJSONResponse:
        del system_prompt, max_output_tokens
        self.calls.append({"operation_name": operation_name, "user_payload": user_payload})
        return ResponsesJSONResponse(
            payload={
                "passage": "Marcus freezes when the publicist names the timestamp on camera.",
                "options": [
                    {"label": "Ask Elena to verify the envelope"},
                    {"label": "Move Marcus away from the host"},
                ],
                "npc_pulse": [
                    {
                        "npc_id": "marcus",
                        "state": "His denial is losing the room.",
                        "shift": "cornered",
                        "reason": "The timestamp is now public.",
                    }
                ],
            },
            response_id="turn-contract-capture",
            usage={},
            input_characters=len(str(user_payload)),
        )


def _seed_runtime(repo: NarrativeRepository, *, owner_user_id: str = "owner") -> tuple[str, str]:
    template_id = "tmpl_research_export"
    session_id = "sess_research_export"
    context = StoryGuideCompressedContext(
        scene_summary="An awards livestream is seconds from exposing a rigged result.",
        player_role="Publicist",
        cast_or_factions=["Elena", "Marcus", "Dana"],
        pressure="The host goes live in three minutes.",
        constraints=["No violence"],
        tone="high_drama",
        confirmed_facts=["The trophy envelope was swapped."],
        rejected_or_changed_facts=["superseded player_role: Backup dancer"],
        non_story_user_intents=["meta_assistant: who are you"],
        readiness_score=0.92,
    )
    brief = build_story_brief(
        seed=(
            "At an awards livestream, Elena, Marcus, and Dana collide over a rigged trophy "
            "three minutes before air. The player is the publicist. No violence."
        ),
        desired_tension_profile="high_drama",
    ).brief
    cast = [
        CastMember(
            character_id="elena",
            display_name="Elena",
            role="award nominee",
            relation_to_protagonist="client",
        ),
        CastMember(
            character_id="marcus",
            display_name="Marcus",
            role="event sponsor",
            relation_to_protagonist="adversary",
        ),
        CastMember(
            character_id="dana",
            display_name="Dana",
            role="crisis advisor",
            relation_to_protagonist="mentor",
        ),
    ]
    repo.create_template(
        template_id=template_id,
        owner_user_id=owner_user_id,
        seed=brief.original_seed,
        title="Rigged Trophy Reveal",
        cast=cast,
        advisor_persona="A precise crisis editor.",
        opening_passage="The host reaches for the rigged envelope.",
        opening_options=[StoryOption(label="Show Elena the proof"), StoryOption(label="Confront Marcus")],
        player_goals=[PlayerGoal(goal="Protect Elena before the reveal", stakes="Her career and your reputation")],
        failure_conditions=[],
        player_role_options=[
            PlayerRole(
                role_id="publicist",
                label="The Publicist",
                public_persona="Elena's crisis manager.",
                hidden_objective="Protect Elena without burying the truth.",
                starting_assets=["Photo of the swapped envelope"],
            )
        ],
        visibility="private",
        language="en",
        story_brief=brief,
        story_guide_context=context,
    )
    repo.create_session(
        session_id=session_id,
        template_id=template_id,
        player_user_id=owner_user_id,
        turn_budget=8,
        selected_player_role_id="publicist",
    )
    repo.append_story_message(
        session_id,
        StoryMessage(
            ord=0,
            role="narrator",
            content="The host reaches for the rigged envelope.",
            options=[StoryOption(label="Show Elena the proof"), StoryOption(label="Confront Marcus")],
        ),
    )
    repo.append_story_message(
        session_id,
        StoryMessage(ord=1, role="player", content="Show Elena the proof before Marcus can intervene."),
    )
    repo.append_story_message(
        session_id,
        StoryMessage(
            ord=2,
            role="narrator",
            content=(
                "Elena checks the timestamp and steps away from Marcus as Dana locks the press-room door. "
                + "The live audience closes in around the disputed envelope. " * 12
            ),
            options=[StoryOption(label="Question Marcus"), StoryOption(label="Secure the original envelope")],
            npc_pulse=[
                NPCPulse(
                    npc_id="elena",
                    state="She trusts your warning.",
                    shift="warmer",
                    reason="You showed verifiable proof.",
                )
            ],
            inventory_delta=InventoryDelta(
                added=["Timestamped envelope photo"],
                reason="Elena verified the image.",
            ),
            gameplay_metadata=TurnGameplayMetadata(
                state_deltas=[GameplayChip(label="Public pressure contained", tone="gain")],
                clue_unlocks=[GameplayChip(label="Envelope timestamp", tone="unlock")],
                opportunity_unlocks=[GameplayChip(label="Press-room interview", tone="unlock")],
            ),
        ),
    )
    repo.touch_session(session_id, increment_turns=1)
    return template_id, session_id


def test_create_memory_seeds_persist_and_export_into_live_session_bundle(tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"
    repo = NarrativeRepository(str(db_path))
    template_id, session_id = _seed_runtime(repo)

    brief, context = repo.get_template_research_context(template_id)
    assert brief is not None
    assert context is not None
    assert context.player_role == "Publicist"

    bundle = NarrativeService(repository=repo, gateway=None).get_rpg_evaluation_bundle(
        session_id,
        player_user_id="owner",
    )
    report = evaluate_rpg_bundle(bundle)

    assert bundle.schema_version == "rpg_evaluation_bundle.v1"
    assert bundle.turns[0].progress_basis == "turn_budget_proxy"
    assert bundle.turns[0].memory.diagnostics.non_story_event_count == 1
    assert any(fact.key == "player_role" and fact.value == "Publicist" for fact in bundle.turns[0].memory.active_facts)
    assert any(fact.value == "Backup dancer" for fact in bundle.turns[0].memory.superseded_facts)
    assert any(delta.target == "elena" for delta in bundle.turns[0].state_deltas)
    assert "Envelope timestamp" in bundle.turns[0].clue_unlocks
    assert "Press-room interview" in bundle.turns[0].opportunity_unlocks
    assert report.status == "pass"
    assert any("turn budget as a proxy" in item for item in report.limitations)


def test_malformed_research_context_downgrades_without_breaking_template(tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"
    repo = NarrativeRepository(str(db_path))
    template_id, _ = _seed_runtime(repo)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE narrative_templates SET story_guide_context_json = ? WHERE template_id = ?",
            ("{not-valid-json", template_id),
        )
        connection.commit()

    brief, context = repo.get_template_research_context(template_id)

    assert repo.get_template(template_id).title == "Rigged Trophy Reveal"
    assert brief is not None
    assert context is None


def test_live_turn_prompt_uses_current_create_memory_without_superseded_or_chat_data(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _, session_id = _seed_runtime(repo)
    gateway = _TurnContractCapture()

    NarrativeService(repository=repo, gateway=gateway).advance(
        session_id,
        AdvanceTurnRequest(chosen_option_index=0),
        player_user_id="owner",
    )

    payload = gateway.calls[-1]["user_payload"]
    assert isinstance(payload, dict)
    contract = payload["story_contract"]
    assert isinstance(contract, dict)
    assert contract["player_role"] == "Publicist"
    assert contract["boundaries"] == ["No violence"]
    assert "The trophy envelope was swapped." in contract["confirmed_facts"]
    assert "Backup dancer" not in str(contract)
    assert "meta_assistant" not in str(contract)
    assert "recent_turns" not in contract


def test_session_export_and_portable_evaluator_are_reachable_through_authenticated_api(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    client = TestClient(main_module.app)
    login = client.post("/auth/login", json={"username": "evaluation_owner"})
    assert login.status_code == 200
    user_id = login.json()["user"]["user_id"]
    _, session_id = _seed_runtime(repo, owner_user_id=user_id)
    service = NarrativeService(repository=repo, gateway=None)
    original_service = main_module.narrative_service
    main_module.narrative_service = service

    try:
        bundle_response = client.get(f"/narrative/sessions/{session_id}/evaluation-bundle")
        report_response = client.post("/research/rpg-evaluations", json=bundle_response.json())
    finally:
        main_module.narrative_service = original_service

    assert bundle_response.status_code == 200
    assert bundle_response.json()["run_id"] == session_id
    assert report_response.status_code == 200
    assert report_response.json()["schema_version"] == "rpg_evaluation_report.v1"
    assert report_response.json()["status"] == "pass"
