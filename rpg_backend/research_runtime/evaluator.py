from __future__ import annotations

import re
from statistics import mean

from rpg_backend.research_runtime.contracts import (
    EvaluationStatus,
    RpgCriterionResultV1,
    RpgEvaluationBundleV1,
    RpgEvaluationReportV1,
)


TECHNICAL_LEAK_RE = re.compile(
    r"\b(provider|model id|api key|schema|token count|chain[- ]of[- ]thought|scratchpad|raw json|fallback_used)\b",
    re.I,
)


def _status(score: int) -> EvaluationStatus:
    if score >= 80:
        return "pass"
    if score >= 55:
        return "warn"
    return "fail"


def _criterion(name: str, score: int, summary: str, evidence: list[str]) -> RpgCriterionResultV1:
    return RpgCriterionResultV1(
        criterion=name,
        status=_status(score),
        score=score,
        summary=summary,
        evidence=evidence[:6],
    )


def evaluate_rpg_bundle(bundle: RpgEvaluationBundleV1) -> RpgEvaluationReportV1:
    turns = bundle.turns
    memory_conflicts: list[str] = []
    memory_overflow: list[str] = []
    consequence_gaps: list[str] = []
    agency_gaps: list[str] = []
    entity_gaps: list[str] = []
    leakage: list[str] = []
    option_signatures: set[tuple[str, ...]] = set()

    previous_progress = 0.0
    progress_regressions = 0
    progress_advances = 0
    for turn in turns:
        active_keys: set[tuple[str, str]] = set()
        superseded_ids = {fact.fact_id for fact in turn.memory.superseded_facts}
        for fact in turn.memory.active_facts:
            lookup = (fact.namespace.casefold(), fact.key.casefold())
            if lookup in active_keys:
                memory_conflicts.append(f"Turn {turn.turn_index}: duplicate active fact {fact.namespace}.{fact.key}")
            active_keys.add(lookup)
            if fact.fact_id in superseded_ids or fact.status != "active":
                memory_conflicts.append(f"Turn {turn.turn_index}: superseded fact remained active")
        if len(turn.memory.active_facts) > 24 or len(turn.memory.recent_events) > 8:
            memory_overflow.append(f"Turn {turn.turn_index}: memory exceeded the portable budget")

        if not turn.state_deltas and not turn.clue_unlocks and not turn.opportunity_unlocks:
            consequence_gaps.append(f"Turn {turn.turn_index}: no typed visible consequence")
        normalized_options = tuple(" ".join(option.casefold().split()) for option in turn.options)
        if len(set(normalized_options)) < 2:
            agency_gaps.append(f"Turn {turn.turn_index}: fewer than two distinct options")
        option_signatures.add(normalized_options)

        unknown_entities = set(turn.referenced_entity_ids) - set(bundle.scenario.entity_ids)
        if unknown_entities:
            entity_gaps.append(f"Turn {turn.turn_index}: unknown entities {', '.join(sorted(unknown_entities))}")

        visible_text = " ".join([turn.player_action, turn.world_response, *turn.options])
        if TECHNICAL_LEAK_RE.search(visible_text):
            leakage.append(f"Turn {turn.turn_index}: technical wording appeared in player-facing text")

        if turn.objective_progress + 0.001 < previous_progress:
            progress_regressions += 1
        elif turn.objective_progress > previous_progress + 0.05:
            progress_advances += 1
        previous_progress = max(previous_progress, turn.objective_progress)

    criteria = [
        _criterion(
            "memory_continuity",
            max(0, 100 - 35 * len(memory_conflicts)),
            "Active facts remain singular and corrections are retained as superseded evidence."
            if not memory_conflicts
            else "Memory contains active/superseded conflicts that can distort later turns.",
            memory_conflicts or [f"{len(turns)} snapshots checked with no active fact conflict."],
        ),
        _criterion(
            "memory_boundedness",
            max(0, 100 - 40 * len(memory_overflow)),
            "Memory stays within the portable fact and recency budgets."
            if not memory_overflow
            else "One or more snapshots exceeded the bounded memory budget.",
            memory_overflow or ["Active facts <= 24 and recent events <= 8 for every turn."],
        ),
        _criterion(
            "consequence_visibility",
            round(100 * (len(turns) - len(consequence_gaps)) / len(turns)),
            "Moves resolve into explicit deltas, clues, or opportunities."
            if not consequence_gaps
            else "Some moves only produced prose without a visible game-state consequence.",
            consequence_gaps or [f"All {len(turns)} turns expose at least one typed consequence."],
        ),
        _criterion(
            "player_agency",
            max(0, round(100 * (len(turns) - len(agency_gaps)) / len(turns))),
            "Each turn preserves at least two distinct next actions."
            if not agency_gaps
            else "At least one turn collapsed into a single or duplicated action path.",
            agency_gaps or [f"Distinct choices preserved across {len(turns)} turns."],
        ),
        _criterion(
            "trajectory_progress",
            max(0, min(100, round(previous_progress * 70) + min(30, progress_advances * 10) - progress_regressions * 25)),
            "Objective progress advances without unexplained regression."
            if progress_regressions == 0
            else "Objective progress regressed on at least one turn.",
            [
                f"Final observed progress: {previous_progress:.0%}.",
                f"Meaningful advances: {progress_advances}; regressions: {progress_regressions}.",
            ],
        ),
        _criterion(
            "entity_coherence",
            max(0, 100 - 35 * len(entity_gaps)),
            "Referenced people and factions remain inside the scenario registry."
            if not entity_gaps
            else "The run referenced entities absent from the scenario contract.",
            entity_gaps or [f"Validated against {len(bundle.scenario.entity_ids)} registered entities."],
        ),
        _criterion(
            "choice_diversity",
            round(100 * len(option_signatures) / len(turns)),
            "Next-action sets change as the trajectory changes."
            if len(option_signatures) == len(turns)
            else "Some turns repeated the same full action set.",
            [f"{len(option_signatures)} distinct action sets across {len(turns)} turns."],
        ),
        _criterion(
            "boundary_hygiene",
            max(0, 100 - 50 * len(leakage)),
            "Player-facing text is free of protocol and private-reasoning language."
            if not leakage
            else "Technical implementation wording leaked into player-facing text.",
            leakage or ["No provider, schema, token, raw JSON, or private-reasoning terms detected."],
        ),
    ]
    score = round(mean(item.score for item in criteria))
    return RpgEvaluationReportV1(
        run_id=bundle.run_id,
        system_label=bundle.system_label,
        status=_status(score),
        score=score,
        criteria=criteria,
        limitations=[
            "This deterministic report is a product reliability diagnostic, not a calibrated research metric.",
            "Narrative appeal and emotional quality still require bounded human review.",
            "Imported state deltas are trusted only to the extent that the source adapter is trustworthy.",
        ],
    )
