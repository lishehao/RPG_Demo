from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Literal

from rpg_backend.content_language import (
    ContentPromptProfile,
    output_language_instruction,
    prompt_role_instruction,
    resolve_content_prompt_profile,
)

SkillContractMode = Literal[
    "strict_json_schema",
    "json_object",
    "narration_prose",
    "compact_contract",
]
SkillPromptVariant = Literal["normal", "repair", "final_contract"]


@dataclass(frozen=True)
class ContextCard:
    card_id: str
    content: Any
    priority: int = 0

    def as_packet_entry(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "content": self.content,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class GenerationSkillPacket:
    skill_id: str
    skill_version: str
    capability: str
    contract_mode: SkillContractMode
    role_style: ContentPromptProfile
    required_output_contract: str
    context_cards: tuple[ContextCard, ...]
    task_brief: str
    snapshot_id: str | None = None
    context_hash: str | None = None
    required_invariants: dict[str, Any] = field(default_factory=dict)
    repair_mode: str = "none"
    repair_note: str | None = None
    final_contract_note: str | None = None
    extra_payload: dict[str, Any] = field(default_factory=dict)
    final_retry_extra_payload: dict[str, Any] | None = None

    def ordered_context_cards(self) -> list[ContextCard]:
        return sorted(self.context_cards, key=lambda item: (item.priority, item.card_id))

    def context_card_ids(self) -> list[str]:
        return [item.card_id for item in self.ordered_context_cards()]

    def context_payload(self, *, final_retry: bool = False) -> dict[str, Any]:
        payload = {
            "skill_context": {
                "skill_id": self.skill_id,
                "skill_version": self.skill_version,
                "capability": self.capability,
                "contract_mode": self.contract_mode,
                "role_style": self.role_style,
                "required_output_contract": self.required_output_contract,
                "snapshot_id": self.snapshot_id,
                "context_hash": self.context_hash,
                "required_invariants": self.required_invariants,
                "repair_mode": self.repair_mode,
                "context_cards": [item.as_packet_entry() for item in self.ordered_context_cards()],
            }
        }
        payload.update(self.extra_payload)
        if final_retry and self.final_retry_extra_payload is not None:
            payload.update(self.final_retry_extra_payload)
        return payload

    def context_packet_characters(self, *, final_retry: bool = False) -> int:
        return len(json.dumps(self.context_payload(final_retry=final_retry), ensure_ascii=False, sort_keys=True))

    def build_system_prompt(self, *, variant: SkillPromptVariant) -> str:
        parts = [
            self.task_brief.strip(),
            f"Output contract: {self.required_output_contract}",
            "Use the provided skill_context.context_cards by card_id.",
            "Do not ignore required cards or invent missing card data.",
        ]
        if variant == "repair":
            parts.append(
                (self.repair_note or "Repair the prior invalid output while keeping the same contract.").strip()
            )
        elif variant == "final_contract":
            parts.append(
                (
                    self.final_contract_note
                    or "Return only output that matches the requested contract. No markdown, labels, or prose outside the contract."
                ).strip()
            )
        return " ".join(part for part in parts if part)


def build_role_style_context(
    *,
    language: str | None,
    en_role: str,
    zh_role: str,
    profile: str | None = None,
    include_ids_note: bool = True,
) -> tuple[ContentPromptProfile, str]:
    resolved_profile = resolve_content_prompt_profile(profile)
    parts = []
    role_instruction = prompt_role_instruction(
        language,
        en_role=en_role,
        zh_role=zh_role,
        profile=resolved_profile,
    )
    if role_instruction:
        parts.append(role_instruction)
    parts.append(output_language_instruction(language, include_ids_note=include_ids_note))
    return resolved_profile, " ".join(parts)
