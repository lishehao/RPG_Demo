from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
BACKUP_DIR = ARTIFACTS_DIR / "db_backups"
DB_BASENAMES = [
    "story_library.sqlite3",
    "runtime_state.sqlite3",
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _db_family_paths(base_path: Path) -> list[Path]:
    suffixes = ["", "-wal", "-shm"]
    return [Path(f"{base_path}{suffix}") for suffix in suffixes]


def backup_databases(*, backup_dir: Path) -> list[Path]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    stamp = _timestamp()
    for basename in DB_BASENAMES:
        base_path = ARTIFACTS_DIR / basename
        for path in _db_family_paths(base_path):
            if not path.exists():
                continue
            destination = backup_dir / f"{stamp}_{path.name}"
            shutil.copy2(path, destination)
            created.append(destination)
    return created


def reset_databases() -> list[Path]:
    removed: list[Path] = []
    for basename in DB_BASENAMES:
        base_path = ARTIFACTS_DIR / basename
        for path in _db_family_paths(base_path):
            if not path.exists():
                continue
            path.unlink()
            removed.append(path)
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup and reset local SQLite business databases.")
    parser.add_argument("--no-backup", action="store_true", help="Delete the local databases without writing backup copies.")
    args = parser.parse_args(argv)

    backups: list[Path] = []
    if not args.no_backup:
        backups = backup_databases(backup_dir=BACKUP_DIR)
    removed = reset_databases()
    print(
        json.dumps(
            {
                "backups": [str(path.relative_to(REPO_ROOT)) for path in backups],
                "removed": [str(path.relative_to(REPO_ROOT)) for path in removed],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
