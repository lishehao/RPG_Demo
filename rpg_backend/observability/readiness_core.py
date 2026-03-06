from __future__ import annotations

import asyncio
import copy
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


def utc_now() -> datetime:
    return datetime.now(UTC)


def monotonic() -> float:
    return time.monotonic()


def build_check_payload(
    *,
    ok: bool,
    latency_ms: int | None,
    checked_at: datetime | None = None,
    error_code: str | None = None,
    message: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "latency_ms": latency_ms,
        "checked_at": checked_at or utc_now(),
        "error_code": error_code,
        "message": message,
        "meta": meta or {},
    }


def validate_required_config(values: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key, value in values.items():
        if value is None:
            missing.append(key)
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(key)
    return missing


def _clone(value: T) -> T:
    model_copy = getattr(value, "model_copy", None)
    if callable(model_copy):
        return model_copy(deep=True)  # type: ignore[return-value]
    return copy.deepcopy(value)


@dataclass
class _CacheEntry(Generic[T]):
    cache_key: str
    expires_at: float
    value: T


class AsyncTTLProbeCache(Generic[T]):
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._entry: _CacheEntry[T] | None = None

    async def reset(self) -> None:
        async with self._lock:
            self._entry = None

    async def get_or_compute(
        self,
        *,
        refresh: bool,
        cache_key: str,
        ttl_seconds: float,
        compute: Callable[[], Awaitable[T]],
        mark_cached: Callable[[T], T],
        now_provider: Callable[[], float] = monotonic,
    ) -> T:
        now = now_provider()
        if not refresh:
            async with self._lock:
                entry = self._entry
                if entry is not None and entry.cache_key == cache_key and entry.expires_at > now:
                    cached = _clone(entry.value)
                    return mark_cached(cached)

        value = await compute()
        async with self._lock:
            self._entry = _CacheEntry(
                cache_key=cache_key,
                expires_at=now_provider() + float(ttl_seconds),
                value=_clone(value),
            )
        return value
