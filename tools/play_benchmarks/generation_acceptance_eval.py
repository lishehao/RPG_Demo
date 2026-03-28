from __future__ import annotations

import argparse
import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

import requests

from tools.play_benchmarks import live_api_playtest
from tools.play_benchmarks.story_seed_factory import (
    GeneratedStorySeed,
    all_story_seed_bucket_ids,
    build_story_seed_for_bucket,
)

DEFAULT_OUTPUT_DIR = live_api_playtest.DEFAULT_OUTPUT_DIR
STORY_DISTRIBUTION_BY_DURATION: tuple[tuple[int, int], ...] = ((10, 4), (17, 3), (25, 3))
MIN_CAST_COUNT = 3
MAX_CAST_COUNT = 5
ENDING_PAYOFF_ACCEPTABLE_THRESHOLD = 4
ENDING_PAYOFF_JUDGE_AVG_THRESHOLD = 3.5
OVERALL_PLAYER_FEEL_THRESHOLD = 3.0
RENDER_FALLBACK_RATE_THRESHOLD = 0.05
ENDING_PAYOFF_ACCEPTABLE_RATE_THRESHOLD = 0.7
DOMINANT_ENDING_FAILURE_RATE_THRESHOLD = 0.2


@dataclass(frozen=True)
class GenerationAcceptanceEvalConfig:
    base_url: str
    output_dir: Path
    label: str | None
    launch_server: bool
    seed: int | None
    story_max_workers: int
    session_ttl_seconds: int
    max_turns: int | None
    agent_transport_style: live_api_playtest.TransportStyle
    judge_max_workers: int
    managed_server_content_prompt_profile: str | None
    reference_artifacts: tuple[Path, ...] = ()


@dataclass(frozen=True)
class IndependentJudgeLens:
    judge_id: str
    judge_label: str
    report_lens: str


INDEPENDENT_JUDGE_LENSES: tuple[IndependentJudgeLens, ...] = (
    IndependentJudgeLens(
        judge_id="ending_payoff_judge",
        judge_label="Ending Payoff Judge",
        report_lens="Judge whether the ending payoff feels earned, resolved, and satisfying rather than merely abrupt or mechanically complete.",
    ),
    IndependentJudgeLens(
        judge_id="system_clarity_judge",
        judge_label="System Clarity Judge",
        report_lens="Judge whether state feedback, consequence legibility, and turn-to-turn payoff tracking stay clear and mechanically distinct.",
    ),
    IndependentJudgeLens(
        judge_id="prose_variety_judge",
        judge_label="Prose Variety Judge",
        report_lens="Judge whether narration and suggestions stay fresh, non-repetitive, and texturally varied without collapsing into templates.",
    ),
)


def parse_args(argv: list[str] | None = None) -> GenerationAcceptanceEvalConfig:
    parser = argparse.ArgumentParser(description="Run 10-story generation acceptance evaluation with multi-judge play review.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--label")
    parser.add_argument("--launch-server", action="store_true")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--story-max-workers", type=int, default=10)
    parser.add_argument("--session-ttl-seconds", type=int, default=3600)
    parser.add_argument("--max-turns", type=int)
    parser.add_argument("--agent-transport-style", choices=("responses", "chat_completions"), default="chat_completions")
    parser.add_argument("--judge-max-workers", type=int, default=5)
    parser.add_argument("--managed-server-content-prompt-profile", choices=("plain", "role_conditioned"))
    parser.add_argument("--reference-artifacts", nargs="*")
    args = parser.parse_args(argv)
    return GenerationAcceptanceEvalConfig(
        base_url=str(args.base_url).rstrip("/"),
        output_dir=Path(args.output_dir).expanduser().resolve(),
        label=args.label,
        launch_server=bool(args.launch_server),
        seed=args.seed,
        story_max_workers=max(int(args.story_max_workers), 1),
        session_ttl_seconds=max(int(args.session_ttl_seconds), 60),
        max_turns=max(int(args.max_turns), 1) if args.max_turns is not None else None,
        agent_transport_style=str(args.agent_transport_style),  # type: ignore[arg-type]
        judge_max_workers=max(int(args.judge_max_workers), 1),
        managed_server_content_prompt_profile=args.managed_server_content_prompt_profile,
        reference_artifacts=tuple(
            Path(item).expanduser().resolve()
            for item in list(args.reference_artifacts or [])
        ),
    )


def _story_duration_assignments(*, rng: Random) -> list[tuple[GeneratedStorySeed, int]]:
    bucket_ids = rng.sample(list(all_story_seed_bucket_ids()), k=len(all_story_seed_bucket_ids()))
    assignments: list[tuple[GeneratedStorySeed, int]] = []
    index = 0
    for duration, count in STORY_DISTRIBUTION_BY_DURATION:
        for _ in range(count):
            bucket_id = bucket_ids[index]
            assignments.append(
                (
                    build_story_seed_for_bucket(
                        bucket_id,
                        rng=rng,
                    ),
                    duration,
                )
            )
            index += 1
    return assignments


def _judge_persona_sessions(
    *,
    story_detail: dict[str, Any],
    sessions: list[dict[str, Any]],
    transport_style: live_api_playtest.TransportStyle,
    judge_max_workers: int,
) -> list[dict[str, Any]]:
    if not sessions:
        return []
    updated: list[dict[str, Any] | None] = [None] * len(sessions)
    with ThreadPoolExecutor(max_workers=min(len(sessions), judge_max_workers)) as executor:
        futures = {
            executor.submit(
                live_api_playtest._judge_play_only_session,  # noqa: SLF001
                story_detail=story_detail,
                session=dict(session),
                transport_style=transport_style,
                enable_strategy_cache=True,
            ): index
            for index, session in enumerate(sessions)
        }
        for future in as_completed(futures):
            updated[futures[future]] = future.result()
    return [dict(item or {}) for item in updated]


def _build_independent_judge_persona(lens: IndependentJudgeLens) -> live_api_playtest.AgentPersona:  # noqa: SLF001
    return live_api_playtest.AgentPersona(  # noqa: SLF001
        persona_id=lens.judge_id,
        label=lens.judge_label,
        turn_style=lens.judge_label,
        decision_lens=lens.judge_label,
        report_lens=lens.report_lens,
    )


def _run_independent_judge(
    *,
    story_detail: dict[str, Any],
    session: dict[str, Any],
    lens: IndependentJudgeLens,
    transport_style: live_api_playtest.TransportStyle,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    judge_agent: live_api_playtest.PlaytestAgentClient | None = None  # noqa: SLF001
    try:
        judge_agent = live_api_playtest.PlaytestAgentClient(  # noqa: SLF001
            _build_independent_judge_persona(lens),
            transport_style=transport_style,
            provider="helper",
            enable_strategy_cache=True,
        )
        report = judge_agent.build_report(
            story_detail=story_detail,
            opening=str(session.get("opening") or ""),
            turns=list(session.get("turns") or []),
            final_snapshot=dict(session.get("final_snapshot") or {}),
            forced_stop=bool(session.get("forced_stop")),
        )
        provider = live_api_playtest._effective_agent_provider(judge_agent, requested_helper=True)  # noqa: SLF001
        return {
            "judge_id": lens.judge_id,
            "judge_label": lens.judge_label,
            "provider": provider,
            "report": report,
            "elapsed_seconds": round(time.perf_counter() - started_at, 3),
            "error": None,
            "report_source": str(report.get("source") or "fallback"),
        }
    except Exception as exc:  # noqa: BLE001
        report = live_api_playtest._deterministic_report_fallback(  # noqa: SLF001
            opening=str(session.get("opening") or ""),
            turns=list(session.get("turns") or []),
            final_snapshot=dict(session.get("final_snapshot") or {}),
            forced_stop=bool(session.get("forced_stop")),
        )
        provider = live_api_playtest._effective_agent_provider(judge_agent, requested_helper=True)  # noqa: SLF001
        return {
            "judge_id": lens.judge_id,
            "judge_label": lens.judge_label,
            "provider": provider,
            "report": report,
            "elapsed_seconds": round(time.perf_counter() - started_at, 3),
            "error": str(exc),
            "report_source": str(report.get("source") or "fallback"),
        }


def _attach_independent_judges(
    *,
    story_detail: dict[str, Any],
    sessions: list[dict[str, Any]],
    transport_style: live_api_playtest.TransportStyle,
    judge_max_workers: int,
) -> list[dict[str, Any]]:
    if not sessions:
        return []
    updated_sessions = [dict(session) for session in sessions]
    max_workers = min(len(updated_sessions) * len(INDEPENDENT_JUDGE_LENSES), judge_max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_independent_judge,
                story_detail=story_detail,
                session=session,
                lens=lens,
                transport_style=transport_style,
            ): (session_index, lens.judge_id)
            for session_index, session in enumerate(updated_sessions)
            for lens in INDEPENDENT_JUDGE_LENSES
        }
        report_rows: dict[int, list[dict[str, Any]]] = {index: [] for index in range(len(updated_sessions))}
        for future in as_completed(futures):
            session_index, _judge_id = futures[future]
            report_rows[session_index].append(future.result())
    for index, session in enumerate(updated_sessions):
        session["independent_judge_reports"] = sorted(
            report_rows.get(index, []),
            key=lambda item: str(item.get("judge_id") or ""),
        )
    return updated_sessions


def _in_range_cast_count(value: int) -> bool:
    return MIN_CAST_COUNT <= int(value) <= MAX_CAST_COUNT


def _safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def _story_final_cast_count(story: dict[str, Any]) -> int:
    published_story = dict(story.get("published_story") or {})
    if int(published_story.get("npc_count") or 0) > 0:
        return int(published_story.get("npc_count") or 0)
    preview = dict(story.get("preview") or {})
    return int(((preview.get("structure") or {}).get("expected_npc_count") or 0))


def _story_final_beat_count(story: dict[str, Any]) -> int:
    published_story = dict(story.get("published_story") or {})
    if int(published_story.get("beat_count") or 0) > 0:
        return int(published_story.get("beat_count") or 0)
    preview = dict(story.get("preview") or {})
    return int(((preview.get("story_flow_plan") or {}).get("target_beat_count") or 0))


def _story_turn_budget(story: dict[str, Any]) -> int:
    if int(story.get("turn_budget") or 0) > 0:
        return int(story.get("turn_budget") or 0)
    detail = dict(story.get("story_detail") or {})
    return int(((detail.get("play_overview") or {}).get("max_turns") or 0))


def _acceptance_summary_for_stories(stories: list[dict[str, Any]]) -> dict[str, Any]:
    def _group(target_duration_minutes: int | None) -> list[dict[str, Any]]:
        return [
            story
            for story in stories
            if target_duration_minutes is None
            or int(story.get("requested_target_duration_minutes") or 0) == int(target_duration_minutes)
        ]

    def _build(stories_for_group: list[dict[str, Any]]) -> dict[str, Any]:
        requested_story_count = len(stories_for_group)
        completed_author_jobs = sum(
            1
            for story in stories_for_group
            if str(((story.get("result") or {}).get("status") or "")) == "completed"
        )
        published_stories = sum(1 for story in stories_for_group if story.get("published_story"))
        preview_duration_matches = sum(
            1
            for story in stories_for_group
            if int((((story.get("preview") or {}).get("story_flow_plan") or {}).get("target_duration_minutes") or 0))
            == int(story.get("requested_target_duration_minutes") or 0)
        )
        preview_expected_cast_in_range = sum(
            1
            for story in stories_for_group
            if _in_range_cast_count(int((((story.get("preview") or {}).get("structure") or {}).get("expected_npc_count") or 0)))
        )
        final_cast_in_range = sum(
            1
            for story in stories_for_group
            if _in_range_cast_count(_story_final_cast_count(story))
        )
        final_cast_matches_preview_expected = sum(
            1
            for story in stories_for_group
            if _story_final_cast_count(story) == int((((story.get("preview") or {}).get("structure") or {}).get("expected_npc_count") or 0))
        )
        final_cast_matches_recommended = sum(
            1
            for story in stories_for_group
            if _story_final_cast_count(story) == int((((story.get("preview") or {}).get("story_flow_plan") or {}).get("recommended_cast_count") or 0))
        )
        beat_count_distribution: dict[str, int] = {}
        turn_budget_distribution: dict[str, int] = {}
        for story in stories_for_group:
            beat_key = str(_story_final_beat_count(story))
            turn_key = str(_story_turn_budget(story))
            beat_count_distribution[beat_key] = beat_count_distribution.get(beat_key, 0) + 1
            turn_budget_distribution[turn_key] = turn_budget_distribution.get(turn_key, 0) + 1
        return {
            "requested_story_count": requested_story_count,
            "completed_author_jobs": completed_author_jobs,
            "published_stories": published_stories,
            "preview_target_duration_match_rate": _safe_ratio(preview_duration_matches, requested_story_count),
            "preview_expected_npc_count_in_range_rate": _safe_ratio(preview_expected_cast_in_range, requested_story_count),
            "final_cast_count_in_range_rate": _safe_ratio(final_cast_in_range, requested_story_count),
            "final_cast_matches_preview_expected_rate": _safe_ratio(final_cast_matches_preview_expected, requested_story_count),
            "final_cast_matches_recommended_rate": _safe_ratio(final_cast_matches_recommended, requested_story_count),
            "final_beat_count_distribution": beat_count_distribution,
            "resolved_turn_budget_distribution": turn_budget_distribution,
        }

    per_duration = {
        str(duration): _build(_group(duration))
        for duration, _count in STORY_DISTRIBUTION_BY_DURATION
    }
    return {
        "overall": _build(stories),
        "per_duration": per_duration,
    }


def _average_rating(reports: list[dict[str, Any]], rating_key: str) -> float:
    values = [
        int((((item.get("report") or {}).get("ratings") or {}).get(rating_key) or 0))
        for item in reports
        if item.get("report")
    ]
    return round(sum(values) / len(values), 3) if values else 0.0


def _distribution(values: list[str]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for value in values:
        key = str(value or "").strip()
        if not key:
            continue
        distribution[key] = distribution.get(key, 0) + 1
    return distribution


def _independent_judge_report_rows(stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for story in stories:
        story_id = str((story.get("published_story") or {}).get("story_id") or (story.get("story_detail") or {}).get("story", {}).get("story_id") or "")
        for session in list(story.get("sessions") or []):
            for report in list(session.get("independent_judge_reports") or []):
                rows.append(
                    {
                        "story_id": story_id,
                        "persona_id": str(session.get("persona_id") or ""),
                        **dict(report),
                    }
                )
    return rows


def _build_independent_judge_metrics(stories: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _independent_judge_report_rows(stories)

    def _build(reports: list[dict[str, Any]]) -> dict[str, Any]:
        strongest_issue_distribution = _distribution(
            [str((item.get("report") or {}).get("strongest_issue") or "") for item in reports]
        )
        flag_distribution: dict[str, int] = {}
        for item in reports:
            for flag in list((item.get("report") or {}).get("flags") or []):
                flag_distribution[str(flag)] = flag_distribution.get(str(flag), 0) + 1
        return {
            "session_count": len(reports),
            "ending_satisfaction": _average_rating(reports, "ending_satisfaction"),
            "overall_player_feel": _average_rating(reports, "overall_player_feel"),
            "content_richness": _average_rating(reports, "content_richness"),
            "state_feedback_distinctness": _average_rating(reports, "state_feedback_distinctness"),
            "strongest_issue_distribution": strongest_issue_distribution,
            "flag_distribution": flag_distribution,
            "report_source_distribution": _distribution([str(item.get("report_source") or "") for item in reports]),
            "error_distribution": _distribution([str(item.get("error") or "") for item in reports if item.get("error")]),
        }

    by_judge = {
        lens.judge_id: {
            "judge_label": lens.judge_label,
            **_build([row for row in rows if str(row.get("judge_id") or "") == lens.judge_id]),
        }
        for lens in INDEPENDENT_JUDGE_LENSES
    }
    return {
        "overall": _build(rows),
        "by_judge": by_judge,
    }


def _build_independent_judge_consensus(stories: list[dict[str, Any]]) -> dict[str, Any]:
    session_rows: list[dict[str, Any]] = []
    disagreement_count = 0
    all_three_ending_payoff_acceptable_count = 0
    dominant_ending_failure_count = 0
    for story in stories:
        story_id = str((story.get("published_story") or {}).get("story_id") or (story.get("story_detail") or {}).get("story", {}).get("story_id") or "")
        for session in list(story.get("sessions") or []):
            reports = list(session.get("independent_judge_reports") or [])
            ending_values = [
                int((((report.get("report") or {}).get("ratings") or {}).get("ending_satisfaction") or 0))
                for report in reports
            ]
            overall_values = [
                int((((report.get("report") or {}).get("ratings") or {}).get("overall_player_feel") or 0))
                for report in reports
            ]
            ending_range = (max(ending_values) - min(ending_values)) if ending_values else 0
            overall_range = (max(overall_values) - min(overall_values)) if overall_values else 0
            if ending_range >= 2 or overall_range >= 2:
                disagreement_count += 1
            if reports and all(value >= ENDING_PAYOFF_ACCEPTABLE_THRESHOLD for value in ending_values):
                all_three_ending_payoff_acceptable_count += 1
            ending_failure_votes = 0
            for report in reports:
                ratings = (report.get("report") or {}).get("ratings") or {}
                flags = set((report.get("report") or {}).get("flags") or [])
                if int(ratings.get("ending_satisfaction") or 0) <= 2 or "ending_feels_unearned" in flags:
                    ending_failure_votes += 1
            if ending_failure_votes >= 2:
                dominant_ending_failure_count += 1
            session_rows.append(
                {
                    "story_id": story_id,
                    "persona_id": str(session.get("persona_id") or ""),
                    "ending_satisfaction_range": ending_range,
                    "overall_player_feel_range": overall_range,
                    "ending_satisfaction_values": ending_values,
                    "overall_player_feel_values": overall_values,
                }
            )
    total_sessions = len(session_rows)
    return {
        "session_count": total_sessions,
        "disagreement_count": disagreement_count,
        "disagreement_rate": _safe_ratio(disagreement_count, total_sessions),
        "all_three_ending_payoff_acceptable_count": all_three_ending_payoff_acceptable_count,
        "all_three_ending_payoff_acceptable_rate": _safe_ratio(all_three_ending_payoff_acceptable_count, total_sessions),
        "dominant_ending_failure_count": dominant_ending_failure_count,
        "dominant_ending_failure_rate": _safe_ratio(dominant_ending_failure_count, total_sessions),
        "sessions": session_rows,
    }


def _reference_summary(reference_artifacts: tuple[Path, ...]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path in reference_artifacts:
        payload = json.loads(path.read_text())
        trace = dict(payload.get("trace_eval") or {})
        judge = dict(payload.get("judge_metrics") or {})
        summaries.append(
            {
                "path": str(path),
                "label": payload.get("label"),
                "completed_turn_count": payload.get("completed_turn_count"),
                "empty_narration_rate": trace.get("empty_narration_rate"),
                "issue_turn_rate": trace.get("issue_turn_rate"),
                "render_source_distribution": trace.get("render_source_distribution"),
                "render_failure_reason_distribution": trace.get("render_failure_reason_distribution"),
                "avg_ending_satisfaction": judge.get("avg_ending_satisfaction"),
                "avg_overall_player_feel": judge.get("avg_overall_player_feel"),
                "avg_content_richness": judge.get("avg_content_richness"),
                "avg_state_feedback_distinctness": judge.get("avg_state_feedback_distinctness"),
            }
        )
    return summaries


def _build_acceptance_checks(
    *,
    stories: list[dict[str, Any]],
    scorecard: dict[str, Any],
    generation_acceptance_summary: dict[str, Any],
    independent_judge_metrics: dict[str, Any],
    independent_judge_consensus: dict[str, Any],
) -> list[dict[str, Any]]:
    overall_generation = dict(generation_acceptance_summary.get("overall") or {})
    actuals = dict(scorecard.get("actuals") or {})
    independent_overall = dict(independent_judge_metrics.get("overall") or {})
    checks = [
        {
            "metric": "author_publish_success_rate",
            "passed": int(overall_generation.get("published_stories") or 0) == len(stories),
            "actual": overall_generation.get("published_stories"),
            "expected": len(stories),
        },
        {
            "metric": "preview_target_duration_match_rate",
            "passed": float(overall_generation.get("preview_target_duration_match_rate") or 0.0) == 1.0,
            "actual": overall_generation.get("preview_target_duration_match_rate"),
            "expected": 1.0,
        },
        {
            "metric": "preview_expected_npc_count_in_range_rate",
            "passed": float(overall_generation.get("preview_expected_npc_count_in_range_rate") or 0.0) == 1.0,
            "actual": overall_generation.get("preview_expected_npc_count_in_range_rate"),
            "expected": 1.0,
        },
        {
            "metric": "final_cast_count_in_range_rate",
            "passed": float(overall_generation.get("final_cast_count_in_range_rate") or 0.0) == 1.0,
            "actual": overall_generation.get("final_cast_count_in_range_rate"),
            "expected": 1.0,
        },
        {
            "metric": "empty_narration_rate",
            "passed": float(actuals.get("empty_narration_rate") or 0.0) == 0.0,
            "actual": actuals.get("empty_narration_rate"),
            "expected": 0.0,
        },
        {
            "metric": "render_fallback_rate",
            "passed": float(actuals.get("render_fallback_rate") or 0.0) < RENDER_FALLBACK_RATE_THRESHOLD,
            "actual": actuals.get("render_fallback_rate"),
            "threshold": RENDER_FALLBACK_RATE_THRESHOLD,
        },
        {
            "metric": "independent_judge_completion",
            "passed": int(independent_overall.get("session_count") or 0) == (len(stories) * len(live_api_playtest.PERSONAS) * len(INDEPENDENT_JUDGE_LENSES)),  # noqa: SLF001
            "actual": independent_overall.get("session_count"),
            "expected": len(stories) * len(live_api_playtest.PERSONAS) * len(INDEPENDENT_JUDGE_LENSES),  # noqa: SLF001
        },
        {
            "metric": "ending_payoff_judge_avg",
            "passed": float((((independent_judge_metrics.get("by_judge") or {}).get("ending_payoff_judge") or {}).get("ending_satisfaction") or 0.0) >= ENDING_PAYOFF_JUDGE_AVG_THRESHOLD),
            "actual": (((independent_judge_metrics.get("by_judge") or {}).get("ending_payoff_judge") or {}).get("ending_satisfaction")),
            "threshold": ENDING_PAYOFF_JUDGE_AVG_THRESHOLD,
        },
        {
            "metric": "overall_player_feel",
            "passed": float(independent_overall.get("overall_player_feel") or 0.0) >= OVERALL_PLAYER_FEEL_THRESHOLD,
            "actual": independent_overall.get("overall_player_feel"),
            "threshold": OVERALL_PLAYER_FEEL_THRESHOLD,
        },
        {
            "metric": "all_three_ending_payoff_acceptable_rate",
            "passed": float(independent_judge_consensus.get("all_three_ending_payoff_acceptable_rate") or 0.0) >= ENDING_PAYOFF_ACCEPTABLE_RATE_THRESHOLD,
            "actual": independent_judge_consensus.get("all_three_ending_payoff_acceptable_rate"),
            "threshold": ENDING_PAYOFF_ACCEPTABLE_RATE_THRESHOLD,
        },
        {
            "metric": "dominant_ending_failure_rate",
            "passed": float(independent_judge_consensus.get("dominant_ending_failure_rate") or 0.0) <= DOMINANT_ENDING_FAILURE_RATE_THRESHOLD,
            "actual": independent_judge_consensus.get("dominant_ending_failure_rate"),
            "threshold": DOMINANT_ENDING_FAILURE_RATE_THRESHOLD,
        },
    ]
    return checks


def _build_verdict(checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "passed": all(bool(item.get("passed")) for item in checks),
        "checks": checks,
    }


def _run_generation_acceptance_story(
    *,
    config: GenerationAcceptanceEvalConfig,
    generated_seed: GeneratedStorySeed,
    target_duration_minutes: int,
) -> dict[str, Any]:
    session = requests.Session()
    try:
        story_record = live_api_playtest._run_author_story(  # noqa: SLF001
            session=session,
            base_url=config.base_url,
            generated_seed=generated_seed,
            target_duration_minutes=target_duration_minutes,
        )
        if story_record.get("error") and live_api_playtest._is_transient_benchmark_error(str(story_record.get("error"))):  # noqa: SLF001
            story_record = live_api_playtest._run_author_story(  # noqa: SLF001
                session=session,
                base_url=config.base_url,
                generated_seed=generated_seed,
                target_duration_minutes=target_duration_minutes,
            )
    finally:
        session.close()
    story_record["requested_target_duration_minutes"] = target_duration_minutes
    if story_record.get("published_story") and story_record.get("story_detail"):
        story_turn_budget = live_api_playtest._resolve_story_turn_budget(story_record["story_detail"], config.max_turns)  # noqa: SLF001
        with ThreadPoolExecutor(max_workers=len(live_api_playtest.PERSONAS)) as executor:  # noqa: SLF001
            capture_futures = [
                executor.submit(
                    live_api_playtest._run_persona_story_capture_session_with_retry,  # noqa: SLF001
                    base_url=config.base_url,
                    story_detail=story_record["story_detail"],
                    persona=persona,
                    max_turns=story_turn_budget,
                    transport_style=config.agent_transport_style,
                    use_helper_agent=False,
                    use_helper_turn_agent=False,
                    use_helper_judge=True,
                    enable_strategy_cache=True,
                )
                for persona in live_api_playtest.PERSONAS  # noqa: SLF001
            ]
        capture_sessions = [future.result() for future in capture_futures]
        judged_sessions = _judge_persona_sessions(
            story_detail=story_record["story_detail"],
            sessions=capture_sessions,
            transport_style=config.agent_transport_style,
            judge_max_workers=config.judge_max_workers,
        )
        story_record["sessions"] = _attach_independent_judges(
            story_detail=story_record["story_detail"],
            sessions=judged_sessions,
            transport_style=config.agent_transport_style,
            judge_max_workers=config.judge_max_workers,
        )
        story_record["turn_budget"] = story_turn_budget
    else:
        story_record["sessions"] = []
        story_record["turn_budget"] = config.max_turns
    return story_record


def run_generation_acceptance_eval(config: GenerationAcceptanceEvalConfig) -> dict[str, Any]:
    live_api_playtest._require_helper_agent_if_requested(use_helper_judge=True)  # noqa: SLF001
    rng = Random(config.seed) if config.seed is not None else Random()
    assignments = _story_duration_assignments(rng=rng)
    stories: list[dict[str, Any]] = []
    managed_config = live_api_playtest.LiveApiPlaytestConfig(  # noqa: SLF001
        base_url=config.base_url,
        output_dir=config.output_dir,
        label=config.label,
        launch_server=config.launch_server,
        session_ttl_seconds=config.session_ttl_seconds,
        max_turns=config.max_turns,
        seed=config.seed,
        story_count=10,
        phase_id="generation_acceptance_eval",
        seed_set_id=f"seed-{config.seed}" if config.seed is not None else None,
        arm="candidate",
        baseline_artifact=None,
        managed_server_content_prompt_profile=config.managed_server_content_prompt_profile,
        target_duration_minutes=25,
        probe_turn_proposal=False,
        agent_transport_style=config.agent_transport_style,
        use_helper_agent=False,
        use_helper_judge=True,
        judge_max_workers=config.judge_max_workers,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        library_db_path = Path(tmpdir) / "stories.sqlite3" if config.launch_server else None
        with live_api_playtest._managed_server(managed_config, library_db_path):  # noqa: SLF001
            ordered_stories: list[dict[str, Any] | None] = [None] * len(assignments)
            with ThreadPoolExecutor(max_workers=min(len(assignments), config.story_max_workers)) as executor:
                futures = {
                    executor.submit(
                        _run_generation_acceptance_story,
                        config=config,
                        generated_seed=generated_seed,
                        target_duration_minutes=target_duration_minutes,
                    ): index
                    for index, (generated_seed, target_duration_minutes) in enumerate(assignments)
                }
                for future in as_completed(futures):
                    ordered_stories[futures[future]] = future.result()
            stories = [dict(item or {}) for item in ordered_stories]
    scorecard = live_api_playtest._build_scorecard(  # noqa: SLF001
        stories,
        target_story_count=len(assignments),
        personas_per_story=len(live_api_playtest.PERSONAS),  # noqa: SLF001
    )
    generation_acceptance_summary = _acceptance_summary_for_stories(stories)
    independent_judge_metrics = _build_independent_judge_metrics(stories)
    independent_judge_consensus = _build_independent_judge_consensus(stories)
    checks = _build_acceptance_checks(
        stories=stories,
        scorecard=scorecard,
        generation_acceptance_summary=generation_acceptance_summary,
        independent_judge_metrics=independent_judge_metrics,
        independent_judge_consensus=independent_judge_consensus,
    )
    return {
        "base_url": config.base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "launch_server": config.launch_server,
        "label": config.label,
        "seed": config.seed,
        "agent_transport_style": config.agent_transport_style,
        "durations": [duration for duration, _count in STORY_DISTRIBUTION_BY_DURATION],
        "duration_story_distribution": {str(duration): count for duration, count in STORY_DISTRIBUTION_BY_DURATION},
        "judge_panel": [
            {
                "judge_id": lens.judge_id,
                "judge_label": lens.judge_label,
                "report_lens": lens.report_lens,
            }
            for lens in INDEPENDENT_JUDGE_LENSES
        ],
        "stories": stories,
        "story_count": len(stories),
        "generation_acceptance_summary": generation_acceptance_summary,
        "scorecard": scorecard,
        "independent_judge_metrics": independent_judge_metrics,
        "independent_judge_consensus": independent_judge_consensus,
        "reference_summaries": _reference_summary(config.reference_artifacts),
        "verdict": _build_verdict(checks),
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    verdict = dict(payload.get("verdict") or {})
    generation_summary = dict((payload.get("generation_acceptance_summary") or {}).get("overall") or {})
    independent_metrics = dict((payload.get("independent_judge_metrics") or {}).get("overall") or {})
    consensus = dict(payload.get("independent_judge_consensus") or {})
    lines = [
        "# Generation Acceptance Eval",
        "",
        f"- Base URL: `{payload.get('base_url')}`",
        f"- Story count: `{payload.get('story_count')}`",
        f"- Durations: `{payload.get('durations')}`",
        f"- Verdict: `{verdict.get('passed')}`",
        "",
        "## Generation Acceptance",
        "",
        f"- Completed author jobs: `{generation_summary.get('completed_author_jobs')}`",
        f"- Published stories: `{generation_summary.get('published_stories')}`",
        f"- Preview duration match rate: `{generation_summary.get('preview_target_duration_match_rate')}`",
        f"- Preview cast-in-range rate: `{generation_summary.get('preview_expected_npc_count_in_range_rate')}`",
        f"- Final cast-in-range rate: `{generation_summary.get('final_cast_count_in_range_rate')}`",
        "",
        "## Independent Judge Summary",
        "",
        f"- Ending satisfaction: `{independent_metrics.get('ending_satisfaction')}`",
        f"- Overall player feel: `{independent_metrics.get('overall_player_feel')}`",
        f"- Content richness: `{independent_metrics.get('content_richness')}`",
        f"- State feedback distinctness: `{independent_metrics.get('state_feedback_distinctness')}`",
        f"- Disagreement rate: `{consensus.get('disagreement_rate')}`",
        f"- All-three ending payoff acceptable rate: `{consensus.get('all_three_ending_payoff_acceptable_rate')}`",
        f"- Dominant ending failure rate: `{consensus.get('dominant_ending_failure_rate')}`",
        "",
        "## Checks",
        "",
    ]
    for item in list(verdict.get("checks") or []):
        lines.append(
            f"- `{item.get('metric')}` passed=`{item.get('passed')}` actual=`{item.get('actual')}` "
            f"expected=`{item.get('expected', item.get('threshold'))}`"
        )
    return "\n".join(lines) + "\n"


def write_artifacts(config: GenerationAcceptanceEvalConfig, payload: dict[str, Any]) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = f"{config.label or 'generation_acceptance_eval'}_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    md_path.write_text(_render_markdown(payload))
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    payload = run_generation_acceptance_eval(config)
    json_path, md_path = write_artifacts(config, payload)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "passed": bool((payload.get("verdict") or {}).get("passed")),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
