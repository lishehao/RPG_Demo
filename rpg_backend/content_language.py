from __future__ import annotations

from typing import Literal

from rpg_backend.config import get_settings

ContentLanguage = Literal["en", "zh"]
ContentPromptProfile = Literal["plain", "role_conditioned"]


def normalize_content_language(value: str | None) -> ContentLanguage:
    return "zh" if (value or "").strip().casefold() == "zh" else "en"


def is_chinese_language(language: str | None) -> bool:
    return normalize_content_language(language) == "zh"


def localized_text(language: str | None, *, en: str, zh: str) -> str:
    return zh if is_chinese_language(language) else en


def resolve_content_prompt_profile(profile: str | None = None) -> ContentPromptProfile:
    normalized = (profile or get_settings().content_prompt_profile or "role_conditioned").strip().casefold()
    if normalized == "plain":
        return "plain"
    return "role_conditioned"


def output_language_instruction(
    language: str | None,
    *,
    include_ids_note: bool = True,
) -> str:
    if is_chinese_language(language):
        instruction = (
            "All user-visible prose must be written in Simplified Chinese for native readers. "
            "Prefer natural Chinese phrasing over literal translation."
        )
        if include_ids_note:
            instruction += " Keep ids, enum-like values, and structural keys in ASCII."
        return instruction
    return "All user-visible prose must be written in English."


def prompt_role_instruction(
    language: str | None,
    *,
    en_role: str,
    zh_role: str,
    profile: str | None = None,
) -> str:
    if resolve_content_prompt_profile(profile) != "role_conditioned":
        return ""
    if is_chinese_language(language):
        return (
            f"你现在是一名{zh_role}。"
            "面向中文母语用户写作：优先使用自然、凝练、能直接进入场景的简体中文，"
            "不要逐字翻译英文句式，不要堆叠抽象名词，也不要反复套用同一模板句。"
        )
    return f"Adopt the role of {en_role}."
