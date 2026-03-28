from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock, Semaphore
from time import monotonic, perf_counter, sleep
from typing import Any

from rpg_backend.config import Settings, get_settings
from rpg_backend.responses_transport import (
    JSONTransport,
    TransportStyle,
    build_json_transport,
    build_openai_client,
)

_HELPER_PROVIDER_MAX_CONCURRENCY = 20
_HELPER_PROVIDER_MAX_REQUESTS_PER_MINUTE = 120
_HELPER_PROVIDER_MIN_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class HelperProviderRateLimitDecision:
    wait_ms: int
    applied: bool


class HelperProviderRateLimiter:
    def __init__(
        self,
        *,
        max_concurrency: int,
        max_requests_per_minute: int,
        clock=monotonic,
        sleeper=sleep,
    ) -> None:
        self.max_concurrency = max(1, int(max_concurrency))
        self.max_requests_per_minute = max(1, int(max_requests_per_minute))
        self._clock = clock
        self._sleeper = sleeper
        self._timestamps: list[float] = []
        self._lock = Lock()
        self._semaphore = Semaphore(self.max_concurrency)

    def _prune(self, now: float) -> None:
        self._timestamps = [item for item in self._timestamps if now - item < 60.0]

    @contextmanager
    def acquire(self):
        started_at = self._clock()
        self._semaphore.acquire()
        try:
            while True:
                now = self._clock()
                with self._lock:
                    self._prune(now)
                    if len(self._timestamps) < self.max_requests_per_minute:
                        self._timestamps.append(now)
                        wait_ms = max(int((now - started_at) * 1000), 0)
                        yield HelperProviderRateLimitDecision(
                            wait_ms=wait_ms,
                            applied=wait_ms > 0,
                        )
                        return
                    next_ready_in = max(60.0 - (now - self._timestamps[0]), 0.01)
                self._sleeper(next_ready_in)
        finally:
            self._semaphore.release()


_HELPER_PROVIDER_LIMITERS: dict[tuple[str, str, int, int], HelperProviderRateLimiter] = {}
_HELPER_PROVIDER_LIMITERS_LOCK = Lock()


def get_shared_helper_provider_limiter(*, base_url: str, model: str) -> HelperProviderRateLimiter:
    key = (
        str(base_url).strip(),
        str(model).strip(),
        _HELPER_PROVIDER_MAX_CONCURRENCY,
        _HELPER_PROVIDER_MAX_REQUESTS_PER_MINUTE,
    )
    with _HELPER_PROVIDER_LIMITERS_LOCK:
        limiter = _HELPER_PROVIDER_LIMITERS.get(key)
        if limiter is None:
            limiter = HelperProviderRateLimiter(
                max_concurrency=_HELPER_PROVIDER_MAX_CONCURRENCY,
                max_requests_per_minute=_HELPER_PROVIDER_MAX_REQUESTS_PER_MINUTE,
            )
            _HELPER_PROVIDER_LIMITERS[key] = limiter
        return limiter


class HelperAgentError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class HelperRequest:
    system_prompt: str
    user_payload: dict[str, Any]
    max_output_tokens: int | None = None
    operation_name: str | None = None
    previous_response_id: str | None = None
    plaintext_fallback_key: str | None = None
    allow_raw_text_passthrough: bool = True


@dataclass(frozen=True)
class HelperResponse:
    payload: dict[str, Any]
    response_id: str | None
    usage: dict[str, Any]
    input_characters: int
    raw_text: str | None
    fallback_source: str | None
    transport_style: str
    model: str
    operation_name: str | None = None
    elapsed_ms: int = 0


@dataclass
class HelperAgentClient:
    settings: Settings | None = None
    transport_style: TransportStyle = "chat_completions"
    temperature: float = 0.3
    default_max_output_tokens: int | None = None
    call_trace: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.settings = self.settings or get_settings()
        assert self.settings is not None
        self._resolved_settings = self.settings
        self._base_url = self._resolved_settings.resolved_helper_gateway_base_url(
            transport_style=self.transport_style
        )
        self._api_key = self._resolved_settings.resolved_helper_gateway_api_key()
        self._model = self._resolved_settings.resolved_helper_gateway_model()
        self._timeout_seconds = max(
            self._resolved_settings.resolved_gateway_timeout_seconds_for_benchmark_driver(),
            _HELPER_PROVIDER_MIN_TIMEOUT_SECONDS,
        )
        self._use_session_cache = self._resolved_settings.resolved_helper_gateway_use_session_cache(
            transport_style=self.transport_style
        )
        if not self._base_url or not self._api_key or not self._model:
            raise HelperAgentError(
                code="helper_agent_config_missing",
                message=(
                    "APP_HELPER_GATEWAY_BASE_URL, APP_HELPER_GATEWAY_API_KEY, and "
                    "APP_HELPER_GATEWAY_MODEL are required for helper agents"
                ),
                status_code=500,
            )
        self._client = build_openai_client(
            base_url=self._base_url,
            api_key=self._api_key,
            use_session_cache=self._use_session_cache,
            session_cache_header=self._resolved_settings.resolved_gateway_session_cache_header(),
            session_cache_value=self._resolved_settings.resolved_gateway_session_cache_value(),
            max_retries=0,
        )
        self._transport: JSONTransport = build_json_transport(
            style=self.transport_style,
            client=self._client,
            model=self._model,
            timeout_seconds=self._timeout_seconds,
            use_session_cache=self._use_session_cache,
            temperature=self.temperature,
            enable_thinking=False,
            provider_failed_code="helper_agent_provider_failed",
            invalid_response_code="helper_agent_invalid_response",
            invalid_json_code="helper_agent_invalid_json",
            error_factory=self._error_factory,
            call_trace=self.call_trace,
        )
        self._rate_limiter = get_shared_helper_provider_limiter(
            base_url=self._base_url,
            model=self._model,
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    def _error_factory(self, code: str, message: str, status_code: int) -> HelperAgentError:
        return HelperAgentError(code=code, message=message, status_code=status_code)

    def invoke(self, request: HelperRequest) -> HelperResponse:
        started_at = perf_counter()
        try:
            with self._rate_limiter.acquire() as decision:
                response = self._transport.invoke_json(
                    system_prompt=request.system_prompt,
                    user_payload=request.user_payload,
                    max_output_tokens=(
                        request.max_output_tokens
                        if request.max_output_tokens is not None
                        else self.default_max_output_tokens
                    ),
                    previous_response_id=request.previous_response_id,
                    operation_name=request.operation_name,
                    plaintext_fallback_key=request.plaintext_fallback_key,
                    allow_raw_text_passthrough=request.allow_raw_text_passthrough,
                )
        except HelperAgentError as exc:
            self.call_trace.append(
                {
                    "transport": self.transport_style,
                    "transport_style": self.transport_style,
                    "operation": request.operation_name or "helper.invoke",
                    "operation_name": request.operation_name or "helper.invoke",
                    "model": self._model,
                    "elapsed_ms": max(int((perf_counter() - started_at) * 1000), 0),
                    "error_code": exc.code,
                    "error_message": exc.message,
                    "provider_rate_limit_wait_ms": 0,
                    "provider_rate_limit_applied": False,
                }
            )
            raise
        if self.call_trace:
            self.call_trace[-1].update(
                {
                    "transport_style": self.transport_style,
                    "operation_name": request.operation_name or self.call_trace[-1].get("operation_name") or "helper.invoke",
                    "model": self._model,
                    "fallback_source": response.fallback_source,
                    "elapsed_ms": max(int((perf_counter() - started_at) * 1000), 0),
                    "provider_rate_limit_wait_ms": decision.wait_ms,
                    "provider_rate_limit_applied": decision.applied,
                }
            )
        return HelperResponse(
            payload=dict(response.payload),
            response_id=response.response_id,
            usage=dict(response.usage),
            input_characters=response.input_characters,
            raw_text=response.raw_text,
            fallback_source=response.fallback_source,
            transport_style=self.transport_style,
            model=self._model,
            operation_name=request.operation_name,
            elapsed_ms=max(int((perf_counter() - started_at) * 1000), 0),
        )

    def invoke_batch(
        self,
        requests: list[HelperRequest],
        *,
        max_concurrency: int = _HELPER_PROVIDER_MAX_CONCURRENCY,
    ) -> list[HelperResponse]:
        if not requests:
            return []
        worker_count = max(1, min(int(max_concurrency), len(requests)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            return list(executor.map(self.invoke, requests))
