from __future__ import annotations

from fastapi.testclient import TestClient

import rpg_backend.main as backend_main


def test_removed_internal_llm_task_routes_return_404() -> None:
    with TestClient(backend_main.app) as client:
        for path in (
            "/internal/llm/tasks/json-object",
            "/internal/llm/tasks/route-intent",
            "/internal/llm/tasks/render-narration",
        ):
            response = client.post(path, json={})
            assert response.status_code == 404
