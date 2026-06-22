from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

import rpg_backend.main as main_module
from rpg_backend.narrative import engine as narrative_engine
from rpg_backend.narrative.contracts import (
    AgentPlan,
    AdvanceTurnRequest,
    CastMember,
    NPCPulse,
    NPCLeverageOverNPC,
    PlayerGoal,
    PlayerLeverageOverNPC,
    PlayerRole,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.engine import build_agent_plan
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import (
    NarrativeService,
    _fallback_verb,
    _fallback_turn_action_phrase,
    _fallback_turn_options,
    _fallback_turn_pulses,
    _gameplay_forecast_for_option,
)
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


def test_fallback_turn_action_phrase_preserves_explicit_focus_target() -> None:
    assert _fallback_turn_action_phrase("Ask who benefits") == "your move to ask who benefits"
    assert (
        _fallback_turn_action_phrase("Mira Vale — Ask why she backed off")
        == "your move toward Mira Vale — Ask why she backed off"
    )


def test_fallback_verb_treats_title_case_character_names_as_singular() -> None:
    assert _fallback_verb("Lena Rojas", "recalculates", "recalculate") == "recalculates"
    assert _fallback_verb("Arthur Vance", "watches", "watch") == "watches"
    assert _fallback_verb("Lena Rojas and Arthur Vance", "reacts", "react") == "react"


def test_gameplay_forecast_turns_probe_actions_into_useful_signals() -> None:
    chips = _gameplay_forecast_for_option(
        StoryOption(
            label="Ask Lena what she saw before the feed went dark",
            hint="Probe",
            handle="ask witness",
        )
    )

    labels = [chip.label for chip in chips]
    assert "May reveal evidence" in labels
    assert "Read the room" not in labels


def test_gameplay_forecast_keeps_gentle_witness_actions_playable() -> None:
    chips = _gameplay_forecast_for_option(
        StoryOption(
            label="Invite the backup dancer to explain the handoff",
            hint="Let the witness speak",
            handle="witness",
        )
    )

    labels = [chip.label for chip in chips]
    assert "May reveal evidence" in labels
    assert "Trust +1" in labels
    assert "Read the room" not in labels


def test_fallback_turn_pulses_prioritize_explicit_action_target(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo)
    template = repo.get_template("tmpl_agent_trace")
    history = repo.list_story_messages("sess_agent_trace")
    plan = build_agent_plan(
        cast=template.cast,
        history=history,
        turn_index=2,
        turn_budget=8,
        difficulty="gauntlet",
        player_role=_player_role(),
        current_inventory=["sealed audit packet"],
        narrator_ord=2,
    )

    pulses = _fallback_turn_pulses(
        template=template,
        agent_plan=plan,
        played_leverage=None,
        profile="high_drama",
        player_action="Mira — Ask why she backed off",
    )

    assert [pulse.npc_id for pulse in pulses][:1] == ["mira"]


def test_fallback_turn_options_follow_latest_pulse_targets(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo)
    template = repo.get_template("tmpl_agent_trace")
    pulses = [
        NPCPulse(npc_id="mira", state="wary", shift="wary"),
        NPCPulse(npc_id="evan", state="wary", shift="wary"),
    ]

    options = _fallback_turn_options(
        template,
        "high_drama",
        pulses,
    )

    labels = [option.label for option in options]
    assert labels[0] == "[Probe] Ask Mira who benefits from this version"
    assert labels[1] == "[Counter] Put one concrete fact to Mira"
    assert labels[2] == "[Watch] Let Evan react to Mira"


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


def test_start_session_pads_sparse_opening_options(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "state.sqlite3"))
    repo.create_template(
        template_id="tmpl_sparse_opening",
        owner_user_id="usr_owner",
        seed="A cofounder announces the secret merger before the audit is ready.",
        title="Sparse Opening Test",
        cast=_cast(),
        advisor_persona="A calm strategy coach.",
        opening_passage="The boardroom waits for the final version.",
        opening_options=[
            StoryOption(
                label="[Probe] Ask who benefits from the version",
                hint="Tests Mira's account",
                handle="ask benefit",
            )
        ],
        player_goals=[
            PlayerGoal(goal="Keep the audit honest", stakes="The record may be buried.")
        ],
        failure_conditions=[],
        player_role_options=[_player_role()],
        visibility="public",
        language="en",
    )
    service = NarrativeService(repository=repo, gateway=None)

    response = service.start_session(
        "tmpl_sparse_opening",
        player_user_id="local-dev",
        turn_budget=8,
    )
    history = service.get_story_history(
        response.session.session_id,
        player_user_id="local-dev",
    )

    assert len(response.opening.options) == 3
    assert response.opening.options[0].label == "[Probe] Ask who benefits from the version"
    assert response.opening.options[1].label != response.opening.options[0].label
    assert len(history.messages[0].options) == 3


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


def test_turn_prompt_keeps_gameplay_metadata_optional_and_compact() -> None:
    prompt = narrative_engine._TURN_SYSTEM_PROMPT

    assert "gameplay_metadata 也是**可选**字段" in prompt
    assert "优先输出一个很小的 metadata block" in prompt
    assert "只写 1-3 个玩家可见条目即可" in prompt
    assert "next_action_context 只解释某个下一步为什么现在成立或更有针对性" in prompt
    assert "npc_id 必须来自 cast" in prompt
    assert "0-based" in prompt
    assert "不要输出空数组占位对象" in prompt
    assert "不能牺牲 passage/options 的质量" in prompt


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
                    {"label": "[Probe] Search evidence under pressure", "hint": "Risk the clock for proof", "handle": "probe"},
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
                "gameplay_metadata": {
                    "state_deltas": [
                        {
                            "label": "Sponsor leverage surfaced",
                            "tone": "unlock",
                            "target": "opportunity",
                            "confidence": "high",
                        },
                        {
                            "label": "Ghost reacts",
                            "tone": "cost",
                            "target": "npc",
                            "npc_id": "ghost",
                        },
                    ],
                    "clue_unlocks": [
                        {
                            "title": "Audit copy route",
                            "summary": "Evan's copy had to come from inside.",
                            "state": "usable",
                            "supports_option_index": 0,
                        },
                        {
                            "title": "Impossible index",
                            "supports_option_index": 99,
                        },
                    ],
                    "opportunity_unlocks": [
                        {
                            "title": "Private witness window",
                            "summary": "Evan can be isolated before the vote.",
                            "supports_option_index": 1,
                        }
                    ],
                    "next_action_context": [
                        {
                            "option_index": 0,
                            "reason": "Evan is focused on the copied memo.",
                        },
                        {
                            "option_index": 99,
                            "reason": "This should be rejected.",
                        },
                    ],
                    "motive_effect": {
                        "acknowledged": True,
                        "label": "Motive sharpened the public stance",
                    },
                },
            },
            response_id="fake-turn",
            usage={},
            input_characters=len(str(user_payload)),
        )


class _MissingGameplayMetadataResponder(_TurnOnlyResponder):
    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        operation_name: str,
        max_output_tokens: int | None = None,
    ) -> ResponsesJSONResponse:
        response = super().invoke_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            operation_name=operation_name,
            max_output_tokens=max_output_tokens,
        )
        response.payload.pop("gameplay_metadata", None)
        return response


class _InvalidGameplayMetadataResponder(_TurnOnlyResponder):
    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        operation_name: str,
        max_output_tokens: int | None = None,
    ) -> ResponsesJSONResponse:
        response = super().invoke_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            operation_name=operation_name,
            max_output_tokens=max_output_tokens,
        )
        response.payload["gameplay_metadata"] = {
            "state_deltas": [
                {
                    "label": "Invalid ghost pressure",
                    "tone": "cost",
                    "target": "npc",
                    "npc_id": "ghost",
                },
                {
                    "label": "Invalid target",
                    "tone": "gain",
                    "target": "not_a_track",
                },
            ],
            "clue_unlocks": [
                {"title": "Bad clue index", "supports_option_index": 99}
            ],
            "opportunity_unlocks": [
                {"title": "Bad opportunity state", "state": "spent"}
            ],
            "next_action_context": [
                {"option_index": 99, "reason": "This should be rejected."}
            ],
            "motive_effect": {"acknowledged": False, "label": "ignored"},
        }
        return response


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
    assert response.gameplay_envelope is not None
    assert response.gameplay_envelope.source == "live_enriched"
    assert response.gameplay_envelope.objective == "Keep the vote alive"
    assert response.gameplay_envelope.action_forecasts
    assert any(
        chip.label == "Time -1"
        for row in response.gameplay_envelope.action_forecasts
        for chip in row
    )
    assert response.gameplay_envelope.action_forecasts[0][0].label == "Why now"
    assert response.gameplay_envelope.action_forecasts[0][0].detail == (
        "Evan is focused on the copied memo."
    )
    assert len(response.gameplay_envelope.action_forecasts[0]) == 3
    assert all(
        chip.label != "This should be rejected." and chip.detail != "This should be rejected."
        for row in response.gameplay_envelope.action_forecasts
        for chip in row
    )
    assert any(chip.label == "Evan: wary" for chip in response.gameplay_envelope.impact)
    assert any(
        chip.label == "Sponsor leverage surfaced"
        for chip in response.gameplay_envelope.impact
    )
    assert any(
        chip.label == "Motive sharpened the public stance"
        for chip in response.gameplay_envelope.impact
    )
    assert any(
        chip.label == "Clue: Audit copy route"
        for chip in response.gameplay_envelope.opportunities
    )
    assert any(
        chip.label == "Opportunity: Private witness window"
        for chip in response.gameplay_envelope.opportunities
    )
    assert all(
        chip.label != "Ghost reacts"
        for chip in response.gameplay_envelope.impact
    )
    assert all(
        chip.label != "Clue: Impossible index"
        for chip in response.gameplay_envelope.opportunities
    )
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
    assert history.gameplay_envelope is not None
    assert history.gameplay_envelope.source == "live_enriched"
    assert history.gameplay_envelope.tracks
    assert history.gameplay_envelope.action_forecasts[0][0].label == "Why now"
    assert history.gameplay_envelope.action_forecasts[0][0].detail == (
        "Evan is focused on the copied memo."
    )
    assert any(
        chip.label == "Sponsor leverage surfaced"
        for chip in history.gameplay_envelope.impact
    )
    persisted_messages = repo.list_story_messages("sess_agent_trace")
    persisted_metadata = persisted_messages[-1].gameplay_metadata
    assert persisted_metadata is not None
    assert persisted_metadata.state_deltas[0].label == "Sponsor leverage surfaced"
    assert "gameplay_metadata" not in history.model_dump(mode="json")["messages"][-1]
    assert len(debug_history.agent_events) == 3
    assert debug_history.agent_events[0].payload == events[0].payload


def test_advance_keeps_backend_envelope_when_live_metadata_is_missing(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo)
    repo.touch_session("sess_agent_trace", increment_turns=1)
    service = NarrativeService(repository=repo, gateway=_MissingGameplayMetadataResponder())

    response = service.advance(
        "sess_agent_trace",
        AdvanceTurnRequest(free_input="I keep the memo visible."),
        player_user_id="local-dev",
    )

    assert response.gameplay_envelope is not None
    assert response.gameplay_envelope.source == "backend"
    assert any(chip.label == "Evan: wary" for chip in response.gameplay_envelope.impact)


def test_advance_drops_invalid_live_metadata_without_failing_turn(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo)
    repo.touch_session("sess_agent_trace", increment_turns=1)
    service = NarrativeService(repository=repo, gateway=_InvalidGameplayMetadataResponder())

    response = service.advance(
        "sess_agent_trace",
        AdvanceTurnRequest(free_input="I keep the memo visible."),
        player_user_id="local-dev",
    )

    assert response.narrator_message.content
    assert response.gameplay_envelope is not None
    assert response.gameplay_envelope.source == "backend"
    assert all(
        chip.label != "Invalid ghost pressure"
        for chip in response.gameplay_envelope.impact
    )
    assert all(
        chip.label != "Clue: Bad clue index"
        for chip in response.gameplay_envelope.opportunities
    )


def test_history_downgrades_malformed_persisted_gameplay_metadata(tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"
    repo = NarrativeRepository(str(db_path))
    _create_template_and_session(repo)

    # Simulate a legacy or hand-edited row that cannot be trusted. Reload
    # should ignore it and keep the backend-derived gameplay envelope.
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE narrative_story_messages
            SET gameplay_metadata_json = ?
            WHERE session_id = ? AND ord = ?
            """,
            ("{not-valid-json", "sess_agent_trace", 0),
        )
        conn.commit()

    messages = repo.list_story_messages("sess_agent_trace")
    assert messages[0].gameplay_metadata is None

    service = NarrativeService(repository=repo, gateway=_MissingGameplayMetadataResponder())
    history = service.get_story_history("sess_agent_trace", player_user_id="local-dev")

    assert history.gameplay_envelope is not None
    assert history.gameplay_envelope.source == "backend"


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


def test_final_turn_with_missing_gateway_completes_with_local_ending(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo, difficulty="story")
    repo.touch_session("sess_agent_trace", increment_turns=7)
    service = NarrativeService(repository=repo, gateway=None)

    response = service.advance(
        "sess_agent_trace",
        AdvanceTurnRequest(chosen_option_index=0),
        player_user_id="local-dev",
    )
    session = repo.get_session("sess_agent_trace")

    assert response.is_complete is True
    assert response.ending is not None
    assert response.ending.label == "决裂"
    assert "[Probe]" not in response.ending.passage
    assert "fallback" not in response.ending.passage.casefold()
    assert "AI service" not in response.ending.passage
    assert session.turn_count == 8
    assert session.turn_budget == 8
    assert session.ending_label == "决裂"


def test_history_repairs_budget_exhausted_session_without_ending(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(repo, difficulty="story")
    repo.touch_session("sess_agent_trace", increment_turns=9)
    service = NarrativeService(repository=repo, gateway=None)

    history = service.get_story_history("sess_agent_trace", player_user_id="local-dev")
    session = repo.get_session("sess_agent_trace")

    assert history.session.turn_count == 8
    assert history.session.turn_budget == 8
    assert history.session.ending_label == "决裂"
    assert session.ending_label == "决裂"
    assert session.turn_count == 9
    with pytest.raises(Exception) as exc_info:
        service.validate_advance_request(
            "sess_agent_trace",
            AdvanceTurnRequest(chosen_option_index=0),
            player_user_id="local-dev",
        )
    assert getattr(exc_info.value, "code", "") == "session_complete"


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
    assert body["gameplay_envelope"]["source"] == "backend"
    assert body["gameplay_envelope"]["tracks"]
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


def test_llm_event_endpoint_requires_reviewer_access(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    client = TestClient(main_module.app)
    login = ensure_authenticated_client(client, display_name="Telemetry Owner")
    user_id = login.json()["user"]["user_id"]
    session_id = f"sess_llm_trace_blocked_{uuid4().hex[:8]}"
    _create_template_and_session(
        repo,
        template_id=f"tmpl_llm_trace_blocked_{uuid4().hex[:8]}",
        session_id=session_id,
        player_user_id=user_id,
    )
    repo.append_llm_call_event(
        operation="narrative.advance_turn",
        status="success",
        source_label="live",
        latency_ms=123,
        input_tokens=20,
        cached_input_tokens=5,
        output_tokens=10,
        total_tokens=30,
        user_id=user_id,
        session_id=session_id,
    )
    service = NarrativeService(repository=repo, gateway=_TurnOnlyResponder())
    original_service = main_module.narrative_service
    main_module.narrative_service = service

    try:
        response = client.get(f"/narrative/sessions/{session_id}/llm-events")
    finally:
        main_module.narrative_service = original_service

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "agent_trace_forbidden"


def test_llm_event_endpoint_returns_sanitized_rows_for_reviewer(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_AGENT_TRACE_REVIEWER_USERNAMES", "portfolio_reviewer")
    main_module.get_settings.cache_clear()
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    client = TestClient(main_module.app)
    login = client.post("/auth/login", json={"username": "portfolio_reviewer"})
    assert login.status_code == 200
    user_id = login.json()["user"]["user_id"]
    session_id = f"sess_llm_trace_allowed_{uuid4().hex[:8]}"
    _create_template_and_session(
        repo,
        template_id=f"tmpl_llm_trace_allowed_{uuid4().hex[:8]}",
        session_id=session_id,
        player_user_id=user_id,
    )
    repo.append_llm_call_event(
        operation="narrative.advance_turn",
        status="success",
        source_label="live",
        latency_ms=123,
        operation_latency_ms=150,
        input_tokens=20,
        cached_input_tokens=5,
        output_tokens=10,
        total_tokens=30,
        retry_count=1,
        repair_count=0,
        response_id="safe-response-id",
        user_id=user_id,
        session_id=session_id,
    )
    service = NarrativeService(repository=repo, gateway=_TurnOnlyResponder())
    original_service = main_module.narrative_service
    main_module.narrative_service = service

    try:
        response = client.get(f"/narrative/sessions/{session_id}/llm-events")
    finally:
        main_module.narrative_service = original_service
        main_module.get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["operation"] == "narrative.advance_turn"
    assert body["items"][0]["source_label"] == "live"
    assert body["items"][0]["latency_ms"] == 123
    assert body["items"][0]["input_tokens"] == 20
    assert body["items"][0]["cached_input_tokens"] == 5
    assert body["items"][0]["output_tokens"] == 10
    assert body["items"][0]["total_tokens"] == 30
    serialized = response.text
    assert "api_key" not in serialized
    assert "Authorization" not in serialized


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
