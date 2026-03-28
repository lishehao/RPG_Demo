from __future__ import annotations

import sqlite3

import pytest

from rpg_backend.author.storage import SQLiteAuthorJobStorage
from rpg_backend.play.storage import SQLitePlaySessionStorage


def test_author_storage_requires_reset_for_pre_migrated_schema(tmp_path) -> None:
    db_path = tmp_path / "author.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE author_jobs (
            job_id TEXT PRIMARY KEY,
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
    connection.commit()
    connection.close()

    storage = SQLiteAuthorJobStorage(str(db_path))
    with pytest.raises(RuntimeError, match="Reset local artifacts with `python tools/reset_local_databases.py`"):
        storage.get_job("missing-job")


def test_play_storage_requires_reset_for_pre_migrated_schema(tmp_path) -> None:
    db_path = tmp_path / "play.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE play_sessions (
            session_id TEXT PRIMARY KEY,
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
    connection.commit()
    connection.close()

    storage = SQLitePlaySessionStorage(str(db_path))
    with pytest.raises(RuntimeError, match="Reset local artifacts with `python tools/reset_local_databases.py`"):
        storage.get_session("missing-session")


def test_author_storage_migrates_copilot_proposal_undo_snapshot_columns(tmp_path) -> None:
    db_path = tmp_path / "author.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE author_jobs (
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
        CREATE TABLE author_copilot_proposals (
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
            proposal_json TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()

    storage = SQLiteAuthorJobStorage(str(db_path))
    assert storage.get_copilot_proposal("missing-proposal") is None

    migrated = sqlite3.connect(db_path)
    columns = {
        row[1]
        for row in migrated.execute("PRAGMA table_info(author_copilot_proposals)").fetchall()
    }
    migrated.close()

    assert {
        "prior_preview_json",
        "prior_summary_json",
        "prior_bundle_json",
        "prior_workspace_snapshot_json",
        "prior_record_revision",
    }.issubset(columns)
