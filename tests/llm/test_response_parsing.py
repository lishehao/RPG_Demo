from __future__ import annotations

from rpg_backend.llm.response_parsing import parse_responses_payload


def test_parse_responses_payload_extracts_text_reasoning_and_usage() -> None:
    payload = {
        "id": "resp_123",
        "output": [
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "brief reasoning"}],
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "final narration line"}],
            },
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }

    parsed = parse_responses_payload(payload)

    assert parsed.response_id == "resp_123"
    assert parsed.output_text == "final narration line"
    assert parsed.reasoning_summary == "brief reasoning"
    assert parsed.usage.input_tokens == 10
    assert parsed.usage.output_tokens == 5
    assert parsed.usage.total_tokens == 15

