from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory


@dataclass
class DatabaseMigrationError(RuntimeError):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _alembic_ini_path() -> Path:
    return _repo_root() / "alembic.ini"


def _alembic_script_location() -> Path:
    return _repo_root() / "alembic"


def _normalize_database_url(value: str) -> str:
    database_url = (value or "").strip()
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _get_database_url() -> str:
    from rpg_backend.config.settings import get_settings

    return _normalize_database_url(get_settings().database_url)


def get_alembic_config() -> Config:
    config = Config(str(_alembic_ini_path()))
    config.set_main_option("script_location", str(_alembic_script_location()))
    config.set_main_option("sqlalchemy.url", _get_database_url())
    return config


def _get_engine():
    from rpg_backend.storage.engine import engine

    return engine


def get_head_revision() -> str:
    script = ScriptDirectory.from_config(get_alembic_config())
    heads = list(script.get_heads())
    if len(heads) != 1:
        raise DatabaseMigrationError(
            code="schema_head_ambiguous",
            message="expected exactly one alembic head revision",
            details={"heads": heads},
        )
    return heads[0]


def get_current_revision() -> str | None:
    try:
        with _get_engine().connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()
    except DatabaseMigrationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DatabaseMigrationError(
            code="database_connection_failed",
            message="failed to read current database revision",
            details={"error": str(exc)},
        ) from exc


def assert_schema_current() -> None:
    head_revision = get_head_revision()
    current_revision = get_current_revision()

    if current_revision is None:
        raise DatabaseMigrationError(
            code="schema_revision_missing",
            message="database has no alembic revision; run migrations before startup",
            details={"current_revision": None, "head_revision": head_revision},
        )

    if current_revision != head_revision:
        raise DatabaseMigrationError(
            code="schema_revision_mismatch",
            message="database revision does not match alembic head",
            details={"current_revision": current_revision, "head_revision": head_revision},
        )


def run_upgrade(revision: str = "head") -> None:
    command.upgrade(get_alembic_config(), revision)


def run_downgrade(revision: str) -> None:
    command.downgrade(get_alembic_config(), revision)
