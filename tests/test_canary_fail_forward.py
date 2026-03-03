from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.providers import DeterministicProvider

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _bootstrap_session(client) -> str:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    story_resp = client.post("/stories", json={"title": "FailForward Story", "pack_json": pack})
    story_id = story_resp.json()["story_id"]
    publish_resp = client.post(f"/stories/{story_id}/publish", json={})
    version = publish_resp.json()["version"]
    session_resp = client.post("/sessions", json={"story_id": story_id, "version": version})
    return session_resp.json()["session_id"]


def test_fail_forward_triggers_for_always_fail_forward_move(client, monkeypatch) -> None:
    from rpg_backend.api import sessions as sessions_api

    monkeypatch.setattr(sessions_api, "get_llm_provider", lambda: DeterministicProvider())
    session_id = _bootstrap_session(client)

    response = client.post(
        f"/sessions/{session_id}/step",
        json={
            "client_action_id": "help-attempt",
            "input": {"type": "button", "move_id": "global.help_me_progress"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recognized"]["move_id"] == "global.help_me_progress"
    assert body["resolution"]["result"] == "fail_forward"
    assert (
        body["resolution"]["costs_summary"] != "none"
        or body["resolution"]["consequences_summary"] != "none"
    )
