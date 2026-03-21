from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from rpg_backend.sqlite_utils import connect_sqlite


class SQLiteAuthStorage:
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
            CREATE TABLE IF NOT EXISTS auth_users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                normalized_email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES auth_users(user_id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions (user_id, created_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions (expires_at)"
        )
        connection.commit()

    def create_user(
        self,
        *,
        user_id: str,
        email: str,
        normalized_email: str,
        display_name: str,
        password_hash: str,
        created_at: datetime,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO auth_users (
                    user_id,
                    email,
                    normalized_email,
                    display_name,
                    password_hash,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    email,
                    normalized_email,
                    display_name,
                    password_hash,
                    created_at.isoformat(),
                ),
            )
            connection.commit()

    def get_user_by_normalized_email(self, normalized_email: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM auth_users
                WHERE normalized_email = ?
                """,
                (normalized_email,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def get_user_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM auth_users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def create_session(
        self,
        *,
        session_id: str,
        user_id: str,
        token_hash: str,
        created_at: datetime,
        expires_at: datetime,
        last_seen_at: datetime,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    session_id,
                    user_id,
                    token_hash,
                    created_at,
                    expires_at,
                    last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    token_hash,
                    created_at.isoformat(),
                    expires_at.isoformat(),
                    last_seen_at.isoformat(),
                ),
            )
            connection.commit()

    def get_session_with_user(self, token_hash: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    sessions.session_id AS session_id,
                    sessions.user_id AS user_id,
                    sessions.token_hash AS token_hash,
                    sessions.created_at AS session_created_at,
                    sessions.expires_at AS expires_at,
                    sessions.last_seen_at AS last_seen_at,
                    users.email AS email,
                    users.normalized_email AS normalized_email,
                    users.display_name AS display_name,
                    users.password_hash AS password_hash,
                    users.created_at AS user_created_at
                FROM auth_sessions AS sessions
                JOIN auth_users AS users
                    ON users.user_id = sessions.user_id
                WHERE sessions.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id": str(row["session_id"]),
            "user_id": str(row["user_id"]),
            "token_hash": str(row["token_hash"]),
            "session_created_at": str(row["session_created_at"]),
            "expires_at": str(row["expires_at"]),
            "last_seen_at": str(row["last_seen_at"]),
            "email": str(row["email"]),
            "normalized_email": str(row["normalized_email"]),
            "display_name": str(row["display_name"]),
            "password_hash": str(row["password_hash"]),
            "user_created_at": str(row["user_created_at"]),
        }

    def touch_session(self, *, session_id: str, expires_at: datetime, last_seen_at: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE auth_sessions
                SET expires_at = ?, last_seen_at = ?
                WHERE session_id = ?
                """,
                (expires_at.isoformat(), last_seen_at.isoformat(), session_id),
            )
            connection.commit()

    def delete_session_by_token_hash(self, token_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM auth_sessions
                WHERE token_hash = ?
                """,
                (token_hash,),
            )
            connection.commit()

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "user_id": str(row["user_id"]),
            "email": str(row["email"]),
            "normalized_email": str(row["normalized_email"]),
            "display_name": str(row["display_name"]),
            "password_hash": str(row["password_hash"]),
            "created_at": str(row["created_at"]),
        }
