from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from threading import Condition, Lock
from time import monotonic, perf_counter
from typing import Any, Literal, Protocol

from rpg_backend.config import Settings, get_settings
from rpg_backend.responses_transport import (
    JSONTransport,
    ResponsesJSONResponse,
    TransportStyle,
    build_json_transport,
    build_openai_client,
    usage_to_dict,
)

TextCapability = Literal[
    "author.story_frame_scaffold",
    "author.story_frame_finalize",
    "author.template_role_draft",
    "author.cast_member_generate",
    "author.cast_member_repair",
    "author.character_instance_variation",
    "author.spark_seed_generate",
    "author.beat_plan_generate",
    "author.beat_skeleton_generate",
    "author.beat_repair",
    "author.rulepack_generate",
    "play.interpret",
    "play.interpret_repair",
    "play.ending_judge",
    "play.pyrrhic_critic",
    "play.render",
    "play.render_repair",
    "copilot.reply",
    "copilot.rewrite_plan",
]
EmbeddingCapability = Literal["embedding.roster_query"]
GatewayProvider = Literal["openai_compatible"]


class GatewayCapabilityError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class TextCapabilityPolicy:
    capability: TextCapability
    provider: GatewayProvider
    model: str
    transport_style: TransportStyle
    timeout_seconds: float
    temperature: float
    enable_thinking: bool
    use_session_cache: bool
    max_output_tokens: int | None
    retry_attempts: int = 1
    plaintext_fallback_key: str | None = None


@dataclass(frozen=True)
class EmbeddingCapabilityPolicy:
    capability: EmbeddingCapability
    provider: GatewayProvider
    model: str
    timeout_seconds: float


@dataclass(frozen=True)
class TextCapabilityRequest:
    system_prompt: str
    user_payload: dict[str, Any]
    previous_response_id: str | None = None
    max_output_tokens: int | None = None
    operation_name: str | None = None
    plaintext_fallback_key: str | None = None
    override_plaintext_fallback_key: bool = False
    allow_raw_text_passthrough: bool = False
    skill_id: str | None = None
    skill_version: str | None = None
    contract_mode: str | None = None
    context_card_ids: list[str] = field(default_factory=list)
    context_packet_characters: int = 0
    repair_mode: str | None = None
    snapshot_id: str | None = None
    context_hash: str | None = None
    required_invariants: dict[str, Any] = field(default_factory=dict)
    context_lock_status: str | None = None


@dataclass(frozen=True)
class EmbeddingCapabilityRequest:
    text: str
    operation_name: str | None = None


@dataclass(frozen=True)
class TextCapabilityResult:
    payload: dict[str, Any]
    provider: GatewayProvider
    capability: TextCapability
    transport_style: str
    model: str
    response_id: str | None
    usage: dict[str, Any]
    input_characters: int
    started_at: datetime
    elapsed_ms: int
    used_previous_response_id: bool
    session_cache_enabled: bool
    operation_name: str | None = None
    fallback_source: str | None = None
    raw_text: str | None = None
    timeout_seconds: float | None = None
    system_prompt_characters: int = 0
    sdk_max_retries: int = 0
    gateway_queue_wait_ms: int = 0
    gateway_rate_limit_applied: bool = False
    gateway_rate_limit_window_10s_count: int = 0
    gateway_rate_limit_window_20s_count: int = 0
    gateway_rate_limit_window_60s_count: int = 0
    skill_id: str | None = None
    skill_version: str | None = None
    contract_mode: str | None = None
    context_card_ids: list[str] = field(default_factory=list)
    context_packet_characters: int = 0
    repair_mode: str | None = None
    snapshot_id: str | None = None
    context_hash: str | None = None
    required_invariants: dict[str, Any] = field(default_factory=dict)
    context_lock_status: str | None = None


@dataclass(frozen=True)
class EmbeddingCapabilityResult:
    value: list[float] | None
    provider: GatewayProvider
    capability: EmbeddingCapability
    transport_style: str
    model: str
    response_id: str | None
    usage: dict[str, Any]
    input_characters: int
    started_at: datetime
    elapsed_ms: int
    operation_name: str | None = None
    fallback_source: str | None = None


class TextCapabilityProvider(Protocol):
    def invoke(
        self,
        *,
        policy: TextCapabilityPolicy,
        request: TextCapabilityRequest,
    ) -> TextCapabilityResult: ...


class EmbeddingCapabilityProvider(Protocol):
    def invoke(
        self,
        *,
        policy: EmbeddingCapabilityPolicy,
        request: EmbeddingCapabilityRequest,
    ) -> EmbeddingCapabilityResult: ...


def _error_factory(code: str, message: str, status_code: int) -> GatewayCapabilityError:
    return GatewayCapabilityError(code=code, message=message, status_code=status_code)


def text_gateway_config_available(settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    return bool(
        resolved.resolved_gateway_base_url()
        and resolved.resolved_gateway_api_key()
        and resolved.resolved_gateway_model()
    )


def helper_gateway_config_available(settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    return bool(
        resolved.resolved_helper_gateway_base_url()
        and resolved.resolved_helper_gateway_api_key()
        and resolved.resolved_helper_gateway_model()
    )


def embedding_gateway_config_available(settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    return bool(
        resolved.resolved_gateway_embedding_base_url()
        and resolved.resolved_gateway_embedding_api_key()
        and resolved.resolved_gateway_embedding_model()
    )


def _trace_from_text_result(result: TextCapabilityResult) -> dict[str, Any]:
    return {
        "provider": result.provider,
        "capability": result.capability,
        "transport_style": result.transport_style,
        "transport": result.transport_style,
        "model": result.model,
        "response_id": result.response_id,
        "used_previous_response_id": result.used_previous_response_id,
        "session_cache_enabled": result.session_cache_enabled,
        "input_characters": result.input_characters,
        "usage": result.usage,
        "started_at": result.started_at.isoformat(),
        "elapsed_ms": result.elapsed_ms,
        "timeout_seconds": result.timeout_seconds,
        "system_prompt_characters": result.system_prompt_characters,
        "sdk_max_retries": result.sdk_max_retries,
        "sdk_retries_disabled": result.sdk_max_retries == 0,
        "fallback_source": result.fallback_source,
        "operation_name": result.operation_name or result.capability,
        "operation": result.operation_name or result.capability,
        "gateway_queue_wait_ms": result.gateway_queue_wait_ms,
        "gateway_rate_limit_applied": result.gateway_rate_limit_applied,
        "gateway_rate_limit_window_10s_count": result.gateway_rate_limit_window_10s_count,
        "gateway_rate_limit_window_20s_count": result.gateway_rate_limit_window_20s_count,
        "gateway_rate_limit_window_60s_count": result.gateway_rate_limit_window_60s_count,
        "skill_id": result.skill_id,
        "skill_version": result.skill_version,
        "contract_mode": result.contract_mode,
        "context_card_ids": list(result.context_card_ids),
        "context_packet_characters": result.context_packet_characters,
        "repair_mode": result.repair_mode,
        "snapshot_id": result.snapshot_id,
        "context_hash": result.context_hash,
        "required_invariants": dict(result.required_invariants),
        "context_lock_status": result.context_lock_status,
    }


def _failed_text_trace(
    *,
    policy: TextCapabilityPolicy,
    request: TextCapabilityRequest,
    error: GatewayCapabilityError,
    started_at: datetime,
    elapsed_ms: int,
    rate_limit: TextRateLimitDecision,
) -> dict[str, Any]:
    return {
        "provider": policy.provider,
        "capability": policy.capability,
        "transport_style": policy.transport_style,
        "transport": policy.transport_style,
        "model": policy.model,
        "response_id": None,
        "used_previous_response_id": bool(request.previous_response_id),
        "session_cache_enabled": bool(policy.use_session_cache),
        "input_characters": len(str(request.user_payload)),
        "usage": {},
        "started_at": started_at.isoformat(),
        "elapsed_ms": elapsed_ms,
        "system_prompt_characters": len(str(request.system_prompt or "")),
        "fallback_source": None,
        "operation_name": request.operation_name or policy.capability,
        "operation": request.operation_name or policy.capability,
        "timeout_seconds": policy.timeout_seconds,
        "sdk_max_retries": 0,
        "sdk_retries_disabled": True,
        "error_code": error.code,
        "error_message": error.message,
        "gateway_queue_wait_ms": rate_limit.wait_ms,
        "gateway_rate_limit_applied": rate_limit.applied,
        "gateway_rate_limit_window_10s_count": int(rate_limit.window_counts.get("10s", 0)),
        "gateway_rate_limit_window_20s_count": int(rate_limit.window_counts.get("20s", 0)),
        "gateway_rate_limit_window_60s_count": int(rate_limit.window_counts.get("60s", 0)),
        "skill_id": request.skill_id,
        "skill_version": request.skill_version,
        "contract_mode": request.contract_mode,
        "context_card_ids": list(request.context_card_ids),
        "context_packet_characters": int(request.context_packet_characters or 0),
        "repair_mode": request.repair_mode,
        "snapshot_id": request.snapshot_id,
        "context_hash": request.context_hash,
        "required_invariants": dict(request.required_invariants),
        "context_lock_status": request.context_lock_status,
    }


def _trace_from_embedding_result(result: EmbeddingCapabilityResult) -> dict[str, Any]:
    return {
        "provider": result.provider,
        "capability": result.capability,
        "transport_style": result.transport_style,
        "transport": result.transport_style,
        "model": result.model,
        "response_id": result.response_id,
        "used_previous_response_id": False,
        "session_cache_enabled": False,
        "input_characters": result.input_characters,
        "usage": result.usage,
        "started_at": result.started_at.isoformat(),
        "elapsed_ms": result.elapsed_ms,
        "fallback_source": result.fallback_source,
        "operation_name": result.operation_name or result.capability,
        "operation": result.operation_name or result.capability,
    }


def _text_policy_spec(
    settings: Settings,
    capability: TextCapability,
    *,
    transport_style: TransportStyle,
) -> TextCapabilityPolicy:
    text_model = settings.resolved_gateway_model_for_text_capability(capability)
    if not text_model:
        raise GatewayCapabilityError(
            code="gateway_text_model_missing",
            message="gateway text model is not configured",
            status_code=500,
        )
    temperature = 0.2 if capability.startswith("author.") or capability.startswith("copilot.") else 0.4
    enable_thinking = settings.resolved_gateway_enable_thinking(capability)
    return TextCapabilityPolicy(
        capability=capability,
        provider=settings.resolved_gateway_text_provider(),
        model=text_model,
        transport_style=transport_style,
        timeout_seconds=settings.resolved_gateway_timeout_seconds_for_text_capability(capability),
        temperature=temperature,
        enable_thinking=enable_thinking,
        use_session_cache=settings.resolved_gateway_use_session_cache(transport_style=transport_style),
        max_output_tokens=settings.resolved_gateway_text_max_output_tokens(capability),
        retry_attempts=1,
        plaintext_fallback_key="narration" if capability in {"play.render", "play.render_repair"} else None,
    )


def _embedding_policy_spec(settings: Settings, capability: EmbeddingCapability) -> EmbeddingCapabilityPolicy:
    embedding_model = settings.resolved_gateway_embedding_model()
    if not embedding_model:
        raise GatewayCapabilityError(
            code="gateway_embedding_model_missing",
            message="gateway embedding model is not configured",
            status_code=500,
        )
    return EmbeddingCapabilityPolicy(
        capability=capability,
        provider=settings.resolved_gateway_embedding_provider(),
        model=embedding_model,
        timeout_seconds=settings.resolved_gateway_timeout_seconds(),
    )


@dataclass(frozen=True)
class _RateLimitWindow:
    label: str
    seconds: float
    cap: int


@dataclass(frozen=True)
class TextRateLimitDecision:
    wait_ms: int
    applied: bool
    window_counts: dict[str, int]


@dataclass(frozen=True)
class GatewayTextRateLimitSnapshot:
    enabled: bool
    current_queue_depth: int
    admitted_last_60s: int
    average_wait_ms: float
    max_wait_ms: int
    total_admitted: int


class ShapedTextRateLimiter:
    def __init__(
        self,
        *,
        enabled: bool,
        windows: tuple[_RateLimitWindow, ...],
        clock: callable = monotonic,
    ) -> None:
        self._enabled = enabled
        self._windows = tuple(sorted(windows, key=lambda item: item.seconds))
        self._max_window_seconds = max((item.seconds for item in self._windows), default=0.0)
        self._clock = clock
        self._timestamps: deque[float] = deque()
        self._condition = Condition()
        self._next_ticket = 0
        self._serving_ticket = 0
        self._wait_ms_total = 0
        self._wait_count = 0
        self._max_wait_ms = 0
        self._total_admitted = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _prune(self, now: float) -> None:
        if self._max_window_seconds <= 0:
            self._timestamps.clear()
            return
        while self._timestamps and now - self._timestamps[0] >= self._max_window_seconds:
            self._timestamps.popleft()

    def _window_counts(self, now: float) -> dict[str, int]:
        self._prune(now)
        counts: dict[str, int] = {}
        timestamps = list(self._timestamps)
        for window in self._windows:
            threshold = now - window.seconds
            counts[window.label] = sum(1 for item in timestamps if item > threshold)
        return counts

    def _admission_delay(self, now: float) -> tuple[float, dict[str, int]]:
        counts = self._window_counts(now)
        next_ready_at = now
        timestamps = list(self._timestamps)
        for window in self._windows:
            count = counts[window.label]
            if count < window.cap:
                continue
            threshold = now - window.seconds
            relevant = [item for item in timestamps if item > threshold]
            if not relevant:
                continue
            next_ready_at = max(next_ready_at, relevant[0] + window.seconds)
        return max(next_ready_at - now, 0.0), counts

    def acquire(self) -> TextRateLimitDecision:
        if not self._enabled:
            return TextRateLimitDecision(
                wait_ms=0,
                applied=False,
                window_counts={"10s": 0, "20s": 0, "60s": 0},
            )
        started_at = self._clock()
        with self._condition:
            ticket = self._next_ticket
            self._next_ticket += 1
            while True:
                now = self._clock()
                if ticket != self._serving_ticket:
                    self._condition.wait(timeout=0.05)
                    continue
                delay_seconds, _counts_before = self._admission_delay(now)
                if delay_seconds <= 0:
                    admitted_at = self._clock()
                    self._timestamps.append(admitted_at)
                    self._serving_ticket += 1
                    wait_ms = max(int((admitted_at - started_at) * 1000), 0)
                    self._wait_ms_total += wait_ms
                    self._wait_count += 1
                    self._max_wait_ms = max(self._max_wait_ms, wait_ms)
                    self._total_admitted += 1
                    counts_after = self._window_counts(admitted_at)
                    self._condition.notify_all()
                    return TextRateLimitDecision(
                        wait_ms=wait_ms,
                        applied=True,
                        window_counts=counts_after,
                    )
                self._condition.wait(timeout=delay_seconds)

    def snapshot(self) -> GatewayTextRateLimitSnapshot:
        with self._condition:
            now = self._clock()
            counts = self._window_counts(now)
            average_wait_ms = (self._wait_ms_total / self._wait_count) if self._wait_count else 0.0
            return GatewayTextRateLimitSnapshot(
                enabled=self._enabled,
                current_queue_depth=max(self._next_ticket - self._serving_ticket, 0),
                admitted_last_60s=counts.get("60s", 0),
                average_wait_ms=average_wait_ms,
                max_wait_ms=self._max_wait_ms,
                total_admitted=self._total_admitted,
            )


_TEXT_RATE_LIMITERS: dict[tuple[bool, int, int, int], ShapedTextRateLimiter] = {}
_TEXT_RATE_LIMITERS_LOCK = Lock()


def _text_rate_limiter_key(settings: Settings) -> tuple[bool, int, int, int]:
    return (
        settings.resolved_gateway_text_rate_limit_enabled(),
        settings.resolved_gateway_text_rate_limit_per_minute(),
        settings.resolved_gateway_text_rate_limit_10s_cap(),
        settings.resolved_gateway_text_rate_limit_20s_cap(),
    )


def get_shared_text_rate_limiter(settings: Settings | None = None) -> ShapedTextRateLimiter:
    resolved = settings or get_settings()
    key = _text_rate_limiter_key(resolved)
    with _TEXT_RATE_LIMITERS_LOCK:
        limiter = _TEXT_RATE_LIMITERS.get(key)
        if limiter is None:
            limiter = ShapedTextRateLimiter(
                enabled=resolved.resolved_gateway_text_rate_limit_enabled(),
                windows=(
                    _RateLimitWindow(label="10s", seconds=10.0, cap=resolved.resolved_gateway_text_rate_limit_10s_cap()),
                    _RateLimitWindow(label="20s", seconds=20.0, cap=resolved.resolved_gateway_text_rate_limit_20s_cap()),
                    _RateLimitWindow(label="60s", seconds=60.0, cap=resolved.resolved_gateway_text_rate_limit_per_minute()),
                ),
            )
            _TEXT_RATE_LIMITERS[key] = limiter
        return limiter


def get_shared_text_rate_limiter_snapshot(settings: Settings | None = None) -> GatewayTextRateLimitSnapshot:
    return get_shared_text_rate_limiter(settings).snapshot()


def reset_shared_text_rate_limiters_for_test() -> None:
    with _TEXT_RATE_LIMITERS_LOCK:
        _TEXT_RATE_LIMITERS.clear()


@dataclass
class OpenAICompatibleTextProvider:
    settings: Settings

    def invoke(
        self,
        *,
        policy: TextCapabilityPolicy,
        request: TextCapabilityRequest,
    ) -> TextCapabilityResult:
        base_url = self.settings.resolved_gateway_base_url(transport_style=policy.transport_style)
        api_key = self.settings.resolved_gateway_api_key()
        if not base_url or not api_key:
            raise GatewayCapabilityError(
                code="gateway_text_config_missing",
                message="gateway text provider base_url/api_key is not configured",
                status_code=500,
            )
        started_at = datetime.now(timezone.utc)
        started_perf = perf_counter()
        transport_trace: list[dict[str, Any]] = []
        client = build_openai_client(
            base_url=base_url,
            api_key=api_key,
            use_session_cache=policy.use_session_cache,
            session_cache_header=self.settings.resolved_gateway_session_cache_header(),
            session_cache_value=self.settings.resolved_gateway_session_cache_value(),
            max_retries=0,
        )
        transport: JSONTransport = build_json_transport(
            style=policy.transport_style,
            client=client,
            model=policy.model,
            timeout_seconds=policy.timeout_seconds,
            use_session_cache=policy.use_session_cache,
            temperature=policy.temperature,
            enable_thinking=policy.enable_thinking,
            provider_failed_code="gateway_text_provider_failed",
            invalid_response_code="gateway_text_invalid_response",
            invalid_json_code="gateway_text_invalid_json",
            error_factory=_error_factory,
            call_trace=transport_trace,
        )
        raw = transport.invoke_json(
            system_prompt=request.system_prompt,
            user_payload=request.user_payload,
            max_output_tokens=request.max_output_tokens if request.max_output_tokens is not None else policy.max_output_tokens,
            previous_response_id=request.previous_response_id,
            operation_name=request.operation_name or policy.capability,
            plaintext_fallback_key=(
                request.plaintext_fallback_key
                if request.override_plaintext_fallback_key
                else request.plaintext_fallback_key or policy.plaintext_fallback_key
            ),
            allow_raw_text_passthrough=request.allow_raw_text_passthrough,
        )
        trace = transport_trace[-1] if transport_trace else {}
        return TextCapabilityResult(
            payload=raw.payload,
            provider=policy.provider,
            capability=policy.capability,
            transport_style=str(trace.get("transport") or policy.transport_style),
            model=policy.model,
            response_id=raw.response_id,
            usage=dict(raw.usage),
            input_characters=raw.input_characters,
            started_at=started_at,
            elapsed_ms=max(int((perf_counter() - started_perf) * 1000), 0),
            used_previous_response_id=bool(trace.get("used_previous_response_id")),
            session_cache_enabled=bool(trace.get("session_cache_enabled")),
            operation_name=request.operation_name,
            fallback_source=getattr(raw, "fallback_source", None),
            raw_text=getattr(raw, "raw_text", None),
            timeout_seconds=policy.timeout_seconds,
            system_prompt_characters=len(request.system_prompt),
            sdk_max_retries=0,
            skill_id=request.skill_id,
            skill_version=request.skill_version,
            contract_mode=request.contract_mode,
            context_card_ids=list(request.context_card_ids),
            context_packet_characters=int(request.context_packet_characters or 0),
            repair_mode=request.repair_mode,
            snapshot_id=request.snapshot_id,
            context_hash=request.context_hash,
            required_invariants=dict(request.required_invariants),
            context_lock_status=request.context_lock_status,
        )


@dataclass
class OpenAICompatibleEmbeddingProvider:
    settings: Settings

    def invoke(
        self,
        *,
        policy: EmbeddingCapabilityPolicy,
        request: EmbeddingCapabilityRequest,
    ) -> EmbeddingCapabilityResult:
        base_url = self.settings.resolved_gateway_embedding_base_url()
        api_key = self.settings.resolved_gateway_embedding_api_key()
        if not base_url or not api_key:
            raise GatewayCapabilityError(
                code="gateway_embedding_config_missing",
                message="gateway embedding provider base_url/api_key is not configured",
                status_code=500,
            )
        started_at = datetime.now(timezone.utc)
        started_perf = perf_counter()
        client = build_openai_client(
            base_url=base_url,
            api_key=api_key,
            use_session_cache=False,
            session_cache_header=self.settings.resolved_gateway_session_cache_header(),
            session_cache_value=self.settings.resolved_gateway_session_cache_value(),
            max_retries=0,
        )
        try:
            response = client.embeddings.create(
                model=policy.model,
                input=[request.text],
                timeout=policy.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise GatewayCapabilityError(
                code="gateway_embedding_provider_failed",
                message=str(exc),
                status_code=502,
            ) from exc
        data = getattr(response, "data", None) or []
        embedding: list[float] | None = None
        if data:
            first = data[0]
            raw_embedding = getattr(first, "embedding", None)
            if raw_embedding:
                embedding = [float(item) for item in raw_embedding]
        return EmbeddingCapabilityResult(
            value=embedding,
            provider=policy.provider,
            capability=policy.capability,
            transport_style="embeddings",
            model=policy.model,
            response_id=getattr(response, "id", None),
            usage=usage_to_dict(getattr(response, "usage", None)),
            input_characters=len(request.text),
            started_at=started_at,
            elapsed_ms=max(int((perf_counter() - started_perf) * 1000), 0),
            operation_name=request.operation_name,
            fallback_source=None if embedding is not None else "empty_embedding",
        )


@dataclass
class CapabilityGatewayCore:
    settings: Settings
    default_transport_style: TransportStyle = "responses"
    capability_transport_overrides: dict[TextCapability, TransportStyle] = field(default_factory=dict)
    call_trace: list[dict[str, Any]] = field(default_factory=list)
    _text_provider: TextCapabilityProvider = field(init=False, repr=False)
    _embedding_provider: EmbeddingCapabilityProvider = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._text_provider = OpenAICompatibleTextProvider(self.settings)
        self._embedding_provider = OpenAICompatibleEmbeddingProvider(self.settings)

    def text_policy(self, capability: TextCapability) -> TextCapabilityPolicy:
        return _text_policy_spec(
            self.settings,
            capability,
            transport_style=self.capability_transport_overrides.get(capability, self.default_transport_style),
        )

    def embedding_policy(self, capability: EmbeddingCapability) -> EmbeddingCapabilityPolicy:
        return _embedding_policy_spec(self.settings, capability)

    def invoke_text_capability(
        self,
        capability: TextCapability,
        request: TextCapabilityRequest,
    ) -> TextCapabilityResult:
        policy = self.text_policy(capability)
        rate_limit = get_shared_text_rate_limiter(self.settings).acquire()
        started_at = datetime.now(timezone.utc)
        started_perf = perf_counter()
        try:
            result = self._text_provider.invoke(policy=policy, request=request)
        except GatewayCapabilityError as exc:
            self.call_trace.append(
                _failed_text_trace(
                    policy=policy,
                    request=request,
                    error=exc,
                    started_at=started_at,
                    elapsed_ms=max(int((perf_counter() - started_perf) * 1000), 0),
                    rate_limit=rate_limit,
                )
            )
            raise
        result = replace(
            result,
            gateway_queue_wait_ms=rate_limit.wait_ms,
            gateway_rate_limit_applied=rate_limit.applied,
            gateway_rate_limit_window_10s_count=int(rate_limit.window_counts.get("10s", 0)),
            gateway_rate_limit_window_20s_count=int(rate_limit.window_counts.get("20s", 0)),
            gateway_rate_limit_window_60s_count=int(rate_limit.window_counts.get("60s", 0)),
        )
        self.call_trace.append(_trace_from_text_result(result))
        return result

    def invoke_embedding_capability(
        self,
        capability: EmbeddingCapability,
        request: EmbeddingCapabilityRequest,
    ) -> EmbeddingCapabilityResult:
        result = self._embedding_provider.invoke(policy=self.embedding_policy(capability), request=request)
        self.call_trace.append(_trace_from_embedding_result(result))
        return result

def build_gateway_core(
    settings: Settings | None = None,
    *,
    transport_style: TransportStyle = "responses",
    capability_transport_overrides: dict[TextCapability, TransportStyle] | None = None,
) -> CapabilityGatewayCore:
    return CapabilityGatewayCore(
        settings=settings or get_settings(),
        default_transport_style=transport_style,
        capability_transport_overrides=dict(capability_transport_overrides or {}),
    )
