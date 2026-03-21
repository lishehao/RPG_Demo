from __future__ import annotations

from tools.playwright_launch import runner


def test_parse_launch_args_defaults() -> None:
    config = runner.parse_args([])

    assert config.app_url == "http://127.0.0.1:5173"
    assert config.browsers == ("chromium",)
    assert config.layers == ("env", "core", "recovery", "parallel")
    assert config.parallel_worker_count == runner.DEFAULT_PARALLEL_WORKER_COUNT
    assert config.max_play_turns == runner.DEFAULT_MAX_PLAY_TURNS


def test_build_parallel_worker_specs_uses_mixed_distribution() -> None:
    specs = runner.build_parallel_worker_specs(worker_count=10, seed=7)

    assert len(specs) == 10
    assert sum(1 for item in specs if item.mode == "author") == 4
    assert sum(1 for item in specs if item.mode == "play") == 4
    assert sum(1 for item in specs if item.mode == "mixed") == 2
    assert all(item.prompt_seed for item in specs if item.mode != "play")


def test_markdown_summary_includes_parallel_failure_count() -> None:
    markdown = runner._markdown_summary(
        {
            "app_url": "http://127.0.0.1:5173",
            "generated_at": "2026-03-20T00:00:00Z",
            "passed": False,
            "results": [
                {
                    "scenario_id": "PLW-PAR-001",
                    "scenario_name": "Parallel Mixed Launch Run",
                    "browser": "chromium",
                    "layer": "parallel",
                    "passed": False,
                    "elapsed_seconds": 12.3,
                    "failed_workers": 2,
                }
            ],
        }
    )

    assert "Parallel Mixed Launch Run" in markdown
    assert "failed_workers=`2`" in markdown
