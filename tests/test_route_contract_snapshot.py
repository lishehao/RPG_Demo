from __future__ import annotations

from rpg_backend.main import app


def test_openapi_paths_snapshot() -> None:
    expected_paths = {
        "/health",
        "/admin/auth/login",
        "/stories/generate",
        "/stories",
        "/sessions",
        "/sessions/{session_id}",
        "/sessions/{session_id}/history",
        "/sessions/{session_id}/step",
    }
    actual_paths = set(app.openapi()["paths"].keys())
    assert actual_paths == expected_paths

