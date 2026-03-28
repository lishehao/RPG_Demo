from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rpg_backend.content_language import is_chinese_language, localized_text
from rpg_backend.roster.contracts import CharacterRosterEntry, CharacterRosterSourceEntry


class _RosterTemplateCarrier(Protocol):
    character_id: str
    name_en: str
    name_zh: str
    role_hint_en: str
    role_hint_zh: str
    public_summary_en: str
    public_summary_zh: str
    pressure_signature_seed_en: str
    pressure_signature_seed_zh: str
    gender_lock: str | None
    personality_core_en: str | None
    personality_core_zh: str | None
    experience_anchor_en: str | None
    experience_anchor_zh: str | None
    identity_lock_notes_en: str | None
    identity_lock_notes_zh: str | None


@dataclass(frozen=True)
class ResolvedCharacterTemplateProfile:
    personality_core: str
    experience_anchor: str
    identity_lock_notes: str
    gender_lock: str | None
    explicit: bool


def template_profile_complete(entry: _RosterTemplateCarrier) -> bool:
    return all(
        (
            str(entry.personality_core_en or "").strip(),
            str(entry.personality_core_zh or "").strip(),
            str(entry.experience_anchor_en or "").strip(),
            str(entry.experience_anchor_zh or "").strip(),
            str(entry.identity_lock_notes_en or "").strip(),
            str(entry.identity_lock_notes_zh or "").strip(),
            str(entry.gender_lock or "").strip(),
        )
    )


def resolved_template_profile(entry: _RosterTemplateCarrier, language: str) -> ResolvedCharacterTemplateProfile:
    zh = is_chinese_language(language)
    personality_core = (
        str(entry.personality_core_zh if zh else entry.personality_core_en or "").strip()
        or str(entry.pressure_signature_seed_zh if zh else entry.pressure_signature_seed_en).strip()
    )
    experience_anchor = (
        str(entry.experience_anchor_zh if zh else entry.experience_anchor_en or "").strip()
        or str(entry.public_summary_zh if zh else entry.public_summary_en).strip()
    )
    identity_lock_notes = (
        str(entry.identity_lock_notes_zh if zh else entry.identity_lock_notes_en or "").strip()
        or localized_text(
            language,
            en=(
                f"This is {entry.name_en}. Keep the same person, the same face, and the same public identity. "
                f"Do not rename them, do not replace them, and do not turn them into a different person than the {entry.role_hint_en} already established here."
            ),
            zh=(
                f"这就是{entry.name_zh}。必须保持同一个人、同一张脸、同一公共身份。"
                f"不得改名，不得换人，也不得把他/她改写成与当前既定{entry.role_hint_zh}不同的另一个人。"
            ),
        )
    )
    return ResolvedCharacterTemplateProfile(
        personality_core=personality_core,
        experience_anchor=experience_anchor,
        identity_lock_notes=identity_lock_notes,
        gender_lock=str(entry.gender_lock or "").strip() or None,
        explicit=template_profile_complete(entry),
    )


def default_template_profile_fields(entry: CharacterRosterSourceEntry) -> dict[str, str]:
    return {
        "personality_core_en": str(entry.pressure_signature_seed_en).strip(),
        "personality_core_zh": str(entry.pressure_signature_seed_zh).strip(),
        "experience_anchor_en": str(entry.public_summary_en).strip(),
        "experience_anchor_zh": str(entry.public_summary_zh).strip(),
        "identity_lock_notes_en": (
            f"This is {entry.name_en}. Keep the same person, the same face, and the same public identity. "
            f"Do not rename them or rewrite them into someone other than the established {entry.role_hint_en}."
        ),
        "identity_lock_notes_zh": (
            f"这就是{entry.name_zh}。必须保持同一个人、同一张脸、同一公共身份，"
            f"不得改名，也不得把他/她改写成不同于既定{entry.role_hint_zh}的另一个人。"
        ),
    }
