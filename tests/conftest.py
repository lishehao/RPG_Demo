from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.main import app
from app.storage import models  # noqa: F401
from app.storage.engine import engine


@pytest.fixture(autouse=True)
def reset_db() -> Generator[None, None, None]:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
