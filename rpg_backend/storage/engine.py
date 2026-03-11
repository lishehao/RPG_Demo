from sqlmodel import Session, create_engine

from rpg_backend.config.settings import get_settings

settings = get_settings()


def _to_sync_database_url(database_url: str) -> str:
    value = (database_url or '').strip()
    if value.startswith('postgresql://'):
        return value.replace('postgresql://', 'postgresql+psycopg://', 1)
    return value


def _engine_connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


SYNC_DATABASE_URL = _to_sync_database_url(settings.database_url)
_connect_args = _engine_connect_args(SYNC_DATABASE_URL)
_engine_kwargs = {"pool_pre_ping": True}
if _connect_args:
    _engine_kwargs["connect_args"] = _connect_args
engine = create_engine(SYNC_DATABASE_URL, **_engine_kwargs)


def init_db() -> None:
    # Startup is strict: schema must already be migrated to current head.
    from rpg_backend.storage.migrations import assert_schema_current

    assert_schema_current()


def get_session():
    with Session(engine) as session:
        yield session
