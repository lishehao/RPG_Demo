from __future__ import annotations

import time

from fastapi.testclient import TestClient

import rpg_backend.author.jobs as author_jobs_module
import rpg_backend.main as main_module
from rpg_backend.author.contracts import AuthorJobProgress
from rpg_backend.author.jobs import AuthorJobService, _AuthorJobRecord
from rpg_backend.author.preview import build_author_story_summary
from rpg_backend.config import get_settings
from rpg_backend.library.service import StoryLibraryService
from rpg_backend.library.storage import SQLiteStoryLibraryStorage
from rpg_backend.main import app
from rpg_backend.play.gateway import PlayGatewayError
from rpg_backend.play.service import PlaySessionService
from tests.auth_helpers import ensure_authenticated_client
from tests.author_fixtures import FakeGateway, author_fixture_bundle
from tests.test_story_library_api import _preview_response


class _BenchmarkFakePlayClient:
    def __init__(self, *, target_npc_ids: list[str] | None = None) -> None:
        self.model = "fake-play-model"
        self.transport_style = "responses"
        self.max_output_tokens_interpret = 220
        self.max_output_tokens_interpret_repair = 320
        self.max_output_tokens_ending_judge = 180
        self.max_output_tokens_ending_judge_repair = 120
        self.max_output_tokens_pyrrhic_critic = 120
        self.max_output_tokens_render = 420
        self.max_output_tokens_render_repair = 640
        self.use_session_cache = True
        self.transport_style = "responses"
        self.model = "test-play-model"
        self.call_trace: list[dict[str, object]] = []
        self._response_index = 0
        self._responses = {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": list(target_npc_ids or []),
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

    def text_policy(self, capability: str):
        budget_by_capability = {
            "play.interpret": self.max_output_tokens_interpret,
            "play.interpret_repair": self.max_output_tokens_interpret_repair,
            "play.ending_judge": self.max_output_tokens_ending_judge,
            "play.pyrrhic_critic": self.max_output_tokens_pyrrhic_critic,
            "play.render": self.max_output_tokens_render,
            "play.render_repair": self.max_output_tokens_render_repair,
        }
        return type(
            "Policy",
            (),
            {
                "capability": capability,
                "max_output_tokens": budget_by_capability.get(capability),
                "transport_style": self.transport_style,
                "use_session_cache": self.use_session_cache,
                "enable_thinking": False,
                "model": self.model,
            },
        )()

    def invoke_text_capability(self, capability: str, request):
        raw = self._invoke_json(
            system_prompt=request.system_prompt,
            user_payload=request.user_payload,
            max_output_tokens=request.max_output_tokens,
            previous_response_id=request.previous_response_id,
            operation_name=request.operation_name,
        )
        return type(
            "CapabilityResult",
            (),
            {
                "payload": raw.payload,
                "response_id": raw.response_id,
                "usage": raw.usage,
                "input_characters": raw.input_characters,
                "capability": capability,
                "provider": "test",
                "model": self.model,
                "transport_style": self.transport_style,
                "fallback_source": getattr(raw, "fallback_source", None),
            },
        )()

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

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENABLE_BENCHMARK_API", "1")
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    play_gateway = _BenchmarkFakePlayClient()
    play_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: play_gateway,
    )
    author_service = AuthorJobService(gateway_factory=lambda _settings=None: FakeGateway())
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
        for _ in range(1000):
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
        get_settings.cache_clear()

    assert preview_response.status_code == 200
    assert job_response.status_code == 200
    assert author_diagnostics.status_code == 200
    assert author_diagnostics.json()["job_id"] == job_id
    assert author_diagnostics.json()["content_prompt_profile"] == "role_conditioned"
    assert author_diagnostics.json()["events"][0]["emitted_at"]
    assert author_diagnostics.json()["stage_timings"]
    assert "story_frame_source" in author_diagnostics.json()["source_summary"]
    assert "gameplay_semantics_source" in author_diagnostics.json()["source_summary"]
    assert "beat_runtime_shard_source" in author_diagnostics.json()["source_summary"]
    assert "context_lock_violation_distribution" in author_diagnostics.json()
    assert "snapshot_stage_distribution" in author_diagnostics.json()
    assert "beat_runtime_shard_count" in author_diagnostics.json()
    assert author_diagnostics.json()["beat_runtime_shard_count"] >= 1
    assert "beat_runtime_shard_fallback_count" in author_diagnostics.json()
    assert "beat_runtime_shard_elapsed_ms" in author_diagnostics.json()
    assert "beat_runtime_shard_drift_distribution" in author_diagnostics.json()
    assert "roster_enabled" in author_diagnostics.json()
    assert "roster_selection_count" in author_diagnostics.json()
    assert "roster_retrieval_trace" in author_diagnostics.json()
    if author_diagnostics.json()["roster_retrieval_trace"]:
        first_trace = author_diagnostics.json()["roster_retrieval_trace"][0]
        assert "query_language" in first_trace
        assert "story_query_text" in first_trace
        assert "slot_query_text" in first_trace
        assert "candidate_pool_size" in first_trace
        assert "assignment_rank" in first_trace
        assert "assignment_score" in first_trace
        assert "selected_template_version" in first_trace
        if first_trace["top_candidates"]:
            assert "template_version" in first_trace["top_candidates"][0]

    assert published_story.status_code == 200
    assert created_session.status_code == 200
    assert submitted_turn.status_code == 200
    assert play_diagnostics.status_code == 200
    assert play_diagnostics.json()["content_prompt_profile"] == "role_conditioned"
    assert play_diagnostics.json()["summary"]["turn_count"] == 1
    assert play_diagnostics.json()["turn_traces"][0]["turn_elapsed_ms"] >= 0
    assert play_diagnostics.json()["turn_traces"][0]["session_cache_enabled"] is True
    assert play_diagnostics.json()["turn_traces"][0]["execution_frame"] == "public"
    assert "involved_npc_template_versions" in play_diagnostics.json()["turn_traces"][0]
    assert play_diagnostics.json()["summary"]["usage_totals"]["input_tokens"] >= 50
    assert "render_failure_reason_distribution" in play_diagnostics.json()["summary"]
    assert "interpret_failure_reason_distribution" in play_diagnostics.json()["summary"]
    assert "render_plan_primary_success_rate" in play_diagnostics.json()["summary"]
    assert "render_stage1_contract_failure_distribution" in play_diagnostics.json()["summary"]
    assert "render_repair_entry_rate" in play_diagnostics.json()["summary"]
    assert "render_primary_path_mode_distribution" in play_diagnostics.json()["summary"]
    assert "render_direct_primary_success_rate" in play_diagnostics.json()["summary"]
    assert "render_skill_id" in play_diagnostics.json()["turn_traces"][0]
    assert play_diagnostics.json()["turn_traces"][0]["render_primary_path_mode"] == "direct_narration"


def test_benchmark_play_diagnostics_exposes_involved_npc_template_versions(monkeypatch, tmp_path) -> None:
    original_library_service = main_module.story_library_service
    original_play_service = main_module.play_session_service

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENABLE_BENCHMARK_API", "1")
    fixture = author_fixture_bundle()
    cast = list(fixture.design_bundle.story_bible.cast)
    cast[1] = cast[1].model_copy(
        update={
            "roster_character_id": "roster_archive_vote_certifier",
            "template_version": "tpl-archive-v1",
        }
    )
    cast[2] = cast[2].model_copy(
        update={
            "roster_character_id": "roster_archive_mandate_broker",
            "template_version": "tpl-broker-v1",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "story_bible": fixture.design_bundle.story_bible.model_copy(
                update={"cast": cast}
            )
        }
    )
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    story = library_service.publish_story(
        owner_user_id="local-dev",
        source_job_id="benchmark-play-template-version",
        prompt_seed="seed",
        summary=build_author_story_summary(bundle, primary_theme="legitimacy_crisis"),
        preview=_preview_response(bundle=bundle),
        bundle=bundle,
        visibility="public",
    )
    play_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: _BenchmarkFakePlayClient(target_npc_ids=[cast[1].npc_id]),
    )
    main_module.story_library_service = library_service
    main_module.play_session_service = play_service

    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="bench-play-template@example.com", display_name="Bench Play Template")
        created_session = client.post("/play/sessions", json={"story_id": story.story_id})
        submitted_turn = client.post(
            f"/play/sessions/{created_session.json()['session_id']}/turns",
            json={"input_text": "I force the hearing to compare the seals in public.", "selected_suggestion_id": None},
        )
        diagnostics = client.get(f"/benchmark/play/sessions/{created_session.json()['session_id']}/diagnostics")
    finally:
        main_module.story_library_service = original_library_service
        main_module.play_session_service = original_play_service
        get_settings.cache_clear()

    assert created_session.status_code == 200
    assert submitted_turn.status_code == 200
    assert diagnostics.status_code == 200
    trace = diagnostics.json()["turn_traces"][0]
    assert trace["involved_npc_template_versions"] == {cast[1].npc_id: "tpl-archive-v1"}


def test_benchmark_author_diagnostics_remain_compatible_with_legacy_retrieval_trace() -> None:
    service = AuthorJobService(gateway_factory=lambda _settings=None: FakeGateway())
    fixture = author_fixture_bundle()
    record = _AuthorJobRecord(
        job_id="legacy-template-trace",
        owner_user_id="local-dev",
        prompt_seed="seed",
        preview=_preview_response(bundle=fixture.design_bundle),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="legitimacy_crisis"),
        bundle=fixture.design_bundle,
        roster_enabled=True,
        roster_catalog_version="legacy-v1",
        roster_retrieval_trace=[
            {
                "slot_index": 1,
                "slot_tag": "guardian",
                "query_language": "en",
                "story_query_text": "archive vote",
                "slot_query_text": "certifier",
                "candidate_pool_size": 1,
                "selected_character_id": "roster_archive_vote_certifier",
                "top_candidates": [{"character_id": "roster_archive_vote_certifier", "rank": 1, "score": 9.0, "score_breakdown": {}}],
                "selection_mode": "embedding+lexical",
                "fallback_reason": None,
                "assignment_rank": 1,
                "assignment_score": 9.0,
            }
        ],
    )
    service._save_record(record)
    diagnostics = service.get_job_diagnostics("legacy-template-trace")
    body = diagnostics.model_dump(mode="json")
    assert body["roster_retrieval_trace"][0]["selected_character_id"] == "roster_archive_vote_certifier"
    assert "selected_template_version" not in body["roster_retrieval_trace"][0]
