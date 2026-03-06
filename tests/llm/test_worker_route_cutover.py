from __future__ import annotations

from fastapi.testclient import TestClient

from rpg_backend.config.settings import get_settings
from rpg_backend.llm.task_executor import TaskUsage
from rpg_backend.llm_worker.main import app, task_service
from rpg_backend.llm_worker.route_paths import (
    WORKER_JSON_OBJECT_TASK_PATH,
    WORKER_RENDER_NARRATION_TASK_PATH,
    WORKER_ROUTE_INTENT_TASK_PATH,
)
from rpg_backend.llm_worker.schemas import (
    WorkerTaskJsonObjectResponse,
    WorkerTaskNarrationResponse,
    WorkerTaskRouteIntentResponse,
)


def _worker_headers() -> dict[str, str]:
    return {"X-Internal-Worker-Token": get_settings().internal_worker_token}


def test_worker_route_intent_uses_internal_path_and_v2_is_removed(monkeypatch) -> None:
    async def _fake_execute_route_intent_task(_payload):  # noqa: ANN001, ANN201
        return (
            WorkerTaskRouteIntentResponse(
                move_id="global.help_me_progress",
                args={},
                confidence=0.92,
                interpreted_intent="help me progress",
                model="test-model",
                attempts=1,
                retry_count=0,
                duration_ms=5,
            ),
            TaskUsage(total_tokens=42),
        )

    monkeypatch.setattr(task_service, "execute_route_intent_task", _fake_execute_route_intent_task)
    with TestClient(app) as client:
        response = client.post(
            WORKER_ROUTE_INTENT_TASK_PATH,
            headers=_worker_headers(),
            json={
                "scene_context": {"moves": [], "fallback_move": "global.help_me_progress"},
                "text": "help me progress",
                "model": "test-model",
                "temperature": 0.1,
                "max_retries": 1,
                "timeout_seconds": 2.0,
            },
        )
        assert response.status_code == 200
        assert response.json()["move_id"] == "global.help_me_progress"

        legacy = client.post(
            "/v2/llm/tasks/route-intent",
            headers=_worker_headers(),
            json={
                "scene_context": {"moves": [], "fallback_move": "global.help_me_progress"},
                "text": "help me progress",
                "model": "test-model",
            },
        )
        assert legacy.status_code == 404


def test_worker_render_narration_uses_internal_path_and_v2_is_removed(monkeypatch) -> None:
    async def _fake_execute_render_narration_task(_payload):  # noqa: ANN001, ANN201
        return (
            WorkerTaskNarrationResponse(
                narration_text="narration ok",
                model="test-model",
                attempts=1,
                retry_count=0,
                duration_ms=5,
            ),
            TaskUsage(total_tokens=36),
        )

    monkeypatch.setattr(task_service, "execute_render_narration_task", _fake_execute_render_narration_task)
    with TestClient(app) as client:
        response = client.post(
            WORKER_RENDER_NARRATION_TASK_PATH,
            headers=_worker_headers(),
            json={
                "slots": {"echo": "x"},
                "style_guard": "neutral",
                "model": "test-model",
                "temperature": 0.1,
                "max_retries": 1,
                "timeout_seconds": 2.0,
            },
        )
        assert response.status_code == 200
        assert response.json()["narration_text"] == "narration ok"

        legacy = client.post(
            "/v2/llm/tasks/render-narration",
            headers=_worker_headers(),
            json={
                "slots": {"echo": "x"},
                "style_guard": "neutral",
                "model": "test-model",
            },
        )
        assert legacy.status_code == 404


def test_worker_json_object_uses_internal_path_and_v2_is_removed(monkeypatch) -> None:
    async def _fake_execute_json_object_task(_payload):  # noqa: ANN001, ANN201
        return (
            WorkerTaskJsonObjectResponse(
                payload={"ok": True},
                model="test-model",
                attempts=1,
                retry_count=0,
                duration_ms=5,
            ),
            TaskUsage(total_tokens=28),
        )

    monkeypatch.setattr(task_service, "execute_json_object_task", _fake_execute_json_object_task)
    with TestClient(app) as client:
        response = client.post(
            WORKER_JSON_OBJECT_TASK_PATH,
            headers=_worker_headers(),
            json={
                "system_prompt": "return json",
                "user_prompt": "{\"ok\":true}",
                "model": "test-model",
                "temperature": 0.1,
                "max_retries": 1,
                "timeout_seconds": 2.0,
            },
        )
        assert response.status_code == 200
        assert response.json()["payload"] == {"ok": True}

        legacy = client.post(
            "/v2/llm/tasks/json-object",
            headers=_worker_headers(),
            json={
                "system_prompt": "return json",
                "user_prompt": "{\"ok\":true}",
                "model": "test-model",
            },
        )
        assert legacy.status_code == 404


def test_worker_task_requires_internal_token() -> None:
    with TestClient(app) as client:
        response = client.post(
            WORKER_ROUTE_INTENT_TASK_PATH,
            json={
                "scene_context": {"moves": [], "fallback_move": "global.help_me_progress"},
                "text": "help me progress",
                "model": "test-model",
                "temperature": 0.1,
                "max_retries": 1,
                "timeout_seconds": 2.0,
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "worker_token_invalid"
