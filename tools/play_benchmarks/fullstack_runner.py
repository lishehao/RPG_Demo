from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rpg_backend.author.contracts import AuthorBundleRequest
from rpg_backend.author.metrics import estimate_token_cost, summarize_cache_metrics
from rpg_backend.author.preview import build_author_preview_from_seed, build_author_story_summary
from rpg_backend.author.workflow import run_author_bundle
from rpg_backend.config import Settings
from rpg_backend.library.service import StoryLibraryService
from rpg_backend.library.storage import SQLiteStoryLibraryStorage
from rpg_backend.play.service import PlaySessionService
from tools.play_benchmarks.scenarios import SCENARIO_SUITES

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "benchmarks"


@dataclass(frozen=True)
class FullstackBenchmarkConfig:
    suite: str
    label: str | None
    output_dir: Path
    play_ttl_seconds: int


def parse_args(argv: list[str] | None = None) -> FullstackBenchmarkConfig:
    parser = argparse.ArgumentParser(description="Run fullstack author+play benchmark.")
    parser.add_argument("--suite", choices=sorted(SCENARIO_SUITES), default="stability_smoke")
    parser.add_argument("--label")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--play-ttl-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    return FullstackBenchmarkConfig(
        suite=args.suite,
        label=args.label,
        output_dir=Path(args.output_dir).expanduser().resolve(),
        play_ttl_seconds=max(int(args.play_ttl_seconds), 60),
    )


def _add_usage(total: dict[str, int], usage: dict[str, Any] | None) -> None:
    if not usage:
        return
    for key, value in usage.items():
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        total[key] = total.get(key, 0) + int(value)


def _summarize_play_usage(traces: list[Any]) -> dict[str, int]:
    total: dict[str, int] = {}
    for trace in traces:
        _add_usage(total, trace.interpret_usage)
        _add_usage(total, trace.ending_judge_usage)
        _add_usage(total, trace.pyrrhic_critic_usage)
        _add_usage(total, trace.render_usage)
    return total


def run_fullstack_benchmark(config: FullstackBenchmarkConfig) -> dict[str, Any]:
    scenarios = SCENARIO_SUITES[config.suite]
    story_frame_counter = Counter()
    beat_plan_counter = Counter()
    ending_source_counter = Counter()
    play_ending_counter = Counter()
    preview_theme_counter = Counter()
    author_theme_counter = Counter()
    stories: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(Path(tmpdir) / "stories.sqlite3")))
        play_service = PlaySessionService(
            story_library_service=library_service,
            settings=Settings(play_session_ttl_seconds=config.play_ttl_seconds),
        )
        for scenario in scenarios:
            preview = build_author_preview_from_seed(scenario.seed)
            result = run_author_bundle(AuthorBundleRequest(raw_brief=scenario.seed))
            author_theme = str(result.state.get("primary_theme") or preview.theme.primary_theme)
            preview_theme = str(preview.theme.primary_theme)
            story_frame_source = str(result.state.get("story_frame_source") or "unknown")
            beat_plan_source = str(result.state.get("beat_plan_source") or "unknown")
            ending_source = str(result.state.get("ending_source") or "unknown")
            story_frame_counter[story_frame_source] += 1
            beat_plan_counter[beat_plan_source] += 1
            ending_source_counter[ending_source] += 1
            preview_theme_counter[preview_theme] += 1
            author_theme_counter[author_theme] += 1
            llm_call_trace = list(result.state.get("llm_call_trace") or [])
            author_cache = summarize_cache_metrics(llm_call_trace)
            author_cost = estimate_token_cost(author_cache)
            summary = build_author_story_summary(result.bundle, primary_theme=author_theme)
            published = library_service.publish_story(
                source_job_id=result.run_id,
                prompt_seed=scenario.seed,
                summary=summary,
                preview=preview,
                bundle=result.bundle,
            )
            snapshot = play_service.create_session(published.story_id)
            for turn in scenario.turns:
                snapshot = play_service.submit_turn(
                    snapshot.session_id,
                    type("TurnRequest", (), {"input_text": turn, "selected_suggestion_id": None})(),
                )
                if snapshot.status != "active":
                    break
            traces = play_service.get_turn_traces(snapshot.session_id)
            ending = snapshot.ending.ending_id if snapshot.ending else "unfinished"
            play_ending_counter[ending] += 1
            stories.append(
                {
                    "slug": scenario.slug,
                    "seed": scenario.seed,
                    "story_id": published.story_id,
                    "title": published.title,
                    "preview_theme": preview_theme,
                    "author_theme": author_theme,
                    "theme_match": preview_theme == author_theme,
                    "story_frame_source": story_frame_source,
                    "beat_plan_source": beat_plan_source,
                    "route_affordance_source": str(result.state.get("route_affordance_source") or "unknown"),
                    "ending_source": ending_source,
                    "author_cache_metrics": author_cache.model_dump(mode="json"),
                    "author_cost_estimate": author_cost.model_dump(mode="json") if author_cost else None,
                    "play_session_id": snapshot.session_id,
                    "play_ending": ending,
                    "play_turn_count": len(traces),
                    "play_finished": snapshot.status == "completed",
                    "play_status": snapshot.status,
                    "play_ending_trigger_reasons": [trace.resolution.ending_trigger_reason for trace in traces if trace.resolution.ending_trigger_reason],
                    "play_usage": _summarize_play_usage(traces),
                    "stories_with_any_stance_change": any(bool(trace.resolution.stance_changes) for trace in traces),
                    "stories_with_any_nonzero_public_pressure_change": any(trace.resolution.axis_changes.get("public_panic", 0) != 0 for trace in traces),
                }
            )

    turn_cap_force_pyrrhic_count = sum(
        1
        for story in stories
        if "turn_cap_force:pyrrhic" in story["play_ending_trigger_reasons"]
    )
    judge_pyrrhic_count = sum(
        1
        for story in stories
        if any(reason in {"judge:pyrrhic", "judge_relaxed:pyrrhic"} for reason in story["play_ending_trigger_reasons"])
    )
    stories_with_any_stance_change = sum(1 for story in stories if story["stories_with_any_stance_change"])
    stories_with_any_nonzero_public_pressure_change = sum(1 for story in stories if story["stories_with_any_nonzero_public_pressure_change"])
    stories_with_zero_visible_feedback_mismatch_risk = sum(
        1
        for story in stories
        if story["stories_with_any_stance_change"] and story["stories_with_any_nonzero_public_pressure_change"]
    )
    unfinished_count = sum(1 for story in stories if not story["play_finished"])
    return {
        "suite": config.suite,
        "label": config.label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "story_count": len(stories),
        "author": {
            "preview_theme_distribution": dict(preview_theme_counter),
            "theme_distribution": dict(author_theme_counter),
            "theme_mismatch_count": sum(1 for story in stories if not story["theme_match"]),
            "story_frame_source_distribution": dict(story_frame_counter),
            "beat_plan_source_distribution": dict(beat_plan_counter),
            "ending_source_distribution": dict(ending_source_counter),
        },
        "play": {
            "ending_distribution": dict(play_ending_counter),
            "unfinished_count": unfinished_count,
            "unfinished_rate": round(unfinished_count / len(stories), 3),
            "avg_turn_count": round(sum(story["play_turn_count"] for story in stories) / len(stories), 3),
            "turn_cap_force_pyrrhic_count": turn_cap_force_pyrrhic_count,
            "judge_pyrrhic_count": judge_pyrrhic_count,
            "stories_with_any_stance_change": stories_with_any_stance_change,
            "stories_with_any_nonzero_public_pressure_change": stories_with_any_nonzero_public_pressure_change,
            "stories_with_zero_visible_feedback_mismatch_risk": stories_with_zero_visible_feedback_mismatch_risk,
        },
        "stories": stories,
    }


def write_artifacts(config: FullstackBenchmarkConfig, summary: dict[str, Any]) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = config.label or config.suite
    stem = f"fullstack_benchmark_{label}_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    md_lines = [
        "# Fullstack Benchmark",
        "",
        f"- Suite: `{config.suite}`",
        f"- Story count: `{summary['story_count']}`",
        f"- Theme mismatch count: `{summary['author']['theme_mismatch_count']}`",
        f"- Beat plan source: `{summary['author']['beat_plan_source_distribution']}`",
        f"- Ending distribution: `{summary['play']['ending_distribution']}`",
        f"- Unfinished rate: `{summary['play']['unfinished_rate']}`",
        f"- Turn-cap force pyrrhic count: `{summary['play']['turn_cap_force_pyrrhic_count']}`",
        f"- Judge pyrrhic count: `{summary['play']['judge_pyrrhic_count']}`",
    ]
    md_path.write_text("\n".join(md_lines) + "\n")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    summary = run_fullstack_benchmark(config)
    json_path, md_path = write_artifacts(config, summary)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
