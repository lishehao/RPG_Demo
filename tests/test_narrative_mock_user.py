from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

import rpg_backend.main as main_module
from rpg_backend.narrative.contracts import (
    AdvanceTurnRequest,
    AdvanceTurnResponse,
    CastMember,
    NPCLeverageOverNPC,
    NPCPulse,
    NarrativeSessionSummary,
    NarrativeTemplateSummary,
    PlayerGoal,
    PlayerLeverageOverNPC,
    PlayerRole,
    StartSessionResponse,
    StoryHistoryResponse,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService
from rpg_backend.responses_transport import ResponsesJSONResponse
from tools.rpg_eval.narrative_mock_user import (
    EpisodeMemory,
    MockUserAction,
    MockUserConfig,
    MockUserRuntimeError,
    MockTurnTrace,
    TestClientNarrativeAdapter,
    _memory_after_turn,
    choose_mock_user_action,
    judge_episode_trajectory,
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


class _TurnResponder:
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


class _AlreadyCompleteAdapter:
    def get_template(self, template_id: str) -> NarrativeTemplateSummary:
        raise AssertionError(f"unexpected template lookup: {template_id}")

    def start_session(
        self,
        template_id: str,
        *,
        player_role_index: int | None,
        turn_budget: int,
    ) -> StartSessionResponse:
        raise AssertionError(f"unexpected session start: {template_id}")

    def get_story(self, session_id: str, *, agent_trace: bool) -> StoryHistoryResponse:
        del agent_trace
        return StoryHistoryResponse(
            template=NarrativeTemplateSummary(
                template_id="tmpl_done",
                owner_user_id="usr_owner",
                seed="done",
                title="Done",
                cast=_cast(),
                advisor_persona="A calm strategy coach.",
                player_goals=[],
                failure_conditions=[],
                player_role_options=[_player_role()],
                visibility="public",
                language="en",
                play_count=1,
                created_at="2026-06-01T00:00:00Z",
            ),
            session=NarrativeSessionSummary(
                session_id=session_id,
                template_id="tmpl_done",
                template_title="Done",
                template_seed="done",
                player_user_id="local-dev",
                turn_count=4,
                turn_budget=4,
                difficulty="gauntlet",
                player_role=_player_role(),
                ending_label="Complete",
                ending_subtitle="Done",
                ending_tier="compromised",
                created_at="2026-06-01T00:00:00Z",
                last_active_at="2026-06-01T00:00:00Z",
            ),
            messages=[
                StoryMessage(
                    ord=0,
                    role="narrator",
                    content="The episode is already complete.",
                    options=[],
                )
            ],
            agent_events=[],
        )

    def advance_turn(
        self,
        session_id: str,
        payload: AdvanceTurnRequest,
        *,
        agent_trace: bool,
    ) -> AdvanceTurnResponse:
        raise AssertionError(f"unexpected advance: {session_id} {payload} {agent_trace}")


class _TransientTurnFailureAdapter:
    def __init__(self, *, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.advance_calls = 0
        self._advanced = False
        self._player = StoryMessage(ord=1, role="player", content="Show the memo.")
        self._narrator = StoryMessage(
            ord=2,
            role="narrator",
            content="Evan studies the audit packet and admits the memo matters.",
            options=[],
            npc_pulse=[NPCPulse(npc_id="evan", state="cornered", shift="wary")],
        )

    def get_template(self, template_id: str) -> NarrativeTemplateSummary:
        raise AssertionError(f"unexpected template lookup: {template_id}")

    def start_session(
        self,
        template_id: str,
        *,
        player_role_index: int | None,
        turn_budget: int,
    ) -> StartSessionResponse:
        raise AssertionError(f"unexpected session start: {template_id} {player_role_index} {turn_budget}")

    def _session(self, session_id: str) -> NarrativeSessionSummary:
        return NarrativeSessionSummary(
            session_id=session_id,
            template_id="tmpl_retry",
            template_title="Retry",
            template_seed="retry",
            player_user_id="local-dev",
            turn_count=1 if self._advanced else 0,
            turn_budget=1,
            difficulty="story",
            player_role=_player_role(),
            ending_label="Complete" if self._advanced else None,
            ending_subtitle="Done" if self._advanced else None,
            ending_tier="victory" if self._advanced else None,
            created_at="2026-06-01T00:00:00Z",
            last_active_at="2026-06-01T00:00:00Z",
        )

    def get_story(self, session_id: str, *, agent_trace: bool) -> StoryHistoryResponse:
        del agent_trace
        messages = [
            StoryMessage(
                ord=0,
                role="narrator",
                content="The control room goes quiet.",
                options=_opening_options(),
                npc_pulse=[NPCPulse(npc_id="evan", state="watching", shift="steady")],
            )
        ]
        if self._advanced:
            messages.extend([self._player, self._narrator])
        return StoryHistoryResponse(
            template=NarrativeTemplateSummary(
                template_id="tmpl_retry",
                owner_user_id="usr_owner",
                seed="retry",
                title="Retry",
                cast=_cast(),
                advisor_persona="A calm strategy coach.",
                player_goals=[],
                failure_conditions=[],
                player_role_options=[_player_role()],
                visibility="public",
                language="en",
                play_count=1,
                created_at="2026-06-01T00:00:00Z",
            ),
            session=self._session(session_id),
            messages=messages,
            agent_events=[],
        )

    def advance_turn(
        self,
        session_id: str,
        payload: AdvanceTurnRequest,
        *,
        agent_trace: bool,
    ) -> AdvanceTurnResponse:
        del session_id, payload, agent_trace
        self.advance_calls += 1
        if self.advance_calls <= self.failures_before_success:
            raise RuntimeError("POST /turns failed: 502 {\"error\":{\"code\":\"llm_invalid_json\"}}")
        self._advanced = True
        return AdvanceTurnResponse(
            player_message=self._player,
            narrator_message=self._narrator,
            is_complete=True,
        )


def test_mock_user_role_selection_and_leverage_action_are_deterministic(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template_and_session(
        repo,
        template_id="tmpl_mock_policy",
        session_id="sess_mock_policy",
        player_user_id="local-dev",
    )
    service = NarrativeService(repository=repo, gateway=_TurnResponder())
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
    repeated = choose_mock_user_action(
        history,
        config,
        turn_index=1,
        memory=EpisodeMemory(played_leverage_cards=[action.played_leverage_summary]),
    )
    assert repeated.played_leverage is None

    cautious = choose_mock_user_action(
        history,
        MockUserConfig(policy="cautious_negotiator", turn_budget=1),
        turn_index=0,
    )
    assert cautious.chosen_option_index == 0

    random_config = MockUserConfig(policy="random_seeded", seed=9, turn_budget=1)
    assert choose_mock_user_action(history, random_config, turn_index=0) == choose_mock_user_action(
        history,
        random_config,
        turn_index=0,
    )

    scripted = choose_mock_user_action(
        history,
        MockUserConfig(policy="regression_script", turn_budget=2),
        turn_index=1,
    )
    assert scripted.chosen_option_index == 1


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
    gateway = _TurnResponder()
    service = NarrativeService(repository=repo, gateway=gateway)
    original_service = main_module.narrative_service
    main_module.narrative_service = service
    output_path = tmp_path / "mock_user_episode.jsonl"
    summary_path = tmp_path / "mock_user_episode_summary.json"

    try:
        adapter = TestClientNarrativeAdapter(client, login=False)
        result = run_mock_user_episode(
            MockUserConfig(
                session_id=session_id,
                policy="leverage_seeker",
                leverage_policy="opportunistic",
                turn_budget=1,
                trace_output_path=str(output_path),
                summary_output_path=str(summary_path),
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
    assert [event.action_type for event in turn.action_loop] == [
        "observe",
        "update_memory",
        "choose_action",
        "play_turn",
        "collect_events",
        "collect_judges",
    ]
    assert turn.memory_summary["played_leverage_cards"] == [
        {
            "card_id": "founder-evan-0",
            "target_npc_id": "evan",
            "action": "reveal",
        }
    ]
    assert turn.step_judge_status == "pass"
    assert turn.contract_judge_status == "pass"
    assert result.trajectory_judge.status == "pass"
    assert result.summary.step_status_counts == {"pass": 1}
    assert result.summary.contract_status_counts == {"pass": 1}
    assert result.summary.trajectory_status == "pass"
    assert result.episode_memory.latest_narrator_ord == turn.narrator_ord
    assert result.action_loop[-2].action_type == "judge_trajectory"
    assert result.action_loop[-1].action_type == "summarize_episode"
    assert gateway.calls

    rows = [json.loads(line) for line in output_path.read_text().splitlines()]
    assert [row["record_type"] for row in rows] == [
        "loop_event",
        "loop_event",
        "loop_event",
        "loop_event",
        "loop_event",
        "loop_event",
        "loop_event",
        "loop_event",
        "turn",
        "trajectory_judge",
        "summary",
    ]
    assert rows[-2]["payload"]["status"] == "pass"
    artifact = output_path.read_text()
    assert "Proof that Evan signed the side letter first" not in artifact
    assert "founder-evan-0" in artifact
    summary_artifact = json.loads(summary_path.read_text())
    assert summary_artifact["trajectory_judge"]["status"] == "pass"
    assert summary_artifact["loop_event_count"] == len(result.action_loop)


def test_live_mock_user_retries_transient_turn_failure_once(tmp_path) -> None:
    trace_path = tmp_path / "retry_episode.jsonl"
    summary_path = tmp_path / "retry_summary.json"
    adapter = _TransientTurnFailureAdapter(failures_before_success=1)

    result = run_mock_user_episode(
        MockUserConfig(
            session_id="sess_retry",
            mode="live",
            turn_budget=1,
            trace_output_path=str(trace_path),
            summary_output_path=str(summary_path),
        ),
        adapter,
    )

    assert adapter.advance_calls == 2
    assert result.summary.runtime_retry_count == 1
    retry_events = [event for event in result.action_loop if event.action_type == "runtime_retry"]
    assert len(retry_events) == 1
    assert retry_events[0].payload["will_retry"] is True
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    assert any(
        row["record_type"] == "loop_event"
        and row["payload"]["action_type"] == "runtime_retry"
        for row in rows
    )
    assert json.loads(summary_path.read_text())["summary"]["runtime_retry_count"] == 1


def test_live_mock_user_repeated_turn_failure_raises_with_retry_evidence() -> None:
    adapter = _TransientTurnFailureAdapter(failures_before_success=2)

    with pytest.raises(MockUserRuntimeError) as exc_info:
        run_mock_user_episode(
            MockUserConfig(session_id="sess_retry_fail", mode="live", turn_budget=1),
            adapter,
        )

    assert adapter.advance_calls == 2
    assert exc_info.value.session_id == "sess_retry_fail"
    assert exc_info.value.runtime_retry_count == 1
    retry_events = [
        event for event in exc_info.value.action_loop if event.action_type == "runtime_retry"
    ]
    assert [event.payload["will_retry"] for event in retry_events] == [True, False]
    assert "llm_invalid_json" in str(exc_info.value)


def test_trajectory_judge_fails_empty_episode() -> None:
    result = run_mock_user_episode(
        MockUserConfig(session_id="already_done", turn_budget=1),
        _AlreadyCompleteAdapter(),
    )

    assert result.turns == []
    assert result.trajectory_judge.status == "fail"
    assert result.summary.trajectory_status == "fail"
    assert any(check.code == "episode_progressed" for check in result.trajectory_judge.checks)


def test_trajectory_judge_warns_on_flat_low_impact_episode() -> None:
    traces = [
        MockTurnTrace(
            turn_index=index,
            narrator_ord=index * 2 + 2,
            role_id="founder",
            observation_summary={"latest_narrator_ord": index},
            memory_before={"objective_progress": "low"},
            selected_action={"selected_option_handle": "wait", "decision_reason": "test"},
            runtime_output_summary={
                "narrator_ord": index * 2 + 2,
                "passage": "The room waits.",
                "option_count": 2,
                "npc_pulse": [{"npc_id": "evan", "shift": "steady", "state": "waiting"}],
                "inventory_delta": {"added_count": 0, "removed_count": 0, "has_reason": False},
            },
            agent_plan_summary={
                "available": True,
                "stage_phase": "hook",
                "turn_budget": 6,
                "active_npc_ids": ["evan"],
            },
            memory_after={"objective_progress": "low"},
            memory_summary={"objective_progress": "low"},
            step_judge_status="pass",
            contract_judge_status="pass",
        )
        for index in range(3)
    ]
    result = judge_episode_trajectory(
        traces=traces,
        memory=EpisodeMemory(
            objective="Keep the vote alive",
            observed_npc_ids=["evan"],
            objective_progress="low",
        ),
        config=MockUserConfig(session_id="sess_warn", turn_budget=3),
        ending_detected=False,
    )

    assert result.status == "warn"
    codes = {check.code for check in result.checks if check.status == "warn"}
    assert {"stage_progression_flat", "objective_progress", "low_divergence_no_impact"}.issubset(codes)


def test_episode_memory_keeps_highest_objective_progress_signal() -> None:
    config = MockUserConfig(
        session_id="sess_progress",
        objective="Stop the secret merger while exposing who altered the audit packet.",
    )
    action = MockUserAction(
        chosen_option_index=0,
        selected_option_label="Press the audit evidence.",
        decision_reason="test",
    )
    memory = EpisodeMemory(objective=config.objective, objective_progress="low")

    progressed = _memory_after_turn(
        memory,
        action=action,
        narrator_message=StoryMessage(
            ord=2,
            role="narrator",
            content="The secret merger and altered audit packet are exposed.",
        ),
        step=None,
        contract=None,
        config=config,
    )
    later_low_signal = _memory_after_turn(
        progressed,
        action=action,
        narrator_message=StoryMessage(
            ord=4,
            role="narrator",
            content="The room falls quiet while everyone waits.",
        ),
        step=None,
        contract=None,
        config=config,
    )

    assert progressed.objective_progress == "high"
    assert later_low_signal.objective_progress == "high"


def test_trajectory_judge_fails_replayed_leverage_card() -> None:
    card = {
        "card_id": "founder-evan-0",
        "target_npc_id": "evan",
        "action": "reveal",
    }
    trace = MockTurnTrace(
        turn_index=0,
        narrator_ord=2,
        role_id="founder",
        observation_summary={"latest_narrator_ord": 0},
        memory_before={"objective_progress": "medium"},
        selected_action={
            "selected_option_handle": "show",
            "played_leverage": card,
            "decision_reason": "test",
        },
        runtime_output_summary={
            "narrator_ord": 2,
            "passage": "The room treats the evidence as material.",
            "option_count": 2,
            "npc_pulse": [{"npc_id": "evan", "shift": "wary", "state": "watching"}],
            "inventory_delta": {"added_count": 0, "removed_count": 0, "has_reason": False},
        },
        agent_plan_summary={
            "available": True,
            "stage_phase": "pressure",
            "active_npc_ids": ["evan"],
        },
        memory_after={"objective_progress": "medium"},
        memory_summary={"played_leverage_cards": [card, card]},
        step_judge_status="pass",
        contract_judge_status="pass",
    )
    result = judge_episode_trajectory(
        traces=[trace],
        memory=EpisodeMemory(
            objective="Keep the vote alive",
            observed_npc_ids=["evan"],
            objective_progress="medium",
            played_leverage_cards=[card, card],
        ),
        config=MockUserConfig(
            session_id="sess_duplicate_card",
            turn_budget=1,
            leverage_policy="opportunistic",
        ),
        ending_detected=False,
    )

    assert result.status == "fail"
    assert any(
        check.code == "leverage_card_reuse" and check.status == "fail"
        for check in result.checks
    )


def test_trajectory_judge_records_target_leverage_payoff_evidence() -> None:
    card = {
        "card_id": "founder-evan-0",
        "target_npc_id": "evan",
        "action": "reveal",
    }
    trace = MockTurnTrace(
        turn_index=0,
        narrator_ord=2,
        role_id="founder",
        observation_summary={"latest_narrator_ord": 0},
        memory_before={"objective_progress": "medium"},
        selected_action={
            "selected_option_handle": "show",
            "played_leverage": card,
            "decision_reason": "test",
        },
        runtime_output_summary={
            "narrator_ord": 2,
            "passage": "The room treats the evidence as material.",
            "option_count": 2,
            "npc_pulse": [{"npc_id": "evan", "shift": "wary", "state": "watching"}],
            "inventory_delta": {"added_count": 0, "removed_count": 0, "has_reason": False},
        },
        agent_plan_summary={
            "available": True,
            "stage_phase": "pressure",
            "active_npc_ids": ["evan"],
        },
        memory_after={"objective_progress": "medium"},
        memory_summary={"played_leverage_cards": [card]},
        step_judge_status="pass",
        contract_judge_status="pass",
    )
    result = judge_episode_trajectory(
        traces=[trace],
        memory=EpisodeMemory(
            objective="Keep the vote alive",
            observed_npc_ids=["evan"],
            objective_progress="medium",
            played_leverage_cards=[card],
        ),
        config=MockUserConfig(
            session_id="sess_payoff_evidence",
            turn_budget=1,
            leverage_policy="opportunistic",
        ),
        ending_detected=False,
    )

    payoff_check = next(
        check for check in result.checks if check.code == "leverage_payoff_continuity"
    )
    assert payoff_check.status == "pass"
    assert payoff_check.evidence
    assert "card_id:founder-evan-0" in payoff_check.evidence[0]
    assert "target_npc_id:evan" in payoff_check.evidence[0]
    assert "pulse_shift:wary" in payoff_check.evidence[0]
