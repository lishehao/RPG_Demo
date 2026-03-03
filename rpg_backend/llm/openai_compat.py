from __future__ import annotations

import json
from typing import Any


def normalize_chat_completions_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/responses"):
        return f"{normalized[:-len('/responses')]}/chat/completions"
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def extract_chat_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("chat completions payload missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("chat completions payload missing first choice object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("chat completions payload missing message")

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        fragments: list[str] = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                fragments.append(part["text"])
        joined = "".join(fragments).strip()
        if joined:
            return joined
    raise ValueError("chat completions payload missing message content")


def parse_json_object(content: str) -> dict[str, Any]:
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("response content is not a JSON object")
    return parsed


def build_json_mode_body(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }


def build_auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
