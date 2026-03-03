from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.providers import DeterministicProvider

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _bootstrap_session(client) -> str:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    story_resp = client.post("/stories", json={"title": "Canary Story", "pack_json": pack})
    story_id = story_resp.json()["story_id"]
    publish_resp = client.post(f"/stories/{story_id}/publish", json={})
    version = publish_resp.json()["version"]
    session_resp = client.post("/sessions", json={"story_id": story_id, "version": version})
    return session_resp.json()["session_id"]


def test_any_text_input_never_4xx_for_active_session(client, monkeypatch) -> None:
    from rpg_backend.api import sessions as sessions_api

    monkeypatch.setattr(sessions_api, "get_llm_provider", lambda: DeterministicProvider())
    session_id = _bootstrap_session(client)
    texts = ["", "   ", "@@@###", "随便写点东西", "x" * 2048]

    for idx, text in enumerate(texts, start=1):
        payload = {
            "client_action_id": f"input-tolerance-{idx}",
            "input": {"type": "text", "text": text},
            "dev_mode": False,
        }
        response = client.post(f"/sessions/{session_id}/step", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["recognized"]["move_id"]
