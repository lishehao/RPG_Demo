from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from rpg_backend.config.settings import get_settings


def _to_async_database_url(database_url: str) -> str:
    value = (database_url or "").strip()
    if value.startswith("sqlite:///"):
        return value.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if value.startswith("sqlite://"):
        return value.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def _engine_kwargs(async_database_url: str) -> dict:
    settings = get_settings()
    kwargs: dict[str, object] = {
        "pool_pre_ping": True,
        "pool_size": int(getattr(settings, "db_async_pool_size", 20)),
        "max_overflow": int(getattr(settings, "db_async_max_overflow", 20)),
        "pool_timeout": float(getattr(settings, "db_async_pool_timeout_seconds", 30.0)),
    }
    if async_database_url.startswith("sqlite+aiosqlite"):
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.pop("pool_timeout", None)
    return kwargs


settings = get_settings()
ASYNC_DATABASE_URL = _to_async_database_url(settings.database_url)
async_engine: AsyncEngine = create_async_engine(
    ASYNC_DATABASE_URL,
    **_engine_kwargs(ASYNC_DATABASE_URL),
)

