from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from rpg_backend.config import get_settings
from rpg_backend.sqlite_utils import connect_sqlite, require_sqlite_columns


def _dump_json(value: Any) -> str:
    def _default(item: Any) -> str:
        if isinstance(item, datetime):
            return item.isoformat()
        raise TypeError(f"Object of type {type(item).__name__} is not JSON serializable")

    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=_default)


def _load_json(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


class SQLitePlaySessionStorage:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    @property
    def db_path(self) -> str:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        connection = connect_sqlite(self._db_path)
        self._ensure_schema(connection)
        return connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS play_sessions (
                session_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL DEFAULT '',
                story_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                finished_at TEXT,
                plan_json TEXT NOT NULL,
                state_json TEXT NOT NULL,
                history_json TEXT NOT NULL,
                turn_traces_json TEXT NOT NULL
            )
            """
        )
        require_sqlite_columns(
            connection,
            table_name="play_sessions",
            required_columns=(
                "session_id",
                "owner_user_id",
                "story_id",
                "created_at",
                "expires_at",
                "finished_at",
                "plan_json",
                "state_json",
                "history_json",
                "turn_traces_json",
            ),
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_play_sessions_story_id ON play_sessions (story_id, created_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_play_sessions_owner_created_at ON play_sessions (owner_user_id, created_at DESC)"
        )
        connection.commit()

    def save_session(self, payload: dict[str, Any]) -> None:
        resolved_owner_user_id = str(payload.get("owner_user_id") or get_settings().default_actor_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO play_sessions (
                    session_id,
                    owner_user_id,
                    story_id,
                    created_at,
                    expires_at,
                    finished_at,
                    plan_json,
                    state_json,
                    history_json,
                    turn_traces_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    owner_user_id = excluded.owner_user_id,
                    story_id = excluded.story_id,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    finished_at = excluded.finished_at,
                    plan_json = excluded.plan_json,
                    state_json = excluded.state_json,
                    history_json = excluded.history_json,
                    turn_traces_json = excluded.turn_traces_json
                """,
                (
                    payload["session_id"],
                    resolved_owner_user_id,
                    payload["story_id"],
                    payload["created_at"],
                    payload["expires_at"],
                    payload["finished_at"],
                    _dump_json(payload["plan"]),
                    _dump_json(payload["state"]),
                    _dump_json(payload.get("history") or []),
                    _dump_json(payload.get("turn_traces") or []),
                ),
            )
            connection.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM play_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id": str(row["session_id"]),
            "owner_user_id": str(row["owner_user_id"]),
            "story_id": str(row["story_id"]),
            "created_at": str(row["created_at"]),
            "expires_at": str(row["expires_at"]),
            "finished_at": str(row["finished_at"]) if row["finished_at"] is not None else None,
            "plan": _load_json(str(row["plan_json"])),
            "state": _load_json(str(row["state_json"])),
            "history": _load_json(str(row["history_json"])) or [],
            "turn_traces": _load_json(str(row["turn_traces_json"])) or [],
        }

    def delete_sessions_for_story(self, *, story_id: str, owner_user_id: str | None = None) -> int:
        with self._connect() as connection:
            if owner_user_id is None:
                cursor = connection.execute(
                    """
                    DELETE FROM play_sessions
                    WHERE story_id = ?
                    """,
                    (story_id,),
                )
            else:
                cursor = connection.execute(
                    """
                    DELETE FROM play_sessions
                    WHERE owner_user_id = ? AND story_id = ?
                    """,
                    (owner_user_id, story_id),
                )
            connection.commit()
            return cursor.rowcount
