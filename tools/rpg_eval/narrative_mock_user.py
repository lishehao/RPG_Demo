from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import random
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib import request as urllib_request
from urllib.error import HTTPError
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, build_opener

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rpg_backend.narrative.contracts import (
    AdvanceTurnRequest,
    AdvanceTurnResponse,
    AgentPlan,
    ContractJudgeResult,
    NarrativeAgentEvent,
    NarrativeTemplateSummary,
    PlayedLeverageCard,
    PlayerLeverageOverNPC,
    PlayerRole,
    StartSessionResponse,
    StepJudgeResult,
    StoryHistoryResponse,
    StoryMessage,
    StoryOption,
)


MockUserPolicy = Literal[
    "option_selector",
    "leverage_seeker",
    "conflict_escalator",
    "cautious_negotiator",
    "goal_directed",
    "random_seeded",
    "regression_script",
]
RoleSelectionPolicy = Literal["first_available", "random_seeded", "protagonist_like"]
LeveragePolicy = Literal[
    "never",
    "opportunistic",
    "target_active_npc",
    "random_valid",
    "scripted",
]
RiskTolerance = Literal["low", "medium", "high"]
JudgeStatusText = Literal["pass", "warn", "fail", "missing"]


class MockUserConfig(BaseModel):
    """Config for a deterministic local player-agent episode run."""

    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, max_length=120)
    template_id: str | None = Field(default=None, max_length=120)
    role_id: str | None = Field(default=None, max_length=64)
    role_selection: RoleSelectionPolicy = "first_available"
    policy: MockUserPolicy = "option_selector"
    turn_budget: int = Field(default=6, ge=1, le=40)
    freeform_rate: float = Field(default=0.0, ge=0, le=1)
    leverage_policy: LeveragePolicy = "never"
    objective: str = Field(
        default="complete the episode while preserving visible player agency",
        min_length=1,
        max_length=300,
    )
    risk_tolerance: RiskTolerance = "medium"
    seed: int = 7
    base_url: str | None = Field(default=None, max_length=240)
    reviewer_username: str = Field(default="portfolio_reviewer", min_length=1, max_length=80)
    request_agent_trace: bool = True
    trace_output_path: str | None = Field(default=None, max_length=500)

    @field_validator("base_url")
    @classmethod
    def _strip_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().rstrip("/")
        return stripped or None


class MockUserAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chosen_option_index: int | None = None
    free_input: str | None = None
    selected_option_label: str | None = None
    played_leverage: PlayedLeverageCard | None = None
    played_leverage_summary: dict[str, str] | None = None
    decision_reason: str = Field(min_length=1, max_length=240)

    def to_request(self) -> AdvanceTurnRequest:
        return AdvanceTurnRequest(
            chosen_option_index=self.chosen_option_index,
            free_input=self.free_input,
            played_leverage=self.played_leverage,
        )


class MockTurnTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_index: int = Field(ge=0)
    narrator_ord: int = Field(ge=0)
    role_id: str | None = None
    observation_summary: dict[str, Any]
    selected_action: dict[str, Any]
    runtime_output_summary: dict[str, Any]
    agent_plan_summary: dict[str, Any]
    step_judge_status: JudgeStatusText
    step_judge_violation_codes: list[str] = Field(default_factory=list)
    contract_judge_status: JudgeStatusText
    contract_judge_violation_codes: list[str] = Field(default_factory=list)


class MockUserEpisodeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_count: int = Field(ge=0)
    completed_turn_budget: bool
    ending_detected: bool
    step_status_counts: dict[str, int] = Field(default_factory=dict)
    contract_status_counts: dict[str, int] = Field(default_factory=dict)
    repeated_violation_codes: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list, max_length=8)


class MockUserEpisodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["narrative_mock_user_episode.v1"] = (
        "narrative_mock_user_episode.v1"
    )
    source: Literal["deterministic_mock_user_v1"] = "deterministic_mock_user_v1"
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    config: MockUserConfig
    session_id: str
    role_id: str | None = None
    turns: list[MockTurnTrace]
    summary: MockUserEpisodeSummary


class NarrativeAPIAdapter(Protocol):
    def get_template(self, template_id: str) -> NarrativeTemplateSummary:
        ...

    def start_session(
        self,
        template_id: str,
        *,
        player_role_index: int | None,
        turn_budget: int,
    ) -> StartSessionResponse:
        ...

    def get_story(self, session_id: str, *, agent_trace: bool) -> StoryHistoryResponse:
        ...

    def advance_turn(
        self,
        session_id: str,
        payload: AdvanceTurnRequest,
        *,
        agent_trace: bool,
    ) -> AdvanceTurnResponse:
        ...


def _clip(value: str | None, max_chars: int = 160) -> str:
    text = " ".join((value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def _option_text(option: StoryOption) -> str:
    return " ".join(part for part in (option.label, option.hint, option.handle) if part)


def _keyword_score(text: str, keywords: tuple[str, ...]) -> int:
    lowered = text.casefold()
    return sum(1 for token in keywords if token in lowered)


def _latest_narrator(messages: list[StoryMessage]) -> StoryMessage:
    for message in reversed(messages):
        if message.role == "narrator":
            return message
    raise ValueError("story history has no narrator message")


def select_role_index(
    template: NarrativeTemplateSummary,
    config: MockUserConfig,
) -> int | None:
    roles = template.player_role_options
    if not roles:
        return None

    if config.role_id:
        for index, role in enumerate(roles):
            if role.role_id == config.role_id:
                return index
        raise ValueError(f"role_id not found in template: {config.role_id}")

    if config.role_selection == "random_seeded":
        return random.Random(config.seed).randrange(len(roles))

    if config.role_selection == "protagonist_like":
        protagonist_tokens = (
            "founder",
            "lead",
            "heir",
            "owner",
            "protagonist",
            "主角",
            "继承",
            "负责人",
        )

        def role_score(role: PlayerRole) -> int:
            text = " ".join((role.role_id, role.label, role.public_persona)).casefold()
            return _keyword_score(text, protagonist_tokens)

        return max(range(len(roles)), key=lambda index: (role_score(roles[index]), -index))

    return 0


def _choose_option_index(
    options: list[StoryOption],
    *,
    config: MockUserConfig,
    turn_index: int,
) -> tuple[int, str]:
    if not options:
        raise ValueError("cannot choose a preset option from an empty option list")
    if config.policy == "random_seeded":
        return random.Random(config.seed + turn_index * 7919).randrange(len(options)), (
            "seeded random option"
        )
    if config.policy == "regression_script":
        return turn_index % len(options), "regression script rotation"

    objective_terms = tuple(
        token.casefold()
        for token in config.objective.replace("/", " ").replace(",", " ").split()
        if len(token) >= 4
    )

    def score(option: StoryOption, index: int) -> tuple[int, int]:
        text = _option_text(option)
        value = 0
        if config.policy == "leverage_seeker":
            value += 6 * _keyword_score(
                text,
                (
                    "leverage",
                    "proof",
                    "evidence",
                    "secret",
                    "memo",
                    "show",
                    "reveal",
                    "trade",
                    "证据",
                    "秘密",
                    "摊牌",
                ),
            )
        elif config.policy == "conflict_escalator":
            value += 5 * _keyword_score(
                text,
                (
                    "confront",
                    "accuse",
                    "pressure",
                    "public",
                    "reveal",
                    "break",
                    "challenge",
                    "逼",
                    "公开",
                    "翻",
                ),
            )
            value += 2 if config.risk_tolerance == "high" else 0
        elif config.policy == "cautious_negotiator":
            value += 5 * _keyword_score(
                text,
                (
                    "listen",
                    "watch",
                    "delay",
                    "private",
                    "calm",
                    "trust",
                    "wait",
                    "稳",
                    "谈",
                    "缓",
                ),
            )
            value -= 3 * _keyword_score(text, ("reveal", "accuse", "public", "威胁"))
        elif config.policy == "goal_directed":
            value += 4 * _keyword_score(text, objective_terms)
        else:
            value += 2 * _keyword_score(
                text,
                ("probe", "ask", "counter", "choose", "press", "问", "试探", "反击"),
            )
        return value, -index

    best_index = max(range(len(options)), key=lambda index: score(options[index], index))
    return best_index, f"{config.policy} option scoring"


def _active_target_ids_from_history(history: StoryHistoryResponse) -> list[str]:
    events = sorted(history.agent_events, key=lambda event: event.event_index, reverse=True)
    for event in events:
        if event.event_type != "agent_plan":
            continue
        payload = event.payload
        if isinstance(payload, AgentPlan):
            return list(payload.director.active_npc_ids)
    for message in reversed(history.messages):
        if message.role == "narrator" and message.npc_pulse:
            return [pulse.npc_id for pulse in message.npc_pulse]
    return []


def _build_leverage_card(
    role: PlayerRole,
    leverage: PlayerLeverageOverNPC,
    *,
    action: str = "reveal",
) -> PlayedLeverageCard:
    index = role.leverages_over_npcs.index(leverage)
    return PlayedLeverageCard(
        card_id=f"{role.role_id}-{leverage.npc_id}-{index}",
        npc_id=leverage.npc_id,
        leverage=leverage.leverage,
        action=action,  # type: ignore[arg-type]
    )


def _choose_leverage(
    history: StoryHistoryResponse,
    *,
    config: MockUserConfig,
    option: StoryOption | None,
    turn_index: int,
) -> PlayedLeverageCard | None:
    role = history.session.player_role
    if role is None or not role.leverages_over_npcs or config.leverage_policy == "never":
        return None

    option_text = _option_text(option) if option is not None else ""
    should_spend = False
    if config.leverage_policy == "opportunistic":
        should_spend = (
            config.policy == "leverage_seeker"
            or _keyword_score(
                option_text,
                ("reveal", "proof", "counter", "show", "trade", "证据", "摊牌"),
            )
            > 0
        )
    elif config.leverage_policy in {"target_active_npc", "random_valid", "scripted"}:
        should_spend = True

    if not should_spend:
        return None

    candidates = list(role.leverages_over_npcs)
    if config.leverage_policy == "target_active_npc":
        active_ids = set(_active_target_ids_from_history(history))
        targeted = [item for item in candidates if item.npc_id in active_ids]
        if targeted:
            return _build_leverage_card(role, targeted[0])
    if config.leverage_policy == "random_valid":
        pick = random.Random(config.seed + turn_index * 104729).choice(candidates)
        return _build_leverage_card(role, pick)
    if config.leverage_policy == "scripted":
        return _build_leverage_card(role, candidates[turn_index % len(candidates)])
    return _build_leverage_card(role, candidates[0])


def choose_mock_user_action(
    history: StoryHistoryResponse,
    config: MockUserConfig,
    *,
    turn_index: int,
) -> MockUserAction:
    narrator = _latest_narrator(history.messages)
    rng = random.Random(config.seed + turn_index * 3571)
    use_freeform = config.freeform_rate > 0 and rng.random() < config.freeform_rate
    chosen_option: StoryOption | None = None

    if use_freeform or not narrator.options:
        free_input = _freeform_action(history, config=config, turn_index=turn_index)
        leverage = _choose_leverage(
            history,
            config=config,
            option=None,
            turn_index=turn_index,
        )
        return MockUserAction(
            free_input=free_input,
            played_leverage=leverage,
            played_leverage_summary=_safe_leverage_summary(leverage),
            decision_reason="freeform policy action",
        )

    option_index, reason = _choose_option_index(
        narrator.options,
        config=config,
        turn_index=turn_index,
    )
    chosen_option = narrator.options[option_index]
    leverage = _choose_leverage(
        history,
        config=config,
        option=chosen_option,
        turn_index=turn_index,
    )
    return MockUserAction(
        chosen_option_index=option_index,
        selected_option_label=chosen_option.label,
        played_leverage=leverage,
        played_leverage_summary=_safe_leverage_summary(leverage),
        decision_reason=reason,
    )


def _freeform_action(
    history: StoryHistoryResponse,
    *,
    config: MockUserConfig,
    turn_index: int,
) -> str:
    narrator = _latest_narrator(history.messages)
    active_ids = _active_target_ids_from_history(history)
    target = active_ids[0] if active_ids else "the room"
    if config.policy == "leverage_seeker":
        return f"I press {target} to answer the evidence without revealing everything yet."
    if config.policy == "conflict_escalator":
        return f"I force the contradiction into the open and make {target} respond now."
    if config.policy == "cautious_negotiator":
        return f"I slow the exchange down and ask {target} for one concrete explanation."
    if config.policy == "goal_directed":
        return f"I move toward my goal: {config.objective[:180]}"
    return f"I respond to the latest beat directly: {_clip(narrator.content, 120)}"


def _safe_leverage_summary(card: PlayedLeverageCard | None) -> dict[str, str] | None:
    if card is None:
        return None
    return {
        "card_id": card.card_id,
        "target_npc_id": card.npc_id,
        "action": card.action,
    }


def _observation_summary(history: StoryHistoryResponse) -> dict[str, Any]:
    narrator = _latest_narrator(history.messages)
    return {
        "latest_narrator_ord": narrator.ord,
        "passage": _clip(narrator.content, 180),
        "option_count": len(narrator.options),
        "option_labels": [_clip(option.label, 80) for option in narrator.options[:4]],
        "npc_pulse": [
            {
                "npc_id": pulse.npc_id,
                "shift": pulse.shift,
                "state": _clip(pulse.state, 80),
            }
            for pulse in (narrator.npc_pulse or [])[:4]
        ],
    }


def _runtime_output_summary(message: StoryMessage) -> dict[str, Any]:
    delta = message.inventory_delta
    return {
        "narrator_ord": message.ord,
        "passage": _clip(message.content, 220),
        "option_count": len(message.options),
        "npc_pulse": [
            {"npc_id": pulse.npc_id, "shift": pulse.shift, "state": _clip(pulse.state, 80)}
            for pulse in (message.npc_pulse or [])[:4]
        ],
        "inventory_delta": {
            "added_count": len(delta.added) if delta else 0,
            "removed_count": len(delta.removed) if delta else 0,
            "has_reason": bool(delta and delta.reason.strip()),
        },
    }


def _agent_plan_summary(plan: AgentPlan | None) -> dict[str, Any]:
    if plan is None:
        return {"available": False}
    return {
        "available": True,
        "schema_version": plan.schema_version,
        "source": plan.source,
        "stage_phase": plan.director.stage_phase,
        "difficulty": plan.director.difficulty,
        "active_npc_ids": list(plan.director.active_npc_ids),
        "twist_kind": plan.director.twist_kind,
        "expected_pressure": plan.director.expected_pressure,
        "npc_intent_count": len(plan.npc_intents),
        "npc_intents": [
            {
                "npc_id": intent.npc_id,
                "intent": intent.intent,
                "has_leverage": bool(intent.leverage),
            }
            for intent in plan.npc_intents[:4]
        ],
        "memory": {
            "unused_leverage_count": len(plan.memory.unused_leverage),
            "inventory_count": plan.memory.current_inventory_count,
            "played_leverage_targets": sorted(plan.memory.played_leverage.keys()),
        },
    }


def _judge_status(result: StepJudgeResult | ContractJudgeResult | None) -> JudgeStatusText:
    return result.status if result is not None else "missing"


def _judge_codes(result: StepJudgeResult | ContractJudgeResult | None) -> list[str]:
    if result is None:
        return []
    return [violation.code for violation in result.violations]


def _events_for_ord(
    history: StoryHistoryResponse,
    narrator_ord: int,
) -> tuple[AgentPlan | None, StepJudgeResult | None, ContractJudgeResult | None]:
    plan: AgentPlan | None = None
    step: StepJudgeResult | None = None
    contract: ContractJudgeResult | None = None
    for event in history.agent_events:
        if event.ord != narrator_ord:
            continue
        if event.event_type == "agent_plan" and isinstance(event.payload, AgentPlan):
            plan = event.payload
        elif event.event_type == "step_judge" and isinstance(event.payload, StepJudgeResult):
            step = event.payload
        elif event.event_type == "contract_judge" and isinstance(
            event.payload,
            ContractJudgeResult,
        ):
            contract = event.payload
    return plan, step, contract


def _selected_action_summary(action: MockUserAction) -> dict[str, Any]:
    return {
        "chosen_option_index": action.chosen_option_index,
        "selected_option_label": _clip(action.selected_option_label, 120),
        "free_input": _clip(action.free_input, 160),
        "played_leverage": action.played_leverage_summary,
        "decision_reason": action.decision_reason,
    }


def run_mock_user_episode(
    config: MockUserConfig,
    adapter: NarrativeAPIAdapter,
) -> MockUserEpisodeResult:
    session_id = config.session_id
    if session_id is None:
        if config.template_id is None:
            raise ValueError("either session_id or template_id is required")
        template = adapter.get_template(config.template_id)
        role_index = select_role_index(template, config)
        started = adapter.start_session(
            config.template_id,
            player_role_index=role_index,
            turn_budget=config.turn_budget,
        )
        session_id = started.session.session_id

    history = adapter.get_story(session_id, agent_trace=config.request_agent_trace)
    traces: list[MockTurnTrace] = []
    ending_detected = bool(history.session.ending_label)

    for turn_index in range(config.turn_budget):
        if ending_detected:
            break
        action = choose_mock_user_action(history, config, turn_index=turn_index)
        response = adapter.advance_turn(
            session_id,
            action.to_request(),
            agent_trace=config.request_agent_trace,
        )
        ending_detected = bool(response.is_complete or response.ending is not None)
        refreshed_history = adapter.get_story(session_id, agent_trace=config.request_agent_trace)
        plan, step, contract = _events_for_ord(
            refreshed_history,
            response.narrator_message.ord,
        )
        if plan is None:
            plan = response.agent_plan
        traces.append(
            MockTurnTrace(
                turn_index=turn_index,
                narrator_ord=response.narrator_message.ord,
                role_id=refreshed_history.session.player_role.role_id
                if refreshed_history.session.player_role
                else None,
                observation_summary=_observation_summary(history),
                selected_action=_selected_action_summary(action),
                runtime_output_summary=_runtime_output_summary(response.narrator_message),
                agent_plan_summary=_agent_plan_summary(plan),
                step_judge_status=_judge_status(step),
                step_judge_violation_codes=_judge_codes(step),
                contract_judge_status=_judge_status(contract),
                contract_judge_violation_codes=_judge_codes(contract),
            )
        )
        history = refreshed_history

    result = MockUserEpisodeResult(
        config=config,
        session_id=session_id,
        role_id=history.session.player_role.role_id if history.session.player_role else None,
        turns=traces,
        summary=_episode_summary(
            traces,
            requested_turn_budget=config.turn_budget,
            ending_detected=ending_detected or bool(history.session.ending_label),
        ),
    )
    if config.trace_output_path:
        write_episode_trace(result, Path(config.trace_output_path))
    return result


def _episode_summary(
    traces: list[MockTurnTrace],
    *,
    requested_turn_budget: int,
    ending_detected: bool,
) -> MockUserEpisodeSummary:
    step_counts = Counter(trace.step_judge_status for trace in traces)
    contract_counts = Counter(trace.contract_judge_status for trace in traces)
    violation_counts = Counter(
        code
        for trace in traces
        for code in (
            trace.step_judge_violation_codes + trace.contract_judge_violation_codes
        )
    )
    repeated = {code: count for code, count in violation_counts.items() if count > 1}
    recommendations: list[str] = []
    if step_counts.get("fail", 0) or contract_counts.get("fail", 0):
        recommendations.append("inspect failed judge events before portfolio/demo capture")
    if step_counts.get("missing", 0) or contract_counts.get("missing", 0):
        recommendations.append("verify reviewer authorization and agent event archive wiring")
    if repeated:
        recommendations.append("prioritize repeated violation codes for deterministic regression fixes")
    if not traces:
        recommendations.append("episode did not advance; check session state and turn budget")
    return MockUserEpisodeSummary(
        turn_count=len(traces),
        completed_turn_budget=len(traces) >= requested_turn_budget,
        ending_detected=ending_detected,
        step_status_counts=dict(step_counts),
        contract_status_counts=dict(contract_counts),
        repeated_violation_codes=repeated,
        recommendations=recommendations,
    )


def write_episode_trace(result: MockUserEpisodeResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for trace in result.turns:
        rows.append(
            {
                "record_type": "turn",
                "schema_version": result.schema_version,
                "session_id": result.session_id,
                "payload": trace.model_dump(mode="json"),
            }
        )
    rows.append(
        {
            "record_type": "summary",
            "schema_version": result.schema_version,
            "session_id": result.session_id,
            "payload": result.summary.model_dump(mode="json"),
        }
    )
    output_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


class TestClientNarrativeAdapter:
    """Narrative adapter backed by FastAPI TestClient or the same interface."""

    __test__ = False

    def __init__(
        self,
        client: Any,
        *,
        reviewer_username: str = "portfolio_reviewer",
        login: bool = True,
    ) -> None:
        self.client = client
        if login:
            response = self.client.post("/auth/login", json={"username": reviewer_username})
            if response.status_code != 200:
                raise RuntimeError(f"reviewer login failed: {response.status_code} {response.text}")

    def get_template(self, template_id: str) -> NarrativeTemplateSummary:
        response = self.client.get(f"/narrative/templates/{template_id}")
        return _parse_response(response, NarrativeTemplateSummary)

    def start_session(
        self,
        template_id: str,
        *,
        player_role_index: int | None,
        turn_budget: int,
    ) -> StartSessionResponse:
        payload: dict[str, Any] = {"turn_budget": turn_budget}
        if player_role_index is not None:
            payload["player_role_index"] = player_role_index
        response = self.client.post(
            f"/narrative/templates/{template_id}/sessions",
            json=payload,
        )
        return _parse_response(response, StartSessionResponse)

    def get_story(self, session_id: str, *, agent_trace: bool) -> StoryHistoryResponse:
        suffix = "?agent_trace=true" if agent_trace else ""
        response = self.client.get(f"/narrative/sessions/{session_id}/story{suffix}")
        return _parse_response(response, StoryHistoryResponse)

    def advance_turn(
        self,
        session_id: str,
        payload: AdvanceTurnRequest,
        *,
        agent_trace: bool,
    ) -> AdvanceTurnResponse:
        suffix = "?agent_trace=true" if agent_trace else ""
        response = self.client.post(
            f"/narrative/sessions/{session_id}/story/turns{suffix}",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        return _parse_response(response, AdvanceTurnResponse)


class LiveHTTPNarrativeAdapter:
    """Small urllib adapter for local servers; no external dependency."""

    def __init__(
        self,
        base_url: str,
        *,
        reviewer_username: str = "portfolio_reviewer",
        login: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))
        if login:
            self._request_json(
                "POST",
                "/auth/login",
                {"username": reviewer_username},
            )

    def get_template(self, template_id: str) -> NarrativeTemplateSummary:
        return NarrativeTemplateSummary.model_validate(
            self._request_json("GET", f"/narrative/templates/{template_id}")
        )

    def start_session(
        self,
        template_id: str,
        *,
        player_role_index: int | None,
        turn_budget: int,
    ) -> StartSessionResponse:
        payload: dict[str, Any] = {"turn_budget": turn_budget}
        if player_role_index is not None:
            payload["player_role_index"] = player_role_index
        return StartSessionResponse.model_validate(
            self._request_json(
                "POST",
                f"/narrative/templates/{template_id}/sessions",
                payload,
            )
        )

    def get_story(self, session_id: str, *, agent_trace: bool) -> StoryHistoryResponse:
        suffix = "?agent_trace=true" if agent_trace else ""
        return StoryHistoryResponse.model_validate(
            self._request_json("GET", f"/narrative/sessions/{session_id}/story{suffix}")
        )

    def advance_turn(
        self,
        session_id: str,
        payload: AdvanceTurnRequest,
        *,
        agent_trace: bool,
    ) -> AdvanceTurnResponse:
        suffix = "?agent_trace=true" if agent_trace else ""
        return AdvanceTurnResponse.model_validate(
            self._request_json(
                "POST",
                f"/narrative/sessions/{session_id}/story/turns{suffix}",
                payload.model_dump(mode="json", exclude_none=True),
            )
        )

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib_request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from exc


def _parse_response(response: Any, model_cls: type[Any]) -> Any:
    if response.status_code >= 400:
        raise RuntimeError(f"API request failed: {response.status_code} {response.text}")
    return model_cls.model_validate(response.json())


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a deterministic mock player against the narrative API and "
            "archive an inspectable agent/judge episode trace."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--session", dest="session_id")
    parser.add_argument("--template", dest="template_id")
    parser.add_argument("--role", dest="role_id")
    parser.add_argument("--role-policy", dest="role_selection", default="first_available")
    parser.add_argument("--policy", default="option_selector")
    parser.add_argument("--turns", dest="turn_budget", type=int, default=6)
    parser.add_argument("--freeform-rate", type=float, default=0.0)
    parser.add_argument("--leverage-policy", default="never")
    parser.add_argument("--objective", default=MockUserConfig.model_fields["objective"].default)
    parser.add_argument("--risk-tolerance", default="medium")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--reviewer-username", default="portfolio_reviewer")
    parser.add_argument("--output", dest="trace_output_path", default="artifacts/mock_user_episode.jsonl")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    config = MockUserConfig(
        session_id=args.session_id,
        template_id=args.template_id,
        role_id=args.role_id,
        role_selection=args.role_selection,
        policy=args.policy,
        turn_budget=args.turn_budget,
        freeform_rate=args.freeform_rate,
        leverage_policy=args.leverage_policy,
        objective=args.objective,
        risk_tolerance=args.risk_tolerance,
        seed=args.seed,
        base_url=args.base_url,
        reviewer_username=args.reviewer_username,
        trace_output_path=args.trace_output_path,
    )
    adapter = LiveHTTPNarrativeAdapter(
        config.base_url or "http://127.0.0.1:8000",
        reviewer_username=config.reviewer_username,
    )
    result = run_mock_user_episode(config, adapter)
    print(result.summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
