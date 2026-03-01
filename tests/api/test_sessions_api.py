from __future__ import annotations

import json
from pathlib import Path

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _bootstrap_story(client):
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    created = client.post("/stories", json={"title": "Session Story", "pack_json": pack})
    story_id = created.json()["story_id"]
    published = client.post(f"/stories/{story_id}/publish", json={})
    version = published.json()["version"]
    return story_id, version


def test_session_create_and_get(client) -> None:
    story_id, version = _bootstrap_story(client)

    created = client.post("/sessions", json={"story_id": story_id, "version": version})
    assert created.status_code == 200
    body = created.json()
    session_id = body["session_id"]
    assert body["scene_id"] == "sc1"

    fetched = client.get(f"/sessions/{session_id}?dev_mode=true")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["session_id"] == session_id
    assert "state" in fetched_body


def test_step_is_idempotent_by_client_action_id(client) -> None:
    story_id, version = _bootstrap_story(client)
    session_resp = client.post("/sessions", json={"story_id": story_id, "version": version})
    session_id = session_resp.json()["session_id"]

    payload = {
        "client_action_id": "action-1",
        "input": {"type": "text", "text": "random noise"},
        "dev_mode": False,
    }
    first = client.post(f"/sessions/{session_id}/step", json=payload)
    second = client.post(f"/sessions/{session_id}/step", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_step_tolerates_button_without_move_id(client) -> None:
    story_id, version = _bootstrap_story(client)
    session_resp = client.post("/sessions", json={"story_id": story_id, "version": version})
    session_id = session_resp.json()["session_id"]

    payload = {
        "client_action_id": "shape-1",
        "input": {"type": "button"},
    }
    response = client.post(f"/sessions/{session_id}/step", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["recognized"]["move_id"] == "global.help_me_progress"


def test_step_tolerates_missing_or_invalid_input_shape(client) -> None:
    story_id, version = _bootstrap_story(client)
    session_resp = client.post("/sessions", json={"story_id": story_id, "version": version})
    session_id = session_resp.json()["session_id"]

    missing_input = client.post(
        f"/sessions/{session_id}/step",
        json={"client_action_id": "shape-2"},
    )
    assert missing_input.status_code == 200
    assert missing_input.json()["recognized"]["move_id"] in {
        "global.help_me_progress",
        "global.clarify",
    }

    invalid_type = client.post(
        f"/sessions/{session_id}/step",
        json={"client_action_id": "shape-3", "input": {"type": "nonsense", "text": ""}},
    )
    assert invalid_type.status_code == 200
    assert invalid_type.json()["recognized"]["move_id"] in {
        "global.help_me_progress",
        "global.clarify",
    }
