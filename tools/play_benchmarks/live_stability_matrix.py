from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

import requests

from rpg_backend.author.contracts import StoryGenerationControls
from rpg_backend.author.planning import build_story_flow_plan
from tools.play_benchmarks import live_api_playtest
from tools.play_benchmarks.story_seed_factory import (
    GeneratedStorySeed,
    all_story_seed_bucket_ids,
    build_story_seed_batch,
    build_story_seed_for_bucket,
)
from tools.http_product_smoke import HttpProductSmokeConfig, _smoke_preflight

DEFAULT_OUTPUT_DIR = live_api_playtest.DEFAULT_OUTPUT_DIR
DEFAULT_MATRIX_DURATIONS: tuple[int, ...] = (10, 17, 25)
_FAILURE_STAGE_PRIORITY = {
    "full_live": 0,
    "turn_probe": 1,
    "author_job": 2,
    "publish": 3,
    "preview": 4,
    "spark": 5,
    "play_turn": 6,
    "play_create": 7,
    "aggregate": 8,
}
_PLAY_SESSION_ROUTE_PATTERN = re.compile(r"^/play/sessions/[^/]+$")
_PLAY_TURN_ROUTE_PATTERN = re.compile(r"^/play/sessions/[^/]+/turns$")
_HTTP_ERROR_PATTERN = re.compile(r"^(GET|POST|PATCH|PUT|DELETE)\s+(https?://[^:]+(?::\d+)?(?P<path>/[^: ]+))(?::\s*(?P<detail>.*))?$")
_BUCKET_EXPECTED_STRATEGIES: dict[str, dict[str, str]] = {
    "legitimacy_warning": {
        "family": "warning_record_*",
        "story_frame_strategy": "warning_record_story",
        "cast_strategy": "warning_record_cast",
        "beat_plan_strategy": "warning_record_compile",
    },
    "ration_infrastructure": {
        "family": "bridge_ration_*",
        "story_frame_strategy": "bridge_ration_story",
        "cast_strategy": "bridge_ration_cast",
        "beat_plan_strategy": "bridge_ration_compile",
    },
    "blackout_panic": {
        "family": "blackout_referendum_*",
        "story_frame_strategy": "blackout_referendum_story",
        "cast_strategy": "blackout_referendum_cast",
        "beat_plan_strategy": "blackout_referendum_compile",
    },
    "harbor_quarantine": {
        "family": "harbor_quarantine_*",
        "story_frame_strategy": "harbor_quarantine_story",
        "cast_strategy": "harbor_quarantine_cast",
        "beat_plan_strategy": "harbor_quarantine_compile",
    },
    "archive_vote_record": {
        "family": "archive_vote_*",
        "story_frame_strategy": "archive_vote_story",
        "cast_strategy": "archive_vote_cast",
        "beat_plan_strategy": "archive_vote_compile",
    },
    "charter_oath_breach": {
        "family": "legitimacy_*",
        "story_frame_strategy": "legitimacy_story",
        "cast_strategy": "legitimacy_cast",
        "beat_plan_strategy": "conservative_direct_draft",
    },
    "checkpoint_corridor_access": {
        "family": "generic_civic_*",
        "story_frame_strategy": "generic_civic_story",
        "cast_strategy": "generic_civic_cast",
        "beat_plan_strategy": "conservative_direct_draft",
    },
    "customs_clearance_standoff": {
        "family": "harbor_quarantine_*",
        "story_frame_strategy": "harbor_quarantine_story",
        "cast_strategy": "harbor_quarantine_cast",
        "beat_plan_strategy": "harbor_quarantine_compile",
    },
    "shelter_capacity_surge": {
        "family": "bridge_ration_*",
        "story_frame_strategy": "bridge_ration_story",
        "cast_strategy": "bridge_ration_cast",
        "beat_plan_strategy": "bridge_ration_compile",
    },
    "testimony_release_timing": {
        "family": "archive_vote_*",
        "story_frame_strategy": "archive_vote_story",
        "cast_strategy": "archive_vote_cast",
        "beat_plan_strategy": "archive_vote_compile",
    },
}


@dataclass(frozen=True)
class LiveStabilityMatrixConfig:
    base_url: str
    output_dir: Path
    label: str | None
    launch_server: bool
    durations: tuple[int, ...]
    bucket_ids: tuple[str, ...]


def _smoke_config_for_preflight(config: LiveStabilityMatrixConfig) -> HttpProductSmokeConfig:
    return HttpProductSmokeConfig(
        base_url=config.base_url,
        language="en",
        prompt_seed="preflight",
        first_turn_input="preflight",
        copilot_message="preflight",
        poll_interval_seconds=0.5,
        poll_timeout_seconds=180.0,
        request_timeout_seconds=60.0,
        output_path=None,
        include_copilot=False,
        include_benchmark_diagnostics=True,
    )


def _default_bucket_ids() -> tuple[str, ...]:
    return all_story_seed_bucket_ids()


def parse_args(argv: list[str] | None = None) -> LiveStabilityMatrixConfig:
    parser = argparse.ArgumentParser(description="Run representative live stability matrix against the HTTP API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--label")
    parser.add_argument("--launch-server", action="store_true")
    parser.add_argument("--durations", default="10,17,25")
    parser.add_argument("--bucket-ids")
    args = parser.parse_args(argv)
    durations = tuple(
        sorted(
            {
                min(max(int(item.strip()), 10), 25)
                for item in str(args.durations).split(",")
                if item.strip()
            }
        )
    ) or DEFAULT_MATRIX_DURATIONS
    bucket_ids = tuple(
        item.strip()
        for item in str(args.bucket_ids or "").split(",")
        if item.strip()
    ) or _default_bucket_ids()
    return LiveStabilityMatrixConfig(
        base_url=args.base_url.rstrip("/"),
        output_dir=Path(args.output_dir).expanduser().resolve(),
        label=args.label,
        launch_server=bool(args.launch_server),
        durations=durations,
        bucket_ids=bucket_ids,
    )


def _expected_lane(duration_minutes: int) -> dict[str, int | str]:
    flow_plan = build_story_flow_plan(
        controls=StoryGenerationControls(target_duration_minutes=duration_minutes),
        primary_theme="truth_record_crisis",
    )
    return {
        "target_duration_minutes": flow_plan.target_duration_minutes,
        "expected_turn_count": flow_plan.target_turn_count,
        "expected_beat_count": flow_plan.target_beat_count,
        "expected_cast_count": flow_plan.recommended_cast_count,
        "branch_budget": flow_plan.branch_budget,
    }


def _stage1_smoke_config(config: LiveStabilityMatrixConfig) -> live_api_playtest.LiveApiPlaytestConfig:
    return live_api_playtest.LiveApiPlaytestConfig(
        base_url=config.base_url,
        output_dir=config.output_dir,
        label=(f"{config.label}_stage1" if config.label else "live_stability_stage1"),
        launch_server=False,
        session_ttl_seconds=3600,
        max_turns=None,
        seed=None,
        story_count=1,
        phase_id="live_stability_stage1",
        seed_set_id=None,
        arm="candidate",
        baseline_artifact=None,
        managed_server_content_prompt_profile=None,
        target_duration_minutes=min(config.durations),
        probe_turn_proposal=False,
        agent_transport_style="chat_completions",
        stage1_spark_smoke=True,
    )


def _run_preflight(config: LiveStabilityMatrixConfig) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "passed": False,
        "smoke_preflight": None,
        "health": None,
        "authenticated": False,
        "error": None,
    }
    try:
        smoke_preflight = _smoke_preflight(_smoke_config_for_preflight(config))
        if not bool(smoke_preflight.get("benchmark_api_enabled")):
            raise RuntimeError("benchmark api is disabled")
        summary["smoke_preflight"] = smoke_preflight
        with requests.Session() as session:
            health_payload, health_elapsed_seconds = live_api_playtest._request_json(  # noqa: SLF001
                session,
                "GET",
                f"{config.base_url}/health",
                timeout_seconds=15,
            )
            summary["health"] = {
                "status": health_payload.get("status"),
                "elapsed_seconds": health_elapsed_seconds,
            }
            auth_payload = live_api_playtest._authenticate_session(  # noqa: SLF001
                session,
                config.base_url,
                label="live-stability-preflight",
            )
            summary["authenticated"] = bool(auth_payload.get("authenticated"))
        summary["passed"] = bool(summary["authenticated"]) and str((summary["health"] or {}).get("status") or "") == "ok"
        return summary
    except Exception as exc:  # noqa: BLE001
        summary["error"] = str(exc)
        return summary


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


def _expected_strategy_family_for_bucket(bucket_id: str) -> dict[str, str]:
    return dict(_BUCKET_EXPECTED_STRATEGIES[str(bucket_id)])


def _safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def _call_with_single_retry(
    *,
    retry_state: dict[str, bool],
    fn,
):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        if retry_state.get("used", False) or not live_api_playtest._is_transient_benchmark_error(str(exc)):
            raise
        retry_state["used"] = True
        return fn()


def _route_template(path: str | None) -> str | None:
    normalized = str(path or "").strip()
    if not normalized:
        return None
    if _PLAY_TURN_ROUTE_PATTERN.match(normalized):
        return "/play/sessions/{id}/turns"
    if _PLAY_SESSION_ROUTE_PATTERN.match(normalized):
        return "/play/sessions/{id}"
    return normalized


def _error_context_from_message(message: str | None) -> dict[str, Any]:
    raw = str(message or "").strip()
    if not raw:
        return {}
    match = _HTTP_ERROR_PATTERN.match(raw)
    if not match:
        return {"message": raw}
    route = _route_template(match.group("path"))
    method = match.group(1)
    detail = str(match.group("detail") or "").strip() or raw
    return {
        "message": detail,
        "route": route,
        "operation": f"{method} {route}" if route else method,
    }


def _probe_failure_context(probes: list[dict[str, Any]]) -> dict[str, Any]:
    for probe in probes:
        input_text = str(((probe.get("proposed_turn") or {}).get("input_text")) or "").strip()
        agent_trace = list(probe.get("agent_call_trace") or [])
        if probe.get("error") or not input_text or not _proposal_text_is_clean(input_text) or not agent_trace:
            return {
                "persona_id": probe.get("persona_id"),
                "operation": "turn_probe",
                "message": str(probe.get("error") or "turn probe failed"),
            }
        for trace in agent_trace:
            if trace.get("error_code"):
                return {
                    "persona_id": probe.get("persona_id"),
                    "operation": "turn_probe",
                    "message": str(trace.get("error_message") or trace.get("error_code") or "turn probe failed"),
                }
    return {}


def _full_live_failure_context(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    for session in sessions:
        error = str(session.get("error") or "").strip()
        if not error:
            continue
        context = _error_context_from_message(error)
        route = str(context.get("route") or "")
        turn_index = None
        if route == "/play/sessions/{id}/turns":
            turn_index = len(list(session.get("turns") or [])) + 1
        return {
            "persona_id": session.get("persona_id"),
            "route": context.get("route"),
            "operation": context.get("operation"),
            "turn_index": turn_index,
            "substage": "play_turn" if route == "/play/sessions/{id}/turns" else "play_create" if route == "/play/sessions/{id}" else "full_live",
            "message": str(context.get("message") or error),
        }
    for session in sessions:
        if session.get("forced_stop"):
            final_snapshot = dict(session.get("final_snapshot") or {})
            return {
                "persona_id": session.get("persona_id"),
                "route": None,
                "operation": "full_live",
                "turn_index": final_snapshot.get("turn_index"),
                "substage": "full_live",
                "message": "session did not finish within the allotted turn budget",
            }
    return {}


def _blocking_cell_payload(cell: dict[str, Any]) -> dict[str, Any]:
    return {
        "bucket_id": cell.get("bucket_id"),
        "target_duration_minutes": cell.get("target_duration_minutes"),
        "seed_slug": cell.get("seed_slug"),
        "story_frame_strategy": cell.get("story_frame_strategy"),
        "cast_strategy": cell.get("cast_strategy"),
        "beat_plan_strategy": cell.get("beat_plan_strategy"),
        "selected_roster_templates": list(cell.get("selected_roster_templates") or []),
        "story_instance_materialized_count": cell.get("story_instance_materialized_count"),
        "story_instance_fallback_count": cell.get("story_instance_fallback_count"),
        "gender_lock_violation_count": cell.get("gender_lock_violation_count"),
        "failure_stage": cell.get("failure_stage"),
        "route": cell.get("route"),
        "operation": cell.get("operation"),
        "persona_id": cell.get("persona_id"),
        "turn_index": cell.get("turn_index"),
        "first_error": cell.get("first_error") or cell.get("error"),
    }


def _run_author_publish_for_cell(
    *,
    session: requests.Session,
    base_url: str,
    generated_seed: GeneratedStorySeed,
    target_duration_minutes: int,
    retry_state: dict[str, bool],
) -> dict[str, Any]:
    preview, preview_elapsed_seconds = _call_with_single_retry(
        retry_state=retry_state,
        fn=lambda: live_api_playtest._create_story_preview_with_controls(
            session,
            base_url,
            generated_seed.seed,
            target_duration_minutes=target_duration_minutes,
        ),
    )
    author_started_at = time.perf_counter()
    job, _job_elapsed_seconds = _call_with_single_retry(
        retry_state=retry_state,
        fn=lambda: live_api_playtest._create_author_job_with_controls(
            session,
            base_url,
            generated_seed.seed,
            str(preview["preview_id"]),
            target_duration_minutes=target_duration_minutes,
        ),
    )
    stream = _call_with_single_retry(
        retry_state=retry_state,
        fn=lambda: live_api_playtest._stream_author_job_to_terminal(session, base_url, str(job["job_id"])),
    )
    result, _result_elapsed_seconds = _call_with_single_retry(
        retry_state=retry_state,
        fn=lambda: live_api_playtest._get_author_job_result(session, base_url, str(job["job_id"])),
    )
    diagnostics = None
    diagnostics_elapsed_seconds = None
    diagnostics_error = None
    try:
        diagnostics, diagnostics_elapsed_seconds = _call_with_single_retry(
            retry_state=retry_state,
            fn=lambda: live_api_playtest._get_author_diagnostics(session, base_url, str(job["job_id"])),
        )
    except Exception as exc:  # noqa: BLE001
        diagnostics_error = str(exc)
    author_total_elapsed_seconds = round(time.perf_counter() - author_started_at, 3)
    published_story = None
    publish_elapsed_seconds = None
    story_detail = None
    detail_elapsed_seconds = None
    if str(result.get("status") or "") == "completed":
        published_story, publish_elapsed_seconds = _call_with_single_retry(
            retry_state=retry_state,
            fn=lambda: live_api_playtest._publish_author_job(session, base_url, str(job["job_id"])),
        )
        story_detail, detail_elapsed_seconds = _call_with_single_retry(
            retry_state=retry_state,
            fn=lambda: live_api_playtest._get_story_detail(session, base_url, str(published_story["story_id"])),
        )
    return {
        "preview": preview,
        "preview_elapsed_seconds": preview_elapsed_seconds,
        "job": job,
        "result": result,
        "diagnostics": diagnostics,
        "diagnostics_elapsed_seconds": diagnostics_elapsed_seconds,
        "diagnostics_error": diagnostics_error,
        "stream": stream,
        "author_total_elapsed_seconds": author_total_elapsed_seconds,
        "published_story": published_story,
        "publish_elapsed_seconds": publish_elapsed_seconds,
        "story_detail": story_detail,
        "detail_elapsed_seconds": detail_elapsed_seconds,
    }


def _build_full_live_scorecard(
    *,
    published_story: dict[str, Any],
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    story_payload = {
        "published_story": published_story,
        "diagnostics": {},
        "sessions": sessions,
    }
    return live_api_playtest._build_scorecard([story_payload], target_story_count=1, personas_per_story=2)


def _author_publish_observation(author_payload: dict[str, Any]) -> dict[str, Any]:
    diagnostics = dict(author_payload.get("diagnostics") or {})
    quality_trace = list(diagnostics.get("quality_trace") or [])
    roster_trace = list(diagnostics.get("roster_retrieval_trace") or [])
    cache_metrics = dict((author_payload.get("result") or {}).get("cache_metrics") or {})
    return {
        "job_id": (author_payload.get("job") or {}).get("job_id"),
        "author_total_elapsed_seconds": author_payload.get("author_total_elapsed_seconds"),
        "stream_elapsed_seconds": (author_payload.get("stream") or {}).get("stream_elapsed_seconds"),
        "publish_elapsed_seconds": author_payload.get("publish_elapsed_seconds"),
        "detail_elapsed_seconds": author_payload.get("detail_elapsed_seconds"),
        "result_status": (author_payload.get("result") or {}).get("status"),
        "published_story_id": (author_payload.get("published_story") or {}).get("story_id"),
        "published_story_title": (author_payload.get("published_story") or {}).get("title"),
        "diagnostics": {
            "status": diagnostics.get("status"),
            "error": diagnostics.get("error") or author_payload.get("diagnostics_error"),
            "source_summary": diagnostics.get("source_summary"),
            "stage_timings": diagnostics.get("stage_timings"),
            "llm_call_trace_len": len(list(diagnostics.get("llm_call_trace") or [])),
            "quality_trace_len": len(list(diagnostics.get("quality_trace") or [])),
            "cache_metrics_total_call_count": diagnostics.get("cache_metrics", {}).get("total_call_count")
            if isinstance(diagnostics.get("cache_metrics"), dict)
            else cache_metrics.get("total_call_count"),
            "content_prompt_profile": diagnostics.get("content_prompt_profile"),
        },
        "selected_roster_templates": live_api_playtest._selected_roster_templates(roster_trace),  # noqa: SLF001
        **live_api_playtest._story_instance_metrics(quality_trace),  # noqa: SLF001
        "passed": False,
        "error": None,
    }


def _turn_probe_observation(probes: list[dict[str, Any]]) -> dict[str, Any]:
    persona_items: list[dict[str, Any]] = []
    max_elapsed = 0.0
    failed_call_trace_count = 0
    for probe in probes:
        proposed_turn = dict(probe.get("proposed_turn") or {})
        input_text = str(proposed_turn.get("input_text") or "") or None
        call_trace = list(probe.get("agent_call_trace") or [])
        failed_call_trace_count += sum(1 for item in call_trace if item.get("error_code"))
        max_elapsed = max(max_elapsed, float(probe.get("propose_turn_elapsed_seconds") or 0.0))
        persona_items.append(
            {
                "persona_id": probe.get("persona_id"),
                "create_elapsed_seconds": probe.get("create_elapsed_seconds"),
                "propose_turn_elapsed_seconds": probe.get("propose_turn_elapsed_seconds"),
                "driver_strategy": probe.get("agent_driver_strategy"),
                "source": proposed_turn.get("source"),
                "attempt": proposed_turn.get("attempt"),
                "move_family": proposed_turn.get("move_family"),
                "input_text": input_text,
                "input_text_clean": _proposal_text_is_clean(input_text),
                "agent_call_trace": call_trace,
                "agent_error_distribution": probe.get("agent_error_distribution") or {},
                "agent_turn_rejection_distribution": probe.get("agent_turn_rejection_distribution") or {},
            }
        )
    return {
        "personas": persona_items,
        "both_personas_passed": False,
        "max_propose_turn_elapsed_seconds": round(max_elapsed, 3),
        "failed_call_trace_count": failed_call_trace_count,
        "passed": False,
        "error": None,
    }


def _full_live_observation(*, sessions: list[dict[str, Any]], scorecard: dict[str, Any]) -> dict[str, Any]:
    session_summaries: list[dict[str, Any]] = []
    for session in sessions:
        diagnostics_summary = dict((session.get("diagnostics") or {}).get("summary") or {})
        turns = list(session.get("turns") or [])
        narration_words = [
            int(turn.get("narration_word_count") or 0)
            for turn in turns
            if int(turn.get("narration_word_count") or 0) > 0
        ]
        session_summaries.append(
            {
                "persona_id": session.get("persona_id"),
                "ending_id": ((session.get("final_snapshot") or {}).get("ending") or {}).get("ending_id"),
                "turn_index": (session.get("final_snapshot") or {}).get("turn_index"),
                "forced_stop": session.get("forced_stop"),
                "turn_budget_utilization": session.get("turn_budget_utilization"),
                "render_source_distribution": diagnostics_summary.get("render_source_distribution") or {},
                "interpret_source_distribution": diagnostics_summary.get("interpret_source_distribution") or {},
                "ending_judge_source_distribution": diagnostics_summary.get("ending_judge_source_distribution") or {},
                "mean_narration_word_count": round(sum(narration_words) / len(narration_words), 3) if narration_words else 0.0,
                "agent_driver_strategy": session.get("agent_driver_strategy"),
            }
        )
    return {
        "scorecard_actuals": (scorecard.get("actuals") or {}),
        "polluted_by_driver": scorecard.get("polluted_by_driver"),
        "driver_fixcheck_passed": scorecard.get("driver_fixcheck_passed"),
        "sessions": session_summaries,
        "passed": False,
        "error": None,
    }


def _run_matrix_cell(
    *,
    base_url: str,
    generated_seed: GeneratedStorySeed,
    target_duration_minutes: int,
) -> dict[str, Any]:
    lane = _expected_lane(target_duration_minutes)
    cell: dict[str, Any] = {
        "bucket_id": generated_seed.bucket_id,
        "seed_slug": generated_seed.slug,
        "target_duration_minutes": target_duration_minutes,
        "expected_cast_count": lane["expected_cast_count"],
        "expected_beat_count": lane["expected_beat_count"],
        "expected_turn_count": lane["expected_turn_count"],
        "story_frame_strategy": None,
        "cast_strategy": None,
        "beat_plan_strategy": None,
        "selected_roster_templates": [],
        "story_instance_materialized_count": 0,
        "story_instance_fallback_count": 0,
        "gender_lock_violation_count": 0,
        "preview_passed": False,
        "author_publish_passed": False,
        "turn_probe_passed": False,
        "full_live_passed": None if target_duration_minutes != 25 else False,
        "failure_stage": None,
        "error": None,
        "first_error": None,
        "route": None,
        "operation": None,
        "persona_id": None,
        "turn_index": None,
        "retry_used": False,
        "observations": {
            "lane_expectation": lane,
            "preview": {"passed": False, "error": None},
            "author_publish": {"passed": False, "error": None},
            "turn_probe": {"passed": False, "error": None},
            "full_live": {"passed": None if target_duration_minutes != 25 else False, "error": None},
        },
    }
    retry_state = {"used": False}
    session = requests.Session()
    try:
        live_api_playtest._authenticate_session(
            session,
            base_url,
            label=f"matrix-{generated_seed.bucket_id}-{target_duration_minutes}",
        )
        author_payload = _run_author_publish_for_cell(
            session=session,
            base_url=base_url,
            generated_seed=generated_seed,
            target_duration_minutes=target_duration_minutes,
            retry_state=retry_state,
        )
        preview = dict(author_payload["preview"])
        structure = dict(preview.get("structure") or {})
        flow_plan = dict(preview.get("story_flow_plan") or {})
        expected_cast_count = int(lane["expected_cast_count"])
        expected_beat_count = int(lane["expected_beat_count"])
        expected_turn_count = int(lane["expected_turn_count"])
        cell.update(
            {
                "preview_elapsed_seconds": author_payload["preview_elapsed_seconds"],
                "preview_id": preview.get("preview_id"),
                "preview_target_turn_count": int(flow_plan.get("target_turn_count") or 0),
                "preview_target_beat_count": int(flow_plan.get("target_beat_count") or 0),
                "preview_expected_npc_count": int(structure.get("expected_npc_count") or 0),
                "job_id": author_payload["job"]["job_id"],
                "author_job_status": author_payload["result"].get("status"),
                "author_total_elapsed_seconds": author_payload["author_total_elapsed_seconds"],
                "published_story_id": author_payload["published_story"].get("story_id"),
                "published_story_title": author_payload["published_story"].get("title"),
                "story_detail": author_payload["story_detail"],
                "retry_used": retry_state["used"],
            }
        )
        cell["observations"]["preview"] = {
            "preview_elapsed_seconds": author_payload["preview_elapsed_seconds"],
            "preview_id": preview.get("preview_id"),
            "story_flow_plan.target_turn_count": int(flow_plan.get("target_turn_count") or 0),
            "story_flow_plan.target_beat_count": int(flow_plan.get("target_beat_count") or 0),
            "structure.expected_npc_count": int(structure.get("expected_npc_count") or 0),
            "theme.primary_theme": (preview.get("theme") or {}).get("primary_theme"),
            "strategies.story_frame_strategy": (preview.get("strategies") or {}).get("story_frame_strategy"),
            "strategies.cast_strategy": (preview.get("strategies") or {}).get("cast_strategy"),
            "strategies.beat_plan_strategy": (preview.get("strategies") or {}).get("beat_plan_strategy"),
            "bucket_strategy_expected": _expected_strategy_family_for_bucket(generated_seed.bucket_id)["family"],
            "strategy_family_consistent": False,
            "passed": False,
            "error": None,
        }
        expected_strategy = _expected_strategy_family_for_bucket(generated_seed.bucket_id)
        cell["story_frame_strategy"] = (preview.get("strategies") or {}).get("story_frame_strategy")
        cell["cast_strategy"] = (preview.get("strategies") or {}).get("cast_strategy")
        cell["beat_plan_strategy"] = (preview.get("strategies") or {}).get("beat_plan_strategy")
        strategy_family_consistent = (
            str((preview.get("strategies") or {}).get("story_frame_strategy") or "") == expected_strategy["story_frame_strategy"]
            and str((preview.get("strategies") or {}).get("cast_strategy") or "") == expected_strategy["cast_strategy"]
            and str((preview.get("strategies") or {}).get("beat_plan_strategy") or "") == expected_strategy["beat_plan_strategy"]
        )
        cell["observations"]["preview"]["strategy_family_consistent"] = strategy_family_consistent
        preview_matches_lane = (
            int(flow_plan.get("target_turn_count") or 0) == expected_turn_count
            and int(flow_plan.get("target_beat_count") or 0) == expected_beat_count
            and int(structure.get("expected_npc_count") or 0) == expected_cast_count
        )
        if not preview_matches_lane or not strategy_family_consistent:
            cell["failure_stage"] = "preview"
            cell["error"] = "preview lane mismatch" if not preview_matches_lane else "strategy family drift"
            cell["first_error"] = cell["error"]
            cell["operation"] = "preview_validation"
            cell["observations"]["preview"]["error"] = cell["error"]
            return cell
        cell["preview_passed"] = True
        cell["observations"]["preview"]["passed"] = True
        cell["author_publish_passed"] = True
        cell["observations"]["author_publish"] = _author_publish_observation(author_payload)
        author_publish_observation = cell["observations"]["author_publish"]
        cell["selected_roster_templates"] = list(author_publish_observation.get("selected_roster_templates") or [])
        cell["story_instance_materialized_count"] = int(author_publish_observation.get("story_instance_materialized_count") or 0)
        cell["story_instance_fallback_count"] = int(author_publish_observation.get("story_instance_fallback_count") or 0)
        cell["gender_lock_violation_count"] = int(author_publish_observation.get("gender_lock_violation_count") or 0)
        author_publish_passed = (
            str(author_publish_observation["result_status"] or "") == "completed"
            and bool(author_publish_observation["published_story_id"])
            and author_publish_observation["diagnostics"]["status"] is not None
        )
        if not author_publish_passed:
            cell["author_publish_passed"] = False
            cell["failure_stage"] = "author_job"
            cell["error"] = str(author_publish_observation["diagnostics"]["error"] or "author publish observation incomplete")
            cell["first_error"] = cell["error"]
            cell["operation"] = "author_publish_validation"
            cell["observations"]["author_publish"]["error"] = cell["error"]
            return cell
        cell["observations"]["author_publish"]["passed"] = True

        probes = _call_with_single_retry(
            retry_state=retry_state,
            fn=lambda: live_api_playtest._run_story_turn_proposal_probes(
                base_url=base_url,
                story_detail=author_payload["story_detail"],
            ),
        )
        cell["probes"] = probes
        cell["observations"]["turn_probe"] = _turn_probe_observation(probes)
        turn_probe_passed = (
            len(probes) == 2
            and all(probe.get("proposed_turn") for probe in probes)
            and all(not probe.get("error") for probe in probes)
            and all(bool(probe.get("agent_call_trace")) for probe in probes)
            and all(_proposal_text_is_clean((probe.get("proposed_turn") or {}).get("input_text")) for probe in probes)
            and all(not any(item.get("error_code") for item in list(probe.get("agent_call_trace") or [])) for probe in probes)
        )
        if not turn_probe_passed:
            context = _probe_failure_context(probes)
            cell["failure_stage"] = "turn_probe"
            cell["error"] = str(context.get("message") or "turn probe failed")
            cell["first_error"] = cell["error"]
            cell["operation"] = context.get("operation")
            cell["persona_id"] = context.get("persona_id")
            cell["retry_used"] = retry_state["used"]
            cell["observations"]["turn_probe"]["error"] = cell["error"]
            return cell
        cell["turn_probe_passed"] = True
        cell["observations"]["turn_probe"]["both_personas_passed"] = True
        cell["observations"]["turn_probe"]["passed"] = True
        if target_duration_minutes != 25:
            cell["retry_used"] = retry_state["used"]
            return cell

        max_turns = live_api_playtest._resolve_story_turn_budget(author_payload["story_detail"], None)
        sessions = _call_with_single_retry(
            retry_state=retry_state,
            fn=lambda: live_api_playtest._run_story_playtests(
                base_url=base_url,
                story_detail=author_payload["story_detail"],
                max_turns=max_turns,
            ),
        )
        cell["sessions"] = sessions
        full_live_scorecard = _build_full_live_scorecard(
            published_story=author_payload["published_story"],
            sessions=sessions,
        )
        cell["full_live_scorecard"] = full_live_scorecard
        cell["observations"]["full_live"] = _full_live_observation(
            sessions=sessions,
            scorecard=full_live_scorecard,
        )
        actuals = dict(full_live_scorecard.get("actuals") or {})
        full_live_passed = (
            int(actuals.get("play_completed_sessions") or 0) == 2
            and int(actuals.get("expired_sessions") or 0) == 0
            and not bool(full_live_scorecard.get("polluted_by_driver"))
            and bool(full_live_scorecard.get("driver_fixcheck_passed"))
        )
        cell["full_live_passed"] = full_live_passed
        if not full_live_passed:
            context = _full_live_failure_context(sessions)
            cell["failure_stage"] = "full_live"
            cell["error"] = str(context.get("message") or "full live subset did not meet stability gates")
            cell["first_error"] = cell["error"]
            cell["route"] = context.get("route")
            cell["operation"] = context.get("operation")
            cell["persona_id"] = context.get("persona_id")
            cell["turn_index"] = context.get("turn_index")
            cell["observations"]["full_live"]["error_context"] = context
            cell["observations"]["full_live"]["error"] = cell["error"]
        else:
            cell["observations"]["full_live"]["passed"] = True
        cell["retry_used"] = retry_state["used"]
        return cell
    except Exception as exc:  # noqa: BLE001
        if cell["failure_stage"] is None:
            if not cell["preview_passed"]:
                cell["failure_stage"] = "preview"
            elif not cell["author_publish_passed"]:
                cell["failure_stage"] = "author_job"
            elif not cell["turn_probe_passed"]:
                cell["failure_stage"] = "turn_probe"
            elif target_duration_minutes == 25:
                cell["failure_stage"] = "full_live"
        cell["error"] = str(exc)
        cell["first_error"] = cell["error"]
        cell["retry_used"] = retry_state["used"]
        failure_stage = str(cell["failure_stage"])
        observation = cell["observations"].get(failure_stage) if failure_stage in cell["observations"] else None
        if isinstance(observation, dict):
            observation["error"] = cell["error"]
        return cell
    finally:
        session.close()


def _build_matrix_summary(
    cells: list[dict[str, Any]],
    *,
    preflight_passed: bool = True,
    stage1_smoke_passed: bool = True,
) -> dict[str, Any]:
    total_cells = len(cells)
    preview_pass_count = sum(1 for cell in cells if cell.get("preview_passed"))
    author_publish_pass_count = sum(1 for cell in cells if cell.get("author_publish_passed"))
    turn_probe_pass_count = sum(1 for cell in cells if cell.get("turn_probe_passed"))
    strategy_consistency_pass_count = sum(
        1
        for cell in cells
        if bool(((cell.get("observations") or {}).get("preview") or {}).get("strategy_family_consistent"))
    )
    full_live_cells = [cell for cell in cells if cell.get("target_duration_minutes") == 25]
    full_live_pass_count = sum(1 for cell in full_live_cells if cell.get("full_live_passed") is True)
    core_cells_passed = sum(
        1
        for cell in cells
        if cell.get("preview_passed")
        and cell.get("author_publish_passed")
        and cell.get("turn_probe_passed")
    )
    cells_passed = sum(
        1
        for cell in cells
        if cell.get("preview_passed")
        and cell.get("author_publish_passed")
        and cell.get("turn_probe_passed")
        and (cell.get("target_duration_minutes") != 25 or cell.get("full_live_passed") is True)
    )
    max_author_elapsed = max((float(cell.get("author_total_elapsed_seconds") or 0.0) for cell in cells), default=0.0)
    max_preview_elapsed = max((float(cell.get("preview_elapsed_seconds") or 0.0) for cell in cells), default=0.0)
    max_turn_probe_elapsed = max(
        (
            float(probe.get("propose_turn_elapsed_seconds") or 0.0)
            for cell in cells
            for probe in cell.get("probes", [])
        ),
        default=0.0,
    )
    failure_stage_distribution: dict[str, int] = {}
    bucket_pass_matrix: dict[str, bool] = {}
    duration_pass_matrix: dict[str, bool] = {}
    strategy_drift_cells: list[dict[str, Any]] = []
    bucket_ids = sorted({str(cell.get("bucket_id")) for cell in cells})
    for bucket_id in bucket_ids:
        bucket_cells = [cell for cell in cells if str(cell.get("bucket_id")) == bucket_id]
        bucket_pass_matrix[bucket_id] = all(
            cell.get("preview_passed")
            and cell.get("author_publish_passed")
            and cell.get("turn_probe_passed")
            and (cell.get("target_duration_minutes") != 25 or cell.get("full_live_passed") is True)
            for cell in bucket_cells
        )
    durations = sorted({int(cell.get("target_duration_minutes") or 0) for cell in cells})
    for duration in durations:
        duration_cells = [cell for cell in cells if int(cell.get("target_duration_minutes") or 0) == duration]
        duration_pass_matrix[str(duration)] = all(
            cell.get("preview_passed")
            and cell.get("author_publish_passed")
            and cell.get("turn_probe_passed")
            and (cell.get("target_duration_minutes") != 25 or cell.get("full_live_passed") is True)
            for cell in duration_cells
        )
    for cell in cells:
        stage = str(cell.get("failure_stage") or "passed")
        failure_stage_distribution[stage] = failure_stage_distribution.get(stage, 0) + 1
        preview_observation = (cell.get("observations") or {}).get("preview") or {}
        if not bool(preview_observation.get("strategy_family_consistent", True)):
            strategy_drift_cells.append(
                {
                    "bucket_id": cell.get("bucket_id"),
                    "target_duration_minutes": cell.get("target_duration_minutes"),
                    "bucket_strategy_expected": preview_observation.get("bucket_strategy_expected"),
                    "story_frame_strategy": preview_observation.get("strategies.story_frame_strategy"),
                    "cast_strategy": preview_observation.get("strategies.cast_strategy"),
                    "beat_plan_strategy": preview_observation.get("strategies.beat_plan_strategy"),
                }
            )
    core_gate_passed = (
        total_cells > 0
        and core_cells_passed == total_cells
        and not strategy_drift_cells
    )
    full_live_gate_passed = (
        len(full_live_cells) > 0
        and all(cell.get("full_live_passed") is True for cell in full_live_cells)
    )
    blocking_cells = [
        _blocking_cell_payload(cell)
        for cell in sorted(
            [cell for cell in cells if not (
                cell.get("preview_passed")
                and cell.get("author_publish_passed")
                and cell.get("turn_probe_passed")
                and (cell.get("target_duration_minutes") != 25 or cell.get("full_live_passed") is True)
            )],
            key=lambda cell: (
                _FAILURE_STAGE_PRIORITY.get(str(cell.get("failure_stage") or ""), 99),
                -int(cell.get("target_duration_minutes") or 0),
                str(cell.get("bucket_id") or ""),
            ),
        )
    ]
    return {
        "passed": bool(preflight_passed and stage1_smoke_passed and core_gate_passed and full_live_gate_passed),
        "preflight_passed": bool(preflight_passed),
        "stage1_smoke_passed": bool(stage1_smoke_passed),
        "core_gate_passed": bool(core_gate_passed),
        "full_live_gate_passed": bool(full_live_gate_passed),
        "preview_pass_rate": round(preview_pass_count / total_cells, 3) if total_cells else 0.0,
        "author_publish_pass_rate": round(author_publish_pass_count / total_cells, 3) if total_cells else 0.0,
        "turn_probe_pass_rate": round(turn_probe_pass_count / total_cells, 3) if total_cells else 0.0,
        "strategy_consistency_pass_rate": round(strategy_consistency_pass_count / total_cells, 3) if total_cells else 0.0,
        "full_live_pass_rate": round(full_live_pass_count / len(full_live_cells), 3) if full_live_cells else 0.0,
        "core_cells_passed": core_cells_passed,
        "core_cells_total": total_cells,
        "full_live_cells_passed": full_live_pass_count,
        "full_live_cells_total": len(full_live_cells),
        "cells_passed": cells_passed,
        "cells_total": total_cells,
        "max_observed_preview_elapsed_seconds": round(max_preview_elapsed, 3),
        "max_observed_author_elapsed_seconds": round(max_author_elapsed, 3),
        "max_observed_turn_proposal_elapsed_seconds": round(max_turn_probe_elapsed, 3),
        "failure_stage_distribution": failure_stage_distribution,
        "bucket_pass_matrix": bucket_pass_matrix,
        "duration_pass_matrix": duration_pass_matrix,
        "strategy_drift_count": len(strategy_drift_cells),
        "strategy_drift_cells": strategy_drift_cells,
        "blocking_cells": blocking_cells[:5],
    }


def run_live_stability_matrix(config: LiveStabilityMatrixConfig) -> dict[str, Any]:
    seeds = [
        build_story_seed_for_bucket(
            bucket_id=bucket_id,
            rng=Random(bucket_id),
        )
        for bucket_id in config.bucket_ids
    ]
    cells: list[dict[str, Any]] = []
    preflight: dict[str, Any] = {}
    stage1_smoke: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory() as tmpdir:
        library_db_path = Path(tmpdir) / "stories.sqlite3" if config.launch_server else None
        with live_api_playtest._managed_server(  # noqa: SLF001
            live_api_playtest.LiveApiPlaytestConfig(
                base_url=config.base_url,
                output_dir=config.output_dir,
                label=config.label,
                launch_server=config.launch_server,
                session_ttl_seconds=3600,
                max_turns=None,
                seed=None,
                story_count=len(config.bucket_ids),
                phase_id="live_stability_matrix",
                seed_set_id=None,
                arm="candidate",
                baseline_artifact=None,
                managed_server_content_prompt_profile=None,
                target_duration_minutes=max(config.durations),
                probe_turn_proposal=False,
                agent_transport_style="chat_completions",
            ),
            library_db_path,
        ):
            preflight = _run_preflight(config)
            if bool(preflight.get("passed")):
                stage1_smoke = live_api_playtest.run_stage1_spark_smoke(_stage1_smoke_config(config))
            if bool(preflight.get("passed")) and bool(((stage1_smoke or {}).get("summary") or {}).get("passed")):
                for generated_seed in seeds:
                    for duration in config.durations:
                        cells.append(
                            _run_matrix_cell(
                                base_url=config.base_url,
                                generated_seed=generated_seed,
                                target_duration_minutes=duration,
                            )
                        )
    stage1_smoke_passed = bool(((stage1_smoke or {}).get("summary") or {}).get("passed"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": config.base_url,
        "label": config.label,
        "launch_server": config.launch_server,
        "durations": list(config.durations),
        "bucket_ids": list(config.bucket_ids),
        "preflight": preflight,
        "stage1_smoke": stage1_smoke,
        "cells": cells,
        "summary": _build_matrix_summary(
            cells,
            preflight_passed=bool(preflight.get("passed")),
            stage1_smoke_passed=stage1_smoke_passed,
        ),
    }


def write_artifacts(config: LiveStabilityMatrixConfig, payload: dict[str, Any]) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = config.label or "live_stability_matrix"
    stem = f"{label}_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Live Stability Matrix",
        "",
        f"- Base URL: `{payload['base_url']}`",
        f"- Durations: `{payload.get('durations')}`",
        f"- Bucket IDs: `{payload.get('bucket_ids')}`",
        f"- Overall verdict: `{summary.get('passed')}`",
        f"- Preflight passed: `{summary.get('preflight_passed')}`",
        f"- Stage-1 smoke passed: `{summary.get('stage1_smoke_passed')}`",
        f"- Core gate passed: `{summary.get('core_gate_passed')}`",
        f"- Full-live gate passed: `{summary.get('full_live_gate_passed')}`",
        f"- Cells passed: `{summary.get('cells_passed')}` / `{summary.get('cells_total')}`",
        f"- Core cells passed: `{summary.get('core_cells_passed')}` / `{summary.get('core_cells_total')}`",
        f"- Full-live cells passed: `{summary.get('full_live_cells_passed')}` / `{summary.get('full_live_cells_total')}`",
        f"- Preview pass rate: `{summary.get('preview_pass_rate')}`",
        f"- Author publish pass rate: `{summary.get('author_publish_pass_rate')}`",
        f"- Turn probe pass rate: `{summary.get('turn_probe_pass_rate')}`",
        f"- Strategy consistency pass rate: `{summary.get('strategy_consistency_pass_rate')}`",
        f"- Full live pass rate: `{summary.get('full_live_pass_rate')}`",
        f"- Max observed preview elapsed seconds: `{summary.get('max_observed_preview_elapsed_seconds')}`",
        f"- Max observed author elapsed seconds: `{summary.get('max_observed_author_elapsed_seconds')}`",
        f"- Max observed turn proposal elapsed seconds: `{summary.get('max_observed_turn_proposal_elapsed_seconds')}`",
        "",
        "## Preflight",
        "",
        f"- Passed: `{((payload.get('preflight') or {}).get('passed'))}`",
        f"- Health: `{(((payload.get('preflight') or {}).get('health')) or {}).get('status')}`",
        f"- Error: `{((payload.get('preflight') or {}).get('error'))}`",
        "",
        "## Stage-1 Smoke",
        "",
        f"- Passed: `{(((payload.get('stage1_smoke') or {}).get('summary')) or {}).get('passed')}`",
        f"- Languages passed: `{((((payload.get('stage1_smoke') or {}).get('summary')) or {}).get('languages_passed'))}` / `{((((payload.get('stage1_smoke') or {}).get('summary')) or {}).get('languages_total'))}`",
        "",
        "## Failure Stage Distribution",
        "",
    ]
    for key, value in dict(summary.get("failure_stage_distribution") or {}).items():
        lines.append(f"- `{key}` count=`{value}`")
    lines.extend(
        [
            "",
            "## Bucket Pass Matrix",
            "",
        ]
    )
    for key, value in dict(summary.get("bucket_pass_matrix") or {}).items():
        lines.append(f"- `{key}` passed=`{value}`")
    lines.extend(
        [
            "",
            "## Duration Pass Matrix",
            "",
        ]
    )
    for key, value in dict(summary.get("duration_pass_matrix") or {}).items():
        lines.append(f"- `{key}` passed=`{value}`")
    lines.extend(
        [
            "",
            "## Strategy Drift",
            "",
            f"- Drift count: `{summary.get('strategy_drift_count')}`",
        ]
    )
    for item in list(summary.get("strategy_drift_cells") or []):
        lines.append(
            f"- `{item.get('bucket_id')}` `duration={item.get('target_duration_minutes')}` "
            f"expected=`{item.get('bucket_strategy_expected')}` "
            f"actual=`{item.get('story_frame_strategy')}` / `{item.get('cast_strategy')}` / `{item.get('beat_plan_strategy')}`"
        )
    lines.extend(["", "## Blocking Cells", ""])
    for item in list(summary.get("blocking_cells") or []):
        lines.append(
            f"- `{item.get('bucket_id')}` `duration={item.get('target_duration_minutes')}` "
            f"stage=`{item.get('failure_stage')}` op=`{item.get('operation')}` route=`{item.get('route')}` "
            f"persona=`{item.get('persona_id')}` turn=`{item.get('turn_index')}` "
            f"error=`{item.get('first_error')}`"
        )
    lines.extend(
        [
            "",
            "## Cells",
        "",
        ]
    )
    for cell in payload.get("cells", []):
        lines.extend(
            [
                f"- `{cell['bucket_id']}` `duration={cell['target_duration_minutes']}` "
                f"preview=`{cell.get('preview_passed')}` author_publish=`{cell.get('author_publish_passed')}` "
                f"turn_probe=`{cell.get('turn_probe_passed')}` full_live=`{cell.get('full_live_passed')}` "
                f"failure_stage=`{cell.get('failure_stage')}` error=`{cell.get('error')}` "
                f"published_story=`{cell.get('published_story_title')}`",
            ]
        )
    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    payload = run_live_stability_matrix(config)
    json_path, md_path = write_artifacts(config, payload)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "passed": bool((payload.get("summary") or {}).get("passed"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
