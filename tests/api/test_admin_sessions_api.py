from __future__ import annotations

import json
from pathlib import Path

from app.llm.base import LLMProvider

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _bootstrap_story(client):
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    created = client.post("/stories", json={"title": "Admin Session Story", "pack_json": pack})
    story_id = created.json()["story_id"]
    published = client.post(f"/stories/{story_id}/publish", json={})
    version = published.json()["version"]
    return story_id, version


def _create_session(client) -> str:
    story_id, version = _bootstrap_story(client)
    session_resp = client.post("/sessions", json={"story_id": story_id, "version": version})
    assert session_resp.status_code == 200
    return session_resp.json()["session_id"]


class _RouteFailureProvider(LLMProvider):
    @property
    def runtime_failfast_on_route_error(self) -> bool:
        return True

    def route_intent(self, scene_context, text):  # noqa: ANN001, ANN201
        raise RuntimeError("route failed")

    def render_narration(self, slots, style_guard):  # noqa: ANN001, ANN201
        return f"{slots['echo']} {slots['commit']} {slots['hook']}"


def test_admin_timeline_contains_started_and_succeeded_events(client) -> None:
    session_id = _create_session(client)
    step = client.post(
        f"/sessions/{session_id}/step",
        json={
            "client_action_id": "admin-step-1",
            "input": {"type": "text", "text": "help me progress"},
            "dev_mode": False,
        },
    )
    assert step.status_code == 200

    timeline = client.get(f"/admin/sessions/{session_id}/timeline")
    assert timeline.status_code == 200
    body = timeline.json()
    event_types = [event["event_type"] for event in body["events"]]
    assert "step_started" in event_types
    assert "step_succeeded" in event_types


def test_admin_timeline_contains_step_failed_on_openai_strict_error(client, monkeypatch) -> None:
    from app.api import sessions as sessions_api

    session_id = _create_session(client)
    monkeypatch.setattr(sessions_api, "get_llm_provider", lambda: _RouteFailureProvider())

    step = client.post(
        f"/sessions/{session_id}/step",
        json={
            "client_action_id": "admin-step-fail-1",
            "input": {"type": "text", "text": "nonsense"},
            "dev_mode": False,
        },
    )
    assert step.status_code == 503

    timeline = client.get(f"/admin/sessions/{session_id}/timeline")
    assert timeline.status_code == 200
    failed_events = [event for event in timeline.json()["events"] if event["event_type"] == "step_failed"]
    assert failed_events
    assert failed_events[-1]["payload"]["error_code"] == "llm_route_failed"


def test_admin_timeline_contains_step_replayed_for_idempotent_call(client) -> None:
    session_id = _create_session(client)
    payload = {
        "client_action_id": "admin-replay-1",
        "input": {"type": "text", "text": "help me progress"},
        "dev_mode": False,
    }
    first = client.post(f"/sessions/{session_id}/step", json=payload)
    second = client.post(f"/sessions/{session_id}/step", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200

    timeline = client.get(f"/admin/sessions/{session_id}/timeline")
    assert timeline.status_code == 200
    event_types = [event["event_type"] for event in timeline.json()["events"]]
    assert "step_replayed" in event_types


def test_admin_feedback_create_and_list(client) -> None:
    session_id = _create_session(client)
    created = client.post(
        f"/admin/sessions/{session_id}/feedback",
        json={
            "verdict": "bad",
            "reason_tags": ["pacing", "choice_clarity"],
            "note": "midgame feels flat",
            "turn_index": 6,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["session_id"] == session_id
    assert body["verdict"] == "bad"
    assert body["reason_tags"] == ["pacing", "choice_clarity"]
    assert body["turn_index"] == 6

    listed = client.get(f"/admin/sessions/{session_id}/feedback")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert items
    assert items[0]["feedback_id"] == body["feedback_id"]


def test_admin_endpoints_return_404_for_missing_session(client) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    timeline = client.get(f"/admin/sessions/{missing}/timeline")
    assert timeline.status_code == 404

    create_feedback = client.post(
        f"/admin/sessions/{missing}/feedback",
        json={"verdict": "bad", "reason_tags": [], "note": "n/a"},
    )
    assert create_feedback.status_code == 404

    list_feedback = client.get(f"/admin/sessions/{missing}/feedback")
    assert list_feedback.status_code == 404
