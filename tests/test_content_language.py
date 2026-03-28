from __future__ import annotations

from rpg_backend.content_language import output_language_instruction, prompt_role_instruction, resolve_content_prompt_profile


def test_output_language_instruction_for_zh_prefers_natural_chinese() -> None:
    instruction = output_language_instruction("zh")

    assert "Simplified Chinese" in instruction
    assert "natural Chinese phrasing" in instruction
    assert "literal translation" in instruction


def test_prompt_role_instruction_for_zh_includes_role_and_native_style_rules() -> None:
    instruction = prompt_role_instruction(
        "zh",
        en_role="a senior editor",
        zh_role="资深中文叙事编辑",
    )

    assert "资深中文叙事编辑" in instruction
    assert "中文母语用户" in instruction
    assert "不要逐字翻译英文句式" in instruction


def test_prompt_role_instruction_for_en_stays_compact() -> None:
    instruction = prompt_role_instruction(
        "en",
        en_role="a senior editor",
        zh_role="资深中文叙事编辑",
    )

    assert instruction == "Adopt the role of a senior editor."


def test_prompt_role_instruction_can_disable_role_conditioning() -> None:
    instruction = prompt_role_instruction(
        "zh",
        en_role="a senior editor",
        zh_role="资深中文叙事编辑",
        profile="plain",
    )

    assert instruction == ""


def test_resolve_content_prompt_profile_defaults_to_role_conditioned() -> None:
    assert resolve_content_prompt_profile("role_conditioned") == "role_conditioned"
    assert resolve_content_prompt_profile("plain") == "plain"
    assert resolve_content_prompt_profile("unexpected") == "role_conditioned"
