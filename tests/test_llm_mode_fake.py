from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import rpg_backend.main as main_module
from rpg_backend.config import Settings
from rpg_backend.narrative.fake_gateway import (
    FAKE_NARRATIVE_SEED,
    FakeNarrativeGateway,
    ensure_fake_demo_template,
)
from rpg_backend.narrative.gateway import NarrativeLLMGateway
from rpg_backend.narrative.service import get_narrative_service


ROOT = Path(__file__).resolve().parents[1]


def test_llm_mode_defaults_to_live(monkeypatch) -> None:
    monkeypatch.delenv("APP_LLM_MODE", raising=False)
    assert Settings(_env_file=None).llm_mode == "live"


def test_llm_mode_reads_app_llm_mode_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_LLM_MODE", "fake")
    assert Settings(_env_file=None).llm_mode == "fake"


def test_live_mode_keeps_existing_gateway_selection(tmp_path) -> None:
    db_path = str(tmp_path / "runtime.sqlite3")
    no_key = get_narrative_service(Settings(_env_file=None, runtime_state_db_path=db_path))
    assert no_key._gateway is None

    with_key = get_narrative_service(
        Settings(
            _env_file=None,
            runtime_state_db_path=db_path,
            responses_play_base_url="http://127.0.0.1:9/v1",
            responses_play_api_key="test-placeholder",
            responses_play_model="test-model",
        )
    )
    assert isinstance(with_key._gateway, NarrativeLLMGateway)


def test_fake_mode_uses_fake_gateway_and_seeds_one_template(tmp_path) -> None:
    service = get_narrative_service(
        Settings(_env_file=None, llm_mode="fake", runtime_state_db_path=str(tmp_path / "runtime.sqlite3"))
    )
    assert isinstance(service._gateway, FakeNarrativeGateway)

    first = ensure_fake_demo_template(service)
    second = ensure_fake_demo_template(service)
    assert first == second
    public = service.list_public_templates(viewer_user_id="anyone").items
    assert [template.template_id for template in public] == [first]
    assert public[0].seed == FAKE_NARRATIVE_SEED


def test_fake_mode_api_serves_template_and_plays_a_turn(tmp_path) -> None:
    service = get_narrative_service(
        Settings(_env_file=None, llm_mode="fake", runtime_state_db_path=str(tmp_path / "runtime.sqlite3"))
    )
    ensure_fake_demo_template(service)
    original_service = main_module.narrative_service
    main_module.narrative_service = service
    try:
        client = TestClient(main_module.app)
        templates = client.get("/narrative/templates")
        assert templates.status_code == 200
        items = templates.json()["items"]
        assert len(items) == 1
        template_id = items[0]["template_id"]

        started = client.post(f"/narrative/templates/{template_id}/sessions", json={})
        assert started.status_code == 200
        session_id = started.json()["session"]["session_id"]

        turn = client.post(
            f"/narrative/sessions/{session_id}/story/turns",
            json={"chosen_option_index": 0},
        )
        assert turn.status_code == 200
        body = turn.json()
        assert body["is_complete"] is False
        assert body["narrator_message"]["content"]
        assert len(body["narrator_message"]["options"]) >= 3
    finally:
        main_module.narrative_service = original_service


def test_backend_started_in_fake_mode_is_playable_without_a_key(tmp_path) -> None:
    script = """
import json
from fastapi.testclient import TestClient
from rpg_backend.main import app

client = TestClient(app)
health = client.get("/health").json()
items = client.get("/narrative/templates").json()["items"]
session = client.post(f"/narrative/templates/{items[0]['template_id']}/sessions", json={}).json()
turn = client.post(
    f"/narrative/sessions/{session['session']['session_id']}/story/turns",
    json={"free_input": "I ask the dean to read the ledger timestamp aloud."},
)
print(json.dumps({"health": health, "template_count": len(items), "turn_status": turn.status_code}))
"""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("APP_RESPONSES_") and not key.startswith("APP_GATEWAY_")
    }
    env.update(
        {
            "APP_LLM_MODE": "fake",
            "APP_RUNTIME_STATE_DB_PATH": str(tmp_path / "runtime.sqlite3"),
            "APP_STORY_LIBRARY_DB_PATH": str(tmp_path / "library.sqlite3"),
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={**env, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["health"]["text_llm"] == "fake"
    assert result["template_count"] == 1
    assert result["turn_status"] == 200
