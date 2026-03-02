from sqlmodel import Session, SQLModel, create_engine

from rpg_backend.config.settings import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    # Ensure SQLModel metadata includes all table models before create_all.
    from rpg_backend.storage import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
