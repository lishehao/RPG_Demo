from __future__ import annotations

from fastapi.testclient import TestClient

import rpg_backend.main as backend_main


def test_legacy_internal_worker_routes_are_removed() -> None:
    with TestClient(backend_main.app) as client:
        for path in (
            "/internal/llm/tasks/json-object",
            "/internal/llm/tasks/route-intent",
            "/internal/llm/tasks/render-narration",
        ):
            response = client.post(path, json={})
            assert response.status_code == 404
