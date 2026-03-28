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


def require_sqlite_columns(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    required_columns: tuple[str, ...],
) -> None:
    existing_columns = {
        str(row["name"]) if isinstance(row, sqlite3.Row) else str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    missing_columns = [column for column in required_columns if column not in existing_columns]
    if not missing_columns:
        return
    missing = ", ".join(missing_columns)
    raise RuntimeError(
        f"Incompatible local database schema for {table_name}; missing columns: {missing}. "
        "Reset local artifacts with `python tools/reset_local_databases.py` and remove stale runtime JSON outputs."
    )
