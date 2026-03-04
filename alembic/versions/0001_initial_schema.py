"""initial schema

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-03-04 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "story",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("draft_pack_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "storyversion",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("story_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("pack_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["story.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "version", name="uq_story_version"),
    )
    op.create_index("ix_storyversion_story_id", "storyversion", ["story_id"], unique=False)
    op.create_index("ix_storyversion_version", "storyversion", ["version"], unique=False)

    op.create_table(
        "session",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("story_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("current_scene_id", sa.String(), nullable=False),
        sa.Column("beat_index", sa.Integer(), nullable=False),
        sa.Column("beat_progress_json", sa.JSON(), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("ended", sa.Boolean(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["story.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_story_id", "session", ["story_id"], unique=False)
    op.create_index("ix_session_version", "session", ["version"], unique=False)

    op.create_table(
        "sessionaction",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("client_action_id", sa.String(), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "client_action_id", name="uq_session_action"),
    )
    op.create_index("ix_sessionaction_client_action_id", "sessionaction", ["client_action_id"], unique=False)
    op.create_index("ix_sessionaction_session_id", "sessionaction", ["session_id"], unique=False)

    op.create_table(
        "runtimeevent",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runtimeevent_session_id", "runtimeevent", ["session_id"], unique=False)

    op.create_table(
        "httprequestevent",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_httprequestevent_created_at", "httprequestevent", ["created_at"], unique=False)
    op.create_index("ix_httprequestevent_method", "httprequestevent", ["method"], unique=False)
    op.create_index("ix_httprequestevent_path", "httprequestevent", ["path"], unique=False)
    op.create_index("ix_httprequestevent_request_id", "httprequestevent", ["request_id"], unique=False)
    op.create_index("ix_httprequestevent_service", "httprequestevent", ["service"], unique=False)
    op.create_index("ix_httprequestevent_status_code", "httprequestevent", ["status_code"], unique=False)

    op.create_table(
        "llmcallevent",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("turn_index", sa.Integer(), nullable=True),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("gateway_mode", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llmcallevent_created_at", "llmcallevent", ["created_at"], unique=False)
    op.create_index("ix_llmcallevent_error_code", "llmcallevent", ["error_code"], unique=False)
    op.create_index("ix_llmcallevent_gateway_mode", "llmcallevent", ["gateway_mode"], unique=False)
    op.create_index("ix_llmcallevent_model", "llmcallevent", ["model"], unique=False)
    op.create_index("ix_llmcallevent_request_id", "llmcallevent", ["request_id"], unique=False)
    op.create_index("ix_llmcallevent_session_id", "llmcallevent", ["session_id"], unique=False)
    op.create_index("ix_llmcallevent_stage", "llmcallevent", ["stage"], unique=False)
    op.create_index("ix_llmcallevent_success", "llmcallevent", ["success"], unique=False)

    op.create_table(
        "readinessprobeevent",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_readinessprobeevent_created_at", "readinessprobeevent", ["created_at"], unique=False)
    op.create_index("ix_readinessprobeevent_error_code", "readinessprobeevent", ["error_code"], unique=False)
    op.create_index("ix_readinessprobeevent_ok", "readinessprobeevent", ["ok"], unique=False)
    op.create_index("ix_readinessprobeevent_request_id", "readinessprobeevent", ["request_id"], unique=False)
    op.create_index("ix_readinessprobeevent_service", "readinessprobeevent", ["service"], unique=False)

    op.create_table(
        "sessionfeedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("story_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("reason_tags_json", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"]),
        sa.ForeignKeyConstraint(["story_id"], ["story.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessionfeedback_session_id", "sessionfeedback", ["session_id"], unique=False)
    op.create_index("ix_sessionfeedback_story_id", "sessionfeedback", ["story_id"], unique=False)
    op.create_index("ix_sessionfeedback_version", "sessionfeedback", ["version"], unique=False)

    op.create_table(
        "runtimealertdispatch",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bucket_key", sa.String(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("window_ended_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runtimealertdispatch_bucket_key", "runtimealertdispatch", ["bucket_key"], unique=False)
    op.create_index(
        "ix_runtimealertdispatch_window_started_at",
        "runtimealertdispatch",
        ["window_started_at"],
        unique=False,
    )
    op.create_index(
        "ix_runtimealertdispatch_window_ended_at",
        "runtimealertdispatch",
        ["window_ended_at"],
        unique=False,
    )
    op.create_index("ix_runtimealertdispatch_sent_at", "runtimealertdispatch", ["sent_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_runtimealertdispatch_sent_at", table_name="runtimealertdispatch")
    op.drop_index("ix_runtimealertdispatch_window_ended_at", table_name="runtimealertdispatch")
    op.drop_index("ix_runtimealertdispatch_window_started_at", table_name="runtimealertdispatch")
    op.drop_index("ix_runtimealertdispatch_bucket_key", table_name="runtimealertdispatch")
    op.drop_table("runtimealertdispatch")

    op.drop_index("ix_sessionfeedback_version", table_name="sessionfeedback")
    op.drop_index("ix_sessionfeedback_story_id", table_name="sessionfeedback")
    op.drop_index("ix_sessionfeedback_session_id", table_name="sessionfeedback")
    op.drop_table("sessionfeedback")

    op.drop_index("ix_readinessprobeevent_service", table_name="readinessprobeevent")
    op.drop_index("ix_readinessprobeevent_request_id", table_name="readinessprobeevent")
    op.drop_index("ix_readinessprobeevent_ok", table_name="readinessprobeevent")
    op.drop_index("ix_readinessprobeevent_error_code", table_name="readinessprobeevent")
    op.drop_index("ix_readinessprobeevent_created_at", table_name="readinessprobeevent")
    op.drop_table("readinessprobeevent")

    op.drop_index("ix_llmcallevent_success", table_name="llmcallevent")
    op.drop_index("ix_llmcallevent_stage", table_name="llmcallevent")
    op.drop_index("ix_llmcallevent_session_id", table_name="llmcallevent")
    op.drop_index("ix_llmcallevent_request_id", table_name="llmcallevent")
    op.drop_index("ix_llmcallevent_model", table_name="llmcallevent")
    op.drop_index("ix_llmcallevent_gateway_mode", table_name="llmcallevent")
    op.drop_index("ix_llmcallevent_error_code", table_name="llmcallevent")
    op.drop_index("ix_llmcallevent_created_at", table_name="llmcallevent")
    op.drop_table("llmcallevent")

    op.drop_index("ix_httprequestevent_status_code", table_name="httprequestevent")
    op.drop_index("ix_httprequestevent_service", table_name="httprequestevent")
    op.drop_index("ix_httprequestevent_request_id", table_name="httprequestevent")
    op.drop_index("ix_httprequestevent_path", table_name="httprequestevent")
    op.drop_index("ix_httprequestevent_method", table_name="httprequestevent")
    op.drop_index("ix_httprequestevent_created_at", table_name="httprequestevent")
    op.drop_table("httprequestevent")

    op.drop_index("ix_runtimeevent_session_id", table_name="runtimeevent")
    op.drop_table("runtimeevent")

    op.drop_index("ix_sessionaction_session_id", table_name="sessionaction")
    op.drop_index("ix_sessionaction_client_action_id", table_name="sessionaction")
    op.drop_table("sessionaction")

    op.drop_index("ix_session_version", table_name="session")
    op.drop_index("ix_session_story_id", table_name="session")
    op.drop_table("session")

    op.drop_index("ix_storyversion_version", table_name="storyversion")
    op.drop_index("ix_storyversion_story_id", table_name="storyversion")
    op.drop_table("storyversion")

    op.drop_table("story")
