from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

import rpg_backend.narrative.service as narrative_service_module
from rpg_backend.main import app
from rpg_backend.narrative.brief import build_story_brief
from rpg_backend.narrative.contracts import (
    AdvanceTurnRequest,
    CastMember,
    CreateTemplateRequest,
    PlayerRole,
    StoryBriefConsistencyCheck,
    StoryBriefConsistencyViolation,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.engine import generate_opening
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService, NarrativeServiceError
from rpg_backend.responses_transport import ResponsesJSONResponse
from tests.auth_helpers import ensure_authenticated_client


class _OpeningCaptureDouble:
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


def test_create_template_with_story_brief_uses_reliable_opening_when_gateway_missing(
    tmp_path,
) -> None:
    seed = (
        "A board vote comedy where the CFO, founder, union observer, and investor chair "
        "argue over a missing launch memo before the public livestream."
    )
    brief = build_story_brief(seed=seed, language="en").brief
    assert narrative_service_module._story_brief_prefers_reliable_opening(brief) is False
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=None)

    response = service.create_template(
        CreateTemplateRequest(seed=seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    assert response.session.session_id.startswith("sess_")
    assert response.opening.role == "narrator"
    assert response.opening.options
    assert "AI service" not in response.opening.content
    assert response.story_brief_consistency is not None


def test_generate_opening_injects_reviewed_story_brief() -> None:
    brief = build_story_brief(
        seed="A comedy launch night where the missing contract is hidden in a cupcake box.",
        language="en",
        desired_tension_profile="comedy",
    ).brief
    gateway = _OpeningCaptureDouble()

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


def test_missing_live_player_role_is_completed_from_reviewed_brief() -> None:
    brief = build_story_brief(
        seed=(
            "颁奖礼直播前歌手失踪，玩家是公关，制作人、赞助商和主持人都在控制室里施压。"
            "倒计时已经开始，不要血腥。"
        ),
        language="zh",
        desired_tension_profile="high_drama",
    ).brief.model_copy(update={"player_role": "公关"})
    opening = narrative_service_module.OpeningResult(
        title="直播暗箱",
        advisor_persona="一位场外顾问守着电话。",
        cast=[
            CastMember(
                character_id="singer",
                display_name="歌手",
                role="失踪的表演者",
                relation_to_protagonist="等待玩家找到她。",
            ),
            CastMember(
                character_id="producer",
                display_name="制作人",
                role="直播负责人",
                relation_to_protagonist="要求节目继续。",
            ),
            CastMember(
                character_id="host",
                display_name="主持人",
                role="台前主持",
                relation_to_protagonist="等待新的说辞。",
            ),
        ],
        opening_message=StoryMessage(
            ord=0,
            role="narrator",
            content="倒计时还在走，控制室里所有人都看向你。",
            options=[StoryOption(label="查看监控", hint="寻找线索", handle="查监控")],
        ),
        player_goals=[],
        failure_conditions=[],
        player_role_options=[],
    )

    completed = narrative_service_module._complete_opening_identity_from_brief(
        opening,
        brief=brief,
        language="zh",
    )

    assert completed.opening_message is opening.opening_message
    assert completed.cast is opening.cast
    assert completed.player_goals == []
    assert [role.label for role in completed.player_role_options] == ["公关"]
    assert completed.player_role_options[0].hidden_objective.startswith("在局势定型前")
    assert completed.player_role_options[0].starting_assets == ["行动筹码"]


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


def test_create_template_uses_brief_fallback_for_consistency_language_artifact(
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

    assert len(calls) == 1
    assert calls[0]["max_attempts"] == 1
    assert response.story_brief_consistency is not None
    assert response.story_brief_consistency.status == "pass"
    assert "已经" not in response.opening.content
    assert "eclipse" in response.opening.content.lower()


def test_create_template_uses_reliable_opening_first_for_heavy_mars_brief(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = build_story_brief(
        seed=(
            "On Mars colony, a comedy talent show with ten groups - Hydroponics, Oxygen, "
            "Security, Medical, Education, Waste Recycling, Transit, Finance, Communications, "
            "Theatre Club, and Earth Media before the final broadcast. "
            "Each group should represent Theatre Club and Earth Media concerns."
        ),
        language="en",
    ).brief
    calls: list[dict[str, Any]] = []

    def fake_generate_opening(**kwargs):
        calls.append(kwargs)
        raise AssertionError("heavy adapted Story Brief should use reliable opening before live retries")

    monkeypatch.setattr(narrative_service_module, "generate_opening", fake_generate_opening)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    response = service.create_template(
        CreateTemplateRequest(seed=brief.original_seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    assert calls == []
    assert response.story_brief_consistency is not None
    assert response.story_brief_consistency.status == "pass"
    assert "Theatre Club" in response.opening.content
    assert "Earth Media" in response.opening.content
    background_cast = {
        member.display_name: member
        for member in response.template.cast
        if "background stakeholder" in member.role.lower()
    }
    assert "Theatre Club" in background_cast
    assert "Earth Media" in background_cast
    assert "protected context" in background_cast["Theatre Club"].relation_to_protagonist.lower()
    assert "protected context" in background_cast["Earth Media"].relation_to_protagonist.lower()
    assert "backup oxygen tank" not in response.opening.content
    assert "At the Mars colony talent show" in response.opening.content
    assert "oxygen rumor" in response.opening.content
    assert "callback" in response.opening.content
    assert "crowd the first decision" not in response.opening.content
    assert "talent show, Mars colony is already underway" not in response.opening.content
    assert "visible mistake" not in response.opening.content
    assert "cleaner way to talk" not in response.opening.content
    visible_text = " ".join(
        [
            response.template.title,
            response.opening.content,
            response.template.advisor_persona,
            *[option.label for option in response.opening.options],
            *[option.hint or "" for option in response.opening.options],
            *[goal.goal for goal in response.template.player_goals],
            *[goal.stakes for goal in response.template.player_goals],
            *[condition.label for condition in response.template.failure_conditions],
            *[condition.description for condition in response.template.failure_conditions],
            *[role.label for role in response.template.player_role_options],
            *[role.public_persona for role in response.template.player_role_options],
        ]
    ).lower()
    for internal_term in (
        "fallback",
        "brief",
        "active focus",
        "background pressure",
        "playable",
        "contract",
        "checker",
        "reviewed",
        "represented parties",
    ):
        assert internal_term not in visible_text


def test_create_template_uses_brief_fallback_after_repeated_consistency_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = build_story_brief(
        seed=(
            "On Mars colony, a lower-stakes comedy talent show involves Hydroponics, "
            "Security, Theatre Club, and Earth Media before the final broadcast; no violence."
        ),
        language="en",
        desired_tension_profile="comedy",
    ).brief

    def fake_generate_opening(**_: object) -> object:
        return type(
            "Opening",
            (),
            {
                "title": "Oxygen Heist",
                "advisor_persona": "A crisis aide calls from the airlock.",
                "cast": [
                    CastMember(
                        character_id="hydroponics",
                        display_name="Hydroponics",
                        role="department",
                        relation_to_protagonist="Part of the emergency.",
                    ),
                    CastMember(
                        character_id="security",
                        display_name="Security",
                        role="department",
                        relation_to_protagonist="Blames the player.",
                    ),
                ],
                "opening_message": StoryMessage(
                    ord=0,
                    role="narrator",
                    content=(
                        "Hydroponics and Security argue over a backup oxygen tank while "
                        "Theatre Club and Earth Media are nowhere in the room."
                    ),
                    options=[StoryOption(label="Ask about the tank", hint="Crisis", handle="ask")],
                ),
                "player_goals": [],
                "failure_conditions": [],
                "player_role_options": [
                    PlayerRole(
                        role_id="producer",
                        label="Producer",
                        public_persona="The producer caught in the airlock crisis.",
                        hidden_objective="Find the tank.",
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

    assert response.story_brief_consistency is not None
    assert response.story_brief_consistency.status == "pass"
    assert "Theatre Club" in response.opening.content
    assert "Earth Media" in response.opening.content
    assert "backup oxygen tank" not in response.opening.content
    assert response.template.player_role_options


def test_create_template_uses_brief_fallback_after_opening_parse_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = build_story_brief(
        seed=(
            "In a floating dragon library, a shy apprentice spellbook, ink sprites, sky pirates, "
            "the Archivist Guild, moon-oracle librarians, and a banished dragon clan argue over "
            "a missing star map before an eclipse in three hours. Keep it fantastical, tense but "
            "playful, and make the eclipse the time pressure."
        ),
        language="en",
    ).brief

    def fake_generate_opening(**_: object) -> object:
        raise ValueError("Expecting ',' delimiter")

    monkeypatch.setattr(narrative_service_module, "generate_opening", fake_generate_opening)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    response = service.create_template(
        CreateTemplateRequest(seed=brief.original_seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    assert response.story_brief_consistency is not None
    assert response.story_brief_consistency.status == "pass"
    assert "已经" not in response.opening.content
    assert "eclipse" in response.opening.content.lower()
    assert "floating dragon library" in response.opening.content
    assert "shy apprentice spellbook" in response.opening.content.lower()
    assert "missing star map" in response.opening.content
    assert "library setting" not in response.opening.content
    assert "visible mistake" not in response.opening.content
    assert response.session.session_id


def test_create_template_cozy_fit_prompt_can_fallback_to_playable_opening(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = build_story_brief(
        seed=(
            "At a neighborhood bake sale, the PTA treasurer, a teen volunteer, "
            "a tired parent, and the cupcake judge argue over a missing recipe card "
            "before judging starts. Keep it cozy and funny: no blackmail, no betrayal, "
            "only misunderstandings, embarrassment, and a callback joke."
        ),
        language="en",
    ).brief

    def fake_generate_opening(**_: object) -> object:
        raise ValueError("missing or non-string field: opening_passage")

    monkeypatch.setattr(narrative_service_module, "generate_opening", fake_generate_opening)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    response = service.create_template(
        CreateTemplateRequest(seed=brief.original_seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    assert response.story_brief_consistency is not None
    assert response.story_brief_consistency.status == "pass"
    assert "At the neighborhood bake sale" in response.opening.content
    assert "PTA treasurer" in response.opening.content
    assert "cupcake judge" in response.opening.content
    assert "missing recipe card" in response.opening.content
    assert "visible mistake" not in response.opening.content
    assert "cleaner way to talk" not in response.opening.content
    assert response.opening.options
    assert response.session.session_id


def test_create_template_exact_cozy_baseline_reaches_first_turn_without_gateway(
    tmp_path,
) -> None:
    seed = (
        "At a neighborhood bake sale, three parents and a shy teen volunteer "
        "try to find who swapped the cupcake labels. Keep it cozy and funny, "
        "no blackmail, no betrayal, no corporate stakes."
    )
    brief = build_story_brief(seed=seed, language="en").brief
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=None)

    response = service.create_template(
        CreateTemplateRequest(seed=seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    assert response.story_brief_consistency is not None
    assert response.story_brief_consistency.status == "pass"
    assert response.opening.options
    assert "cupcake labels become" in response.opening.content.casefold()
    assert "cupcake labels becomes" not in response.opening.content.casefold()
    assert "cupcake labels have pulled" in response.opening.content.casefold()
    assert "cupcake labels has pulled" not in response.opening.content.casefold()
    opening_lower = response.opening.content.casefold()
    assert "player" not in opening_lower
    assert "mix-up witness" not in opening_lower
    assert "embarrassed helper" not in opening_lower
    assert "deadline host" not in opening_lower
    role_labels = {role.label for role in response.template.player_role_options}
    assert "Label checker" in role_labels
    assert "Callback keeper" not in role_labels
    option_labels = " ".join(option.label for option in response.opening.options).casefold()
    assert "cupcake labels" in option_labels
    assert "missing prop" not in option_labels
    visible_opening_text = " ".join(
        [
            response.opening.content,
            *[option.label for option in response.opening.options],
            *[option.hint or "" for option in response.opening.options],
            *[role.label for role in response.template.player_role_options],
            *[role.public_persona for role in response.template.player_role_options],
        ]
    ).casefold()
    for taboo in (
        "accuse",
        "fight",
        "scapegoat",
        "takes the fall",
        "security footage",
        "hacking",
        "permanent position",
        "blackmail",
        "betrayal",
    ):
        assert taboo not in visible_opening_text

    turn = service.advance(
        response.session.session_id,
        AdvanceTurnRequest(chosen_option_index=0),
        player_user_id="usr_test",
        include_agent_trace=True,
    )
    second_turn = service.advance(
        response.session.session_id,
        AdvanceTurnRequest(chosen_option_index=0),
        player_user_id="usr_test",
        include_agent_trace=True,
    )
    events = repo.list_agent_events(response.session.session_id)

    assert turn.narrator_message.options
    assert second_turn.narrator_message.options
    assert "AI service" not in turn.narrator_message.content
    assert "AI service" not in second_turn.narrator_message.content
    assert "fallback" not in turn.narrator_message.content.casefold()
    assert "fallback" not in second_turn.narrator_message.content.casefold()
    assert turn.narrator_message.content != second_turn.narrator_message.content
    assert "shifts after" not in second_turn.narrator_message.content.casefold()
    assert "cupcake labels" in turn.narrator_message.content.casefold()
    assert "cupcake labels" in second_turn.narrator_message.content.casefold()
    assert [event.event_type for event in events[:3]] == [
        "agent_plan",
        "step_judge",
        "contract_judge",
    ]
    assert [event.event_type for event in events[3:]] == [
        "agent_plan",
        "step_judge",
        "contract_judge",
    ]
    assert events[1].payload.status == "pass"
    assert events[2].payload.status == "pass"
    assert events[4].payload.status == "pass"
    assert events[5].payload.status == "pass"


def test_create_template_uses_brief_fallback_after_consistency_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = build_story_brief(
        seed=(
            "On Mars colony, a lower-stakes comedy talent show involves Hydroponics, "
            "Security, Theatre Club, and Earth Media before the final broadcast; no violence."
        ),
        language="en",
        desired_tension_profile="comedy",
    ).brief

    calls: list[dict[str, object]] = []

    def fake_generate_opening(**kwargs: object) -> object:
        calls.append(kwargs)
        return type(
            "Opening",
            (),
            {
                "title": "Oxygen Heist",
                "advisor_persona": "A crisis aide calls from the airlock.",
                "cast": [
                    CastMember(
                        character_id="hydroponics",
                        display_name="Hydroponics",
                        role="department",
                        relation_to_protagonist="Part of the emergency.",
                    )
                ],
                "opening_message": StoryMessage(
                    ord=0,
                    role="narrator",
                    content="Hydroponics argues over a backup oxygen tank.",
                    options=[StoryOption(label="Ask about the tank", hint="Crisis", handle="ask")],
                ),
                "player_goals": [],
                "failure_conditions": [],
                "player_role_options": [
                    PlayerRole(
                        role_id="producer",
                        label="Producer",
                        public_persona="The producer caught in the airlock crisis.",
                        hidden_objective="Find the tank.",
                    )
                ],
            },
        )()

    def always_fail_check(**_: object) -> StoryBriefConsistencyCheck:
        return StoryBriefConsistencyCheck(
            status="fail",
            should_retry=False,
            summary="Forced failure for actionable error mapping.",
            violations=[
                StoryBriefConsistencyViolation(
                    code="brief_emphasized_entity_absent",
                    severity="fail",
                    rationale="Required entities are absent.",
                    evidence=["Theatre Club", "Earth Media"],
                )
            ],
        )

    monkeypatch.setattr(narrative_service_module, "generate_opening", fake_generate_opening)
    monkeypatch.setattr(narrative_service_module, "check_story_brief_opening_consistency", always_fail_check)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    response = service.create_template(
        CreateTemplateRequest(seed=brief.original_seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    assert len(calls) == 1
    assert calls[0]["max_attempts"] == 1
    assert response.session.session_id.startswith("sess_")
    assert response.opening.role == "narrator"
    assert response.opening.options
    assert response.story_brief_consistency is not None
    assert response.story_brief_consistency.status == "warn"
    assert response.story_brief_consistency.should_retry is False
    assert response.opening_recovery == "tightened_from_brief"


def test_create_template_caps_story_brief_live_opening_latency(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = (
        "Minutes before the awards livestream, a famous singer disappears from the control room. "
        "The player is the anxious publicist, the producer wants to keep the livestream moving, "
        "the backup dancer witnessed the singer leave, and the award audience is watching. "
        "The contested pressure is whether to stop the livestream and reveal the disappearance "
        "before sponsors and fans panic; keep it English and high-drama with no gore."
    )
    brief = build_story_brief(seed=seed, language="en", desired_tension_profile="high_drama").brief
    calls: list[dict[str, object]] = []

    def slow_generate_opening(**kwargs: object) -> object:
        calls.append(kwargs)
        time.sleep(0.05)
        raise AssertionError("Timed-out live opening result should be discarded")

    monkeypatch.setattr(narrative_service_module, "_STORY_BRIEF_LIVE_OPENING_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(narrative_service_module, "generate_opening", slow_generate_opening)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    response = service.create_template(
        CreateTemplateRequest(seed=brief.original_seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    assert len(calls) == 1
    assert calls[0]["max_attempts"] == 1
    assert response.session.session_id.startswith("sess_")
    assert "disappearance" in response.opening.content.lower()
    assert response.opening.options
    assert response.story_brief_consistency is not None
    assert response.story_brief_consistency.status in {"pass", "warn"}
    assert response.opening_recovery == "tightened_from_brief"


def test_create_template_reliable_opening_avoids_agent_chat_entity_fragments(tmp_path) -> None:
    seed = (
        "Make it a short English high drama backstage scene where NPCs fight back. "
        "A publicist, producer, backup dancer, sponsor, and missing singer are trapped before "
        "a livestream, and the player must decide what to reveal while fans panic outside."
    )
    brief = build_story_brief(seed=seed, language="en", desired_tension_profile="high_drama").brief
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=None)

    response = service.create_template(
        CreateTemplateRequest(seed=seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    opening = response.opening.content.lower()
    assert response.session.session_id.startswith("sess_")
    assert response.opening.options
    assert "missing singer are trapped" not in opening
    assert "singer are trapped" not in opening
    assert "player must" not in opening
    assert "publicist" in opening
    assert "producer" in opening
    assert "backup dancer" in opening


def test_create_template_reliable_opening_keeps_negated_constraints_out_of_cast(tmp_path) -> None:
    seed = (
        "Make it a short English high drama backstage scene where NPCs fight back: "
        "I play a nervous publicist, Producer Han wants the awards livestream to continue, "
        "Rina the backup dancer saw singer Seo Mina leave, sponsors and fans are watching, "
        "and there is no gore."
    )
    brief = build_story_brief(seed=seed, language="en", desired_tension_profile="high_drama").brief
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=None)

    response = service.create_template(
        CreateTemplateRequest(seed=seed, language="en", story_brief=brief),
        owner_user_id="usr_test",
    )

    cast_blob = " ".join(
        f"{member.character_id} {member.display_name} {member.role} {member.relation_to_protagonist}"
        for member in response.template.cast
    ).lower()
    opening = response.opening.content.lower()

    assert response.session.session_id.startswith("sess_")
    assert response.opening.options
    assert "there_is_no_gore" not in cast_blob
    assert "no_gore" not in cast_blob
    assert "there is no gore" not in cast_blob
    assert "no gore" not in cast_blob
    assert "there is no gore" not in opening
    assert "no gore stays" not in opening
    assert "nervous publicist" in opening
    assert "producer han" in opening or "producer" in opening
    assert "rina backup dancer" in opening or "backup dancer" in opening
