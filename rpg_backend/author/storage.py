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


def _existing_sqlite_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row["name"]) if isinstance(row, sqlite3.Row) else str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _ensure_nullable_text_columns(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    column_names: tuple[str, ...],
) -> None:
    existing = _existing_sqlite_columns(connection, table_name)
    for column_name in column_names:
        if column_name in existing:
            continue
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT")
        existing.add(column_name)


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
                roster_catalog_version TEXT,
                roster_enabled INTEGER NOT NULL DEFAULT 0,
                roster_retrieval_trace_json TEXT NOT NULL DEFAULT '[]',
                copilot_workspace_snapshot_json TEXT,
                events_json TEXT NOT NULL,
                summary_json TEXT,
                bundle_json TEXT,
                error_json TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS author_copilot_proposals (
                proposal_id TEXT PRIMARY KEY,
                proposal_group_id TEXT NOT NULL DEFAULT '',
                session_id TEXT,
                job_id TEXT NOT NULL,
                owner_user_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                base_revision TEXT NOT NULL,
                instruction TEXT NOT NULL,
                variant_index INTEGER NOT NULL DEFAULT 1,
                variant_label TEXT NOT NULL DEFAULT '',
                supersedes_proposal_id TEXT,
                variant_fingerprint TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                applied_at TEXT,
                prior_preview_json TEXT,
                prior_summary_json TEXT,
                prior_bundle_json TEXT,
                prior_workspace_snapshot_json TEXT,
                prior_record_revision TEXT,
                proposal_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS author_copilot_sessions (
                session_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                owner_user_id TEXT NOT NULL DEFAULT '',
                hidden INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                base_revision TEXT NOT NULL,
                last_proposal_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT,
                session_json TEXT NOT NULL
            )
            """
        )
        require_sqlite_columns(
            connection,
            table_name="author_previews",
            required_columns=("preview_id", "owner_user_id", "created_at", "preview_json"),
        )
        require_sqlite_columns(
            connection,
            table_name="author_jobs",
            required_columns=(
                "job_id",
                "owner_user_id",
                "prompt_seed",
                "status",
                "preview_json",
                "progress_json",
                "created_at",
                "updated_at",
                "finished_at",
                "cache_metrics_json",
                "llm_call_trace_json",
                "quality_trace_json",
                "source_summary_json",
                "roster_catalog_version",
                "roster_enabled",
                "roster_retrieval_trace_json",
                "copilot_workspace_snapshot_json",
                "events_json",
                "summary_json",
                "bundle_json",
                "error_json",
            ),
        )
        _ensure_nullable_text_columns(
            connection,
            table_name="author_copilot_proposals",
            column_names=(
                "prior_preview_json",
                "prior_summary_json",
                "prior_bundle_json",
                "prior_workspace_snapshot_json",
                "prior_record_revision",
            ),
        )
        require_sqlite_columns(
            connection,
            table_name="author_copilot_proposals",
            required_columns=(
                "proposal_id",
                "proposal_group_id",
                "session_id",
                "job_id",
                "owner_user_id",
                "status",
                "base_revision",
                "instruction",
                "variant_index",
                "variant_label",
                "supersedes_proposal_id",
                "variant_fingerprint",
                "created_at",
                "updated_at",
                "applied_at",
                "prior_preview_json",
                "prior_summary_json",
                "prior_bundle_json",
                "prior_workspace_snapshot_json",
                "prior_record_revision",
                "proposal_json",
            ),
        )
        require_sqlite_columns(
            connection,
            table_name="author_copilot_sessions",
            required_columns=(
                "session_id",
                "job_id",
                "owner_user_id",
                "hidden",
                "status",
                "base_revision",
                "last_proposal_id",
                "created_at",
                "updated_at",
                "closed_at",
                "session_json",
            ),
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_author_jobs_status ON author_jobs (status, updated_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_author_jobs_owner_status ON author_jobs (owner_user_id, status, updated_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_author_copilot_proposals_job_created ON author_copilot_proposals (job_id, created_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_author_copilot_sessions_job_updated ON author_copilot_sessions (job_id, updated_at DESC)"
        )
        connection.commit()

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
                    roster_catalog_version,
                    roster_enabled,
                    roster_retrieval_trace_json,
                    copilot_workspace_snapshot_json,
                    events_json,
                    summary_json,
                    bundle_json,
                    error_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    roster_catalog_version = excluded.roster_catalog_version,
                    roster_enabled = excluded.roster_enabled,
                    roster_retrieval_trace_json = excluded.roster_retrieval_trace_json,
                    copilot_workspace_snapshot_json = excluded.copilot_workspace_snapshot_json,
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
                    payload.get("roster_catalog_version"),
                    1 if payload.get("roster_enabled") else 0,
                    _dump_json(payload.get("roster_retrieval_trace") or []),
                    _dump_json(payload["copilot_workspace_snapshot"]) if payload.get("copilot_workspace_snapshot") is not None else None,
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

    def save_copilot_proposal(self, payload: dict[str, Any]) -> None:
        resolved_owner_user_id = str(payload.get("owner_user_id") or get_settings().default_actor_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO author_copilot_proposals (
                    proposal_id,
                    proposal_group_id,
                    session_id,
                    job_id,
                    owner_user_id,
                    status,
                    base_revision,
                    instruction,
                    variant_index,
                    variant_label,
                    supersedes_proposal_id,
                    variant_fingerprint,
                    created_at,
                    updated_at,
                    applied_at,
                    prior_preview_json,
                    prior_summary_json,
                    prior_bundle_json,
                    prior_workspace_snapshot_json,
                    prior_record_revision,
                    proposal_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    proposal_group_id = excluded.proposal_group_id,
                    session_id = excluded.session_id,
                    job_id = excluded.job_id,
                    owner_user_id = excluded.owner_user_id,
                    status = excluded.status,
                    base_revision = excluded.base_revision,
                    instruction = excluded.instruction,
                    variant_index = excluded.variant_index,
                    variant_label = excluded.variant_label,
                    supersedes_proposal_id = excluded.supersedes_proposal_id,
                    variant_fingerprint = excluded.variant_fingerprint,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    applied_at = excluded.applied_at,
                    prior_preview_json = excluded.prior_preview_json,
                    prior_summary_json = excluded.prior_summary_json,
                    prior_bundle_json = excluded.prior_bundle_json,
                    prior_workspace_snapshot_json = excluded.prior_workspace_snapshot_json,
                    prior_record_revision = excluded.prior_record_revision,
                    proposal_json = excluded.proposal_json
                """,
                (
                    payload["proposal_id"],
                    payload["proposal_group_id"],
                    payload.get("session_id"),
                    payload["job_id"],
                    resolved_owner_user_id,
                    payload["status"],
                    payload["base_revision"],
                    payload["instruction"],
                    payload.get("variant_index", 1),
                    payload.get("variant_label", "Initial suggestion"),
                    payload.get("supersedes_proposal_id"),
                    payload.get("variant_fingerprint", payload["proposal_id"]),
                    payload["created_at"],
                    payload["updated_at"],
                    payload.get("applied_at"),
                    _dump_json(payload["prior_preview"]) if payload.get("prior_preview") is not None else None,
                    _dump_json(payload["prior_summary"]) if payload.get("prior_summary") is not None else None,
                    _dump_json(payload["prior_bundle"]) if payload.get("prior_bundle") is not None else None,
                    _dump_json(payload["prior_workspace_snapshot"]) if payload.get("prior_workspace_snapshot") is not None else None,
                    payload.get("prior_record_revision"),
                    _dump_json(payload["proposal"]),
                ),
            )
            connection.commit()

    def get_copilot_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM author_copilot_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        proposal_payload = _load_json(str(row["proposal_json"]))
        proposal_payload.setdefault("proposal_group_id", str(row["proposal_group_id"]) or str(row["proposal_id"]))
        proposal_payload.setdefault("variant_index", int(row["variant_index"]) if row["variant_index"] is not None else 1)
        proposal_payload.setdefault("variant_label", str(row["variant_label"]) or "Initial suggestion")
        proposal_payload.setdefault("supersedes_proposal_id", str(row["supersedes_proposal_id"]) if row["supersedes_proposal_id"] is not None else None)
        return {
            "proposal_id": str(row["proposal_id"]),
            "proposal_group_id": str(row["proposal_group_id"]) or str(row["proposal_id"]),
            "session_id": str(row["session_id"]) if row["session_id"] is not None else None,
            "job_id": str(row["job_id"]),
            "owner_user_id": str(row["owner_user_id"]),
            "status": str(row["status"]),
            "base_revision": str(row["base_revision"]),
            "instruction": str(row["instruction"]),
            "variant_index": int(row["variant_index"]) if row["variant_index"] is not None else 1,
            "variant_label": str(row["variant_label"]) or "Initial suggestion",
            "supersedes_proposal_id": str(row["supersedes_proposal_id"]) if row["supersedes_proposal_id"] is not None else None,
            "variant_fingerprint": str(row["variant_fingerprint"]) or str(row["proposal_id"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "applied_at": str(row["applied_at"]) if row["applied_at"] is not None else None,
            "prior_preview": _load_json(row["prior_preview_json"]),
            "prior_summary": _load_json(row["prior_summary_json"]),
            "prior_bundle": _load_json(row["prior_bundle_json"]),
            "prior_workspace_snapshot": _load_json(row["prior_workspace_snapshot_json"]),
            "prior_record_revision": str(row["prior_record_revision"]) if row["prior_record_revision"] is not None else None,
            "proposal": proposal_payload,
        }

    def list_copilot_proposals_for_group(self, job_id: str, proposal_group_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM author_copilot_proposals
                WHERE job_id = ? AND proposal_group_id = ?
                ORDER BY variant_index ASC, created_at ASC
                """,
                (job_id, proposal_group_id),
            ).fetchall()
        payloads: list[dict[str, Any]] = []
        for row in rows:
            proposal_payload = _load_json(str(row["proposal_json"]))
            proposal_payload.setdefault("proposal_group_id", str(row["proposal_group_id"]) or str(row["proposal_id"]))
            proposal_payload.setdefault("variant_index", int(row["variant_index"]) if row["variant_index"] is not None else 1)
            proposal_payload.setdefault("variant_label", str(row["variant_label"]) or "Initial suggestion")
            proposal_payload.setdefault("supersedes_proposal_id", str(row["supersedes_proposal_id"]) if row["supersedes_proposal_id"] is not None else None)
            payloads.append(
                {
                    "proposal_id": str(row["proposal_id"]),
                    "proposal_group_id": str(row["proposal_group_id"]) or str(row["proposal_id"]),
                    "session_id": str(row["session_id"]) if row["session_id"] is not None else None,
                    "job_id": str(row["job_id"]),
                    "owner_user_id": str(row["owner_user_id"]),
                    "status": str(row["status"]),
                    "base_revision": str(row["base_revision"]),
                    "instruction": str(row["instruction"]),
                    "variant_index": int(row["variant_index"]) if row["variant_index"] is not None else 1,
                    "variant_label": str(row["variant_label"]) or "Initial suggestion",
                    "supersedes_proposal_id": str(row["supersedes_proposal_id"]) if row["supersedes_proposal_id"] is not None else None,
                    "variant_fingerprint": str(row["variant_fingerprint"]) or str(row["proposal_id"]),
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"]),
                    "applied_at": str(row["applied_at"]) if row["applied_at"] is not None else None,
                    "prior_preview": _load_json(row["prior_preview_json"]),
                    "prior_summary": _load_json(row["prior_summary_json"]),
                    "prior_bundle": _load_json(row["prior_bundle_json"]),
                    "prior_workspace_snapshot": _load_json(row["prior_workspace_snapshot_json"]),
                    "prior_record_revision": str(row["prior_record_revision"]) if row["prior_record_revision"] is not None else None,
                    "proposal": proposal_payload,
                }
            )
        return payloads

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
            "roster_catalog_version": str(row["roster_catalog_version"]) if row["roster_catalog_version"] is not None else None,
            "roster_enabled": bool(row["roster_enabled"]),
            "roster_retrieval_trace": _load_json(str(row["roster_retrieval_trace_json"])) or [],
            "copilot_workspace_snapshot": _load_json(row["copilot_workspace_snapshot_json"]),
            "events": _load_json(str(row["events_json"])) or [],
            "summary": _load_json(row["summary_json"]),
            "bundle": _load_json(row["bundle_json"]),
            "error": _load_json(row["error_json"]),
        }

    def save_copilot_session(self, payload: dict[str, Any]) -> None:
        resolved_owner_user_id = str(payload.get("owner_user_id") or get_settings().default_actor_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO author_copilot_sessions (
                    session_id,
                    job_id,
                    owner_user_id,
                    hidden,
                    status,
                    base_revision,
                    last_proposal_id,
                    created_at,
                    updated_at,
                    closed_at,
                    session_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    job_id = excluded.job_id,
                    owner_user_id = excluded.owner_user_id,
                    hidden = excluded.hidden,
                    status = excluded.status,
                    base_revision = excluded.base_revision,
                    last_proposal_id = excluded.last_proposal_id,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    closed_at = excluded.closed_at,
                    session_json = excluded.session_json
                """,
                (
                    payload["session_id"],
                    payload["job_id"],
                    resolved_owner_user_id,
                    1 if payload.get("hidden") else 0,
                    payload["status"],
                    payload["base_revision"],
                    payload.get("last_proposal_id"),
                    payload["created_at"],
                    payload["updated_at"],
                    payload.get("closed_at"),
                    _dump_json(payload["session"]),
                ),
            )
            connection.commit()

    def get_copilot_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM author_copilot_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id": str(row["session_id"]),
            "job_id": str(row["job_id"]),
            "owner_user_id": str(row["owner_user_id"]),
            "hidden": bool(row["hidden"]),
            "status": str(row["status"]),
            "base_revision": str(row["base_revision"]),
            "last_proposal_id": str(row["last_proposal_id"]) if row["last_proposal_id"] is not None else None,
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "closed_at": str(row["closed_at"]) if row["closed_at"] is not None else None,
            "session": _load_json(str(row["session_json"])),
        }

    def list_copilot_sessions_for_job(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM author_copilot_sessions
                WHERE job_id = ?
                ORDER BY updated_at DESC, created_at DESC, session_id DESC
                """,
                (job_id,),
            ).fetchall()
        payloads: list[dict[str, Any]] = []
        for row in rows:
            payloads.append(
                {
                    "session_id": str(row["session_id"]),
                    "job_id": str(row["job_id"]),
                    "owner_user_id": str(row["owner_user_id"]),
                    "hidden": bool(row["hidden"]),
                    "status": str(row["status"]),
                    "base_revision": str(row["base_revision"]),
                    "last_proposal_id": str(row["last_proposal_id"]) if row["last_proposal_id"] is not None else None,
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"]),
                    "closed_at": str(row["closed_at"]) if row["closed_at"] is not None else None,
                    "session": _load_json(str(row["session_json"])),
                }
            )
        return payloads
