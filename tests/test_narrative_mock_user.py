from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

import rpg_backend.main as main_module
from rpg_backend.narrative.contracts import (
    CastMember,
    NPCLeverageOverNPC,
    NPCPulse,
    PlayerGoal,
    PlayerLeverageOverNPC,
    PlayerRole,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService
from rpg_backend.responses_transport import ResponsesJSONResponse
from tools.rpg_eval.narrative_mock_user import (
    MockUserConfig,
    TestClientNarrativeAdapter,
    choose_mock_user_action,
    run_mock_user_episode,
    select_role_index,
)


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


def _player_role(role_id: str = "founder", label: str = "Founder") -> PlayerRole:
    return PlayerRole(
        role_id=role_id,
        label=label,
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
        StoryOption(label="Wait for Mira", hint="Delay the confrontation", handle="wait"),
        StoryOption(
            label="Show the memo evidence",
            hint="Use proof to pressure Evan",
            handle="show",
        ),
    ]


def _create_template_and_session(
    repo: NarrativeRepository,
    *,
    template_id: str,
    session_id: str,
    player_user_id: str,
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
        player_role_options=[_player_role(), _player_role("observer", "Observer")],
        visibility="public",
        language="en",
    )
    repo.create_session(
        session_id=session_id,
        template_id=template_id,
        player_user_id=player_user_id,
        turn_budget=4,
        difficulty="gauntlet",
        selected_player_role_id="founder",
    )
    repo.append_story_message(
        session_id,
        StoryMessage(
            ord=0,
            role="narrator",
            content="The control room goes quiet.",
            options=_opening_options(),
            npc_pulse=[NPCPulse(npc_id="evan", state="watching the memo", shift="wary")],
        ),
    )


class _TurnGateway:
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
                    {
                        "label": "Ask Evan who copied it",
                        "hint": "Test the source",
                        "handle": "probe",
                    },
                    {
                        "label": "Let Mira answer first",
                        "hint": "Delay",
                        "handle": "watch",
                    },
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
            response_id="mock-user-turn",
            usage={},
            input_characters=len(str(user_payload)),
        )


def test_mock_user_role_selection_and_leverage_action_are_deterministic(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(
        repo,
        template_id="tmpl_mock_policy",
        session_id="sess_mock_policy",
        player_user_id="local-dev",
    )
    service = NarrativeService(repository=repo, gateway=_TurnGateway())
    history = service.get_story_history(
        "sess_mock_policy",
        player_user_id="local-dev",
        include_agent_trace=True,
    )

    explicit = MockUserConfig(role_id="observer")
    assert select_role_index(history.template, explicit) == 1
    seeded = MockUserConfig(role_selection="random_seeded", seed=3)
    assert select_role_index(history.template, seeded) == select_role_index(
        history.template,
        seeded,
    )

    config = MockUserConfig(
        policy="leverage_seeker",
        leverage_policy="opportunistic",
        turn_budget=1,
        seed=11,
    )
    action = choose_mock_user_action(history, config, turn_index=0)

    assert action.chosen_option_index == 1
    assert action.played_leverage is not None
    assert action.played_leverage.npc_id == "evan"
    assert action.played_leverage_summary == {
        "card_id": "founder-evan-0",
        "target_npc_id": "evan",
        "action": "reveal",
    }
    assert "side letter" not in json.dumps(action.played_leverage_summary)


def test_mock_user_episode_collects_agent_and_judge_trace_via_api(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AGENT_TRACE_REVIEWER_USERNAMES", "portfolio_reviewer")
    main_module.get_settings.cache_clear()
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    client = TestClient(main_module.app)
    login = client.post("/auth/login", json={"username": "portfolio_reviewer"})
    assert login.status_code == 200
    assert login.json()["can_view_agent_trace"] is True
    session_id = f"sess_mock_trace_{uuid4().hex[:8]}"
    _create_template_and_session(
        repo,
        template_id=f"tmpl_mock_trace_{uuid4().hex[:8]}",
        session_id=session_id,
        player_user_id=login.json()["user"]["user_id"],
    )
    gateway = _TurnGateway()
    service = NarrativeService(repository=repo, gateway=gateway)
    original_service = main_module.narrative_service
    main_module.narrative_service = service
    output_path = tmp_path / "mock_user_episode.jsonl"

    try:
        adapter = TestClientNarrativeAdapter(client, login=False)
        result = run_mock_user_episode(
            MockUserConfig(
                session_id=session_id,
                policy="leverage_seeker",
                leverage_policy="opportunistic",
                turn_budget=1,
                trace_output_path=str(output_path),
            ),
            adapter,
        )
    finally:
        main_module.narrative_service = original_service
        main_module.get_settings.cache_clear()

    assert len(result.turns) == 1
    turn = result.turns[0]
    assert turn.agent_plan_summary["available"] is True
    assert turn.agent_plan_summary["stage_phase"] in {"hook", "opening", "pressure"}
    assert turn.step_judge_status == "pass"
    assert turn.contract_judge_status == "pass"
    assert result.summary.step_status_counts == {"pass": 1}
    assert result.summary.contract_status_counts == {"pass": 1}
    assert gateway.calls

    rows = [json.loads(line) for line in output_path.read_text().splitlines()]
    assert [row["record_type"] for row in rows] == ["turn", "summary"]
    artifact = output_path.read_text()
    assert "Proof that Evan signed the side letter first" not in artifact
    assert "founder-evan-0" in artifact
