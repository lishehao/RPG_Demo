from __future__ import annotations

from rpg_backend.narrative.contracts import (
    AgentPlan,
    CastMember,
    DirectorDecision,
    InventoryDelta,
    MemorySnapshot,
    NPCIntent,
    NPCLeverageOverNPC,
    NPCPulse,
    PlayedLeverageCard,
    PlayerLeverageOverNPC,
    PlayerRole,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.judges import judge_contract, judge_step
from rpg_backend.narrative.repository import NarrativeRepository


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


def _option() -> StoryOption:
    return StoryOption(label="Ask who copied the memo", hint="Probe the source", handle="probe")


def _plan(
    *,
    active_npc_ids: list[str] | None = None,
    twist_kind: str | None = None,
    stage_phase: str = "pressure",
    expected_pressure: str = "medium",
) -> AgentPlan:
    active_ids = active_npc_ids if active_npc_ids is not None else ["evan"]
    return AgentPlan(
        turn_index=2,
        turn_budget=8,
        narrator_ord=2,
        director=DirectorDecision(
            stage_phase=stage_phase,
            difficulty="gauntlet",
            active_npc_ids=active_ids,
            twist_kind=twist_kind,
            expected_pressure=expected_pressure,
            reason="Deterministic test director decision.",
        ),
        npc_intents=[
            NPCIntent(
                npc_id=npc_id,
                display_name=npc_id.title(),
                intent="press",
                intent_brief="Push the player on the exposed contradiction.",
            )
            for npc_id in active_ids
        ],
        memory=MemorySnapshot(
            last_player_action={"summary": "kept the memo visible"},
            npc_pulse_trend={},
            unused_leverage=[],
            current_inventory_count=1,
            current_inventory_preview=["sealed audit packet"],
            played_leverage={},
        ),
        twist_directive={"kind": twist_kind} if twist_kind else None,
    )


def _player_message(*, played_leverage: PlayedLeverageCard | None = None) -> StoryMessage:
    return StoryMessage(
        ord=1,
        role="player",
        content="I keep the memo visible.",
        options=[],
        played_leverage=played_leverage,
    )


def _narrator_message(
    *,
    content: str = "Evan taps the draft memo and asks why the board never saw it.",
    pulses: list[NPCPulse] | None = None,
    inventory_delta: InventoryDelta | None = None,
) -> StoryMessage:
    return StoryMessage(
        ord=2,
        role="narrator",
        content=content,
        options=[_option()],
        npc_pulse=pulses
        if pulses is not None
        else [
            NPCPulse(
                npc_id="evan",
                state="pressing the contradiction",
                shift="wary",
                reason="Memo stayed public.",
            )
        ],
        inventory_delta=inventory_delta,
    )


def test_step_judge_passes_when_active_npc_and_pressure_are_observed() -> None:
    result = judge_step(
        agent_plan=_plan(),
        player_message=_player_message(),
        narrator_message=_narrator_message(),
        cast=_cast(),
    )

    assert result.schema_version == "step_judge.v1"
    assert result.status == "pass"
    assert result.violations == []


def test_step_judge_fails_when_active_npc_intent_is_missing() -> None:
    result = judge_step(
        agent_plan=_plan(active_npc_ids=["evan"]),
        player_message=_player_message(),
        narrator_message=_narrator_message(
            content="Mira changes the subject before the room can answer.",
            pulses=[NPCPulse(npc_id="mira", state="deflecting", shift="steady")],
        ),
        cast=_cast(),
    )

    assert result.status == "fail"
    assert [v.code for v in result.violations] == ["active_npc_intent_missing"]


def test_step_judge_fails_when_played_leverage_has_no_impact() -> None:
    result = judge_step(
        agent_plan=_plan(active_npc_ids=[]),
        player_message=_player_message(
            played_leverage=PlayedLeverageCard(
                card_id="founder-evan-0",
                npc_id="evan",
                leverage="Proof that Evan signed the side letter first.",
                action="reveal",
            )
        ),
        narrator_message=_narrator_message(
            content="The room waits in a flat silence.",
            pulses=[NPCPulse(npc_id="mira", state="watching", shift="steady")],
        ),
        cast=_cast(),
    )

    assert result.status == "fail"
    assert "played_leverage_no_observable_impact" in {v.code for v in result.violations}


def test_step_judge_warns_when_twist_turn_has_no_consequence() -> None:
    result = judge_step(
        agent_plan=_plan(active_npc_ids=[], twist_kind="reversal", stage_phase="reversal"),
        player_message=_player_message(),
        narrator_message=_narrator_message(
            content="Everyone waits without changing position.",
            pulses=[NPCPulse(npc_id="mira", state="waiting", shift="steady")],
        ),
        cast=_cast(),
    )

    assert result.status == "warn"
    assert [v.code for v in result.violations] == ["twist_turn_no_consequence"]


def test_step_judge_warns_on_inventory_delta_placeholder() -> None:
    result = judge_step(
        agent_plan=_plan(active_npc_ids=[]),
        player_message=_player_message(),
        narrator_message=_narrator_message(
            inventory_delta=InventoryDelta(added=[], removed=[], reason="")
        ),
        cast=_cast(),
    )

    assert result.status == "warn"
    assert "inventory_delta_empty" in {v.code for v in result.violations}


def test_contract_judge_fails_unknown_npc_id_reference() -> None:
    result = judge_contract(
        agent_plan=_plan(active_npc_ids=[]),
        player_message=_player_message(),
        narrator_message=_narrator_message(
            pulses=[NPCPulse(npc_id="ghost", state="impossible", shift="wary")]
        ),
        cast=_cast(),
        player_role=_player_role(),
    )

    assert result.status == "fail"
    assert "unknown_npc_pulse_id" in {v.code for v in result.violations}


def test_contract_judge_flags_hidden_info_leak() -> None:
    result = judge_contract(
        agent_plan=_plan(active_npc_ids=[]),
        player_message=_player_message(),
        narrator_message=_narrator_message(
            content="Evan blurts: A draft memo that contradicts the player's story.",
        ),
        cast=_cast(),
        player_role=_player_role(),
    )

    assert result.status == "fail"
    assert "hidden_info_leak" in {v.code for v in result.violations}


def test_contract_judge_warns_on_noop_inventory_delta() -> None:
    result = judge_contract(
        agent_plan=_plan(active_npc_ids=[]),
        player_message=_player_message(),
        narrator_message=_narrator_message(
            inventory_delta=InventoryDelta(added=[], removed=[], reason="no change")
        ),
        cast=_cast(),
        player_role=_player_role(),
    )

    assert result.status == "warn"
    assert "inventory_delta_noop" in {v.code for v in result.violations}


def test_repository_round_trips_step_and_contract_judge_events(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    repo.create_template(
        template_id="tmpl_judge_events",
        owner_user_id="usr_owner",
        seed="A cofounder announces the merger before the audit is ready.",
        title="Merger Test",
        cast=_cast(),
        advisor_persona="A calm strategy coach.",
        opening_passage="The room goes quiet.",
        opening_options=[_option()],
        player_goals=[],
        failure_conditions=[],
        player_role_options=[_player_role()],
        visibility="public",
        language="en",
    )
    repo.create_session(
        session_id="sess_judge_events",
        template_id="tmpl_judge_events",
        player_user_id="local-dev",
        turn_budget=8,
        difficulty="gauntlet",
        selected_player_role_id="founder",
    )
    plan = _plan()
    step = judge_step(
        agent_plan=plan,
        player_message=_player_message(),
        narrator_message=_narrator_message(),
        cast=_cast(),
    )
    contract = judge_contract(
        agent_plan=plan,
        player_message=_player_message(),
        narrator_message=_narrator_message(),
        cast=_cast(),
        player_role=_player_role(),
    )

    repo.append_agent_event(
        "sess_judge_events",
        ord_value=2,
        event_type="step_judge",
        payload=step,
    )
    repo.append_agent_event(
        "sess_judge_events",
        ord_value=2,
        event_type="contract_judge",
        payload=contract,
    )

    events = repo.list_agent_events("sess_judge_events")

    assert [event.event_type for event in events] == ["step_judge", "contract_judge"]
    assert events[0].payload == step
    assert events[1].payload == contract
