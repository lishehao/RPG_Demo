from __future__ import annotations

import argparse
import shutil
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = REPO_ROOT / "artifacts" / "benchmarks"
CACHE_PATHS = [
    REPO_ROOT / ".pytest_cache",
    REPO_ROOT / "frontend" / "node_modules",
    *REPO_ROOT.glob("**/__pycache__"),
]


def benchmark_family(path: Path) -> str:
    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].isdigit():
        return "_".join(parts[:-2])
    if len(parts) >= 2 and parts[-1].isdigit():
        return "_".join(parts[:-1])
    return stem


def prune_benchmarks(*, keep_latest: int) -> list[Path]:
    if not BENCHMARK_DIR.exists():
        return []
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(BENCHMARK_DIR.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.is_file():
            grouped[benchmark_family(path)].append(path)
    removed: list[Path] = []
    for files in grouped.values():
        for path in files[keep_latest:]:
            path.unlink(missing_ok=True)
            removed.append(path)
    return removed


def remove_caches() -> list[Path]:
    removed: list[Path] = []
    seen: set[Path] = set()
    for path in CACHE_PATHS:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(path)
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean local benchmark artifacts and generated caches.")
    parser.add_argument("--keep-latest", type=int, default=5)
    parser.add_argument("--skip-benchmarks", action="store_true")
    parser.add_argument("--skip-caches", action="store_true")
    args = parser.parse_args(argv)

    removed_benchmarks = [] if args.skip_benchmarks else prune_benchmarks(keep_latest=max(args.keep_latest, 0))
    removed_caches = [] if args.skip_caches else remove_caches()
    print(
        {
            "removed_benchmarks": [str(path.relative_to(REPO_ROOT)) for path in removed_benchmarks],
            "removed_caches": [str(path.relative_to(REPO_ROOT)) for path in removed_caches],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
