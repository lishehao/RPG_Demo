from __future__ import annotations


def test_auth_required_returns_unified_error_envelope(client) -> None:
    response = client.get("/stories")
    assert response.status_code == 401
    body = response.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "retryable", "request_id"}
    assert body["error"]["code"] == "unauthorized"
    assert isinstance(body["error"]["request_id"], str)


def test_story_session_step_history_flow(client, auth_headers) -> None:
    generated = client.post(
        "/stories/generate",
        headers=auth_headers,
        json={"theme": "fantasy", "difficulty": "medium"},
    )
    assert generated.status_code == 200
    story_id = generated.json()["story_id"]
    assert generated.json()["published"] is True

    listed = client.get("/stories", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["story_id"] == story_id for item in listed.json()["stories"])

    session_created = client.post("/sessions", headers=auth_headers, json={"story_id": story_id})
    assert session_created.status_code == 200
    session_id = session_created.json()["session_id"]

    first_step = client.post(
        f"/sessions/{session_id}/step",
        headers=auth_headers,
        json={"move_id": "look"},
    )
    assert first_step.status_code == 200
    first_body = first_step.json()
    assert set(first_body.keys()) == {"turn", "narration", "actions", "risk_hint"}
    assert first_body["turn"] == 1
    assert first_body["risk_hint"] in {"low", "medium", "high"}
    assert all(set(action.keys()) == {"id", "label"} for action in first_body["actions"])

    second_step = client.post(
        f"/sessions/{session_id}/step",
        headers=auth_headers,
        json={"free_text": "I try to climb the tree"},
    )
    assert second_step.status_code == 200
    assert second_step.json()["turn"] == 2

    history = client.get(f"/sessions/{session_id}/history", headers=auth_headers)
    assert history.status_code == 200
    history_items = history.json()["history"]
    assert len(history_items) == 2
    assert history_items[0]["turn"] == 1
    assert history_items[1]["turn"] == 2
    assert all(set(item.keys()) == {"turn", "narration", "actions"} for item in history_items)


def test_get_session_shape(client, auth_headers) -> None:
    generated = client.post(
        "/stories/generate",
        headers=auth_headers,
        json={"theme": "sci-fi", "difficulty": "hard"},
    )
    story_id = generated.json()["story_id"]

    session_created = client.post("/sessions", headers=auth_headers, json={"story_id": story_id})
    session_id = session_created.json()["session_id"]

    session = client.get(f"/sessions/{session_id}", headers=auth_headers)
    assert session.status_code == 200
    body = session.json()
    assert set(body.keys()) == {"session_id", "story_id", "created_at", "state"}
    assert body["session_id"] == session_id
    assert body["story_id"] == story_id
    assert body["state"] in {"active", "completed"}

