from __future__ import annotations


class RuntimeLLMError(RuntimeError):
    def __init__(
        self,
        *,
        error_code: str,
        stage: str,
        provider: str,
        message: str,
        provider_error_code: str | None = None,
        llm_duration_ms: int | None = None,
        gateway_mode: str | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.stage = stage
        self.provider = provider
        self.message = message
        self.provider_error_code = provider_error_code
        self.llm_duration_ms = llm_duration_ms
        self.gateway_mode = gateway_mode


class RuntimeRouteError(RuntimeLLMError):
    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        provider: str = "openai",
        provider_error_code: str | None = None,
        llm_duration_ms: int | None = None,
        gateway_mode: str | None = None,
    ):
        super().__init__(
            error_code=error_code,
            stage="route",
            provider=provider,
            message=message,
            provider_error_code=provider_error_code,
            llm_duration_ms=llm_duration_ms,
            gateway_mode=gateway_mode,
        )


class RuntimeNarrationError(RuntimeLLMError):
    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        provider: str = "openai",
        provider_error_code: str | None = None,
        llm_duration_ms: int | None = None,
        gateway_mode: str | None = None,
    ):
        super().__init__(
            error_code=error_code,
            stage="narration",
            provider=provider,
            message=message,
            provider_error_code=provider_error_code,
            llm_duration_ms=llm_duration_ms,
            gateway_mode=gateway_mode,
        )
