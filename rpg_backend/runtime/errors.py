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
        response_id: str | None = None,
        reasoning_summary: str | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.stage = stage
        self.provider = provider
        self.message = message
        self.provider_error_code = provider_error_code
        self.llm_duration_ms = llm_duration_ms
        self.gateway_mode = gateway_mode
        self.response_id = response_id
        self.reasoning_summary = reasoning_summary


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
        response_id: str | None = None,
        reasoning_summary: str | None = None,
    ):
        super().__init__(
            error_code=error_code,
            stage="interpret_turn",
            provider=provider,
            message=message,
            provider_error_code=provider_error_code,
            llm_duration_ms=llm_duration_ms,
            gateway_mode=gateway_mode,
            response_id=response_id,
            reasoning_summary=reasoning_summary,
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
        response_id: str | None = None,
        reasoning_summary: str | None = None,
    ):
        super().__init__(
            error_code=error_code,
            stage="render_resolved_turn",
            provider=provider,
            message=message,
            provider_error_code=provider_error_code,
            llm_duration_ms=llm_duration_ms,
            gateway_mode=gateway_mode,
            response_id=response_id,
            reasoning_summary=reasoning_summary,
        )
