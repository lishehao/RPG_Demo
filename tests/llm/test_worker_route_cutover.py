from __future__ import annotations

from fastapi.testclient import TestClient

from rpg_backend.config.settings import get_settings
from rpg_backend.llm.task_executor import TaskUsage
from rpg_backend.llm_worker.main import app, task_service
from rpg_backend.llm_worker.route_paths import WORKER_JSON_OBJECT_TASK_PATH
from rpg_backend.llm_worker.schemas import WorkerTaskJsonObjectResponse


def _worker_headers() -> dict[str, str]:
    return {"X-Internal-Worker-Token": get_settings().internal_worker_token}


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

        legacy_route = client.post(
            "/internal/llm/tasks/route-intent",
            headers=_worker_headers(),
            json={"model": "test-model"},
        )
        assert legacy_route.status_code == 404

        legacy_narration = client.post(
            "/internal/llm/tasks/render-narration",
            headers=_worker_headers(),
            json={"model": "test-model"},
        )
        assert legacy_narration.status_code == 404


def test_worker_task_requires_internal_token() -> None:
    with TestClient(app) as client:
        response = client.post(
            WORKER_JSON_OBJECT_TASK_PATH,
            json={
                "system_prompt": "return json",
                "user_prompt": "{\"ok\":true}",
                "model": "test-model",
                "temperature": 0.1,
                "max_retries": 1,
                "timeout_seconds": 2.0,
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "worker_token_invalid"
