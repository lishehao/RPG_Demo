from __future__ import annotations

import time

from fastapi.testclient import TestClient

import rpg_backend.author.jobs as author_jobs_module
import rpg_backend.main as main_module
from rpg_backend.author.jobs import AuthorJobService
from rpg_backend.config import get_settings
from rpg_backend.library.service import StoryLibraryService
from rpg_backend.library.storage import SQLiteStoryLibraryStorage
from rpg_backend.main import app
from rpg_backend.play.gateway import PlayGatewayError
from rpg_backend.play.service import PlaySessionService
from tests.auth_helpers import ensure_authenticated_client
from tests.author_fixtures import FakeGateway


class _BenchmarkFakePlayClient:
    def __init__(self) -> None:
        self.max_output_tokens_interpret = 220
        self.max_output_tokens_interpret_repair = 320
        self.max_output_tokens_ending_judge = 180
        self.max_output_tokens_ending_judge_repair = 120
        self.max_output_tokens_pyrrhic_critic = 120
        self.max_output_tokens_render = 420
        self.max_output_tokens_render_repair = 640
        self.use_session_cache = True
        self.call_trace: list[dict[str, object]] = []
        self._response_index = 0
        self._responses = {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": [],
                    "risk_level": "medium",
                    "execution_frame": "public",
                    "tactic_summary": "You force the ledgers into the open before the room can splinter.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "mixed",
                }
            ],
            "play_pyrrhic_critic": [
                {
                    "ending_id": "mixed",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You force the archive delegates to compare the ledgers in public, and the room tilts toward one record instead of three competing lies.",
                    "suggested_actions": [
                        {"label": "Name the saboteur", "prompt": "You publicly identify who altered the record and demand an answer."},
                        {"label": "Stabilize the hall", "prompt": "You steady the witnesses and keep the hearing on one verified transcript."},
                        {"label": "Press for a ruling", "prompt": "You force the council to commit to one public record before rumor hardens."},
                    ],
                }
            ],
        }

    def _invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, object],
        max_output_tokens: int | None,
        previous_response_id: str | None = None,
        operation_name: str | None = None,
    ):
        del system_prompt
        operation = operation_name or "unknown"
        queue = self._responses.get(operation)
        if not queue:
            raise PlayGatewayError(code="play_llm_invalid_json", message=f"missing fake payload for {operation}", status_code=502)
        next_item = queue.pop(0)
        self._response_index += 1
        response_id = f"play-{self._response_index}"
        self.call_trace.append(
            {
                "operation": operation,
                "response_id": response_id,
                "used_previous_response_id": bool(previous_response_id),
                "session_cache_enabled": True,
                "max_output_tokens": max_output_tokens,
                "input_characters": len(str(user_payload)),
                "usage": {
                    "input_tokens": 50,
                    "output_tokens": 20,
                    "total_tokens": 70,
                    "cached_input_tokens": 15,
                    "cache_creation_input_tokens": 5,
                },
            }
        )
        return type(
            "FakeResponse",
            (),
            {
                "payload": next_item,
                "response_id": response_id,
                "usage": {
                    "input_tokens": 50,
                    "output_tokens": 20,
                    "total_tokens": 70,
                    "cached_input_tokens": 15,
                    "cache_creation_input_tokens": 5,
                },
                "input_characters": len(str(user_payload)),
            },
        )()


def test_benchmark_routes_return_404_when_disabled(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("APP_ENABLE_BENCHMARK_API", raising=False)
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="bench-disabled@example.com", display_name="Bench Disabled")
        response = client.get("/benchmark/author/jobs/job-missing/diagnostics")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 404


def test_benchmark_routes_expose_author_and_play_diagnostics(monkeypatch, tmp_path) -> None:
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    original_play_service = main_module.play_session_service
    original_gateway_factory = author_jobs_module.get_author_llm_gateway

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENABLE_BENCHMARK_API", "1")
    author_jobs_module.get_author_llm_gateway = lambda: FakeGateway()
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    play_gateway = _BenchmarkFakePlayClient()
    play_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: play_gateway,
    )
    author_service = AuthorJobService()
    main_module.author_job_service = author_service
    main_module.story_library_service = library_service
    main_module.play_session_service = play_service

    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="bench-enabled@example.com", display_name="Bench Enabled")
        preview_response = client.post(
            "/author/story-previews",
            json={"prompt_seed": "A city archivist must restore one public record before an emergency vote hardens into factional law."},
        )
        job_response = client.post(
            "/author/jobs",
            json={
                "prompt_seed": "A city archivist must restore one public record before an emergency vote hardens into factional law.",
                "preview_id": preview_response.json()["preview_id"],
            },
        )
        job_id = job_response.json()["job_id"]
        for _ in range(100):
            status_response = client.get(f"/author/jobs/{job_id}")
            if status_response.json()["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)
        assert status_response.json()["status"] == "completed"

        author_diagnostics = client.get(f"/benchmark/author/jobs/{job_id}/diagnostics")
        published_story = client.post(f"/author/jobs/{job_id}/publish")
        created_session = client.post("/play/sessions", json={"story_id": published_story.json()["story_id"]})
        submitted_turn = client.post(
            f"/play/sessions/{created_session.json()['session_id']}/turns",
            json={"input_text": "I force the delegates to compare the sealed ledgers in public before anyone can bury the discrepancy."},
        )
        play_diagnostics = client.get(f"/benchmark/play/sessions/{created_session.json()['session_id']}/diagnostics")
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service
        main_module.play_session_service = original_play_service
        author_jobs_module.get_author_llm_gateway = original_gateway_factory
        get_settings.cache_clear()

    assert preview_response.status_code == 200
    assert job_response.status_code == 200
    assert author_diagnostics.status_code == 200
    assert author_diagnostics.json()["job_id"] == job_id
    assert author_diagnostics.json()["events"][0]["emitted_at"]
    assert author_diagnostics.json()["stage_timings"]
    assert "story_frame_source" in author_diagnostics.json()["source_summary"]
    assert "gameplay_semantics_source" in author_diagnostics.json()["source_summary"]

    assert published_story.status_code == 200
    assert created_session.status_code == 200
    assert submitted_turn.status_code == 200
    assert play_diagnostics.status_code == 200
    assert play_diagnostics.json()["summary"]["turn_count"] == 1
    assert play_diagnostics.json()["turn_traces"][0]["turn_elapsed_ms"] >= 0
    assert play_diagnostics.json()["turn_traces"][0]["session_cache_enabled"] is True
    assert play_diagnostics.json()["turn_traces"][0]["execution_frame"] == "public"
    assert play_diagnostics.json()["summary"]["usage_totals"]["input_tokens"] >= 50
