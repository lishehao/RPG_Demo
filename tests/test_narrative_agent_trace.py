from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

import rpg_backend.main as main_module
from rpg_backend.narrative.contracts import (
    AgentPlan,
    AdvanceTurnRequest,
    CastMember,
    NPCLeverageOverNPC,
    PlayerGoal,
    PlayerLeverageOverNPC,
    PlayerRole,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.engine import build_agent_plan
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService
from rpg_backend.responses_transport import ResponsesJSONResponse
from tests.auth_helpers import ensure_authenticated_client


def _cast() -> list[CastMember]:
    return [
        CastMember(
            character_id="mira",
            display_name="Mira",
            role="Cofounder",
            relation_to_protagonist="Player role",
        ),
        CastMember(
            character_id="evan",
            display_name="Evan",
            role="Witness",
            relation_to_protagonist="Former partner with leverage",
            hidden_objective="Push Mira into admitting the board knew.",
            leverage_over_player="A draft memo that contradicts the player's story.",
            leverages_over_other_npcs=[
                NPCLeverageOverNPC(
                    target_npc_id="mira",
                    leverage="Knows Mira authorized the first leak.",
                )
            ],
        ),
    ]


def _player_role() -> PlayerRole:
    return PlayerRole(
        role_id="founder",
        label="Founder",
        public_persona="Cofounder under pressure",
        hidden_objective="Keep the audit from becoming a cover-up.",
        leverages_over_npcs=[
            PlayerLeverageOverNPC(
                npc_id="evan",
                leverage="Proof that Evan signed the side letter first.",
            )
        ],
        starting_assets=["sealed audit packet"],
    )


def _opening_options() -> list[StoryOption]:
    return [
        StoryOption(label="Let the witness speak", hint="Trade control for trust", handle="witness")
    ]


def _create_template_and_session(
    repo: NarrativeRepository,
    *,
    template_id: str = "tmpl_agent_trace",
    session_id: str = "sess_agent_trace",
    player_user_id: str = "local-dev",
    difficulty: str = "gauntlet",
) -> None:
    repo.create_template(
        template_id=template_id,
        owner_user_id="usr_owner",
        seed="A cofounder announces the secret merger before the audit is ready.",
        title="Merger Test",
        cast=_cast(),
        advisor_persona="A calm strategy coach.",
        opening_passage="The control room goes quiet.",
        opening_options=_opening_options(),
        player_goals=[
            PlayerGoal(goal="Keep the vote alive", stakes="The company may collapse.")
        ],
        failure_conditions=[],
        player_role_options=[_player_role()],
        visibility="public",
        language="en",
    )
    repo.create_session(
        session_id=session_id,
        template_id=template_id,
        player_user_id=player_user_id,
        turn_budget=8,
        difficulty=difficulty,  # type: ignore[arg-type]
        selected_player_role_id="founder",
    )
    repo.append_story_message(
        session_id,
        StoryMessage(
            ord=0,
            role="narrator",
            content="The control room goes quiet.",
            options=_opening_options(),
        ),
    )


def _append_agent_plan_event(repo: NarrativeRepository, session_id: str) -> AgentPlan:
    plan = build_agent_plan(
        cast=_cast(),
        history=repo.list_story_messages(session_id),
        turn_index=2,
        turn_budget=8,
        difficulty="gauntlet",
        player_role=_player_role(),
        current_inventory=["sealed audit packet"],
        narrator_ord=2,
    )
    repo.append_agent_event(
        session_id,
        ord_value=2,
        event_type="agent_plan",
        payload=plan,
    )
    return plan


def test_agent_plan_schema_is_versioned_and_compact() -> None:
    plan = build_agent_plan(
        cast=_cast(),
        history=[
            StoryMessage(ord=0, role="narrator", content="Opening.", options=[]),
            StoryMessage(ord=1, role="player", content="I keep the memo visible.", options=[]),
        ],
        turn_index=2,
        turn_budget=8,
        difficulty="gauntlet",
        player_role=_player_role(),
        current_inventory=["sealed audit packet", "board memo"],
        narrator_ord=2,
    )

    assert plan.schema_version == "agent_plan.v1"
    assert plan.source == "deterministic_v1"
    assert plan.director.stage_phase == "pressure"
    assert plan.director.expected_pressure == "medium"
    assert plan.npc_intents[0].npc_id == "evan"
    assert len(plan.director.focus_window_npc_ids) <= 5
    assert "evan" in plan.director.focus_window_npc_ids
    assert plan.memory.current_inventory_count == 2
    assert "history" not in plan.model_dump()


def test_repository_agent_event_round_trips(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo)
    plan = build_agent_plan(
        cast=_cast(),
        history=[StoryMessage(ord=0, role="narrator", content="Opening.", options=[])],
        turn_index=2,
        turn_budget=8,
        difficulty="gauntlet",
        player_role=_player_role(),
        current_inventory=["sealed audit packet"],
        narrator_ord=2,
    )

    event = repo.append_agent_event(
        "sess_agent_trace",
        ord_value=2,
        event_type="agent_plan",
        payload=plan,
    )
    events = repo.list_agent_events("sess_agent_trace")

    assert event.event_index == 0
    assert len(events) == 1
    assert events[0].payload == plan


class _TurnOnlyResponder:
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
        assert operation_name == "narrative.advance_turn"
        return ResponsesJSONResponse(
            payload={
                "passage": "Evan taps the draft memo and asks why the board never saw it.",
                "options": [
                    {"label": "[Probe] Ask Evan who copied it", "hint": "Test the source", "handle": "probe"},
                    {"label": "[Counter] Show the audit seal", "hint": "Spend pressure", "handle": "seal"},
                    {"label": "[Watch] Let Mira answer first", "hint": "Delay", "handle": "watch"},
                ],
                "npc_pulse": [
                    {
                        "npc_id": "evan",
                        "state": "pressing the contradiction",
                        "shift": "wary",
                        "reason": "You kept the memo public.",
                    }
                ],
            },
            response_id="fake-turn",
            usage={},
            input_characters=len(str(user_payload)),
        )


def test_advance_persists_agent_plan_and_gates_response_trace_by_default(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo)
    # Make the next turn index 2, which is a pressure-stage gauntlet turn
    # that schedules an NPC agenda entry.
    repo.touch_session("sess_agent_trace", increment_turns=1)
    gateway = _TurnOnlyResponder()
    service = NarrativeService(repository=repo, gateway=gateway)

    response = service.advance(
        "sess_agent_trace",
        AdvanceTurnRequest(free_input="I keep the memo visible."),
        player_user_id="local-dev",
    )
    history = service.get_story_history("sess_agent_trace", player_user_id="local-dev")
    debug_history = service.get_story_history(
        "sess_agent_trace",
        player_user_id="local-dev",
        include_agent_trace=True,
    )
    events = repo.list_agent_events("sess_agent_trace")

    assert response.agent_plan is None
    assert response.agent_events == []
    assert gateway.calls[0]["user_payload"]["npc_agenda_this_turn"][0]["npc_id"] == "evan"
    assert [event.event_type for event in events] == [
        "agent_plan",
        "step_judge",
        "contract_judge",
    ]
    assert events[0].payload.narrator_ord == response.narrator_message.ord
    assert events[0].payload.npc_intents[0].npc_id == "evan"
    assert events[1].payload.status == "pass"
    assert events[2].payload.status == "pass"
    assert history.agent_events == []
    assert len(debug_history.agent_events) == 3
    assert debug_history.agent_events[0].payload == events[0].payload


def test_advance_with_missing_gateway_uses_deterministic_beta_turn(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo, difficulty="story")
    service = NarrativeService(repository=repo, gateway=None)

    response = service.advance(
        "sess_agent_trace",
        AdvanceTurnRequest(chosen_option_index=0),
        player_user_id="local-dev",
        include_agent_trace=True,
    )
    history = service.get_story_history("sess_agent_trace", player_user_id="local-dev")
    events = repo.list_agent_events("sess_agent_trace")

    assert response.player_message.content == "Let the witness speak"
    assert response.narrator_message.role == "narrator"
    assert response.narrator_message.options
    assert "AI service" not in response.narrator_message.content
    assert "fallback" not in response.narrator_message.content.casefold()
    assert history.session.turn_count == 1
    assert [event.event_type for event in events] == [
        "agent_plan",
        "step_judge",
        "contract_judge",
    ]
    assert events[1].payload.status == "pass"
    assert events[2].payload.status == "pass"
    assert response.agent_plan is not None
    assert response.agent_events


def test_turn_endpoint_with_missing_gateway_returns_deterministic_beta_turn(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    client = TestClient(main_module.app)
    login = ensure_authenticated_client(client, display_name="Beta Player")
    user_id = login.json()["user"]["user_id"]
    session_id = f"sess_missing_gateway_{uuid4().hex[:8]}"
    _create_template_and_session(
        repo,
        template_id=f"tmpl_missing_gateway_{uuid4().hex[:8]}",
        session_id=session_id,
        player_user_id=user_id,
        difficulty="story",
    )
    service = NarrativeService(repository=repo, gateway=None)
    original_service = main_module.narrative_service
    main_module.narrative_service = service

    try:
        response = client.post(
            f"/narrative/sessions/{session_id}/story/turns",
            json={"chosen_option_index": 0},
        )
    finally:
        main_module.narrative_service = original_service

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["player_message"]["content"] == "Let the witness speak"
    assert body["narrator_message"]["role"] == "narrator"
    assert body["narrator_message"]["options"]
    assert "AI service" not in body["narrator_message"]["content"]


def test_advance_can_return_agent_plan_for_debug_trace(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo, session_id="sess_agent_trace_debug")
    repo.touch_session("sess_agent_trace_debug", increment_turns=1)
    service = NarrativeService(repository=repo, gateway=_TurnOnlyResponder())

    response = service.advance(
        "sess_agent_trace_debug",
        AdvanceTurnRequest(free_input="I keep the memo visible."),
        player_user_id="local-dev",
        include_agent_trace=True,
    )

    assert response.agent_plan is not None
    assert response.agent_plan.narrator_ord == response.narrator_message.ord
    assert response.agent_plan.npc_intents[0].npc_id == "evan"
    assert [event.event_type for event in response.agent_events] == [
        "agent_plan",
        "step_judge",
        "contract_judge",
    ]
    assert response.agent_events[0].payload == response.agent_plan


def test_story_endpoint_requires_reviewer_for_agent_trace(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    client = TestClient(main_module.app)
    login = ensure_authenticated_client(client, display_name="Trace Owner")
    user_id = login.json()["user"]["user_id"]
    session_id = f"sess_trace_route_{uuid4().hex[:8]}"
    _create_template_and_session(
        repo,
        template_id=f"tmpl_trace_route_{uuid4().hex[:8]}",
        session_id=session_id,
        player_user_id=user_id,
    )
    _append_agent_plan_event(repo, session_id)
    service = NarrativeService(repository=repo, gateway=_TurnOnlyResponder())
    original_service = main_module.narrative_service
    main_module.narrative_service = service

    try:
        response = client.get(f"/narrative/sessions/{session_id}/story?agent_trace=true")
    finally:
        main_module.narrative_service = original_service
        main_module.get_settings.cache_clear()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "agent_trace_forbidden"


def test_story_endpoint_returns_agent_trace_for_authorized_reviewer(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_AGENT_TRACE_REVIEWER_USERNAMES", "portfolio_reviewer")
    main_module.get_settings.cache_clear()
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    client = TestClient(main_module.app)
    login = client.post("/auth/login", json={"username": "portfolio_reviewer"})
    assert login.status_code == 200
    assert login.json()["can_view_agent_trace"] is True
    user_id = login.json()["user"]["user_id"]
    session_id = f"sess_trace_reviewer_{uuid4().hex[:8]}"
    _create_template_and_session(
        repo,
        template_id=f"tmpl_trace_reviewer_{uuid4().hex[:8]}",
        session_id=session_id,
        player_user_id=user_id,
    )
    expected_plan = _append_agent_plan_event(repo, session_id)
    service = NarrativeService(repository=repo, gateway=_TurnOnlyResponder())
    original_service = main_module.narrative_service
    main_module.narrative_service = service

    try:
        default_response = client.get(f"/narrative/sessions/{session_id}/story")
        trace_response = client.get(f"/narrative/sessions/{session_id}/story?agent_trace=true")
        replay_response = client.get(f"/narrative/sessions/{session_id}/replay?agent_trace=true")
    finally:
        main_module.narrative_service = original_service
        main_module.get_settings.cache_clear()

    assert default_response.status_code == 200
    assert default_response.json()["agent_events"] == []
    assert trace_response.status_code == 200
    trace_events = trace_response.json()["agent_events"]
    assert len(trace_events) == 1
    assert trace_events[0]["payload"]["schema_version"] == expected_plan.schema_version
    assert trace_events[0]["payload"]["source"] == expected_plan.source
    assert replay_response.status_code == 200
    assert "agent_events" not in replay_response.json()
    assert "agent_plan" not in replay_response.json()


def test_advance_endpoint_rejects_unauthorized_agent_trace_before_runtime(monkeypatch) -> None:
    class RuntimeShouldNotRun:
        validate_called = False
        estimated = False
        advanced = False

        def validate_advance_request(self, *_args, **_kwargs) -> None:
            self.validate_called = True
            raise AssertionError("trace auth should run before turn validation")

        def estimate_advance_llm_operation_cost(self, *_args, **_kwargs) -> int:
            self.estimated = True
            raise AssertionError("trace auth should run before quota estimate")

        def advance(self, *_args, **_kwargs):  # noqa: ANN202
            self.advanced = True
            raise AssertionError("trace auth should run before advance")

    client = TestClient(main_module.app)
    ensure_authenticated_client(client, display_name="Trace Ordinary")
    fake_service = RuntimeShouldNotRun()
    original_service = main_module.narrative_service
    main_module.narrative_service = fake_service

    try:
        response = client.post(
            "/narrative/sessions/sess_trace_blocked/story/turns?agent_trace=true",
            json={"free_input": "I test the trace gate."},
        )
    finally:
        main_module.narrative_service = original_service

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "agent_trace_forbidden"
    assert fake_service.validate_called is False
    assert fake_service.estimated is False
    assert fake_service.advanced is False
