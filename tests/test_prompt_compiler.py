from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from rpg_backend.generator.prompt_compiler import PromptCompileError, PromptCompiler


def _settings_stub(*, max_retries: int = 3) -> SimpleNamespace:
    return SimpleNamespace(
        llm_openai_base_url="https://example.com/compatible-mode",
        llm_openai_api_key="test-key",
        llm_openai_model="test-model",
        llm_openai_route_model=None,
        llm_openai_narration_model=None,
        llm_openai_generator_model=None,
        llm_openai_timeout_seconds=5.0,
        llm_openai_generator_temperature=0.15,
        llm_openai_generator_max_retries=max_retries,
    )


def _spec_payload(*, premise: str) -> dict[str, object]:
    return {
        "title": "Signal Rift Protocol",
        "premise": premise,
        "tone": "tense and practical",
        "stakes": "Containment failure will cascade through the district grid.",
        "beats": [
            {
                "title": "Fault Ignition",
                "objective": "Find primary signal fault",
                "conflict": "Contradictory telemetry",
                "required_event": "b1.root_cause_locked",
            },
            {
                "title": "Checkpoint Friction",
                "objective": "Cross lockdown corridors",
                "conflict": "Security pressure",
                "required_event": "b2.lockdown_rerouted",
            },
            {
                "title": "Core Arbitration",
                "objective": "Resolve competing plans",
                "conflict": "Team split",
                "required_event": "b3.command_resolution",
            },
        ],
        "npcs": [
            {"name": "Mara", "role": "engineer", "motivation": "prevent collapse"},
            {"name": "Rook", "role": "security lead", "motivation": "protect civilians"},
            {"name": "Sera", "role": "analyst", "motivation": "preserve evidence"},
        ],
        "scene_constraints": [
            "Open with immediate operational damage.",
            "Escalate with conflicting directives.",
            "End with one irreversible tradeoff.",
        ],
        "move_bias": ["technical", "investigate"],
        "ending_shape": "pyrrhic",
    }


def _chat_payload(content: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}]}


def test_compile_succeeds_after_validation_feedback(monkeypatch) -> None:
    import rpg_backend.generator.prompt_compiler as prompt_module

    monkeypatch.setattr(prompt_module, "get_settings", lambda: _settings_stub(max_retries=3))

    invalid = _spec_payload(premise="x" * 401)
    valid = _spec_payload(premise="A compact premise that fits all schema limits.")
    queued = [invalid, valid]
    captured_prompts: list[dict[str, object]] = []

    def _fake_call(self, *, system_prompt: str, user_prompt: str):  # noqa: ANN001, ANN201
        del system_prompt
        captured_prompts.append(json.loads(user_prompt))
        return _chat_payload(json.dumps(queued.pop(0), ensure_ascii=False))

    monkeypatch.setattr(prompt_module.PromptCompiler, "_call_chat_completions", _fake_call)
    compiled = PromptCompiler().compile(
        prompt_text="Generate a concise emergency scenario",
        target_minutes=10,
        npc_count=4,
        style="neutral",
    )

    assert compiled.attempts == 2
    assert captured_prompts[0]["validation_feedback"] == []
    assert captured_prompts[0]["field_limits"]["premise"] == "<=400 chars"
    second_feedback = captured_prompts[1]["validation_feedback"]
    assert second_feedback
    assert any("premise" in item for item in second_feedback)


def test_compile_fails_after_three_invalid_attempts(monkeypatch) -> None:
    import rpg_backend.generator.prompt_compiler as prompt_module

    monkeypatch.setattr(prompt_module, "get_settings", lambda: _settings_stub(max_retries=3))
    invalid = _spec_payload(premise="y" * 450)
    calls = {"count": 0}
    captured_prompts: list[dict[str, object]] = []

    def _always_invalid(self, *, system_prompt: str, user_prompt: str):  # noqa: ANN001, ANN201
        del system_prompt
        calls["count"] += 1
        captured_prompts.append(json.loads(user_prompt))
        return _chat_payload(json.dumps(invalid, ensure_ascii=False))

    monkeypatch.setattr(prompt_module.PromptCompiler, "_call_chat_completions", _always_invalid)

    with pytest.raises(PromptCompileError) as exc_info:
        PromptCompiler().compile(
            prompt_text="Generate a concise emergency scenario",
            target_minutes=10,
            npc_count=4,
        )
    assert exc_info.value.error_code == "prompt_spec_invalid"
    assert calls["count"] == 3
    assert captured_prompts[-1]["validation_feedback"]


def test_compile_does_not_truncate_fields_locally(monkeypatch) -> None:
    import rpg_backend.generator.prompt_compiler as prompt_module

    monkeypatch.setattr(prompt_module, "get_settings", lambda: _settings_stub(max_retries=1))
    invalid = _spec_payload(premise="z" * 430)
    calls = {"count": 0}

    def _single_invalid(self, *, system_prompt: str, user_prompt: str):  # noqa: ANN001, ANN201
        del system_prompt, user_prompt
        calls["count"] += 1
        return _chat_payload(json.dumps(invalid, ensure_ascii=False))

    monkeypatch.setattr(prompt_module.PromptCompiler, "_call_chat_completions", _single_invalid)

    with pytest.raises(PromptCompileError) as exc_info:
        PromptCompiler().compile(
            prompt_text="Generate strict StorySpec without truncation",
            target_minutes=10,
            npc_count=4,
        )
    assert exc_info.value.error_code == "prompt_spec_invalid"
    assert calls["count"] == 1

