from __future__ import annotations

import json
import httpx
import pytest

import rpg_backend.eval.story_quality_judge as judge_module
from rpg_backend.eval.story_quality_judge import StoryQualityJudge, StoryQualityJudgeError


def _valid_payload() -> dict[str, object]:
    return {
        "overall_score": 8.2,
        "playability_score": 8.1,
        "coherence_score": 8.0,
        "tension_curve_score": 7.9,
        "choice_impact_score": 8.3,
        "prompt_fidelity_score": 8.4,
        "major_issues": ["midgame stakes spike is abrupt"],
        "strengths": ["clear objective ladder", "costly decisions remain playable"],
        "verdict": "pass",
    }


def test_judge_response_schema_valid() -> None:
    parsed = StoryQualityJudge.parse_result_payload(_valid_payload())
    assert parsed.overall_score == 8.2
    assert parsed.prompt_fidelity_score == 8.4
    assert parsed.verdict == "pass"


def test_judge_response_schema_invalid_raises() -> None:
    payload = _valid_payload()
    payload["verdict"] = "excellent"
    with pytest.raises(StoryQualityJudgeError) as exc_info:
        StoryQualityJudge.parse_result_payload(payload)
    assert exc_info.value.error_type == "judge_schema_invalid"


def test_judge_parser_handles_missing_fields() -> None:
    payload = _valid_payload()
    payload.pop("overall_score")
    with pytest.raises(StoryQualityJudgeError) as exc_info:
        StoryQualityJudge.parse_result_payload(payload)
    assert exc_info.value.error_type == "judge_schema_invalid"
    assert "overall_score" in str(exc_info.value)


def _new_judge_for_retry_tests(max_retries: int = 3) -> StoryQualityJudge:
    judge = StoryQualityJudge.__new__(StoryQualityJudge)
    judge.model = "judge-model"
    judge.max_retries = max_retries
    return judge


def test_judge_does_not_retry_on_401(monkeypatch) -> None:
    judge = _new_judge_for_retry_tests(max_retries=3)
    call_count = 0

    def _unauthorized(*, system_prompt: str, user_prompt: str) -> dict:  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        request = httpx.Request("POST", "https://example.com/v1/chat/completions")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    monkeypatch.setattr(judge, "_call_chat_completions", _unauthorized)

    with pytest.raises(StoryQualityJudgeError) as exc_info:
        judge.evaluate(
            prompt_text="prompt",
            expected_tone="tense",
            pack_summary={"scenes": 14},
            transcript_summary={"steps": 14},
            metrics={"completion_rate": 1.0},
        )

    assert exc_info.value.error_type == "judge_failed"
    assert call_count == 1


def test_judge_retries_on_503_then_succeeds(monkeypatch) -> None:
    judge = _new_judge_for_retry_tests(max_retries=3)
    call_count = 0

    monkeypatch.setattr(judge_module.time, "sleep", lambda _delay: None)

    def _flaky_then_ok(*, system_prompt: str, user_prompt: str) -> dict:  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            request = httpx.Request("POST", "https://example.com/v1/chat/completions")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("temporary failure", request=request, response=response)
        return {"choices": [{"message": {"content": json.dumps(_valid_payload())}}]}

    monkeypatch.setattr(judge, "_call_chat_completions", _flaky_then_ok)

    decision = judge.evaluate(
        prompt_text="prompt",
        expected_tone="tense",
        pack_summary={"scenes": 14},
        transcript_summary={"steps": 14},
        metrics={"completion_rate": 1.0},
    )

    assert decision.attempts == 3
    assert decision.result.verdict == "pass"
