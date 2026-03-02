from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import ValidationError

from app.config.settings import get_settings
from app.generator.spec_schema import StorySpec
from app.generator.versioning import compute_payload_hash
from app.llm.factory import resolve_openai_models


@dataclass
class PromptCompileResult:
    spec: StorySpec
    spec_hash: str
    model: str
    attempts: int
    notes: list[str] = field(default_factory=list)


class PromptCompileError(RuntimeError):
    def __init__(self, *, error_code: str, errors: list[str], notes: list[str] | None = None):
        super().__init__("prompt compile failed")
        self.error_code = error_code
        self.errors = errors
        self.notes = notes or []


class PromptCompiler:
    _FIELD_LIMITS: dict[str, str] = {
        "title": "<=120 chars",
        "premise": "<=400 chars",
        "tone": "<=120 chars",
        "stakes": "<=300 chars",
        "beats": "3..5 items",
        "npcs": "3..5 items",
        "scene_constraints": "3..5 items",
        "move_bias": "1..6 items",
    }

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = (settings.llm_openai_base_url or "").strip()
        self.api_key = (settings.llm_openai_api_key or "").strip()
        self.model = self._resolve_model(settings)
        self.timeout_seconds = settings.llm_openai_timeout_seconds
        self.temperature = settings.llm_openai_generator_temperature
        self.max_retries = max(1, min(settings.llm_openai_generator_max_retries, 3))
        self.chat_completions_url = self._normalize_chat_completions_url(self.base_url)

    @staticmethod
    def _resolve_model(settings) -> str:
        explicit = (settings.llm_openai_generator_model or "").strip()
        if explicit:
            return explicit
        route_model, _ = resolve_openai_models(
            settings.llm_openai_route_model,
            settings.llm_openai_narration_model,
            settings.llm_openai_model,
        )
        return route_model

    @staticmethod
    def _normalize_chat_completions_url(base_url: str) -> str:
        normalized = (base_url or "").strip().rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        if normalized.endswith("/responses"):
            return f"{normalized[:-len('/responses')]}/chat/completions"
        if normalized.endswith("/v1"):
            return f"{normalized}/chat/completions"
        return f"{normalized}/v1/chat/completions"

    @staticmethod
    def _extract_chat_content(payload: dict[str, Any]) -> str:
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

    @staticmethod
    def _is_retriable(exc: Exception) -> bool:
        if isinstance(exc, (json.JSONDecodeError, ValidationError, ValueError)):
            return True
        if isinstance(
            exc,
            (
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
                httpx.RemoteProtocolError,
            ),
        ):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
        return False

    @staticmethod
    def _retry_delay_seconds(attempt: int, exc: Exception) -> float:
        if isinstance(exc, (json.JSONDecodeError, ValidationError, ValueError)):
            return 0.0
        schedule = (0.25, 0.8, 1.5)
        index = min(max(attempt - 1, 0), len(schedule) - 1)
        return schedule[index]

    @staticmethod
    def _build_validation_feedback(exc: ValidationError) -> list[str]:
        feedback: list[str] = []
        for issue in exc.errors():
            path = ".".join(str(part) for part in issue.get("loc", ())) or "<root>"
            error_type = str(issue.get("type", "validation_error"))
            message = str(issue.get("msg", "invalid value"))
            ctx = issue.get("ctx") or {}
            constraints: list[str] = []
            if isinstance(ctx, dict):
                for key in ("max_length", "min_length", "max_items", "min_items", "ge", "gt", "le", "lt"):
                    if key in ctx:
                        constraints.append(f"{key}={ctx[key]}")
            constraint_text = f" ({', '.join(constraints)})" if constraints else ""
            feedback.append(f"{path}: {error_type}{constraint_text} - {message}")
        return feedback or ["schema validation failed: unknown constraint violation"]

    def _call_chat_completions(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.chat_completions_url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    def compile(
        self,
        *,
        prompt_text: str,
        target_minutes: int,
        npc_count: int,
        style: str | None = None,
        attempt_index: int = 0,
        attempt_seed: str | None = None,
    ) -> PromptCompileResult:
        prompt_value = (prompt_text or "").strip()
        if not prompt_value:
            raise PromptCompileError(
                error_code="prompt_compile_failed",
                errors=["prompt_text must not be blank"],
                notes=["prompt compiler input validation failed"],
            )
        if not self.base_url or not self.api_key or not self.model:
            raise PromptCompileError(
                error_code="prompt_compile_failed",
                errors=["openai generator config missing base_url/api_key/model"],
                notes=["check APP_LLM_OPENAI_BASE_URL, APP_LLM_OPENAI_API_KEY, and generator model settings"],
            )

        schema = StorySpec.model_json_schema()
        system_prompt = (
            "You are a story architect for an interactive narrative game runtime. "
            "Return JSON only and strictly satisfy every field limit before output. "
            "Field limits: title<=120 chars, premise<=400 chars, tone<=120 chars, stakes<=300 chars, "
            "beats=3..5 items, npcs=3..5 items, scene_constraints=3..5 items, move_bias=1..6 items. "
            "Self-check lengths and counts before returning. Any value outside limits is invalid."
        )
        request_payload: dict[str, Any] = {
            "task": "compile_story_prompt",
            "prompt_text": prompt_value,
            "target_minutes": target_minutes,
            "npc_count": npc_count,
            "style": style or "",
            "attempt_index": attempt_index,
            "attempt_seed": attempt_seed or "",
            "required_move_bias_tags": [
                "social",
                "stealth",
                "technical",
                "investigate",
                "support",
                "resource",
                "conflict",
                "mobility",
            ],
            "required_ending_shapes": ["triumph", "pyrrhic", "uncertain", "sacrifice"],
            "field_limits": dict(self._FIELD_LIMITS),
            "output_schema": schema,
        }

        last_error: Exception | None = None
        validation_feedback: list[str] = []
        for attempt in range(1, self.max_retries + 1):
            per_attempt_payload = dict(request_payload)
            per_attempt_payload["compile_attempt"] = attempt
            per_attempt_payload["validation_feedback"] = list(validation_feedback)
            if validation_feedback:
                per_attempt_payload["retry_instruction"] = (
                    "Previous output failed validation. Regenerate the full JSON and fix all listed violations."
                )
            user_prompt = json.dumps(per_attempt_payload, ensure_ascii=False)
            try:
                payload = self._call_chat_completions(system_prompt=system_prompt, user_prompt=user_prompt)
                content = self._extract_chat_content(payload)
                parsed = json.loads(content)
                spec = StorySpec.model_validate(parsed)
                spec_hash = compute_payload_hash(spec.model_dump())
                return PromptCompileResult(
                    spec=spec,
                    spec_hash=spec_hash,
                    model=self.model,
                    attempts=attempt,
                    notes=[
                        f"prompt_compiler_model={self.model}",
                        f"prompt_compiler_attempts={attempt}",
                        f"prompt_compile_attempt_index={attempt_index}",
                        f"prompt_compile_attempt_seed={attempt_seed or ''}",
                    ],
                )
            except ValidationError as exc:
                last_error = exc
                validation_feedback = self._build_validation_feedback(exc)
                if attempt >= self.max_retries:
                    raise PromptCompileError(
                        error_code="prompt_spec_invalid",
                        errors=[str(exc)],
                        notes=[f"prompt compiler schema validation failed after {attempt} attempts"],
                    ) from exc
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not self._is_retriable(exc) or attempt >= self.max_retries:
                    break
                delay = self._retry_delay_seconds(attempt, exc)
                if delay > 0:
                    time.sleep(delay)

        raise PromptCompileError(
            error_code="prompt_compile_failed",
            errors=[str(last_error) if last_error else "unknown prompt compile failure"],
            notes=[f"prompt compiler failed after {self.max_retries} attempts"],
        ) from last_error
