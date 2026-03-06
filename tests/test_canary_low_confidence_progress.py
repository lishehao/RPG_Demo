from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.route_paths import session_path, session_step_path, sessions_path, story_publish_path, stories_path
from tests.helpers.providers import DeterministicProvider

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _bootstrap_session(client) -> str:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    story_resp = client.post(stories_path(), json={"title": "HealthyPath Story", "pack_json": pack})
    story_id = story_resp.json()["story_id"]
    publish_resp = client.post(story_publish_path(story_id), json={})
    version = publish_resp.json()["version"]
    session_resp = client.post(sessions_path(), json={"story_id": story_id, "version": version})
    return session_resp.json()["session_id"]


def test_three_text_inputs_advance_progress_on_healthy_path(client, monkeypatch) -> None:
    from rpg_backend.api import sessions as sessions_api

    monkeypatch.setattr(sessions_api, "get_llm_provider", lambda: DeterministicProvider())
    session_id = _bootstrap_session(client)
    start = client.get(session_path(session_id)).json()
    start_progress = sum(int(v) for v in start["beat_progress"].values())

    for idx in range(1, 4):
        response = client.post(
            session_step_path(session_id),
            json={
                "client_action_id": f"healthy-text-{idx}",
                "input": {"type": "text", "text": "help me progress"},
            },
        )
        assert response.status_code == 200

    end = client.get(session_path(session_id)).json()
    end_progress = sum(int(v) for v in end["beat_progress"].values())
    assert end_progress > start_progress
