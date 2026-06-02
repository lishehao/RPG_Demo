from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import rpg_backend.narrative.service as narrative_service_module
from rpg_backend.main import app
from rpg_backend.narrative.brief import build_story_brief
from rpg_backend.narrative.contracts import (
    CastMember,
    CreateTemplateRequest,
    PlayerRole,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.engine import generate_opening
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService, NarrativeServiceError
from rpg_backend.responses_transport import ResponsesJSONResponse
from tests.auth_helpers import ensure_authenticated_client


class _OpeningCaptureGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        operation_name: str,
        max_output_tokens: int | None = None,
    ) -> ResponsesJSONResponse:
        del system_prompt, max_output_tokens
        self.calls.append({"operation_name": operation_name, "user_payload": user_payload})
        return ResponsesJSONResponse(
            payload={
                "title": "Launch Night",
                "advisor_persona": (
                    "Nora is your former producer, stuck outside the venue on a call, "
                    "sharp enough to name the risk without taking over."
                ),
                "cast": [
                    {
                        "character_id": "mara",
                        "display_name": "Mara Vale",
                        "role": "cofounder",
                        "relation_to_protagonist": "She needs you quiet before the vote.",
                        "hidden_objective": "Push the merger through before the recording leaks.",
                        "leverage_over_player": "She has the unsigned indemnity memo.",
                        "leverages_over_other_npcs": [
                            {"target_npc_id": "jules", "leverage": "Knows Jules changed the board packet."},
                            {"target_npc_id": "tess", "leverage": "Has Tess's off-book sponsor email."},
                        ],
                    },
                    {
                        "character_id": "jules",
                        "display_name": "Jules Ren",
                        "role": "board chair",
                        "relation_to_protagonist": "He can kill your launch slot.",
                        "hidden_objective": "Make the missing contract look like your fault.",
                        "leverage_over_player": "He controls the camera feed from rehearsal.",
                        "leverages_over_other_npcs": [
                            {"target_npc_id": "mara", "leverage": "Has Mara's first merger draft."},
                        ],
                    },
                    {
                        "character_id": "tess",
                        "display_name": "Tess Orlo",
                        "role": "legal counsel",
                        "relation_to_protagonist": "She warned you once and now wants distance.",
                        "hidden_objective": "Protect her license before protecting anyone else.",
                        "leverage_over_player": "She has your annotated contract scan.",
                        "leverages_over_other_npcs": [
                            {"target_npc_id": "jules", "leverage": "Can prove Jules backdated the notice."},
                        ],
                    },
                ],
                "player_goals": [
                    {"goal": "Keep control of the launch.", "stakes": "Lose the company vote."},
                    {"goal": "Find who altered the contract.", "stakes": "Take the public blame."},
                ],
                "failure_conditions": [
                    {"label": "Public confession", "description": "You accept legal blame before turn five."},
                    {"label": "Evidence handoff", "description": "You hand the contract scan to Mara."},
                    {"label": "Camera outburst", "description": "You threaten Jules on livestream."},
                ],
                "player_role_options": [
                    {
                        "role_id": "founder",
                        "label": "Cornered founder",
                        "public_persona": "Everyone sees you as the tired founder trying to hold the room.",
                        "hidden_objective": "Expose who changed the launch contract.",
                        "leverages_over_npcs": [
                            {"npc_id": "mara", "leverage": "You have her first merger voice memo."}
                        ],
                        "starting_assets": ["Annotated contract scan"],
                    }
                ],
                "opening_passage": "You stand beside the launch podium while Mara smiles too calmly.",
                "options": [
                    {"label": "Ask Mara who saw the memo", "hint": "Quiet pressure", "handle": "ask Mara"},
                    {"label": "Signal Tess to step closer", "hint": "Build cover", "handle": "signal Tess"},
                    {"label": "Let Jules speak first", "hint": "Watch the room", "handle": "wait"},
                ],
            },
            response_id="resp_opening",
            usage={},
            input_characters=0,
        )


def test_create_template_surfaces_small_cast_prompt_shape_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_generate_opening(**_: object) -> object:
        raise ValueError("cast too small after sanitization: 1")

    monkeypatch.setattr(narrative_service_module, "generate_opening", fake_generate_opening)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    with pytest.raises(NarrativeServiceError) as exc_info:
        service.create_template(
            CreateTemplateRequest(seed="A quiet laundromat ring goes missing."),
            owner_user_id="usr_test",
        )

    assert exc_info.value.code == "opening_prompt_shape_mismatch"
    assert exc_info.value.status_code == 422
    assert "3+ people" in exc_info.value.message


def test_story_brief_route_returns_small_cast_warning() -> None:
    client = TestClient(app)
    ensure_authenticated_client(client, display_name="BriefPlanner")

    response = client.post(
        "/narrative/story-briefs",
        json={
            "seed": "A two-person comedy about a missing cupcake with no villain.",
            "language": "en",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["can_generate"] is False
    assert body["brief"]["runtime_fit_status"] == "not_fit"
    assert body["brief"]["tension_profile"] == "comedy"
    assert body["brief"]["warnings"]


def test_generate_opening_injects_reviewed_story_brief() -> None:
    brief = build_story_brief(
        seed="A comedy launch night where the missing contract is hidden in a cupcake box.",
        language="en",
        desired_tension_profile="comedy",
    ).brief
    gateway = _OpeningCaptureGateway()

    generate_opening(
        gateway=gateway,  # type: ignore[arg-type]
        seed=brief.original_seed,
        language="en",
        story_brief=brief,
    )

    assert gateway.calls
    payload = gateway.calls[0]["user_payload"]
    assert payload["story_brief"]["tension_profile"] == "comedy"
    assert payload["story_brief"]["intervention_card_label"] == "Callback card"
    assert "intervention_card_label" in payload["story_brief_generation_rules"]
    assert "lower-stakes tension contract" in payload["story_brief_generation_rules"]
    assert "Do not convert a comedy/cozy brief" in payload["story_brief_generation_rules"]


def test_create_template_blocks_explicit_small_cast_prompt_before_llm(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_generate_opening(**_: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("LLM opening generation should not run")

    monkeypatch.setattr(narrative_service_module, "generate_opening", fake_generate_opening)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    with pytest.raises(NarrativeServiceError) as exc_info:
        service.create_template(
            CreateTemplateRequest(
                seed="A quiet laundromat ring goes missing: only two people, no villains."
            ),
            owner_user_id="usr_test",
        )

    assert called is False
    assert exc_info.value.code == "opening_prompt_shape_mismatch"
    assert exc_info.value.status_code == 422


def test_create_template_retries_brief_consistency_language_artifact(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = build_story_brief(
        seed=(
            "In a fantasy library during an eclipse, dragons, ink sprites, "
            "and a head librarian argue over a cursed index."
        ),
        language="en",
    ).brief
    calls: list[dict[str, Any]] = []

    def fake_generate_opening(**kwargs):
        calls.append(kwargs)
        content = (
            "The eclipse 已经开始 above the stacks while dragons and ink sprites glare at the head librarian."
            if len(calls) == 1
            else "The eclipse begins above the stacks while dragons and ink sprites glare at the head librarian."
        )
        return type(
            "Opening",
            (),
            {
                "title": "Eclipse Index",
                "advisor_persona": "Mira waits outside the library with a careful warning.",
                "cast": [
                    CastMember(
                        character_id="dragons",
                        display_name="dragons",
                        role="faction",
                        relation_to_protagonist="Accuse the book of hiding the index.",
                    ),
                    CastMember(
                        character_id="ink_sprites",
                        display_name="ink sprites",
                        role="faction",
                        relation_to_protagonist="Know which margin changed.",
                    ),
                    CastMember(
                        character_id="head_librarian",
                        display_name="head librarian",
                        role="keeper",
                        relation_to_protagonist="Controls the locked shelves.",
                    ),
                ],
                "opening_message": StoryMessage(
                    ord=0,
                    role="narrator",
                    content=content,
                    options=[StoryOption(label="Check the cursed index", hint="Probe", handle="check")],
                ),
                "player_goals": [],
                "failure_conditions": [],
                "player_role_options": [
                    PlayerRole(
                        role_id="book",
                        label="Apprentice spellbook",
                        public_persona="A book accused of misfiling the cursed index.",
                        hidden_objective="Prove the index changed itself during the eclipse.",
                    )
                ],
            },
        )()

    monkeypatch.setattr(narrative_service_module, "generate_opening", fake_generate_opening)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    response = service.create_template(
        CreateTemplateRequest(seed=brief.original_seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    assert len(calls) == 2
    assert calls[1]["brief_consistency_feedback"]
    assert response.story_brief_consistency is not None
    assert response.story_brief_consistency.status == "pass"
