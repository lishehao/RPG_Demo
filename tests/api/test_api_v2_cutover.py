from __future__ import annotations


def _assert_not_found_envelope(response) -> None:
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["retryable"] is False


def test_v1_business_routes_are_removed(client) -> None:
    responses = [
        client.get("/stories/demo-story"),
        client.post("/stories/generate", json={"seed_text": "legacy route"}),
        client.get("/sessions/demo-session"),
        client.post(
            "/sessions/demo-session/step",
            json={"client_action_id": "legacy-step", "input": {"type": "move", "move_id": "m1"}},
        ),
        client.get("/admin/sessions/demo-session/timeline"),
        client.get("/admin/observability/runtime-errors"),
    ]
    for response in responses:
        _assert_not_found_envelope(response)


def test_probe_routes_stay_unversioned(client) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    _assert_not_found_envelope(client.get("/v2/health"))
