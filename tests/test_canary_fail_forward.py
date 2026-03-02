from __future__ import annotations

import json
from pathlib import Path

from rpg_backend.llm.base import LLMProvider, RouteIntentResult

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _bootstrap_session(client) -> str:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    story_resp = client.post("/stories", json={"title": "FailForward Story", "pack_json": pack})
    story_id = story_resp.json()["story_id"]
    publish_resp = client.post(f"/stories/{story_id}/publish", json={})
    version = publish_resp.json()["version"]
    session_resp = client.post("/sessions", json={"story_id": story_id, "version": version})
    return session_resp.json()["session_id"]


class _DeterministicProvider(LLMProvider):
    def route_intent(self, scene_context, text):  # noqa: ANN001, ANN201
        fallback = scene_context.get("fallback_move", "global.help_me_progress")
        return RouteIntentResult(
            move_id=fallback,
            args={},
            confidence=0.95,
            interpreted_intent=(text or "").strip() or "help me progress",
        )

    def render_narration(self, slots, style_guard):  # noqa: ANN001, ANN201
        return f"{slots['echo']} {slots['commit']} {slots['hook']}"


def test_fail_forward_triggers_when_preconditions_not_met(client, monkeypatch) -> None:
    from rpg_backend.api import sessions as sessions_api

    monkeypatch.setattr(sessions_api, "get_llm_provider", lambda: _DeterministicProvider())
    session_id = _bootstrap_session(client)

    client.post(
        f"/sessions/{session_id}/step",
        json={"client_action_id": "prep-1", "input": {"type": "button", "move_id": "global.clarify"}},
    )
    client.post(
        f"/sessions/{session_id}/step",
        json={"client_action_id": "prep-2", "input": {"type": "button", "move_id": "global.clarify"}},
    )
    client.post(
        f"/sessions/{session_id}/step",
        json={"client_action_id": "prep-3", "input": {"type": "button", "move_id": "global.clarify"}},
    )

    response = client.post(
        f"/sessions/{session_id}/step",
        json={"client_action_id": "decode-attempt", "input": {"type": "button", "move_id": "decode_core"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["resolution"]["result"] == "fail_forward"
    assert (
        body["resolution"]["costs_summary"] != "none"
        or body["resolution"]["consequences_summary"] != "none"
    )
