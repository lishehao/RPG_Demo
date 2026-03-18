from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from openai import OpenAI

from rpg_backend.author.compiler.bundle import assemble_story_overview
from rpg_backend.author.contracts import (
    CastDraft,
    CastOverviewDraft,
    DesignBundle,
    EndingAnchorSuggestionDraft,
    EndingIntentDraft,
    EndingRulesDraft,
    FocusedBrief,
    RulePack,
    StoryFrameDraft,
    StoryFrameScaffoldDraft,
    StoryOverviewDraft,
)
from rpg_backend.author.generation import beats as beat_generation
from rpg_backend.author.generation import cast as cast_generation
from rpg_backend.author.generation import endings as ending_generation
from rpg_backend.author.generation import routes as route_generation
from rpg_backend.author.generation import story_frame as story_generation
from rpg_backend.config import Settings, get_settings

ALLOWED_AFFORDANCE_TAGS = {
    "reveal_truth",
    "build_trust",
    "contain_chaos",
    "shift_public_narrative",
    "protect_civilians",
    "secure_resources",
    "unlock_ally",
    "pay_cost",
}
VALID_STORY_FUNCTIONS = {
    "advance",
    "reveal",
    "stabilize",
    "detour",
    "pay_cost",
}
T = TypeVar("T")


class AuthorGatewayError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class GatewayJSONResponse:
    payload: dict[str, Any]
    response_id: str | None
    usage: dict[str, int]
    input_characters: int


@dataclass(frozen=True)
class GatewayStructuredResponse(Generic[T]):
    value: T
    response_id: str | None


@dataclass(frozen=True)
class AuthorLLMGateway:
    client: OpenAI
    model: str
    timeout_seconds: float
    max_output_tokens_overview: int | None
    max_output_tokens_beat_plan: int | None
    max_output_tokens_rulepack: int | None
    use_session_cache: bool = False
    call_trace: list[dict[str, Any]] = field(default_factory=list, repr=False, compare=False)

    @staticmethod
    def _usage_to_dict(usage: Any) -> dict[str, Any]:
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            raw = usage.model_dump()
        elif isinstance(usage, dict):
            raw = usage
        else:
            raw = {}
            for key in dir(usage):
                if key.startswith("_"):
                    continue
                try:
                    raw[key] = getattr(usage, key)
                except Exception:  # noqa: BLE001
                    continue
        normalized: dict[str, Any] = {}
        input_details = raw.get("input_tokens_details")
        if isinstance(input_details, dict):
            if isinstance(input_details.get("cached_tokens"), (int, float)):
                normalized["cached_input_tokens"] = int(input_details["cached_tokens"])
        output_details = raw.get("output_tokens_details")
        if isinstance(output_details, dict):
            if isinstance(output_details.get("reasoning_tokens"), (int, float)):
                normalized["reasoning_tokens"] = int(output_details["reasoning_tokens"])
        x_details = raw.get("x_details")
        if isinstance(x_details, list) and x_details:
            detail = x_details[0]
            if isinstance(detail, dict):
                if isinstance(detail.get("x_billing_type"), str):
                    normalized["billing_type"] = detail["x_billing_type"]
                prompt_details = detail.get("prompt_tokens_details")
                if isinstance(prompt_details, dict):
                    if isinstance(prompt_details.get("cached_tokens"), (int, float)):
                        normalized["cached_input_tokens"] = int(prompt_details["cached_tokens"])
                    if isinstance(prompt_details.get("cache_creation_input_tokens"), (int, float)):
                        normalized["cache_creation_input_tokens"] = int(prompt_details["cache_creation_input_tokens"])
                    cache_creation = prompt_details.get("cache_creation")
                    if isinstance(cache_creation, dict):
                        for key, value in cache_creation.items():
                            if isinstance(value, (int, float)):
                                normalized[str(key)] = int(value)
                    if isinstance(prompt_details.get("cache_type"), str):
                        normalized["cache_type"] = prompt_details["cache_type"]
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = raw.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                normalized[str(key)] = int(value)
        return normalized

    def _invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_output_tokens: int | None,
        previous_response_id: str | None = None,
        operation_name: str | None = None,
    ) -> GatewayJSONResponse:
        user_text = json.dumps(user_payload, ensure_ascii=False, sort_keys=True)
        input_characters = len(user_text)
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "instructions": system_prompt,
            "input": user_text,
            "max_output_tokens": max_output_tokens,
            "timeout": self.timeout_seconds,
            "temperature": 0.2,
            "extra_body": {"enable_thinking": False},
        }
        if self.use_session_cache and previous_response_id:
            request_kwargs["previous_response_id"] = previous_response_id
        try:
            response = self.client.responses.create(**request_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise AuthorGatewayError(
                code="llm_provider_failed",
                message=str(exc),
                status_code=502,
            ) from exc
        try:
            content = response.output_text
        except Exception as exc:  # noqa: BLE001
            raise AuthorGatewayError(
                code="llm_invalid_response",
                message="provider response did not include message content",
                status_code=502,
            ) from exc
        text = str(content or "").strip()
        if not text:
            raise AuthorGatewayError(
                code="llm_invalid_json",
                message="provider returned empty content",
                status_code=502,
            )
        if text.startswith("```"):
            lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        try:
            payload = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            raise AuthorGatewayError(
                code="llm_invalid_json",
                message=str(exc),
                status_code=502,
            ) from exc
        if not isinstance(payload, dict):
            raise AuthorGatewayError(
                code="llm_invalid_json",
                message="provider returned a non-object JSON payload",
                status_code=502,
            )
        usage = self._usage_to_dict(getattr(response, "usage", None))
        self.call_trace.append(
            {
                "operation": operation_name or "unknown",
                "response_id": getattr(response, "id", None),
                "used_previous_response_id": bool(previous_response_id),
                "session_cache_enabled": bool(self.use_session_cache),
                "max_output_tokens": max_output_tokens,
                "input_characters": input_characters,
                "usage": usage,
            }
        )
        return GatewayJSONResponse(
            payload=payload,
            response_id=getattr(response, "id", None),
            usage=usage,
            input_characters=input_characters,
        )

    @staticmethod
    def _trim_text(value: Any, limit: int) -> Any:
        if not isinstance(value, str):
            return value
        text = " ".join(value.strip().split())
        if len(text) <= limit:
            return text
        clipped = text[: limit + 1]
        for separator in (". ", "; ", ", "):
            idx = clipped.rfind(separator)
            if idx >= max(24, limit // 3):
                return clipped[: idx + 1].strip()
        return text[:limit].rstrip(" ,;")

    @staticmethod
    def _coerce_int(value: Any, default: int = 0) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value or "").strip().casefold()
        if not text:
            return default
        mappings = {
            "low": 1,
            "medium": 2,
            "moderate": 2,
            "high": 3,
            "critical": 4,
            "severe": 4,
        }
        if text in mappings:
            return mappings[text]
        try:
            return int(float(text))
        except Exception:  # noqa: BLE001
            return default

    @staticmethod
    def _unique_preserve(items: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            lowered = item.casefold()
            if not item or lowered in seen:
                continue
            seen.add(lowered)
            ordered.append(item)
        return ordered

    @classmethod
    def _normalize_id_list(
        cls,
        value: Any,
        *,
        limit: int,
        text_limit: int = 80,
    ) -> list[str]:
        if isinstance(value, str):
            items = [value]
        else:
            items = list(value or [])
        normalized = [
            cls._trim_text(item, text_limit)
            for item in items[:limit]
            if isinstance(item, str) and cls._trim_text(item, text_limit)
        ]
        return cls._unique_preserve(normalized)

    @staticmethod
    def _normalize_affordance_tag(value: Any) -> str:
        text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
        mapping = {
            "reveal": "reveal_truth",
            "investigate": "reveal_truth",
            "dialogue": "build_trust",
            "trust": "build_trust",
            "community_gathering": "build_trust",
            "oral_testimony": "shift_public_narrative",
            "manual_ledger": "secure_resources",
            "calm": "contain_chaos",
            "resolution": "contain_chaos",
            "storytelling": "shift_public_narrative",
            "celebration": "build_trust",
            "hope": "build_trust",
            "resource_management": "secure_resources",
            "teamwork": "unlock_ally",
            "transparent_audit": "reveal_truth",
            "negotiated_compromise": "build_trust",
            "collective_action": "unlock_ally",
            "future_planning": "pay_cost",
        }
        normalized = mapping.get(text, text)
        if normalized not in ALLOWED_AFFORDANCE_TAGS:
            return "build_trust"
        return normalized

    @classmethod
    def _default_story_function_for_tag(cls, tag: str) -> str:
        normalized = cls._normalize_affordance_tag(tag)
        if "reveal" in normalized or "investigate" in normalized:
            return "reveal"
        if "chaos" in normalized or "protect" in normalized:
            return "stabilize"
        if "cost" in normalized:
            return "pay_cost"
        return "advance"

    @classmethod
    def _normalize_story_function(cls, value: Any, affordance_tag: str) -> str:
        text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
        if text in VALID_STORY_FUNCTIONS:
            return text
        return cls._default_story_function_for_tag(affordance_tag)

    def generate_story_frame_semantics(
        self,
        focused_brief: FocusedBrief,
        *,
        previous_response_id: str | None = None,
        story_frame_strategy: str | None = None,
    ) -> GatewayStructuredResponse[StoryFrameScaffoldDraft]:
        return story_generation.generate_story_frame_semantics(
            self,
            focused_brief,
            previous_response_id=previous_response_id,
            story_frame_strategy=story_frame_strategy,
        )

    def generate_story_frame(
        self,
        focused_brief: FocusedBrief,
        *,
        previous_response_id: str | None = None,
        story_frame_strategy: str | None = None,
    ) -> GatewayStructuredResponse[StoryFrameDraft]:
        return story_generation.generate_story_frame(
            self,
            focused_brief,
            previous_response_id=previous_response_id,
            story_frame_strategy=story_frame_strategy,
        )

    def glean_story_frame(
        self,
        focused_brief: FocusedBrief,
        partial_story_frame: StoryFrameDraft,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[StoryFrameDraft]:
        return story_generation.glean_story_frame(
            self,
            focused_brief,
            partial_story_frame,
            previous_response_id=previous_response_id,
        )

    def generate_cast_overview(
        self,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[CastOverviewDraft]:
        return cast_generation.generate_cast_overview(
            self,
            focused_brief,
            story_frame,
            previous_response_id=previous_response_id,
        )

    def glean_cast_overview(
        self,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        partial_cast_overview: CastOverviewDraft,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[CastOverviewDraft]:
        return cast_generation.glean_cast_overview(
            self,
            focused_brief,
            story_frame,
            partial_cast_overview,
            previous_response_id=previous_response_id,
        )

    def generate_story_cast(
        self,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        cast_overview: CastOverviewDraft,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[CastDraft]:
        return cast_generation.generate_story_cast(
            self,
            focused_brief,
            story_frame,
            cast_overview,
            previous_response_id=previous_response_id,
        )

    def generate_story_cast_member(
        self,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        cast_slot: dict[str, Any],
        existing_cast: list[dict[str, Any]],
        *,
        previous_response_id: str | None = None,
    ):
        return cast_generation.generate_story_cast_member(
            self,
            focused_brief,
            story_frame,
            cast_slot,
            existing_cast,
            previous_response_id=previous_response_id,
        )

    def glean_story_cast_member(
        self,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        cast_slot: dict[str, Any],
        existing_cast: list[dict[str, Any]],
        partial_member: dict[str, Any],
        *,
        previous_response_id: str | None = None,
    ):
        return cast_generation.glean_story_cast_member(
            self,
            focused_brief,
            story_frame,
            cast_slot,
            existing_cast,
            partial_member,
            previous_response_id=previous_response_id,
        )

    def glean_story_cast(
        self,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        cast_overview: CastOverviewDraft,
        partial_cast: CastDraft,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[CastDraft]:
        return cast_generation.glean_story_cast(
            self,
            focused_brief,
            story_frame,
            cast_overview,
            partial_cast,
            previous_response_id=previous_response_id,
        )

    def generate_beat_plan(
        self,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        cast_draft: CastDraft,
        *,
        previous_response_id: str | None = None,
    ):
        return beat_generation.generate_beat_plan(
            self,
            focused_brief,
            story_frame,
            cast_draft,
            previous_response_id=previous_response_id,
        )

    def generate_beat_plan_conservative(
        self,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        cast_draft: CastDraft,
        *,
        previous_response_id: str | None = None,
    ):
        return beat_generation.generate_beat_plan_conservative(
            self,
            focused_brief,
            story_frame,
            cast_draft,
            previous_response_id=previous_response_id,
        )

    def glean_beat_plan(
        self,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        cast_draft: CastDraft,
        partial_beat_plan,
        *,
        previous_response_id: str | None = None,
    ):
        return beat_generation.glean_beat_plan(
            self,
            focused_brief,
            story_frame,
            cast_draft,
            partial_beat_plan,
            previous_response_id=previous_response_id,
        )

    def generate_story_overview(self, focused_brief: FocusedBrief) -> StoryOverviewDraft:
        frame = self.generate_story_frame(focused_brief)
        cast_overview = self.generate_cast_overview(
            focused_brief,
            frame.value,
            previous_response_id=frame.response_id,
        )
        cast = self.generate_story_cast(
            focused_brief,
            frame.value,
            cast_overview.value,
            previous_response_id=cast_overview.response_id or frame.response_id,
        )
        beats = self.generate_beat_plan(
            focused_brief,
            frame.value,
            cast.value,
            previous_response_id=cast.response_id or frame.response_id,
        )
        return assemble_story_overview(frame.value, cast.value, beats.value)

    def generate_route_opportunity_plan_result(
        self,
        design_bundle: DesignBundle,
        *,
        previous_response_id: str | None = None,
    ):
        return route_generation.generate_route_opportunity_plan_result(
            self,
            design_bundle,
            previous_response_id=previous_response_id,
        )

    def generate_route_affordance_pack_result(
        self,
        design_bundle: DesignBundle,
        *,
        previous_response_id: str | None = None,
    ):
        return route_generation.generate_route_affordance_pack_result(
            self,
            design_bundle,
            previous_response_id=previous_response_id,
        )

    def generate_ending_anchor_suggestions(
        self,
        design_bundle: DesignBundle,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[EndingAnchorSuggestionDraft]:
        return ending_generation.generate_ending_anchor_suggestions(
            self,
            design_bundle,
            previous_response_id=previous_response_id,
        )

    def glean_ending_anchor_suggestions(
        self,
        design_bundle: DesignBundle,
        partial_ending_anchor_suggestions: EndingAnchorSuggestionDraft,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[EndingAnchorSuggestionDraft]:
        return ending_generation.glean_ending_anchor_suggestions(
            self,
            design_bundle,
            partial_ending_anchor_suggestions,
            previous_response_id=previous_response_id,
        )

    def generate_ending_intent_result(
        self,
        design_bundle: DesignBundle,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[EndingIntentDraft]:
        return ending_generation.generate_ending_intent_result(
            self,
            design_bundle,
            previous_response_id=previous_response_id,
        )

    def glean_ending_intent(
        self,
        design_bundle: DesignBundle,
        partial_ending_intent: EndingIntentDraft,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[EndingIntentDraft]:
        return ending_generation.glean_ending_intent(
            self,
            design_bundle,
            partial_ending_intent,
            previous_response_id=previous_response_id,
        )

    def generate_ending_rules_result(
        self,
        design_bundle: DesignBundle,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[EndingRulesDraft]:
        return ending_generation.generate_ending_rules_result(
            self,
            design_bundle,
            previous_response_id=previous_response_id,
        )

    def glean_ending_rules(
        self,
        design_bundle: DesignBundle,
        partial_ending_rules: EndingRulesDraft,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[EndingRulesDraft]:
        del partial_ending_rules
        return self.generate_ending_rules_result(
            design_bundle,
            previous_response_id=previous_response_id,
        )

    def generate_global_rulepack_result(
        self,
        design_bundle: DesignBundle,
        *,
        previous_response_id: str | None = None,
    ) -> GatewayStructuredResponse[RulePack]:
        route_affordance_pack = self.generate_route_affordance_pack_result(
            design_bundle,
            previous_response_id=previous_response_id,
        )
        ending_rules = self.generate_ending_rules_result(
            design_bundle,
            previous_response_id=route_affordance_pack.response_id,
        )
        return GatewayStructuredResponse(
            value=RulePack(
                route_unlock_rules=route_affordance_pack.value.route_unlock_rules,
                ending_rules=ending_rules.value.ending_rules,
                affordance_effect_profiles=route_affordance_pack.value.affordance_effect_profiles,
            ),
            response_id=ending_rules.response_id,
        )

    def generate_global_rulepack(self, design_bundle: DesignBundle) -> RulePack:
        return self.generate_global_rulepack_result(design_bundle).value


def get_author_llm_gateway(settings: Settings | None = None) -> AuthorLLMGateway:
    resolved = settings or get_settings()
    base_url = (resolved.responses_base_url or "").strip()
    api_key = (resolved.responses_api_key or "").strip()
    model = (resolved.responses_model or "").strip()
    if not base_url or not api_key or not model:
        raise AuthorGatewayError(
            code="llm_config_missing",
            message="APP_RESPONSES_BASE_URL, APP_RESPONSES_API_KEY, and APP_RESPONSES_MODEL are required",
            status_code=500,
        )
    use_session_cache = resolved.responses_use_session_cache
    if use_session_cache is None:
        use_session_cache = "dashscope" in base_url.casefold()
    client_kwargs: dict[str, Any] = {
        "base_url": base_url,
        "api_key": api_key,
    }
    if use_session_cache:
        client_kwargs["default_headers"] = {
            resolved.responses_session_cache_header: resolved.responses_session_cache_value,
        }
    client = OpenAI(**client_kwargs)
    return AuthorLLMGateway(
        client=client,
        model=model,
        timeout_seconds=float(resolved.responses_timeout_seconds),
        max_output_tokens_overview=resolved.responses_max_output_tokens_author_overview,
        max_output_tokens_beat_plan=resolved.responses_max_output_tokens_author_beat_plan,
        max_output_tokens_rulepack=resolved.responses_max_output_tokens_author_rulepack,
        use_session_cache=bool(use_session_cache),
    )
