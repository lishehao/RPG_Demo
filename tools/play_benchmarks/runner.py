from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rpg_backend.author.contracts import AuthorBundleRequest
from rpg_backend.author.preview import build_author_preview_from_seed, build_author_story_summary
from rpg_backend.author.workflow import run_author_bundle
from rpg_backend.config import Settings
from rpg_backend.library.service import StoryLibraryService
from rpg_backend.library.storage import SQLiteStoryLibraryStorage
from rpg_backend.play.gateway import PlayGatewayError
from rpg_backend.play.service import PlaySessionService
from tools.play_benchmarks.scenarios import PlayBenchmarkScenario, SCENARIO_SUITES

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "benchmarks"


@dataclass(frozen=True)
class PlayBenchmarkConfig:
    suite: str
    label: str | None
    output_dir: Path
    play_ttl_seconds: int


def parse_args(argv: list[str] | None = None) -> PlayBenchmarkConfig:
    parser = argparse.ArgumentParser(description="Run play telemetry A/B benchmark.")
    parser.add_argument("--suite", choices=sorted(SCENARIO_SUITES), default="stability_smoke")
    parser.add_argument("--label")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--play-ttl-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    return PlayBenchmarkConfig(
        suite=args.suite,
        label=args.label,
        output_dir=Path(args.output_dir).expanduser().resolve(),
        play_ttl_seconds=max(int(args.play_ttl_seconds), 60),
    )


def _no_gateway(_settings=None):
    raise PlayGatewayError(code="play_llm_config_missing", message="disabled_for_abtest", status_code=500)


def generate_published_stories(
    scenarios: list[PlayBenchmarkScenario],
    library_service: StoryLibraryService,
) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    for scenario in scenarios:
        preview = build_author_preview_from_seed(scenario.seed)
        result = run_author_bundle(AuthorBundleRequest(raw_brief=scenario.seed))
        primary_theme = result.state.get("primary_theme") or preview.theme.primary_theme
        summary = build_author_story_summary(result.bundle, primary_theme=primary_theme)
        story = library_service.publish_story(
            source_job_id=result.run_id,
            prompt_seed=scenario.seed,
            summary=summary,
            preview=preview,
            bundle=result.bundle,
        )
        published.append(
            {
                "slug": scenario.slug,
                "seed": scenario.seed,
                "story_id": story.story_id,
                "title": story.title,
                "theme": story.theme,
                "turns": list(scenario.turns),
            }
        )
    return published


def _play_story(
    *,
    service: PlaySessionService,
    story_id: str,
    turns: list[str],
    include_trace: bool,
) -> dict[str, Any]:
    created = service.create_session(story_id)
    result = {
        "story_id": story_id,
        "session_id": created.session_id,
        "opening_beat": created.beat_title,
        "turns": [],
    }
    for text in turns:
        snapshot = service.submit_turn(
            created.session_id,
            type("TurnRequest", (), {"input_text": text, "selected_suggestion_id": None})(),
        )
        result["turns"].append(
            {
                "input": text,
                "status": snapshot.status,
                "beat_index": snapshot.beat_index,
                "beat_title": snapshot.beat_title,
                "ending": snapshot.ending.ending_id if snapshot.ending else None,
                "state_bars": {bar.label: bar.current_value for bar in snapshot.state_bars},
            }
        )
        if snapshot.status != "active":
            break
    if include_trace:
        traces = service.get_turn_traces(created.session_id)
        result["trace_summary"] = {
            "turn_count": len(traces),
            "interpret_sources": [item.interpret_source for item in traces],
            "ending_judge_sources": [item.ending_judge_source for item in traces],
            "ending_judge_proposals": [item.ending_judge_proposed_id for item in traces if item.ending_judge_proposed_id],
            "render_sources": [item.render_source for item in traces],
            "ending_trigger_reasons": [item.resolution.ending_trigger_reason for item in traces if item.resolution.ending_trigger_reason],
        }
    return result


def _compare_arms(arm_a: list[dict[str, Any]], arm_b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for a_story, b_story in zip(arm_a, arm_b, strict=True):
        comparisons.append(
            {
                "story_id": a_story["story_id"],
                "same_turn_count": len(a_story["turns"]) == len(b_story["turns"]),
                "same_turn_outcomes": a_story["turns"] == b_story["turns"],
                "telemetry_turn_count": b_story["trace_summary"]["turn_count"],
                "telemetry_sources": {
                    "interpret": b_story["trace_summary"]["interpret_sources"],
                    "ending_judge": b_story["trace_summary"]["ending_judge_sources"],
                    "render": b_story["trace_summary"]["render_sources"],
                },
                "ending_judge_proposals": b_story["trace_summary"]["ending_judge_proposals"],
                "ending_trigger_reasons": b_story["trace_summary"]["ending_trigger_reasons"],
            }
        )
    return comparisons


def run_abtest(config: PlayBenchmarkConfig) -> tuple[dict[str, Any], str]:
    scenarios = SCENARIO_SUITES[config.suite]
    with tempfile.TemporaryDirectory() as tmpdir:
        library_service = StoryLibraryService(
            SQLiteStoryLibraryStorage(str(Path(tmpdir) / "stories.sqlite3"))
        )
        stories = generate_published_stories(scenarios, library_service)
        arm_a_service = PlaySessionService(
            story_library_service=library_service,
            gateway_factory=_no_gateway,
            settings=Settings(play_session_ttl_seconds=config.play_ttl_seconds),
            enable_turn_telemetry=False,
        )
        arm_b_service = PlaySessionService(
            story_library_service=library_service,
            gateway_factory=_no_gateway,
            settings=Settings(play_session_ttl_seconds=config.play_ttl_seconds),
            enable_turn_telemetry=True,
        )
        arm_a = [
            _play_story(
                service=arm_a_service,
                story_id=story["story_id"],
                turns=story["turns"],
                include_trace=False,
            )
            for story in stories
        ]
        arm_b = [
            _play_story(
                service=arm_b_service,
                story_id=story["story_id"],
                turns=story["turns"],
                include_trace=True,
            )
            for story in stories
        ]
    comparisons = _compare_arms(arm_a, arm_b)
    summary = {
        "suite": config.suite,
        "label": config.label,
        "generated_story_count": len(stories),
        "stories": stories,
        "comparisons": comparisons,
        "all_same_turn_outcomes": all(item["same_turn_outcomes"] for item in comparisons),
        "all_same_turn_count": all(item["same_turn_count"] for item in comparisons),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    markdown_lines = [
        "# Play Telemetry A/B",
        "",
        f"- Suite: `{config.suite}`",
        f"- Stories: `{len(stories)}`",
        f"- All same turn counts: `{summary['all_same_turn_count']}`",
        f"- All same turn outcomes: `{summary['all_same_turn_outcomes']}`",
        "",
        "## Stories",
    ]
    for story in stories:
        markdown_lines.append(f"- `{story['title']}` `{story['theme']}` `{story['story_id']}`")
    markdown_lines.append("")
    markdown_lines.append("## Comparisons")
    for item in comparisons:
        markdown_lines.append(
            f"- `{item['story_id']}` same_outcomes=`{item['same_turn_outcomes']}` telemetry_turns=`{item['telemetry_turn_count']}`"
        )
    markdown = "\n".join(markdown_lines) + "\n"
    return summary, markdown


def write_artifacts(config: PlayBenchmarkConfig, summary: dict[str, Any], markdown: str) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = config.label or config.suite
    stem = f"play_abtest_{label}_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    md_path.write_text(markdown)
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    summary, markdown = run_abtest(config)
    json_path, md_path = write_artifacts(config, summary, markdown)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
