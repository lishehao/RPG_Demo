from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

import rpg_backend.llm_gateway as llm_gateway_module
from rpg_backend.config import Settings
from rpg_backend.llm_gateway import (
    GatewayCapabilityError,
    GatewayTextRateLimitSnapshot,
    build_gateway_core,
    EmbeddingCapabilityRequest,
    TextCapabilityRequest,
    get_shared_text_rate_limiter_snapshot,
    reset_shared_text_rate_limiters_for_test,
)


class _FakeResponsesClient:
    def __init__(self, *, output_text: str = '{"ok": true}') -> None:
        self._output_text = output_text
        self.responses = SimpleNamespace(create=self._create_response)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create_chat_completion))
        self.embeddings = SimpleNamespace(create=self._create_embedding)

    def _create_response(self, **_kwargs):
        return SimpleNamespace(
            output_text=self._output_text,
            id="resp-1",
            usage={"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
        )

    def _create_chat_completion(self, **_kwargs):
        return SimpleNamespace(
            id="chat-1",
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
            usage={"input_tokens": 9, "output_tokens": 3, "total_tokens": 12},
        )

    def _create_embedding(self, **_kwargs):
        return SimpleNamespace(
            id="emb-1",
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
            usage={"input_tokens": 6, "total_tokens": 6},
        )


class _FailingChatClient(_FakeResponsesClient):
    def _create_chat_completion(self, **_kwargs):
        raise TimeoutError("Request timed out.")


def test_settings_gateway_resolution_uses_new_canonical_fields_only(monkeypatch) -> None:
    canonical = Settings(
        _env_file=None,
        gateway_base_url="https://canonical.example/v1",
        gateway_responses_base_url="https://canonical-responses.example/v1",
        gateway_api_key="canonical-key",
        gateway_model="canonical-text-model",
        gateway_embedding_base_url="https://canonical-embedding.example/v1",
        gateway_embedding_api_key="canonical-embedding-key",
        gateway_embedding_model="canonical-embedding-model",
        gateway_timeout_seconds=33,
        gateway_timeout_seconds_author=120,
        gateway_timeout_seconds_author_cast_generation=40,
        gateway_timeout_seconds_author_story_frame=45,
        gateway_use_session_cache=True,
        gateway_session_cache_header="X-Gateway-Cache",
        gateway_session_cache_value="enabled",
    )

    assert canonical.resolved_gateway_base_url(transport_style="chat_completions") == "https://canonical.example/v1"
    assert canonical.resolved_gateway_base_url(transport_style="responses") == "https://canonical-responses.example/v1"
    assert canonical.resolved_gateway_api_key() == "canonical-key"
    assert canonical.resolved_gateway_model() == "canonical-text-model"
    assert canonical.resolved_gateway_embedding_base_url() == "https://canonical-embedding.example/v1"
    assert canonical.resolved_gateway_embedding_api_key() == "canonical-embedding-key"
    assert canonical.resolved_gateway_embedding_model() == "canonical-embedding-model"
    assert canonical.resolved_gateway_timeout_seconds() == 33.0
    assert canonical.resolved_gateway_timeout_seconds_for_text_capability("author.spark_seed_generate") == 8.0
    assert canonical.resolved_gateway_timeout_seconds_for_text_capability("author.cast_member_generate") == 40.0
    assert canonical.resolved_gateway_timeout_seconds_for_text_capability("author.cast_member_repair") == 40.0
    assert canonical.resolved_gateway_timeout_seconds_for_text_capability("author.character_instance_variation") == 40.0
    assert canonical.resolved_gateway_timeout_seconds_for_text_capability("author.story_frame_scaffold") == 45.0
    assert canonical.resolved_gateway_timeout_seconds_for_text_capability("author.story_frame_finalize") == 45.0
    assert canonical.resolved_gateway_timeout_seconds_for_text_capability("author.beat_plan_generate") == 120.0
    assert canonical.resolved_gateway_timeout_seconds_for_text_capability("play.render") == 33.0
    assert canonical.resolved_gateway_use_session_cache() is True
    assert canonical.resolved_gateway_use_session_cache(transport_style="chat_completions") is False
    assert canonical.resolved_gateway_session_cache_header() == "X-Gateway-Cache"
    assert canonical.resolved_gateway_session_cache_value() == "enabled"

    monkeypatch.setenv("APP_LLM_BASE_URL", "https://legacy.example/v1")
    monkeypatch.setenv("APP_LLM_API_KEY", "legacy-key")
    monkeypatch.setenv("APP_LLM_MODEL", "legacy-text-model")
    monkeypatch.setenv("APP_RESPONSES_BASE_URL", "https://legacy-responses.example/v1")
    monkeypatch.setenv("APP_RESPONSES_API_KEY", "legacy-responses-key")
    monkeypatch.setenv("APP_RESPONSES_MODEL", "legacy-responses-model")
    monkeypatch.setenv("APP_ROSTER_EMBEDDING_API_BASE", "https://legacy-embedding.example/v1")
    monkeypatch.setenv("APP_ROSTER_EMBEDDING_API_KEY", "legacy-embedding-key")
    monkeypatch.setenv("APP_ROSTER_EMBEDDING_MODEL", "legacy-embedding-model")
    legacy = Settings(_env_file=None)

    assert legacy.resolved_gateway_base_url(transport_style="chat_completions") == ""
    assert legacy.resolved_gateway_base_url(transport_style="responses") == ""
    assert legacy.resolved_gateway_api_key() == ""
    assert legacy.resolved_gateway_model() == ""
    assert legacy.resolved_gateway_embedding_base_url() == ""
    assert legacy.resolved_gateway_embedding_api_key() == ""
    assert legacy.resolved_gateway_embedding_model() == ""



def test_gateway_core_invokes_responses_capability_and_records_trace(monkeypatch) -> None:
    reset_shared_text_rate_limiters_for_test()
    captured: dict[str, object] = {}

    def _fake_client(**kwargs):
        captured.update(kwargs)
        return _FakeResponsesClient()

    monkeypatch.setattr(llm_gateway_module, "build_openai_client", _fake_client)
    settings = Settings(
        _env_file=None,
        gateway_base_url="https://example.com/v1",
        gateway_responses_base_url="https://responses.example.com/v1",
        gateway_api_key="test-key",
        gateway_model="gateway-text-model",
    )
    core = build_gateway_core(settings, transport_style="responses")

    result = core.invoke_text_capability(
        "play.render",
        TextCapabilityRequest(
            system_prompt="render",
            user_payload={"turn": 1},
            operation_name="play_render_turn",
            skill_id="play.render.plan",
            skill_version="v1",
            contract_mode="strict_json_schema",
            context_card_ids=["beat_card", "resolution_card"],
            context_packet_characters=256,
            repair_mode="none",
        ),
    )

    assert result.capability == "play.render"
    assert result.provider == "openai_compatible"
    assert result.transport_style == "responses"
    assert result.model == "gateway-text-model"
    assert captured["base_url"] == "https://responses.example.com/v1"
    assert core.call_trace[0]["capability"] == "play.render"
    assert core.call_trace[0]["provider"] == "openai_compatible"
    assert core.call_trace[0]["operation_name"] == "play_render_turn"
    assert core.call_trace[0]["timeout_seconds"] == 20.0
    assert core.call_trace[0]["sdk_max_retries"] == 0
    assert core.call_trace[0]["sdk_retries_disabled"] is True
    assert "gateway_queue_wait_ms" in core.call_trace[0]
    assert "gateway_rate_limit_applied" in core.call_trace[0]
    assert "gateway_rate_limit_window_10s_count" in core.call_trace[0]
    assert "gateway_rate_limit_window_20s_count" in core.call_trace[0]
    assert "gateway_rate_limit_window_60s_count" in core.call_trace[0]
    assert core.call_trace[0]["skill_id"] == "play.render.plan"
    assert core.call_trace[0]["skill_version"] == "v1"
    assert core.call_trace[0]["contract_mode"] == "strict_json_schema"
    assert core.call_trace[0]["context_card_ids"] == ["beat_card", "resolution_card"]
    assert core.call_trace[0]["context_packet_characters"] == 256
    assert core.call_trace[0]["repair_mode"] == "none"


def test_gateway_core_supports_plaintext_salvage_for_text_capabilities(monkeypatch) -> None:
    reset_shared_text_rate_limiters_for_test()
    monkeypatch.setattr(
        llm_gateway_module,
        "build_openai_client",
        lambda **_kwargs: _FakeResponsesClient(output_text="Plain text render body."),
    )
    settings = Settings(
        gateway_base_url="https://example.com/v1",
        gateway_api_key="test-key",
        gateway_model="gateway-text-model",
    )
    core = build_gateway_core(settings, transport_style="responses")

    result = core.invoke_text_capability(
        "play.render",
        TextCapabilityRequest(
            system_prompt="render",
            user_payload={"turn": 1},
            operation_name="play_render_turn",
            plaintext_fallback_key="narration",
        ),
    )

    assert result.payload == {"narration": "Plain text render body."}
    assert result.fallback_source == "plaintext_salvage"
    assert result.raw_text == "Plain text render body."
    assert core.call_trace[0]["fallback_source"] == "plaintext_salvage"


def test_gateway_core_can_passthrough_raw_text_when_json_is_invalid(monkeypatch) -> None:
    reset_shared_text_rate_limiters_for_test()
    monkeypatch.setattr(
        llm_gateway_module,
        "build_openai_client",
        lambda **_kwargs: _FakeResponsesClient(output_text="Here is the JSON requested: affordance_tag: reveal_truth"),
    )
    settings = Settings(
        gateway_base_url="https://example.com/v1",
        gateway_api_key="test-key",
        gateway_model="gateway-text-model",
    )
    core = build_gateway_core(settings, transport_style="responses")

    result = core.invoke_text_capability(
        "play.interpret",
        TextCapabilityRequest(
            system_prompt="interpret",
            user_payload={"turn": 1},
            operation_name="play_interpret_turn",
            allow_raw_text_passthrough=True,
        ),
    )

    assert result.payload == {}
    assert result.fallback_source == "raw_text_passthrough"
    assert "affordance_tag" in str(result.raw_text)
    assert core.call_trace[0]["fallback_source"] == "raw_text_passthrough"


def test_gateway_core_invokes_chat_completions_capability(monkeypatch) -> None:
    reset_shared_text_rate_limiters_for_test()
    monkeypatch.setattr(llm_gateway_module, "build_openai_client", lambda **_kwargs: _FakeResponsesClient())
    settings = Settings(
        gateway_base_url="https://example.com/v1",
        gateway_api_key="test-key",
        gateway_model="gateway-text-model",
    )
    core = build_gateway_core(settings, transport_style="chat_completions")

    result = core.invoke_text_capability(
        "copilot.reply",
        TextCapabilityRequest(
            system_prompt="reply",
            user_payload={"message": "help"},
            operation_name="copilot_session_reply",
        ),
    )

    assert result.capability == "copilot.reply"
    assert result.transport_style == "chat_completions"
    assert core.call_trace[0]["transport_style"] == "chat_completions"


def test_gateway_core_records_failed_text_trace_with_author_timeout_override(monkeypatch) -> None:
    reset_shared_text_rate_limiters_for_test()
    monkeypatch.setattr(llm_gateway_module, "build_openai_client", lambda **_kwargs: _FailingChatClient())
    settings = Settings(
        gateway_base_url="https://example.com/v1",
        gateway_api_key="test-key",
        gateway_model="gateway-text-model",
        gateway_timeout_seconds=20,
        gateway_timeout_seconds_author=120,
        gateway_timeout_seconds_author_story_frame=45,
    )
    core = build_gateway_core(settings, transport_style="chat_completions")

    with pytest.raises(GatewayCapabilityError) as exc_info:
        core.invoke_text_capability(
            "author.story_frame_scaffold",
            TextCapabilityRequest(
                system_prompt="story frame",
                user_payload={"seed": "blackout"},
                operation_name="story_frame_semantics",
            ),
        )

    assert exc_info.value.code == "gateway_text_provider_failed"
    assert core.call_trace[0]["capability"] == "author.story_frame_scaffold"
    assert core.call_trace[0]["operation_name"] == "story_frame_semantics"
    assert core.call_trace[0]["timeout_seconds"] == 45.0
    assert core.call_trace[0]["error_code"] == "gateway_text_provider_failed"
    assert "Request timed out." in str(core.call_trace[0]["error_message"])


def test_gateway_core_invokes_embedding_capability_and_records_trace(monkeypatch) -> None:
    reset_shared_text_rate_limiters_for_test()
    monkeypatch.setattr(llm_gateway_module, "build_openai_client", lambda **_kwargs: _FakeResponsesClient())
    settings = Settings(
        gateway_base_url="https://example.com/v1",
        gateway_api_key="test-key",
        gateway_embedding_base_url="https://embedding.example/v1",
        gateway_embedding_api_key="embedding-key",
        gateway_embedding_model="gateway-embedding-model",
    )
    core = build_gateway_core(settings)

    result = core.invoke_embedding_capability(
        "embedding.roster_query",
        EmbeddingCapabilityRequest(
            text="harbor quarantine manifest panic",
            operation_name="embedding.roster_query",
        ),
    )

    assert result.capability == "embedding.roster_query"
    assert result.provider == "openai_compatible"
    assert result.value == [0.1, 0.2, 0.3]
    assert core.call_trace[0]["capability"] == "embedding.roster_query"
    assert core.call_trace[0]["transport_style"] == "embeddings"


def test_gateway_core_returns_capability_policy_defaults() -> None:
    settings = Settings(
        gateway_base_url="https://example.com/v1",
        gateway_api_key="test-key",
        gateway_model="gateway-text-model",
    )
    core = build_gateway_core(settings)

    render_policy = core.text_policy("play.render")
    rewrite_policy = core.text_policy("copilot.rewrite_plan")

    assert render_policy.max_output_tokens == settings.responses_max_output_tokens_play_render
    assert render_policy.enable_thinking is settings.responses_enable_thinking_play
    assert rewrite_policy.max_output_tokens == settings.responses_max_output_tokens_author_rulepack


def test_gateway_core_rate_limit_window_helpers_shape_burst_without_spending_minute_budget() -> None:
    limiter = llm_gateway_module.ShapedTextRateLimiter(
        enabled=True,
        windows=(
            llm_gateway_module._RateLimitWindow(label="10s", seconds=10.0, cap=2),
            llm_gateway_module._RateLimitWindow(label="20s", seconds=20.0, cap=3),
            llm_gateway_module._RateLimitWindow(label="60s", seconds=60.0, cap=5),
        ),
        clock=lambda: 100.0,
    )
    limiter._timestamps.extend([45.0, 50.0, 85.0, 98.1, 98.2])

    delay_seconds, counts = limiter._admission_delay(100.0)

    assert counts == {"10s": 2, "20s": 3, "60s": 5}
    assert round(delay_seconds, 1) == 8.1


def test_shared_text_rate_limiter_tracks_wait_and_preserves_fifo_under_threads() -> None:
    reset_shared_text_rate_limiters_for_test()
    limiter = llm_gateway_module.ShapedTextRateLimiter(
        enabled=True,
        windows=(
            llm_gateway_module._RateLimitWindow(label="10s", seconds=0.05, cap=2),
            llm_gateway_module._RateLimitWindow(label="20s", seconds=0.10, cap=3),
            llm_gateway_module._RateLimitWindow(label="60s", seconds=0.20, cap=4),
        ),
    )
    barrier = threading.Barrier(4)
    wait_ms_results: list[int] = []

    def _worker() -> None:
        barrier.wait()
        decision = limiter.acquire()
        wait_ms_results.append(decision.wait_ms)

    threads = [threading.Thread(target=_worker) for _ in range(4)]
    started_at = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - started_at
    snapshot = limiter.snapshot()

    assert len(wait_ms_results) == 4
    assert any(wait > 0 for wait in wait_ms_results)
    assert snapshot.total_admitted == 4
    assert snapshot.max_wait_ms >= max(wait_ms_results)
    assert snapshot.current_queue_depth == 0
    assert elapsed >= 0.05


def test_embedding_capability_does_not_consume_text_rate_limiter_budget(monkeypatch) -> None:
    reset_shared_text_rate_limiters_for_test()
    monkeypatch.setattr(llm_gateway_module, "build_openai_client", lambda **_kwargs: _FakeResponsesClient())
    settings = Settings(
        gateway_base_url="https://example.com/v1",
        gateway_api_key="test-key",
        gateway_model="gateway-text-model",
        gateway_embedding_base_url="https://embedding.example/v1",
        gateway_embedding_api_key="embedding-key",
        gateway_embedding_model="gateway-embedding-model",
        gateway_text_rate_limit_enabled=True,
        gateway_text_rate_limit_per_minute=2,
        gateway_text_rate_limit_10s_cap=1,
        gateway_text_rate_limit_20s_cap=2,
    )
    core = build_gateway_core(settings)

    before = get_shared_text_rate_limiter_snapshot(settings)
    core.invoke_embedding_capability(
        "embedding.roster_query",
        EmbeddingCapabilityRequest(text="harbor", operation_name="embedding.roster_query"),
    )
    after = get_shared_text_rate_limiter_snapshot(settings)

    assert isinstance(before, GatewayTextRateLimitSnapshot)
    assert before.total_admitted == after.total_admitted


def test_gateway_core_can_choose_transport_per_callsite_with_same_model(monkeypatch) -> None:
    reset_shared_text_rate_limiters_for_test()
    monkeypatch.setattr(llm_gateway_module, "build_openai_client", lambda **_kwargs: _FakeResponsesClient())
    settings = Settings(
        gateway_base_url="https://example.com/v1",
        gateway_api_key="test-key",
        gateway_model="gateway-text-model",
    )
    responses_core = build_gateway_core(settings, transport_style="responses")
    chat_core = build_gateway_core(settings, transport_style="chat_completions")

    responses_result = responses_core.invoke_text_capability(
        "play.render",
        TextCapabilityRequest(system_prompt="render", user_payload={"turn": 1}),
    )
    chat_result = chat_core.invoke_text_capability(
        "play.render",
        TextCapabilityRequest(system_prompt="render", user_payload={"turn": 1}),
    )

    assert responses_result.transport_style == "responses"
    assert chat_result.transport_style == "chat_completions"


def test_play_capabilities_can_override_text_model(monkeypatch) -> None:
    monkeypatch.setattr(llm_gateway_module, "build_openai_client", lambda **_kwargs: _FakeResponsesClient())
    settings = Settings(
        _env_file=None,
        gateway_base_url="https://example.com/v1",
        gateway_api_key="test-key",
        gateway_model="gateway-text-model",
        gateway_play_model="qwen3.5-plus",
    )
    core = build_gateway_core(settings, transport_style="responses")

    play_policy = core.text_policy("play.render")
    author_policy = core.text_policy("author.story_frame_scaffold")

    assert play_policy.model == "qwen3.5-plus"
    assert author_policy.model == "gateway-text-model"
