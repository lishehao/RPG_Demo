from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from math import ceil
from pathlib import Path
from typing import Any

from tools.rpg_eval.tiny_stories_reliability_harness import (
    LIVE_ACCEPTED_SOURCE_LABELS,
    LIVE_ACCEPTED_STATUSES,
    LIVE_ACCEPTANCE_SEED,
    REQUIRED_HEALTH_CONFIG,
    REPO_ROOT,
    LiveHarnessClient,
    LiveHarnessHTTPError,
    _event_summary,
    _events_by_operation,
    _health_failures,
    _live_failure,
    _live_operation_failures,
    _load_live_events_from_runtime_db,
    _session_event_failures,
    _utc_now_iso,
    _write_json,
)


GOLDEN_PATH_TURN_BUDGET = 12
DEFAULT_OUTPUT = REPO_ROOT / "artifacts/eval_tiny_stories/golden_path_12_turn_summary.json"
DEFAULT_REPORT = REPO_ROOT / "artifacts/eval_tiny_stories/golden_path_12_turn_report.md"
GOLDEN_PATH_REQUIRED_OPERATIONS = {
    "create.story_butler_turn",
    "narrative.story_brief",
    "narrative.opening",
    "narrative.advance_turn",
}
QUALITY_CRITERIA = (
    "consequence_clarity",
    "choice_diversity",
    "escalation",
    "character_intent",
    "brief_payoff",
    "playable_options",
)


def _latest_narrator(story: dict[str, Any]) -> dict[str, Any] | None:
    narrators = [
        message for message in story.get("messages") or []
        if isinstance(message, dict) and message.get("role") == "narrator"
    ]
    return narrators[-1] if narrators else None


def _option_labels(narrator: dict[str, Any] | None) -> list[str]:
    if narrator is None:
        return []
    labels: list[str] = []
    for option in narrator.get("options") or []:
        if isinstance(option, dict):
            label = str(option.get("label") or "").strip()
            if label:
                labels.append(label)
    return labels


def _choose_option_index(story: dict[str, Any], turn_number: int) -> int:
    labels = _option_labels(_latest_narrator(story))
    if not labels:
        return 0
    # Vary the path deterministically so the golden run is not twelve
    # identical first-option choices, while staying stable across reruns.
    return (turn_number - 1) % min(len(labels), 3)


def _agent_event_payloads(events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != event_type:
            continue
        payload = event.get("payload")
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _status_counts(payloads: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "unknown": 0}
    for payload in payloads:
        status = str(payload.get("status") or "unknown")
        if status not in counts:
            status = "unknown"
        counts[status] += 1
    return counts


def _stage_phase(payload: dict[str, Any]) -> str | None:
    director = payload.get("director")
    if isinstance(director, dict):
        phase = str(director.get("stage_phase") or "").strip()
        return phase or None
    return None


def _active_npc_count(payload: dict[str, Any]) -> int:
    director = payload.get("director")
    if not isinstance(director, dict):
        return 0
    active = director.get("active_npc_ids")
    return len(active) if isinstance(active, list) else 0


def _focused_npc_count(payload: dict[str, Any]) -> int:
    director = payload.get("director")
    if not isinstance(director, dict):
        return 0
    focused = director.get("focus_window_npc_ids")
    return len(focused) if isinstance(focused, list) else 0


def _director_difficulty(payload: dict[str, Any]) -> str | None:
    director = payload.get("director")
    if not isinstance(director, dict):
        return None
    difficulty = str(director.get("difficulty") or "").strip()
    return difficulty or None


def _npc_response_evidence(
    story: dict[str, Any],
    *,
    expected_turn_count: int,
) -> dict[str, Any]:
    narrators = [
        message for message in story.get("messages") or []
        if isinstance(message, dict) and message.get("role") == "narrator"
    ]
    # A complete story includes the opening narrator message before resolved
    # turn messages. Keep the newest expected_turn_count beats so the opening
    # does not dilute the response-rate denominator.
    if expected_turn_count > 0 and len(narrators) > expected_turn_count:
        narrators = narrators[-expected_turn_count:]

    responsive_turns = 0
    shifted_turns = 0
    distinct_npc_ids: set[str] = set()
    for message in narrators:
        pulses = [pulse for pulse in message.get("npc_pulse") or [] if isinstance(pulse, dict)]
        if not pulses:
            continue
        responsive_turns += 1
        has_meaningful_shift = False
        for pulse in pulses:
            npc_id = str(pulse.get("npc_id") or "").strip()
            if npc_id:
                distinct_npc_ids.add(npc_id)
            shift = str(pulse.get("shift") or "").strip().casefold()
            if shift and shift not in {"steady", "unchanged", "neutral", "none"}:
                has_meaningful_shift = True
        if has_meaningful_shift:
            shifted_turns += 1

    return {
        "observed_turns": len(narrators),
        "responsive_npc_turns": responsive_turns,
        "shifted_npc_turns": shifted_turns,
        "distinct_npc_ids": sorted(distinct_npc_ids),
    }


def _visible_text_for_payoff(story: dict[str, Any], ending: dict[str, Any] | None) -> str:
    parts: list[str] = []
    for message in story.get("messages") or []:
        if isinstance(message, dict):
            parts.append(str(message.get("content") or ""))
    if isinstance(ending, dict):
        parts.extend([
            str(ending.get("label") or ""),
            str(ending.get("subtitle") or ""),
            str(ending.get("passage") or ""),
        ])
    return " ".join(parts).casefold()


def _quality_summary(
    *,
    turn_summaries: list[dict[str, Any]],
    agent_events: list[dict[str, Any]],
    story: dict[str, Any],
    ending: dict[str, Any] | None,
    seed: str,
) -> dict[str, Any]:
    step_payloads = _agent_event_payloads(agent_events, "step_judge")
    contract_payloads = _agent_event_payloads(agent_events, "contract_judge")
    plan_payloads = _agent_event_payloads(agent_events, "agent_plan")
    step_counts = _status_counts(step_payloads)
    contract_counts = _status_counts(contract_payloads)
    stage_phases = [phase for payload in plan_payloads if (phase := _stage_phase(payload))]
    active_npc_turns = sum(1 for payload in plan_payloads if _active_npc_count(payload) > 0)
    focused_npc_turns = sum(1 for payload in plan_payloads if _focused_npc_count(payload) > 0)
    difficulties = [
        difficulty for payload in plan_payloads
        if (difficulty := _director_difficulty(payload))
    ]
    character_mode = "gauntlet" if "gauntlet" in difficulties or (not difficulties and active_npc_turns) else "story"
    npc_response = _npc_response_evidence(story, expected_turn_count=len(turn_summaries))
    observed_character_turns = max(1, int(npc_response["observed_turns"]) or len(turn_summaries))
    responsive_required = max(1, ceil(observed_character_turns * (0.5 if character_mode == "gauntlet" else 0.75)))
    shifted_required = max(1, ceil(observed_character_turns * 0.5))
    distinct_required = 1 if observed_character_turns == 1 else 2
    active_required = max(2, ceil(len(plan_payloads) * 0.4)) if plan_payloads else 1
    character_intent_passes = (
        int(npc_response["responsive_npc_turns"]) >= responsive_required
        and int(npc_response["shifted_npc_turns"]) >= shifted_required
        and len(npc_response["distinct_npc_ids"]) >= distinct_required
        and (character_mode != "gauntlet" or active_npc_turns >= active_required)
    )
    non_final = [turn for turn in turn_summaries if not turn.get("is_complete")]
    chosen_labels = [
        str(turn.get("chosen_option_label") or "").strip().casefold()
        for turn in turn_summaries
        if str(turn.get("chosen_option_label") or "").strip()
    ]
    option_counts = [
        int(turn.get("next_option_count") or 0)
        for turn in non_final
    ]
    visible_text = _visible_text_for_payoff(story, ending)
    payoff_terms = [
        term for term in ("gala", "award", "livestream", "publicist", "singer", "sponsor", "trophy")
        if term in seed.casefold()
    ]
    payoff_hits = [term for term in payoff_terms if term in visible_text]

    criteria = {
        "consequence_clarity": {
            "status": "pass" if step_counts["fail"] == 0 and contract_counts["fail"] == 0 else "fail",
            "evidence": {
                "step_judge": step_counts,
                "contract_judge": contract_counts,
            },
        },
        "choice_diversity": {
            "status": "pass" if len(set(chosen_labels)) >= 4 else "warn",
            "evidence": {
                "unique_chosen_option_labels": len(set(chosen_labels)),
                "chosen_option_labels": chosen_labels[:12],
            },
        },
        "escalation": {
            "status": "pass" if len(set(stage_phases)) >= 4 and any(phase in {"climax", "pre_finale", "finale"} for phase in stage_phases) else "warn",
            "evidence": {
                "stage_phases": stage_phases,
                "distinct_stage_phases": sorted(set(stage_phases)),
            },
        },
        "character_intent": {
            "status": "pass" if character_intent_passes else "warn",
            "evidence": {
                "mode": character_mode,
                "active_npc_turns": active_npc_turns,
                "active_npc_turns_required": active_required if character_mode == "gauntlet" else 0,
                "focused_npc_turns": focused_npc_turns,
                "responsive_npc_turns": npc_response["responsive_npc_turns"],
                "responsive_npc_turns_required": responsive_required,
                "shifted_npc_turns": npc_response["shifted_npc_turns"],
                "shifted_npc_turns_required": shifted_required,
                "distinct_npc_ids": npc_response["distinct_npc_ids"],
                "distinct_npc_ids_required": distinct_required,
                "plan_count": len(plan_payloads),
            },
        },
        "brief_payoff": {
            "status": "pass" if ending and len(payoff_hits) >= max(2, min(4, len(payoff_terms))) else "warn",
            "evidence": {
                "ending_present": bool(ending),
                "payoff_terms_seen": payoff_hits,
            },
        },
        "playable_options": {
            "status": "pass" if option_counts and min(option_counts) >= 2 else "fail",
            "evidence": {
                "non_final_option_counts": option_counts,
                "min_non_final_option_count": min(option_counts) if option_counts else 0,
            },
        },
    }
    verdict = "pass"
    if any(item["status"] == "fail" for item in criteria.values()):
        verdict = "fail"
    elif any(item["status"] == "warn" for item in criteria.values()):
        verdict = "warn"
    rationale = (
        "Deterministic quality packaging only: it checks judge pass/fail rows, "
        "choice variety, stage escalation, mode-aware character response, ending payoff, and option availability. "
        "It is not a calibrated fun metric."
    )
    return {
        "schema_version": "tiny_stories_golden_path_quality.v2",
        "status": verdict,
        "criteria": criteria,
        "rationale": rationale,
    }


def _accepted_live_event(event: dict[str, Any]) -> bool:
    return (
        event.get("source_label") in LIVE_ACCEPTED_SOURCE_LABELS
        and event.get("status") in LIVE_ACCEPTED_STATUSES
        and not event.get("fallback_reason")
    )


def _turn_telemetry_summaries(events: list[dict[str, Any]], session_id: str | None) -> list[dict[str, Any]]:
    rows = [
        event for event in events
        if event.get("operation") == "narrative.advance_turn"
        and (not session_id or event.get("session_id") == session_id)
    ]
    return [_event_summary(event) for event in rows]


def _telemetry_failures(
    *,
    events: list[dict[str, Any]],
    session_id: str | None,
    turn_budget: int,
) -> list[dict[str, Any]]:
    failures = _live_operation_failures(events, GOLDEN_PATH_REQUIRED_OPERATIONS)
    turn_events = [
        event for event in events
        if event.get("operation") == "narrative.advance_turn"
        and (not session_id or event.get("session_id") == session_id)
    ]
    if len(turn_events) < turn_budget:
        failures.append(
            _live_failure(
                "telemetry_missing",
                "narrative.advance_turn",
                f"expected at least {turn_budget} live advance-turn telemetry rows",
                observed_count=len(turn_events),
            )
        )
    bad_turn_rows = [
        {
            "event_id": event.get("event_id"),
            "status": event.get("status"),
            "source_label": event.get("source_label"),
            "fallback_reason": event.get("fallback_reason"),
        }
        for event in turn_events[:turn_budget]
        if not _accepted_live_event(event)
    ]
    if bad_turn_rows:
        failures.append(
            _live_failure(
                "provider",
                "narrative.advance_turn",
                "one or more required 12-turn rows were fallback/non-live",
                observed=bad_turn_rows,
            )
        )
    return failures


def _write_markdown_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    quality = payload.get("quality_fun_gate") or {}
    events = payload.get("turn_telemetry") or []
    lines = [
        "# Tiny Stories 12-Turn Live Golden Path",
        "",
        f"- Generated: `{payload.get('generated_at')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Session: `{payload.get('session_id')}`",
        f"- Template: `{payload.get('template_id')}`",
        f"- Turn result: `{payload.get('completed_turns')}/{payload.get('turn_budget')}`",
        f"- Ending reached: `{bool(payload.get('ending'))}`",
        f"- Quality gate: `{quality.get('status')}`",
        "",
        "## Live Turn Telemetry",
        "",
        "| # | source | status | latency_ms | op_latency_ms | input | cached | output | total | fallback |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for index, event in enumerate(events[:GOLDEN_PATH_TURN_BUDGET], start=1):
        lines.append(
            "| {index} | `{source}` | `{status}` | {latency} | {op_latency} | {input_tokens} | {cached} | {output} | {total} | {fallback} |".format(
                index=index,
                source=event.get("source_label"),
                status=event.get("status"),
                latency=event.get("latency_ms"),
                op_latency=event.get("operation_latency_ms"),
                input_tokens=event.get("input_tokens"),
                cached=event.get("cached_input_tokens"),
                output=event.get("output_tokens"),
                total=event.get("total_tokens"),
                fallback=event.get("fallback_reason") or "none",
            )
        )
    lines.extend([
        "",
        "## Quality / Fun Gate",
        "",
        quality.get("rationale") or "",
        "",
    ])
    for name, item in (quality.get("criteria") or {}).items():
        lines.append(f"- `{name}`: `{item.get('status')}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure.get('stage')}`: {failure.get('message')}")
    path.write_text("\n".join(lines).rstrip() + "\n")


def run_live_golden_path(
    *,
    base_url: str,
    output: Path = DEFAULT_OUTPUT,
    report: Path = DEFAULT_REPORT,
    username: str = "portfolio_reviewer",
    seed: str = LIVE_ACCEPTANCE_SEED,
    runtime_db: Path | None = None,
    timeout: float = 180.0,
    turn_budget: int = GOLDEN_PATH_TURN_BUDGET,
) -> dict[str, Any]:
    run_started_at = _utc_now_iso()
    client = LiveHarnessClient(base_url, timeout=timeout)
    failures: list[dict[str, Any]] = []
    api_latencies: dict[str, Any] = {}
    stage_sources: dict[str, Any] = {}
    turn_summaries: list[dict[str, Any]] = []
    template_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    final_story: dict[str, Any] = {}
    ending_payload: dict[str, Any] | None = None
    session_events: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []

    try:
        health, api_latencies["health_ms"] = client.request_json("GET", "/health", timeout=30)
        failures.extend(_health_failures(health))

        login, api_latencies["login_ms"] = client.request_json(
            "POST",
            "/auth/login",
            payload={"username": username},
            timeout=30,
        )
        user = login.get("user") if isinstance(login.get("user"), dict) else {}
        user_id = str(user.get("user_id") or "")
        if not user_id:
            failures.append(_live_failure("environment", "auth", "login did not return a user id"))

        initial_guide_seed = seed.replace(
            "The player is the publicist",
            "The player is a backup dancer",
        )
        guide, api_latencies["story_guide_ms"] = client.request_json(
            "POST",
            "/narrative/story-guide/turns",
            payload={"message": initial_guide_seed, "language": "en"},
            timeout=timeout,
        )
        corrected_guide, api_latencies["story_guide_correction_ms"] = client.request_json(
            "POST",
            "/narrative/story-guide/turns",
            payload={
                "message": "Correction: I am the publicist, not the backup dancer.",
                "language": "en",
                "current_seed": initial_guide_seed,
                "previous_assistant_reply": guide.get("reply"),
                "state": guide.get("state"),
            },
            timeout=timeout,
        )
        guide_context = ((corrected_guide.get("state") or {}).get("context") or {})
        stage_sources["story_guide"] = {
            "initial_source": guide.get("source"),
            "correction_source": corrected_guide.get("source"),
            "status": corrected_guide.get("status"),
            "canShapeBrief": corrected_guide.get("canShapeBrief"),
            "reply_excerpt": str(corrected_guide.get("reply") or "")[:180],
            "player_role": guide_context.get("player_role"),
            "active_cast": guide_context.get("cast_or_factions"),
            "superseded_count": len(guide_context.get("rejected_or_changed_facts") or []),
        }
        if (
            guide.get("source") not in LIVE_ACCEPTED_SOURCE_LABELS
            or corrected_guide.get("source") not in LIVE_ACCEPTED_SOURCE_LABELS
        ):
            failures.append(
                _live_failure(
                    "provider",
                    "create.story_butler_turn",
                    "One or more Story Butler guide responses were not live-backed",
                    initial_source=guide.get("source"),
                    correction_source=corrected_guide.get("source"),
                )
            )
        if "publicist" not in str(guide_context.get("player_role") or "").lower():
            failures.append(
                _live_failure(
                    "story_guide_intent",
                    "create.story_butler_turn",
                    "Correction did not replace the initial player role",
                    observed_role=guide_context.get("player_role"),
                )
            )
        if not any(
            "superseded player_role" in str(item).lower()
            for item in guide_context.get("rejected_or_changed_facts") or []
        ):
            failures.append(
                _live_failure(
                    "story_guide_intent",
                    "create.story_butler_turn",
                    "Correction did not preserve superseded role evidence",
                )
            )
        active_cast = {
            str(item).strip().casefold()
            for item in guide_context.get("cast_or_factions") or []
        }
        if {"backup dancer", "publicist"}.intersection(active_cast):
            failures.append(
                _live_failure(
                    "story_guide_intent",
                    "create.story_butler_turn",
                    "Player-role identities leaked into the active NPC cast after correction",
                    observed_cast=sorted(active_cast),
                )
            )
        active_truth = " ".join(
            [
                str(guide_context.get("scene_summary") or ""),
                str(guide_context.get("pressure") or ""),
                *[str(item) for item in guide_context.get("constraints") or []],
                *[str(item) for item in guide_context.get("confirmed_facts") or []],
            ]
        ).casefold()
        if "backup dancer" in active_truth:
            failures.append(
                _live_failure(
                    "story_guide_intent",
                    "create.story_butler_turn",
                    "Superseded player role remained in active compressed story facts",
                )
            )

        brief_guide_context = {
            key: guide_context.get(key)
            for key in (
                "scene_summary",
                "player_role",
                "cast_or_factions",
                "pressure",
                "constraints",
                "tone",
                "confirmed_facts",
            )
        }

        brief, api_latencies["story_brief_ms"] = client.request_json(
            "POST",
            "/narrative/story-briefs",
            payload={
                "seed": seed,
                "language": "en",
                "desired_tension_profile": "high_drama",
                "guide_context": brief_guide_context,
            },
            timeout=timeout,
        )
        stage_sources["story_brief"] = {
            "source": brief.get("source"),
            "runtime_source": brief.get("runtime_source"),
            "can_generate": brief.get("can_generate"),
        }
        if brief.get("runtime_source") not in LIVE_ACCEPTED_SOURCE_LABELS:
            failures.append(
                _live_failure(
                    "provider",
                    "narrative.story_brief",
                    "Story Brief runtime source was not an accepted live source",
                    observed_source=brief.get("runtime_source"),
                )
            )
        if brief.get("can_generate") is not True:
            failures.append(_live_failure("brief_contract", "narrative.story_brief", "Story Brief was not generatable"))

        template_response, api_latencies["template_opening_ms"] = client.request_json(
            "POST",
            "/narrative/templates",
            payload={
                "seed": seed,
                "visibility": "private",
                "turn_budget": turn_budget,
                "difficulty": "story",
                "language": "en",
                "story_brief": brief.get("brief"),
                "story_guide_context": guide_context,
            },
            timeout=timeout,
        )
        template = template_response.get("template") or {}
        session = template_response.get("session") or {}
        template_id = str(template.get("template_id") or "")
        session_id = str(session.get("session_id") or "")
        stage_sources["opening"] = {
            "template_id": template_id,
            "session_id": session_id,
            "opening_recovery": template_response.get("opening_recovery"),
            "consistency_status": ((template_response.get("story_brief_consistency") or {}).get("status")),
        }
        if not template_id or not session_id:
            failures.append(_live_failure("schema", "narrative.templates", "template/session id missing"))

        story, api_latencies["initial_story_ms"] = client.request_json(
            "GET",
            f"/narrative/sessions/{session_id}/story",
            query={"agent_trace": True},
            timeout=timeout,
        )

        for turn_number in range(1, turn_budget + 1):
            before_narrator = _latest_narrator(story)
            before_options = _option_labels(before_narrator)
            if not before_options:
                failures.append(
                    _live_failure(
                        "trajectory_judge",
                        f"turn_{turn_number}",
                        "no playable options before turn",
                    )
                )
                break
            chosen_index = _choose_option_index(story, turn_number)
            chosen_label = before_options[chosen_index] if chosen_index < len(before_options) else before_options[0]
            turn, elapsed_ms = client.request_json(
                "POST",
                f"/narrative/sessions/{session_id}/story/turns",
                payload={"chosen_option_index": chosen_index},
                query={"agent_trace": True},
                timeout=timeout,
            )
            story, story_elapsed_ms = client.request_json(
                "GET",
                f"/narrative/sessions/{session_id}/story",
                query={"agent_trace": True},
                timeout=timeout,
            )
            after_narrator = _latest_narrator(story)
            next_options = _option_labels(after_narrator)
            if turn.get("ending"):
                ending_payload = turn.get("ending") if isinstance(turn.get("ending"), dict) else None
            turn_summaries.append({
                "turn_number": turn_number,
                "api_latency_ms": elapsed_ms,
                "story_refresh_latency_ms": story_elapsed_ms,
                "chosen_option_index": chosen_index,
                "chosen_option_label": chosen_label,
                "narrator_ord": (turn.get("narrator_message") or {}).get("ord"),
                "is_complete": bool(turn.get("is_complete")),
                "ending_present": isinstance(turn.get("ending"), dict),
                "next_option_count": len(next_options),
                "step_judge_status": next(
                    (
                        ((event.get("payload") or {}).get("status"))
                        for event in turn.get("agent_events") or []
                        if isinstance(event, dict) and event.get("event_type") == "step_judge"
                    ),
                    None,
                ),
                "contract_judge_status": next(
                    (
                        ((event.get("payload") or {}).get("status"))
                        for event in turn.get("agent_events") or []
                        if isinstance(event, dict) and event.get("event_type") == "contract_judge"
                    ),
                    None,
                ),
            })
            if turn_number < turn_budget and turn.get("is_complete"):
                failures.append(
                    _live_failure(
                        "trajectory_judge",
                        f"turn_{turn_number}",
                        "session completed before the 12-turn golden path budget",
                    )
                )
                break
            if turn_number < turn_budget and len(next_options) < 2:
                failures.append(
                    _live_failure(
                        "trajectory_judge",
                        f"turn_{turn_number}",
                        "non-final turn did not expose enough next choices",
                        next_option_count=len(next_options),
                    )
                )
            final_story = story

        completed_turns = len(turn_summaries)
        if completed_turns != turn_budget:
            failures.append(
                _live_failure(
                    "trajectory_judge",
                    "turn_count",
                    f"expected {turn_budget} submitted turns",
                    completed_turns=completed_turns,
                )
            )
        if not turn_summaries or not turn_summaries[-1].get("is_complete"):
            failures.append(_live_failure("trajectory_judge", "ending", "12th turn did not complete the session"))

        if ending_payload is None and session_id:
            ending, api_latencies["ending_ms"] = client.request_json(
                "GET",
                f"/narrative/sessions/{session_id}/ending",
                timeout=timeout,
            )
            ending_payload = ending if ending and ending.get("label") else None
        if ending_payload is None:
            failures.append(_live_failure("trajectory_judge", "ending", "ending payload was not available"))

        evaluation_bundle, api_latencies["evaluation_bundle_ms"] = client.request_json(
            "GET",
            f"/narrative/sessions/{session_id}/evaluation-bundle",
            timeout=timeout,
        )
        evaluation_report, api_latencies["evaluation_report_ms"] = client.request_json(
            "POST",
            "/research/rpg-evaluations",
            payload=evaluation_bundle,
            timeout=timeout,
        )
        latest_memory = ((evaluation_bundle.get("turns") or [{}])[-1].get("memory") or {})
        stage_sources["portable_evaluation"] = {
            "bundle_schema": evaluation_bundle.get("schema_version"),
            "report_schema": evaluation_report.get("schema_version"),
            "status": evaluation_report.get("status"),
            "score": evaluation_report.get("score"),
            "progress_basis": ((evaluation_bundle.get("turns") or [{}])[-1].get("progress_basis")),
            "active_fact_count": len(latest_memory.get("active_facts") or []),
            "superseded_fact_count": len(latest_memory.get("superseded_facts") or []),
        }
        if evaluation_bundle.get("schema_version") != "rpg_evaluation_bundle.v1":
            failures.append(_live_failure("schema", "research.rpg_evaluation", "portable bundle schema missing"))
        if evaluation_report.get("schema_version") != "rpg_evaluation_report.v1":
            failures.append(_live_failure("schema", "research.rpg_evaluation", "portable report schema missing"))
        if not any(
            "backup dancer" in str(fact.get("value") or "").lower()
            for fact in latest_memory.get("superseded_facts") or []
            if isinstance(fact, dict)
        ):
            failures.append(
                _live_failure(
                    "artifact",
                    "research.rpg_evaluation",
                    "Create correction was not retained in the 12-turn evaluation memory",
                )
            )

        session_event_response, api_latencies["llm_events_ms"] = client.request_json(
            "GET",
            f"/narrative/sessions/{session_id}/llm-events",
            timeout=timeout,
        )
        session_events = [
            event for event in session_event_response.get("items") or []
            if isinstance(event, dict)
        ]
        failures.extend(_session_event_failures(session_events))

        if runtime_db is not None:
            all_events = _load_live_events_from_runtime_db(
                runtime_db,
                user_id=user_id or "",
                started_at=run_started_at,
            )
        if not all_events:
            all_events = session_events
            missing_user_events = sorted({"create.story_butler_turn", "narrative.story_brief"}.difference(_events_by_operation(all_events)))
            if missing_user_events:
                failures.append(
                    _live_failure(
                        "telemetry_missing",
                        "runtime_db",
                        "runtime DB events are required to validate pre-session Create/Brief telemetry",
                        missing_operations=missing_user_events,
                        runtime_db=str(runtime_db) if runtime_db is not None else None,
                    )
                )
        failures.extend(
            _telemetry_failures(
                events=all_events,
                session_id=session_id,
                turn_budget=turn_budget,
            )
        )
    except LiveHarnessHTTPError as exc:
        failures.append(
            _live_failure(
                "provider" if exc.status is None or exc.status >= 500 else "schema",
                exc.path,
                str(exc),
                status=exc.status,
                body=exc.body,
            )
        )

    final_agent_events = [
        event for event in final_story.get("agent_events") or []
        if isinstance(event, dict)
    ]
    quality = _quality_summary(
        turn_summaries=turn_summaries,
        agent_events=final_agent_events,
        story=final_story,
        ending=ending_payload,
        seed=seed,
    )
    if quality["status"] == "fail":
        failures.append(
            _live_failure(
                "trajectory_judge",
                "quality_fun_gate",
                "deterministic quality gate failed",
            )
        )

    operation_events = {
        operation: [_event_summary(event) for event in events]
        for operation, events in sorted(_events_by_operation(all_events).items())
        if operation in GOLDEN_PATH_REQUIRED_OPERATIONS or operation in {"narrative.ending", "narrative.highlights", "narrative.branches"}
    }
    payload = {
        "schema_version": "tiny_stories_live_golden_path.v1",
        "mode": "live_golden_path_12_turn",
        "generated_at": _utc_now_iso(),
        "run_started_at": run_started_at,
        "status": "fail" if failures else "pass",
        "base_url": base_url,
        "username": username,
        "seed_excerpt": seed[:240],
        "turn_budget": turn_budget,
        "completed_turns": len(turn_summaries),
        "template_id": template_id,
        "session_id": session_id,
        "health_required": sorted(REQUIRED_HEALTH_CONFIG),
        "required_operations": sorted(GOLDEN_PATH_REQUIRED_OPERATIONS),
        "api_latencies_ms": api_latencies,
        "stage_sources": stage_sources,
        "turns": turn_summaries,
        "turn_telemetry": _turn_telemetry_summaries(all_events, session_id),
        "operation_events": operation_events,
        "session_llm_events": [_event_summary(event) for event in session_events],
        "quality_fun_gate": quality,
        "ending": ending_payload,
        "reviewer_evidence": {
            "agent_event_count": len(final_agent_events),
            "step_judge_count": len(_agent_event_payloads(final_agent_events, "step_judge")),
            "contract_judge_count": len(_agent_event_payloads(final_agent_events, "contract_judge")),
            "session_llm_event_count": len(session_events),
        },
        "runtime_db": str(runtime_db) if runtime_db is not None else None,
        "failures": failures,
        "notes": [
            "This is strict live acceptance evidence for one canonical 12-turn Tiny Stories run.",
            "Required Story Butler, Story Brief, opening, and Play turn operations must be live/live_repaired with no fallback_reason.",
            "The quality/fun gate is deterministic product evidence, not a calibrated research metric.",
        ],
    }
    _write_json(output, payload)
    _write_markdown_report(report, payload)
    return payload


def resume_live_golden_path_evidence(
    *,
    base_url: str,
    artifact: Path,
    report: Path,
    runtime_db: Path,
    username: str = "portfolio_reviewer",
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Finish deterministic/reviewer evidence for an already completed live run.

    This recovery path never submits a Play turn or invokes an LLM. It is for
    evaluator/telemetry failures that happen after the live trajectory has
    already reached its persisted ending.
    """

    payload = json.loads(artifact.read_text())
    session_id = str(payload.get("session_id") or "")
    if not session_id or int(payload.get("completed_turns") or 0) != int(payload.get("turn_budget") or 0):
        raise ValueError("Resume requires an artifact with a complete persisted trajectory.")

    client = LiveHarnessClient(base_url, timeout=timeout)
    failures = [
        failure
        for failure in payload.get("failures") or []
        if str(failure.get("stage") or "") != "/research/rpg-evaluations"
    ]
    api_latencies = dict(payload.get("api_latencies_ms") or {})
    stage_sources = dict(payload.get("stage_sources") or {})

    health, api_latencies["resume_health_ms"] = client.request_json("GET", "/health", timeout=30)
    failures.extend(_health_failures(health))
    login, api_latencies["resume_login_ms"] = client.request_json(
        "POST", "/auth/login", payload={"username": username}, timeout=30,
    )
    user = login.get("user") if isinstance(login.get("user"), dict) else {}
    user_id = str(user.get("user_id") or "")
    story, api_latencies["resume_story_ms"] = client.request_json(
        "GET", f"/narrative/sessions/{session_id}/story", query={"agent_trace": True}, timeout=timeout,
    )
    ending, api_latencies["resume_ending_ms"] = client.request_json(
        "GET", f"/narrative/sessions/{session_id}/ending", timeout=timeout,
    )
    bundle, api_latencies["resume_evaluation_bundle_ms"] = client.request_json(
        "GET", f"/narrative/sessions/{session_id}/evaluation-bundle", timeout=timeout,
    )
    evaluation, api_latencies["resume_evaluation_report_ms"] = client.request_json(
        "POST", "/research/rpg-evaluations", payload=bundle, timeout=timeout,
    )
    event_response, api_latencies["resume_llm_events_ms"] = client.request_json(
        "GET", f"/narrative/sessions/{session_id}/llm-events", timeout=timeout,
    )
    session_events = [item for item in event_response.get("items") or [] if isinstance(item, dict)]
    all_events = _load_live_events_from_runtime_db(
        runtime_db,
        user_id=user_id,
        started_at=str(payload.get("run_started_at") or payload.get("generated_at") or ""),
    )
    failures.extend(_session_event_failures(session_events))
    failures.extend(
        _telemetry_failures(
            events=all_events,
            session_id=session_id,
            turn_budget=int(payload.get("turn_budget") or GOLDEN_PATH_TURN_BUDGET),
        )
    )

    latest_memory = ((bundle.get("turns") or [{}])[-1].get("memory") or {})
    stage_sources["portable_evaluation"] = {
        "bundle_schema": bundle.get("schema_version"),
        "report_schema": evaluation.get("schema_version"),
        "status": evaluation.get("status"),
        "score": evaluation.get("score"),
        "progress_basis": ((bundle.get("turns") or [{}])[-1].get("progress_basis")),
        "active_fact_count": len(latest_memory.get("active_facts") or []),
        "superseded_fact_count": len(latest_memory.get("superseded_facts") or []),
    }
    if bundle.get("schema_version") != "rpg_evaluation_bundle.v1" or evaluation.get("schema_version") != "rpg_evaluation_report.v1":
        failures.append(_live_failure("schema", "research.rpg_evaluation", "portable evaluation schema missing"))
    if not any(
        "backup dancer" in str(fact.get("value") or "").lower()
        for fact in latest_memory.get("superseded_facts") or []
        if isinstance(fact, dict)
    ):
        failures.append(_live_failure("artifact", "research.rpg_evaluation", "Create correction missing from evaluation memory"))

    agent_events = [event for event in story.get("agent_events") or [] if isinstance(event, dict)]
    quality = _quality_summary(
        turn_summaries=list(payload.get("turns") or []),
        agent_events=agent_events,
        story=story,
        ending=ending,
        seed=str(payload.get("seed_excerpt") or ""),
    )
    if quality["status"] == "fail":
        failures.append(_live_failure("trajectory_judge", "quality_fun_gate", "deterministic quality gate failed"))

    payload.update({
        "status": "fail" if failures else "pass",
        "base_url": base_url,
        "api_latencies_ms": api_latencies,
        "stage_sources": stage_sources,
        "turn_telemetry": _turn_telemetry_summaries(all_events, session_id),
        "operation_events": {
            operation: [_event_summary(event) for event in events]
            for operation, events in sorted(_events_by_operation(all_events).items())
            if operation in GOLDEN_PATH_REQUIRED_OPERATIONS
            or operation in {"narrative.ending", "narrative.highlights", "narrative.branches"}
        },
        "session_llm_events": [_event_summary(event) for event in session_events],
        "quality_fun_gate": quality,
        "ending": ending,
        "reviewer_evidence": {
            "agent_event_count": len(agent_events),
            "step_judge_count": len(_agent_event_payloads(agent_events, "step_judge")),
            "contract_judge_count": len(_agent_event_payloads(agent_events, "contract_judge")),
            "session_llm_event_count": len(session_events),
        },
        "runtime_db": str(runtime_db),
        "failures": failures,
    })
    payload.setdefault("notes", []).append(
        "Post-run evaluator and telemetry evidence was resumed without additional LLM or Play calls."
    )
    _write_json(artifact, payload)
    _write_markdown_report(report, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Tiny Stories strict 12-turn live golden path gate.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8350", help="Backend base URL.")
    parser.add_argument("--username", default="portfolio_reviewer", help="Reviewer username.")
    parser.add_argument("--seed", default=LIVE_ACCEPTANCE_SEED, help="Canonical story seed.")
    parser.add_argument("--runtime-db", default=None, help="Runtime SQLite DB path. Defaults to APP_RUNTIME_STATE_DB_PATH.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Per-request timeout in seconds.")
    parser.add_argument("--turn-budget", type=int, default=GOLDEN_PATH_TURN_BUDGET, help="Expected live turn count.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Summary JSON path.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Markdown report path.")
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Resume evaluator/telemetry evidence from --output without submitting more live turns.",
    )
    args = parser.parse_args()

    runtime_db = Path(args.runtime_db) if args.runtime_db else None
    if runtime_db is None:
        import os

        runtime_db_env = os.environ.get("APP_RUNTIME_STATE_DB_PATH")
        runtime_db = Path(runtime_db_env) if runtime_db_env else None
    if args.resume_existing:
        if runtime_db is None:
            parser.error("--resume-existing requires --runtime-db or APP_RUNTIME_STATE_DB_PATH")
        payload = resume_live_golden_path_evidence(
            base_url=args.base_url,
            artifact=Path(args.output),
            report=Path(args.report),
            runtime_db=runtime_db,
            username=args.username,
            timeout=args.timeout,
        )
    else:
        payload = run_live_golden_path(
            base_url=args.base_url,
            output=Path(args.output),
            report=Path(args.report),
            username=args.username,
            seed=args.seed,
            runtime_db=runtime_db,
            timeout=args.timeout,
            turn_budget=args.turn_budget,
        )
    print(json.dumps({
        "status": payload["status"],
        "mode": payload["mode"],
        "template_id": payload.get("template_id"),
        "session_id": payload.get("session_id"),
        "completed_turns": payload.get("completed_turns"),
        "quality_status": (payload.get("quality_fun_gate") or {}).get("status"),
        "failure_count": len(payload.get("failures") or []),
        "output": str(args.output),
        "report": str(args.report),
    }, ensure_ascii=False))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
