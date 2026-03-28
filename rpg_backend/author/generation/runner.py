from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, TypeVar

from rpg_backend.author.gateway import AuthorGatewayError
from rpg_backend.generation_skill import GenerationSkillPacket, SkillPromptVariant
from rpg_backend.llm_gateway import CapabilityGatewayCore, GatewayCapabilityError, TextCapability, TextCapabilityRequest
from rpg_backend.responses_transport import StructuredResponse

T = TypeVar("T")


def invoke_structured_generation_with_retries(
    gateway: CapabilityGatewayCore,
    *,
    capability: TextCapability,
    primary_payload: dict[str, Any],
    prompts: tuple[str, ...],
    previous_response_id: str | None,
    max_output_tokens: int | None,
    operation_name: str,
    parse_value: Callable[[dict[str, Any]], T],
    final_retry_payload: dict[str, Any] | None = None,
    skill_packet: GenerationSkillPacket | None = None,
) -> StructuredResponse[T]:
    retryable_codes = {"llm_invalid_json", "llm_schema_invalid"}
    attempt_prev = previous_response_id
    last_error: Exception | None = None

    packet_variants: tuple[SkillPromptVariant, ...] = ("normal", "repair", "final_contract")
    for index, prompt in enumerate(prompts):
        is_final_retry = index == len(prompts) - 1
        if skill_packet is not None:
            variant = packet_variants[min(index, len(packet_variants) - 1)]
            payload = skill_packet.context_payload(final_retry=is_final_retry)
            prompt = skill_packet.build_system_prompt(variant=variant)
        else:
            payload = (
                final_retry_payload
                if final_retry_payload is not None and is_final_retry
                else primary_payload
            )
        try:
            result = gateway.invoke_text_capability(
                capability,
                TextCapabilityRequest(
                    system_prompt=prompt,
                    user_payload=payload,
                    max_output_tokens=max_output_tokens,
                    previous_response_id=attempt_prev,
                    operation_name=operation_name,
                    skill_id=skill_packet.skill_id if skill_packet is not None else None,
                    skill_version=skill_packet.skill_version if skill_packet is not None else None,
                    contract_mode=skill_packet.contract_mode if skill_packet is not None else None,
                    context_card_ids=skill_packet.context_card_ids() if skill_packet is not None else [],
                    context_packet_characters=skill_packet.context_packet_characters(final_retry=is_final_retry) if skill_packet is not None else len(str(payload)),
                    repair_mode=skill_packet.repair_mode if skill_packet is not None else None,
                ),
            )
        except GatewayCapabilityError as exc:
            author_error = AuthorGatewayError(
                code={
                    "gateway_text_provider_failed": "llm_provider_failed",
                    "gateway_text_invalid_response": "llm_invalid_response",
                    "gateway_text_invalid_json": "llm_invalid_json",
                }.get(exc.code, exc.code),
                message=exc.message,
                status_code=exc.status_code,
            )
            last_error = author_error
            if author_error.code not in retryable_codes or index == len(prompts) - 1:
                raise author_error from exc
            continue
        except AuthorGatewayError as exc:
            last_error = exc
            if exc.code not in retryable_codes or index == len(prompts) - 1:
                raise
            continue

        try:
            value = parse_value(result.payload)
        except Exception as exc:  # noqa: BLE001
            last_error = AuthorGatewayError(
                code="llm_schema_invalid",
                message=str(exc),
                status_code=502,
            )
            attempt_prev = result.response_id or attempt_prev
            if index == len(prompts) - 1:
                raise last_error from exc
            continue

        return StructuredResponse(
            value=value,
            response_id=result.response_id or attempt_prev,
        )

    if isinstance(last_error, AuthorGatewayError):
        raise last_error
    raise AuthorGatewayError(
        code="llm_schema_invalid",
        message=str(last_error or f"{operation_name} failed"),
        status_code=502,
    )
