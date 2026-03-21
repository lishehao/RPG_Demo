from __future__ import annotations

import json
from pathlib import Path

from tools.play_benchmarks import runner
from tools.play_benchmarks import fullstack_runner


def test_parse_play_benchmark_args_defaults(tmp_path: Path) -> None:
    config = runner.parse_args(["--output-dir", str(tmp_path)])

    assert config.suite == "stability_smoke"
    assert config.output_dir == tmp_path.resolve()
    assert config.play_ttl_seconds == 3600


def test_run_play_abtest_summarizes_arm_comparisons(monkeypatch, tmp_path: Path) -> None:
    stories = [
        {"story_id": "story-1", "title": "One", "theme": "Legitimacy crisis", "turns": ["a", "b"]},
        {"story_id": "story-2", "title": "Two", "theme": "Logistics quarantine crisis", "turns": ["c"]},
    ]

    def _fake_generate_published_stories(_scenarios, _library_service):
        return stories

    def _fake_play_story(*, service, story_id, turns, include_trace):  # noqa: ANN001
        payload = {
            "story_id": story_id,
            "session_id": f"{story_id}-session",
            "opening_beat": "Opening Pressure",
            "turns": [
                {
                    "input": turn,
                    "status": "active" if index < len(turns) - 1 else "completed",
                    "beat_index": index + 1,
                    "beat_title": f"Beat {index + 1}",
                    "ending": None if index < len(turns) - 1 else "mixed",
                    "state_bars": {"External Pressure": index + 1},
                }
                for index, turn in enumerate(turns)
            ],
        }
        if include_trace:
            payload["trace_summary"] = {
                "turn_count": len(turns),
                "interpret_sources": ["heuristic"] * len(turns),
                "ending_judge_sources": ["skipped"] * len(turns),
                "ending_judge_proposals": ["mixed"] if turns else [],
                "render_sources": ["fallback"] * len(turns),
                "ending_trigger_reasons": ["final_beat_default:mixed"] if turns else [],
            }
        return payload

    monkeypatch.setattr(runner, "generate_published_stories", _fake_generate_published_stories)
    monkeypatch.setattr(runner, "_play_story", _fake_play_story)
    config = runner.PlayBenchmarkConfig(
        suite="stability_smoke",
        label="telemetry-pass",
        output_dir=tmp_path,
        play_ttl_seconds=3600,
    )

    summary, markdown = runner.run_abtest(config)

    assert summary["generated_story_count"] == 2
    assert summary["all_same_turn_outcomes"] is True
    assert summary["comparisons"][0]["telemetry_turn_count"] == 2
    assert summary["comparisons"][1]["telemetry_sources"]["interpret"] == ["heuristic"]
    assert summary["comparisons"][0]["telemetry_sources"]["ending_judge"] == ["skipped", "skipped"]
    assert summary["comparisons"][0]["ending_judge_proposals"] == ["mixed"]
    assert "## Comparisons" in markdown


def test_write_play_benchmark_artifacts(tmp_path: Path) -> None:
    config = runner.PlayBenchmarkConfig(
        suite="stability_smoke",
        label="telemetry-pass",
        output_dir=tmp_path,
        play_ttl_seconds=3600,
    )
    summary = {
        "suite": "stability_smoke",
        "stories": [],
        "comparisons": [],
        "all_same_turn_outcomes": True,
        "all_same_turn_count": True,
    }
    markdown = "# Play Telemetry A/B\n"

    json_path, md_path = runner.write_artifacts(config, summary, markdown)

    assert json.loads(json_path.read_text())["suite"] == "stability_smoke"
    assert md_path.read_text() == markdown


def test_fullstack_runner_parse_args_defaults(tmp_path: Path) -> None:
    config = fullstack_runner.parse_args(["--output-dir", str(tmp_path)])

    assert config.suite == "stability_smoke"
    assert config.output_dir == tmp_path.resolve()
    assert config.play_ttl_seconds == 3600
