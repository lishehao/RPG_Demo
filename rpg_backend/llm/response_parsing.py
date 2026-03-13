from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedResponseUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ParsedResponsePayload:
    response_id: str | None
    output_text: str
    reasoning_summary: str | None
    usage: ParsedResponseUsage
    raw_payload: dict[str, Any]



def _as_dict(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return dict(response)
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {}



def _extract_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = payload.get("output")
    if not isinstance(output, list):
        return ""

    fragments: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "")
        if item_type not in {"message", "output_text", "reasoning"}:
            continue

        content = item.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    fragments.append(text)
        elif isinstance(content, str) and content.strip():
            fragments.append(content)

        text = item.get("text")
        if isinstance(text, str) and text.strip():
            fragments.append(text)

    return "\n".join(text.strip() for text in fragments if isinstance(text, str) and text.strip()).strip()



def _extract_reasoning_summary(payload: dict[str, Any]) -> str | None:
    output = payload.get("output")
    if not isinstance(output, list):
        return None

    summary_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "") != "reasoning":
            continue

        summary = item.get("summary")
        if isinstance(summary, str) and summary.strip():
            summary_parts.append(summary.strip())
            continue

        if isinstance(summary, list):
            for part in summary:
                if isinstance(part, str) and part.strip():
                    summary_parts.append(part.strip())
                elif isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        summary_parts.append(text.strip())

    if not summary_parts:
        return None
    return "\n".join(summary_parts)



def _extract_usage(payload: dict[str, Any]) -> ParsedResponseUsage:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return ParsedResponseUsage()

    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")

    return ParsedResponseUsage(
        input_tokens=int(input_tokens) if isinstance(input_tokens, int) else None,
        output_tokens=int(output_tokens) if isinstance(output_tokens, int) else None,
        total_tokens=int(total_tokens) if isinstance(total_tokens, int) else None,
    )



def parse_responses_payload(response: Any) -> ParsedResponsePayload:
    payload = _as_dict(response)
    response_id = payload.get("id")
    output_text = _extract_output_text(payload)
    reasoning_summary = _extract_reasoning_summary(payload)
    usage = _extract_usage(payload)

    return ParsedResponsePayload(
        response_id=str(response_id) if isinstance(response_id, str) else None,
        output_text=str(output_text or ""),
        reasoning_summary=reasoning_summary,
        usage=usage,
        raw_payload=payload,
    )
