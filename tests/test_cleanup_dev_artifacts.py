from __future__ import annotations

from pathlib import Path

from tools.cleanup_dev_artifacts import benchmark_family, prune_benchmarks


def test_benchmark_family_groups_timestamped_outputs() -> None:
    path = Path("fullstack_validation_5stories_latest_20260319_045412.json")
    assert benchmark_family(path) == "fullstack_validation_5stories_latest"


def test_prune_benchmarks_keeps_latest_per_family(tmp_path, monkeypatch) -> None:
    from tools import cleanup_dev_artifacts as cleanup

    benchmark_dir = tmp_path / "benchmarks"
    benchmark_dir.mkdir()
    files = [
        benchmark_dir / "suite_a_20260319_010101.json",
        benchmark_dir / "suite_a_20260319_010102.json",
        benchmark_dir / "suite_a_20260319_010103.json",
        benchmark_dir / "suite_b_20260319_010101.json",
        benchmark_dir / "suite_b_20260319_010102.json",
    ]
    for index, path in enumerate(files):
        path.write_text("x")
        path.touch()
        path.chmod(0o644)
    monkeypatch.setattr(cleanup, "BENCHMARK_DIR", benchmark_dir)

    removed = prune_benchmarks(keep_latest=2)

    assert {path.name for path in removed} == {"suite_a_20260319_010101.json"}
    assert (benchmark_dir / "suite_a_20260319_010102.json").exists()
    assert (benchmark_dir / "suite_a_20260319_010103.json").exists()
