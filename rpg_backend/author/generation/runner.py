from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, TypeVar

from rpg_backend.responses_transport import StructuredResponse

if TYPE_CHECKING:
    from rpg_backend.author.gateway import AuthorLLMGateway

T = TypeVar("T")


def invoke_structured_generation_with_retries(
    gateway: "AuthorLLMGateway",
    *,
    primary_payload: dict[str, Any],
    prompts: tuple[str, ...],
    previous_response_id: str | None,
    max_output_tokens: int | None,
    operation_name: str,
    parse_value: Callable[[dict[str, Any]], T],
    final_retry_payload: dict[str, Any] | None = None,
) -> StructuredResponse[T]:
    from rpg_backend.author.gateway import AuthorGatewayError

    retryable_codes = {"llm_invalid_json", "llm_schema_invalid"}
    attempt_prev = previous_response_id
    last_error: Exception | None = None

    for index, prompt in enumerate(prompts):
        payload = (
            final_retry_payload
            if final_retry_payload is not None and index == len(prompts) - 1
            else primary_payload
        )
        try:
            raw = gateway._invoke_json(
                system_prompt=prompt,
                user_payload=payload,
                max_output_tokens=max_output_tokens,
                previous_response_id=attempt_prev,
                operation_name=operation_name,
            )
        except AuthorGatewayError as exc:
            last_error = exc
            if exc.code not in retryable_codes or index == len(prompts) - 1:
                raise
            continue

        try:
            value = parse_value(raw.payload)
        except Exception as exc:  # noqa: BLE001
            last_error = AuthorGatewayError(
                code="llm_schema_invalid",
                message=str(exc),
                status_code=502,
            )
            attempt_prev = raw.response_id or attempt_prev
            if index == len(prompts) - 1:
                raise last_error from exc
            continue

        return StructuredResponse(
            value=value,
            response_id=raw.response_id or attempt_prev,
        )

    if isinstance(last_error, AuthorGatewayError):
        raise last_error
    raise AuthorGatewayError(
        code="llm_schema_invalid",
        message=str(last_error or f"{operation_name} failed"),
        status_code=502,
    )
