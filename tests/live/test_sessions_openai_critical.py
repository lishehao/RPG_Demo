from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

PACK_PATH = Path("sample_data/story_pack_v1.json")

pytestmark = pytest.mark.live_openai_critical


def _has_openai_env() -> bool:
    base_url = (os.getenv("APP_LLM_OPENAI_BASE_URL") or "").strip()
    api_key = (os.getenv("APP_LLM_OPENAI_API_KEY") or "").strip()
    model = (os.getenv("APP_LLM_OPENAI_ROUTE_MODEL") or "").strip() or (
        os.getenv("APP_LLM_OPENAI_NARRATION_MODEL") or ""
    ).strip() or (os.getenv("APP_LLM_OPENAI_MODEL") or "").strip()
    return bool(base_url and api_key and model)


def test_live_openai_session_step_critical_path(client) -> None:
    if not _has_openai_env():
        pytest.skip("missing OpenAI runtime env for live critical test")

    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    created = client.post("/v2/stories", json={"title": "Live OpenAI Critical Story", "pack_json": pack})
    assert created.status_code == 200
    story_id = created.json()["story_id"]

    published = client.post(f"/v2/stories/{story_id}/publish", json={})
    assert published.status_code == 200
    version = published.json()["version"]

    session = client.post("/v2/sessions", json={"story_id": story_id, "version": version})
    assert session.status_code == 200
    session_id = session.json()["session_id"]

    step = client.post(
        f"/v2/sessions/{session_id}/step",
        json={
            "client_action_id": "live-critical-1",
            "input": {"type": "text", "text": "help me progress"},
            "dev_mode": False,
        },
    )
    assert step.status_code == 200, step.text
    body = step.json()
    assert body["recognized"]["route_source"] == "llm"
    assert isinstance(body["narration_text"], str)
    assert body["narration_text"].strip()
