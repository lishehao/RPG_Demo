"""add response session cursors table

Revision ID: 0006_response_session_cursors
Revises: 0005_author_runs_workflow
Create Date: 2026-03-13 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_response_session_cursors"
down_revision: str | None = "0005_author_runs_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGET_TABLE = "response_session_cursors"
LEGACY_TABLE = "responsesessioncursor"


def _table_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {str(name) for name in inspector.get_table_names()}


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for index in inspector.get_indexes(table_name):
        if str(index.get("name") or "") == index_name:
            return True
    return False


def _unique_exists(table_name: str, unique_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for item in inspector.get_unique_constraints(table_name):
        if str(item.get("name") or "") == unique_name:
            return True
    return False


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    table_names = _table_names()

    if TARGET_TABLE not in table_names and LEGACY_TABLE in table_names:
        op.rename_table(LEGACY_TABLE, TARGET_TABLE)
        table_names = _table_names()

    if TARGET_TABLE not in table_names:
        op.create_table(
            TARGET_TABLE,
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("scope_type", sa.String(), nullable=False),
            sa.Column("scope_id", sa.String(), nullable=False),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("model", sa.String(), nullable=False),
            sa.Column("previous_response_id", sa.String(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("scope_type", "scope_id", "channel", name="uq_response_session_cursor_scope_channel"),
        )

    # Normalize indexes to the SQLModel-generated naming style.
    if not _index_exists(TARGET_TABLE, "ix_response_session_cursors_scope_type"):
        op.create_index(
            "ix_response_session_cursors_scope_type",
            TARGET_TABLE,
            ["scope_type"],
            unique=False,
        )
    if not _index_exists(TARGET_TABLE, "ix_response_session_cursors_scope_id"):
        op.create_index(
            "ix_response_session_cursors_scope_id",
            TARGET_TABLE,
            ["scope_id"],
            unique=False,
        )
    if not _index_exists(TARGET_TABLE, "ix_response_session_cursors_channel"):
        op.create_index(
            "ix_response_session_cursors_channel",
            TARGET_TABLE,
            ["channel"],
            unique=False,
        )
    if not _index_exists(TARGET_TABLE, "ix_response_session_cursors_previous_response_id"):
        op.create_index(
            "ix_response_session_cursors_previous_response_id",
            TARGET_TABLE,
            ["previous_response_id"],
            unique=False,
        )
    if not _index_exists(TARGET_TABLE, "ix_response_session_cursors_updated_at"):
        op.create_index(
            "ix_response_session_cursors_updated_at",
            TARGET_TABLE,
            ["updated_at"],
            unique=False,
        )

    if not _unique_exists(TARGET_TABLE, "uq_response_session_cursor_scope_channel"):
        op.create_unique_constraint(
            "uq_response_session_cursor_scope_channel",
            TARGET_TABLE,
            ["scope_type", "scope_id", "channel"],
        )

    # Drop legacy index names if the table came from an older local iteration.
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_scope_type")
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_scope_id")
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_channel")
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_previous_response_id")
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_updated_at")


def downgrade() -> None:
    table_names = _table_names()
    if TARGET_TABLE not in table_names:
        return

    _drop_index_if_exists(TARGET_TABLE, "ix_response_session_cursors_updated_at")
    _drop_index_if_exists(TARGET_TABLE, "ix_response_session_cursors_previous_response_id")
    _drop_index_if_exists(TARGET_TABLE, "ix_response_session_cursors_channel")
    _drop_index_if_exists(TARGET_TABLE, "ix_response_session_cursors_scope_id")
    _drop_index_if_exists(TARGET_TABLE, "ix_response_session_cursors_scope_type")
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_updated_at")
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_previous_response_id")
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_channel")
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_scope_id")
    _drop_index_if_exists(TARGET_TABLE, "ix_responsesessioncursor_scope_type")

    op.drop_table(TARGET_TABLE)

