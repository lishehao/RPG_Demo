"""add author run workflow tables

Revision ID: 0005_author_runs_workflow
Revises: 0004_refactor_async_storage_and_observability_indexes
Create Date: 2026-03-08 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_author_runs_workflow"
down_revision: str | None = "0004_refactor_async_storage_and_observability_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "authorrun",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("story_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_node", sa.String(), nullable=True),
        sa.Column("raw_brief", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["story_id"], ["story.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_authorrun_story_id", "authorrun", ["story_id"], unique=False)
    op.create_index("ix_authorrun_status", "authorrun", ["status"], unique=False)
    op.create_index("ix_authorrun_current_node", "authorrun", ["current_node"], unique=False)
    op.create_index("ix_authorrun_error_code", "authorrun", ["error_code"], unique=False)
    op.create_index("ix_authorrun_created_at", "authorrun", ["created_at"], unique=False)
    op.create_index("ix_authorrun_updated_at", "authorrun", ["updated_at"], unique=False)
    op.create_index("ix_authorrun_completed_at", "authorrun", ["completed_at"], unique=False)

    op.create_table(
        "authorrunevent",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("node_name", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["authorrun.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_authorrunevent_run_id", "authorrunevent", ["run_id"], unique=False)
    op.create_index("ix_authorrunevent_node_name", "authorrunevent", ["node_name"], unique=False)
    op.create_index("ix_authorrunevent_event_type", "authorrunevent", ["event_type"], unique=False)
    op.create_index("ix_authorrunevent_created_at", "authorrunevent", ["created_at"], unique=False)

    op.create_table(
        "authorrunartifact",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("artifact_type", sa.String(), nullable=False),
        sa.Column("artifact_key", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["authorrun.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "artifact_type", "artifact_key", name="uq_author_run_artifact"),
    )
    op.create_index("ix_authorrunartifact_run_id", "authorrunartifact", ["run_id"], unique=False)
    op.create_index("ix_authorrunartifact_artifact_type", "authorrunartifact", ["artifact_type"], unique=False)
    op.create_index("ix_authorrunartifact_artifact_key", "authorrunartifact", ["artifact_key"], unique=False)
    op.create_index("ix_authorrunartifact_updated_at", "authorrunartifact", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_authorrunartifact_updated_at", table_name="authorrunartifact")
    op.drop_index("ix_authorrunartifact_artifact_key", table_name="authorrunartifact")
    op.drop_index("ix_authorrunartifact_artifact_type", table_name="authorrunartifact")
    op.drop_index("ix_authorrunartifact_run_id", table_name="authorrunartifact")
    op.drop_table("authorrunartifact")

    op.drop_index("ix_authorrunevent_created_at", table_name="authorrunevent")
    op.drop_index("ix_authorrunevent_event_type", table_name="authorrunevent")
    op.drop_index("ix_authorrunevent_node_name", table_name="authorrunevent")
    op.drop_index("ix_authorrunevent_run_id", table_name="authorrunevent")
    op.drop_table("authorrunevent")

    op.drop_index("ix_authorrun_completed_at", table_name="authorrun")
    op.drop_index("ix_authorrun_updated_at", table_name="authorrun")
    op.drop_index("ix_authorrun_created_at", table_name="authorrun")
    op.drop_index("ix_authorrun_error_code", table_name="authorrun")
    op.drop_index("ix_authorrun_current_node", table_name="authorrun")
    op.drop_index("ix_authorrun_status", table_name="authorrun")
    op.drop_index("ix_authorrun_story_id", table_name="authorrun")
    op.drop_table("authorrun")
