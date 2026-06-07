from __future__ import annotations

import json
from types import SimpleNamespace

from rpg_backend.config import Settings
from rpg_backend.narrative.contracts import StoryBriefAdvisorRequest, StoryGuideTurnRequest
from rpg_backend.narrative.gateway import NarrativeLLMGateway, get_narrative_gateway
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService
from rpg_backend.responses_transport import ResponsesJSONTransport, build_chat_completions_client, usage_to_dict

ROOT_FILES = (
    "frontend2/src/pages/create/create-page.tsx",
    "frontend2/src/api/route-map.ts",
)


class _FakeResponses:
    def __init__(self, output_text: str, usage: dict | None = None) -> None:
        self.output_text = output_text
        self.usage = usage
        self.calls: list[dict] = []

    def create(self, **kwargs):  # noqa: ANN001, ANN201
        self.calls.append(kwargs)
        return SimpleNamespace(id="resp_fake_123", output_text=self.output_text, usage=self.usage)


class _FakeClient:
    def __init__(self, responses: _FakeResponses) -> None:
        self.responses = responses


def _transport(output: dict | str, usage: dict | None = None) -> ResponsesJSONTransport:
    output_text = output if isinstance(output, str) else json.dumps(output)
    return ResponsesJSONTransport(
        client=_FakeClient(_FakeResponses(output_text, usage)),
        model="deepseek-test",
        timeout_seconds=5,
        use_session_cache=True,
        temperature=0.2,
        enable_thinking=False,
        explicit_disable_thinking=True,
        json_object_prompt_only=True,
        provider_failed_code="llm_provider_failed",
        invalid_response_code="llm_invalid_response",
        invalid_json_code="llm_invalid_json",
        error_factory=lambda code, message, status_code: RuntimeError(f"{code}:{status_code}:{message}"),
    )


def test_unified_text_gateway_uses_generic_responses_config_for_narrative_path() -> None:
    settings = Settings(
        responses_base_url="https://api.deepseek.com",
        responses_api_key="redacted-test-key",
        responses_model="deepseek-test",
    )
    gateway = get_narrative_gateway(settings)

    assert gateway is not None
    assert gateway.model == "deepseek-test"


def test_explicit_single_responses_keys_precede_stale_key_pools() -> None:
    settings = Settings(
        responses_api_key="generic-current",
        responses_api_keys="generic-stale,generic-current",
        responses_play_api_key="play-current",
        responses_play_api_keys="play-stale,play-current",
        responses_author_api_key="author-current",
        responses_author_api_keys="author-stale,author-current",
    )

    assert settings.responses_api_key_pool() == ("generic-current", "generic-stale")
    assert settings.play_responses_api_key_pool()[:3] == (
        "play-current",
        "play-stale",
        "generic-current",
    )
    assert settings.author_responses_api_key_pool()[:3] == (
        "author-current",
        "author-stale",
        "generic-current",
    )


def test_chat_transport_keeps_primary_key_sticky_when_pool_has_stale_keys() -> None:
    client = build_chat_completions_client(
        base_url="https://api.deepseek.com",
        api_key="primary-current",
        api_keys=("primary-current", "stale-old"),
        use_session_cache=False,
        session_cache_header="x-cache",
        session_cache_value="enable",
    )
    completions = client.chat.completions

    assert completions._next_api_key() == "primary-current"  # noqa: SLF001
    assert completions._next_api_key() == "primary-current"  # noqa: SLF001


def test_usage_parser_extracts_input_output_total_and_cache_tokens() -> None:
    usage = usage_to_dict(
        {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "prompt_tokens_details": {"cached_tokens": 5},
        }
    )

    assert usage["input_tokens"] == 11
    assert usage["output_tokens"] == 7
    assert usage["total_tokens"] == 18
    assert usage["cached_input_tokens"] == 5


def test_transport_records_latency_usage_and_repaired_status() -> None:
    transport = _transport(
        '{"reply":"The room is taking shape. Who can push back?",}',
        usage={"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
    )

    response = transport.invoke_json(
        system_prompt="Return JSON.",
        user_payload={"message": "Gala goes wrong"},
        operation_name="create.story_butler_turn",
        max_output_tokens=120,
    )

    assert response.payload["reply"].startswith("The room")
    assert transport.call_trace
    trace = transport.call_trace[-1]
    assert trace["operation"] == "create.story_butler_turn"
    assert trace["status"] == "repaired"
    assert trace["repair_count"] == 1
    assert trace["latency_ms"] >= 0
    assert trace["usage"]["input_tokens"] == 12
    assert trace["usage"]["output_tokens"] == 8
    assert trace["usage"]["total_tokens"] == 20


def test_transport_records_missing_usage_as_empty_trace_usage() -> None:
    transport = _transport({"reply": "Who else is in the room?"}, usage=None)

    transport.invoke_json(
        system_prompt="Return JSON.",
        user_payload={"message": "Gala goes wrong"},
        operation_name="create.story_butler_turn",
        max_output_tokens=120,
    )

    assert transport.call_trace[-1]["status"] == "success"
    assert transport.call_trace[-1]["usage"] == {}


def test_story_butler_turn_uses_live_gateway_and_persists_safe_telemetry(tmp_path) -> None:
    transport = _transport(
        {"reply": "The gala has pressure, but I need the person who can push back in the first room."},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48, "cached_input_tokens": 10},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong before a livestream with a publicist and producer.", language="en"),
        owner_user_id="user_live",
    )
    events = service._repo.list_recent_llm_call_events_for_user("user_live")  # noqa: SLF001

    assert response.source == "live"
    assert response.reply.startswith("The gala has pressure")
    assert events
    assert events[0].operation == "create.story_butler_turn"
    assert events[0].status == "success"
    assert events[0].input_tokens == 30
    assert events[0].cached_input_tokens == 10
    assert events[0].output_tokens == 18
    assert events[0].total_tokens == 48
    serialized = events[0].model_dump_json()
    assert "redacted-test-key" not in serialized


def test_story_butler_turn_unwraps_stringified_reply_json(tmp_path) -> None:
    transport = _transport(
        {"reply": '{"reply":"A gala gone wrong already crackles. Who are you in the scene?"}'},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong.", language="en"),
        owner_user_id="user_live",
    )

    assert response.source == "live"
    assert response.reply == "A gala gone wrong already crackles. Who are you in the scene?"
    assert '{"reply"' not in response.reply
    assert "}" not in response.reply


def test_story_butler_turn_accepts_natural_text_plaintext_fallback(tmp_path) -> None:
    transport = _transport(
        "A gala gone wrong is a clean spark. Who can lose something public in this room?",
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong.", language="en"),
        owner_user_id="user_live",
    )

    assert response.source == "live"
    assert response.reply.startswith("A gala gone wrong is a clean spark")
    assert '{"reply"' not in response.reply


def test_story_butler_turn_recovers_malformed_reply_wrapper(tmp_path) -> None:
    transport = _transport(
        {"reply": '{"reply":"The publicist is in the room. What pressure hits first?",}'},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong.", language="en"),
        owner_user_id="user_live",
    )

    assert response.source == "live"
    assert response.reply == "The publicist is in the room. What pressure hits first?"
    assert '{"reply"' not in response.reply
    assert response.ledger is not None


def test_story_butler_turn_falls_back_without_gateway_and_records_no_gateway_event(tmp_path) -> None:
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=None,
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong before a livestream with a publicist and producer.", language="en"),
        owner_user_id="user_fallback",
    )
    events = service._repo.list_recent_llm_call_events_for_user("user_fallback")  # noqa: SLF001

    assert response.source == "no_gateway_fallback"
    assert events[0].operation == "create.story_butler_turn"
    assert events[0].source_label == "no_gateway_fallback"
    assert events[0].status == "fallback_used"


def test_story_brief_uses_live_hybrid_copy_without_changing_generation_gate(tmp_path) -> None:
    transport = _transport(
        {
            "premise_summary": "A publicist must decide what to reveal before the awards livestream collapses.",
            "genre_tone": "High-drama backstage pressure with public fallout.",
            "story_kernel": "Protect the witness, manage the producer, and keep the room playable under deadline.",
            "adaptation_note": "Live editor tightened copy while preserving the safety-checked plan.",
            "next_step": "Build the first scene from this Brief.",
        },
        usage={"input_tokens": 80, "output_tokens": 42, "total_tokens": 122},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_brief(
        StoryBriefAdvisorRequest(
            seed=(
                "Ten minutes before an awards livestream, an anxious publicist, a producer, "
                "a backup dancer, and a sponsor representative discover that a famous singer has disappeared."
            ),
            language="en",
            desired_tension_profile="high_drama",
        ),
        owner_user_id="user_brief",
    )
    events = service._repo.list_recent_llm_call_events_for_user("user_brief")  # noqa: SLF001

    assert response.source == "live_hybrid_v1"
    assert response.runtime_source == "live"
    assert response.brief.source == "live_hybrid_v1"
    assert response.can_generate is True
    assert "awards livestream" in response.brief.premise_summary
    assert events[0].operation == "narrative.story_brief"
    assert events[0].total_tokens == 122


def test_create_page_calls_backend_story_guide_turn_and_shows_thinking_row() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    create_page = (root / "frontend2/src/pages/create/create-page.tsx").read_text()
    route_map = (root / "frontend2/src/api/route-map.ts").read_text()

    assert "createNarrativeStoryGuideTurn" in create_page
    assert 'data-guide-node="story_butler_turn"' in create_page
    assert "guideBusy" in create_page
    assert "normalizeGuideReplyText(response.reply)" in create_page
    assert '"reply"\\s*:' in create_page
    assert "/narrative/story-guide/turns" in route_map
