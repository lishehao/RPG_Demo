from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from random import Random
from typing import Any
from urllib.parse import urlparse

import requests

from rpg_backend.author.metrics import estimate_token_cost, summarize_cache_metrics
from rpg_backend.author.contracts import AuthorCacheMetrics
from rpg_backend.config import Settings, get_settings
from rpg_backend.content_language import resolve_content_prompt_profile
from rpg_backend.helper.agent import (
    HelperProviderRateLimitDecision as _BenchmarkProviderRateLimitDecision,
    get_shared_helper_provider_limiter as get_shared_benchmark_provider_limiter,
)
from rpg_backend.llm_gateway import helper_gateway_config_available
from rpg_backend.play.text_quality import has_language_contamination
from rpg_backend.responses_transport import (
    JSONTransport,
    ResponsesJSONResponse,
    TransportStyle,
    build_json_transport,
    build_openai_client,
    strip_model_meta_wrapper_text,
)
from tools.play_benchmarks.story_seed_factory import GeneratedStorySeed, build_story_seed_batch

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "benchmarks"
HELPER_BENCHMARK_TIMEOUT_FLOOR_SECONDS = 60.0
TURN_AGENT_MAX_OUTPUT_TOKENS = 260
REPORT_AGENT_MAX_OUTPUT_TOKENS = 420
LONGFORM_TURN_AGENT_MAX_OUTPUT_TOKENS = 420
LONGFORM_REPORT_AGENT_MAX_OUTPUT_TOKENS = 800
LONGFORM_TURN_AGENT_STAGE2_MAX_OUTPUT_TOKENS = 520
LONGFORM_REPORT_AGENT_STAGE2_MAX_OUTPUT_TOKENS = 1000
DEFAULT_TRANSCRIPT_WINDOW_ENTRIES = 8
LONGFORM_TRANSCRIPT_WINDOW_ENTRIES = 12
DEFAULT_REQUEST_TIMEOUT_SECONDS = 180
DEFAULT_CONNECT_TIMEOUT_SECONDS = 15
STAGE1_SMOKE_TURN_COUNT = 2
STAGE1_SMOKE_LANGUAGES: tuple[str, ...] = ("zh", "en")
PLAY_ONLY_TRACE_CAUSE_BUCKETS: tuple[str, ...] = (
    "stage1_plan_protocol_mismatch",
    "quality_gate_rejection",
    "repair_instability",
    "language_contamination",
    "other_runtime_issue",
)


@dataclass(frozen=True)
class AgentPersona:
    persona_id: str
    label: str
    turn_style: str
    decision_lens: str
    report_lens: str


@dataclass(frozen=True)
class TurnPlan:
    beat_anchor: str
    beat_goal: str
    move_family: str
    target_npcs: list[str]
    risk_posture: str
    anti_repeat_note: str
    prompt_outline: str
    input_text: str | None = None


PERSONAS: tuple[AgentPersona, ...] = (
    AgentPersona(
        persona_id="assertive_operator",
        label="Assertive Operator",
        turn_style="Push pressure into the open, force public commitments, and prefer decisive moves over caution.",
        decision_lens="Escalate toward visible leverage, confrontation, and rapid closure when the fiction supports it.",
        report_lens="Judge whether the game rewarded aggressive public pressure with coherent consequences.",
    ),
    AgentPersona(
        persona_id="coalition_builder",
        label="Coalition Builder",
        turn_style="Stabilize institutions, reconcile witnesses, and prefer evidence-backed coordination over threat displays.",
        decision_lens="Look for multi-party alignment, procedural legitimacy, and durable settlements before escalation.",
        report_lens="Judge whether the game supported negotiation, evidence work, and coalition maintenance without going flat.",
    ),
    AgentPersona(
        persona_id="evidence_archivist",
        label="Evidence Archivist",
        turn_style="Lock records, testimony, and chain-of-custody before adversaries can reinterpret the scene.",
        decision_lens="Prefer evidence preservation, witness alignment, and audit-ready moves over rhetorical escalation.",
        report_lens="Judge whether the game rewards record control, testimony release timing, and evidence-backed progress.",
    ),
    AgentPersona(
        persona_id="resource_broker",
        label="Resource Broker",
        turn_style="Control bottlenecks, routing, and scarce operational leverage before procedural language turns into private advantage.",
        decision_lens="Look for supply chokepoints, corridor access, and bargaining leverage that can convert chaos into terms.",
        report_lens="Judge whether the game turns logistical leverage and scarcity control into distinct, legible consequences.",
    ),
    AgentPersona(
        persona_id="legitimacy_guardian",
        label="Legitimacy Guardian",
        turn_style="Protect public mandate, oath legitimacy, and visible consent even when speed would make private shortcuts easier.",
        decision_lens="Prefer moves that restore lawful authority, clarify public mandate, and force binding settlement before panic captures the city.",
        report_lens="Judge whether the game meaningfully models public legitimacy, mandate repair, and settlement under civic pressure.",
    ),
)


@dataclass(frozen=True)
class LiveApiPlaytestConfig:
    base_url: str
    output_dir: Path
    label: str | None
    launch_server: bool
    session_ttl_seconds: int
    max_turns: int | None
    seed: int | None
    story_count: int
    phase_id: str | None
    seed_set_id: str | None
    arm: str
    baseline_artifact: Path | None
    managed_server_content_prompt_profile: str | None
    target_duration_minutes: int
    probe_turn_proposal: bool
    agent_transport_style: TransportStyle
    stage1_spark_smoke: bool = False
    play_issue_inspect: bool = False
    inspect_story_id: str | None = None
    inspect_language: str = "zh"
    inspect_prompt_count: int = 10
    use_helper_agent: bool = False
    play_only_campaign: bool = False
    play_only_story_ids: tuple[str, ...] = ()
    target_total_turns: int = 240
    max_sessions_per_cell: int = 6
    use_helper_judge: bool = False
    use_helper_turn_agent: bool = False
    play_only_checkpoint_path: Path | None = None
    resume_from: Path | None = None
    checkpoint_every_sessions: int = 1
    judge_max_workers: int = 8


def parse_args(argv: list[str] | None = None) -> LiveApiPlaytestConfig:
    parser = argparse.ArgumentParser(description="Run live author->publish->play benchmark against the HTTP API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--label")
    parser.add_argument("--launch-server", action="store_true")
    parser.add_argument("--session-ttl-seconds", type=int, default=3600)
    parser.add_argument("--max-turns", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--story-count", type=int, default=3)
    parser.add_argument("--phase-id")
    parser.add_argument("--seed-set-id")
    parser.add_argument("--arm", choices=("baseline", "candidate"), default="candidate")
    parser.add_argument("--baseline-artifact")
    parser.add_argument("--managed-server-content-prompt-profile", choices=("plain", "role_conditioned"))
    parser.add_argument("--target-duration-minutes", type=int, default=25)
    parser.add_argument("--probe-turn-proposal", action="store_true")
    parser.add_argument("--agent-transport-style", choices=("responses", "chat_completions"), default="chat_completions")
    parser.add_argument("--use-helper-agent", action="store_true")
    parser.add_argument("--use-helper-turn-agent", action="store_true")
    parser.add_argument("--use-helper-judge", action="store_true")
    parser.add_argument("--stage1-spark-smoke", action="store_true")
    parser.add_argument("--play-issue-inspect", action="store_true")
    parser.add_argument("--inspect-story-id")
    parser.add_argument("--inspect-language", choices=("en", "zh"), default="zh")
    parser.add_argument("--inspect-prompt-count", type=int, default=10)
    parser.add_argument("--play-only-campaign", action="store_true")
    parser.add_argument("--play-only-story-ids")
    parser.add_argument("--target-total-turns", type=int, default=240)
    parser.add_argument("--max-sessions-per-cell", type=int, default=6)
    parser.add_argument("--play-only-checkpoint-path")
    parser.add_argument("--resume-from")
    parser.add_argument("--checkpoint-every-sessions", type=int, default=1)
    parser.add_argument("--judge-max-workers", type=int, default=8)
    args = parser.parse_args(argv)
    play_only_story_ids = tuple(
        item.strip()
        for item in str(args.play_only_story_ids or "").split(",")
        if item.strip()
    )
    use_helper_turn_agent = bool(args.use_helper_turn_agent or args.use_helper_agent)
    use_helper_judge = bool(args.use_helper_judge or args.use_helper_agent)
    return LiveApiPlaytestConfig(
        base_url=args.base_url.rstrip("/"),
        output_dir=Path(args.output_dir).expanduser().resolve(),
        label=args.label,
        launch_server=bool(args.launch_server),
        session_ttl_seconds=max(int(args.session_ttl_seconds), 60),
        max_turns=max(int(args.max_turns), 1) if args.max_turns is not None else None,
        seed=args.seed,
        story_count=max(int(args.story_count), 1),
        phase_id=args.phase_id,
        seed_set_id=args.seed_set_id,
        arm=args.arm,
        baseline_artifact=Path(args.baseline_artifact).expanduser().resolve() if args.baseline_artifact else None,
        managed_server_content_prompt_profile=args.managed_server_content_prompt_profile,
        target_duration_minutes=min(max(int(args.target_duration_minutes), 10), 25),
        probe_turn_proposal=bool(args.probe_turn_proposal),
        agent_transport_style=str(args.agent_transport_style),  # type: ignore[arg-type]
        stage1_spark_smoke=bool(args.stage1_spark_smoke),
        play_issue_inspect=bool(args.play_issue_inspect),
        inspect_story_id=str(args.inspect_story_id).strip() if args.inspect_story_id else None,
        inspect_language=str(args.inspect_language),
        inspect_prompt_count=max(int(args.inspect_prompt_count), 1),
        use_helper_agent=bool(args.use_helper_agent),
        play_only_campaign=bool(args.play_only_campaign),
        play_only_story_ids=play_only_story_ids,
        target_total_turns=max(int(args.target_total_turns), 1),
        max_sessions_per_cell=max(int(args.max_sessions_per_cell), 1),
        use_helper_judge=use_helper_judge,
        use_helper_turn_agent=use_helper_turn_agent,
        play_only_checkpoint_path=Path(args.play_only_checkpoint_path).expanduser().resolve() if args.play_only_checkpoint_path else None,
        resume_from=Path(args.resume_from).expanduser().resolve() if args.resume_from else None,
        checkpoint_every_sessions=max(int(args.checkpoint_every_sessions), 1),
        judge_max_workers=max(int(args.judge_max_workers), 1),
    )


def _read_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"request failed with status {response.status_code}"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
    return f"request failed with status {response.status_code}"


def _benchmark_driver_budget_context(story_detail: dict[str, Any]) -> dict[str, int]:
    play_overview = dict(story_detail.get("play_overview") or {})
    target_duration_minutes = int(play_overview.get("target_duration_minutes") or 0)
    branch_budget = str(play_overview.get("branch_budget") or "").casefold()
    is_longform = target_duration_minutes >= 22 or branch_budget == "high"
    return {
        "turn_max_output_tokens": LONGFORM_TURN_AGENT_MAX_OUTPUT_TOKENS if is_longform else TURN_AGENT_MAX_OUTPUT_TOKENS,
        "report_max_output_tokens": LONGFORM_REPORT_AGENT_MAX_OUTPUT_TOKENS if is_longform else REPORT_AGENT_MAX_OUTPUT_TOKENS,
        "turn_stage2_max_output_tokens": LONGFORM_TURN_AGENT_STAGE2_MAX_OUTPUT_TOKENS if is_longform else TURN_AGENT_MAX_OUTPUT_TOKENS,
        "report_stage2_max_output_tokens": LONGFORM_REPORT_AGENT_STAGE2_MAX_OUTPUT_TOKENS if is_longform else REPORT_AGENT_MAX_OUTPUT_TOKENS,
        "transcript_window_entries": LONGFORM_TRANSCRIPT_WINDOW_ENTRIES if is_longform else DEFAULT_TRANSCRIPT_WINDOW_ENTRIES,
    }


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> tuple[dict[str, Any], float]:
    started_at = time.perf_counter()
    response = session.request(
        method,
        url,
        timeout=(DEFAULT_CONNECT_TIMEOUT_SECONDS, timeout_seconds),
        **kwargs,
    )
    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    if not response.ok:
        raise RuntimeError(f"{method} {url}: {_read_error_message(response)}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{method} {url}: expected JSON object payload")
    return payload, elapsed_seconds


def _authenticate_session(session: requests.Session, base_url: str, *, label: str) -> dict[str, Any]:
    suffix = secrets.token_hex(6)
    email = f"{label}-{suffix}@bench.local"
    payload = {
        "display_name": label.replace("-", " ").title(),
        "email": email,
        "password": "BenchPass123!",
    }
    response = session.post(
        f"{base_url}/auth/register",
        json=payload,
        timeout=(DEFAULT_CONNECT_TIMEOUT_SECONDS, DEFAULT_REQUEST_TIMEOUT_SECONDS),
    )
    if not response.ok:
        raise RuntimeError(f"POST {base_url}/auth/register: {_read_error_message(response)}")
    body = response.json()
    if not isinstance(body, dict) or not body.get("authenticated"):
        raise RuntimeError("benchmark auth registration did not return an authenticated session")
    return body


def _parse_sse_event(block: str) -> dict[str, Any] | None:
    event_id = 0
    event_name = "message"
    data_lines: list[str] = []
    for line in block.splitlines():
        if not line or line.startswith(":"):
            continue
        if line.startswith("id:"):
            event_id = int(line[3:].strip() or 0)
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip() or "message"
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
    if not data_lines:
        return None
    return {
        "id": event_id,
        "event": event_name,
        "data": json.loads("\n".join(data_lines)),
    }


def _stream_author_job_to_terminal(session: requests.Session, base_url: str, job_id: str) -> dict[str, Any]:
    url = f"{base_url}/author/jobs/{job_id}/events"
    started_at = time.perf_counter()
    events: list[dict[str, Any]] = []
    response = session.get(
        url,
        headers={"Accept": "text/event-stream"},
        stream=True,
        timeout=(DEFAULT_CONNECT_TIMEOUT_SECONDS, 600),
    )
    if not response.ok:
        raise RuntimeError(f"GET {url}: {_read_error_message(response)}")
    try:
        buffer: list[str] = []
        for raw_line in response.iter_lines(decode_unicode=True):
            line = raw_line or ""
            if line == "":
                event = _parse_sse_event("\n".join(buffer))
                buffer = []
                if event is None:
                    continue
                events.append(event)
                if event["event"] in {"job_completed", "job_failed"}:
                    break
                continue
            buffer.append(line)
        if buffer:
            trailing = _parse_sse_event("\n".join(buffer))
            if trailing is not None:
                events.append(trailing)
    finally:
        response.close()
    return {
        "events": events,
        "stream_elapsed_seconds": round(time.perf_counter() - started_at, 3),
        "terminal_event": events[-1] if events else None,
    }


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(ceil(q * len(ordered)) - 1, 0)
    return ordered[min(index, len(ordered) - 1)]


def _session_feedback_metrics(turns: list[dict[str, Any]]) -> dict[str, int]:
    distinct_axes = {
        axis_id
        for turn in turns
        for axis_id, value in dict((turn.get("feedback") or {}).get("last_turn_axis_deltas") or {}).items()
        if int(value) != 0
    }
    distinct_stances = {
        stance_id
        for turn in turns
        for stance_id, value in dict((turn.get("feedback") or {}).get("last_turn_stance_deltas") or {}).items()
        if int(value) != 0
    }
    distinct_consequences = {
        consequence
        for turn in turns
        for consequence in list((turn.get("feedback") or {}).get("last_turn_consequences") or [])
        if isinstance(consequence, str) and consequence.strip()
    }
    nonzero_feedback_turns = sum(
        1
        for turn in turns
        if any(int(value) != 0 for value in dict((turn.get("feedback") or {}).get("last_turn_axis_deltas") or {}).values())
        or any(int(value) != 0 for value in dict((turn.get("feedback") or {}).get("last_turn_stance_deltas") or {}).values())
    )
    return {
        "distinct_axis_count": len(distinct_axes),
        "distinct_stance_count": len(distinct_stances),
        "distinct_consequence_count": len(distinct_consequences),
        "nonzero_feedback_turns": nonzero_feedback_turns,
    }


def _late_half_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not turns:
        return []
    return turns[len(turns) // 2 :]


def _normalize_agent_report(
    *,
    report: dict[str, Any],
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = dict(report)
    ratings = dict(normalized.get("ratings") or {})
    ratings.setdefault("narration_coherence", 3)
    ratings.setdefault("suggested_action_relevance", 3)
    ratings.setdefault("state_feedback_credibility", 3)
    ratings.setdefault("ending_satisfaction", 3)
    ratings.setdefault("overall_player_feel", 3)
    ratings.setdefault("content_richness", 3)
    ratings.setdefault("state_feedback_distinctness", ratings.get("state_feedback_credibility", 3))
    ratings.setdefault("protagonist_identity_clarity", 3)
    normalized["ratings"] = ratings
    flags = [
        flag
        for flag in list(normalized.get("flags") or [])
        if flag
        in {
            "flat_state_feedback",
            "late_game_flatness",
            "suggestion_template_drift",
            "ending_feels_unearned",
            "narration_does_not_pay_off_state",
            "player_identity_confusion",
            "templated_opening",
        }
    ]
    metrics = _session_feedback_metrics(turns)
    distinctness = int(ratings.get("state_feedback_distinctness") or 0)
    credibility = int(ratings.get("state_feedback_credibility") or 0)
    flat_supported = (
        metrics["distinct_axis_count"] <= 1
        and metrics["distinct_stance_count"] <= 1
        and metrics["distinct_consequence_count"] <= 2
        and metrics["nonzero_feedback_turns"] <= 2
        and distinctness <= 3
        and credibility <= 3
    )
    if "flat_state_feedback" in flags and not flat_supported:
        flags = [flag for flag in flags if flag != "flat_state_feedback"]
    if "flat_state_feedback" not in flags and flat_supported:
        flags.append("flat_state_feedback")
    late_half_metrics = _session_feedback_metrics(_late_half_turns(turns))
    late_game_flatness_supported = (
        len(turns) >= 4
        and late_half_metrics["distinct_axis_count"] <= 1
        and late_half_metrics["distinct_stance_count"] <= 1
        and late_half_metrics["distinct_consequence_count"] <= 1
        and late_half_metrics["nonzero_feedback_turns"] <= 2
        and distinctness <= 3
    )
    if "late_game_flatness" in flags and not late_game_flatness_supported:
        flags = [flag for flag in flags if flag != "late_game_flatness"]
    if "late_game_flatness" not in flags and late_game_flatness_supported:
        flags.append("late_game_flatness")
    normalized["flags"] = flags
    normalized["best_moment"] = str(normalized.get("best_moment") or "No clear peak moment reported.")
    normalized["verdict"] = str(normalized.get("verdict") or "Playable but needs closer review.")
    return normalized


class _PlaytestAgentError(RuntimeError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _extract_turn_input_from_raw_text(raw_text: str | None) -> str:
    cleaned = strip_model_meta_wrapper_text(str(raw_text or ""))
    if not cleaned:
        return ""
    json_key_match = re.search(r'"?input_text"?\s*[:=]\s*"?(.*?)"?$', cleaned, flags=re.IGNORECASE | re.DOTALL)
    if json_key_match:
        return strip_model_meta_wrapper_text(json_key_match.group(1))
    first_line = cleaned.splitlines()[0].strip()
    return first_line.strip('"').strip()


def _proposal_text_is_clean(text: str | None) -> bool:
    lowered = str(text or "").casefold()
    return not any(
        marker in lowered
        for marker in (
            'input_text":',
            '{"input_text"',
            'input_text\\"',
            "json",
            "```",
        )
    )


_BENCHMARK_META_STOPWORDS = {
    "",
    "{",
    "}",
    "json",
    "input_text",
    "input text",
    "requested output",
    "here is the json requested",
    "here is the requested output",
    "here is the json request",
}

_MOVE_FAMILIES: tuple[str, ...] = (
    "public_pressure",
    "coalition_repair",
    "evidence_lock",
    "resource_control",
    "institutional_audit",
    "protect_legitimacy",
    "force_settlement",
)


def _tokenize_benchmark_text(text: str) -> list[str]:
    return re.findall(r"[a-z]{3,}", text.casefold())


def _split_candidate_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def _is_structured_report_fragment(text: str) -> bool:
    lowered = text.casefold().strip().strip('"').strip().strip("{").strip("}").strip()
    return any(
        token in lowered
        for token in (
            "ending:",
            "ending_id",
            "strongest issue",
            "strongest_issue",
            "best moment",
            "best_moment",
            "verdict",
            "narration_coherence",
            "narration coherence",
            "suggested_action_relevance",
            "suggested action relevance",
            "state_feedback_credibility",
            "state feedback credibility",
            "ending_satisfaction",
            "ending satisfaction",
            "overall_player_feel",
            "overall player feel",
            "content_richness",
            "content richness",
            "state_feedback_distinctness",
            "state feedback distinctness",
            "protagonist_identity_clarity",
            "protagonist identity clarity",
        )
    )


def _structured_turn_candidates(raw_text: str) -> list[str]:
    patterns = (
        r'"input_text"\s*:\s*"([^"]+)"',
        r"\binput_text\b\s*[:=]\s*(.+)",
        r"\binput text\b\s*[:=]\s*(.+)",
        r"\bplayer move\b\s*[:=]\s*(.+)",
        r"\bplayer action\b\s*[:=]\s*(.+)",
        r"\bturn\b\s*[:=]\s*(.+)",
        r"^\s*-\s*(?:input_text|input text|player move|player action)\s*[:=]\s*(.+)$",
    )
    candidates: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, raw_text, flags=re.IGNORECASE | re.MULTILINE):
            candidate = strip_model_meta_wrapper_text(match.group(1))
            if candidate:
                candidates.append(candidate)
    return candidates


def _strip_turn_field_prefix(text: str) -> str:
    return re.sub(
        r'^(?:\{?\s*)?(?:"?(?:input_text|input text|player move|player action|turn)"?\s*[:=]\s*)+',
        "",
        text.strip(),
        flags=re.IGNORECASE,
    ).strip()


def _extract_turn_input_from_jsonish_text(text: str) -> str:
    candidate = text.strip()
    for _ in range(2):
        if not candidate:
            break
        decoded = None
        decode_variants = [candidate]
        if '\\"' in candidate:
            decode_variants.append(candidate.replace('\\"', '"'))
        for variant in decode_variants:
            try:
                decoded = json.loads(variant)
                break
            except Exception:
                continue
        if decoded is None:
            break
        if isinstance(decoded, dict):
            for key in ("input_text", "input text", "player move", "player action", "turn"):
                value = decoded.get(key)
                if isinstance(value, str) and value.strip():
                    candidate = value.strip()
                    break
            else:
                break
            continue
        if isinstance(decoded, str):
            candidate = decoded.strip()
            continue
        break
    return candidate


def _normalize_turn_candidate_text(text: str | None) -> str:
    candidate = strip_model_meta_wrapper_text(str(text or "")).strip()
    if not candidate:
        return ""
    candidate = _extract_turn_input_from_jsonish_text(candidate)
    candidate = strip_model_meta_wrapper_text(candidate).strip()
    candidate = _strip_turn_field_prefix(candidate)
    candidate = candidate.strip().strip('"').strip("'").strip()
    candidate = _strip_turn_field_prefix(candidate)
    candidate = candidate.strip().strip('"').strip("'").strip()
    candidate = candidate.lstrip(":").strip().strip("}").strip()
    candidate = candidate.lstrip(":").strip()
    return candidate


def _natural_turn_candidates(raw_text: str) -> list[str]:
    candidates: list[str] = []
    for sentence in _split_candidate_sentences(strip_model_meta_wrapper_text(raw_text)):
        if re.search(r"\bI\b", sentence):
            candidates.append(sentence)
    return candidates


def _turn_candidate_rejection_reason(
    candidate: str,
    *,
    snapshot: dict[str, Any],
    forbidden_verbatim: list[str],
    rejected_candidates: set[str],
) -> str | None:
    normalized = _normalize_turn_candidate_text(candidate)
    lowered = normalized.casefold()
    if lowered in _BENCHMARK_META_STOPWORDS:
        return "meta_token"
    if lowered in rejected_candidates:
        return "repeated_rejection"
    if normalized.casefold() in {item.casefold() for item in forbidden_verbatim if item}:
        return "verbatim_suggestion"
    if _word_count(normalized) < 8 and len(normalized) < 40:
        return "too_short"
    if not re.search(r"\bI\b", normalized):
        return "missing_first_person"
    beat_title = str(snapshot.get("beat_title") or "").casefold().strip()
    if beat_title and beat_title in lowered and _word_count(normalized) <= _word_count(beat_title) + 5:
        return "beat_title_echo"
    suggestion_labels = {
        str(item.get("label") or "").casefold().strip()
        for item in list(snapshot.get("suggested_actions") or [])
        if str(item.get("label") or "").strip()
    }
    if lowered in suggestion_labels or any(lowered == f"i {label}" for label in suggestion_labels):
        return "label_rewrite_without_action"
    if any(
        marker in lowered
        for marker in (
            "here is",
            "the json is",
            "requested output",
            "input_text",
            '{"input_text"',
            'input_text":',
            'input_text\\"',
            "json request",
        )
    ):
        return "meta_wrapper"
    return None


def _turn_candidate_score(candidate: str, *, snapshot: dict[str, Any]) -> tuple[int, int, int]:
    candidate_tokens = set(_tokenize_benchmark_text(candidate))
    beat = " ".join(
        [
            str(snapshot.get("beat_title") or ""),
            str(((snapshot.get("progress") or {}).get("current_beat_goal") or "")),
            " ".join(str(item.get("prompt") or "") for item in list(snapshot.get("suggested_actions") or [])),
        ]
    )
    beat_tokens = set(_tokenize_benchmark_text(beat))
    overlap = len(candidate_tokens & beat_tokens)
    return (
        overlap,
        _word_count(candidate),
        -sum(1 for marker in ("json", "requested", "output") if marker in candidate.casefold()),
    )


def _extract_turn_input_candidates(raw_text: str | None) -> list[str]:
    cleaned = str(raw_text or "")
    if not cleaned.strip():
        return []
    candidates = [
        *_structured_turn_candidates(cleaned),
        *_natural_turn_candidates(cleaned),
    ]
    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_turn_candidate_text(candidate)
        lowered = normalized.casefold()
        if not normalized or lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(normalized)
    return ordered


def _suggested_prompt_salvage_candidates(snapshot: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for item in list(snapshot.get("suggested_actions") or []):
        prompt = strip_model_meta_wrapper_text(str(item.get("prompt") or "")).strip()
        if not prompt:
            continue
        if prompt.startswith("You "):
            candidates.append(f"I {prompt[4:].rstrip('.')}.")
        else:
            normalized = prompt[:1].lower() + prompt[1:] if prompt else prompt
            candidates.append(f"I {normalized.rstrip('.')}.")
    return candidates


def _extract_move_family_candidates(raw_text: str | None) -> list[str]:
    cleaned = strip_model_meta_wrapper_text(str(raw_text or ""))
    if not cleaned:
        return []
    candidates: list[str] = []
    patterns = (
        r'"move_family"\s*:\s*"([^"]+)"',
        r"\bmove_family\b\s*[:=]\s*([a-z_]+)",
        r"\bmove family\b\s*[:=]\s*([a-z_]+)",
        r"\bmove_family\b[^a-z_]*(public_pressure|coalition_repair|evidence_lock|resource_control|institutional_audit|protect_legitimacy|force_settlement)\b",
        r"\bmove family\b[^a-z_]*(public_pressure|coalition_repair|evidence_lock|resource_control|institutional_audit|protect_legitimacy|force_settlement)\b",
    )
    lowered = cleaned.casefold()
    for pattern in patterns:
        for match in re.finditer(pattern, lowered, flags=re.IGNORECASE | re.MULTILINE):
            candidate = str(match.group(1) or "").strip().casefold()
            if candidate in _MOVE_FAMILIES:
                candidates.append(candidate)
    for family in _MOVE_FAMILIES:
        if family in lowered:
            candidates.append(family)
    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _top_state_bar_labels(snapshot: dict[str, Any]) -> list[str]:
    bars = list(snapshot.get("state_bars") or [])
    ranked = sorted(
        [
            (abs(int(item.get("current_value") or 0)), str(item.get("label") or ""))
            for item in bars
            if str(item.get("label") or "").strip()
        ],
        reverse=True,
    )
    return [label for _score, label in ranked[:4]]


def _recent_player_moves(transcript: list[dict[str, str]], limit: int = 2) -> list[str]:
    player_lines = [str(item.get("text") or "").strip() for item in transcript if item.get("speaker") == "player"]
    return player_lines[-limit:]


def _recent_gm_consequences(transcript: list[dict[str, str]], limit: int = 2) -> list[str]:
    gm_lines = [str(item.get("text") or "").strip() for item in transcript if item.get("speaker") == "gm"]
    return gm_lines[-limit:]


def _target_npc_names(snapshot: dict[str, Any]) -> list[str]:
    visuals = list(snapshot.get("npc_visuals") or [])
    ranked = sorted(
        [
            (abs(int(item.get("stance_value") or 0)), str(item.get("name") or ""))
            for item in visuals
            if str(item.get("name") or "").strip()
        ],
        reverse=True,
    )
    return [name for _score, name in ranked[:3]]


def _build_turn_working_digest(
    *,
    story_detail: dict[str, Any],
    snapshot: dict[str, Any],
    transcript: list[dict[str, str]],
) -> dict[str, Any]:
    story = dict(story_detail.get("story") or {})
    play_overview = dict(story_detail.get("play_overview") or {})
    feedback = dict(snapshot.get("feedback") or {})
    return {
        "story_title": str(story.get("title") or ""),
        "runtime_profile": str(play_overview.get("runtime_profile_label") or play_overview.get("runtime_profile") or ""),
        "current_beat": {
            "title": str(snapshot.get("beat_title") or ""),
            "turn_index": int(snapshot.get("turn_index") or 0),
        },
        "recent_player_moves": _recent_player_moves(transcript),
        "recent_gm_consequences": _recent_gm_consequences(transcript),
        "key_state_bars": _top_state_bar_labels(snapshot),
        "target_npcs": _target_npc_names(snapshot),
        "last_feedback_consequences": list(feedback.get("last_turn_consequences") or [])[:3],
        "suggested_actions": [
            {
                "label": str(item.get("label") or ""),
                "prompt": str(item.get("prompt") or ""),
            }
            for item in list(snapshot.get("suggested_actions") or [])[:3]
        ],
    }


def _deterministic_move_family(*, snapshot: dict[str, Any], persona: AgentPersona, transcript: list[dict[str, str]]) -> str:
    text = " ".join(
        [
            str(snapshot.get("beat_title") or ""),
            " ".join(str(item.get("label") or "") for item in list(snapshot.get("suggested_actions") or [])),
            " ".join(str(item.get("prompt") or "") for item in list(snapshot.get("suggested_actions") or [])),
            " ".join(_recent_player_moves(transcript)),
        ]
    ).casefold()
    if any(token in text for token in ("record", "ledger", "proof", "evidence", "seal", "witness")):
        return "evidence_lock"
    if any(token in text for token in ("dock", "harbor", "supply", "ration", "resource", "corridor")):
        return "resource_control"
    if any(token in text for token in ("audit", "verify", "protocol", "charter", "inspection")):
        return "institutional_audit"
    if any(token in text for token in ("coalition", "ally", "witnesses", "reconcile", "agreement")):
        return "coalition_repair"
    if any(token in text for token in ("public", "crowd", "chamber", "floor", "mandate", "speech")):
        return "public_pressure"
    if persona.persona_id == "evidence_archivist":
        return "evidence_lock"
    if persona.persona_id == "resource_broker":
        return "resource_control"
    if persona.persona_id == "legitimacy_guardian":
        return "protect_legitimacy"
    if persona.persona_id == "coalition_builder":
        return "coalition_repair"
    return "public_pressure"


def _deterministic_turn_from_move_family(
    *,
    move_family: str,
    snapshot: dict[str, Any],
    persona: AgentPersona,
) -> str:
    beat_title = str(snapshot.get("beat_title") or "the crisis")
    target_npcs = _target_npc_names(snapshot)
    target_clause = f" with {' and '.join(target_npcs[:2])}" if target_npcs else ""
    templates = {
        "public_pressure": f"I force the room to answer publicly around {beat_title}{target_clause} before anyone can bury the truth again.",
        "coalition_repair": f"I pull the fractured sides back into one working bargain around {beat_title}{target_clause} before the room splinters.",
        "evidence_lock": f"I lock the strongest surviving record in place around {beat_title}{target_clause} before anyone can revise it again.",
        "resource_control": f"I secure the practical leverage around {beat_title}{target_clause} before scarcity turns into private rule.",
        "institutional_audit": f"I force a line-by-line institutional check around {beat_title}{target_clause} before procedure is used to hide the damage.",
        "protect_legitimacy": f"I make the public authority behind {beat_title} legible again{target_clause} before panic decides the mandate for us.",
        "force_settlement": f"I force the final terms around {beat_title}{target_clause} before the crisis hardens into a worse default.",
    }
    if move_family in templates:
        return templates[move_family]
    return PlaytestAgentClient._fallback_turn(persona, snapshot)


def _extract_turn_plan_from_raw_text(raw_text: str | None, *, snapshot: dict[str, Any]) -> TurnPlan | None:
    cleaned = str(raw_text or "").strip()
    if not cleaned:
        return None
    lowered = cleaned.casefold()
    extracted_any = False

    def _extract(patterns: tuple[str, ...]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, cleaned, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                return strip_model_meta_wrapper_text(match.group(1)).strip()
        return None

    move_family = None
    for family in _MOVE_FAMILIES:
        if re.search(rf"\b{re.escape(family)}\b", lowered):
            move_family = family
            extracted_any = True
            break
    if move_family is None:
        move_family = "public_pressure"
    beat_anchor = _extract((r'"?beat_anchor"?\s*[:=]\s*"?(.*?)"?$', r"\bBEAT_ANCHOR\b\s*[:=]\s*(.+)")) or str(snapshot.get("beat_title") or "")
    beat_goal = _extract((r'"?beat_goal"?\s*[:=]\s*"?(.*?)"?$', r"\bBEAT_GOAL\b\s*[:=]\s*(.+)")) or str(((snapshot.get("progress") or {}).get("current_beat_goal") or ""))
    risk_posture = (_extract((r'"?risk_posture"?\s*[:=]\s*"?(low|medium|high)"?', r"\bRISK_POSTURE\b\s*[:=]\s*(low|medium|high)")) or "medium").casefold()
    anti_repeat_note = _extract((r'"?anti_repeat_note"?\s*[:=]\s*"?(.*?)"?$', r"\bANTI_REPEAT_NOTE\b\s*[:=]\s*(.+)")) or ""
    prompt_outline = _extract((r'"?prompt_outline"?\s*[:=]\s*"?(.*?)"?$', r"\bPROMPT_OUTLINE\b\s*[:=]\s*(.+)")) or ""
    input_text = _normalize_turn_candidate_text(
        _extract((r'"?input_text"?\s*[:=]\s*"?(.*?)"?$', r"\bINPUT_TEXT\b\s*[:=]\s*(.+)"))
    )
    target_npcs_text = _extract((r'"?target_npcs"?\s*[:=]\s*\[(.*?)\]', r"\bTARGET_NPCS\b\s*[:=]\s*(.+)")) or ""
    target_npcs = [item.strip().strip('"') for item in re.split(r"[,/]", target_npcs_text) if item.strip()]
    if any((anti_repeat_note, prompt_outline, input_text, target_npcs_text)):
        extracted_any = True
    if not extracted_any:
        return None
    return TurnPlan(
        beat_anchor=beat_anchor,
        beat_goal=beat_goal,
        move_family=move_family,
        target_npcs=target_npcs[:3],
        risk_posture=risk_posture if risk_posture in {"low", "medium", "high"} else "medium",
        anti_repeat_note=anti_repeat_note,
        prompt_outline=prompt_outline,
        input_text=input_text,
    )


def _deterministic_turn_from_plan(*, plan: TurnPlan, snapshot: dict[str, Any], persona: AgentPersona) -> str:
    target_clause = f" with {' and '.join(plan.target_npcs[:2])}" if plan.target_npcs else ""
    base = _deterministic_turn_from_move_family(move_family=plan.move_family, snapshot=snapshot, persona=persona)
    if target_clause and target_clause not in base:
        base = base.rstrip(".") + f"{target_clause}."
    return base


def _select_turn_candidate(
    *,
    candidates: list[str],
    snapshot: dict[str, Any],
    forbidden_verbatim: list[str],
    rejected_candidates: set[str],
) -> tuple[str | None, dict[str, int], set[str]]:
    rejection_distribution: dict[str, int] = {}
    if not candidates:
        rejection_distribution["no_candidate_extracted"] = 1
        return None, rejection_distribution, rejected_candidates
    ranked: list[tuple[tuple[int, int, int], str]] = []
    updated_rejected = set(rejected_candidates)
    for candidate in candidates:
        normalized_candidate = _normalize_turn_candidate_text(candidate)
        rejection_reason = _turn_candidate_rejection_reason(
            normalized_candidate,
            snapshot=snapshot,
            forbidden_verbatim=forbidden_verbatim,
            rejected_candidates=updated_rejected,
        )
        if rejection_reason is not None:
            rejection_distribution[rejection_reason] = rejection_distribution.get(rejection_reason, 0) + 1
            if normalized_candidate:
                updated_rejected.add(normalized_candidate.casefold())
            continue
        ranked.append((_turn_candidate_score(normalized_candidate, snapshot=snapshot), normalized_candidate))
    if not ranked:
        return None, rejection_distribution, updated_rejected
    best_candidate = sorted(ranked, key=lambda item: item[0], reverse=True)[0][1]
    return best_candidate, rejection_distribution, updated_rejected


def _best_turn_moment(turns: list[dict[str, Any]]) -> str:
    if not turns:
        return "No clear peak moment reported."
    scored = []
    for turn in turns:
        feedback = dict(turn.get("feedback") or {})
        axis_count = sum(1 for value in dict(feedback.get("last_turn_axis_deltas") or {}).values() if int(value) != 0)
        stance_count = sum(1 for value in dict(feedback.get("last_turn_stance_deltas") or {}).values() if int(value) != 0)
        consequence_count = len(list(feedback.get("last_turn_consequences") or []))
        scored.append((axis_count + stance_count + consequence_count, int(turn.get("narration_word_count") or 0), turn))
    best_turn = max(scored, key=lambda item: (item[0], item[1]))[2]
    beat_title = str(best_turn.get("beat_title") or "the scene")
    return f"Turn {int(best_turn.get('turn_index') or 0)} in {beat_title} carried the clearest visible consequence."


def _deterministic_report_fallback(
    *,
    opening: str,
    turns: list[dict[str, Any]],
    final_snapshot: dict[str, Any],
    forced_stop: bool,
) -> dict[str, Any]:
    metrics = _session_feedback_metrics(turns)
    avg_narration_words = statistics.mean([int(turn.get("narration_word_count") or 0) for turn in turns]) if turns else 0.0
    meta_wrapper_turns = sum(
        1
        for turn in turns
        if "here is the json requested" in str(turn.get("narration") or "").casefold()
    )
    flags: list[str] = []
    if metrics["distinct_axis_count"] <= 1 and metrics["distinct_stance_count"] <= 1:
        flags.append("flat_state_feedback")
    if len(turns) >= 4 and _session_feedback_metrics(_late_half_turns(turns))["distinct_axis_count"] <= 1:
        flags.append("late_game_flatness")
    if "you" not in opening.casefold():
        flags.append("templated_opening")
    if meta_wrapper_turns:
        flags.append("narration_does_not_pay_off_state")
    ending_id = str((final_snapshot.get("ending") or {}).get("ending_id") or "unfinished")
    strongest_issue = "State changes landed as repeated slogans instead of realized scene prose."
    if forced_stop:
        strongest_issue = "The session ran out of runway before the play loop could land an ending."
    elif meta_wrapper_turns:
        strongest_issue = "Render output leaked response-wrapper text into the narration."
    elif metrics["distinct_axis_count"] <= 1 and metrics["distinct_stance_count"] <= 1:
        strongest_issue = "Most turns pushed the same visible feedback lane without enough contrast."
    ratings = {
        "narration_coherence": 2 if meta_wrapper_turns else 3 if avg_narration_words < 60 else 4,
        "suggested_action_relevance": 3 if turns else 1,
        "state_feedback_credibility": 2 if metrics["nonzero_feedback_turns"] <= 1 else 3 if metrics["distinct_axis_count"] <= 1 else 4,
        "ending_satisfaction": 2 if ending_id == "unfinished" else 3,
        "overall_player_feel": 2 if meta_wrapper_turns else 3,
        "protagonist_identity_clarity": 3,
        "content_richness": 2 if avg_narration_words < 30 else 3 if avg_narration_words < 70 else 4,
        "state_feedback_distinctness": 2 if metrics["distinct_axis_count"] <= 1 and metrics["distinct_stance_count"] <= 1 else 3 if metrics["distinct_axis_count"] <= 2 else 4,
    }
    return _normalize_agent_report(
        report={
            "ending_id": ending_id,
            "turn_count": int(final_snapshot.get("turn_index") or len(turns)),
            "ratings": ratings,
            "flags": flags,
            "strongest_issue": strongest_issue,
            "best_moment": _best_turn_moment(turns),
            "verdict": "Deterministic benchmark rubric fallback was used for this session.",
            "source": "fallback",
        },
        turns=turns,
    )


def _report_rubric_defaults(
    *,
    opening: str,
    turns: list[dict[str, Any]],
    final_snapshot: dict[str, Any],
    forced_stop: bool,
) -> dict[str, Any]:
    fallback = _deterministic_report_fallback(
        opening=opening,
        turns=turns,
        final_snapshot=final_snapshot,
        forced_stop=forced_stop,
    )
    return {
        "ending_id": fallback["ending_id"],
        "turn_count": fallback["turn_count"],
        "ratings": dict(fallback.get("ratings") or {}),
        "flags": list(fallback.get("flags") or []),
        "strongest_issue": fallback.get("strongest_issue"),
        "best_moment": fallback.get("best_moment"),
        "verdict": fallback.get("verdict"),
    }


def _salvage_report_from_raw_text(
    *,
    raw_text: str | None,
    opening: str,
    turns: list[dict[str, Any]],
    final_snapshot: dict[str, Any],
    forced_stop: bool,
) -> dict[str, Any] | None:
    cleaned = strip_model_meta_wrapper_text(str(raw_text or ""))
    if not cleaned:
        return None
    lowered = cleaned.casefold()
    ending_match = re.search(r"\b(collapse|pyrrhic|mixed)\b", lowered)
    field_patterns = {
        "narration_coherence": r"narration_coherence\s*[:=]\s*([1-5])",
        "suggested_action_relevance": r"suggested_action_relevance\s*[:=]\s*([1-5])",
        "state_feedback_credibility": r"state_feedback_credibility\s*[:=]\s*([1-5])",
        "ending_satisfaction": r"ending_satisfaction\s*[:=]\s*([1-5])",
        "overall_player_feel": r"overall_player_feel\s*[:=]\s*([1-5])",
        "content_richness": r"content_richness\s*[:=]\s*([1-5])",
        "state_feedback_distinctness": r"state_feedback_distinctness\s*[:=]\s*([1-5])",
        "protagonist_identity_clarity": r"protagonist_identity_clarity\s*[:=]\s*([1-5])",
    }
    ratings = {
        key: int(match.group(1))
        for key, pattern in field_patterns.items()
        if (match := re.search(pattern, lowered))
    }
    issue_match = re.search(r"strongest[ _]issue\s*[:=]\s*(.+)", cleaned, flags=re.IGNORECASE)
    best_match = re.search(r"best[ _]moment\s*[:=]\s*(.+)", cleaned, flags=re.IGNORECASE)
    verdict_match = re.search(r"verdict\s*[:=]\s*(.+)", cleaned, flags=re.IGNORECASE)
    sentences = _split_candidate_sentences(cleaned)
    natural_sentences = [sentence for sentence in sentences if not _is_structured_report_fragment(sentence)]
    defaults = _report_rubric_defaults(
        opening=opening,
        turns=turns,
        final_snapshot=final_snapshot,
        forced_stop=forced_stop,
    )
    strongest_issue = issue_match.group(1).strip() if issue_match else None
    verdict = verdict_match.group(1).strip() if verdict_match else None
    if strongest_issue is None and len(natural_sentences) >= 2:
        strongest_issue = natural_sentences[1]
    if verdict is None and natural_sentences:
        verdict = natural_sentences[0]
    best_moment = best_match.group(1).strip() if best_match else defaults["best_moment"]
    if not ratings and ending_match is None and strongest_issue is None and verdict is None:
        return None
    missing_fields = {
        field: 1
        for field in (
            "ending_id",
            "strongest_issue",
            "best_moment",
            "verdict",
            "narration_coherence",
            "suggested_action_relevance",
            "state_feedback_credibility",
            "ending_satisfaction",
            "overall_player_feel",
            "content_richness",
            "state_feedback_distinctness",
            "protagonist_identity_clarity",
        )
        if (
            (field == "ending_id" and ending_match is None)
            or (field == "strongest_issue" and issue_match is None and len(natural_sentences) < 2)
            or (field == "best_moment" and best_match is None)
            or (field == "verdict" and verdict_match is None and not natural_sentences)
            or (field in defaults["ratings"] and field not in ratings)
        )
    }
    return _normalize_agent_report(
        report={
            "ending_id": ending_match.group(1) if ending_match else defaults["ending_id"],
            "turn_count": int(final_snapshot.get("turn_index") or len(turns)),
            "ratings": {**defaults["ratings"], **ratings},
            "flags": defaults["flags"],
            "strongest_issue": strongest_issue or defaults["strongest_issue"],
            "best_moment": best_moment,
            "verdict": verdict or "Salvaged benchmark report from non-JSON model output.",
            "source": "llm_salvage_partial",
            "missing_field_distribution": missing_fields,
        },
        turns=turns,
    )


class PlaytestAgentClient:
    _helper_json_schema_probe_cache: dict[tuple[str, str], dict[str, Any]] = {}
    _driver_strategy_cache: dict[tuple[str, str, str, str], str] = {}

    def __init__(
        self,
        persona: AgentPersona,
        settings: Settings | None = None,
        *,
        transport_style: TransportStyle = "chat_completions",
        provider: str = "primary",
        enable_strategy_cache: bool = False,
    ) -> None:
        self.persona = persona
        self._settings = settings or get_settings()
        self._transport_style = transport_style
        self._enable_strategy_cache = enable_strategy_cache
        self._timeout_seconds = self._settings.resolved_gateway_timeout_seconds_for_benchmark_driver()
        self.call_trace: list[dict[str, Any]] = []
        self.error_distribution: dict[str, int] = {}
        self.turn_rejection_distribution: dict[str, int] = {}
        self.report_missing_field_distribution: dict[str, int] = {}
        self._driver_strategy = "json_mode_compact_prompt"
        self._previous_response_id: str | None = None
        self._provider = "helper" if provider == "helper" else "primary"
        self._model = ""
        if self._provider == "helper":
            self._timeout_seconds = max(self._timeout_seconds, HELPER_BENCHMARK_TIMEOUT_FLOOR_SECONDS)
            self._configure_provider(provider_label="helper", transport_style=transport_style)
            if transport_style != "chat_completions":
                self._driver_strategy = "json_mode_compact_prompt"
                return
            helper_probe = self._probe_helper_json_schema_capability()
            if helper_probe["supported"]:
                self._driver_strategy = "strict_schema"
                return
            self._append_failed_call_trace(
                capability_context="benchmark_driver.provider_probe",
                operation_name="playtest_helper_provider_probe",
                stage_source="helper_provider_probe",
                error=_PlaytestAgentError(
                    code="playtest_agent_helper_provider_probe_failed",
                    message=str(helper_probe["error_message"] or "helper provider does not support strict json schema"),
                ),
                elapsed_ms=int(helper_probe["elapsed_ms"] or 0),
                provider_rate_limit_wait_ms=int(helper_probe.get("rate_limit_wait_ms") or 0),
                provider_rate_limit_applied=bool(helper_probe.get("rate_limit_applied")),
            )
            self._configure_provider(provider_label="primary", transport_style=transport_style)
            self._append_direct_call_trace(
                capability_context="benchmark_driver.provider_probe",
                operation_name="playtest_helper_provider_fallback",
                stage_source="helper_provider_fallback",
                response_id=None,
                input_characters=0,
                elapsed_ms=0,
                fallback_source="primary",
            )
            self._driver_strategy = self._probe_driver_strategy()
            return
        self._configure_provider(provider_label="primary", transport_style=transport_style)
        self._driver_strategy = self._probe_driver_strategy()

    def _configure_provider(
        self,
        *,
        provider_label: str,
        transport_style: TransportStyle,
    ) -> None:
        if provider_label == "helper":
            base_url = self._settings.resolved_helper_gateway_base_url(transport_style=transport_style)
            api_key = self._settings.resolved_helper_gateway_api_key()
            model = self._settings.resolved_helper_gateway_model()
            use_session_cache = self._settings.resolved_helper_gateway_use_session_cache(transport_style=transport_style)
            missing_message = (
                "APP_HELPER_GATEWAY_BASE_URL, APP_HELPER_GATEWAY_API_KEY, and "
                "APP_HELPER_GATEWAY_MODEL are required for helper benchmark agents"
            )
        else:
            base_url = self._settings.resolved_gateway_base_url(transport_style=transport_style)
            api_key = self._settings.resolved_gateway_api_key()
            model = self._settings.resolved_gateway_model()
            use_session_cache = self._settings.resolved_gateway_use_session_cache(transport_style=transport_style)
            missing_message = (
                "APP_GATEWAY_BASE_URL, APP_GATEWAY_API_KEY, and APP_GATEWAY_MODEL are required for benchmark agents"
            )
        if not base_url or not api_key or not model:
            raise _PlaytestAgentError(code="playtest_agent_config_missing", message=missing_message)
        self._provider = provider_label
        self._provider_base_url = base_url
        self._model = model
        self._client = build_openai_client(
            base_url=base_url,
            api_key=api_key,
            use_session_cache=bool(use_session_cache),
            session_cache_header=self._settings.resolved_gateway_session_cache_header(),
            session_cache_value=self._settings.resolved_gateway_session_cache_value(),
        )
        self._transport: JSONTransport = build_json_transport(
            style=self._transport_style,
            client=self._client,
            model=model,
            timeout_seconds=self._timeout_seconds,
            use_session_cache=bool(use_session_cache),
            temperature=0.45,
            enable_thinking=False,
            provider_failed_code="playtest_agent_provider_failed",
            invalid_response_code="playtest_agent_invalid_response",
            invalid_json_code="playtest_agent_invalid_json",
            error_factory=self._error_factory,
            call_trace=self.call_trace,
        )

    @contextmanager
    def _benchmark_rate_limit_slot(self):
        if self._provider != "helper":
            yield _BenchmarkProviderRateLimitDecision(wait_ms=0, applied=False)
            return
        limiter = get_shared_benchmark_provider_limiter(
            base_url=self._provider_base_url,
            model=self._model,
        )
        with limiter.acquire() as decision:
            yield decision

    def _probe_helper_json_schema_capability(self) -> dict[str, Any]:
        started_at = time.perf_counter()
        probe_base_url = self._settings.resolved_helper_gateway_base_url(transport_style="chat_completions")
        probe_api_key = self._settings.resolved_helper_gateway_api_key()
        probe_model = self._settings.resolved_helper_gateway_model()
        if not probe_base_url or not probe_api_key or not probe_model:
            return {
                "supported": False,
                "elapsed_ms": 0,
                "error_message": "helper provider config missing",
                "rate_limit_wait_ms": 0,
                "rate_limit_applied": False,
            }
        cache_key = (probe_base_url.rstrip("/"), probe_model)
        if self._enable_strategy_cache:
            cached = self.__class__._helper_json_schema_probe_cache.get(cache_key)
            if cached is not None:
                return {**cached, "elapsed_ms": 0}
        probe_client = build_openai_client(
            base_url=probe_base_url,
            api_key=probe_api_key,
            use_session_cache=False,
            session_cache_header=self._settings.resolved_gateway_session_cache_header(),
            session_cache_value=self._settings.resolved_gateway_session_cache_value(),
        )
        try:
            with self._benchmark_rate_limit_slot() as decision:
                response = probe_client.chat.completions.create(
                    model=probe_model,
                    messages=[
                        {"role": "system", "content": "Return strict JSON."},
                        {"role": "user", "content": "Return ok=true"},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "benchmark_probe",
                            "schema": {
                                "type": "object",
                                "properties": {"ok": {"type": "boolean"}},
                                "required": ["ok"],
                                "additionalProperties": False,
                            },
                            "strict": True,
                        },
                    },
                    max_completion_tokens=32,
                    timeout=self._timeout_seconds,
                    temperature=0,
                )
            message = getattr((getattr(response, "choices", None) or [None])[0], "message", None)
            content = getattr(message, "content", None)
            text = str(content or "")
            result = {
                "supported": "\"ok\"" in text or "ok" in text.casefold(),
                "elapsed_ms": max(int((time.perf_counter() - started_at) * 1000), 0),
                "error_message": None,
                "rate_limit_wait_ms": decision.wait_ms,
                "rate_limit_applied": decision.applied,
            }
            if self._enable_strategy_cache:
                self.__class__._helper_json_schema_probe_cache[cache_key] = dict(result)
            return result
        except Exception as exc:  # noqa: BLE001
            result = {
                "supported": False,
                "elapsed_ms": max(int((time.perf_counter() - started_at) * 1000), 0),
                "error_message": str(exc),
                "rate_limit_wait_ms": 0,
                "rate_limit_applied": False,
            }
            if self._enable_strategy_cache:
                self.__class__._helper_json_schema_probe_cache[cache_key] = dict(result)
            return result

    def _error_factory(self, code: str, message: str, _status_code: int) -> _PlaytestAgentError:
        self.error_distribution[code] = self.error_distribution.get(code, 0) + 1
        return _PlaytestAgentError(code=code, message=message)

    def _extend_last_call_trace(
        self,
        *,
        capability_context: str,
        operation_name: str,
        stage_source: str,
        elapsed_ms: int,
        provider_rate_limit_wait_ms: int = 0,
        provider_rate_limit_applied: bool = False,
    ) -> None:
        if not self.call_trace:
            return
        self.call_trace[-1].update(
            {
                "capability_context": capability_context,
                "persona_id": self.persona.persona_id,
                "agent_provider": self._provider,
                "timeout_seconds": self._timeout_seconds,
                "elapsed_ms": elapsed_ms,
                "operation_name": operation_name,
                "stage_source": stage_source,
                "provider_rate_limit_wait_ms": provider_rate_limit_wait_ms,
                "provider_rate_limit_applied": provider_rate_limit_applied,
            }
        )

    def _append_failed_call_trace(
        self,
        *,
        capability_context: str,
        operation_name: str,
        stage_source: str,
        error: _PlaytestAgentError,
        elapsed_ms: int,
        provider_rate_limit_wait_ms: int = 0,
        provider_rate_limit_applied: bool = False,
    ) -> None:
        self.call_trace.append(
            {
                "transport": self._transport_style,
                "transport_style": self._transport_style,
                "operation": operation_name,
                "operation_name": operation_name,
                "capability_context": capability_context,
                "persona_id": self.persona.persona_id,
                "agent_provider": self._provider,
                "model": self._model,
                "timeout_seconds": self._timeout_seconds,
                "elapsed_ms": elapsed_ms,
                "error_code": error.code,
                "error_message": error.message,
                "stage_source": stage_source,
                "provider_rate_limit_wait_ms": provider_rate_limit_wait_ms,
                "provider_rate_limit_applied": provider_rate_limit_applied,
                "response_id": None,
                "fallback_source": None,
            }
        )

    def _append_direct_call_trace(
        self,
        *,
        capability_context: str,
        operation_name: str,
        stage_source: str,
        response_id: str | None,
        input_characters: int,
        elapsed_ms: int,
        fallback_source: str | None,
        error: _PlaytestAgentError | None = None,
        provider_rate_limit_wait_ms: int = 0,
        provider_rate_limit_applied: bool = False,
    ) -> None:
        entry: dict[str, Any] = {
            "transport": self._transport_style,
            "transport_style": self._transport_style,
            "operation": operation_name,
            "operation_name": operation_name,
            "capability_context": capability_context,
            "persona_id": self.persona.persona_id,
            "agent_provider": self._provider,
            "model": self._model,
            "timeout_seconds": self._timeout_seconds,
            "elapsed_ms": elapsed_ms,
            "response_id": response_id,
            "input_characters": input_characters,
            "fallback_source": fallback_source,
            "stage_source": stage_source,
            "provider_rate_limit_wait_ms": provider_rate_limit_wait_ms,
            "provider_rate_limit_applied": provider_rate_limit_applied,
        }
        if error is not None:
            entry["error_code"] = error.code
            entry["error_message"] = error.message
        self.call_trace.append(entry)

    def _probe_driver_strategy(self) -> str:
        if self._transport_style != "chat_completions":
            return "json_mode_compact_prompt"
        cache_key = (
            self._provider,
            self._transport_style,
            self._provider_base_url.rstrip("/"),
            self._model,
        )
        if self._enable_strategy_cache:
            cached = self.__class__._driver_strategy_cache.get(cache_key)
            if cached is not None:
                return cached
        started_at = time.perf_counter()
        try:
            with self._benchmark_rate_limit_slot() as decision:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": "Return strict JSON."},
                        {"role": "user", "content": "Return ok=true"},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "benchmark_probe",
                            "schema": {
                                "type": "object",
                                "properties": {"ok": {"type": "boolean"}},
                                "required": ["ok"],
                                "additionalProperties": False,
                            },
                            "strict": True,
                        },
                    },
                    max_completion_tokens=32,
                    timeout=self._timeout_seconds,
                    temperature=0,
                )
            message = getattr((getattr(response, "choices", None) or [None])[0], "message", None)
            content = getattr(message, "content", None)
            text = str(content or "")
            self._append_direct_call_trace(
                capability_context="benchmark_driver.driver_strategy_probe",
                operation_name="playtest_driver_strategy_probe",
                stage_source="structured_probe",
                response_id=getattr(response, "id", None),
                input_characters=len("Return ok=true"),
                elapsed_ms=max(int((time.perf_counter() - started_at) * 1000), 0),
                fallback_source=None,
                provider_rate_limit_wait_ms=decision.wait_ms,
                provider_rate_limit_applied=decision.applied,
            )
            if "\"ok\"" in text or "ok" in text.casefold():
                if self._enable_strategy_cache:
                    self.__class__._driver_strategy_cache[cache_key] = "strict_schema"
                return "strict_schema"
        except Exception as exc:  # noqa: BLE001
            error = self._error_factory("playtest_agent_structured_output_probe_failed", str(exc), 502)
            self.error_distribution[f"playtest_agent_structured_output_probe_reason:{type(exc).__name__}"] = (
                self.error_distribution.get(f"playtest_agent_structured_output_probe_reason:{type(exc).__name__}", 0) + 1
            )
            self._append_failed_call_trace(
                capability_context="benchmark_driver.driver_strategy_probe",
                operation_name="playtest_driver_strategy_probe",
                stage_source="structured_probe",
                error=error,
                elapsed_ms=max(int((time.perf_counter() - started_at) * 1000), 0),
                provider_rate_limit_wait_ms=0,
                provider_rate_limit_applied=False,
            )
        if self._enable_strategy_cache:
            self.__class__._driver_strategy_cache[cache_key] = "json_mode_compact_prompt"
        return "json_mode_compact_prompt"

    def _invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_output_tokens: int,
        operation_name: str,
        capability_context: str,
        stage_source: str,
        record_passthrough_as_invalid_json: bool = True,
    ) -> ResponsesJSONResponse:
        started_at = time.perf_counter()
        try:
            with self._benchmark_rate_limit_slot() as decision:
                response = self._transport.invoke_json(
                    system_prompt=system_prompt,
                    user_payload=user_payload,
                    max_output_tokens=max_output_tokens,
                    previous_response_id=self._previous_response_id,
                    operation_name=operation_name,
                    allow_raw_text_passthrough=True,
                )
        except _PlaytestAgentError as exc:
            self._append_failed_call_trace(
                capability_context=capability_context,
                operation_name=operation_name,
                stage_source=stage_source,
                error=exc,
                elapsed_ms=max(int((time.perf_counter() - started_at) * 1000), 0),
                provider_rate_limit_wait_ms=0,
                provider_rate_limit_applied=False,
            )
            raise
        self._previous_response_id = response.response_id or self._previous_response_id
        self._extend_last_call_trace(
            capability_context=capability_context,
            operation_name=operation_name,
            stage_source=stage_source,
            elapsed_ms=max(int((time.perf_counter() - started_at) * 1000), 0),
            provider_rate_limit_wait_ms=decision.wait_ms,
            provider_rate_limit_applied=decision.applied,
        )
        if response.fallback_source == "raw_text_passthrough" and record_passthrough_as_invalid_json:
            self.error_distribution["playtest_agent_invalid_json"] = self.error_distribution.get("playtest_agent_invalid_json", 0) + 1
        return response

    def _invoke_structured_output_chat(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        operation_name: str,
        capability_context: str,
        stage_source: str,
        max_output_tokens: int,
        schema_name: str,
        schema_properties: dict[str, Any],
        required_fields: list[str],
    ) -> ResponsesJSONResponse:
        started_at = time.perf_counter()
        try:
            with self._benchmark_rate_limit_slot() as decision:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True)},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "schema": {
                                "type": "object",
                                "properties": schema_properties,
                                "required": required_fields,
                                "additionalProperties": False,
                            },
                            "strict": True,
                        },
                    },
                    max_completion_tokens=max_output_tokens,
                    timeout=self._timeout_seconds,
                    temperature=0.3,
                )
        except Exception as exc:  # noqa: BLE001
            error = self._error_factory("playtest_agent_provider_failed", str(exc), 502)
            self._append_failed_call_trace(
                capability_context=capability_context,
                operation_name=operation_name,
                stage_source=stage_source,
                error=error,
                elapsed_ms=max(int((time.perf_counter() - started_at) * 1000), 0),
                provider_rate_limit_wait_ms=0,
                provider_rate_limit_applied=False,
            )
            raise error from exc
        try:
            choice = (getattr(response, "choices", None) or [])[0]
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
            raw_text = str(content or "")
            payload = json.loads(strip_model_meta_wrapper_text(raw_text))
        except Exception as exc:  # noqa: BLE001
            self.error_distribution["playtest_agent_invalid_json"] = self.error_distribution.get("playtest_agent_invalid_json", 0) + 1
            self._append_direct_call_trace(
                capability_context=capability_context,
                operation_name=operation_name,
                stage_source=stage_source,
                response_id=getattr(response, "id", None),
                input_characters=len(json.dumps(user_payload, ensure_ascii=False, sort_keys=True)),
                elapsed_ms=max(int((time.perf_counter() - started_at) * 1000), 0),
                fallback_source="raw_text_passthrough",
                error=_PlaytestAgentError(code="playtest_agent_invalid_json", message=str(exc)),
            )
            return ResponsesJSONResponse(
                payload={},
                response_id=getattr(response, "id", None),
                usage={},
                input_characters=len(json.dumps(user_payload, ensure_ascii=False, sort_keys=True)),
                fallback_source="raw_text_passthrough",
                raw_text=str(getattr((getattr(response, "choices", None) or [None])[0], "message", None) or ""),
            )
        self._append_direct_call_trace(
            capability_context=capability_context,
            operation_name=operation_name,
            stage_source=stage_source,
            response_id=getattr(response, "id", None),
            input_characters=len(json.dumps(user_payload, ensure_ascii=False, sort_keys=True)),
            elapsed_ms=max(int((time.perf_counter() - started_at) * 1000), 0),
            fallback_source=None,
            provider_rate_limit_wait_ms=decision.wait_ms,
            provider_rate_limit_applied=decision.applied,
        )
        return ResponsesJSONResponse(
            payload=payload if isinstance(payload, dict) else {},
            response_id=getattr(response, "id", None),
            usage={},
            input_characters=len(json.dumps(user_payload, ensure_ascii=False, sort_keys=True)),
            fallback_source=None,
            raw_text=raw_text,
        )

    @staticmethod
    def _turn_json_system_prompt(persona: AgentPersona) -> str:
        return (
            "You are a benchmark playtest agent for an interactive fiction API. "
            "Stay in English. Output only JSON with one key: input_text. "
            "Write one concrete first-person player move, 1-2 sentences, grounded in the current scene. "
            "You may draw inspiration from suggested actions but must not copy their prompt text verbatim. "
            f"Persona: {persona.label}. "
            f"Turn style: {persona.turn_style} "
            f"Decision lens: {persona.decision_lens}"
        )

    @staticmethod
    def _turn_plan_json_system_prompt(persona: AgentPersona) -> str:
        families = ", ".join(_MOVE_FAMILIES)
        return (
            "You are a benchmark playtest planner for an interactive fiction API. "
            "Stay in English. Output only JSON with keys: beat_anchor, beat_goal, move_family, target_npcs, risk_posture, anti_repeat_note, prompt_outline, input_text. "
            f"Allowed move_family values: {families}. "
            "risk_posture must be low, medium, or high. "
            "input_text must be a concrete first-person player move, 1-2 sentences, grounded in the current beat and not a beat-title restatement. "
            f"Persona: {persona.label}. Turn style: {persona.turn_style} Decision lens: {persona.decision_lens}"
        )

    @staticmethod
    def _turn_plan_plaintext_system_prompt(persona: AgentPersona) -> str:
        families = ", ".join(_MOVE_FAMILIES)
        return (
            "You are a benchmark playtest planner for an interactive fiction API. "
            "Stay in English. Do not return JSON. Return a compact block with these fields on separate lines: "
            "BEAT_ANCHOR, BEAT_GOAL, MOVE_FAMILY, TARGET_NPCS, RISK_POSTURE, ANTI_REPEAT_NOTE, PROMPT_OUTLINE, INPUT_TEXT. "
            f"Allowed move family values: {families}. "
            "INPUT_TEXT must be a concrete first-person player move, 1-2 sentences, grounded in the current beat and not a beat-title restatement. "
            f"Persona: {persona.label}. Turn style: {persona.turn_style} Decision lens: {persona.decision_lens}"
        )

    @staticmethod
    def _turn_plaintext_system_prompt(persona: AgentPersona) -> str:
        return (
            "You are a benchmark playtest agent for an interactive fiction API. "
            "Stay in English. Return exactly one line in this format: INPUT_TEXT: <player move>. "
            "Do not return JSON. Do not explain yourself. "
            "The move must be first-person, concrete, 1-2 sentences, and grounded in the current scene. "
            f"Persona: {persona.label}. "
            f"Turn style: {persona.turn_style} "
            f"Decision lens: {persona.decision_lens}"
        )

    @staticmethod
    def _move_family_json_system_prompt(persona: AgentPersona) -> str:
        families = ", ".join(_MOVE_FAMILIES)
        return (
            "You are selecting a move family for a benchmark playtest agent. "
            "Stay in English. Output only JSON with one key: move_family. "
            f"Allowed move_family values: {families}. "
            "Choose the single best family for the next player move."
            f" Persona: {persona.label}. Turn style: {persona.turn_style} Decision lens: {persona.decision_lens}"
        )

    @staticmethod
    def _move_family_plaintext_system_prompt(persona: AgentPersona) -> str:
        families = ", ".join(_MOVE_FAMILIES)
        return (
            "You are selecting a move family for a benchmark playtest agent. "
            f"Allowed move family values: {families}. "
            "Return exactly one line in this format: MOVE_FAMILY: <family>. "
            "Do not return JSON. Do not explain yourself."
            f" Persona: {persona.label}. Turn style: {persona.turn_style} Decision lens: {persona.decision_lens}"
        )

    @staticmethod
    def _turn_json_with_family_system_prompt(persona: AgentPersona) -> str:
        return (
            "You are a benchmark playtest agent for an interactive fiction API. "
            "Stay in English. Output only JSON with one key: input_text. "
            "Write one concrete first-person player move, 1-2 sentences, grounded in the current scene and the provided move_family. "
            "Do not echo beat titles. Do not copy suggested prompts verbatim."
            f" Persona: {persona.label}. Turn style: {persona.turn_style} Decision lens: {persona.decision_lens}"
        )

    @staticmethod
    def _turn_plaintext_with_family_system_prompt(persona: AgentPersona) -> str:
        return (
            "You are a benchmark playtest agent for an interactive fiction API. "
            "Stay in English. Return exactly one line in this format: INPUT_TEXT: <player move>. "
            "Use the provided move_family. Do not return JSON. Do not explain yourself. "
            "The move must be first-person, concrete, 1-2 sentences, grounded in the current scene, and not a beat-title restatement."
            f" Persona: {persona.label}. Turn style: {persona.turn_style} Decision lens: {persona.decision_lens}"
        )

    @staticmethod
    def _fallback_turn(persona: AgentPersona, snapshot: dict[str, Any]) -> str:
        beat_title = str(snapshot.get("beat_title") or "the crisis")
        if persona.persona_id == "assertive_operator":
            return f"I force the key officials to face the evidence around {beat_title} in public before anyone can hide behind procedure again."
        return f"I gather the opposing sides around the strongest record tied to {beat_title} and make them reconcile the facts before the room fractures."

    def propose_turn(
        self,
        *,
        story_detail: dict[str, Any],
        snapshot: dict[str, Any],
        transcript: list[dict[str, str]],
    ) -> dict[str, Any]:
        budget_context = _benchmark_driver_budget_context(story_detail)
        suggested_actions = snapshot.get("suggested_actions") or []
        forbidden_verbatim = [str(item.get("prompt") or "").strip() for item in suggested_actions if item.get("prompt")]
        working_digest = _build_turn_working_digest(
            story_detail=story_detail,
            snapshot=snapshot,
            transcript=transcript,
        )
        verbatim_recall = transcript[-2:]
        move_family_payload = {
            "working_digest": working_digest,
            "verbatim_recall_slice": verbatim_recall,
        }
        payload = {
            "working_digest": working_digest,
            "verbatim_recall_slice": verbatim_recall,
            "forbidden_verbatim_prompts": forbidden_verbatim,
        }
        if self._driver_strategy != "strict_schema":
            legacy_payload = {
                "working_digest": working_digest,
                "verbatim_recall_slice": verbatim_recall,
                "forbidden_verbatim_prompts": forbidden_verbatim,
                "last_move_family": None,
            }
            rejected_candidates: set[str] = set()
            stage_specs = (
                ("llm", self._turn_plan_json_system_prompt(self.persona), budget_context["turn_max_output_tokens"], True),
                ("llm_salvage", self._turn_plan_plaintext_system_prompt(self.persona), budget_context["turn_stage2_max_output_tokens"], False),
            )
            for attempt, (stage_source, system_prompt, max_output_tokens, record_passthrough_as_invalid_json) in enumerate(stage_specs, start=1):
                try:
                    response = self._invoke_json(
                        system_prompt=system_prompt,
                        user_payload=legacy_payload,
                        max_output_tokens=max_output_tokens,
                        operation_name=f"playtest_turn_{self.persona.persona_id}",
                        capability_context="benchmark_driver.turn_proposal",
                        stage_source=stage_source,
                        record_passthrough_as_invalid_json=record_passthrough_as_invalid_json,
                    )
                    candidates: list[str] = []
                    turn_plan = _extract_turn_plan_from_raw_text(
                        response.raw_text or json.dumps(response.payload, ensure_ascii=False),
                        snapshot=snapshot,
                    )
                    payload_input = _normalize_turn_candidate_text(response.payload.get("input_text"))
                    if payload_input:
                        candidates.append(payload_input)
                    if turn_plan is not None and turn_plan.input_text:
                        candidates.append(_normalize_turn_candidate_text(turn_plan.input_text))
                    if response.raw_text:
                        candidates.extend(_extract_turn_input_candidates(response.raw_text))
                    if turn_plan is not None and not candidates:
                        candidates.append(_deterministic_turn_from_plan(plan=turn_plan, snapshot=snapshot, persona=self.persona))
                    if stage_source == "llm_salvage" and not candidates:
                        candidates.extend(_suggested_prompt_salvage_candidates(snapshot))
                    input_text, rejection_distribution, rejected_candidates = _select_turn_candidate(
                        candidates=candidates,
                        snapshot=snapshot,
                        forbidden_verbatim=forbidden_verbatim,
                        rejected_candidates=rejected_candidates,
                    )
                    for key, value in rejection_distribution.items():
                        self.turn_rejection_distribution[key] = self.turn_rejection_distribution.get(key, 0) + int(value)
                    if input_text:
                        return {
                            "input_text": input_text,
                            "source": stage_source,
                            "attempt": attempt,
                            "move_family": turn_plan.move_family if turn_plan is not None else None,
                            "move_family_stage1_success": False,
                            "turn_stage1_success_count": 1 if stage_source == "llm" else 0,
                            "turn_stage2_rescue_count": 1 if stage_source == "llm_salvage" else 0,
                        }
                    legacy_payload["forbidden_verbatim_prompts"] = [*forbidden_verbatim, *sorted(rejected_candidates)]
                except _PlaytestAgentError:
                    continue
            return {
                "input_text": self._fallback_turn(self.persona, snapshot),
                "source": "fallback",
                "attempt": 0,
                "move_family": None,
                "move_family_stage1_success": False,
                "turn_stage1_success_count": 0,
                "turn_stage2_rescue_count": 0,
            }
        move_family = _deterministic_move_family(snapshot=snapshot, persona=self.persona, transcript=transcript)
        turn_stage1_success_count = 0
        turn_stage2_rescue_count = 0
        move_family_stage1_success = False
        rejected_candidates: set[str] = set()
        if self._driver_strategy == "strict_schema":
            family_stage_specs = (
                ("llm", self._move_family_json_system_prompt(self.persona), budget_context["turn_max_output_tokens"], True),
                ("llm_salvage", self._move_family_plaintext_system_prompt(self.persona), budget_context["turn_stage2_max_output_tokens"], False),
            )
            for family_attempt, (family_source, system_prompt, max_output_tokens, record_passthrough_as_invalid_json) in enumerate(family_stage_specs, start=1):
                try:
                    if family_source == "llm":
                        response = self._invoke_structured_output_chat(
                            system_prompt=system_prompt,
                            user_payload=move_family_payload,
                            operation_name=f"playtest_move_family_{self.persona.persona_id}",
                            capability_context="benchmark_driver.turn_proposal",
                            stage_source=family_source,
                            max_output_tokens=max_output_tokens,
                            schema_name="benchmark_move_family",
                            schema_properties={"move_family": {"type": "string", "enum": list(_MOVE_FAMILIES)}},
                            required_fields=["move_family"],
                        )
                    else:
                        response = self._invoke_json(
                            system_prompt=system_prompt,
                            user_payload=move_family_payload,
                            max_output_tokens=max_output_tokens,
                            operation_name=f"playtest_move_family_{self.persona.persona_id}",
                            capability_context="benchmark_driver.turn_proposal",
                            stage_source=family_source,
                            record_passthrough_as_invalid_json=record_passthrough_as_invalid_json,
                        )
                    candidates = _extract_move_family_candidates(response.raw_text or json.dumps(response.payload, ensure_ascii=False))
                    payload_family = str(response.payload.get("move_family") or "").strip().casefold()
                    if payload_family in _MOVE_FAMILIES:
                        candidates = [payload_family, *candidates]
                    if candidates:
                        move_family = candidates[0]
                        if family_source == "llm":
                            move_family_stage1_success = True
                        break
                except _PlaytestAgentError:
                    continue
        turn_payload = {
            **payload,
            "move_family": move_family,
            "driver_strategy": self._driver_strategy,
        }
        stage_specs = (
            ("llm", self._turn_json_with_family_system_prompt(self.persona), budget_context["turn_max_output_tokens"], True),
            ("llm_salvage", self._turn_plaintext_with_family_system_prompt(self.persona), budget_context["turn_stage2_max_output_tokens"], False),
        )
        for attempt, (stage_source, system_prompt, max_output_tokens, record_passthrough_as_invalid_json) in enumerate(stage_specs, start=1):
            try:
                if self._driver_strategy == "strict_schema" and stage_source == "llm":
                    response = self._invoke_structured_output_chat(
                        system_prompt=system_prompt,
                        user_payload=turn_payload,
                        operation_name=f"playtest_turn_{self.persona.persona_id}",
                        capability_context="benchmark_driver.turn_proposal",
                        stage_source=stage_source,
                        max_output_tokens=max_output_tokens,
                        schema_name="benchmark_turn_input",
                        schema_properties={"input_text": {"type": "string"}},
                        required_fields=["input_text"],
                    )
                else:
                    response = self._invoke_json(
                        system_prompt=system_prompt,
                        user_payload=turn_payload,
                        max_output_tokens=max_output_tokens,
                        operation_name=f"playtest_turn_{self.persona.persona_id}",
                        capability_context="benchmark_driver.turn_proposal",
                        stage_source=stage_source,
                        record_passthrough_as_invalid_json=record_passthrough_as_invalid_json,
                    )
                candidates: list[str] = []
                payload_input = _normalize_turn_candidate_text(response.payload.get("input_text"))
                if payload_input:
                    candidates.append(payload_input)
                if response.raw_text:
                    candidates.extend(_extract_turn_input_candidates(response.raw_text))
                if stage_source == "llm_salvage" and not candidates:
                    candidates.extend(_suggested_prompt_salvage_candidates(snapshot))
                input_text, rejection_distribution, rejected_candidates = _select_turn_candidate(
                    candidates=candidates,
                    snapshot=snapshot,
                    forbidden_verbatim=forbidden_verbatim,
                    rejected_candidates=rejected_candidates,
                )
                for key, value in rejection_distribution.items():
                    self.turn_rejection_distribution[key] = self.turn_rejection_distribution.get(key, 0) + int(value)
                if input_text:
                    if stage_source == "llm":
                        turn_stage1_success_count += 1
                    else:
                        turn_stage2_rescue_count += 1
                    return {
                        "input_text": input_text,
                        "source": stage_source,
                        "attempt": attempt,
                        "move_family": move_family,
                        "move_family_stage1_success": move_family_stage1_success,
                        "turn_stage1_success_count": turn_stage1_success_count,
                        "turn_stage2_rescue_count": turn_stage2_rescue_count,
                    }
                turn_payload["forbidden_verbatim_prompts"] = [*forbidden_verbatim, *sorted(rejected_candidates)]
            except _PlaytestAgentError:
                continue
        return {
            "input_text": _deterministic_turn_from_move_family(move_family=move_family, snapshot=snapshot, persona=self.persona),
            "source": "fallback",
            "attempt": 0,
            "move_family": move_family,
            "move_family_stage1_success": move_family_stage1_success,
            "turn_stage1_success_count": turn_stage1_success_count,
            "turn_stage2_rescue_count": turn_stage2_rescue_count,
        }

    def build_report(
        self,
        *,
        story_detail: dict[str, Any],
        opening: str,
        turns: list[dict[str, Any]],
        final_snapshot: dict[str, Any],
        forced_stop: bool,
    ) -> dict[str, Any]:
        budget_context = _benchmark_driver_budget_context(story_detail)
        report_stage1_success = False
        report_stage2_rescue = False
        payload = {
            "story_detail": story_detail,
            "opening": opening,
            "turns": turns,
            "final_snapshot": final_snapshot,
            "forced_stop": forced_stop,
        }
        json_system_prompt = (
            "You are grading an interactive fiction play session. Stay in English. "
            "Output only JSON with keys: ending_id, turn_count, ratings, flags, strongest_issue, best_moment, verdict. "
            "ratings must contain narration_coherence, suggested_action_relevance, state_feedback_credibility, ending_satisfaction, overall_player_feel, content_richness, state_feedback_distinctness, protagonist_identity_clarity as integers 1-5. "
            "flags must be a list chosen from flat_state_feedback, late_game_flatness, suggestion_template_drift, ending_feels_unearned, narration_does_not_pay_off_state, player_identity_confusion, templated_opening. "
            "Only use flat_state_feedback when most turns produce nearly identical visible feedback or almost no distinct state change. "
            "Use late_game_flatness when the middle or late turns start feeling semantically repetitive even if the opening had momentum. "
            f"Persona lens: {self.persona.report_lens}"
        )
        compact_system_prompt = (
            "You are grading an interactive fiction play session. Stay in English. "
            "Do not return JSON. Return a compact block with one field per line in this exact style: "
            "ENDING: <collapse|pyrrhic|mixed>; NARRATION_COHERENCE: <1-5>; SUGGESTED_ACTION_RELEVANCE: <1-5>; "
            "STATE_FEEDBACK_CREDIBILITY: <1-5>; ENDING_SATISFACTION: <1-5>; OVERALL_PLAYER_FEEL: <1-5>; "
            "CONTENT_RICHNESS: <1-5>; STATE_FEEDBACK_DISTINCTNESS: <1-5>; PROTAGONIST_IDENTITY_CLARITY: <1-5>; "
            "STRONGEST_ISSUE: <text>; BEST_MOMENT: <text>; VERDICT: <text>. "
            f"Persona lens: {self.persona.report_lens}"
        )
        try:
            if self._driver_strategy == "strict_schema":
                response = self._invoke_structured_output_chat(
                    system_prompt=json_system_prompt,
                    user_payload=payload,
                    operation_name=f"playtest_report_{self.persona.persona_id}",
                    capability_context="benchmark_driver.report",
                    stage_source="llm",
                    max_output_tokens=budget_context["report_max_output_tokens"],
                    schema_name="benchmark_report",
                    schema_properties={
                        "ending_id": {"type": "string", "enum": ["collapse", "pyrrhic", "mixed"]},
                        "turn_count": {"type": "integer"},
                        "ratings": {"type": "object"},
                        "flags": {"type": "array"},
                        "strongest_issue": {"type": "string"},
                        "best_moment": {"type": "string"},
                        "verdict": {"type": "string"},
                    },
                    required_fields=["ending_id", "turn_count", "ratings", "flags", "strongest_issue", "best_moment", "verdict"],
                )
            else:
                response = self._invoke_json(
                    system_prompt=json_system_prompt,
                    user_payload=payload,
                    max_output_tokens=budget_context["report_max_output_tokens"],
                    operation_name=f"playtest_report_{self.persona.persona_id}",
                    capability_context="benchmark_driver.report",
                    stage_source="llm",
                )
            if response.fallback_source != "raw_text_passthrough":
                ratings = dict(response.payload.get("ratings") or {})
                flags = [
                    flag
                    for flag in list(response.payload.get("flags") or [])
                    if flag in {"flat_state_feedback", "late_game_flatness", "player_identity_confusion", "templated_opening"}
                ]
                report_stage1_success = True
                normalized = _normalize_agent_report(
                    report={
                        "ending_id": str(response.payload.get("ending_id") or ((final_snapshot.get("ending") or {}).get("ending_id") or "unfinished")),
                        "turn_count": int(response.payload.get("turn_count") or final_snapshot.get("turn_index") or len(turns)),
                        "ratings": {
                            "narration_coherence": int(ratings.get("narration_coherence") or 3),
                            "suggested_action_relevance": int(ratings.get("suggested_action_relevance") or 3),
                            "state_feedback_credibility": int(ratings.get("state_feedback_credibility") or 3),
                            "ending_satisfaction": int(ratings.get("ending_satisfaction") or 3),
                            "overall_player_feel": int(ratings.get("overall_player_feel") or 3),
                            "protagonist_identity_clarity": int(ratings.get("protagonist_identity_clarity") or 3),
                            "content_richness": int(ratings.get("content_richness") or 3),
                            "state_feedback_distinctness": int(ratings.get("state_feedback_distinctness") or ratings.get("state_feedback_credibility") or 3),
                        },
                        "flags": flags,
                        "strongest_issue": str(response.payload.get("strongest_issue") or "No dominant issue reported."),
                        "best_moment": str(response.payload.get("best_moment") or "No clear peak moment reported."),
                        "verdict": str(response.payload.get("verdict") or "Playable but needs closer manual review."),
                        "source": "llm",
                    },
                    turns=turns,
                )
                return {
                    **normalized,
                    "report_stage1_success": report_stage1_success,
                    "report_stage2_rescue": report_stage2_rescue,
                }
        except _PlaytestAgentError:
            pass
        try:
            response = self._invoke_json(
                system_prompt=compact_system_prompt,
                user_payload=payload,
                max_output_tokens=budget_context["report_stage2_max_output_tokens"],
                operation_name=f"playtest_report_{self.persona.persona_id}_compact",
                capability_context="benchmark_driver.report",
                stage_source="llm_salvage",
                record_passthrough_as_invalid_json=False,
            )
            salvaged = _salvage_report_from_raw_text(
                raw_text=response.raw_text or json.dumps(response.payload, ensure_ascii=False),
                opening=opening,
                turns=turns,
                final_snapshot=final_snapshot,
                forced_stop=forced_stop,
            )
            if salvaged is not None:
                for key, value in dict(salvaged.get("missing_field_distribution") or {}).items():
                    self.report_missing_field_distribution[key] = self.report_missing_field_distribution.get(key, 0) + int(value)
                report_stage2_rescue = True
                return {
                    **salvaged,
                    "report_stage1_success": report_stage1_success,
                    "report_stage2_rescue": report_stage2_rescue,
                }
        except _PlaytestAgentError:
            pass
        fallback = _deterministic_report_fallback(
            opening=opening,
            turns=turns,
            final_snapshot=final_snapshot,
            forced_stop=forced_stop,
        )
        return {
            **fallback,
            "report_stage1_success": report_stage1_success,
            "report_stage2_rescue": report_stage2_rescue,
        }


def _create_story_preview(session: requests.Session, base_url: str, prompt_seed: str) -> tuple[dict[str, Any], float]:
    return _create_story_preview_with_controls(session, base_url, prompt_seed, target_duration_minutes=None)


def _create_story_spark(
    session: requests.Session,
    base_url: str,
    *,
    language: str,
) -> tuple[dict[str, Any], float]:
    return _request_json(
        session,
        "POST",
        f"{base_url}/author/story-seeds/spark",
        json={"language": language},
    )


def _create_story_preview_with_controls(
    session: requests.Session,
    base_url: str,
    prompt_seed: str,
    *,
    target_duration_minutes: int | None,
    language: str | None = None,
) -> tuple[dict[str, Any], float]:
    payload: dict[str, Any] = {"prompt_seed": prompt_seed}
    if target_duration_minutes is not None:
        payload["target_duration_minutes"] = target_duration_minutes
    if language is not None:
        payload["language"] = language
    return _request_json(
        session,
        "POST",
        f"{base_url}/author/story-previews",
        json=payload,
    )


def _create_author_job(session: requests.Session, base_url: str, prompt_seed: str, preview_id: str) -> tuple[dict[str, Any], float]:
    return _create_author_job_with_controls(
        session,
        base_url,
        prompt_seed,
        preview_id,
        target_duration_minutes=None,
    )


def _create_author_job_with_controls(
    session: requests.Session,
    base_url: str,
    prompt_seed: str,
    preview_id: str,
    *,
    target_duration_minutes: int | None,
    language: str | None = None,
) -> tuple[dict[str, Any], float]:
    payload: dict[str, Any] = {"prompt_seed": prompt_seed, "preview_id": preview_id}
    if target_duration_minutes is not None:
        payload["target_duration_minutes"] = target_duration_minutes
    if language is not None:
        payload["language"] = language
    return _request_json(
        session,
        "POST",
        f"{base_url}/author/jobs",
        json=payload,
    )


def _get_author_job_result(session: requests.Session, base_url: str, job_id: str) -> tuple[dict[str, Any], float]:
    return _request_json(session, "GET", f"{base_url}/author/jobs/{job_id}/result")


def _get_author_job(session: requests.Session, base_url: str, job_id: str) -> tuple[dict[str, Any], float]:
    return _request_json(session, "GET", f"{base_url}/author/jobs/{job_id}")


def _publish_author_job(session: requests.Session, base_url: str, job_id: str) -> tuple[dict[str, Any], float]:
    return _request_json(
        session,
        "POST",
        f"{base_url}/author/jobs/{job_id}/publish",
        params={"visibility": "public"},
    )


def _get_story_detail(session: requests.Session, base_url: str, story_id: str) -> tuple[dict[str, Any], float]:
    return _request_json(session, "GET", f"{base_url}/stories/{story_id}")


def _get_author_diagnostics(session: requests.Session, base_url: str, job_id: str) -> tuple[dict[str, Any], float]:
    return _request_json(session, "GET", f"{base_url}/benchmark/author/jobs/{job_id}/diagnostics")


def _create_play_session(session: requests.Session, base_url: str, story_id: str) -> tuple[dict[str, Any], float]:
    return _request_json(session, "POST", f"{base_url}/play/sessions", json={"story_id": story_id})


def _submit_play_turn(session: requests.Session, base_url: str, session_id: str, input_text: str) -> tuple[dict[str, Any], float]:
    return _request_json(
        session,
        "POST",
        f"{base_url}/play/sessions/{session_id}/turns",
        json={"input_text": input_text},
    )


def _get_play_diagnostics(session: requests.Session, base_url: str, session_id: str) -> tuple[dict[str, Any], float]:
    return _request_json(session, "GET", f"{base_url}/benchmark/play/sessions/{session_id}/diagnostics")


def _is_transient_benchmark_error(message: str | None) -> bool:
    if not message:
        return False
    lowered = message.casefold()
    transient_markers = (
        "timeout",
        "timed out",
        "connection reset",
        "connection aborted",
        "temporarily unavailable",
        "bad gateway",
        "service unavailable",
        "expecting value",
        "expecting property name enclosed in double quotes",
        "provider_failed",
    )
    return any(marker in lowered for marker in transient_markers)


def _run_author_story(
    *,
    session: requests.Session,
    base_url: str,
    generated_seed: GeneratedStorySeed,
    target_duration_minutes: int | None,
) -> dict[str, Any]:
    seed_started_at = time.perf_counter()
    story_payload: dict[str, Any] = {
        "bucket_id": generated_seed.bucket_id,
        "slug": generated_seed.slug,
        "seed": generated_seed.seed,
        "generated_at": generated_seed.generated_at,
        "job_id": None,
        "preview": None,
        "stream": None,
        "result": None,
        "diagnostics": None,
        "published_story": None,
        "story_detail": None,
        "error": None,
        "timings": {
            "author_total_elapsed_seconds": round(time.perf_counter() - seed_started_at, 3),
        },
    }
    try:
        _authenticate_session(session, base_url, label=f"author-{generated_seed.slug}")
        preview, preview_elapsed_seconds = _create_story_preview_with_controls(
            session,
            base_url,
            generated_seed.seed,
            target_duration_minutes=target_duration_minutes,
        )
        job, create_job_elapsed_seconds = _create_author_job_with_controls(
            session,
            base_url,
            generated_seed.seed,
            str(preview["preview_id"]),
            target_duration_minutes=target_duration_minutes,
        )
        job_id = str(job["job_id"])
        stream_result = _stream_author_job_to_terminal(session, base_url, job_id)
        result, result_elapsed_seconds = _get_author_job_result(session, base_url, job_id)
        diagnostics, diagnostics_elapsed_seconds = _get_author_diagnostics(session, base_url, job_id)
        story_payload.update(
            {
                "job_id": job_id,
                "preview": preview,
                "stream": stream_result,
                "result": result,
                "diagnostics": diagnostics,
            }
        )
        story_payload["timings"].update(
            {
                "preview_elapsed_seconds": preview_elapsed_seconds,
                "create_job_elapsed_seconds": create_job_elapsed_seconds,
                "get_result_elapsed_seconds": result_elapsed_seconds,
                "get_diagnostics_elapsed_seconds": diagnostics_elapsed_seconds,
            }
        )
        if result.get("status") != "completed":
            story_payload["timings"]["author_total_elapsed_seconds"] = round(time.perf_counter() - seed_started_at, 3)
            return story_payload
        published_story, publish_elapsed_seconds = _publish_author_job(session, base_url, job_id)
        story_detail, detail_elapsed_seconds = _get_story_detail(session, base_url, str(published_story["story_id"]))
        story_payload["published_story"] = published_story
        story_payload["story_detail"] = story_detail
        story_payload["timings"]["publish_elapsed_seconds"] = publish_elapsed_seconds
        story_payload["timings"]["get_story_detail_elapsed_seconds"] = detail_elapsed_seconds
    except Exception as exc:  # noqa: BLE001
        story_payload["error"] = str(exc)
    story_payload["timings"]["author_total_elapsed_seconds"] = round(time.perf_counter() - seed_started_at, 3)
    return story_payload


def _story_instance_metrics(quality_trace: list[dict[str, Any]] | None) -> dict[str, int]:
    trace = list(quality_trace or [])
    return {
        "story_instance_materialized_count": sum(
            1
            for item in trace
            if item.get("stage") == "cast_member" and "story_instance_materialized" in list(item.get("reasons") or [])
        ),
        "story_instance_fallback_count": sum(
            1
            for item in trace
            if item.get("stage") == "cast_member" and "story_instance_fallback" in list(item.get("reasons") or [])
        ),
        "gender_lock_violation_count": sum(
            1
            for item in trace
            if item.get("stage") == "cast_member" and "story_instance_gender_lock_violation" in list(item.get("reasons") or [])
        ),
    }


def _selected_roster_templates(roster_retrieval_trace: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in list(roster_retrieval_trace or []):
        character_id = str(item.get("selected_character_id") or "").strip()
        template_version = str(item.get("selected_template_version") or "").strip()
        if not character_id:
            continue
        key = (character_id, template_version)
        if key in seen:
            continue
        seen.add(key)
        selected.append(
            {
                "character_id": character_id,
                "template_version": template_version or None,
            }
        )
    return selected


def _lane_matches_preview(preview: dict[str, Any], *, target_duration_minutes: int) -> bool:
    story_flow_plan = dict(preview.get("story_flow_plan") or {})
    structure = dict(preview.get("structure") or {})
    if int(story_flow_plan.get("target_duration_minutes") or 0) != int(target_duration_minutes):
        return False
    return all(
        int(value or 0) > 0
        for value in (
            story_flow_plan.get("target_turn_count"),
            story_flow_plan.get("target_beat_count"),
            structure.get("expected_npc_count"),
        )
    )


def _run_stage1_smoke_language(
    *,
    session: requests.Session,
    base_url: str,
    language: str,
    target_duration_minutes: int,
    transport_style: TransportStyle,
    use_helper_agent: bool,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "language": language,
        "target_duration_minutes": target_duration_minutes,
        "spark": None,
        "preview": None,
        "author": None,
        "publish": None,
        "play": None,
        "passed": False,
        "failure_stage": None,
        "error": None,
    }
    try:
        _authenticate_session(session, base_url, label=f"stage1-smoke-{language}")
        record["failure_stage"] = "spark"
        spark, spark_elapsed_seconds = _create_story_spark(session, base_url, language=language)
        record["spark"] = {
            "language": language,
            "prompt_seed": spark.get("prompt_seed"),
            "elapsed_seconds": spark_elapsed_seconds,
        }
        record["failure_stage"] = "preview"
        preview, preview_elapsed_seconds = _create_story_preview_with_controls(
            session,
            base_url,
            str(spark["prompt_seed"]),
            target_duration_minutes=target_duration_minutes,
            language=language,
        )
        record["preview"] = {
            "preview_id": preview.get("preview_id"),
            "primary_theme": (preview.get("theme") or {}).get("primary_theme"),
            "strategies": dict(preview.get("strategies") or {}),
            "story_flow_plan": dict(preview.get("story_flow_plan") or {}),
            "structure": dict(preview.get("structure") or {}),
            "elapsed_seconds": preview_elapsed_seconds,
            "lane_matches": _lane_matches_preview(preview, target_duration_minutes=target_duration_minutes),
        }
        if not record["preview"]["lane_matches"]:
            record["failure_stage"] = "preview"
            record["error"] = "preview lane mismatch"
            return record

        record["failure_stage"] = "author_job"
        job, create_job_elapsed_seconds = _create_author_job_with_controls(
            session,
            base_url,
            str(spark["prompt_seed"]),
            str(preview["preview_id"]),
            target_duration_minutes=target_duration_minutes,
            language=language,
        )
        job_id = str(job["job_id"])
        stream = _stream_author_job_to_terminal(session, base_url, job_id)
        job_status, job_status_elapsed_seconds = _get_author_job(session, base_url, job_id)
        result, result_elapsed_seconds = _get_author_job_result(session, base_url, job_id)
        diagnostics, diagnostics_elapsed_seconds = _get_author_diagnostics(session, base_url, job_id)
        story_instance_metrics = _story_instance_metrics(list(diagnostics.get("quality_trace") or []))
        record["author"] = {
            "job_id": job_id,
            "result_status": result.get("status"),
            "progress_snapshot": job_status.get("progress_snapshot"),
            "create_job_elapsed_seconds": create_job_elapsed_seconds,
            "stream_elapsed_seconds": stream.get("stream_elapsed_seconds"),
            "job_status_elapsed_seconds": job_status_elapsed_seconds,
            "result_elapsed_seconds": result_elapsed_seconds,
            "diagnostics_elapsed_seconds": diagnostics_elapsed_seconds,
            "author_total_elapsed_seconds": round(
                create_job_elapsed_seconds
                + float(stream.get("stream_elapsed_seconds") or 0.0)
                + result_elapsed_seconds
                + diagnostics_elapsed_seconds,
                3,
            ),
            "llm_call_trace_len": len(list(diagnostics.get("llm_call_trace") or [])),
            "quality_trace_len": len(list(diagnostics.get("quality_trace") or [])),
            "roster_retrieval_trace": list(diagnostics.get("roster_retrieval_trace") or []),
            **story_instance_metrics,
        }
        if result.get("status") != "completed":
            record["failure_stage"] = "author_job"
            record["error"] = str((diagnostics.get("error") or {}).get("message") or "author job did not complete")
            return record

        record["failure_stage"] = "publish"
        published_story, publish_elapsed_seconds = _publish_author_job(session, base_url, job_id)
        story_detail, detail_elapsed_seconds = _get_story_detail(session, base_url, str(published_story["story_id"]))
        record["publish"] = {
            "story_id": published_story.get("story_id"),
            "title": published_story.get("title"),
            "publish_elapsed_seconds": publish_elapsed_seconds,
            "detail_elapsed_seconds": detail_elapsed_seconds,
            "selected_roster_templates": _selected_roster_templates(record["author"]["roster_retrieval_trace"]),
        }

        record["failure_stage"] = "turn_probe"
        probes = _run_story_turn_proposal_probes(
            base_url=base_url,
            story_detail=story_detail,
            transport_style=transport_style,
            use_helper_agent=use_helper_agent,
        )
        sessions = _run_story_playtests(
            base_url=base_url,
            story_detail=story_detail,
            max_turns=STAGE1_SMOKE_TURN_COUNT,
            transport_style=transport_style,
            use_helper_agent=use_helper_agent,
        )
        persona_results: list[dict[str, Any]] = []
        for probe, session_result in zip(probes, sessions, strict=False):
            diagnostics_summary = dict((session_result.get("diagnostics") or {}).get("summary") or {})
            persona_results.append(
                {
                    "persona_id": probe.get("persona_id") or session_result.get("persona_id"),
                    "propose_turn_elapsed_seconds": probe.get("propose_turn_elapsed_seconds"),
                    "input_text": ((probe.get("proposed_turn") or {}).get("input_text")),
                    "input_text_clean": _proposal_text_is_clean((probe.get("proposed_turn") or {}).get("input_text")),
                    "agent_call_trace": list(probe.get("agent_call_trace") or []),
                    "agent_error_distribution": dict(probe.get("agent_error_distribution") or {}),
                    "turn_count": len(list(session_result.get("turns") or [])),
                    "first_two_turns_success": (
                        not session_result.get("error")
                        and len(list(session_result.get("turns") or [])) == STAGE1_SMOKE_TURN_COUNT
                    ),
                    "render_source_distribution": diagnostics_summary.get("render_source_distribution") or {},
                    "render_fallback_turn_count": diagnostics_summary.get("render_fallback_turn_count"),
                    "error": session_result.get("error") or probe.get("error"),
                }
            )
        play_passed = (
            len(persona_results) == len(PERSONAS)
            and all(item.get("input_text") for item in persona_results)
            and all(bool(item.get("agent_call_trace")) for item in persona_results)
            and all(bool(item.get("input_text_clean")) for item in persona_results)
            and all(bool(item.get("first_two_turns_success")) for item in persona_results)
            and all(not item.get("error") for item in persona_results)
        )
        record["play"] = {
            "personas": persona_results,
            "passed": play_passed,
        }
        if not play_passed:
            record["failure_stage"] = next(
                (
                    "play_turn"
                    if "/play/sessions/" in str(item.get("error") or "") and "/turns" in str(item.get("error") or "")
                    else "play_create"
                    if "/play/sessions" in str(item.get("error") or "")
                    else "turn_probe"
                    for item in persona_results
                    if item.get("error")
                    or not item.get("input_text")
                    or not item.get("input_text_clean")
                    or not item.get("first_two_turns_success")
                    or not item.get("agent_call_trace")
                ),
                "play_turn",
            )
            record["error"] = next(
                (
                    str(item.get("error") or "stage1 smoke play checks failed")
                    for item in persona_results
                    if item.get("error")
                    or not item.get("input_text")
                    or not item.get("input_text_clean")
                    or not item.get("first_two_turns_success")
                    or not item.get("agent_call_trace")
                ),
                "stage1 smoke play checks failed",
            )
            return record
        record["failure_stage"] = None
        record["passed"] = True
        return record
    except Exception as exc:  # noqa: BLE001
        record["error"] = str(exc)
        return record


def _run_persona_story_session(
    *,
    base_url: str,
    story_detail: dict[str, Any],
    persona: AgentPersona,
    max_turns: int,
    transport_style: TransportStyle,
    use_helper_agent: bool,
    use_helper_turn_agent: bool | None = None,
    use_helper_judge: bool | None = None,
    enable_strategy_cache: bool = False,
) -> dict[str, Any]:
    session = requests.Session()
    proposal_agent: PlaytestAgentClient | None = None
    judge_agent: PlaytestAgentClient | None = None
    proposal_uses_helper, judge_uses_helper = _resolve_helper_agent_roles(
        use_helper_agent=use_helper_agent,
        use_helper_turn_agent=use_helper_turn_agent,
        use_helper_judge=use_helper_judge,
    )
    story_id = str((story_detail.get("story") or {}).get("story_id") or "")
    story_title = str((story_detail.get("story") or {}).get("title") or "")
    story_language = str((story_detail.get("story") or {}).get("language") or "en")
    try:
        _authenticate_session(
            session,
            base_url,
            label=f"{persona.persona_id}-{story_id[:8]}",
        )
        proposal_agent = PlaytestAgentClient(
            persona,
            transport_style=transport_style,
            provider="helper" if proposal_uses_helper else "primary",
            enable_strategy_cache=enable_strategy_cache,
        )
        judge_agent = PlaytestAgentClient(
            persona,
            transport_style=transport_style,
            provider="helper" if judge_uses_helper else "primary",
            enable_strategy_cache=enable_strategy_cache,
        )
        created_snapshot, create_elapsed_seconds = _create_play_session(session, base_url, story_id)
        session_id = str(created_snapshot["session_id"])
        opening = str(created_snapshot.get("narration") or "")
        transcript = [{"speaker": "gm", "text": opening}]
        turn_records: list[dict[str, Any]] = []
        snapshot = created_snapshot
        forced_stop = False
        for _ in range(max_turns):
            if snapshot.get("status") != "active":
                break
            proposed = proposal_agent.propose_turn(
                story_detail=story_detail,
                snapshot=snapshot,
                transcript=transcript,
            )
            next_snapshot, submit_elapsed_seconds = _submit_play_turn(
                session,
                base_url,
                session_id,
                str(proposed["input_text"]),
            )
            narration = str(next_snapshot.get("narration") or "")
            transcript.append({"speaker": "player", "text": str(proposed["input_text"])})
            transcript.append({"speaker": "gm", "text": narration})
            turn_records.append(
                {
                    "input_text": str(proposed["input_text"]),
                    "agent_turn_source": proposed["source"],
                    "agent_turn_attempt": proposed["attempt"],
                    "move_family": proposed.get("move_family"),
                    "turn_stage1_success_count": proposed.get("turn_stage1_success_count", 0),
                    "turn_stage2_rescue_count": proposed.get("turn_stage2_rescue_count", 0),
                    "submit_elapsed_seconds": submit_elapsed_seconds,
                    "status": next_snapshot.get("status"),
                    "beat_index": next_snapshot.get("beat_index"),
                    "beat_title": next_snapshot.get("beat_title"),
                    "narration": narration,
                    "feedback": next_snapshot.get("feedback"),
                    "suggested_actions": next_snapshot.get("suggested_actions"),
                    "state_bars": next_snapshot.get("state_bars"),
                    "ending": next_snapshot.get("ending"),
                    "turn_index": next_snapshot.get("turn_index"),
                    "narration_word_count": _word_count(narration),
                }
            )
            snapshot = next_snapshot
        if snapshot.get("status") == "active":
            forced_stop = True
        diagnostics, diagnostics_elapsed_seconds = _get_play_diagnostics(session, base_url, session_id)
        report = judge_agent.build_report(
            story_detail=story_detail,
            opening=opening,
            turns=turn_records,
            final_snapshot=snapshot,
            forced_stop=forced_stop,
        )
        proposal_agent_call_trace = list(proposal_agent.call_trace)
        judge_agent_call_trace = list(judge_agent.call_trace)
        combined_agent_call_trace = proposal_agent_call_trace + judge_agent_call_trace
        agent_cache_metrics = summarize_cache_metrics(combined_agent_call_trace)
        agent_cost_estimate = estimate_token_cost(agent_cache_metrics)
        proposal_agent_provider = _effective_agent_provider(
            proposal_agent,
            requested_helper=proposal_uses_helper,
        )
        judge_agent_provider = _effective_agent_provider(
            judge_agent,
            requested_helper=judge_uses_helper,
        )
        proposal_agent_error_distribution = dict(proposal_agent.error_distribution)
        judge_agent_error_distribution = dict(judge_agent.error_distribution)
        proposal_agent_turn_rejection_distribution = dict(proposal_agent.turn_rejection_distribution)
        judge_agent_report_missing_field_distribution = dict(judge_agent.report_missing_field_distribution)
        budget_context = _benchmark_driver_budget_context(story_detail)
        return {
            "story_id": story_id,
            "story_title": story_title,
            "story_language": story_language,
            "persona_id": persona.persona_id,
            "persona_label": persona.label,
            "session_id": session_id,
            "turn_budget": max_turns,
            "turn_budget_utilization": round(
                min(float(snapshot.get("turn_index") or len(turn_records)), float(max_turns)) / float(max_turns),
                3,
            ) if max_turns else 0.0,
            "create_elapsed_seconds": create_elapsed_seconds,
            "forced_stop": forced_stop,
            "opening": opening,
            "final_snapshot": snapshot,
            "turns": turn_records,
            "feedback_metrics": _session_feedback_metrics(turn_records),
            "late_half_feedback_metrics": _session_feedback_metrics(_late_half_turns(turn_records)),
            "diagnostics": diagnostics,
            "diagnostics_elapsed_seconds": diagnostics_elapsed_seconds,
            "agent_report": report,
            "agent_cache_metrics": agent_cache_metrics.model_dump(mode="json"),
            "agent_cost_estimate": agent_cost_estimate.model_dump(mode="json") if agent_cost_estimate else None,
            "proposal_agent_provider": proposal_agent_provider,
            "judge_agent_provider": judge_agent_provider,
            "agent_provider_mode": "shared" if proposal_agent_provider == judge_agent_provider else "split",
            "proposal_agent_call_trace": proposal_agent_call_trace,
            "judge_agent_call_trace": judge_agent_call_trace,
            "agent_call_trace": combined_agent_call_trace,
            "proposal_agent_error_distribution": proposal_agent_error_distribution,
            "judge_agent_error_distribution": judge_agent_error_distribution,
            "agent_error_distribution": _merge_distribution_maps(
                proposal_agent_error_distribution,
                judge_agent_error_distribution,
            ),
            "proposal_agent_turn_rejection_distribution": proposal_agent_turn_rejection_distribution,
            "agent_turn_rejection_distribution": proposal_agent_turn_rejection_distribution,
            "judge_agent_report_missing_field_distribution": judge_agent_report_missing_field_distribution,
            "agent_report_missing_field_distribution": judge_agent_report_missing_field_distribution,
            "agent_turn_max_output_tokens": budget_context["turn_max_output_tokens"],
            "agent_report_max_output_tokens": budget_context["report_max_output_tokens"],
            "agent_transcript_window_entries": budget_context["transcript_window_entries"],
            "agent_turn_stage1_success_count": sum(int(turn.get("turn_stage1_success_count") or 0) for turn in turn_records),
            "agent_turn_stage2_rescue_count": sum(int(turn.get("turn_stage2_rescue_count") or 0) for turn in turn_records),
            "agent_report_stage1_success": bool(report.get("report_stage1_success")),
            "agent_report_stage2_rescue": bool(report.get("report_stage2_rescue")),
            "proposal_agent_driver_strategy": proposal_agent._driver_strategy,
            "judge_agent_driver_strategy": judge_agent._driver_strategy,
            "agent_driver_strategy": proposal_agent._driver_strategy,
            "agent_provider": proposal_agent_provider,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        proposal_agent_provider = _effective_agent_provider(
            proposal_agent,
            requested_helper=proposal_uses_helper,
        )
        judge_agent_provider = _effective_agent_provider(
            judge_agent,
            requested_helper=judge_uses_helper,
        )
        proposal_agent_call_trace = list(getattr(proposal_agent, "call_trace", []) or [])
        judge_agent_call_trace = list(getattr(judge_agent, "call_trace", []) or [])
        proposal_agent_error_distribution = dict(getattr(proposal_agent, "error_distribution", {}) or {})
        judge_agent_error_distribution = dict(getattr(judge_agent, "error_distribution", {}) or {})
        proposal_agent_turn_rejection_distribution = dict(getattr(proposal_agent, "turn_rejection_distribution", {}) or {})
        judge_agent_report_missing_field_distribution = dict(getattr(judge_agent, "report_missing_field_distribution", {}) or {})
        return {
            "story_id": story_id,
            "story_title": story_title,
            "story_language": story_language,
            "persona_id": persona.persona_id,
            "persona_label": persona.label,
            "session_id": None,
            "turn_budget": max_turns,
            "turn_budget_utilization": 0.0,
            "create_elapsed_seconds": 0.0,
            "forced_stop": False,
            "opening": "",
            "final_snapshot": {"status": "failed", "turn_index": 0, "ending": None},
            "turns": [],
            "feedback_metrics": _session_feedback_metrics([]),
            "late_half_feedback_metrics": _session_feedback_metrics([]),
            "diagnostics": {"summary": {}},
            "diagnostics_elapsed_seconds": 0.0,
            "agent_report": {
                "ending_id": "unfinished",
                "turn_count": 0,
                "ratings": {
                    "narration_coherence": 1,
                    "suggested_action_relevance": 1,
                    "state_feedback_credibility": 1,
                    "ending_satisfaction": 1,
                    "overall_player_feel": 1,
                    "protagonist_identity_clarity": 1,
                    "content_richness": 1,
                    "state_feedback_distinctness": 1,
                },
                "flags": [],
                "strongest_issue": "Benchmark agent session failed before completion.",
                "best_moment": "No clear peak moment reported.",
                "verdict": "Session execution failed.",
                "source": "fallback",
            },
            "agent_cache_metrics": summarize_cache_metrics([]).model_dump(mode="json"),
            "agent_cost_estimate": None,
            "proposal_agent_provider": proposal_agent_provider,
            "judge_agent_provider": judge_agent_provider,
            "agent_provider_mode": "shared" if proposal_agent_provider == judge_agent_provider else "split",
            "proposal_agent_call_trace": proposal_agent_call_trace,
            "judge_agent_call_trace": judge_agent_call_trace,
            "agent_call_trace": proposal_agent_call_trace + judge_agent_call_trace,
            "proposal_agent_error_distribution": proposal_agent_error_distribution,
            "judge_agent_error_distribution": judge_agent_error_distribution,
            "agent_error_distribution": _merge_distribution_maps(
                proposal_agent_error_distribution,
                judge_agent_error_distribution,
            ),
            "proposal_agent_turn_rejection_distribution": proposal_agent_turn_rejection_distribution,
            "agent_turn_rejection_distribution": proposal_agent_turn_rejection_distribution,
            "judge_agent_report_missing_field_distribution": judge_agent_report_missing_field_distribution,
            "agent_report_missing_field_distribution": judge_agent_report_missing_field_distribution,
            "agent_turn_max_output_tokens": 0,
            "agent_report_max_output_tokens": 0,
            "agent_transcript_window_entries": 0,
            "agent_turn_stage1_success_count": 0,
            "agent_turn_stage2_rescue_count": 0,
            "agent_report_stage1_success": False,
            "agent_report_stage2_rescue": False,
            "proposal_agent_driver_strategy": str(getattr(proposal_agent, "_driver_strategy", "fallback")),
            "judge_agent_driver_strategy": str(getattr(judge_agent, "_driver_strategy", "fallback")),
            "agent_driver_strategy": str(getattr(proposal_agent, "_driver_strategy", "fallback")),
            "agent_provider": proposal_agent_provider,
            "error": str(exc),
        }
    finally:
        session.close()


def _run_persona_story_session_with_retry(
    *,
    base_url: str,
    story_detail: dict[str, Any],
    persona: AgentPersona,
    max_turns: int,
    transport_style: TransportStyle,
    use_helper_agent: bool,
    use_helper_turn_agent: bool | None = None,
    use_helper_judge: bool | None = None,
    enable_strategy_cache: bool = False,
) -> dict[str, Any]:
    session_record = _run_persona_story_session(
        base_url=base_url,
        story_detail=story_detail,
        persona=persona,
        max_turns=max_turns,
        transport_style=transport_style,
        use_helper_agent=use_helper_agent,
        use_helper_turn_agent=use_helper_turn_agent,
        use_helper_judge=use_helper_judge,
        enable_strategy_cache=enable_strategy_cache,
    )
    if session_record.get("error") and _is_transient_benchmark_error(str(session_record.get("error"))):
        return _run_persona_story_session(
            base_url=base_url,
            story_detail=story_detail,
            persona=persona,
            max_turns=max_turns,
            transport_style=transport_style,
            use_helper_agent=use_helper_agent,
            use_helper_turn_agent=use_helper_turn_agent,
            use_helper_judge=use_helper_judge,
            enable_strategy_cache=enable_strategy_cache,
        )
    return session_record


def _pending_agent_report(*, final_snapshot: dict[str, Any], turns: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ending_id": str((final_snapshot.get("ending") or {}).get("ending_id") or "unfinished"),
        "turn_count": int(final_snapshot.get("turn_index") or len(turns)),
        "ratings": {
            "narration_coherence": 0,
            "suggested_action_relevance": 0,
            "state_feedback_credibility": 0,
            "ending_satisfaction": 0,
            "overall_player_feel": 0,
            "content_richness": 0,
            "state_feedback_distinctness": 0,
            "protagonist_identity_clarity": 0,
        },
        "flags": [],
        "strongest_issue": "Helper judge pending.",
        "best_moment": "Pending helper judge.",
        "verdict": "Helper judge has not run yet.",
        "source": "pending",
    }


def _proposal_only_session_artifacts(
    *,
    proposal_agent: Any | None,
    proposal_uses_helper: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]], dict[str, int], dict[str, int], str, str]:
    proposal_agent_call_trace = list(getattr(proposal_agent, "call_trace", []) or [])
    proposal_agent_error_distribution = dict(getattr(proposal_agent, "error_distribution", {}) or {})
    proposal_agent_turn_rejection_distribution = dict(getattr(proposal_agent, "turn_rejection_distribution", {}) or {})
    proposal_agent_provider = _effective_agent_provider(
        proposal_agent,
        requested_helper=proposal_uses_helper,
    )
    cache_metrics = summarize_cache_metrics(proposal_agent_call_trace)
    cost_estimate = estimate_token_cost(cache_metrics)
    return (
        cache_metrics.model_dump(mode="json"),
        cost_estimate.model_dump(mode="json") if cost_estimate else None,
        proposal_agent_call_trace,
        proposal_agent_error_distribution,
        proposal_agent_turn_rejection_distribution,
        proposal_agent_provider,
        str(getattr(proposal_agent, "_driver_strategy", "fallback")),
    )


def _capture_session_result(
    *,
    story_id: str,
    story_title: str,
    story_language: str,
    persona: AgentPersona,
    max_turns: int,
    snapshot: dict[str, Any],
    create_elapsed_seconds: float,
    opening: str,
    turn_records: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    diagnostics_elapsed_seconds: float,
    proposal_agent: Any | None,
    proposal_uses_helper: bool,
    judge_requested_helper: bool,
    forced_stop: bool,
    budget_context: dict[str, int],
) -> dict[str, Any]:
    (
        agent_cache_metrics,
        agent_cost_estimate,
        proposal_agent_call_trace,
        proposal_agent_error_distribution,
        proposal_agent_turn_rejection_distribution,
        proposal_agent_provider,
        proposal_agent_driver_strategy,
    ) = _proposal_only_session_artifacts(
        proposal_agent=proposal_agent,
        proposal_uses_helper=proposal_uses_helper,
    )
    judge_agent_provider_requested = _agent_provider_label(use_helper_agent=judge_requested_helper)
    pending_report = _pending_agent_report(final_snapshot=snapshot, turns=turn_records)
    return {
        "story_id": story_id,
        "story_title": story_title,
        "story_language": story_language,
        "persona_id": persona.persona_id,
        "persona_label": persona.label,
        "session_id": str(snapshot.get("session_id") or ""),
        "turn_budget": max_turns,
        "turn_budget_utilization": round(
            min(float(snapshot.get("turn_index") or len(turn_records)), float(max_turns)) / float(max_turns),
            3,
        ) if max_turns else 0.0,
        "create_elapsed_seconds": create_elapsed_seconds,
        "forced_stop": forced_stop,
        "opening": opening,
        "final_snapshot": snapshot,
        "turns": turn_records,
        "feedback_metrics": _session_feedback_metrics(turn_records),
        "late_half_feedback_metrics": _session_feedback_metrics(_late_half_turns(turn_records)),
        "diagnostics": diagnostics,
        "diagnostics_elapsed_seconds": diagnostics_elapsed_seconds,
        "agent_report": pending_report,
        "agent_cache_metrics": agent_cache_metrics,
        "agent_cost_estimate": agent_cost_estimate,
        "proposal_agent_provider": proposal_agent_provider,
        "judge_agent_provider_requested": judge_agent_provider_requested,
        "judge_agent_provider": "pending",
        "agent_provider_mode": "shared" if proposal_agent_provider == judge_agent_provider_requested else "split",
        "proposal_agent_call_trace": proposal_agent_call_trace,
        "judge_agent_call_trace": [],
        "agent_call_trace": list(proposal_agent_call_trace),
        "proposal_agent_error_distribution": proposal_agent_error_distribution,
        "judge_agent_error_distribution": {},
        "agent_error_distribution": dict(proposal_agent_error_distribution),
        "proposal_agent_turn_rejection_distribution": proposal_agent_turn_rejection_distribution,
        "agent_turn_rejection_distribution": dict(proposal_agent_turn_rejection_distribution),
        "judge_agent_report_missing_field_distribution": {},
        "agent_report_missing_field_distribution": {},
        "agent_turn_max_output_tokens": budget_context["turn_max_output_tokens"],
        "agent_report_max_output_tokens": budget_context["report_max_output_tokens"],
        "agent_transcript_window_entries": budget_context["transcript_window_entries"],
        "agent_turn_stage1_success_count": sum(int(turn.get("turn_stage1_success_count") or 0) for turn in turn_records),
        "agent_turn_stage2_rescue_count": sum(int(turn.get("turn_stage2_rescue_count") or 0) for turn in turn_records),
        "agent_report_stage1_success": False,
        "agent_report_stage2_rescue": False,
        "proposal_agent_driver_strategy": proposal_agent_driver_strategy,
        "judge_agent_driver_strategy": "pending",
        "agent_driver_strategy": proposal_agent_driver_strategy,
        "agent_provider": proposal_agent_provider,
        "judge_status": "pending",
        "judge_started_at": None,
        "judge_completed_at": None,
        "judge_elapsed_seconds": None,
        "judge_error": None,
        "error": None,
    }


def _run_persona_story_capture_session(
    *,
    base_url: str,
    story_detail: dict[str, Any],
    persona: AgentPersona,
    max_turns: int,
    transport_style: TransportStyle,
    use_helper_agent: bool,
    use_helper_turn_agent: bool | None = None,
    use_helper_judge: bool | None = None,
    enable_strategy_cache: bool = False,
) -> dict[str, Any]:
    session = requests.Session()
    proposal_agent: PlaytestAgentClient | None = None
    proposal_uses_helper, judge_uses_helper = _resolve_helper_agent_roles(
        use_helper_agent=use_helper_agent,
        use_helper_turn_agent=use_helper_turn_agent,
        use_helper_judge=use_helper_judge,
    )
    story_id = str((story_detail.get("story") or {}).get("story_id") or "")
    story_title = str((story_detail.get("story") or {}).get("title") or "")
    story_language = str((story_detail.get("story") or {}).get("language") or "en")
    budget_context = _benchmark_driver_budget_context(story_detail)
    try:
        _authenticate_session(
            session,
            base_url,
            label=f"{persona.persona_id}-{story_id[:8]}",
        )
        proposal_agent = PlaytestAgentClient(
            persona,
            transport_style=transport_style,
            provider="helper" if proposal_uses_helper else "primary",
            enable_strategy_cache=enable_strategy_cache,
        )
        created_snapshot, create_elapsed_seconds = _create_play_session(session, base_url, story_id)
        session_id = str(created_snapshot["session_id"])
        opening = str(created_snapshot.get("narration") or "")
        transcript = [{"speaker": "gm", "text": opening}]
        turn_records: list[dict[str, Any]] = []
        snapshot = created_snapshot
        forced_stop = False
        for _ in range(max_turns):
            if snapshot.get("status") != "active":
                break
            proposed = proposal_agent.propose_turn(
                story_detail=story_detail,
                snapshot=snapshot,
                transcript=transcript,
            )
            next_snapshot, submit_elapsed_seconds = _submit_play_turn(
                session,
                base_url,
                session_id,
                str(proposed["input_text"]),
            )
            narration = str(next_snapshot.get("narration") or "")
            transcript.append({"speaker": "player", "text": str(proposed["input_text"])})
            transcript.append({"speaker": "gm", "text": narration})
            turn_records.append(
                {
                    "input_text": str(proposed["input_text"]),
                    "agent_turn_source": proposed["source"],
                    "agent_turn_attempt": proposed["attempt"],
                    "move_family": proposed.get("move_family"),
                    "turn_stage1_success_count": proposed.get("turn_stage1_success_count", 0),
                    "turn_stage2_rescue_count": proposed.get("turn_stage2_rescue_count", 0),
                    "submit_elapsed_seconds": submit_elapsed_seconds,
                    "status": next_snapshot.get("status"),
                    "beat_index": next_snapshot.get("beat_index"),
                    "beat_title": next_snapshot.get("beat_title"),
                    "narration": narration,
                    "feedback": next_snapshot.get("feedback"),
                    "suggested_actions": next_snapshot.get("suggested_actions"),
                    "state_bars": next_snapshot.get("state_bars"),
                    "ending": next_snapshot.get("ending"),
                    "turn_index": next_snapshot.get("turn_index"),
                    "narration_word_count": _word_count(narration),
                }
            )
            snapshot = next_snapshot
        if snapshot.get("status") == "active":
            forced_stop = True
        diagnostics, diagnostics_elapsed_seconds = _get_play_diagnostics(session, base_url, session_id)
        capture_result = _capture_session_result(
            story_id=story_id,
            story_title=story_title,
            story_language=story_language,
            persona=persona,
            max_turns=max_turns,
            snapshot=snapshot,
            create_elapsed_seconds=create_elapsed_seconds,
            opening=opening,
            turn_records=turn_records,
            diagnostics=diagnostics,
            diagnostics_elapsed_seconds=diagnostics_elapsed_seconds,
            proposal_agent=proposal_agent,
            proposal_uses_helper=proposal_uses_helper,
            judge_requested_helper=judge_uses_helper,
            forced_stop=forced_stop,
            budget_context=budget_context,
        )
        return capture_result
    except Exception as exc:  # noqa: BLE001
        (
            agent_cache_metrics,
            agent_cost_estimate,
            proposal_agent_call_trace,
            proposal_agent_error_distribution,
            proposal_agent_turn_rejection_distribution,
            proposal_agent_provider,
            proposal_agent_driver_strategy,
        ) = _proposal_only_session_artifacts(
            proposal_agent=proposal_agent,
            proposal_uses_helper=proposal_uses_helper,
        )
        judge_agent_provider_requested = _agent_provider_label(use_helper_agent=judge_uses_helper)
        return {
            "story_id": story_id,
            "story_title": story_title,
            "story_language": story_language,
            "persona_id": persona.persona_id,
            "persona_label": persona.label,
            "session_id": None,
            "turn_budget": max_turns,
            "turn_budget_utilization": 0.0,
            "create_elapsed_seconds": 0.0,
            "forced_stop": False,
            "opening": "",
            "final_snapshot": {"status": "failed", "turn_index": 0, "ending": None},
            "turns": [],
            "feedback_metrics": _session_feedback_metrics([]),
            "late_half_feedback_metrics": _session_feedback_metrics([]),
            "diagnostics": {"summary": {}},
            "diagnostics_elapsed_seconds": 0.0,
            "agent_report": _pending_agent_report(final_snapshot={"ending": None, "turn_index": 0}, turns=[]),
            "agent_cache_metrics": agent_cache_metrics,
            "agent_cost_estimate": agent_cost_estimate,
            "proposal_agent_provider": proposal_agent_provider,
            "judge_agent_provider_requested": judge_agent_provider_requested,
            "judge_agent_provider": "pending",
            "agent_provider_mode": "shared" if proposal_agent_provider == judge_agent_provider_requested else "split",
            "proposal_agent_call_trace": proposal_agent_call_trace,
            "judge_agent_call_trace": [],
            "agent_call_trace": list(proposal_agent_call_trace),
            "proposal_agent_error_distribution": proposal_agent_error_distribution,
            "judge_agent_error_distribution": {},
            "agent_error_distribution": dict(proposal_agent_error_distribution),
            "proposal_agent_turn_rejection_distribution": proposal_agent_turn_rejection_distribution,
            "agent_turn_rejection_distribution": dict(proposal_agent_turn_rejection_distribution),
            "judge_agent_report_missing_field_distribution": {},
            "agent_report_missing_field_distribution": {},
            "agent_turn_max_output_tokens": 0,
            "agent_report_max_output_tokens": 0,
            "agent_transcript_window_entries": 0,
            "agent_turn_stage1_success_count": 0,
            "agent_turn_stage2_rescue_count": 0,
            "agent_report_stage1_success": False,
            "agent_report_stage2_rescue": False,
            "proposal_agent_driver_strategy": proposal_agent_driver_strategy,
            "judge_agent_driver_strategy": "pending",
            "agent_driver_strategy": proposal_agent_driver_strategy,
            "agent_provider": proposal_agent_provider,
            "judge_status": "pending",
            "judge_started_at": None,
            "judge_completed_at": None,
            "judge_elapsed_seconds": None,
            "judge_error": None,
            "error": str(exc),
        }
    finally:
        session.close()


def _run_persona_story_capture_session_with_retry(
    *,
    base_url: str,
    story_detail: dict[str, Any],
    persona: AgentPersona,
    max_turns: int,
    transport_style: TransportStyle,
    use_helper_agent: bool,
    use_helper_turn_agent: bool | None = None,
    use_helper_judge: bool | None = None,
    enable_strategy_cache: bool = False,
) -> dict[str, Any]:
    session_record = _run_persona_story_capture_session(
        base_url=base_url,
        story_detail=story_detail,
        persona=persona,
        max_turns=max_turns,
        transport_style=transport_style,
        use_helper_agent=use_helper_agent,
        use_helper_turn_agent=use_helper_turn_agent,
        use_helper_judge=use_helper_judge,
        enable_strategy_cache=enable_strategy_cache,
    )
    if session_record.get("error") and _is_transient_benchmark_error(str(session_record.get("error"))):
        return _run_persona_story_capture_session(
            base_url=base_url,
            story_detail=story_detail,
            persona=persona,
            max_turns=max_turns,
            transport_style=transport_style,
            use_helper_agent=use_helper_agent,
            use_helper_turn_agent=use_helper_turn_agent,
            use_helper_judge=use_helper_judge,
            enable_strategy_cache=enable_strategy_cache,
        )
    return session_record


def _session_with_judge_result(
    session: dict[str, Any],
    *,
    judge_agent: Any | None,
    judge_requested_helper: bool,
    report: dict[str, Any],
    judge_status: str,
    judge_error: str | None,
    judge_started_at: str | None,
    judge_completed_at: str | None,
    judge_elapsed_seconds: float | None,
) -> dict[str, Any]:
    updated = dict(session)
    proposal_agent_call_trace = list(updated.get("proposal_agent_call_trace") or [])
    judge_agent_call_trace = list(getattr(judge_agent, "call_trace", []) or [])
    proposal_agent_error_distribution = dict(updated.get("proposal_agent_error_distribution") or {})
    judge_agent_error_distribution = dict(getattr(judge_agent, "error_distribution", {}) or {})
    judge_agent_report_missing_field_distribution = dict(getattr(judge_agent, "report_missing_field_distribution", {}) or {})
    judge_agent_provider = _effective_agent_provider(
        judge_agent,
        requested_helper=judge_requested_helper,
    ) if judge_status != "pending" else "pending"
    combined_call_trace = proposal_agent_call_trace + judge_agent_call_trace
    cache_metrics = summarize_cache_metrics(combined_call_trace)
    cost_estimate = estimate_token_cost(cache_metrics)
    updated["agent_report"] = report
    updated["judge_agent_provider"] = judge_agent_provider
    updated["agent_provider_mode"] = "shared" if str(updated.get("proposal_agent_provider") or "") == judge_agent_provider else "split"
    updated["judge_agent_call_trace"] = judge_agent_call_trace
    updated["agent_call_trace"] = combined_call_trace
    updated["judge_agent_error_distribution"] = judge_agent_error_distribution
    updated["agent_error_distribution"] = _merge_distribution_maps(
        proposal_agent_error_distribution,
        judge_agent_error_distribution,
    )
    updated["judge_agent_report_missing_field_distribution"] = judge_agent_report_missing_field_distribution
    updated["agent_report_missing_field_distribution"] = judge_agent_report_missing_field_distribution
    updated["agent_cache_metrics"] = cache_metrics.model_dump(mode="json")
    updated["agent_cost_estimate"] = cost_estimate.model_dump(mode="json") if cost_estimate else None
    updated["judge_status"] = judge_status
    updated["judge_started_at"] = judge_started_at
    updated["judge_completed_at"] = judge_completed_at
    updated["judge_elapsed_seconds"] = judge_elapsed_seconds
    updated["judge_error"] = judge_error
    updated["judge_agent_driver_strategy"] = str(getattr(judge_agent, "_driver_strategy", "fallback")) if judge_status != "pending" else "pending"
    updated["agent_report_stage1_success"] = bool(report.get("report_stage1_success")) if judge_status == "completed" else False
    updated["agent_report_stage2_rescue"] = bool(report.get("report_stage2_rescue")) if judge_status == "completed" else False
    return updated


def _judge_play_only_session(
    *,
    story_detail: dict[str, Any],
    session: dict[str, Any],
    transport_style: TransportStyle,
    enable_strategy_cache: bool,
) -> dict[str, Any]:
    persona = next(persona for persona in PERSONAS if persona.persona_id == str(session.get("persona_id") or ""))
    judge_requested_helper = str(session.get("judge_agent_provider_requested") or "primary") == "helper"
    judge_started_at = datetime.now(timezone.utc).isoformat()
    started_at = time.perf_counter()
    judge_agent: PlaytestAgentClient | None = None
    try:
        judge_agent = PlaytestAgentClient(
            persona,
            transport_style=transport_style,
            provider="helper" if judge_requested_helper else "primary",
            enable_strategy_cache=enable_strategy_cache,
        )
        report = judge_agent.build_report(
            story_detail=story_detail,
            opening=str(session.get("opening") or ""),
            turns=list(session.get("turns") or []),
            final_snapshot=dict(session.get("final_snapshot") or {}),
            forced_stop=bool(session.get("forced_stop")),
        )
        return _session_with_judge_result(
            session,
            judge_agent=judge_agent,
            judge_requested_helper=judge_requested_helper,
            report=report,
            judge_status="completed",
            judge_error=None,
            judge_started_at=judge_started_at,
            judge_completed_at=datetime.now(timezone.utc).isoformat(),
            judge_elapsed_seconds=round(time.perf_counter() - started_at, 3),
        )
    except Exception as exc:  # noqa: BLE001
        report = _deterministic_report_fallback(
            opening=str(session.get("opening") or ""),
            turns=list(session.get("turns") or []),
            final_snapshot=dict(session.get("final_snapshot") or {}),
            forced_stop=bool(session.get("forced_stop")),
        )
        return _session_with_judge_result(
            session,
            judge_agent=judge_agent,
            judge_requested_helper=judge_requested_helper,
            report=report,
            judge_status="failed",
            judge_error=str(exc),
            judge_started_at=judge_started_at,
            judge_completed_at=datetime.now(timezone.utc).isoformat(),
            judge_elapsed_seconds=round(time.perf_counter() - started_at, 3),
        )


def _pending_judge_sessions(story_records: list[dict[str, Any]]) -> list[tuple[int, int, dict[str, Any], dict[str, Any]]]:
    pending: list[tuple[int, int, dict[str, Any], dict[str, Any]]] = []
    for story_index, record in enumerate(story_records):
        story_detail = dict(record.get("story_detail") or {})
        for session_index, session in enumerate(list(record.get("sessions") or [])):
            if str(session.get("judge_status") or "pending") != "completed":
                pending.append((story_index, session_index, dict(session), story_detail))
    return pending


def _run_play_only_judge_phase(
    *,
    config: LiveApiPlaytestConfig,
    story_records: list[dict[str, Any]],
    cell_session_counts: dict[str, int],
    completed_turn_count: int,
    checkpoint_json_path: Path,
    checkpoint_md_path: Path,
) -> None:
    pending_sessions = _pending_judge_sessions(story_records)
    if not pending_sessions:
        return
    judged_since_checkpoint = 0
    with ThreadPoolExecutor(max_workers=config.judge_max_workers) as executor:
        futures = {
            executor.submit(
                _judge_play_only_session,
                story_detail=story_detail,
                session=session,
                transport_style=config.agent_transport_style,
                enable_strategy_cache=True,
            ): (story_index, session_index)
            for story_index, session_index, session, story_detail in pending_sessions
        }
        for future in as_completed(futures):
            story_index, session_index = futures[future]
            story_records[story_index]["sessions"][session_index] = future.result()
            judged_since_checkpoint += 1
            if judged_since_checkpoint >= config.checkpoint_every_sessions:
                checkpoint_payload = _build_play_only_campaign_payload(
                    config=config,
                    story_records=story_records,
                    cell_session_counts=cell_session_counts,
                    completed_turn_count=completed_turn_count,
                    checkpoint_path=checkpoint_json_path,
                    resume_from=config.resume_from,
                    run_status="judge_running",
                    capture_status="completed",
                    judge_status="running",
                )
                _write_play_only_checkpoint(
                    path_json=checkpoint_json_path,
                    path_md=checkpoint_md_path,
                    payload=checkpoint_payload,
                )
                judged_since_checkpoint = 0


def _run_story_playtests(
    *,
    base_url: str,
    story_detail: dict[str, Any],
    max_turns: int,
    transport_style: TransportStyle,
    use_helper_agent: bool,
) -> list[dict[str, Any]]:
    with ThreadPoolExecutor(max_workers=len(PERSONAS)) as executor:
        futures = [
            executor.submit(
                _run_persona_story_session_with_retry,
                base_url=base_url,
                story_detail=story_detail,
                persona=persona,
                max_turns=max_turns,
                transport_style=transport_style,
                use_helper_agent=use_helper_agent,
            )
            for persona in PERSONAS
        ]
    return [future.result() for future in futures]


def _probe_persona_turn_proposal(
    *,
    base_url: str,
    story_detail: dict[str, Any],
    persona: AgentPersona,
    transport_style: TransportStyle,
    use_helper_agent: bool,
) -> dict[str, Any]:
    session = requests.Session()
    try:
        _authenticate_session(
            session,
            base_url,
            label=f"{persona.persona_id}-{str(story_detail['story']['story_id'])[:8]}",
        )
        agent = PlaytestAgentClient(
            persona,
            transport_style=transport_style,
            provider="helper" if use_helper_agent else "primary",
        )
        story_id = str(story_detail["story"]["story_id"])
        created_snapshot, create_elapsed_seconds = _create_play_session(session, base_url, story_id)
        opening = str(created_snapshot.get("narration") or "")
        transcript = [{"speaker": "gm", "text": opening}]
        started_at = time.perf_counter()
        try:
            proposed = agent.propose_turn(
                story_detail=story_detail,
                snapshot=created_snapshot,
                transcript=transcript,
            )
            error = None
        except Exception as exc:  # noqa: BLE001
            proposed = None
            error = str(exc)
        propose_turn_elapsed_seconds = round(time.perf_counter() - started_at, 3)
        budget_context = _benchmark_driver_budget_context(story_detail)
        return {
            "persona_id": persona.persona_id,
            "persona_label": persona.label,
            "session_id": str(created_snapshot["session_id"]),
            "create_elapsed_seconds": create_elapsed_seconds,
            "propose_turn_elapsed_seconds": propose_turn_elapsed_seconds,
            "opening": opening,
            "opening_snapshot": {
                "beat_title": str(created_snapshot.get("beat_title") or ""),
                "suggested_actions": list(created_snapshot.get("suggested_actions") or []),
                "state_bars": list(created_snapshot.get("state_bars") or []),
            },
            "proposed_turn": proposed,
            "agent_call_trace": list(agent.call_trace),
            "agent_error_distribution": dict(agent.error_distribution),
            "agent_turn_rejection_distribution": dict(agent.turn_rejection_distribution),
            "agent_driver_strategy": agent._driver_strategy,
            "agent_provider": getattr(agent, "_provider", _agent_provider_label(use_helper_agent=use_helper_agent)),
            "agent_turn_max_output_tokens": budget_context["turn_max_output_tokens"],
            "agent_transcript_window_entries": budget_context["transcript_window_entries"],
            "error": error,
        }
    finally:
        session.close()


def _run_story_turn_proposal_probes(
    *,
    base_url: str,
    story_detail: dict[str, Any],
    transport_style: TransportStyle,
    use_helper_agent: bool,
) -> list[dict[str, Any]]:
    with ThreadPoolExecutor(max_workers=len(PERSONAS)) as executor:
        futures = [
            executor.submit(
                _probe_persona_turn_proposal,
                base_url=base_url,
                story_detail=story_detail,
                persona=persona,
                transport_style=transport_style,
                use_helper_agent=use_helper_agent,
            )
            for persona in PERSONAS
        ]
    return [future.result() for future in futures]


def _agent_provider_label(*, use_helper_agent: bool) -> str:
    return "helper" if use_helper_agent else "primary"


def _resolve_helper_agent_roles(
    *,
    use_helper_agent: bool,
    use_helper_turn_agent: bool | None = None,
    use_helper_judge: bool | None = None,
) -> tuple[bool, bool]:
    proposal_uses_helper = bool(use_helper_agent or use_helper_turn_agent)
    judge_uses_helper = bool(use_helper_agent or use_helper_judge)
    return proposal_uses_helper, judge_uses_helper


def _effective_agent_provider(agent: Any | None, *, requested_helper: bool) -> str:
    if agent is None:
        return _agent_provider_label(use_helper_agent=requested_helper)
    return str(getattr(agent, "_provider", _agent_provider_label(use_helper_agent=requested_helper)))


def _require_helper_agent_if_requested(
    *,
    use_helper_agent: bool = False,
    use_helper_turn_agent: bool = False,
    use_helper_judge: bool = False,
) -> None:
    proposal_uses_helper, judge_uses_helper = _resolve_helper_agent_roles(
        use_helper_agent=use_helper_agent,
        use_helper_turn_agent=use_helper_turn_agent,
        use_helper_judge=use_helper_judge,
    )
    if (proposal_uses_helper or judge_uses_helper) and not helper_gateway_config_available():
        raise RuntimeError(
            "helper agent mode requires APP_HELPER_GATEWAY_BASE_URL, "
            "APP_HELPER_GATEWAY_API_KEY, and APP_HELPER_GATEWAY_MODEL"
        )


def _resolve_story_turn_budget(story_detail: dict[str, Any], hard_cap: int | None) -> int:
    play_overview = dict(story_detail.get("play_overview") or {})
    story_max_turns = int(play_overview.get("max_turns") or 0)
    if story_max_turns <= 0:
        story_max_turns = 6
    if hard_cap is None:
        return story_max_turns
    return max(min(story_max_turns, int(hard_cap)), 1)


def _accumulate_distribution(total: dict[str, int], values: dict[str, int]) -> None:
    for key, value in values.items():
        total[str(key)] = total.get(str(key), 0) + int(value)


def _merge_distribution_maps(*values: dict[str, int]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for value in values:
        _accumulate_distribution(merged, value)
    return merged


def _axis_diversity_per_session(sessions: list[dict[str, Any]]) -> float:
    values: list[int] = []
    for session in sessions:
        axis_ids = {
            axis_id
            for turn in session.get("turns", [])
            for axis_id, delta in dict((turn.get("feedback") or {}).get("last_turn_axis_deltas") or {}).items()
            if int(delta) != 0
        }
        if axis_ids:
            values.append(len(axis_ids))
    return round(statistics.mean(values), 3) if values else 0.0


def _stance_target_diversity_per_session(sessions: list[dict[str, Any]]) -> float:
    values: list[int] = []
    for session in sessions:
        stance_ids = {
            stance_id
            for turn in session.get("turns", [])
            for stance_id, delta in dict((turn.get("feedback") or {}).get("last_turn_stance_deltas") or {}).items()
            if int(delta) != 0
        }
        if stance_ids:
            values.append(len(stance_ids))
    return round(statistics.mean(values), 3) if values else 0.0


def _late_half_axis_diversity_per_session(sessions: list[dict[str, Any]]) -> float:
    values = [
        int((session.get("late_half_feedback_metrics") or {}).get("distinct_axis_count") or 0)
        for session in sessions
        if session.get("late_half_feedback_metrics")
    ]
    return round(statistics.mean(values), 3) if values else 0.0


def _late_half_stance_target_diversity_per_session(sessions: list[dict[str, Any]]) -> float:
    values = [
        int((session.get("late_half_feedback_metrics") or {}).get("distinct_stance_count") or 0)
        for session in sessions
        if session.get("late_half_feedback_metrics")
    ]
    return round(statistics.mean(values), 3) if values else 0.0


def _average_report_rating(sessions: list[dict[str, Any]], key: str) -> float:
    values = [
        int((session.get("agent_report", {}).get("ratings") or {}).get(key) or 0)
        for session in sessions
        if session.get("agent_report")
    ]
    return round(statistics.mean(values), 3) if values else 0.0


def _cost_rmb_to_usd(value_rmb: float) -> float:
    return round(float(value_rmb) * get_settings().responses_usd_per_rmb, 6)


def _estimate_usage_cost_from_totals(usage_totals: dict[str, int]) -> dict[str, float]:
    metrics = AuthorCacheMetrics(
        session_cache_enabled=bool(
            int(usage_totals.get("cached_input_tokens") or 0) > 0
            or int(usage_totals.get("cache_creation_input_tokens") or 0) > 0
        ),
        cache_path_used=False,
        total_call_count=0,
        previous_response_call_count=0,
        total_input_characters=0,
        estimated_input_tokens_from_chars=0,
        provider_usage={str(key): int(value) for key, value in usage_totals.items()},
        input_tokens=int(usage_totals.get("input_tokens") or 0),
        output_tokens=int(usage_totals.get("output_tokens") or 0),
        total_tokens=int(usage_totals.get("total_tokens") or 0) or None,
        reasoning_tokens=int(usage_totals.get("reasoning_tokens") or 0) or None,
        cached_input_tokens=int(usage_totals.get("cached_input_tokens") or 0) or None,
        cache_hit_tokens=int(usage_totals.get("cache_hit_tokens") or 0) or None,
        cache_write_tokens=int(usage_totals.get("cache_write_tokens") or 0) or None,
        cache_creation_input_tokens=int(usage_totals.get("cache_creation_input_tokens") or 0) or None,
        cache_metrics_source="benchmark_usage_totals",
    )
    estimate = estimate_token_cost(metrics)
    if estimate is None:
        return {"rmb": 0.0, "usd": 0.0}
    total_rmb = round(float(estimate.estimated_total_cost_rmb), 6)
    return {"rmb": total_rmb, "usd": _cost_rmb_to_usd(total_rmb)}


def _completed_sessions_only(all_sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        session
        for session in all_sessions
        if session.get("final_snapshot", {}).get("status") == "completed" and not bool(session.get("forced_stop"))
    ]


def _session_has_nonempty_trace(session: dict[str, Any], key: str) -> bool:
    values = list(session.get(key) or [])
    return bool(values)


def _session_has_nonempty_play_trace(session: dict[str, Any]) -> bool:
    traces = list((session.get("diagnostics") or {}).get("turn_traces") or [])
    return bool(traces)


def _trace_has_labeled_failure(trace: dict[str, Any]) -> bool:
    return any(
        str(trace.get(field) or "").strip()
        for field in (
            "interpret_failure_reason",
            "render_failure_reason",
            "ending_judge_failure_reason",
            "pyrrhic_critic_failure_reason",
        )
    )


def _trace_is_repaired_or_fallback(trace: dict[str, Any]) -> bool:
    render_source = str(trace.get("render_source") or "")
    interpret_source = str(trace.get("interpret_source") or "")
    ending_judge_source = str(trace.get("ending_judge_source") or "")
    pyrrhic_critic_source = str(trace.get("pyrrhic_critic_source") or "")
    return any(
        source in {"llm_repair", "llm_salvage", "heuristic", "failed", "fallback"}
        for source in (
            render_source,
            interpret_source,
            ending_judge_source,
            pyrrhic_critic_source,
        )
    )


def _build_scorecard(stories: list[dict[str, Any]], *, target_story_count: int, personas_per_story: int) -> dict[str, Any]:
    author_successes = sum(1 for story in stories if story.get("published_story"))
    target_session_count = target_story_count * personas_per_story
    all_sessions = [session for story in stories for session in story.get("sessions", [])]
    completed_session_records = _completed_sessions_only(all_sessions)
    completed_sessions = len(completed_session_records)
    expired_sessions = sum(1 for session in all_sessions if session["final_snapshot"].get("status") == "expired")
    create_session_seconds = [float(session["create_elapsed_seconds"]) for session in all_sessions]
    submit_turn_seconds = [
        float(turn["submit_elapsed_seconds"])
        for session in all_sessions
        for turn in session["turns"]
    ]
    first_submit_turn_seconds = [
        float(session["turns"][0]["submit_elapsed_seconds"])
        for session in all_sessions
        if list(session.get("turns") or [])
    ]
    total_turns = sum(len(session["turns"]) for session in all_sessions)
    benchmark_agent_turn_fallback_count = sum(
        1
        for session in all_sessions
        for turn in session.get("turns", [])
        if str(turn.get("agent_turn_source") or "") == "fallback"
    )
    benchmark_agent_turn_llm_count = sum(
        1
        for session in all_sessions
        for turn in session.get("turns", [])
        if str(turn.get("agent_turn_source") or "") == "llm"
    )
    benchmark_agent_turn_llm_salvage_count = sum(
        1
        for session in all_sessions
        for turn in session.get("turns", [])
        if str(turn.get("agent_turn_source") or "") == "llm_salvage"
    )
    benchmark_agent_report_fallback_count = sum(
        1
        for session in all_sessions
        if str((session.get("agent_report") or {}).get("source") or "") == "fallback"
    )
    benchmark_agent_report_llm_count = sum(
        1
        for session in all_sessions
        if str((session.get("agent_report") or {}).get("source") or "") == "llm"
    )
    benchmark_agent_report_llm_salvage_partial_count = sum(
        1
        for session in all_sessions
        if str((session.get("agent_report") or {}).get("source") or "") == "llm_salvage_partial"
    )
    benchmark_agent_turn_stage1_success_count = sum(int(session.get("agent_turn_stage1_success_count") or 0) for session in all_sessions)
    benchmark_agent_turn_stage2_rescue_count = sum(int(session.get("agent_turn_stage2_rescue_count") or 0) for session in all_sessions)
    benchmark_agent_report_stage1_success_count = sum(1 for session in all_sessions if session.get("agent_report_stage1_success"))
    benchmark_agent_report_stage2_rescue_count = sum(1 for session in all_sessions if session.get("agent_report_stage2_rescue"))
    render_fallback_turns = sum(
        int((session["diagnostics"].get("summary") or {}).get("render_fallback_turn_count") or 0)
        for session in all_sessions
    )
    heuristic_interpret_turns = sum(
        int((session["diagnostics"].get("summary") or {}).get("heuristic_interpret_turn_count") or 0)
        for session in all_sessions
    )
    flat_state_feedback_count = sum(
        1
        for session in all_sessions
        if "flat_state_feedback" in set(session["agent_report"].get("flags") or [])
    )
    late_game_flatness_count = sum(
        1
        for session in all_sessions
        if "late_game_flatness" in set(session["agent_report"].get("flags") or [])
    )
    player_identity_confusion_count = sum(
        1
        for session in all_sessions
        if "player_identity_confusion" in set(session["agent_report"].get("flags") or [])
    )
    templated_opening_count = sum(
        1
        for session in all_sessions
        if "templated_opening" in set(session["agent_report"].get("flags") or [])
    )
    narration_word_counts = [
        int(turn["narration_word_count"])
        for session in all_sessions
        for turn in session["turns"]
    ]
    richness_scores = [
        int((session["agent_report"].get("ratings") or {}).get("content_richness") or 0)
        for session in all_sessions
    ]
    turn_budget_utilization = [
        float(session.get("turn_budget_utilization") or 0.0)
        for session in all_sessions
        if session.get("turn_budget")
    ]
    author_total_estimated_cost_rmb = round(
        sum(
            float((((story.get("diagnostics") or {}).get("token_cost_estimate") or {}).get("estimated_total_cost_rmb") or 0.0))
            for story in stories
        ),
        6,
    )
    author_total_estimated_cost_usd = _cost_rmb_to_usd(author_total_estimated_cost_rmb)
    play_usage_totals: dict[str, int] = {}
    author_source_distribution: dict[str, int] = {}
    play_interpret_distribution: dict[str, int] = {}
    play_render_distribution: dict[str, int] = {}
    ending_distribution: dict[str, int] = {}
    early_non_collapse_ending_count = 0
    ending_judge_failed_turns = 0
    benchmark_agent_error_distribution: dict[str, int] = {}
    benchmark_agent_turn_rejection_distribution: dict[str, int] = {}
    benchmark_agent_report_missing_field_distribution: dict[str, int] = {}
    benchmark_agent_turn_max_output_tokens = 0
    benchmark_agent_report_max_output_tokens = 0
    benchmark_agent_transcript_window_entries = 0
    benchmark_agent_total_estimated_cost_rmb = 0.0
    agent_trace_coverage_count = 0
    play_trace_coverage_count = 0
    repaired_or_fallback_trace_turn_count = 0
    labeled_failure_trace_turn_count = 0
    for story in stories:
        source_summary = dict((story.get("diagnostics") or {}).get("source_summary") or {})
        for key, value in source_summary.items():
            author_source_distribution[f"{key}:{value}"] = author_source_distribution.get(f"{key}:{value}", 0) + 1
        for session in story.get("sessions", []):
            summary = dict(session["diagnostics"].get("summary") or {})
            _accumulate_distribution(play_usage_totals, dict(summary.get("usage_totals") or {}))
            _accumulate_distribution(play_interpret_distribution, dict(summary.get("interpret_source_distribution") or {}))
            _accumulate_distribution(play_render_distribution, dict(summary.get("render_source_distribution") or {}))
            ending_judge_failed_turns += int((summary.get("ending_judge_source_distribution") or {}).get("failed") or 0)
            _accumulate_distribution(benchmark_agent_error_distribution, dict(session.get("agent_error_distribution") or {}))
            _accumulate_distribution(benchmark_agent_turn_rejection_distribution, dict(session.get("agent_turn_rejection_distribution") or {}))
            _accumulate_distribution(benchmark_agent_report_missing_field_distribution, dict(session.get("agent_report_missing_field_distribution") or {}))
            benchmark_agent_turn_max_output_tokens = max(benchmark_agent_turn_max_output_tokens, int(session.get("agent_turn_max_output_tokens") or 0))
            benchmark_agent_report_max_output_tokens = max(benchmark_agent_report_max_output_tokens, int(session.get("agent_report_max_output_tokens") or 0))
            benchmark_agent_transcript_window_entries = max(benchmark_agent_transcript_window_entries, int(session.get("agent_transcript_window_entries") or 0))
            benchmark_agent_total_estimated_cost_rmb += float(
                ((session.get("agent_cost_estimate") or {}).get("estimated_total_cost_rmb") or 0.0)
            )
            if session in completed_session_records:
                if _session_has_nonempty_trace(session, "agent_call_trace"):
                    agent_trace_coverage_count += 1
                if _session_has_nonempty_play_trace(session):
                    play_trace_coverage_count += 1
                for trace in list((session.get("diagnostics") or {}).get("turn_traces") or []):
                    if _trace_is_repaired_or_fallback(trace):
                        repaired_or_fallback_trace_turn_count += 1
                        if _trace_has_labeled_failure(trace):
                            labeled_failure_trace_turn_count += 1
            ending_id = str((session["final_snapshot"].get("ending") or {}).get("ending_id") or "unfinished")
            ending_distribution[ending_id] = ending_distribution.get(ending_id, 0) + 1
            turn_budget = int(session.get("turn_budget") or 0)
            ending_turn = int(session["final_snapshot"].get("turn_index") or 0)
            if ending_id not in {"collapse", "unfinished"} and turn_budget and ending_turn and ending_turn < max(ceil(turn_budget / 2), 2):
                early_non_collapse_ending_count += 1
    benchmark_agent_total_estimated_cost_rmb = round(benchmark_agent_total_estimated_cost_rmb, 6)
    benchmark_agent_total_estimated_cost_usd = _cost_rmb_to_usd(benchmark_agent_total_estimated_cost_rmb)
    play_runtime_cost = _estimate_usage_cost_from_totals(play_usage_totals)
    combined_runtime_total_estimated_cost_rmb = round(
        author_total_estimated_cost_rmb + float(play_runtime_cost["rmb"]),
        6,
    )
    combined_runtime_total_estimated_cost_usd = _cost_rmb_to_usd(combined_runtime_total_estimated_cost_rmb)
    combined_benchmark_total_estimated_cost_rmb = round(
        combined_runtime_total_estimated_cost_rmb + benchmark_agent_total_estimated_cost_rmb,
        6,
    )
    combined_benchmark_total_estimated_cost_usd = _cost_rmb_to_usd(combined_benchmark_total_estimated_cost_rmb)
    actuals = {
        "author_publish_success_rate": round(author_successes / target_story_count, 3) if target_story_count else 0.0,
        "play_completed_sessions": completed_sessions,
        "expired_sessions": expired_sessions,
        "median_create_session_seconds": round(statistics.median(create_session_seconds), 3) if create_session_seconds else 0.0,
        "median_first_submit_turn_seconds": round(statistics.median(first_submit_turn_seconds), 3) if first_submit_turn_seconds else 0.0,
        "p95_submit_turn_seconds": round(_percentile(submit_turn_seconds, 0.95), 3) if submit_turn_seconds else 0.0,
        "render_fallback_rate": round(render_fallback_turns / total_turns, 3) if total_turns else 0.0,
        "heuristic_interpret_rate": round(heuristic_interpret_turns / total_turns, 3) if total_turns else 0.0,
        "ending_judge_failed_rate": round(ending_judge_failed_turns / total_turns, 3) if total_turns else 0.0,
        "player_identity_confusion_flag_rate": round(player_identity_confusion_count / len(all_sessions), 3) if all_sessions else 0.0,
        "flat_state_feedback_flag_rate": round(flat_state_feedback_count / len(all_sessions), 3) if all_sessions else 0.0,
        "late_game_flatness_flag_rate": round(late_game_flatness_count / len(all_sessions), 3) if all_sessions else 0.0,
        "benchmark_agent_turn_llm_rate": round(benchmark_agent_turn_llm_count / total_turns, 3) if total_turns else 0.0,
        "benchmark_agent_turn_llm_salvage_rate": round(benchmark_agent_turn_llm_salvage_count / total_turns, 3) if total_turns else 0.0,
        "benchmark_agent_turn_fallback_rate": round(benchmark_agent_turn_fallback_count / total_turns, 3) if total_turns else 0.0,
        "benchmark_agent_turn_stage1_success_rate": round(benchmark_agent_turn_stage1_success_count / total_turns, 3) if total_turns else 0.0,
        "benchmark_agent_turn_stage2_rescue_rate": round(benchmark_agent_turn_stage2_rescue_count / total_turns, 3) if total_turns else 0.0,
        "benchmark_agent_report_llm_rate": round(benchmark_agent_report_llm_count / len(all_sessions), 3) if all_sessions else 0.0,
        "benchmark_agent_report_llm_salvage_partial_rate": round(benchmark_agent_report_llm_salvage_partial_count / len(all_sessions), 3) if all_sessions else 0.0,
        "benchmark_agent_report_fallback_rate": round(benchmark_agent_report_fallback_count / len(all_sessions), 3) if all_sessions else 0.0,
        "benchmark_agent_report_stage1_success_rate": round(benchmark_agent_report_stage1_success_count / len(all_sessions), 3) if all_sessions else 0.0,
        "benchmark_agent_report_stage2_rescue_rate": round(benchmark_agent_report_stage2_rescue_count / len(all_sessions), 3) if all_sessions else 0.0,
        "judge_nonfallback_rate": round(
            (
                (benchmark_agent_report_llm_count + benchmark_agent_report_llm_salvage_partial_count) / len(all_sessions)
            ),
            3,
        ) if all_sessions else 0.0,
        "judge_fallback_rate": round(benchmark_agent_report_fallback_count / len(all_sessions), 3) if all_sessions else 0.0,
        "playtest_agent_invalid_json_count": int(benchmark_agent_error_distribution.get("playtest_agent_invalid_json") or 0),
        "benchmark_agent_turn_max_output_tokens": benchmark_agent_turn_max_output_tokens,
        "benchmark_agent_report_max_output_tokens": benchmark_agent_report_max_output_tokens,
        "benchmark_agent_transcript_window_entries": benchmark_agent_transcript_window_entries,
        "agent_trace_coverage_rate": round(agent_trace_coverage_count / completed_sessions, 3) if completed_sessions else 0.0,
        "play_trace_coverage_rate": round(play_trace_coverage_count / completed_sessions, 3) if completed_sessions else 0.0,
        "trace_labeled_failure_rate": round(
            labeled_failure_trace_turn_count / repaired_or_fallback_trace_turn_count,
            3,
        ) if repaired_or_fallback_trace_turn_count else 0.0,
        "mean_narration_word_count_per_turn": round(statistics.mean(narration_word_counts), 3) if narration_word_counts else 0.0,
        "content_richness": round(statistics.mean(richness_scores), 3) if richness_scores else 0.0,
        "axis_diversity_per_session": _axis_diversity_per_session(all_sessions),
        "stance_target_diversity_per_session": _stance_target_diversity_per_session(all_sessions),
        "late_half_axis_diversity_per_session": _late_half_axis_diversity_per_session(all_sessions),
        "late_half_stance_target_diversity_per_session": _late_half_stance_target_diversity_per_session(all_sessions),
        "turn_budget_utilization": round(statistics.mean(turn_budget_utilization), 3) if turn_budget_utilization else 0.0,
        "early_non_collapse_ending_count": early_non_collapse_ending_count,
        "state_feedback_distinctness": round(
            statistics.mean(
                [
                    int((session["agent_report"].get("ratings") or {}).get("state_feedback_distinctness") or 0)
                    for session in all_sessions
                    if session.get("agent_report")
                ]
            ),
            3,
        ) if all_sessions else 0.0,
        "author_total_estimated_cost_rmb": author_total_estimated_cost_rmb,
        "author_total_estimated_cost_usd": author_total_estimated_cost_usd,
        "play_runtime_total_estimated_cost_rmb": float(play_runtime_cost["rmb"]),
        "play_runtime_total_estimated_cost_usd": float(play_runtime_cost["usd"]),
        "benchmark_agent_total_estimated_cost_rmb": benchmark_agent_total_estimated_cost_rmb,
        "benchmark_agent_total_estimated_cost_usd": benchmark_agent_total_estimated_cost_usd,
        "combined_runtime_total_estimated_cost_rmb": combined_runtime_total_estimated_cost_rmb,
        "combined_runtime_total_estimated_cost_usd": combined_runtime_total_estimated_cost_usd,
        "combined_benchmark_total_estimated_cost_rmb": combined_benchmark_total_estimated_cost_rmb,
        "combined_benchmark_total_estimated_cost_usd": combined_benchmark_total_estimated_cost_usd,
    }
    polluted_by_driver = actuals["benchmark_agent_turn_fallback_rate"] > 0.2
    subjective_reference_only = actuals["benchmark_agent_report_fallback_rate"] > 0.34 or polluted_by_driver
    driver_fixcheck_gates = [
        {"metric": "benchmark_agent_turn_fallback_rate", "passed": actuals["benchmark_agent_turn_fallback_rate"] < 0.2},
        {"metric": "benchmark_agent_report_fallback_rate", "passed": actuals["benchmark_agent_report_fallback_rate"] < 0.34},
        {"metric": "benchmark_agent_turn_llm_plus_salvage_rate", "passed": (actuals["benchmark_agent_turn_llm_rate"] + actuals["benchmark_agent_turn_llm_salvage_rate"]) >= 0.8},
        {"metric": "benchmark_agent_report_llm_plus_salvage_rate", "passed": (actuals["benchmark_agent_report_llm_rate"] + actuals["benchmark_agent_report_llm_salvage_partial_rate"]) >= 0.66},
    ]
    gates = [
        {"metric": "author_publish_success_rate", "actual": actuals["author_publish_success_rate"], "threshold": 1.0, "operator": ">=", "passed": actuals["author_publish_success_rate"] >= 1.0},
        {
            "metric": "play_completed_sessions",
            "actual": actuals["play_completed_sessions"],
            "threshold": min(target_session_count, 9),
            "operator": ">=",
            "passed": actuals["play_completed_sessions"] >= min(target_session_count, 9),
        },
        {"metric": "expired_sessions", "actual": actuals["expired_sessions"], "threshold": 0, "operator": "<=", "passed": actuals["expired_sessions"] <= 0},
        {"metric": "median_create_session_seconds", "actual": actuals["median_create_session_seconds"], "threshold": 5.0, "operator": "<=", "passed": actuals["median_create_session_seconds"] <= 5.0},
        {"metric": "p95_submit_turn_seconds", "actual": actuals["p95_submit_turn_seconds"], "threshold": 25.0, "operator": "<=", "passed": actuals["p95_submit_turn_seconds"] <= 25.0},
        {"metric": "render_fallback_rate", "actual": actuals["render_fallback_rate"], "threshold": 0.35, "operator": "<=", "passed": actuals["render_fallback_rate"] <= 0.35},
        {"metric": "heuristic_interpret_rate", "actual": actuals["heuristic_interpret_rate"], "threshold": 0.35, "operator": "<=", "passed": actuals["heuristic_interpret_rate"] <= 0.35},
        {"metric": "player_identity_confusion_flag_rate", "actual": actuals["player_identity_confusion_flag_rate"], "threshold": 0.20, "operator": "<=", "passed": actuals["player_identity_confusion_flag_rate"] <= 0.20},
        {"metric": "flat_state_feedback_flag_rate", "actual": actuals["flat_state_feedback_flag_rate"], "threshold": 0.40, "operator": "<=", "passed": actuals["flat_state_feedback_flag_rate"] <= 0.40},
        {"metric": "mean_narration_word_count_per_turn", "actual": actuals["mean_narration_word_count_per_turn"], "threshold": 70.0, "operator": ">=", "passed": actuals["mean_narration_word_count_per_turn"] >= 70.0},
    ]
    return {
        "passed": all(gate["passed"] for gate in gates) and not polluted_by_driver,
        "driver_fixcheck_passed": all(gate["passed"] for gate in driver_fixcheck_gates),
        "driver_fixcheck_gates": driver_fixcheck_gates,
        "polluted_by_driver": polluted_by_driver,
        "subjective_reference_only": subjective_reference_only,
        "target_story_count": target_story_count,
        "target_session_count": target_session_count,
        "actuals": actuals,
        "gates": gates,
        "content_richness": {
            "average_rating": round(statistics.mean(richness_scores), 3) if richness_scores else 0.0,
            "report_count": len(richness_scores),
            "templated_opening_flag_count": templated_opening_count,
        },
        "subjective_summary": {
            "avg_narration_coherence": _average_report_rating(all_sessions, "narration_coherence"),
            "avg_suggested_action_relevance": _average_report_rating(all_sessions, "suggested_action_relevance"),
            "avg_state_feedback_credibility": _average_report_rating(all_sessions, "state_feedback_credibility"),
            "avg_ending_satisfaction": _average_report_rating(all_sessions, "ending_satisfaction"),
            "avg_overall_player_feel": _average_report_rating(all_sessions, "overall_player_feel"),
        },
        "cost_and_cache": {
            "author_total_estimated_cost_rmb": author_total_estimated_cost_rmb,
            "author_total_estimated_cost_usd": author_total_estimated_cost_usd,
            "play_runtime_total_estimated_cost_rmb": float(play_runtime_cost["rmb"]),
            "play_runtime_total_estimated_cost_usd": float(play_runtime_cost["usd"]),
            "benchmark_agent_total_estimated_cost_rmb": benchmark_agent_total_estimated_cost_rmb,
            "benchmark_agent_total_estimated_cost_usd": benchmark_agent_total_estimated_cost_usd,
            "play_usage_totals": play_usage_totals,
            "benchmark_agent_error_distribution": benchmark_agent_error_distribution,
            "benchmark_agent_turn_rejection_distribution": benchmark_agent_turn_rejection_distribution,
            "benchmark_agent_report_missing_field_distribution": benchmark_agent_report_missing_field_distribution,
        },
        "source_distribution": {
            "author": author_source_distribution,
            "play_interpret": play_interpret_distribution,
            "play_render": play_render_distribution,
        },
        "ending_distribution": ending_distribution,
        "benchmark_agent_error_distribution": benchmark_agent_error_distribution,
        "benchmark_agent_turn_rejection_distribution": benchmark_agent_turn_rejection_distribution,
        "benchmark_agent_report_missing_field_distribution": benchmark_agent_report_missing_field_distribution,
    }


def _distribution_shift(baseline: dict[str, int], candidate: dict[str, int]) -> dict[str, int]:
    keys = sorted({*baseline.keys(), *candidate.keys()})
    return {key: int(candidate.get(key, 0)) - int(baseline.get(key, 0)) for key in keys}


def compare_benchmark_payloads(
    *,
    baseline_payload: dict[str, Any],
    candidate_payload: dict[str, Any],
    phase_id: str | None,
    baseline_artifact: str | None,
) -> dict[str, Any]:
    baseline_scorecard = dict(baseline_payload.get("scorecard") or {})
    candidate_scorecard = dict(candidate_payload.get("scorecard") or {})
    baseline_actuals = dict(baseline_scorecard.get("actuals") or {})
    candidate_actuals = dict(candidate_scorecard.get("actuals") or {})
    baseline_subjective = dict(baseline_scorecard.get("subjective_summary") or {})
    candidate_subjective = dict(candidate_scorecard.get("subjective_summary") or {})
    deltas = {
        key: round(float(candidate_actuals.get(key, 0.0)) - float(baseline_actuals.get(key, 0.0)), 3)
        for key in sorted({*baseline_actuals.keys(), *candidate_actuals.keys()})
    }
    subjective_deltas = {
        key: round(float(candidate_subjective.get(key, 0.0)) - float(baseline_subjective.get(key, 0.0)), 3)
        for key in sorted({*baseline_subjective.keys(), *candidate_subjective.keys()})
    }
    reliability_passed = (
        candidate_actuals.get("author_publish_success_rate", 0.0) >= 1.0
        and candidate_actuals.get("play_completed_sessions", 0) >= baseline_scorecard.get("target_session_count", 6)
        and candidate_actuals.get("expired_sessions", 0) <= 0
    )
    if phase_id == "stage1":
        phase_gates = [
            {"metric": "reliability_gate", "passed": reliability_passed},
            {"metric": "flat_state_feedback_flag_rate", "passed": candidate_actuals.get("flat_state_feedback_flag_rate", 1.0) < baseline_actuals.get("flat_state_feedback_flag_rate", 1.0)},
            {"metric": "axis_diversity_per_session", "passed": candidate_actuals.get("axis_diversity_per_session", 0.0) > baseline_actuals.get("axis_diversity_per_session", 0.0)},
            {"metric": "p95_submit_turn_seconds", "passed": candidate_actuals.get("p95_submit_turn_seconds", 999.0) <= min(float(baseline_actuals.get("p95_submit_turn_seconds", 25.0)) * 1.2, 25.0)},
            {"metric": "heuristic_interpret_rate", "passed": candidate_actuals.get("heuristic_interpret_rate", 1.0) <= float(baseline_actuals.get("heuristic_interpret_rate", 0.0)) + 0.05},
            {"metric": "render_fallback_rate", "passed": candidate_actuals.get("render_fallback_rate", 1.0) <= baseline_actuals.get("render_fallback_rate", 1.0)},
        ]
    elif phase_id == "stage2":
        phase_gates = [
            {"metric": "reliability_gate", "passed": reliability_passed},
            {"metric": "flat_state_feedback_flag_rate", "passed": candidate_actuals.get("flat_state_feedback_flag_rate", 1.0) <= 0.4},
            {"metric": "state_feedback_distinctness", "passed": candidate_actuals.get("state_feedback_distinctness", 0.0) > baseline_actuals.get("state_feedback_distinctness", 0.0)},
            {"metric": "mean_narration_word_count_per_turn", "passed": candidate_actuals.get("mean_narration_word_count_per_turn", 0.0) >= 70.0},
            {"metric": "player_identity_confusion_flag_rate", "passed": candidate_actuals.get("player_identity_confusion_flag_rate", 1.0) <= 0.2},
            {"metric": "render_fallback_rate", "passed": candidate_actuals.get("render_fallback_rate", 1.0) <= 0.35},
        ]
    elif phase_id == "zh-naturalness":
        phase_gates = [
            {"metric": "reliability_gate", "passed": reliability_passed},
            {
                "metric": "avg_suggested_action_relevance",
                "passed": candidate_subjective.get("avg_suggested_action_relevance", 0.0)
                > baseline_subjective.get("avg_suggested_action_relevance", 0.0),
            },
            {
                "metric": "avg_state_feedback_credibility",
                "passed": candidate_subjective.get("avg_state_feedback_credibility", 0.0)
                >= baseline_subjective.get("avg_state_feedback_credibility", 0.0),
            },
            {
                "metric": "avg_overall_player_feel",
                "passed": candidate_subjective.get("avg_overall_player_feel", 0.0)
                > baseline_subjective.get("avg_overall_player_feel", 0.0),
            },
            {
                "metric": "avg_narration_coherence",
                "passed": candidate_subjective.get("avg_narration_coherence", 0.0)
                >= baseline_subjective.get("avg_narration_coherence", 0.0),
            },
            {
                "metric": "state_feedback_distinctness",
                "passed": candidate_actuals.get("state_feedback_distinctness", 0.0)
                >= baseline_actuals.get("state_feedback_distinctness", 0.0),
            },
            {
                "metric": "mean_narration_word_count_per_turn",
                "passed": candidate_actuals.get("mean_narration_word_count_per_turn", 0.0)
                >= baseline_actuals.get("mean_narration_word_count_per_turn", 0.0),
            },
            {
                "metric": "heuristic_interpret_rate",
                "passed": candidate_actuals.get("heuristic_interpret_rate", 1.0)
                <= baseline_actuals.get("heuristic_interpret_rate", 1.0),
            },
            {
                "metric": "p95_submit_turn_seconds",
                "passed": candidate_actuals.get("p95_submit_turn_seconds", 999.0)
                <= min(float(baseline_actuals.get("p95_submit_turn_seconds", 25.0)) * 1.2, 25.0),
            },
            {
                "metric": "render_fallback_rate",
                "passed": candidate_actuals.get("render_fallback_rate", 1.0)
                <= baseline_actuals.get("render_fallback_rate", 1.0),
            },
            {
                "metric": "player_identity_confusion_flag_rate",
                "passed": candidate_actuals.get("player_identity_confusion_flag_rate", 1.0)
                <= baseline_actuals.get("player_identity_confusion_flag_rate", 1.0),
            },
        ]
    else:
        phase_gates = [
            {"metric": "reliability_gate", "passed": reliability_passed},
        ]
    return {
        "phase_id": phase_id,
        "seed_set_id": candidate_payload.get("seed_set_id"),
        "baseline_artifact": baseline_artifact,
        "baseline_label": baseline_payload.get("label"),
        "candidate_label": candidate_payload.get("label"),
        "baseline_content_prompt_profile": baseline_payload.get("configured_content_prompt_profile"),
        "candidate_content_prompt_profile": candidate_payload.get("configured_content_prompt_profile"),
        "baseline_scorecard": baseline_scorecard,
        "candidate_scorecard": candidate_scorecard,
        "delta_actuals": deltas,
        "delta_subjective_summary": subjective_deltas,
        "ending_distribution_shift": _distribution_shift(
            dict(baseline_scorecard.get("ending_distribution") or {}),
            dict(candidate_scorecard.get("ending_distribution") or {}),
        ),
        "phase_gates": phase_gates,
        "passed": all(bool(gate["passed"]) for gate in phase_gates),
    }


def _excerpt_text(value: str | None, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _turn_has_play_only_issue(
    *,
    turn: dict[str, Any],
    trace: dict[str, Any],
    language: str | None,
) -> bool:
    narration = str(turn.get("narration") or "").strip()
    if not narration:
        return True
    if has_language_contamination(narration, language):
        return True
    failure_fields = (
        "render_failure_reason",
        "interpret_failure_reason",
        "render_primary_failure_reason",
        "render_quality_reason_before_repair",
        "render_repair_failure_reason",
    )
    if any(str(trace.get(field) or "").strip() for field in failure_fields):
        return True
    source_fields = (
        "render_source",
        "interpret_source",
        "ending_judge_source",
        "pyrrhic_critic_source",
    )
    if any(
        str(trace.get(field) or "").strip() in {"llm_repair", "llm_salvage", "heuristic", "failed", "fallback"}
        for field in source_fields
    ):
        return True
    return False


def _classify_play_only_issue_turn(
    *,
    turn: dict[str, Any],
    trace: dict[str, Any],
    language: str | None,
) -> str:
    primary_failure_reason = str(trace.get("render_primary_failure_reason") or "").strip()
    primary_fallback_source = str(trace.get("render_primary_fallback_source") or "").strip()
    primary_raw_excerpt = str(trace.get("render_primary_raw_excerpt") or "")
    if (
        primary_failure_reason == "scene_plan_missing"
        and primary_fallback_source == "plaintext_salvage"
        and any(marker in primary_raw_excerpt.upper() for marker in ("SCENE_REACTION", "AXIS_PAYOFF"))
    ):
        return "stage1_plan_protocol_mismatch"
    if (
        str(trace.get("render_quality_reason_before_repair") or "").strip()
        and not primary_failure_reason
    ):
        return "quality_gate_rejection"
    if str(trace.get("render_repair_failure_reason") or "").strip():
        return "repair_instability"
    if (
        has_language_contamination(turn.get("narration"), language)
        or has_language_contamination(trace.get("render_primary_raw_excerpt"), language)
        or has_language_contamination(trace.get("render_repair_raw_excerpt"), language)
    ):
        return "language_contamination"
    if _turn_has_play_only_issue(turn=turn, trace=trace, language=language):
        return "other_runtime_issue"
    return "clean"


def _trace_issue_excerpt(turn: dict[str, Any], trace: dict[str, Any]) -> str:
    for value in (
        trace.get("render_primary_raw_excerpt"),
        trace.get("render_repair_raw_excerpt"),
        turn.get("narration"),
    ):
        excerpt = _excerpt_text(str(value or ""), limit=280)
        if excerpt:
            return excerpt
    return ""


def _build_play_only_trace_eval(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    render_source_distribution: dict[str, int] = {}
    render_failure_reason_distribution: dict[str, int] = {}
    interpret_failure_reason_distribution: dict[str, int] = {}
    ending_judge_source_distribution: dict[str, int] = {}
    trace_cause_distribution: dict[str, int] = {}
    issue_examples_by_bucket: dict[str, list[dict[str, Any]]] = {}
    total_turn_count = 0
    empty_narration_count = 0
    issue_turn_count = 0
    for session in sessions:
        diagnostics = dict(session.get("diagnostics") or {})
        summary = dict(diagnostics.get("summary") or {})
        _accumulate_distribution(render_source_distribution, dict(summary.get("render_source_distribution") or {}))
        _accumulate_distribution(
            render_failure_reason_distribution,
            dict(summary.get("render_failure_reason_distribution") or {}),
        )
        _accumulate_distribution(
            interpret_failure_reason_distribution,
            dict(summary.get("interpret_failure_reason_distribution") or {}),
        )
        _accumulate_distribution(
            ending_judge_source_distribution,
            dict(summary.get("ending_judge_source_distribution") or {}),
        )
        language = str(session.get("story_language") or "en")
        traces = list(diagnostics.get("turn_traces") or [])
        for index, turn in enumerate(list(session.get("turns") or []), start=1):
            total_turn_count += 1
            narration = str(turn.get("narration") or "").strip()
            if not narration:
                empty_narration_count += 1
            trace = dict(traces[index - 1] or {}) if index - 1 < len(traces) else {}
            if not _turn_has_play_only_issue(turn=turn, trace=trace, language=language):
                continue
            bucket = _classify_play_only_issue_turn(turn=turn, trace=trace, language=language)
            if bucket == "clean":
                bucket = "other_runtime_issue"
            issue_turn_count += 1
            trace_cause_distribution[bucket] = trace_cause_distribution.get(bucket, 0) + 1
            examples = issue_examples_by_bucket.setdefault(bucket, [])
            if len(examples) < 3:
                examples.append(
                    {
                        "story_id": session.get("story_id"),
                        "story_language": language,
                        "persona_id": session.get("persona_id"),
                        "session_id": session.get("session_id"),
                        "turn_index": int(turn.get("turn_index") or index),
                        "render_source": trace.get("render_source"),
                        "render_failure_reason": trace.get("render_failure_reason"),
                        "interpret_failure_reason": trace.get("interpret_failure_reason"),
                        "render_primary_failure_reason": trace.get("render_primary_failure_reason"),
                        "render_primary_fallback_source": trace.get("render_primary_fallback_source"),
                        "render_quality_reason_before_repair": trace.get("render_quality_reason_before_repair"),
                        "render_repair_failure_reason": trace.get("render_repair_failure_reason"),
                        "excerpt": _trace_issue_excerpt(turn, trace),
                    }
                )
    ordered_issue_examples = {
        bucket: issue_examples_by_bucket[bucket]
        for bucket, _count in sorted(
            trace_cause_distribution.items(),
            key=lambda item: (-item[1], item[0]),
        )
    }
    return {
        "total_turn_count": total_turn_count,
        "issue_turn_count": issue_turn_count,
        "issue_turn_rate": round(issue_turn_count / total_turn_count, 3) if total_turn_count else 0.0,
        "empty_narration_count": empty_narration_count,
        "empty_narration_rate": round(empty_narration_count / total_turn_count, 3) if total_turn_count else 0.0,
        "render_source_distribution": render_source_distribution,
        "render_failure_reason_distribution": render_failure_reason_distribution,
        "interpret_failure_reason_distribution": interpret_failure_reason_distribution,
        "ending_judge_source_distribution": ending_judge_source_distribution,
        "trace_issue_distribution": trace_cause_distribution,
        "representative_excerpts": ordered_issue_examples,
        "classified_issue_turn_count": issue_turn_count,
        "unclassified_issue_turn_count": 0,
    }


def _build_play_only_agent_metrics(sessions: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    proposal_provider_distribution: dict[str, int] = {}
    judge_provider_distribution: dict[str, int] = {}
    agent_provider_mode_distribution: dict[str, int] = {}
    proposal_turn_source_distribution: dict[str, int] = {}
    proposal_error_distribution: dict[str, int] = {}
    judge_error_distribution: dict[str, int] = {}
    proposal_turn_rejection_distribution: dict[str, int] = {}
    judge_report_missing_field_distribution: dict[str, int] = {}
    judge_report_source_distribution: dict[str, int] = {}
    total_turn_count = 0
    total_turn_stage1_success_count = 0
    total_turn_stage2_rescue_count = 0
    judge_nonfallback_count = 0
    judge_fallback_count = 0
    judged_sessions: list[dict[str, Any]] = []
    for session in sessions:
        proposal_provider = str(session.get("proposal_agent_provider") or "primary")
        judge_provider = str(session.get("judge_agent_provider") or "pending")
        provider_mode = str(session.get("agent_provider_mode") or "shared")
        proposal_provider_distribution[proposal_provider] = proposal_provider_distribution.get(proposal_provider, 0) + 1
        judge_provider_distribution[judge_provider] = judge_provider_distribution.get(judge_provider, 0) + 1
        agent_provider_mode_distribution[provider_mode] = agent_provider_mode_distribution.get(provider_mode, 0) + 1
        _accumulate_distribution(
            proposal_error_distribution,
            dict(session.get("proposal_agent_error_distribution") or {}),
        )
        _accumulate_distribution(
            judge_error_distribution,
            dict(session.get("judge_agent_error_distribution") or {}),
        )
        _accumulate_distribution(
            proposal_turn_rejection_distribution,
            dict(session.get("proposal_agent_turn_rejection_distribution") or {}),
        )
        _accumulate_distribution(
            judge_report_missing_field_distribution,
            dict(session.get("judge_agent_report_missing_field_distribution") or {}),
        )
        report_source = str((session.get("agent_report") or {}).get("source") or "fallback")
        if report_source != "pending":
            judged_sessions.append(session)
            judge_report_source_distribution[report_source] = judge_report_source_distribution.get(report_source, 0) + 1
            if report_source == "fallback":
                judge_fallback_count += 1
            else:
                judge_nonfallback_count += 1
        turns = list(session.get("turns") or [])
        total_turn_count += len(turns)
        total_turn_stage1_success_count += int(session.get("agent_turn_stage1_success_count") or 0)
        total_turn_stage2_rescue_count += int(session.get("agent_turn_stage2_rescue_count") or 0)
        for turn in turns:
            source = str(turn.get("agent_turn_source") or "fallback")
            proposal_turn_source_distribution[source] = proposal_turn_source_distribution.get(source, 0) + 1
    proposal_metrics = {
        "provider_distribution": proposal_provider_distribution,
        "turn_source_distribution": proposal_turn_source_distribution,
        "error_distribution": proposal_error_distribution,
        "turn_rejection_distribution": proposal_turn_rejection_distribution,
        "stage1_success_rate": round(total_turn_stage1_success_count / total_turn_count, 3) if total_turn_count else 0.0,
        "stage2_rescue_rate": round(total_turn_stage2_rescue_count / total_turn_count, 3) if total_turn_count else 0.0,
        "turn_count": total_turn_count,
    }
    judge_metrics = {
        "provider_distribution": judge_provider_distribution,
        "report_source_distribution": judge_report_source_distribution,
        "error_distribution": judge_error_distribution,
        "report_missing_field_distribution": judge_report_missing_field_distribution,
        "judge_nonfallback_rate": round(judge_nonfallback_count / len(judged_sessions), 3) if judged_sessions else 0.0,
        "judge_fallback_rate": round(judge_fallback_count / len(judged_sessions), 3) if judged_sessions else 0.0,
        "avg_narration_coherence": _average_report_rating(judged_sessions, "narration_coherence"),
        "avg_suggested_action_relevance": _average_report_rating(judged_sessions, "suggested_action_relevance"),
        "avg_state_feedback_credibility": _average_report_rating(judged_sessions, "state_feedback_credibility"),
        "avg_ending_satisfaction": _average_report_rating(judged_sessions, "ending_satisfaction"),
        "avg_overall_player_feel": _average_report_rating(judged_sessions, "overall_player_feel"),
        "avg_content_richness": _average_report_rating(judged_sessions, "content_richness"),
        "avg_state_feedback_distinctness": _average_report_rating(judged_sessions, "state_feedback_distinctness"),
        "session_count": len(judged_sessions),
    }
    return proposal_metrics, judge_metrics, agent_provider_mode_distribution


def _build_play_only_split_summary(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    trace_eval = _build_play_only_trace_eval(sessions)
    proposal_metrics, judge_metrics, agent_provider_mode_distribution = _build_play_only_agent_metrics(sessions)
    return {
        "session_count": len(sessions),
        "completed_session_count": len(_completed_sessions_only(sessions)),
        "turn_count": trace_eval["total_turn_count"],
        "empty_narration_count": trace_eval["empty_narration_count"],
        "empty_narration_rate": trace_eval["empty_narration_rate"],
        "issue_turn_count": trace_eval["issue_turn_count"],
        "issue_turn_rate": trace_eval["issue_turn_rate"],
        "proposal_provider_distribution": proposal_metrics["provider_distribution"],
        "judge_provider_distribution": judge_metrics["provider_distribution"],
        "agent_provider_mode_distribution": agent_provider_mode_distribution,
        "trace_issue_distribution": trace_eval["trace_issue_distribution"],
    }


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(content)
    temp_path.replace(path)


def _write_play_only_checkpoint(
    *,
    path_json: Path,
    path_md: Path,
    payload: dict[str, Any],
) -> None:
    _write_text_atomic(path_json, json.dumps(payload, ensure_ascii=False, indent=2))
    _write_text_atomic(path_md, _render_play_only_campaign_markdown(payload))


def _default_play_only_checkpoint_path(config: LiveApiPlaytestConfig) -> Path:
    label = config.label or "play_only_campaign"
    return config.output_dir / f"{label}_checkpoint.json"


def _load_play_only_resume_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if str(payload.get("mode") or "") != "play_only_campaign":
        raise RuntimeError(f"resume checkpoint must be a play_only_campaign artifact: {path}")
    return payload


def _resolved_play_only_story_ids(
    *,
    config: LiveApiPlaytestConfig,
    resume_payload: dict[str, Any] | None,
) -> tuple[str, ...]:
    if config.play_only_story_ids:
        return tuple(config.play_only_story_ids)
    if resume_payload is not None:
        fixed_story_pool = list(resume_payload.get("fixed_story_pool") or [])
        story_ids = tuple(
            str(item.get("story_id") or "").strip()
            for item in fixed_story_pool
            if str(item.get("story_id") or "").strip()
        )
        if story_ids:
            return story_ids
    raise RuntimeError("play-only campaign requires story ids via --play-only-story-ids or --resume-from")


def _play_only_checkpoint_paths(config: LiveApiPlaytestConfig) -> tuple[Path, Path]:
    json_path = config.play_only_checkpoint_path or config.resume_from or _default_play_only_checkpoint_path(config)
    return json_path, json_path.with_suffix(".md")


def _play_only_cell_counts_from_sessions(
    *,
    story_records: list[dict[str, Any]],
    max_sessions_per_cell: int,
    seeded_counts: dict[str, int] | None = None,
) -> dict[str, int]:
    counts = {
        f"{record['story_id']}::{persona.persona_id}": 0
        for record in story_records
        for persona in PERSONAS
    }
    for key, value in dict(seeded_counts or {}).items():
        if key in counts:
            counts[key] = max(min(int(value), max_sessions_per_cell), 0)
    for record in story_records:
        for session in list(record.get("sessions") or []):
            key = f"{record['story_id']}::{session.get('persona_id')}"
            if key in counts:
                counts[key] = max(
                    counts[key],
                    min(int(session.get("cell_session_index") or 0), max_sessions_per_cell),
                )
    return counts


def _play_only_completed_turn_count(story_records: list[dict[str, Any]]) -> int:
    return sum(
        len(list(session.get("turns") or []))
        for record in story_records
        for session in list(record.get("sessions") or [])
    )


def _build_play_only_campaign_payload(
    *,
    config: LiveApiPlaytestConfig,
    story_records: list[dict[str, Any]],
    cell_session_counts: dict[str, int],
    completed_turn_count: int,
    checkpoint_path: Path | None,
    resume_from: Path | None,
    run_status: str,
    capture_status: str,
    judge_status: str,
) -> dict[str, Any]:
    fixed_story_pool = [
        {
            "story_id": record["story_id"],
            "title": record["title"],
            "language": record["language"],
            "turn_budget": record["turn_budget"],
            "target_duration_minutes": int((record.get("play_overview") or {}).get("target_duration_minutes") or 0),
            "branch_budget": (record.get("play_overview") or {}).get("branch_budget"),
        }
        for record in story_records
    ]
    output_stories = [
        {
            "story_id": record["story_id"],
            "title": record["title"],
            "language": record["language"],
            "turn_budget": record["turn_budget"],
            "story_fetch_elapsed_seconds": record["story_fetch_elapsed_seconds"],
            "play_overview": record["play_overview"],
            "sessions": list(record["sessions"]),
        }
        for record in story_records
    ]
    all_sessions = [session for record in output_stories for session in record["sessions"]]
    trace_eval = _build_play_only_trace_eval(all_sessions)
    proposal_metrics, judge_metrics, agent_provider_mode_distribution = _build_play_only_agent_metrics(all_sessions)
    per_story = {
        record["story_id"]: {
            "story_id": record["story_id"],
            "title": record["title"],
            "language": record["language"],
            **_build_play_only_split_summary(list(record["sessions"])),
        }
        for record in output_stories
    }
    per_language_sessions: dict[str, list[dict[str, Any]]] = {}
    for session in all_sessions:
        language = str(session.get("story_language") or "en")
        per_language_sessions.setdefault(language, []).append(session)
    per_language = {
        language: _build_play_only_split_summary(language_sessions)
        for language, language_sessions in sorted(per_language_sessions.items())
    }
    required_completed_turns = min(max(config.target_total_turns, 1), 200)
    total_cells = len(story_records) * len(PERSONAS)
    completed_cells = sum(1 for value in cell_session_counts.values() if int(value) >= config.max_sessions_per_cell)
    total_session_target = total_cells * config.max_sessions_per_cell
    current_session_count = sum(int(value) for value in cell_session_counts.values())
    judged_completed_sessions = sum(
        1
        for session in all_sessions
        if str(session.get("judge_status") or "") == "completed"
    )
    judge_pending_sessions = sum(
        1
        for session in all_sessions
        if str(session.get("judge_status") or "pending") != "completed"
    )
    verdict = {
        "passed": (
            completed_turn_count >= required_completed_turns
            and int(trace_eval.get("empty_narration_count") or 0) == 0
            and int(trace_eval.get("unclassified_issue_turn_count") or 0) == 0
            and run_status == "completed"
        ),
        "required_completed_turns": required_completed_turns,
        "completed_turn_count": completed_turn_count,
        "empty_narration_rate": trace_eval["empty_narration_rate"],
        "issue_turn_rate": trace_eval["issue_turn_rate"],
    }
    return {
        "mode": "play_only_campaign",
        "run_status": run_status,
        "capture_status": capture_status,
        "judge_status": judge_status,
        "base_url": config.base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "launch_server": config.launch_server,
        "label": config.label,
        "agent_transport_style": config.agent_transport_style,
        "checkpoint_path": str(checkpoint_path) if checkpoint_path is not None else None,
        "resumed_from": str(resume_from) if resume_from is not None else None,
        "judge_max_workers": config.judge_max_workers,
        "run_config": {
            "target_total_turns": config.target_total_turns,
            "max_sessions_per_cell": config.max_sessions_per_cell,
            "play_only_story_ids": [record["story_id"] for record in fixed_story_pool],
            "proposal_provider_requested": "helper" if (config.use_helper_agent or config.use_helper_turn_agent) else "primary",
            "judge_provider_requested": "helper" if (config.use_helper_agent or config.use_helper_judge) else "primary",
            "checkpoint_every_sessions": config.checkpoint_every_sessions,
        },
        "progress": {
            "completed_turn_count": completed_turn_count,
            "target_total_turns": config.target_total_turns,
            "completed_cells": completed_cells,
            "total_cells": total_cells,
            "completed_sessions": current_session_count,
            "target_sessions": total_session_target,
            "capture_completed_sessions": len(all_sessions),
            "judge_completed_sessions": judged_completed_sessions,
            "judge_pending_sessions": judge_pending_sessions,
        },
        "fixed_story_pool": fixed_story_pool,
        "story_count": len(output_stories),
        "stories": output_stories,
        "cell_session_counts": cell_session_counts,
        "session_count": len(all_sessions),
        "completed_session_count": len(_completed_sessions_only(all_sessions)),
        "completed_turn_count": completed_turn_count,
        "proposal_metrics": proposal_metrics,
        "judge_metrics": judge_metrics,
        "agent_provider_mode_distribution": agent_provider_mode_distribution,
        "trace_eval": trace_eval,
        "per_story": per_story,
        "per_language": per_language,
        "follow_up_recommendations": _play_only_recommendations(trace_eval),
        "verdict": verdict,
    }


def _play_only_recommendations(trace_eval: dict[str, Any]) -> list[str]:
    issue_distribution = dict(trace_eval.get("trace_issue_distribution") or {})
    if not issue_distribution:
        return [
            "Current play-only sample is stable enough to use as the next comparison baseline.",
            "Keep helper judge isolated from the main runtime and compare future runs against this artifact shape.",
        ]
    dominant_bucket = max(issue_distribution.items(), key=lambda item: item[1])[0]
    if dominant_bucket == "stage1_plan_protocol_mismatch":
        return [
            "Tighten stage-1 render planning around strict JSON-only `PlayRenderPlanDraft` output.",
            "Add explicit anti-labeled-text examples because plaintext salvage still leaks plan labels into the first render pass.",
        ]
    if dominant_bucket == "quality_gate_rejection":
        return [
            "Strengthen state/payoff grounding in render and repair prompts before loosening any quality gate thresholds.",
            "Track which anchors are repeatedly omitted so prompt fixes stay targeted instead of broadening acceptance.",
        ]
    if dominant_bucket == "repair_instability":
        return [
            "Repair is still carrying too much runtime stability load; reduce repair dependence before increasing traffic further.",
            "Investigate whether repair failures correlate with timeout pressure, malformed primary output, or missing anchors.",
        ]
    if dominant_bucket == "language_contamination":
        return [
            "Add stronger language locking in render/repair prompts and keep contamination visible in trace summaries.",
            "Sample contaminated turns against prompt family and story language to see whether the leak is prompt- or provider-driven.",
        ]
    return [
        "Use the representative trace excerpts to tighten the next failure-specific fix instead of broad runtime changes.",
        "Keep proposal generation on the primary gateway and judge traffic on helper so runtime measurements stay comparable.",
    ]


def run_play_only_campaign(config: LiveApiPlaytestConfig) -> dict[str, Any]:
    _require_helper_agent_if_requested(
        use_helper_agent=config.use_helper_agent,
        use_helper_turn_agent=config.use_helper_turn_agent,
        use_helper_judge=config.use_helper_judge,
    )
    if (
        (config.use_helper_agent or config.use_helper_turn_agent or config.use_helper_judge)
        and config.agent_transport_style != "chat_completions"
    ):
        raise RuntimeError("play-only campaign helper paths require --agent-transport-style chat_completions")
    resume_payload = _load_play_only_resume_payload(config.resume_from) if config.resume_from is not None else None
    story_ids = _resolved_play_only_story_ids(config=config, resume_payload=resume_payload)
    checkpoint_json_path, checkpoint_md_path = _play_only_checkpoint_paths(config)
    story_records: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        library_db_path = Path(tmpdir) / "stories.sqlite3" if config.launch_server else None
        with _managed_server(config, library_db_path):
            session = requests.Session()
            try:
                for story_id in story_ids:
                    story_detail, fetch_elapsed_seconds = _get_story_detail(session, config.base_url, story_id)
                    story = dict(story_detail.get("story") or {})
                    play_overview = dict(story_detail.get("play_overview") or {})
                    story_records.append(
                        {
                            "story_id": str(story.get("story_id") or story_id),
                            "title": str(story.get("title") or ""),
                            "language": str(story.get("language") or "en"),
                            "turn_budget": _resolve_story_turn_budget(story_detail, config.max_turns),
                            "story_fetch_elapsed_seconds": fetch_elapsed_seconds,
                            "play_overview": play_overview,
                            "story_detail": story_detail,
                            "sessions": [],
                        }
                    )
            finally:
                session.close()
    if resume_payload is not None:
        resumed_stories = {
            str(record.get("story_id") or ""): dict(record)
            for record in list(resume_payload.get("stories") or [])
            if str(record.get("story_id") or "").strip()
        }
        for record in story_records:
            resumed_record = resumed_stories.get(record["story_id"])
            if resumed_record is not None:
                record["sessions"] = list(resumed_record.get("sessions") or [])
    cell_session_counts = _play_only_cell_counts_from_sessions(
        story_records=story_records,
        max_sessions_per_cell=config.max_sessions_per_cell,
        seeded_counts=dict((resume_payload or {}).get("cell_session_counts") or {}),
    )
    completed_turn_count = int((resume_payload or {}).get("completed_turn_count") or 0)
    if completed_turn_count <= 0:
        completed_turn_count = _play_only_completed_turn_count(story_records)
    sessions_since_checkpoint = 0
    capture_complete = bool(
        str((resume_payload or {}).get("capture_status") or "").strip() == "completed"
        or completed_turn_count >= config.target_total_turns
        or all(count >= config.max_sessions_per_cell for count in cell_session_counts.values())
    )

    checkpoint_payload = _build_play_only_campaign_payload(
        config=config,
        story_records=story_records,
        cell_session_counts=cell_session_counts,
        completed_turn_count=completed_turn_count,
        checkpoint_path=checkpoint_json_path,
        resume_from=config.resume_from,
        run_status="capture_completed" if capture_complete else "capture_running",
        capture_status="completed" if capture_complete else "running",
        judge_status="pending",
    )
    _write_play_only_checkpoint(
        path_json=checkpoint_json_path,
        path_md=checkpoint_md_path,
        payload=checkpoint_payload,
    )

    while not capture_complete:
        progressed = False
        for record in story_records:
            for persona in PERSONAS:
                cell_key = f"{record['story_id']}::{persona.persona_id}"
                if cell_session_counts[cell_key] >= config.max_sessions_per_cell:
                    continue
                session_record = _run_persona_story_capture_session_with_retry(
                    base_url=config.base_url,
                    story_detail=dict(record["story_detail"]),
                    persona=persona,
                    max_turns=int(record["turn_budget"]),
                    transport_style=config.agent_transport_style,
                    use_helper_agent=config.use_helper_agent,
                    use_helper_turn_agent=config.use_helper_turn_agent,
                    use_helper_judge=config.use_helper_judge,
                    enable_strategy_cache=True,
                )
                session_record["cell_session_index"] = cell_session_counts[cell_key] + 1
                record["sessions"].append(session_record)
                cell_session_counts[cell_key] += 1
                completed_turn_count += len(list(session_record.get("turns") or []))
                sessions_since_checkpoint += 1
                progressed = True
                capture_complete = bool(
                    completed_turn_count >= config.target_total_turns
                    or all(count >= config.max_sessions_per_cell for count in cell_session_counts.values())
                )
                if sessions_since_checkpoint >= config.checkpoint_every_sessions or capture_complete:
                    checkpoint_payload = _build_play_only_campaign_payload(
                        config=config,
                        story_records=story_records,
                        cell_session_counts=cell_session_counts,
                        completed_turn_count=completed_turn_count,
                        checkpoint_path=checkpoint_json_path,
                        resume_from=config.resume_from,
                        run_status="capture_completed" if capture_complete else "capture_running",
                        capture_status="completed" if capture_complete else "running",
                        judge_status="pending",
                    )
                    _write_play_only_checkpoint(
                        path_json=checkpoint_json_path,
                        path_md=checkpoint_md_path,
                        payload=checkpoint_payload,
                    )
                    sessions_since_checkpoint = 0
                if capture_complete:
                    break
            if capture_complete:
                break
        if not progressed:
            failed_payload = _build_play_only_campaign_payload(
                config=config,
                story_records=story_records,
                cell_session_counts=cell_session_counts,
                completed_turn_count=completed_turn_count,
                checkpoint_path=checkpoint_json_path,
                resume_from=config.resume_from,
                run_status="failed",
                capture_status="failed",
                judge_status="pending",
            )
            _write_play_only_checkpoint(
                path_json=checkpoint_json_path,
                path_md=checkpoint_md_path,
                payload=failed_payload,
            )
            return failed_payload

    capture_completed_payload = _build_play_only_campaign_payload(
        config=config,
        story_records=story_records,
        cell_session_counts=cell_session_counts,
        completed_turn_count=completed_turn_count,
        checkpoint_path=checkpoint_json_path,
        resume_from=config.resume_from,
        run_status="capture_completed",
        capture_status="completed",
        judge_status="pending",
    )
    _write_play_only_checkpoint(
        path_json=checkpoint_json_path,
        path_md=checkpoint_md_path,
        payload=capture_completed_payload,
    )

    pending_sessions = _pending_judge_sessions(story_records)
    if pending_sessions:
        judge_running_payload = _build_play_only_campaign_payload(
            config=config,
            story_records=story_records,
            cell_session_counts=cell_session_counts,
            completed_turn_count=completed_turn_count,
            checkpoint_path=checkpoint_json_path,
            resume_from=config.resume_from,
            run_status="judge_running",
            capture_status="completed",
            judge_status="running",
        )
        _write_play_only_checkpoint(
            path_json=checkpoint_json_path,
            path_md=checkpoint_md_path,
            payload=judge_running_payload,
        )
        _run_play_only_judge_phase(
            config=config,
            story_records=story_records,
            cell_session_counts=cell_session_counts,
            completed_turn_count=completed_turn_count,
            checkpoint_json_path=checkpoint_json_path,
            checkpoint_md_path=checkpoint_md_path,
        )

    payload = _build_play_only_campaign_payload(
        config=config,
        story_records=story_records,
        cell_session_counts=cell_session_counts,
        completed_turn_count=completed_turn_count,
        checkpoint_path=checkpoint_json_path,
        resume_from=config.resume_from,
        run_status="completed",
        capture_status="completed",
        judge_status="completed",
    )
    _write_play_only_checkpoint(
        path_json=checkpoint_json_path,
        path_md=checkpoint_md_path,
        payload=payload,
    )
    return payload


@contextmanager
def _managed_server(config: LiveApiPlaytestConfig, library_db_path: Path | None):
    if not config.launch_server:
        yield
        return
    if library_db_path is None:
        raise RuntimeError("library_db_path is required when --launch-server is used")
    parsed = urlparse(config.base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8010
    env = os.environ.copy()
    env["APP_STORY_LIBRARY_DB_PATH"] = str(library_db_path)
    env["APP_RUNTIME_STATE_DB_PATH"] = str((library_db_path.parent / "runtime_state.sqlite3").resolve())
    env["APP_PLAY_SESSION_TTL_SECONDS"] = str(config.session_ttl_seconds)
    env["APP_ENABLE_BENCHMARK_API"] = "1"
    if config.managed_server_content_prompt_profile:
        env["APP_CONTENT_PROMPT_PROFILE"] = config.managed_server_content_prompt_profile
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "rpg_backend.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("managed API server exited before becoming healthy")
            try:
                response = requests.get(f"{config.base_url}/health", timeout=1)
                if response.ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError("managed API server did not become healthy in time")
        yield
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def run_live_api_playtest(config: LiveApiPlaytestConfig) -> dict[str, Any]:
    _require_helper_agent_if_requested(use_helper_agent=config.use_helper_agent)
    rng = Random(config.seed) if config.seed is not None else Random()
    generated_seeds = build_story_seed_batch(rng=rng, story_count=config.story_count)
    stories: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        library_db_path = Path(tmpdir) / "stories.sqlite3" if config.launch_server else None
        with _managed_server(config, library_db_path):
            author_session = requests.Session()
            try:
                for generated_seed in generated_seeds:
                    story_record = _run_author_story(
                        session=author_session,
                        base_url=config.base_url,
                        generated_seed=generated_seed,
                        target_duration_minutes=config.target_duration_minutes,
                    )
                    if story_record.get("error") and _is_transient_benchmark_error(str(story_record.get("error"))):
                        story_record = _run_author_story(
                            session=author_session,
                            base_url=config.base_url,
                            generated_seed=generated_seed,
                            target_duration_minutes=config.target_duration_minutes,
                        )
                    if story_record.get("published_story") and story_record.get("story_detail"):
                        story_turn_budget = _resolve_story_turn_budget(story_record["story_detail"], config.max_turns)
                        story_record["sessions"] = _run_story_playtests(
                            base_url=config.base_url,
                            story_detail=story_record["story_detail"],
                            max_turns=story_turn_budget,
                            transport_style=config.agent_transport_style,
                            use_helper_agent=config.use_helper_agent,
                        )
                        story_record["turn_budget"] = story_turn_budget
                    else:
                        story_record["sessions"] = []
                        story_record["turn_budget"] = config.max_turns
                    stories.append(story_record)
            finally:
                author_session.close()
    observed_author_profiles = {
        str((story.get("diagnostics") or {}).get("content_prompt_profile") or "").strip()
        for story in stories
        if (story.get("diagnostics") or {}).get("content_prompt_profile")
    }
    observed_play_profiles = {
        str((session.get("diagnostics") or {}).get("content_prompt_profile") or "").strip()
        for story in stories
        for session in story.get("sessions", [])
        if (session.get("diagnostics") or {}).get("content_prompt_profile")
    }
    configured_profile = resolve_content_prompt_profile(
        config.managed_server_content_prompt_profile or get_settings().content_prompt_profile
    )
    scorecard = _build_scorecard(
        stories,
        target_story_count=len(generated_seeds),
        personas_per_story=len(PERSONAS),
    )
    if config.phase_id and "benchmark_driver_fixcheck" in config.phase_id:
        scorecard["passed"] = bool(scorecard.get("driver_fixcheck_passed"))
    return {
        "base_url": config.base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "launch_server": config.launch_server,
        "label": config.label,
        "phase_id": config.phase_id,
        "seed_set_id": config.seed_set_id or (f"seed-{config.seed}" if config.seed is not None else None),
        "arm": config.arm,
        "baseline_artifact": str(config.baseline_artifact) if config.baseline_artifact else None,
        "target_duration_minutes": config.target_duration_minutes,
        "agent_provider": _agent_provider_label(use_helper_agent=config.use_helper_agent),
        "agent_transport_style": config.agent_transport_style,
        "configured_content_prompt_profile": configured_profile,
        "observed_author_content_prompt_profiles": sorted(observed_author_profiles),
        "observed_play_content_prompt_profiles": sorted(observed_play_profiles),
        "personas": [persona.persona_id for persona in PERSONAS],
        "max_turns": config.max_turns,
        "story_count_requested": config.story_count,
        "story_count": len(generated_seeds),
        "stories": stories,
        "scorecard": scorecard,
        "polluted_by_driver": bool(scorecard.get("polluted_by_driver")),
        "driver_fixcheck_passed": bool(scorecard.get("driver_fixcheck_passed")),
    }


def run_turn_proposal_probe(config: LiveApiPlaytestConfig) -> dict[str, Any]:
    _require_helper_agent_if_requested(use_helper_agent=config.use_helper_agent)
    rng = Random(config.seed) if config.seed is not None else Random()
    generated_seeds = build_story_seed_batch(rng=rng, story_count=config.story_count)
    stories: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        library_db_path = Path(tmpdir) / "stories.sqlite3" if config.launch_server else None
        with _managed_server(config, library_db_path):
            author_session = requests.Session()
            try:
                for generated_seed in generated_seeds:
                    story_record = _run_author_story(
                        session=author_session,
                        base_url=config.base_url,
                        generated_seed=generated_seed,
                        target_duration_minutes=config.target_duration_minutes,
                    )
                    if story_record.get("error") and _is_transient_benchmark_error(str(story_record.get("error"))):
                        story_record = _run_author_story(
                            session=author_session,
                            base_url=config.base_url,
                            generated_seed=generated_seed,
                            target_duration_minutes=config.target_duration_minutes,
                        )
                    if story_record.get("published_story") and story_record.get("story_detail"):
                        story_record["probes"] = _run_story_turn_proposal_probes(
                            base_url=config.base_url,
                            story_detail=story_record["story_detail"],
                            transport_style=config.agent_transport_style,
                            use_helper_agent=config.use_helper_agent,
                        )
                    else:
                        story_record["probes"] = []
                    stories.append(story_record)
            finally:
                author_session.close()
    target_probe_count = len(generated_seeds) * len(PERSONAS)
    author_successes = sum(1 for story in stories if story.get("published_story"))
    all_probes = [probe for story in stories for probe in story.get("probes", [])]
    probe_success_count = sum(1 for probe in all_probes if probe.get("proposed_turn") and not probe.get("error"))
    benchmark_agent_error_distribution: dict[str, int] = {}
    benchmark_agent_turn_rejection_distribution: dict[str, int] = {}
    benchmark_agent_turn_max_output_tokens = 0
    benchmark_agent_transcript_window_entries = 0
    for probe in all_probes:
        _accumulate_distribution(benchmark_agent_error_distribution, dict(probe.get("agent_error_distribution") or {}))
        _accumulate_distribution(
            benchmark_agent_turn_rejection_distribution,
            dict(probe.get("agent_turn_rejection_distribution") or {}),
        )
        benchmark_agent_turn_max_output_tokens = max(
            benchmark_agent_turn_max_output_tokens,
            int(probe.get("agent_turn_max_output_tokens") or 0),
        )
        benchmark_agent_transcript_window_entries = max(
            benchmark_agent_transcript_window_entries,
            int(probe.get("agent_transcript_window_entries") or 0),
        )
    probe_summary = {
        "passed": (
            author_successes == len(generated_seeds)
            and probe_success_count == target_probe_count
            and all(bool(probe.get("agent_call_trace")) for probe in all_probes)
        ),
        "target_story_count": len(generated_seeds),
        "target_probe_count": target_probe_count,
        "author_publish_success_rate": round(author_successes / len(generated_seeds), 3) if generated_seeds else 0.0,
        "probe_success_count": probe_success_count,
        "probe_success_rate": round(probe_success_count / target_probe_count, 3) if target_probe_count else 0.0,
        "benchmark_agent_turn_max_output_tokens": benchmark_agent_turn_max_output_tokens,
        "benchmark_agent_transcript_window_entries": benchmark_agent_transcript_window_entries,
        "benchmark_agent_error_distribution": benchmark_agent_error_distribution,
        "benchmark_agent_turn_rejection_distribution": benchmark_agent_turn_rejection_distribution,
    }
    return {
        "mode": "turn_proposal_probe",
        "base_url": config.base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "launch_server": config.launch_server,
        "label": config.label,
        "phase_id": config.phase_id,
        "seed_set_id": config.seed_set_id or (f"seed-{config.seed}" if config.seed is not None else None),
        "arm": config.arm,
        "target_duration_minutes": config.target_duration_minutes,
        "agent_provider": _agent_provider_label(use_helper_agent=config.use_helper_agent),
        "agent_transport_style": config.agent_transport_style,
        "personas": [persona.persona_id for persona in PERSONAS],
        "story_count_requested": config.story_count,
        "story_count": len(generated_seeds),
        "stories": stories,
        "probe_summary": probe_summary,
    }


def run_stage1_spark_smoke(config: LiveApiPlaytestConfig) -> dict[str, Any]:
    _require_helper_agent_if_requested(use_helper_agent=config.use_helper_agent)
    language_runs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        library_db_path = Path(tmpdir) / "stories.sqlite3" if config.launch_server else None
        with _managed_server(config, library_db_path):
            session = requests.Session()
            try:
                for language in STAGE1_SMOKE_LANGUAGES:
                    language_runs.append(
                        _run_stage1_smoke_language(
                            session=session,
                            base_url=config.base_url,
                            language=language,
                            target_duration_minutes=config.target_duration_minutes,
                            transport_style=config.agent_transport_style,
                            use_helper_agent=config.use_helper_agent,
                        )
                    )
            finally:
                session.close()
    passed_count = sum(1 for item in language_runs if item.get("passed"))
    summary = {
        "passed": passed_count == len(STAGE1_SMOKE_LANGUAGES),
        "languages_total": len(STAGE1_SMOKE_LANGUAGES),
        "languages_passed": passed_count,
        "language_pass_rate": round(passed_count / len(STAGE1_SMOKE_LANGUAGES), 3) if STAGE1_SMOKE_LANGUAGES else 0.0,
        "failure_stage_distribution": {
            str(item.get("failure_stage") or "passed"): sum(
                1
                for candidate in language_runs
                if str(candidate.get("failure_stage") or "passed") == str(item.get("failure_stage") or "passed")
            )
            for item in language_runs
        },
        "max_author_elapsed_seconds": round(
            max(
                (
                    float((item.get("author") or {}).get("author_total_elapsed_seconds") or 0.0)
                    for item in language_runs
                ),
                default=0.0,
            ),
            3,
        ),
        "max_propose_turn_elapsed_seconds": round(
            max(
                (
                    float(persona.get("propose_turn_elapsed_seconds") or 0.0)
                    for item in language_runs
                    for persona in list((item.get("play") or {}).get("personas") or [])
                ),
                default=0.0,
            ),
            3,
        ),
    }
    return {
        "mode": "stage1_spark_smoke",
        "base_url": config.base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "launch_server": config.launch_server,
        "label": config.label,
        "phase_id": config.phase_id,
        "target_duration_minutes": config.target_duration_minutes,
        "agent_provider": _agent_provider_label(use_helper_agent=config.use_helper_agent),
        "agent_transport_style": config.agent_transport_style,
        "languages": list(STAGE1_SMOKE_LANGUAGES),
        "personas": [persona.persona_id for persona in PERSONAS],
        "runs": language_runs,
        "summary": summary,
    }


def write_play_only_campaign_artifacts(
    config: LiveApiPlaytestConfig,
    payload: dict[str, Any],
) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = config.label or "play_only_campaign"
    stem = f"{label}_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    md_path.write_text(_render_play_only_campaign_markdown(payload))
    return json_path, md_path


def _render_play_only_campaign_markdown(payload: dict[str, Any]) -> str:
    verdict = dict(payload.get("verdict") or {})
    proposal_metrics = dict(payload.get("proposal_metrics") or {})
    judge_metrics = dict(payload.get("judge_metrics") or {})
    trace_eval = dict(payload.get("trace_eval") or {})
    lines = [
        "# Play-Only Pressure Campaign",
        "",
        f"- Base URL: `{payload.get('base_url')}`",
        f"- Run status: `{payload.get('run_status')}`",
        f"- Capture status: `{payload.get('capture_status')}`",
        f"- Judge status: `{payload.get('judge_status')}`",
        f"- Agent transport: `{payload.get('agent_transport_style')}`",
        f"- Target turns: `{((payload.get('run_config') or {}).get('target_total_turns'))}`",
        f"- Completed turns: `{payload.get('completed_turn_count')}`",
        f"- Session count: `{payload.get('session_count')}`",
        f"- Completed sessions: `{payload.get('completed_session_count')}`",
        f"- Capture completed sessions: `{((payload.get('progress') or {}).get('capture_completed_sessions'))}`",
        f"- Judge completed sessions: `{((payload.get('progress') or {}).get('judge_completed_sessions'))}`",
        f"- Judge pending sessions: `{((payload.get('progress') or {}).get('judge_pending_sessions'))}`",
        f"- Proposal provider requested: `{((payload.get('run_config') or {}).get('proposal_provider_requested'))}`",
        f"- Judge provider requested: `{((payload.get('run_config') or {}).get('judge_provider_requested'))}`",
        f"- Judge max workers: `{payload.get('judge_max_workers')}`",
        f"- Checkpoint path: `{payload.get('checkpoint_path')}`",
        f"- Resumed from: `{payload.get('resumed_from')}`",
        f"- Partial checkpoint: `{payload.get('run_status') != 'completed'}`",
        f"- Overall pass: `{verdict.get('passed')}`",
        "",
        "## Failure Rate Table",
        "",
        f"- Empty narration rate: `{trace_eval.get('empty_narration_rate')}`",
        f"- Issue turn rate: `{trace_eval.get('issue_turn_rate')}`",
        f"- Stage-1 plan protocol mismatch: `{(trace_eval.get('trace_issue_distribution') or {}).get('stage1_plan_protocol_mismatch', 0)}`",
        f"- Quality gate rejection: `{(trace_eval.get('trace_issue_distribution') or {}).get('quality_gate_rejection', 0)}`",
        f"- Repair instability: `{(trace_eval.get('trace_issue_distribution') or {}).get('repair_instability', 0)}`",
        f"- Language contamination: `{(trace_eval.get('trace_issue_distribution') or {}).get('language_contamination', 0)}`",
        "",
        "## Provider Metrics",
        "",
        f"- Proposal provider distribution: `{proposal_metrics.get('provider_distribution')}`",
        f"- Proposal turn source distribution: `{proposal_metrics.get('turn_source_distribution')}`",
        f"- Proposal stage1 success rate: `{proposal_metrics.get('stage1_success_rate')}`",
        f"- Proposal stage2 rescue rate: `{proposal_metrics.get('stage2_rescue_rate')}`",
        f"- Judge provider distribution: `{judge_metrics.get('provider_distribution')}`",
        f"- Judge report source distribution: `{judge_metrics.get('report_source_distribution')}`",
        f"- Judge non-fallback rate: `{judge_metrics.get('judge_nonfallback_rate')}`",
        f"- Judge fallback rate: `{judge_metrics.get('judge_fallback_rate')}`",
        "",
        "## Per-Language Split",
        "",
    ]
    for language, summary in dict(payload.get("per_language") or {}).items():
        lines.append(
            f"- `{language}` turns=`{summary.get('turn_count')}` sessions=`{summary.get('session_count')}` "
            f"empty_rate=`{summary.get('empty_narration_rate')}` issue_rate=`{summary.get('issue_turn_rate')}` "
            f"issues=`{summary.get('trace_issue_distribution')}`"
        )
    lines.extend(["", "## Top Issue Clusters", ""])
    for bucket, count in sorted(
        dict(trace_eval.get("trace_issue_distribution") or {}).items(),
        key=lambda item: (-item[1], item[0]),
    )[:5]:
        lines.append(f"- `{bucket}` count=`{count}`")
    lines.extend(["", "## Representative Excerpts", ""])
    for bucket, examples in dict(trace_eval.get("representative_excerpts") or {}).items():
        if not examples:
            continue
        first = dict(examples[0] or {})
        lines.append(
            f"- `{bucket}` story=`{first.get('story_id')}` persona=`{first.get('persona_id')}` "
            f"turn=`{first.get('turn_index')}` excerpt=`{first.get('excerpt')}`"
        )
    lines.extend(["", "## Follow-Up Recommendations", ""])
    for item in list(payload.get("follow_up_recommendations") or []):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_artifacts(config: LiveApiPlaytestConfig, payload: dict[str, Any]) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = config.label or "live_api_playtest"
    stem = f"{label}_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    scorecard = dict(payload.get("scorecard") or {})
    actuals = dict(scorecard.get("actuals") or {})
    subjective_summary = dict(scorecard.get("subjective_summary") or {})
    lines = [
        "# Live Author->Play Benchmark",
        "",
        f"- Base URL: `{payload['base_url']}`",
        f"- Phase: `{payload.get('phase_id')}`",
        f"- Seed set: `{payload.get('seed_set_id')}`",
        f"- Arm: `{payload.get('arm')}`",
        f"- Target duration minutes: `{payload.get('target_duration_minutes')}`",
        f"- Agent provider: `{payload.get('agent_provider')}`",
        f"- Agent transport: `{payload.get('agent_transport_style')}`",
        f"- Content prompt profile: `{payload.get('configured_content_prompt_profile')}`",
        f"- Story count: `{payload['story_count']}`",
        f"- Personas per story: `{len(payload.get('personas') or [])}`",
        f"- Overall pass: `{scorecard.get('passed')}`",
        f"- Polluted by driver: `{scorecard.get('polluted_by_driver')}`",
        f"- Subjective reference only: `{scorecard.get('subjective_reference_only')}`",
        "",
        "## Scorecard",
        "",
        f"- Author publish success rate: `{actuals.get('author_publish_success_rate')}`",
        f"- Completed sessions: `{actuals.get('play_completed_sessions')}`",
        f"- Expired sessions: `{actuals.get('expired_sessions')}`",
        f"- Median create session seconds: `{actuals.get('median_create_session_seconds')}`",
        f"- Median first-submit seconds: `{actuals.get('median_first_submit_turn_seconds')}`",
        f"- P95 submit turn seconds: `{actuals.get('p95_submit_turn_seconds')}`",
        f"- Render fallback rate: `{actuals.get('render_fallback_rate')}`",
        f"- Heuristic interpret rate: `{actuals.get('heuristic_interpret_rate')}`",
        f"- Ending judge failed rate: `{actuals.get('ending_judge_failed_rate')}`",
        f"- Benchmark agent turn llm rate: `{actuals.get('benchmark_agent_turn_llm_rate')}`",
        f"- Benchmark agent turn llm salvage rate: `{actuals.get('benchmark_agent_turn_llm_salvage_rate')}`",
        f"- Benchmark agent turn fallback rate: `{actuals.get('benchmark_agent_turn_fallback_rate')}`",
        f"- Benchmark agent turn stage1 success rate: `{actuals.get('benchmark_agent_turn_stage1_success_rate')}`",
        f"- Benchmark agent turn stage2 rescue rate: `{actuals.get('benchmark_agent_turn_stage2_rescue_rate')}`",
        f"- Benchmark agent report llm rate: `{actuals.get('benchmark_agent_report_llm_rate')}`",
        f"- Benchmark agent report llm salvage partial rate: `{actuals.get('benchmark_agent_report_llm_salvage_partial_rate')}`",
        f"- Benchmark agent report fallback rate: `{actuals.get('benchmark_agent_report_fallback_rate')}`",
        f"- Benchmark agent report stage1 success rate: `{actuals.get('benchmark_agent_report_stage1_success_rate')}`",
        f"- Benchmark agent report stage2 rescue rate: `{actuals.get('benchmark_agent_report_stage2_rescue_rate')}`",
        f"- Judge non-fallback rate: `{actuals.get('judge_nonfallback_rate')}`",
        f"- Judge fallback rate: `{actuals.get('judge_fallback_rate')}`",
        f"- Playtest agent invalid JSON count: `{actuals.get('playtest_agent_invalid_json_count')}`",
        f"- Benchmark agent turn max output tokens: `{actuals.get('benchmark_agent_turn_max_output_tokens')}`",
        f"- Benchmark agent report max output tokens: `{actuals.get('benchmark_agent_report_max_output_tokens')}`",
        f"- Benchmark agent transcript window entries: `{actuals.get('benchmark_agent_transcript_window_entries')}`",
        f"- Agent trace coverage rate: `{actuals.get('agent_trace_coverage_rate')}`",
        f"- Play trace coverage rate: `{actuals.get('play_trace_coverage_rate')}`",
        f"- Trace labeled failure rate: `{actuals.get('trace_labeled_failure_rate')}`",
        f"- Identity confusion flag rate: `{actuals.get('player_identity_confusion_flag_rate')}`",
        f"- Flat state feedback flag rate: `{actuals.get('flat_state_feedback_flag_rate')}`",
        f"- Mean narration words per turn: `{actuals.get('mean_narration_word_count_per_turn')}`",
        f"- Content richness: `{actuals.get('content_richness')}`",
        f"- Late-half axis diversity per session: `{actuals.get('late_half_axis_diversity_per_session')}`",
        f"- Late-half stance target diversity per session: `{actuals.get('late_half_stance_target_diversity_per_session')}`",
        f"- Turn budget utilization: `{actuals.get('turn_budget_utilization')}`",
        f"- Early non-collapse ending count: `{actuals.get('early_non_collapse_ending_count')}`",
        f"- Late-game flatness flag rate: `{actuals.get('late_game_flatness_flag_rate')}`",
        f"- Author runtime cost (RMB): `{actuals.get('author_total_estimated_cost_rmb')}`",
        f"- Play runtime cost (RMB): `{actuals.get('play_runtime_total_estimated_cost_rmb')}`",
        f"- Benchmark agent cost (RMB): `{actuals.get('benchmark_agent_total_estimated_cost_rmb')}`",
        f"- Combined runtime cost (RMB): `{actuals.get('combined_runtime_total_estimated_cost_rmb')}`",
        "",
        "## Driver Errors",
        "",
    ]
    for key, value in dict(scorecard.get("benchmark_agent_error_distribution") or {}).items():
        lines.append(f"- `{key}` count=`{value}`")
    lines.extend(
        [
            "",
            "## Driver Rejections",
            "",
        ]
    )
    for key, value in dict(scorecard.get("benchmark_agent_turn_rejection_distribution") or {}).items():
        lines.append(f"- turn `{key}` count=`{value}`")
    for key, value in dict(scorecard.get("benchmark_agent_report_missing_field_distribution") or {}).items():
        lines.append(f"- report_missing `{key}` count=`{value}`")
    lines.extend(
        [
            "",
            "## Driver Fixcheck Gates",
            "",
        ]
    )
    for gate in list(scorecard.get("driver_fixcheck_gates") or []):
        lines.append(f"- `{gate['metric']}` passed=`{gate['passed']}`")
    lines.extend(
        [
            "",
        "## Subjective",
        "",
        f"- Avg narration coherence: `{subjective_summary.get('avg_narration_coherence')}`",
        f"- Avg suggested action relevance: `{subjective_summary.get('avg_suggested_action_relevance')}`",
        f"- Avg state feedback credibility: `{subjective_summary.get('avg_state_feedback_credibility')}`",
        f"- Avg ending satisfaction: `{subjective_summary.get('avg_ending_satisfaction')}`",
        f"- Avg overall player feel: `{subjective_summary.get('avg_overall_player_feel')}`",
        "",
        "## Stories",
        "",
        ]
    )
    for story in payload["stories"]:
        result = story.get("result") or {}
        published_story = story.get("published_story") or {}
        lines.extend(
            [
                f"### {story['slug']}",
                "",
                f"- Bucket: `{story['bucket_id']}`",
                f"- Seed: {story['seed']}",
                f"- Turn budget: `{story.get('turn_budget')}`",
                f"- Job: `{story['job_id']}` status=`{result.get('status')}`",
                f"- Published story: `{published_story.get('story_id')}` `{published_story.get('title')}`",
            ]
        )
        if story.get("error"):
            lines.append(f"- Error: `{story['error']}`")
        for session in story.get("sessions", []):
            lines.append(
                f"- `{session['persona_id']}` ending=`{(session['final_snapshot'].get('ending') or {}).get('ending_id', 'unfinished')}` "
                f"turns=`{session['final_snapshot'].get('turn_index')}`/{session.get('turn_budget')} forced_stop=`{session['forced_stop']}` "
                f"turn_source_llm_rate=`{round(sum(1 for turn in session.get('turns', []) if turn.get('agent_turn_source') == 'llm') / max(len(session.get('turns', [])), 1), 3)}` "
                f"turn_source_llm_salvage_rate=`{round(sum(1 for turn in session.get('turns', []) if turn.get('agent_turn_source') == 'llm_salvage') / max(len(session.get('turns', [])), 1), 3)}` "
                f"turn_source_fallback_rate=`{round(sum(1 for turn in session.get('turns', []) if turn.get('agent_turn_source') == 'fallback') / max(len(session.get('turns', [])), 1), 3)}` "
                f"driver_strategy=`{session.get('agent_driver_strategy')}` "
                f"report_source=`{session['agent_report'].get('source')}` "
                f"distinctness=`{session['agent_report']['ratings']['state_feedback_distinctness']}` "
                f"richness=`{session['agent_report']['ratings']['content_richness']}` "
                f"late_half_axes=`{(session.get('late_half_feedback_metrics') or {}).get('distinct_axis_count')}` "
                f"late_half_stances=`{(session.get('late_half_feedback_metrics') or {}).get('distinct_stance_count')}` "
                f"issue=`{session['agent_report'].get('strongest_issue')}`"
            )
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path


def write_compare_artifacts(config: LiveApiPlaytestConfig, compare_payload: dict[str, Any]) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = config.label or "live_api_abcompare"
    phase = config.phase_id or "phase"
    stem = f"{label}_{phase}_compare_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(compare_payload, ensure_ascii=False, indent=2))
    lines = [
        "# Live Author->Play A/B Compare",
        "",
        f"- Phase: `{compare_payload.get('phase_id')}`",
        f"- Seed set: `{compare_payload.get('seed_set_id')}`",
        f"- Baseline prompt profile: `{compare_payload.get('baseline_content_prompt_profile')}`",
        f"- Candidate prompt profile: `{compare_payload.get('candidate_content_prompt_profile')}`",
        f"- Overall pass: `{compare_payload.get('passed')}`",
        "",
        "## Gates",
        "",
    ]
    for gate in compare_payload.get("phase_gates", []):
        lines.append(f"- `{gate['metric']}` passed=`{gate['passed']}`")
    lines.extend(
        [
            "",
            "## Deltas",
            "",
        ]
    )
    for key, value in dict(compare_payload.get("delta_actuals") or {}).items():
        lines.append(f"- `{key}` delta=`{value}`")
    lines.extend(
        [
            "",
            "## Ending Distribution Shift",
            "",
        ]
    )
    for key, value in dict(compare_payload.get("ending_distribution_shift") or {}).items():
        lines.append(f"- `{key}` delta=`{value}`")
    lines.extend(
        [
            "",
            "## Subjective Deltas",
            "",
        ]
    )
    for key, value in dict(compare_payload.get("delta_subjective_summary") or {}).items():
        lines.append(f"- `{key}` delta=`{value}`")
    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path


def write_probe_artifacts(config: LiveApiPlaytestConfig, payload: dict[str, Any]) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = config.label or "turn_proposal_probe"
    stem = f"{label}_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    summary = dict(payload.get("probe_summary") or {})
    lines = [
        "# Turn Proposal Probe",
        "",
        f"- Base URL: `{payload['base_url']}`",
        f"- Phase: `{payload.get('phase_id')}`",
        f"- Seed set: `{payload.get('seed_set_id')}`",
        f"- Target duration minutes: `{payload.get('target_duration_minutes')}`",
        f"- Agent provider: `{payload.get('agent_provider')}`",
        f"- Agent transport: `{payload.get('agent_transport_style')}`",
        f"- Story count: `{payload.get('story_count')}`",
        f"- Personas per story: `{len(payload.get('personas') or [])}`",
        f"- Probe pass: `{summary.get('passed')}`",
        f"- Author publish success rate: `{summary.get('author_publish_success_rate')}`",
        f"- Probe success count: `{summary.get('probe_success_count')}` / `{summary.get('target_probe_count')}`",
        f"- Benchmark agent turn max output tokens: `{summary.get('benchmark_agent_turn_max_output_tokens')}`",
        f"- Benchmark agent transcript window entries: `{summary.get('benchmark_agent_transcript_window_entries')}`",
        "",
        "## Driver Errors",
        "",
    ]
    for key, value in dict(summary.get("benchmark_agent_error_distribution") or {}).items():
        lines.append(f"- `{key}` count=`{value}`")
    lines.extend(["", "## Driver Rejections", ""])
    for key, value in dict(summary.get("benchmark_agent_turn_rejection_distribution") or {}).items():
        lines.append(f"- `{key}` count=`{value}`")
    lines.extend(["", "## Stories", ""])
    for story in payload.get("stories", []):
        published_story = story.get("published_story") or {}
        lines.extend(
            [
                f"### {story['slug']}",
                "",
                f"- Bucket: `{story['bucket_id']}`",
                f"- Job: `{story['job_id']}` status=`{(story.get('result') or {}).get('status')}`",
                f"- Published story: `{published_story.get('story_id')}` `{published_story.get('title')}`",
            ]
        )
        if story.get("error"):
            lines.append(f"- Error: `{story['error']}`")
        for probe in story.get("probes", []):
            proposed_turn = probe.get("proposed_turn") or {}
            opening_snapshot = probe.get("opening_snapshot") or {}
            lines.append(
                f"- `{probe['persona_id']}` elapsed=`{probe.get('propose_turn_elapsed_seconds')}`s "
                f"driver_strategy=`{probe.get('agent_driver_strategy')}` "
                f"source=`{proposed_turn.get('source')}` attempt=`{proposed_turn.get('attempt')}` "
                f"beat=`{opening_snapshot.get('beat_title')}` "
                f"error=`{probe.get('error')}`"
            )
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path


def write_stage1_spark_smoke_artifacts(config: LiveApiPlaytestConfig, payload: dict[str, Any]) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = config.label or "stage1_spark_smoke"
    stem = f"{label}_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Stage-1 Spark Smoke",
        "",
        f"- Base URL: `{payload.get('base_url')}`",
        f"- Phase: `{payload.get('phase_id')}`",
        f"- Target duration minutes: `{payload.get('target_duration_minutes')}`",
        f"- Agent provider: `{payload.get('agent_provider')}`",
        f"- Agent transport: `{payload.get('agent_transport_style')}`",
        f"- Overall pass: `{summary.get('passed')}`",
        f"- Languages passed: `{summary.get('languages_passed')}` / `{summary.get('languages_total')}`",
        f"- Max author elapsed seconds: `{summary.get('max_author_elapsed_seconds')}`",
        f"- Max propose-turn elapsed seconds: `{summary.get('max_propose_turn_elapsed_seconds')}`",
        "",
        "## Failure Stage Distribution",
        "",
    ]
    for key, value in dict(summary.get("failure_stage_distribution") or {}).items():
        lines.append(f"- `{key}` count=`{value}`")
    lines.extend(["", "## Runs", ""])
    for run in payload.get("runs", []):
        author = dict(run.get("author") or {})
        play = dict(run.get("play") or {})
        lines.extend(
            [
                f"### {run.get('language')}",
                "",
                f"- Passed: `{run.get('passed')}`",
                f"- Failure stage: `{run.get('failure_stage')}`",
                f"- Error: `{run.get('error')}`",
                f"- Spark seed: `{((run.get('spark') or {}).get('prompt_seed'))}`",
                f"- Preview theme: `{((run.get('preview') or {}).get('primary_theme'))}`",
                f"- Author job: `{author.get('job_id')}` status=`{author.get('result_status')}`",
                f"- Story instance materialized count: `{author.get('story_instance_materialized_count')}`",
                f"- Story instance fallback count: `{author.get('story_instance_fallback_count')}`",
                f"- Gender lock violation count: `{author.get('gender_lock_violation_count')}`",
            ]
        )
        progress_snapshot = dict(author.get("progress_snapshot") or {})
        if progress_snapshot:
            lines.append(
                f"- Running detail: stage=`{progress_snapshot.get('stage')}` "
                f"substage=`{progress_snapshot.get('running_substage')}` "
                f"slot=`{progress_snapshot.get('running_slot_index')}`/`{progress_snapshot.get('running_slot_total')}` "
                f"capability=`{progress_snapshot.get('running_capability')}`"
            )
        for persona in list(play.get("personas") or []):
            lines.append(
                f"- `{persona.get('persona_id')}` propose=`{persona.get('propose_turn_elapsed_seconds')}`s "
                f"clean=`{persona.get('input_text_clean')}` turns_ok=`{persona.get('first_two_turns_success')}` "
                f"render=`{persona.get('render_source_distribution')}` error=`{persona.get('error')}`"
            )
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    if config.play_issue_inspect:
        from tools.play_benchmarks.play_issue_inspect import (
            PlayIssueInspectConfig,
            run_play_issue_inspect,
            write_artifacts as write_inspect_artifacts,
        )

        inspect_payload = run_play_issue_inspect(
            PlayIssueInspectConfig(
                base_url=config.base_url,
                output_dir=config.output_dir,
                launch_server=config.launch_server,
                story_id=config.inspect_story_id,
                language=config.inspect_language,  # type: ignore[arg-type]
                prompt_count=config.inspect_prompt_count,
                seed=config.seed,
                label=config.label,
                session_ttl_seconds=config.session_ttl_seconds,
                target_duration_minutes=config.target_duration_minutes,
                managed_server_content_prompt_profile=config.managed_server_content_prompt_profile,
            )
        )
        json_path, md_path = write_inspect_artifacts(
            PlayIssueInspectConfig(
                base_url=config.base_url,
                output_dir=config.output_dir,
                launch_server=config.launch_server,
                story_id=config.inspect_story_id,
                language=config.inspect_language,  # type: ignore[arg-type]
                prompt_count=config.inspect_prompt_count,
                seed=config.seed,
                label=config.label,
                session_ttl_seconds=config.session_ttl_seconds,
                target_duration_minutes=config.target_duration_minutes,
                managed_server_content_prompt_profile=config.managed_server_content_prompt_profile,
            ),
            inspect_payload,
        )
        print(
            json.dumps(
                {
                    "json": str(json_path),
                    "markdown": str(md_path),
                    "passed": bool((inspect_payload.get("summary") or {}).get("passed")),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if config.play_only_campaign:
        payload = run_play_only_campaign(config)
        json_path, md_path = write_play_only_campaign_artifacts(config, payload)
        print(
            json.dumps(
                {
                    "json": str(json_path),
                    "markdown": str(md_path),
                    "checkpoint_json": payload.get("checkpoint_path"),
                    "checkpoint_markdown": str(Path(str(payload.get("checkpoint_path"))).with_suffix(".md")) if payload.get("checkpoint_path") else None,
                    "passed": bool((payload.get("verdict") or {}).get("passed")),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if config.stage1_spark_smoke:
        payload = run_stage1_spark_smoke(config)
        json_path, md_path = write_stage1_spark_smoke_artifacts(config, payload)
        print(
            json.dumps(
                {
                    "json": str(json_path),
                    "markdown": str(md_path),
                    "passed": bool((payload.get("summary") or {}).get("passed")),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if config.probe_turn_proposal:
        payload = run_turn_proposal_probe(config)
        json_path, md_path = write_probe_artifacts(config, payload)
        print(
            json.dumps(
                {
                    "json": str(json_path),
                    "markdown": str(md_path),
                    "passed": bool((payload.get("probe_summary") or {}).get("passed")),
                }
            )
        )
        return 0
    payload = run_live_api_playtest(config)
    json_path, md_path = write_artifacts(config, payload)
    compare_json_path: str | None = None
    compare_md_path: str | None = None
    compare_passed: bool | None = None
    if config.baseline_artifact is not None:
        baseline_payload = json.loads(config.baseline_artifact.read_text())
        compare_payload = compare_benchmark_payloads(
            baseline_payload=baseline_payload,
            candidate_payload=payload,
            phase_id=config.phase_id,
            baseline_artifact=str(config.baseline_artifact),
        )
        compare_json, compare_md = write_compare_artifacts(config, compare_payload)
        compare_json_path = str(compare_json)
        compare_md_path = str(compare_md)
        compare_passed = bool(compare_payload.get("passed"))
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "passed": bool((payload.get("scorecard") or {}).get("passed")),
                "compare_json": compare_json_path,
                "compare_markdown": compare_md_path,
                "compare_passed": compare_passed,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
