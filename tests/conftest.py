import os
from collections.abc import Generator
import asyncio
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DB_DIR = REPO_ROOT / 'output' / 'test_runtime'
TEST_DB_PATH = TEST_DB_DIR / 'pytest_app.db'
TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('APP_DATABASE_URL', f'sqlite:///{TEST_DB_PATH}')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

from rpg_backend.api.route_paths import admin_auth_login_path
from rpg_backend.config.settings import get_settings
from rpg_backend.infrastructure.db.async_engine import async_engine
from rpg_backend.main import app
from rpg_backend.storage.engine import engine
from rpg_backend.storage.migrations import run_downgrade, run_upgrade


@pytest.fixture(autouse=True)
def reset_db() -> Generator[None, None, None]:
    # Keep tests on the same migration path as runtime; avoid create_all shortcuts.
    settings = get_settings()
    asyncio.run(async_engine.dispose())
    engine.dispose()
    database_url = (settings.database_url or "").strip()
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.replace("sqlite:///", "", 1))
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        if db_path.exists():
            db_path.unlink()
    else:
        run_downgrade("base")
    run_upgrade("head")
    yield
    asyncio.run(async_engine.dispose())
    engine.dispose()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        settings = get_settings()
        login_response = test_client.post(
            admin_auth_login_path(),
            json={
                "email": settings.admin_bootstrap_email,
                "password": settings.admin_bootstrap_password,
            },
        )
        assert login_response.status_code == 200, login_response.text
        token = login_response.json()["access_token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client


@pytest.fixture()
def anon_client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
