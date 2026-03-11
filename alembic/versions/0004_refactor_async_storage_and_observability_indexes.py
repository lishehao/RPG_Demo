"""refactor llm quota pk and add observability hot indexes

Revision ID: 0004_refactor_async_storage_and_observability_indexes
Revises: 0003_worker_llm_quota
Create Date: 2026-03-05 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_refactor_async_storage_and_observability_indexes"
down_revision: str | None = "0003_worker_llm_quota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
    op.create_table(
        "_llmquotawindow_new",
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("window_epoch_minute", sa.Integer(), nullable=False),
        sa.Column("rpm_used", sa.Integer(), nullable=False),
        sa.Column("tpm_used", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("model", "window_epoch_minute", name="pk_llmquotawindow"),
    )
    op.execute(
        """
        INSERT INTO _llmquotawindow_new (model, window_epoch_minute, rpm_used, tpm_used, updated_at)
        SELECT model, window_epoch_minute, rpm_used, tpm_used, updated_at
        FROM llmquotawindow
        """
    )
    op.drop_table("llmquotawindow")
    op.rename_table("_llmquotawindow_new", "llmquotawindow")
    op.create_index("ix_llmquotawindow_model", "llmquotawindow", ["model"], unique=False)
    op.create_index("ix_llmquotawindow_window_epoch_minute", "llmquotawindow", ["window_epoch_minute"], unique=False)
    op.create_index("ix_llmquotawindow_updated_at", "llmquotawindow", ["updated_at"], unique=False)

    op.create_index(
        "ix_llmcallevent_created_at_gateway_mode_stage",
        "llmcallevent",
        ["created_at", "gateway_mode", "stage"],
        unique=False,
    )
    op.create_index(
        "ix_httprequestevent_created_at_service_status_code",
        "httprequestevent",
        ["created_at", "service", "status_code"],
        unique=False,
    )
    op.create_index(
        "ix_readinessprobeevent_created_at_service_ok",
        "readinessprobeevent",
        ["created_at", "service", "ok"],
        unique=False,
    )
    op.create_index(
        "ix_runtimeevent_created_at_event_type",
        "runtimeevent",
        ["created_at", "event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_runtimeevent_created_at_event_type", table_name="runtimeevent")
    op.drop_index("ix_readinessprobeevent_created_at_service_ok", table_name="readinessprobeevent")
    op.drop_index("ix_httprequestevent_created_at_service_status_code", table_name="httprequestevent")
    op.drop_index("ix_llmcallevent_created_at_gateway_mode_stage", table_name="llmcallevent")

    op.create_table(
        "_llmquotawindow_old",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("window_epoch_minute", sa.Integer(), nullable=False),
        sa.Column("rpm_used", sa.Integer(), nullable=False),
        sa.Column("tpm_used", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model", "window_epoch_minute", name="uq_llm_quota_window_model_minute"),
    )
    op.execute(
        """
        INSERT INTO _llmquotawindow_old (id, model, window_epoch_minute, rpm_used, tpm_used, updated_at)
        SELECT model || ':' || CAST(window_epoch_minute AS TEXT), model, window_epoch_minute, rpm_used, tpm_used, updated_at
        FROM llmquotawindow
        """
    )
    op.drop_table("llmquotawindow")
    op.rename_table("_llmquotawindow_old", "llmquotawindow")
    op.create_index("ix_llmquotawindow_model", "llmquotawindow", ["model"], unique=False)
    op.create_index("ix_llmquotawindow_window_epoch_minute", "llmquotawindow", ["window_epoch_minute"], unique=False)
    op.create_index("ix_llmquotawindow_updated_at", "llmquotawindow", ["updated_at"], unique=False)
