from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from rpg_backend.config import get_settings
from rpg_backend.sqlite_utils import connect_sqlite


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


class SQLiteAuthorJobStorage:
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
            CREATE TABLE IF NOT EXISTS author_previews (
                preview_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                preview_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS author_jobs (
                job_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL DEFAULT '',
                prompt_seed TEXT NOT NULL,
                status TEXT NOT NULL,
                preview_json TEXT NOT NULL,
                progress_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finished_at TEXT,
                cache_metrics_json TEXT,
                llm_call_trace_json TEXT NOT NULL,
                quality_trace_json TEXT NOT NULL,
                source_summary_json TEXT NOT NULL,
                events_json TEXT NOT NULL,
                summary_json TEXT,
                bundle_json TEXT,
                error_json TEXT
            )
            """
        )
        self._migrate_owner_columns(connection)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_author_jobs_status ON author_jobs (status, updated_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_author_jobs_owner_status ON author_jobs (owner_user_id, status, updated_at DESC)"
        )
        connection.commit()

    def _migrate_owner_columns(self, connection: sqlite3.Connection) -> None:
        default_actor_id = get_settings().default_actor_id
        preview_columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(author_previews)").fetchall()}
        if "owner_user_id" not in preview_columns:
            connection.execute(
                f"ALTER TABLE author_previews ADD COLUMN owner_user_id TEXT NOT NULL DEFAULT '{default_actor_id}'"
            )
        job_columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(author_jobs)").fetchall()}
        if "owner_user_id" not in job_columns:
            connection.execute(
                f"ALTER TABLE author_jobs ADD COLUMN owner_user_id TEXT NOT NULL DEFAULT '{default_actor_id}'"
            )
        connection.execute(
            """
            UPDATE author_previews
            SET owner_user_id = ?
            WHERE owner_user_id IS NULL OR owner_user_id = ''
            """,
            (default_actor_id,),
        )
        connection.execute(
            """
            UPDATE author_jobs
            SET owner_user_id = ?
            WHERE owner_user_id IS NULL OR owner_user_id = ''
            """,
            (default_actor_id,),
        )

    def save_preview(
        self,
        preview_id: str,
        preview_payload: dict[str, Any],
        *,
        owner_user_id: str | None = None,
        created_at: datetime,
    ) -> None:
        resolved_owner_user_id = owner_user_id or get_settings().default_actor_id
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO author_previews (preview_id, owner_user_id, created_at, preview_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(preview_id) DO UPDATE SET
                    owner_user_id = excluded.owner_user_id,
                    created_at = excluded.created_at,
                    preview_json = excluded.preview_json
                """,
                (
                    preview_id,
                    resolved_owner_user_id,
                    created_at.isoformat(),
                    _dump_json(preview_payload),
                ),
            )
            connection.commit()

    def get_preview(self, preview_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT owner_user_id, preview_json FROM author_previews WHERE preview_id = ?",
                (preview_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "owner_user_id": str(row["owner_user_id"]),
            "preview": _load_json(str(row["preview_json"])),
        }

    def save_job(self, payload: dict[str, Any]) -> None:
        resolved_owner_user_id = str(payload.get("owner_user_id") or get_settings().default_actor_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO author_jobs (
                    job_id,
                    owner_user_id,
                    prompt_seed,
                    status,
                    preview_json,
                    progress_json,
                    created_at,
                    updated_at,
                    finished_at,
                    cache_metrics_json,
                    llm_call_trace_json,
                    quality_trace_json,
                    source_summary_json,
                    events_json,
                    summary_json,
                    bundle_json,
                    error_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    owner_user_id = excluded.owner_user_id,
                    prompt_seed = excluded.prompt_seed,
                    status = excluded.status,
                    preview_json = excluded.preview_json,
                    progress_json = excluded.progress_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    finished_at = excluded.finished_at,
                    cache_metrics_json = excluded.cache_metrics_json,
                    llm_call_trace_json = excluded.llm_call_trace_json,
                    quality_trace_json = excluded.quality_trace_json,
                    source_summary_json = excluded.source_summary_json,
                    events_json = excluded.events_json,
                    summary_json = excluded.summary_json,
                    bundle_json = excluded.bundle_json,
                    error_json = excluded.error_json
                """,
                (
                    payload["job_id"],
                    resolved_owner_user_id,
                    payload["prompt_seed"],
                    payload["status"],
                    _dump_json(payload["preview"]),
                    _dump_json(payload["progress"]),
                    payload["created_at"],
                    payload["updated_at"],
                    payload["finished_at"],
                    _dump_json(payload["cache_metrics"]) if payload.get("cache_metrics") is not None else None,
                    _dump_json(payload.get("llm_call_trace") or []),
                    _dump_json(payload.get("quality_trace") or []),
                    _dump_json(payload.get("source_summary") or {}),
                    _dump_json(payload.get("events") or []),
                    _dump_json(payload["summary"]) if payload.get("summary") is not None else None,
                    _dump_json(payload["bundle"]) if payload.get("bundle") is not None else None,
                    _dump_json(payload["error"]) if payload.get("error") is not None else None,
                ),
            )
            connection.commit()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM author_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return self._row_to_payload(row)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM author_jobs ORDER BY created_at DESC, job_id DESC"
            ).fetchall()
        return [payload for row in rows if (payload := self._row_to_payload(row)) is not None]

    @staticmethod
    def _row_to_payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "job_id": str(row["job_id"]),
            "owner_user_id": str(row["owner_user_id"]),
            "prompt_seed": str(row["prompt_seed"]),
            "status": str(row["status"]),
            "preview": _load_json(str(row["preview_json"])),
            "progress": _load_json(str(row["progress_json"])),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "finished_at": str(row["finished_at"]) if row["finished_at"] is not None else None,
            "cache_metrics": _load_json(row["cache_metrics_json"]),
            "llm_call_trace": _load_json(str(row["llm_call_trace_json"])) or [],
            "quality_trace": _load_json(str(row["quality_trace_json"])) or [],
            "source_summary": _load_json(str(row["source_summary_json"])) or {},
            "events": _load_json(str(row["events_json"])) or [],
            "summary": _load_json(row["summary_json"]),
            "bundle": _load_json(row["bundle_json"]),
            "error": _load_json(row["error_json"]),
        }
