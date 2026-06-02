from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import random
import tempfile
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4
from urllib import request as urllib_request
from urllib.error import HTTPError
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, build_opener

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rpg_backend.narrative.contracts import (
    AdvanceTurnRequest,
    AdvanceTurnResponse,
    AgentPlan,
    CastMember,
    ContractJudgeResult,
    NarrativeTemplateSummary,
    NPCLeverageOverNPC,
    NPCPulse,
    PlayedLeverageCard,
    PlayerGoal,
    PlayerLeverageOverNPC,
    PlayerRole,
    StartSessionResponse,
    StepJudgeResult,
    StoryHistoryResponse,
    StoryMessage,
    StoryOption,
)
from rpg_backend.responses_transport import ResponsesJSONResponse


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
AgentLoopAction = Literal[
    "observe",
    "update_memory",
    "choose_action",
    "play_turn",
    "collect_events",
    "collect_judges",
    "summarize_episode",
    "judge_trajectory",
]


class MockUserConfig(BaseModel):
    """Config for a deterministic local player-agent episode run."""

    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, max_length=120)
    template_id: str | None = Field(default=None, max_length=120)
    mode: Literal["fixture", "live"] = "live"
    fixture: Literal["merger_audit", "none"] = "merger_audit"
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
    summary_output_path: str | None = Field(default=None, max_length=500)

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
    selected_option_handle: str | None = None
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


class AgentLoopEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["mock_user_loop_event.v1"] = "mock_user_loop_event.v1"
    event_index: int = Field(ge=0)
    turn_index: int | None = Field(default=None, ge=0)
    action_type: AgentLoopAction
    summary: str = Field(min_length=1, max_length=240)
    payload: dict[str, Any] = Field(default_factory=dict)


class EpisodeMemory(BaseModel):
    """Sanitized memory carried by the deterministic player policy."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["mock_user_episode_memory.v1"] = "mock_user_episode_memory.v1"
    objective: str = Field(default="", max_length=300)
    latest_narrator_ord: int | None = Field(default=None, ge=0)
    narrator_ord_path: list[int] = Field(default_factory=list, max_length=80)
    recent_observations: list[str] = Field(default_factory=list, max_length=4)
    observed_npc_ids: list[str] = Field(default_factory=list, max_length=32)
    npc_pulse_trend: dict[str, list[str]] = Field(default_factory=dict)
    selected_option_handles: list[str] = Field(default_factory=list, max_length=80)
    played_leverage_cards: list[dict[str, str]] = Field(default_factory=list, max_length=40)
    inventory_events: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    unresolved_goals: list[str] = Field(default_factory=list, max_length=8)
    judge_violation_counts: dict[str, int] = Field(default_factory=dict)
    policy_decision_counts: dict[str, int] = Field(default_factory=dict)
    pressure_signal_count: int = Field(default=0, ge=0)
    objective_progress: Literal["unknown", "low", "medium", "high"] = "unknown"
    last_action_summary: str | None = Field(default=None, max_length=200)


class TrajectoryJudgeCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    status: Literal["pass", "warn", "fail"]
    rationale: str = Field(min_length=1, max_length=260)
    evidence: list[str] = Field(default_factory=list, max_length=8)


class TrajectoryJudgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trajectory_judge.v1"] = "trajectory_judge.v1"
    source: Literal["deterministic_v1"] = "deterministic_v1"
    status: JudgeStatusText
    turn_count: int = Field(ge=0)
    checks: list[TrajectoryJudgeCheck] = Field(default_factory=list, max_length=16)
    summary: str = Field(min_length=1, max_length=280)


class MockTurnTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_index: int = Field(ge=0)
    narrator_ord: int = Field(ge=0)
    role_id: str | None = None
    observation_summary: dict[str, Any]
    memory_before: dict[str, Any] = Field(default_factory=dict)
    selected_action: dict[str, Any]
    runtime_output_summary: dict[str, Any]
    agent_plan_summary: dict[str, Any]
    memory_after: dict[str, Any] = Field(default_factory=dict)
    memory_summary: dict[str, Any] = Field(default_factory=dict)
    action_loop: list[AgentLoopEvent] = Field(default_factory=list, max_length=8)
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
    trajectory_status: JudgeStatusText = "missing"
    trajectory_check_counts: dict[str, int] = Field(default_factory=dict)
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
    episode_memory: EpisodeMemory = Field(default_factory=EpisodeMemory)
    trajectory_judge: TrajectoryJudgeResult
    action_loop: list[AgentLoopEvent] = Field(default_factory=list)
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


def _new_episode_memory(config: MockUserConfig) -> EpisodeMemory:
    return EpisodeMemory(
        objective=config.objective,
        unresolved_goals=[config.objective],
    )


def _append_limited(values: list[Any], value: Any, *, max_items: int) -> list[Any]:
    next_values = [*values, value]
    return next_values[-max_items:]


def _unique_limited(values: list[str], additions: list[str], *, max_items: int) -> list[str]:
    merged = list(values)
    for item in additions:
        if item and item not in merged:
            merged.append(item)
    return merged[-max_items:]


def _memory_from_observation(
    memory: EpisodeMemory,
    history: StoryHistoryResponse,
    *,
    config: MockUserConfig,
) -> EpisodeMemory:
    narrator = _latest_narrator(history.messages)
    observed_npc_ids = [pulse.npc_id for pulse in narrator.npc_pulse]
    npc_pulse_trend = {
        npc_id: list(shifts)
        for npc_id, shifts in memory.npc_pulse_trend.items()
    } if hasattr(memory, "npc_pulse_trend") else {}
    for pulse in narrator.npc_pulse:
        existing = npc_pulse_trend.get(pulse.npc_id, [])
        npc_pulse_trend[pulse.npc_id] = _append_limited(existing, pulse.shift, max_items=6)
    pressure_count = memory.pressure_signal_count + sum(
        1 for pulse in narrator.npc_pulse if pulse.shift in {"wary", "broken", "colder"}
    )
    observed_progress = _objective_progress(config.objective, narrator.content)
    return memory.model_copy(
        update={
            "objective": memory.objective or config.objective,
            "latest_narrator_ord": narrator.ord,
            "narrator_ord_path": _append_limited(
                memory.narrator_ord_path,
                narrator.ord,
                max_items=80,
            ),
            "recent_observations": _append_limited(
                memory.recent_observations,
                _clip(narrator.content, 140),
                max_items=4,
            ),
            "observed_npc_ids": _unique_limited(
                memory.observed_npc_ids,
                observed_npc_ids,
                max_items=32,
            ),
            "npc_pulse_trend": npc_pulse_trend,
            "pressure_signal_count": pressure_count,
            "objective_progress": _max_objective_progress(memory.objective_progress, observed_progress),
        }
    )


def _memory_after_turn(
    memory: EpisodeMemory,
    *,
    action: MockUserAction,
    narrator_message: StoryMessage,
    step: StepJudgeResult | None,
    contract: ContractJudgeResult | None,
    config: MockUserConfig,
) -> EpisodeMemory:
    npc_pulse_trend = {
        npc_id: list(shifts)
        for npc_id, shifts in memory.npc_pulse_trend.items()
    }
    for pulse in narrator_message.npc_pulse:
        existing = npc_pulse_trend.get(pulse.npc_id, [])
        npc_pulse_trend[pulse.npc_id] = _append_limited(existing, pulse.shift, max_items=6)
    pressure_count = memory.pressure_signal_count + sum(
        1 for pulse in narrator_message.npc_pulse if pulse.shift in {"wary", "broken", "colder"}
    )
    selected_handles = list(memory.selected_option_handles)
    if action.selected_option_handle:
        selected_handles = _append_limited(selected_handles, action.selected_option_handle, max_items=80)
    used_cards = list(memory.played_leverage_cards)
    if action.played_leverage_summary:
        used_cards = _append_limited(
            used_cards,
            dict(action.played_leverage_summary),
            max_items=40,
        )
    inventory_events = list(memory.inventory_events)
    if narrator_message.inventory_delta and (
        narrator_message.inventory_delta.added or narrator_message.inventory_delta.removed
    ):
        inventory_events = _append_limited(
            inventory_events,
            {
                "narrator_ord": str(narrator_message.ord),
                "added_count": str(len(narrator_message.inventory_delta.added)),
                "removed_count": str(len(narrator_message.inventory_delta.removed)),
            },
            max_items=12,
        )
    counts = dict(memory.judge_violation_counts)
    for judge in (step, contract):
        if judge is None:
            continue
        for violation in judge.violations:
            counts[violation.code] = counts.get(violation.code, 0) + 1
    policy_counts = dict(memory.policy_decision_counts)
    policy_counts[config.policy] = policy_counts.get(config.policy, 0) + 1
    last_action = action.selected_option_label or action.free_input or "unknown action"
    observed_progress = _objective_progress(config.objective, narrator_message.content)
    return memory.model_copy(
        update={
            "latest_narrator_ord": narrator_message.ord,
            "narrator_ord_path": _append_limited(
                memory.narrator_ord_path,
                narrator_message.ord,
                max_items=80,
            ),
            "recent_observations": _append_limited(
                memory.recent_observations,
                _clip(narrator_message.content, 140),
                max_items=4,
            ),
            "observed_npc_ids": _unique_limited(
                memory.observed_npc_ids,
                [pulse.npc_id for pulse in narrator_message.npc_pulse],
                max_items=32,
            ),
            "npc_pulse_trend": npc_pulse_trend,
            "selected_option_handles": selected_handles,
            "played_leverage_cards": used_cards,
            "inventory_events": inventory_events,
            "judge_violation_counts": counts,
            "policy_decision_counts": policy_counts,
            "pressure_signal_count": pressure_count,
            "last_action_summary": _clip(last_action, 180),
            "objective_progress": _max_objective_progress(memory.objective_progress, observed_progress),
        }
    )


def _memory_summary(memory: EpisodeMemory) -> dict[str, Any]:
    return {
        "schema_version": memory.schema_version,
        "latest_narrator_ord": memory.latest_narrator_ord,
        "narrator_ord_path": memory.narrator_ord_path[-8:],
        "recent_observation_count": len(memory.recent_observations),
        "observed_npc_ids": memory.observed_npc_ids[:6],
        "selected_option_handles": memory.selected_option_handles[-6:],
        "played_leverage_cards": memory.played_leverage_cards[-6:],
        "used_leverage_count": len(memory.played_leverage_cards),
        "inventory_event_count": len(memory.inventory_events),
        "repeated_violation_codes": {
            code: count
            for code, count in memory.judge_violation_counts.items()
            if count > 1
        },
        "objective_progress": memory.objective_progress,
        "last_action_summary": memory.last_action_summary,
    }


def _objective_progress(objective: str, text: str) -> Literal["unknown", "low", "medium", "high"]:
    terms = [token.casefold() for token in objective.split() if len(token) >= 4]
    if not terms:
        return "unknown"
    hits = _keyword_score(text, tuple(terms))
    if hits >= 3:
        return "high"
    if hits >= 1:
        return "medium"
    return "low"


def _max_objective_progress(
    current: Literal["unknown", "low", "medium", "high"],
    observed: Literal["unknown", "low", "medium", "high"],
) -> Literal["unknown", "low", "medium", "high"]:
    ranks = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
    return current if ranks[current] >= ranks[observed] else observed


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


class ActionPolicy(Protocol):
    policy_id: MockUserPolicy

    def score_option(
        self,
        option: StoryOption,
        *,
        config: MockUserConfig,
        memory: EpisodeMemory,
        turn_index: int,
    ) -> tuple[int, list[str]]:
        ...


class BaseActionPolicy:
    policy_id: MockUserPolicy = "option_selector"
    keywords: tuple[str, ...] = ()
    weight: int = 2

    def score_option(
        self,
        option: StoryOption,
        *,
        config: MockUserConfig,
        memory: EpisodeMemory,
        turn_index: int,
    ) -> tuple[int, list[str]]:
        del config, memory, turn_index
        text = _option_text(option)
        hits = _keyword_score(text, self.keywords)
        reasons = [f"keyword_hits:{hits}"] if hits else ["default option prior"]
        return hits * self.weight, reasons


class OptionSelectorPolicy(BaseActionPolicy):
    policy_id = "option_selector"
    keywords = ("probe", "ask", "counter", "choose", "press", "问", "试探", "反击")
    weight = 2


class LeverageSeekerPolicy(BaseActionPolicy):
    policy_id = "leverage_seeker"
    keywords = (
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
    )
    weight = 6


class ConflictEscalatorPolicy(BaseActionPolicy):
    policy_id = "conflict_escalator"
    keywords = (
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
    )
    weight = 5

    def score_option(
        self,
        option: StoryOption,
        *,
        config: MockUserConfig,
        memory: EpisodeMemory,
        turn_index: int,
    ) -> tuple[int, list[str]]:
        score, reasons = super().score_option(
            option,
            config=config,
            memory=memory,
            turn_index=turn_index,
        )
        if config.risk_tolerance == "high":
            score += 2
            reasons.append("risk_tolerance:high")
        if memory.pressure_signal_count > 0:
            score += 1
            reasons.append("memory:pressure_seen")
        return score, reasons


class CautiousNegotiatorPolicy(BaseActionPolicy):
    policy_id = "cautious_negotiator"
    keywords = (
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
    )
    weight = 5

    def score_option(
        self,
        option: StoryOption,
        *,
        config: MockUserConfig,
        memory: EpisodeMemory,
        turn_index: int,
    ) -> tuple[int, list[str]]:
        score, reasons = super().score_option(
            option,
            config=config,
            memory=memory,
            turn_index=turn_index,
        )
        risky_hits = _keyword_score(_option_text(option), ("reveal", "accuse", "public", "威胁"))
        if risky_hits:
            score -= risky_hits * 3
            reasons.append(f"risk_penalty:{risky_hits}")
        return score, reasons


class GoalDirectedPolicy(BaseActionPolicy):
    policy_id = "goal_directed"

    def score_option(
        self,
        option: StoryOption,
        *,
        config: MockUserConfig,
        memory: EpisodeMemory,
        turn_index: int,
    ) -> tuple[int, list[str]]:
        del turn_index
        objective_terms = tuple(
            token.casefold()
            for token in (config.objective or memory.objective).replace("/", " ").replace(",", " ").split()
            if len(token) >= 4
        )
        hits = _keyword_score(_option_text(option), objective_terms)
        score = hits * 4
        reasons = [f"objective_term_hits:{hits}"] if hits else ["objective fallback"]
        if memory.objective_progress in {"low", "unknown"}:
            score += 1
            reasons.append("memory:objective_not_resolved")
        return score, reasons


class RandomSeededPolicy(BaseActionPolicy):
    policy_id = "random_seeded"

    def score_option(
        self,
        option: StoryOption,
        *,
        config: MockUserConfig,
        memory: EpisodeMemory,
        turn_index: int,
    ) -> tuple[int, list[str]]:
        del option, memory
        score = random.Random(config.seed + turn_index * 7919).randrange(1000)
        return score, ["seeded_random_score"]


class RegressionScriptPolicy(BaseActionPolicy):
    policy_id = "regression_script"

    def score_option(
        self,
        option: StoryOption,
        *,
        config: MockUserConfig,
        memory: EpisodeMemory,
        turn_index: int,
    ) -> tuple[int, list[str]]:
        del option, config, memory
        return -turn_index, ["scripted_rotation"]


POLICY_REGISTRY: dict[MockUserPolicy, ActionPolicy] = {
    "option_selector": OptionSelectorPolicy(),
    "leverage_seeker": LeverageSeekerPolicy(),
    "conflict_escalator": ConflictEscalatorPolicy(),
    "cautious_negotiator": CautiousNegotiatorPolicy(),
    "goal_directed": GoalDirectedPolicy(),
    "random_seeded": RandomSeededPolicy(),
    "regression_script": RegressionScriptPolicy(),
}


def _choose_option_index(
    options: list[StoryOption],
    *,
    config: MockUserConfig,
    turn_index: int,
    memory: EpisodeMemory | None = None,
) -> tuple[int, str]:
    if not options:
        raise ValueError("cannot choose a preset option from an empty option list")
    active_memory = memory or _new_episode_memory(config)
    if config.policy == "regression_script":
        return turn_index % len(options), "regression script rotation"

    policy = POLICY_REGISTRY[config.policy]
    scored = [
        (
            *policy.score_option(
                option,
                config=config,
                memory=active_memory,
                turn_index=turn_index,
            ),
            index,
        )
        for index, option in enumerate(options)
    ]
    best_score, reasons, best_index = max(scored, key=lambda item: (item[0], -item[2]))
    return best_index, f"{config.policy} option scoring: score={best_score}; {', '.join(reasons[:3])}"


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
    return PlayedLeverageCard(
        card_id=_leverage_card_id(role, leverage),
        npc_id=leverage.npc_id,
        leverage=leverage.leverage,
        action=action,  # type: ignore[arg-type]
    )


def _leverage_card_id(role: PlayerRole, leverage: PlayerLeverageOverNPC) -> str:
    index = role.leverages_over_npcs.index(leverage)
    return f"{role.role_id}-{leverage.npc_id}-{index}"


def _choose_leverage(
    history: StoryHistoryResponse,
    *,
    config: MockUserConfig,
    option: StoryOption | None,
    turn_index: int,
    memory: EpisodeMemory | None = None,
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

    used_card_ids = {
        str(card.get("card_id"))
        for card in (memory.played_leverage_cards if memory is not None else [])
        if card.get("card_id")
    }
    candidates = [
        item
        for item in role.leverages_over_npcs
        if _leverage_card_id(role, item) not in used_card_ids
    ]
    if not candidates:
        return None
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
    memory: EpisodeMemory | None = None,
) -> MockUserAction:
    narrator = _latest_narrator(history.messages)
    active_memory = memory or _new_episode_memory(config)
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
            memory=active_memory,
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
        memory=active_memory,
    )
    chosen_option = narrator.options[option_index]
    leverage = _choose_leverage(
        history,
        config=config,
        option=chosen_option,
        turn_index=turn_index,
        memory=active_memory,
    )
    return MockUserAction(
        chosen_option_index=option_index,
        selected_option_handle=chosen_option.handle,
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
        "selected_option_handle": _clip(action.selected_option_handle, 40),
        "selected_option_label": _clip(action.selected_option_label, 120),
        "free_input": _clip(action.free_input, 160),
        "played_leverage": action.played_leverage_summary,
        "decision_reason": action.decision_reason,
    }


def _loop_event(
    events: list[AgentLoopEvent],
    *,
    turn_index: int | None,
    action_type: AgentLoopAction,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> AgentLoopEvent:
    event = AgentLoopEvent(
        event_index=len(events),
        turn_index=turn_index,
        action_type=action_type,
        summary=summary,
        payload=payload or {},
    )
    events.append(event)
    return event


def _trajectory_check_counts(checks: list[TrajectoryJudgeCheck]) -> dict[str, int]:
    counts = Counter(check.status for check in checks)
    return dict(counts)


def _trace_has_runtime_impact(trace: MockTurnTrace) -> bool:
    pulses = trace.runtime_output_summary.get("npc_pulse") or []
    if any(
        isinstance(pulse, dict) and str(pulse.get("shift") or "steady") != "steady"
        for pulse in pulses
    ):
        return True
    delta = trace.runtime_output_summary.get("inventory_delta") or {}
    if isinstance(delta, dict):
        return bool(int(delta.get("added_count") or 0) or int(delta.get("removed_count") or 0))
    return False


def judge_episode_trajectory(
    *,
    traces: list[MockTurnTrace],
    memory: EpisodeMemory,
    config: MockUserConfig,
    ending_detected: bool,
) -> TrajectoryJudgeResult:
    checks: list[TrajectoryJudgeCheck] = []

    def add_check(
        code: str,
        status: Literal["pass", "warn", "fail"],
        rationale: str,
        evidence: list[str] | None = None,
    ) -> None:
        checks.append(
            TrajectoryJudgeCheck(
                code=code,
                status=status,
                rationale=rationale,
                evidence=evidence or [],
            )
        )

    if traces:
        add_check(
            "episode_progressed",
            "pass",
            "The policy advanced at least one narrator turn.",
            [f"turn_count:{len(traces)}"],
        )
    else:
        add_check("episode_progressed", "fail", "The policy did not advance the episode.")

    ord_path = [trace.narrator_ord for trace in traces]
    if len(ord_path) == len(set(ord_path)):
        add_check("narrator_ord_unique", "pass", "Each captured turn has a unique narrator ordinal.")
    else:
        add_check(
            "narrator_ord_unique",
            "fail",
            "The episode repeated a narrator ordinal, which suggests trace refresh drift.",
            [f"narrator_ord_path:{ord_path}"],
        )

    missing_step = sum(1 for trace in traces if trace.step_judge_status == "missing")
    missing_contract = sum(1 for trace in traces if trace.contract_judge_status == "missing")
    failed_judges = sum(
        1
        for trace in traces
        if trace.step_judge_status == "fail" or trace.contract_judge_status == "fail"
    )
    repeated_violations = {
        code: count
        for code, count in memory.judge_violation_counts.items()
        if count > 1
    }
    if failed_judges:
        add_check(
            "turn_judges_clear",
            "fail",
            "At least one deterministic step or contract judge failed.",
            [f"failed_turn_judges:{failed_judges}"],
        )
    elif config.request_agent_trace and (missing_step or missing_contract):
        add_check(
            "turn_judges_clear",
            "warn",
            "Reviewer trace was requested but some turn judges were missing.",
            [f"missing_step:{missing_step}", f"missing_contract:{missing_contract}"],
        )
    else:
        add_check("turn_judges_clear", "pass", "No deterministic turn judge failed.")

    if repeated_violations:
        add_check(
            "repeated_step_contract_violations",
            "fail",
            "The same Step/Contract violation appeared repeatedly across the episode.",
            [f"{code}:{count}" for code, count in sorted(repeated_violations.items())[:8]],
        )
    else:
        add_check(
            "repeated_step_contract_violations",
            "pass",
            "No repeated Step/Contract violation codes were observed.",
        )

    available_plans = sum(1 for trace in traces if trace.agent_plan_summary.get("available"))
    if config.request_agent_trace and traces and available_plans == 0:
        add_check(
            "agent_plan_visible",
            "fail",
            "Reviewer trace was requested but no AgentPlan was visible in the episode.",
        )
    elif config.request_agent_trace and available_plans < len(traces):
        add_check(
            "agent_plan_visible",
            "warn",
            "Some turns did not expose an AgentPlan for reviewer audit.",
            [f"available_plans:{available_plans}", f"turn_count:{len(traces)}"],
        )
    else:
        add_check(
            "agent_plan_visible",
            "pass",
            "AgentPlan trace is visible for the captured turns.",
            [f"available_plans:{available_plans}"],
        )

    if memory.observed_npc_ids:
        add_check(
            "npc_state_observed",
            "pass",
            "The trajectory observed at least one active or pulsed NPC.",
            [f"npc_ids:{','.join(memory.observed_npc_ids[:6])}"],
        )
    else:
        add_check(
            "npc_state_observed",
            "warn",
            "No active NPC state was observed across the trajectory.",
        )

    stage_phases = [
        str(trace.agent_plan_summary.get("stage_phase") or "")
        for trace in traces
        if trace.agent_plan_summary.get("stage_phase")
    ]
    if not stage_phases and config.request_agent_trace:
        add_check(
            "stage_progression_visible",
            "fail",
            "No AgentPlan stage phases were available for trajectory review.",
        )
    elif len(set(stage_phases)) == 1 and len(stage_phases) >= 3:
        add_check(
            "stage_progression_flat",
            "warn",
            "AgentPlan stage stayed flat across a multi-turn episode.",
            [f"stage:{stage_phases[0]}", f"turns:{len(stage_phases)}"],
        )
    elif stage_phases:
        add_check(
            "stage_progression_visible",
            "pass",
            "AgentPlan stage phases were visible for trajectory review.",
            [f"stages:{','.join(stage_phases[:8])}"],
        )

    role_ids = {trace.role_id for trace in traces if trace.role_id}
    if config.role_id and config.role_id not in role_ids:
        add_check(
            "role_coherence",
            "fail",
            "Configured role_id did not match the role observed in episode traces.",
            [f"configured:{config.role_id}", f"observed:{','.join(sorted(role_ids))}"],
        )
    elif role_ids:
        add_check(
            "role_coherence",
            "pass",
            "Episode traces include a concrete player role.",
            [f"roles:{','.join(sorted(role_ids))}"],
        )

    if memory.objective_progress in {"medium", "high"}:
        add_check(
            "objective_progress",
            "pass",
            "Compressed memory observed objective-relevant signals.",
            [f"objective_progress:{memory.objective_progress}"],
        )
    elif len(traces) >= 2:
        add_check(
            "objective_progress",
            "warn",
            "Episode advanced multiple turns without objective-relevant signals.",
            [f"objective_progress:{memory.objective_progress}"],
        )

    if config.leverage_policy != "never" and not memory.played_leverage_cards:
        add_check(
            "leverage_policy_exercised",
            "warn",
            "A leverage policy was configured but no sanitized leverage card was played.",
            [f"leverage_policy:{config.leverage_policy}"],
        )
    elif config.leverage_policy != "never":
        add_check(
            "leverage_policy_exercised",
            "pass",
            "The configured leverage policy produced a played leverage card.",
            [f"played_leverage_count:{len(memory.played_leverage_cards)}"],
        )
        no_payoff = [
            trace.narrator_ord
            for trace in traces
            if trace.selected_action.get("played_leverage") and not _trace_has_runtime_impact(trace)
        ]
        if no_payoff:
            add_check(
                "leverage_payoff_continuity",
                "warn",
                "Some played leverage cards did not produce visible runtime impact.",
                [f"narrator_ord:{ord_value}" for ord_value in no_payoff[:8]],
            )
        else:
            add_check(
                "leverage_payoff_continuity",
                "pass",
                "Played leverage cards produced visible pulse or inventory impact.",
            )

    leverage_card_ids = [
        str(card.get("card_id"))
        for card in memory.played_leverage_cards
        if card.get("card_id")
    ]
    repeated_leverage_cards = {
        card_id: count
        for card_id, count in Counter(leverage_card_ids).items()
        if count > 1
    }
    if repeated_leverage_cards:
        add_check(
            "leverage_card_reuse",
            "fail",
            "The mock user replayed a leverage card that was already spent in episode memory.",
            [f"{card_id}:{count}" for card_id, count in sorted(repeated_leverage_cards.items())[:8]],
        )
    elif leverage_card_ids:
        add_check(
            "leverage_card_reuse",
            "pass",
            "No leverage card id was replayed across the episode.",
        )

    if traces and any(_trace_has_runtime_impact(trace) for trace in traces):
        add_check(
            "runtime_impact_observed",
            "pass",
            "At least one turn produced pulse shift or inventory impact.",
        )
    elif traces:
        add_check(
            "low_divergence_no_impact",
            "warn",
            "Episode produced no pulse shift or inventory delta signals.",
            [f"turn_count:{len(traces)}"],
        )

    if len(traces) >= config.turn_budget or ending_detected:
        add_check(
            "episode_reached_stop_condition",
            "pass",
            "The episode reached the requested turn budget or an ending.",
            [f"ending_detected:{ending_detected}"],
        )
    else:
        add_check(
            "episode_reached_stop_condition",
            "warn",
            "The episode stopped before the requested budget without an ending.",
            [f"turn_count:{len(traces)}", f"turn_budget:{config.turn_budget}"],
        )

    status: JudgeStatusText
    if any(check.status == "fail" for check in checks):
        status = "fail"
    elif any(check.status == "warn" for check in checks):
        status = "warn"
    elif checks:
        status = "pass"
    else:
        status = "missing"
    return TrajectoryJudgeResult(
        status=status,
        turn_count=len(traces),
        checks=checks,
        summary=f"Trajectory judge {status}: {len(traces)} turns, {len(memory.observed_npc_ids)} observed NPC ids.",
    )


def run_mock_user_episode(
    config: MockUserConfig,
    adapter: NarrativeAPIAdapter,
) -> MockUserEpisodeResult:
    session_id = config.session_id
    loop_events: list[AgentLoopEvent] = []
    memory = _new_episode_memory(config)
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
        turn_loop_events: list[AgentLoopEvent] = []
        observation = _observation_summary(history)
        turn_loop_events.append(
            _loop_event(
                loop_events,
                turn_index=turn_index,
                action_type="observe",
                summary="Read latest narrator beat and available player options.",
                payload=observation,
            )
        )
        memory = _memory_from_observation(memory, history, config=config)
        memory_before_action = _memory_summary(memory)
        turn_loop_events.append(
            _loop_event(
                loop_events,
                turn_index=turn_index,
                action_type="update_memory",
                summary="Update sanitized episode memory from the latest observation.",
                payload=memory_before_action,
            )
        )
        action = choose_mock_user_action(history, config, turn_index=turn_index, memory=memory)
        selected_action = _selected_action_summary(action)
        turn_loop_events.append(
            _loop_event(
                loop_events,
                turn_index=turn_index,
                action_type="choose_action",
                summary="Apply deterministic player policy to choose the next action.",
                payload=selected_action,
            )
        )
        response = adapter.advance_turn(
            session_id,
            action.to_request(),
            agent_trace=config.request_agent_trace,
        )
        turn_loop_events.append(
            _loop_event(
                loop_events,
                turn_index=turn_index,
                action_type="play_turn",
                summary="Submit action to the narrative runtime.",
                payload={
                    "narrator_ord": response.narrator_message.ord,
                    "is_complete": response.is_complete,
                    "has_ending": response.ending is not None,
                },
            )
        )
        ending_detected = bool(response.is_complete or response.ending is not None)
        refreshed_history = adapter.get_story(session_id, agent_trace=config.request_agent_trace)
        turn_loop_events.append(
            _loop_event(
                loop_events,
                turn_index=turn_index,
                action_type="collect_events",
                summary="Refresh story history and reviewer trace after the turn.",
                payload={
                    "message_count": len(refreshed_history.messages),
                    "agent_event_count": len(refreshed_history.agent_events),
                    "ending_label": refreshed_history.session.ending_label,
                },
            )
        )
        plan, step, contract = _events_for_ord(
            refreshed_history,
            response.narrator_message.ord,
        )
        if plan is None:
            plan = response.agent_plan
        turn_loop_events.append(
            _loop_event(
                loop_events,
                turn_index=turn_index,
                action_type="collect_judges",
                summary="Collect StepJudge and ContractJudge results for the narrator turn.",
                payload={
                    "step_judge_status": _judge_status(step),
                    "step_judge_codes": _judge_codes(step),
                    "contract_judge_status": _judge_status(contract),
                    "contract_judge_codes": _judge_codes(contract),
                },
            )
        )
        trace = MockTurnTrace(
            turn_index=turn_index,
            narrator_ord=response.narrator_message.ord,
            role_id=refreshed_history.session.player_role.role_id
            if refreshed_history.session.player_role
            else None,
            observation_summary=observation,
            memory_before=memory_before_action,
            selected_action=selected_action,
            runtime_output_summary=_runtime_output_summary(response.narrator_message),
            agent_plan_summary=_agent_plan_summary(plan),
            action_loop=turn_loop_events,
            step_judge_status=_judge_status(step),
            step_judge_violation_codes=_judge_codes(step),
            contract_judge_status=_judge_status(contract),
            contract_judge_violation_codes=_judge_codes(contract),
        )
        memory = _memory_after_turn(
            memory,
            action=action,
            narrator_message=response.narrator_message,
            step=step,
            contract=contract,
            config=config,
        )
        memory_after_action = _memory_summary(memory)
        trace.memory_after = memory_after_action
        trace.memory_summary = memory_after_action
        traces.append(trace)
        history = refreshed_history

    trajectory_judge = judge_episode_trajectory(
        traces=traces,
        memory=memory,
        config=config,
        ending_detected=ending_detected or bool(history.session.ending_label),
    )
    _loop_event(
        loop_events,
        turn_index=None,
        action_type="judge_trajectory",
        summary="Run deterministic trajectory-level checks over the episode trace.",
        payload=trajectory_judge.model_dump(mode="json"),
    )
    result = MockUserEpisodeResult(
        config=config,
        session_id=session_id,
        role_id=history.session.player_role.role_id if history.session.player_role else None,
        episode_memory=memory,
        trajectory_judge=trajectory_judge,
        action_loop=loop_events,
        turns=traces,
        summary=_episode_summary(
            traces,
            requested_turn_budget=config.turn_budget,
            ending_detected=ending_detected or bool(history.session.ending_label),
            trajectory_judge=trajectory_judge,
        ),
    )
    _loop_event(
        loop_events,
        turn_index=None,
        action_type="summarize_episode",
        summary="Build compact episode summary for reviewer/eval inspection.",
        payload=result.summary.model_dump(mode="json"),
    )
    result = result.model_copy(update={"action_loop": loop_events})
    if config.trace_output_path:
        write_episode_trace(result, Path(config.trace_output_path))
    if config.summary_output_path:
        write_episode_summary(result, Path(config.summary_output_path))
    return result


def _episode_summary(
    traces: list[MockTurnTrace],
    *,
    requested_turn_budget: int,
    ending_detected: bool,
    trajectory_judge: TrajectoryJudgeResult,
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
    if trajectory_judge.status == "fail":
        recommendations.append("fix trajectory-level failures before treating the episode as release evidence")
    elif trajectory_judge.status == "warn":
        recommendations.append("review trajectory warnings before demo or portfolio capture")
    if not traces:
        recommendations.append("episode did not advance; check session state and turn budget")
    return MockUserEpisodeSummary(
        turn_count=len(traces),
        completed_turn_budget=len(traces) >= requested_turn_budget,
        ending_detected=ending_detected,
        step_status_counts=dict(step_counts),
        contract_status_counts=dict(contract_counts),
        trajectory_status=trajectory_judge.status,
        trajectory_check_counts=_trajectory_check_counts(trajectory_judge.checks),
        repeated_violation_codes=repeated,
        recommendations=recommendations,
    )


def write_episode_trace(result: MockUserEpisodeResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for event in result.action_loop:
        rows.append(
            {
                "record_type": "loop_event",
                "schema_version": event.schema_version,
                "session_id": result.session_id,
                "payload": event.model_dump(mode="json"),
            }
        )
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
            "record_type": "trajectory_judge",
            "schema_version": result.trajectory_judge.schema_version,
            "session_id": result.session_id,
            "payload": result.trajectory_judge.model_dump(mode="json"),
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


def write_episode_summary(result: MockUserEpisodeResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "schema_version": result.schema_version,
                "session_id": result.session_id,
                "role_id": result.role_id,
                "summary": result.summary.model_dump(mode="json"),
                "trajectory_judge": result.trajectory_judge.model_dump(mode="json"),
                "episode_memory": result.episode_memory.model_dump(mode="json"),
                "loop_event_count": len(result.action_loop),
                "turn_count": len(result.turns),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
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


class ServiceNarrativeAdapter:
    """In-process adapter for deterministic fixture runs."""

    def __init__(self, service: Any, *, player_user_id: str) -> None:
        self.service = service
        self.player_user_id = player_user_id

    def get_template(self, template_id: str) -> NarrativeTemplateSummary:
        return self.service.get_template(template_id, viewer_user_id=self.player_user_id)

    def start_session(
        self,
        template_id: str,
        *,
        player_role_index: int | None,
        turn_budget: int,
    ) -> StartSessionResponse:
        return self.service.start_session(
            template_id,
            player_user_id=self.player_user_id,
            turn_budget=turn_budget,
            difficulty="gauntlet",
            player_role_index=player_role_index,
        )

    def get_story(self, session_id: str, *, agent_trace: bool) -> StoryHistoryResponse:
        return self.service.get_story_history(
            session_id,
            player_user_id=self.player_user_id,
            include_agent_trace=agent_trace,
        )

    def advance_turn(
        self,
        session_id: str,
        payload: AdvanceTurnRequest,
        *,
        agent_trace: bool,
    ) -> AdvanceTurnResponse:
        return self.service.advance(
            session_id,
            payload,
            player_user_id=self.player_user_id,
            include_agent_trace=agent_trace,
        )


class _FixtureGateway:
    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        operation_name: str,
        max_output_tokens: int | None = None,
    ) -> ResponsesJSONResponse:
        del system_prompt, max_output_tokens
        if operation_name != "narrative.advance_turn":
            raise RuntimeError(f"fixture gateway only supports advance_turn, got {operation_name}")
        active_ids = [
            str(item.get("npc_id"))
            for item in user_payload.get("npc_agenda_this_turn", [])
            if isinstance(item, dict) and item.get("npc_id")
        ]
        target = active_ids[0] if active_ids else "evan"
        passage = (
            f"{target.title()} reacts to the player's move and forces the room "
            "to account for the exposed contradiction."
        )
        return ResponsesJSONResponse(
            payload={
                "passage": passage,
                "options": [
                    {
                        "label": "Ask who benefits from the contradiction",
                        "hint": "Probe motive without spending all leverage",
                        "handle": "probe",
                    },
                    {
                        "label": "Show the audit packet",
                        "hint": "Use proof to shift pressure",
                        "handle": "show",
                    },
                    {
                        "label": "Slow the room down",
                        "hint": "Negotiate before the public break",
                        "handle": "slow",
                    },
                ],
                "npc_pulse": [
                    {
                        "npc_id": target,
                        "state": "pressing the contradiction",
                        "shift": "wary",
                        "reason": "The player kept the evidence visible.",
                    }
                ],
                "inventory_delta": {
                    "added": ["audited contradiction marker"],
                    "removed": [],
                    "reason": "The room now treats the contradiction as evidence.",
                },
            },
            response_id=f"fixture-{uuid4().hex[:8]}",
            usage={},
            input_characters=len(str(user_payload)),
        )


def build_fixture_adapter(config: MockUserConfig) -> tuple[NarrativeAPIAdapter, MockUserConfig]:
    from rpg_backend.narrative.repository import NarrativeRepository
    from rpg_backend.narrative.service import NarrativeService

    if config.fixture != "merger_audit":
        raise ValueError(f"unsupported fixture: {config.fixture}")

    tmpdir = tempfile.TemporaryDirectory(prefix="tiny-stories-agent-eval-")
    repo = NarrativeRepository(str(Path(tmpdir.name) / "fixture.sqlite3"))
    template_id = config.template_id or f"tmpl_fixture_{uuid4().hex[:8]}"
    session_id = config.session_id or f"sess_fixture_{uuid4().hex[:8]}"
    player_user_id = "fixture-reviewer"
    repo.create_template(
        template_id=template_id,
        owner_user_id="fixture-owner",
        seed="A cofounder announces a secret merger before the audit is ready.",
        title="Offline Merger Audit Fixture",
        cast=_fixture_cast(),
        advisor_persona="A concise reviewer-safe strategy coach.",
        opening_passage="The control room goes quiet as the audit packet lands on the table.",
        opening_options=[
            StoryOption(label="Ask Evan to explain the memo", hint="Probe the source", handle="probe"),
            StoryOption(label="Show the audit seal", hint="Use proof carefully", handle="show"),
            StoryOption(label="Let Mira answer first", hint="Delay and observe", handle="wait"),
        ],
        player_goals=[PlayerGoal(goal="Keep the vote alive", stakes="The company may collapse.")],
        failure_conditions=[],
        player_role_options=[
            _fixture_player_role("founder", "Founder"),
            _fixture_player_role("observer", "Observer"),
        ],
        visibility="public",
        language="en",
    )
    repo.create_session(
        session_id=session_id,
        template_id=template_id,
        player_user_id=player_user_id,
        turn_budget=max(config.turn_budget + 2, 4),
        difficulty="gauntlet",
        selected_player_role_id=config.role_id or "founder",
    )
    repo.append_story_message(
        session_id,
        StoryMessage(
            ord=0,
            role="narrator",
            content="The control room goes quiet as the audit packet lands on the table.",
            options=[
                StoryOption(label="Ask Evan to explain the memo", hint="Probe the source", handle="probe"),
                StoryOption(label="Show the audit seal", hint="Use proof carefully", handle="show"),
                StoryOption(label="Let Mira answer first", hint="Delay and observe", handle="wait"),
            ],
            npc_pulse=[NPCPulse(npc_id="evan", state="watching the packet", shift="wary")],
        ),
    )
    service = NarrativeService(repository=repo, gateway=_FixtureGateway())
    adapter = ServiceNarrativeAdapter(service, player_user_id=player_user_id)
    setattr(adapter, "_tmpdir", tmpdir)
    return adapter, config.model_copy(update={"session_id": session_id, "template_id": template_id})


def _fixture_cast() -> list[CastMember]:
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


def _fixture_player_role(role_id: str, label: str) -> PlayerRole:
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


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a deterministic mock player against the live narrative API by "
            "default and archive an inspectable agent/judge episode trace. "
            "Use --mode fixture only for CI/test dry-runs."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=("fixture", "live"), default="live")
    parser.add_argument("--fixture", choices=("merger_audit", "none"), default="merger_audit")
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
    parser.add_argument("--summary-output", dest="summary_output_path", default="artifacts/mock_user_episode_summary.json")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    config = MockUserConfig(
        session_id=args.session_id,
        template_id=args.template_id,
        mode=args.mode,
        fixture=args.fixture,
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
        summary_output_path=args.summary_output_path,
    )
    if config.mode == "live" and config.session_id is None and config.template_id is None:
        raise SystemExit("live mode requires --session <session_id> or --template <template_id>")
    if config.mode == "fixture":
        adapter, config = build_fixture_adapter(config)
    else:
        adapter = LiveHTTPNarrativeAdapter(
            config.base_url or "http://127.0.0.1:8000",
            reviewer_username=config.reviewer_username,
        )
    result = run_mock_user_episode(config, adapter)
    print(result.summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
