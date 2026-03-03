from __future__ import annotations

import json
import time
from typing import Any

import httpx

from rpg_backend.llm.base import LLMNarrationError, LLMProvider, LLMRouteError, RouteIntentResult
from rpg_backend.llm.openai_compat import (
    build_auth_headers,
    build_json_mode_body,
    extract_chat_content,
    normalize_chat_completions_url,
    parse_json_object,
)
from rpg_backend.llm.retry_policy import is_retriable_llm_error, retry_delay_seconds


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider using Chat Completions with JSON mode."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str | None = None,
        route_model: str | None = None,
        narration_model: str | None = None,
        timeout_seconds: float = 20.0,
        route_max_retries: int = 3,
        narration_max_retries: int = 1,
        route_temperature: float = 0.1,
        narration_temperature: float = 0.4,
    ) -> None:
        self.base_url = base_url.strip()
        self.api_key = api_key.strip()
        default_model = (model or "").strip()
        route = (route_model or "").strip()
        narration = (narration_model or "").strip()
        self.route_model = route or narration or default_model
        self.narration_model = narration or route or default_model
        self.timeout_seconds = timeout_seconds
        self.route_max_retries = max(1, min(route_max_retries, 3))
        self.narration_max_retries = max(1, min(narration_max_retries, 3))
        self.route_temperature = route_temperature
        self.narration_temperature = narration_temperature
        self.chat_completions_url = normalize_chat_completions_url(self.base_url)

    def _call_chat_completions(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> dict[str, Any]:
        body = build_json_mode_body(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
        headers = build_auth_headers(self.api_key)

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.chat_completions_url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    def route_intent(self, scene_context: dict[str, Any], text: str) -> RouteIntentResult:
        system_prompt = (
            "You route player text to a move. "
            "Return JSON only with keys: move_id (string), args (object), confidence (0..1), interpreted_intent (string). "
            "Prefer scene-specific moves over global moves. "
            "Use global.help_me_progress only when the user explicitly asks for help or says they are stuck."
        )
        user_prompt = json.dumps(
            {
                "task": "route_intent",
                "input_text": text or "",
                "fallback_move": scene_context.get("fallback_move"),
                "moves": scene_context.get("moves", []),
                "scene_seed": scene_context.get("scene_seed", ""),
                "route_policy": {
                    "prefer_scene_specific": True,
                    "allow_global_help": bool(scene_context.get("allow_global_help", False)),
                },
            },
            ensure_ascii=False,
        )
        last_error: Exception | None = None

        for attempt in range(1, self.route_max_retries + 1):
            try:
                raw_payload = self._call_chat_completions(
                    model=self.route_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self.route_temperature,
                )
                content = extract_chat_content(raw_payload)
                parsed = parse_json_object(content)
                routed = RouteIntentResult.model_validate(parsed)
                if not routed.move_id.strip():
                    raise ValueError("move_id is blank")
                if not routed.interpreted_intent.strip():
                    raise ValueError("interpreted_intent is blank")
                routed.move_id = routed.move_id.strip()
                return routed
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not is_retriable_llm_error(exc):
                    break
                if attempt < self.route_max_retries:
                    delay = retry_delay_seconds(attempt, exc)
                    if delay > 0:
                        time.sleep(delay)

        raise LLMRouteError("openai route_intent failed after retries") from last_error

    def render_narration(self, slots: dict[str, Any], style_guard: str) -> str:
        system_prompt = (
            "Write one concise narration paragraph from given slots. "
            "Return JSON only with key narration_text (string)."
        )
        user_prompt = json.dumps(
            {
                "task": "render_narration",
                "style_guard": style_guard,
                "slots": slots,
            },
            ensure_ascii=False,
        )
        last_error: Exception | None = None

        for attempt in range(1, self.narration_max_retries + 1):
            try:
                raw_payload = self._call_chat_completions(
                    model=self.narration_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self.narration_temperature,
                )
                content = extract_chat_content(raw_payload)
                parsed = parse_json_object(content)
                text = parsed.get("narration_text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("narration_text is blank")
                return text.strip()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not is_retriable_llm_error(exc):
                    break
                if attempt < self.narration_max_retries:
                    delay = retry_delay_seconds(attempt, exc)
                    if delay > 0:
                        time.sleep(delay)

        raise LLMNarrationError("openai render_narration failed after retries") from last_error
