from __future__ import annotations

from pathlib import Path

from tools import reset_local_databases


def test_db_family_paths_include_wal_and_shm() -> None:
    base = Path("/tmp/example.sqlite3")

    assert reset_local_databases._db_family_paths(base) == [
        Path("/tmp/example.sqlite3"),
        Path("/tmp/example.sqlite3-wal"),
        Path("/tmp/example.sqlite3-shm"),
    ]
