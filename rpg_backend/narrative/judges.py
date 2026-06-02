from __future__ import annotations

from collections.abc import Iterable

from rpg_backend.narrative.contracts import (
    AgentPlan,
    CastMember,
    ContractJudgeResult,
    InventoryDelta,
    JudgeSeverity,
    JudgeStatus,
    JudgeViolation,
    PlayerRole,
    StepJudgeResult,
    StoryMessage,
)


_NOOP_DELTA_REASONS = {
    "",
    "none",
    "n/a",
    "no change",
    "unchanged",
    "same as before",
    "placeholder",
}
_PRESSURE_WORDS = {
    "break",
    "broken",
    "cost",
    "collapse",
    "confront",
    "betray",
    "pressure",
    "reveal",
    "strained",
    "strain",
    "threat",
    "wary",
}
_HIGH_STAGES = {"reversal", "climax", "pre_finale", "pre_finale_open", "finale"}


def judge_step(
    *,
    agent_plan: AgentPlan,
    player_message: StoryMessage,
    narrator_message: StoryMessage,
    cast: list[CastMember],
) -> StepJudgeResult:
    """Deterministic audit of whether the turn paid off the AgentPlan."""
    violations: list[JudgeViolation] = []
    cast_by_id = {npc.character_id: npc for npc in cast}

    for npc_id in agent_plan.director.active_npc_ids:
        npc = cast_by_id.get(npc_id)
        if not _npc_has_observable_presence(npc_id, npc, narrator_message):
            violations.append(
                _violation(
                    code="active_npc_intent_missing",
                    severity="error",
                    rationale=(
                        "The director scheduled an active NPC, but the narrator turn "
                        "did not show that NPC in pulse or visible consequence."
                    ),
                    evidence=[
                        f"director.active_npc_ids:{npc_id}",
                        f"narrator_ord:{narrator_message.ord}",
                    ],
                )
            )

    if player_message.played_leverage is not None:
        leverage = player_message.played_leverage
        target_npc = cast_by_id.get(leverage.npc_id)
        if not _played_leverage_has_impact(leverage.npc_id, target_npc, narrator_message):
            violations.append(
                _violation(
                    code="played_leverage_no_observable_impact",
                    severity="error",
                    rationale=(
                        "The player committed a leverage card, but the turn has no "
                        "target pulse shift, inventory impact, or explicit consequence."
                    ),
                    evidence=[
                        f"played_leverage.card_id:{leverage.card_id}",
                        f"played_leverage.npc_id:{leverage.npc_id}",
                    ],
                )
            )

    if _is_twist_or_high_stage(agent_plan) and not _has_observable_consequence(narrator_message):
        violations.append(
            _violation(
                code="twist_turn_no_consequence",
                severity="warn",
                rationale=(
                    "A twist, reversal, climax, or finale-stage turn should produce "
                    "a visible pulse shift, inventory change, or consequence signal."
                ),
                evidence=[
                    f"stage_phase:{agent_plan.director.stage_phase}",
                    f"twist_kind:{agent_plan.director.twist_kind or 'none'}",
                ],
            )
        )

    violations.extend(
        _inventory_delta_violations(
            narrator_message.inventory_delta,
            empty_code="inventory_delta_empty",
            reason_code="inventory_delta_reason_missing",
            conflict_code="inventory_delta_conflicting_refs",
        )
    )

    if _is_high_expected_pressure(agent_plan) and not _has_pressure_signal(narrator_message):
        violations.append(
            _violation(
                code="expected_pressure_not_observed",
                severity="warn",
                rationale=(
                    "The director expected high pressure, but the turn lacks a pulse "
                    "shift, inventory change, or pressure consequence language."
                ),
                evidence=[f"expected_pressure:{agent_plan.director.expected_pressure}"],
            )
        )

    return StepJudgeResult(
        turn_index=agent_plan.turn_index,
        narrator_ord=agent_plan.narrator_ord,
        status=_status_from(violations),
        violations=violations[:12],
        summary=_summary("step judge", violations),
    )


def judge_contract(
    *,
    agent_plan: AgentPlan,
    player_message: StoryMessage,
    narrator_message: StoryMessage,
    cast: list[CastMember],
    player_role: PlayerRole | None = None,
) -> ContractJudgeResult:
    """Deterministic runtime contract audit for one narrator turn."""
    violations: list[JudgeViolation] = []
    known_npc_ids = {npc.character_id for npc in cast}

    if narrator_message.role != "narrator":
        violations.append(
            _violation(
                code="narrator_role_invalid",
                severity="error",
                rationale="Contract judge expected a narrator message.",
                evidence=[f"role:{narrator_message.role}"],
            )
        )

    if not narrator_message.content.strip():
        violations.append(
            _violation(
                code="passage_empty",
                severity="error",
                rationale="Narrator passage must not be empty.",
                evidence=[f"narrator_ord:{narrator_message.ord}"],
            )
        )

    if not 1 <= len(narrator_message.options) <= 4:
        violations.append(
            _violation(
                code="options_count_invalid",
                severity="error",
                rationale="Narrator output should include between 1 and 4 player options.",
                evidence=[f"options_count:{len(narrator_message.options)}"],
            )
        )
    for index, option in enumerate(narrator_message.options):
        if not option.label.strip():
            violations.append(
                _violation(
                    code="option_label_missing",
                    severity="error",
                    rationale="Each option needs a visible label.",
                    evidence=[f"option_index:{index}"],
                )
            )

    for pulse in narrator_message.npc_pulse:
        if pulse.npc_id not in known_npc_ids:
            violations.append(
                _violation(
                    code="unknown_npc_pulse_id",
                    severity="error",
                    rationale="npc_pulse referenced an NPC id that is not in the template cast.",
                    evidence=[f"npc_pulse.npc_id:{pulse.npc_id}"],
                )
            )

    for npc_id in agent_plan.director.active_npc_ids:
        if npc_id not in known_npc_ids:
            violations.append(
                _violation(
                    code="unknown_director_npc_id",
                    severity="error",
                    rationale="AgentPlan director referenced an NPC id that is not in the template cast.",
                    evidence=[f"director.active_npc_ids:{npc_id}"],
                )
            )
    for intent in agent_plan.npc_intents:
        if intent.npc_id not in known_npc_ids:
            violations.append(
                _violation(
                    code="unknown_npc_intent_id",
                    severity="error",
                    rationale="AgentPlan NPC intent referenced an NPC id that is not in the template cast.",
                    evidence=[f"npc_intents.npc_id:{intent.npc_id}"],
                )
            )

    if player_message.played_leverage is not None:
        target_id = player_message.played_leverage.npc_id
        if target_id not in known_npc_ids:
            violations.append(
                _violation(
                    code="unknown_played_leverage_npc",
                    severity="error",
                    rationale="Played leverage referenced an NPC id that is not in the template cast.",
                    evidence=[f"played_leverage.npc_id:{target_id}"],
                )
            )
        if player_role is not None:
            known_cards = {card.npc_id for card in player_role.leverages_over_npcs}
            if target_id in known_npc_ids and target_id not in known_cards:
                violations.append(
                    _violation(
                        code="played_leverage_not_in_role",
                        severity="warn",
                        rationale="Played leverage target is not present in the selected player role card list.",
                        evidence=[
                            f"played_leverage.npc_id:{target_id}",
                            f"role_id:{player_role.role_id}",
                        ],
                    )
                )

    violations.extend(_hidden_info_leak_violations(cast, narrator_message))
    violations.extend(
        _inventory_delta_violations(
            narrator_message.inventory_delta,
            empty_code="inventory_delta_noop",
            reason_code="inventory_delta_reason_unusable",
            conflict_code="inventory_delta_conflicting_refs",
        )
    )

    if _is_twist_or_high_stage(agent_plan) and not _has_observable_consequence(narrator_message):
        violations.append(
            _violation(
                code="stage_contract_no_consequence",
                severity="warn",
                rationale="High-stage/twist runtime output should not be a steady no-op.",
                evidence=[
                    f"stage_phase:{agent_plan.director.stage_phase}",
                    f"twist_kind:{agent_plan.director.twist_kind or 'none'}",
                ],
            )
        )

    return ContractJudgeResult(
        turn_index=agent_plan.turn_index,
        narrator_ord=agent_plan.narrator_ord,
        status=_status_from(violations),
        violations=violations[:12],
        summary=_summary("contract judge", violations),
    )


def _npc_has_observable_presence(
    npc_id: str,
    npc: CastMember | None,
    narrator_message: StoryMessage,
) -> bool:
    if any(pulse.npc_id == npc_id for pulse in narrator_message.npc_pulse):
        return True
    haystack = narrator_message.content.casefold()
    if npc_id.casefold() in haystack:
        return True
    return bool(npc and npc.display_name.casefold() in haystack)


def _played_leverage_has_impact(
    npc_id: str,
    npc: CastMember | None,
    narrator_message: StoryMessage,
) -> bool:
    for pulse in narrator_message.npc_pulse:
        if pulse.npc_id == npc_id and pulse.shift != "steady":
            return True
    if _meaningful_inventory_delta(narrator_message.inventory_delta):
        return True
    return _npc_has_observable_presence(npc_id, npc, narrator_message) and _has_pressure_signal(
        narrator_message
    )


def _has_observable_consequence(message: StoryMessage) -> bool:
    return _has_nonsteady_pulse(message) or _meaningful_inventory_delta(message.inventory_delta)


def _has_pressure_signal(message: StoryMessage) -> bool:
    if _has_observable_consequence(message):
        return True
    text = _message_visible_text(message).casefold()
    return any(word in text for word in _PRESSURE_WORDS)


def _has_nonsteady_pulse(message: StoryMessage) -> bool:
    return any(pulse.shift != "steady" for pulse in message.npc_pulse)


def _meaningful_inventory_delta(delta: InventoryDelta | None) -> bool:
    if delta is None:
        return False
    return bool(delta.added or delta.removed)


def _inventory_delta_violations(
    delta: InventoryDelta | None,
    *,
    empty_code: str,
    reason_code: str,
    conflict_code: str,
) -> list[JudgeViolation]:
    if delta is None:
        return []
    violations: list[JudgeViolation] = []
    if not delta.added and not delta.removed:
        violations.append(
            _violation(
                code=empty_code,
                severity="warn",
                rationale="inventory_delta is present but does not add or remove anything.",
                evidence=["inventory_delta.added:0", "inventory_delta.removed:0"],
            )
        )
    if delta.added or delta.removed:
        reason = delta.reason.strip().casefold()
        if reason in _NOOP_DELTA_REASONS or len(reason) < 4:
            violations.append(
                _violation(
                    code=reason_code,
                    severity="warn",
                    rationale="inventory_delta changed state without an auditable reason.",
                    evidence=[f"inventory_delta.reason:{delta.reason or '<empty>'}"],
                )
            )
    overlap = set(delta.added).intersection(set(delta.removed))
    if overlap:
        violations.append(
            _violation(
                code=conflict_code,
                severity="warn",
                rationale="inventory_delta adds and removes the same reference in one turn.",
                evidence=[f"inventory_delta.ref:{next(iter(overlap))}"],
            )
        )
    return violations


def _hidden_info_leak_violations(
    cast: list[CastMember],
    narrator_message: StoryMessage,
) -> list[JudgeViolation]:
    visible_text = _message_visible_text(narrator_message).casefold()
    leaks: list[JudgeViolation] = []
    for label, sensitive_text in _sensitive_cast_strings(cast):
        normalized = sensitive_text.strip().casefold()
        if len(normalized) < 12:
            continue
        if normalized in visible_text:
            leaks.append(
                _violation(
                    code="hidden_info_leak",
                    severity="error",
                    rationale="Narrator output exposed hidden cast information verbatim.",
                    evidence=[label],
                )
            )
    return leaks


def _sensitive_cast_strings(cast: Iterable[CastMember]) -> Iterable[tuple[str, str]]:
    for npc in cast:
        if npc.hidden_objective:
            yield f"cast.{npc.character_id}.hidden_objective", npc.hidden_objective
        if npc.leverage_over_player:
            yield f"cast.{npc.character_id}.leverage_over_player", npc.leverage_over_player
        for index, leverage in enumerate(npc.leverages_over_other_npcs):
            yield (
                f"cast.{npc.character_id}.leverages_over_other_npcs.{index}",
                leverage.leverage,
            )


def _message_visible_text(message: StoryMessage) -> str:
    parts = [message.content]
    for option in message.options:
        parts.extend([option.label, option.hint, option.handle])
    for pulse in message.npc_pulse:
        parts.extend([pulse.npc_id, pulse.state, pulse.shift, pulse.reason or ""])
    if message.inventory_delta is not None:
        parts.extend(message.inventory_delta.added)
        parts.extend(message.inventory_delta.removed)
        parts.append(message.inventory_delta.reason)
    return "\n".join(parts)


def _is_twist_or_high_stage(agent_plan: AgentPlan) -> bool:
    stage = agent_plan.director.stage_phase.strip().casefold()
    return bool(agent_plan.director.twist_kind or agent_plan.twist_directive or stage in _HIGH_STAGES)


def _is_high_expected_pressure(agent_plan: AgentPlan) -> bool:
    return "high" in agent_plan.director.expected_pressure.strip().casefold()


def _status_from(violations: list[JudgeViolation]) -> JudgeStatus:
    if any(v.severity == "error" for v in violations):
        return "fail"
    if any(v.severity == "warn" for v in violations):
        return "warn"
    return "pass"


def _summary(label: str, violations: list[JudgeViolation]) -> str:
    status = _status_from(violations)
    if status == "pass":
        return f"{label} pass: runtime output satisfied deterministic checks."
    return f"{label} {status}: {len(violations)} deterministic issue(s) archived."


def _violation(
    *,
    code: str,
    severity: JudgeSeverity,
    rationale: str,
    evidence: list[str],
) -> JudgeViolation:
    return JudgeViolation(
        code=code,
        severity=severity,
        rationale=rationale,
        evidence=evidence,
    )
