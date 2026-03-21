from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

import rpg_backend.main as main_module
from rpg_backend.library.service import StoryLibraryService
from rpg_backend.library.storage import SQLiteStoryLibraryStorage
from rpg_backend.main import app
from tests.auth_helpers import DEFAULT_TEST_PASSWORD, ensure_authenticated_client
from tests.test_story_library_api import _FakeAuthorJobService, _publish_source


def test_auth_register_login_logout_cycle() -> None:
    client = TestClient(app)
    email = f"auth-cycle-{uuid4().hex[:10]}@example.com"

    register_response = client.post(
        "/auth/register",
        json={
            "display_name": "Auth Cycle",
            "email": email,
            "password": DEFAULT_TEST_PASSWORD,
        },
    )
    session_response = client.get("/auth/session")
    logout_response = client.post("/auth/logout")
    logged_out_session = client.get("/auth/session")
    login_response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": DEFAULT_TEST_PASSWORD,
        },
    )
    logged_in_again = client.get("/auth/session")

    assert register_response.status_code == 200
    assert session_response.json()["authenticated"] is True
    assert session_response.json()["user"]["email"] == email
    assert logout_response.status_code == 204
    assert logged_out_session.json() == {"authenticated": False, "user": None}
    assert login_response.status_code == 200
    assert logged_in_again.json()["authenticated"] is True


def test_protected_author_route_requires_auth_session() -> None:
    client = TestClient(app)

    response = client.post(
        "/author/story-previews",
        json={"prompt_seed": "A city archivist tries to hold one public record together."},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_session_required"


def test_logged_out_story_views_are_public_only(tmp_path) -> None:
    source = _publish_source("job-auth-public")
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    main_module.author_job_service = _FakeAuthorJobService(source)
    main_module.story_library_service = library_service
    owner_client = TestClient(app)
    anon_client = TestClient(app)
    try:
        ensure_authenticated_client(owner_client, email="auth-public-owner@example.com", display_name="Public Owner")
        published = owner_client.post(f"/author/jobs/{source.source_job_id}/publish?visibility=public")
        public_list = anon_client.get("/stories")
        public_detail = anon_client.get(f"/stories/{published.json()['story_id']}")
        mine_list = anon_client.get("/stories", params={"view": "mine"})
        play_create = anon_client.post("/play/sessions", json={"story_id": published.json()["story_id"]})
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert published.status_code == 200
    assert public_list.status_code == 200
    assert [story["story_id"] for story in public_list.json()["stories"]] == [published.json()["story_id"]]
    assert public_detail.status_code == 200
    assert mine_list.status_code == 401
    assert mine_list.json()["error"]["code"] == "auth_session_required"
    assert play_create.status_code == 401
    assert play_create.json()["error"]["code"] == "auth_session_required"


def test_logged_out_cannot_read_private_story_detail(tmp_path) -> None:
    source = _publish_source("job-auth-private")
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    main_module.author_job_service = _FakeAuthorJobService(source)
    main_module.story_library_service = library_service
    owner_client = TestClient(app)
    anon_client = TestClient(app)
    try:
        ensure_authenticated_client(owner_client, email="auth-private-owner@example.com", display_name="Private Owner")
        published = owner_client.post(f"/author/jobs/{source.source_job_id}/publish?visibility=private")
        hidden = anon_client.get(f"/stories/{published.json()['story_id']}")
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert published.status_code == 200
    assert hidden.status_code == 404
