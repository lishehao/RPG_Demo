from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.route_paths import session_path, session_step_path, sessions_path, story_publish_path, stories_path
from tests.helpers.providers import DeterministicProvider

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _bootstrap_session(client) -> str:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    story_resp = client.post(stories_path(), json={"title": "Completion Story", "pack_json": pack})
    story_id = story_resp.json()["story_id"]
    publish_resp = client.post(story_publish_path(story_id), json={})
    version = publish_resp.json()["version"]
    session_resp = client.post(sessions_path(), json={"story_id": story_id, "version": version})
    return session_resp.json()["session_id"]


def test_sample_story_finishes_in_14_to_16_steps(client, monkeypatch) -> None:
    from rpg_backend.api import sessions as sessions_api

    monkeypatch.setattr(sessions_api, "get_llm_provider", lambda: DeterministicProvider())
    session_id = _bootstrap_session(client)
    ended = False
    steps = 0

    for idx in range(1, 25):
        response = client.post(
            session_step_path(session_id),
            json={
                "client_action_id": f"pace-{idx}",
                "input": {"type": "text", "text": "keep moving"},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["resolution"]["consequences_summary"] != "none"

        steps = idx
        if body.get("debug") is not None:
            pass

        session_state = client.get(session_path(session_id)).json()
        ended = bool(session_state["ended"])
        if ended:
            break

    assert ended
    assert 14 <= steps <= 16
