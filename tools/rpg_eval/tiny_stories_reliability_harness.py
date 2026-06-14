from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from tools.rpg_eval.narrative_mock_user import (
    EpisodeMemory,
    MockTurnTrace,
    MockUserConfig,
    judge_episode_trajectory,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_SET_PATH = REPO_ROOT / "tools/rpg_eval/gold_sets/tiny_stories_reliability.json"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts/eval_tiny_stories/reliability_protocol_summary.json"
DEFAULT_LIVE_OUTPUT = REPO_ROOT / "artifacts/eval_tiny_stories/reliability_live_summary.json"
LIVE_ACCEPTED_SOURCE_LABELS = {"live", "live_repaired"}
LIVE_ACCEPTED_STATUSES = {"success", "repaired"}
REQUIRED_HEALTH_CONFIG = {
    "text_llm",
    "create_story_butler",
    "story_brief",
    "opening",
    "play_turns",
}
REQUIRED_LIVE_OPERATIONS = {
    "create.story_butler_turn",
    "narrative.story_brief",
    "narrative.opening",
    "narrative.advance_turn",
}
LIVE_ACCEPTANCE_SEED = (
    "At an awards gala, a publicist, a singer, and a sponsor discover the live trophy reveal is rigged. "
    "The player is the publicist who must protect the singer before the host walks onstage. No gore."
)
REQUIRED_CASES = {
    "arbitrary_input_smalltalk",
    "meta_help_input",
    "unsafe_prompt_redirect",
    "laundromat_not_fit_gate",
    "high_drama_awards_supported",
    "multi_turn_correction_supersedes_fact",
    "play_turn_consequence",
}
REQUIRED_FAILURE_CATEGORIES = {
    "environment",
    "provider",
    "schema",
    "unsafe_redirect",
    "not_fit_gate",
    "story_guide_intent",
    "brief_contract",
    "entity_hygiene",
    "opening_recovery",
    "step_judge",
    "trajectory_judge",
    "telemetry_missing",
    "normal_ui_leak",
    "artifact",
}


def _read_protocol(path: Path = GOLD_SET_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _protocol_failures(protocol: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    cases = protocol.get("cases")
    if not isinstance(cases, list):
        return [{"category": "schema", "stage": "load", "message": "cases must be a list"}]
    case_ids = {str(case.get("case_id") or "") for case in cases if isinstance(case, dict)}
    missing = sorted(REQUIRED_CASES.difference(case_ids))
    if missing:
        failures.append({
            "category": "schema",
            "stage": "case_catalog",
            "message": f"missing required cases: {', '.join(missing)}",
        })
    taxonomy = set(str(item) for item in protocol.get("failure_taxonomy") or [])
    missing_taxonomy = sorted(REQUIRED_FAILURE_CATEGORIES.difference(taxonomy))
    if missing_taxonomy:
        failures.append({
            "category": "schema",
            "stage": "failure_taxonomy",
            "message": f"missing failure categories: {', '.join(missing_taxonomy)}",
        })
    for case in cases:
        if not isinstance(case, dict):
            failures.append({"category": "schema", "stage": "case_catalog", "message": "case must be an object"})
            continue
        case_id = str(case.get("case_id") or "")
        if not case.get("surface"):
            failures.append({"category": "schema", "stage": case_id, "message": "surface is required"})
        if not case.get("expected"):
            failures.append({"category": "schema", "stage": case_id, "message": "expected contract is required"})
        if case.get("surface") == "create_story_butler" and not case.get("prompt_sequence"):
            failures.append({"category": "schema", "stage": case_id, "message": "prompt_sequence is required"})
    return failures


def _fixture_trajectory_summary() -> dict[str, Any]:
    trace = MockTurnTrace(
        turn_index=1,
        narrator_ord=2,
        role_id="founder",
        observation_summary={"latest_narrator": "Evan presses the contradiction."},
        selected_action={"chosen_option_index": 0, "selected_option_label": "Show the memo evidence"},
        runtime_output_summary={
            "npc_pulse": [{"npc_id": "evan", "shift": "wary"}],
            "inventory_delta": {"added": ["public contradiction"], "removed": []},
        },
        agent_plan_summary={
            "available": True,
            "stage_phase": "pressure",
            "expected_pressure": "medium",
        },
        step_judge_status="pass",
        step_judge_violation_codes=[],
        contract_judge_status="pass",
        contract_judge_violation_codes=[],
    )
    memory = EpisodeMemory(
        objective="Keep the vote alive while making the contradiction visible.",
        latest_narrator_ord=2,
        narrator_ord_path=[2],
        recent_observations=["Evan presses the contradiction."],
        observed_npc_ids=["evan"],
        npc_pulse_trend={"evan": ["wary"]},
        selected_option_handles=["show"],
        pressure_signal_count=1,
        objective_progress="medium",
    )
    result = judge_episode_trajectory(
        traces=[trace],
        memory=memory,
        config=MockUserConfig(mode="fixture", turn_budget=1, request_agent_trace=True),
        ending_detected=False,
    )
    return result.model_dump(mode="json")


def run_protocol_contract(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    protocol = _read_protocol()
    failures = _protocol_failures(protocol)
    trajectory = _fixture_trajectory_summary()
    case_results = []
    for case in protocol.get("cases") or []:
        case_id = str(case.get("case_id") or "")
        case_failures = [failure for failure in failures if failure["stage"] == case_id]
        status = "fail" if case_failures else "pass"
        evidence = "protocol contract present"
        if case_id == "play_turn_consequence":
            status = "pass" if trajectory["status"] in {"pass", "warn"} else "fail"
            evidence = trajectory["summary"]
        case_results.append({
            "case_id": case_id,
            "surface": case.get("surface"),
            "status": status,
            "evidence": evidence,
            "failure_category_if_bad": (case.get("expected") or {}).get("failure_category_if_bad"),
        })
    payload = {
        "schema_version": "tiny_stories_reliability_protocol_summary.v1",
        "mode": "protocol_contract",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold_set_id": protocol.get("gold_set_id"),
        "status": "fail" if failures or any(case["status"] == "fail" for case in case_results) else "pass",
        "case_count": len(case_results),
        "pass_count": sum(1 for case in case_results if case["status"] == "pass"),
        "failures": failures,
        "cases": case_results,
        "trajectory_judge": trajectory,
        "notes": [
            "This command validates the gold protocol and deterministic trajectory evidence.",
            "Final product preview validation must still use live browser telemetry.",
        ],
    }
    _write_json(output, payload)
    return payload


class LiveHarnessHTTPError(RuntimeError):
    def __init__(self, *, method: str, path: str, status: int | None, body: str) -> None:
        super().__init__(f"{method} {path} failed with status {status}: {body[:300]}")
        self.method = method
        self.path = path
        self.status = status
        self.body = body[:2000]


class LiveHarnessClient:
    def __init__(self, base_url: str, *, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, str | int | bool | None] | None = None,
        timeout: float | None = None,
    ) -> tuple[dict[str, Any], int]:
        suffix = path
        if query:
            clean_query = {key: str(value).lower() if isinstance(value, bool) else value for key, value in query.items() if value is not None}
            if clean_query:
                suffix = f"{path}?{urlencode(clean_query)}"
        url = f"{self.base_url}{suffix}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        started = time.monotonic()
        try:
            with self._opener.open(request, timeout=timeout or self.timeout) as response:
                raw = response.read().decode("utf-8")
                elapsed_ms = int((time.monotonic() - started) * 1000)
                if not raw:
                    return {}, elapsed_ms
                return json.loads(raw), elapsed_ms
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LiveHarnessHTTPError(method=method, path=path, status=exc.code, body=body) from exc
        except URLError as exc:
            raise LiveHarnessHTTPError(method=method, path=path, status=None, body=str(exc.reason)) from exc


def _live_failure(category: str, stage: str, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"category": category, "stage": stage, "message": message}
    payload.update(extra)
    return payload


def _health_failures(health: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if health.get("status") != "ok":
        failures.append(_live_failure("environment", "health", f"health status is {health.get('status')!r}"))
    for key in sorted(REQUIRED_HEALTH_CONFIG):
        if health.get(key) != "configured":
            failures.append(
                _live_failure(
                    "provider",
                    "health",
                    f"{key} is not configured",
                    key=key,
                    observed=health.get(key),
                )
            )
    return failures


def _load_live_events_from_runtime_db(
    runtime_db: Path | None,
    *,
    user_id: str,
    started_at: str,
) -> list[dict[str, Any]]:
    if runtime_db is None or not runtime_db.exists():
        return []
    conn = sqlite3.connect(runtime_db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT event_id, operation, status, source_label, latency_ms, operation_latency_ms,
               input_tokens, cached_input_tokens, output_tokens, total_tokens,
               retry_count, repair_count, fallback_reason, response_id,
               user_id, template_id, session_id, created_at
        FROM narrative_llm_call_events
        WHERE user_id = ? AND created_at >= ?
        ORDER BY event_id
        """,
        (user_id, started_at),
    ).fetchall()
    return [dict(row) for row in rows]


def _events_by_operation(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(str(event.get("operation") or ""), []).append(event)
    return grouped


def _live_operation_failures(
    events: list[dict[str, Any]],
    required_operations: set[str] = REQUIRED_LIVE_OPERATIONS,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    grouped = _events_by_operation(events)
    for operation in sorted(required_operations):
        operation_events = grouped.get(operation) or []
        if not operation_events:
            failures.append(
                _live_failure(
                    "telemetry_missing",
                    operation,
                    f"missing LLM telemetry for {operation}",
                )
            )
            continue
        fallback_or_non_live = [
            event for event in operation_events
            if event.get("status") == "fallback_used"
            or event.get("source_label") not in LIVE_ACCEPTED_SOURCE_LABELS
            or bool(event.get("fallback_reason"))
        ]
        if fallback_or_non_live:
            failures.append(
                _live_failure(
                    "provider",
                    operation,
                    f"{operation} recorded fallback or non-live telemetry",
                    observed=[
                        {
                            "status": event.get("status"),
                            "source_label": event.get("source_label"),
                            "fallback_reason": event.get("fallback_reason"),
                        }
                        for event in fallback_or_non_live
                    ],
                )
            )
            continue
        accepted = [
            event for event in operation_events
            if event.get("source_label") in LIVE_ACCEPTED_SOURCE_LABELS
            and event.get("status") in LIVE_ACCEPTED_STATUSES
            and not event.get("fallback_reason")
        ]
        if not accepted:
            failures.append(
                _live_failure(
                    "provider",
                    operation,
                    f"{operation} did not record an accepted live success",
                    observed=[
                        {
                            "status": event.get("status"),
                            "source_label": event.get("source_label"),
                            "fallback_reason": event.get("fallback_reason"),
                        }
                        for event in operation_events
                    ],
                )
            )
    return failures


def _session_event_failures(session_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    session_operations = {str(event.get("operation") or "") for event in session_events}
    for operation in ("narrative.opening", "narrative.advance_turn"):
        if operation not in session_operations:
            failures.append(
                _live_failure(
                    "telemetry_missing",
                    operation,
                    f"reviewer session telemetry endpoint did not include {operation}",
                )
            )
    return failures


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "operation": event.get("operation"),
        "status": event.get("status"),
        "source_label": event.get("source_label"),
        "latency_ms": event.get("latency_ms"),
        "operation_latency_ms": event.get("operation_latency_ms"),
        "input_tokens": event.get("input_tokens"),
        "cached_input_tokens": event.get("cached_input_tokens"),
        "output_tokens": event.get("output_tokens"),
        "total_tokens": event.get("total_tokens"),
        "retry_count": event.get("retry_count"),
        "repair_count": event.get("repair_count"),
        "fallback_reason": event.get("fallback_reason"),
        "template_id": event.get("template_id"),
        "session_id": event.get("session_id"),
        "created_at": event.get("created_at"),
    }


def _first_option_index(story: dict[str, Any]) -> int:
    messages = story.get("messages") or []
    narrators = [message for message in messages if message.get("role") == "narrator"]
    if not narrators:
        return 0
    options = narrators[-1].get("options") or []
    return 0 if options else 0


def run_live_acceptance(
    *,
    base_url: str,
    output: Path = DEFAULT_LIVE_OUTPUT,
    username: str = "portfolio_reviewer",
    seed: str = LIVE_ACCEPTANCE_SEED,
    runtime_db: Path | None = None,
    timeout: float = 150.0,
) -> dict[str, Any]:
    run_started_at = _utc_now_iso()
    client = LiveHarnessClient(base_url, timeout=timeout)
    failures: list[dict[str, Any]] = []
    api_latencies: dict[str, int] = {}
    stage_sources: dict[str, Any] = {}
    template_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
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

        guide, api_latencies["story_guide_ms"] = client.request_json(
            "POST",
            "/narrative/story-guide/turns",
            payload={"message": seed, "language": "en"},
            timeout=timeout,
        )
        stage_sources["story_guide"] = {
            "source": guide.get("source"),
            "status": guide.get("status"),
            "canShapeBrief": guide.get("canShapeBrief"),
            "reply_excerpt": str(guide.get("reply") or "")[:180],
        }
        if guide.get("source") not in LIVE_ACCEPTED_SOURCE_LABELS:
            failures.append(
                _live_failure(
                    "provider",
                    "create.story_butler_turn",
                    "Story Butler guide response was not live-backed",
                    observed_source=guide.get("source"),
                )
            )

        brief, api_latencies["story_brief_ms"] = client.request_json(
            "POST",
            "/narrative/story-briefs",
            payload={
                "seed": seed,
                "language": "en",
                "desired_tension_profile": "high_drama",
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
                "turn_budget": 8,
                "difficulty": "gauntlet",
                "language": "en",
                "story_brief": brief.get("brief"),
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

        story, api_latencies["story_with_trace_ms"] = client.request_json(
            "GET",
            f"/narrative/sessions/{session_id}/story",
            query={"agent_trace": True},
            timeout=timeout,
        )
        chosen_option_index = _first_option_index(story)

        turn, api_latencies["advance_turn_ms"] = client.request_json(
            "POST",
            f"/narrative/sessions/{session_id}/story/turns",
            payload={"chosen_option_index": chosen_option_index},
            query={"agent_trace": True},
            timeout=timeout,
        )
        agent_event_types = [
            event.get("event_type") for event in turn.get("agent_events") or []
            if isinstance(event, dict)
        ]
        stage_sources["advance_turn"] = {
            "is_complete": turn.get("is_complete"),
            "agent_event_types": agent_event_types,
        }
        if "step_judge" not in agent_event_types or "contract_judge" not in agent_event_types:
            failures.append(
                _live_failure(
                    "step_judge",
                    "narrative.advance_turn",
                    "advance turn did not return step/contract judge evidence",
                    agent_event_types=agent_event_types,
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
        failures.extend(_live_operation_failures(all_events))
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

    operation_events = {
        operation: [_event_summary(event) for event in events]
        for operation, events in sorted(_events_by_operation(all_events).items())
        if operation in REQUIRED_LIVE_OPERATIONS or operation.startswith("create.story_butler")
    }
    payload = {
        "schema_version": "tiny_stories_reliability_live_summary.v1",
        "mode": "live_acceptance",
        "generated_at": _utc_now_iso(),
        "run_started_at": run_started_at,
        "status": "fail" if failures else "pass",
        "base_url": base_url,
        "username": username,
        "seed_excerpt": seed[:220],
        "template_id": template_id,
        "session_id": session_id,
        "required_operations": sorted(REQUIRED_LIVE_OPERATIONS),
        "health_required": sorted(REQUIRED_HEALTH_CONFIG),
        "api_latencies_ms": api_latencies,
        "stage_sources": stage_sources,
        "failures": failures,
        "operation_events": operation_events,
        "session_llm_events": [_event_summary(event) for event in session_events],
        "runtime_db": str(runtime_db) if runtime_db is not None else None,
        "notes": [
            "This is the live acceptance path: it drives Story Butler, Story Brief, opening/template, Play turn, and reviewer telemetry APIs.",
            "A pass requires accepted live/live_repaired telemetry for all required operations and no fallback_reason on those rows.",
            "Protocol/fixture checks are separate and cheaper; they are not the main acceptance evidence.",
        ],
    }
    _write_json(output, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tiny Stories reliability protocol checks.")
    parser.add_argument(
        "--mode",
        choices=("protocol_contract", "live_acceptance"),
        default="protocol_contract",
        help="Which evaluation mode to run. live_acceptance exercises real backend LLM calls.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8350", help="Backend base URL for live_acceptance.")
    parser.add_argument("--username", default="portfolio_reviewer", help="Reviewer username for live_acceptance.")
    parser.add_argument("--seed", default=LIVE_ACCEPTANCE_SEED, help="Story seed for live_acceptance.")
    parser.add_argument(
        "--runtime-db",
        default=None,
        help="Runtime SQLite DB path for pre-session live telemetry validation. Defaults to APP_RUNTIME_STATE_DB_PATH.",
    )
    parser.add_argument("--timeout", type=float, default=150.0, help="Per-request timeout for live_acceptance.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path for summary JSON.")
    args = parser.parse_args()
    output = Path(args.output)
    if args.mode == "live_acceptance" and args.output == str(DEFAULT_OUTPUT):
        output = DEFAULT_LIVE_OUTPUT

    if args.mode == "live_acceptance":
        runtime_db = Path(args.runtime_db) if args.runtime_db else None
        if runtime_db is None:
            import os

            runtime_db_env = os.environ.get("APP_RUNTIME_STATE_DB_PATH")
            runtime_db = Path(runtime_db_env) if runtime_db_env else None
        payload = run_live_acceptance(
            base_url=args.base_url,
            output=output,
            username=args.username,
            seed=args.seed,
            runtime_db=runtime_db,
            timeout=args.timeout,
        )
    else:
        payload = run_protocol_contract(output)
    print(json.dumps({
        "status": payload["status"],
        "mode": payload["mode"],
        "case_count": payload.get("case_count"),
        "pass_count": payload.get("pass_count"),
        "template_id": payload.get("template_id"),
        "session_id": payload.get("session_id"),
        "failure_count": len(payload.get("failures") or []),
        "output": str(output),
    }, ensure_ascii=False))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
