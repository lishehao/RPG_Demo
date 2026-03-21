from __future__ import annotations

from pathlib import Path
import sqlite3


def ensure_sqlite_parent_dir(db_path: str) -> None:
    if db_path == ":memory:":
        return
    path = Path(db_path)
    if path.parent != Path():
        path.parent.mkdir(parents=True, exist_ok=True)


def connect_sqlite(db_path: str) -> sqlite3.Connection:
    ensure_sqlite_parent_dir(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection
