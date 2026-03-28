from __future__ import annotations

import re

from rpg_backend.author.contracts import FocusedBrief, StoryFrameDraft

_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
_GENERIC_ZH_TITLES = {
    "公议协约",
    "城市协约",
    "公共协约",
    "紧急议会",
    "最终结算",
}


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().split())


FATAL_STORY_FRAME_REASONS = {
    "premise_bad_terminal_punctuation",
    "premise_missing_finite_action",
    "stakes_bad_terminal_punctuation",
}


def is_fatal_story_frame_reason(reason: str) -> bool:
    return reason in FATAL_STORY_FRAME_REASONS


def story_frame_should_repair(reasons: list[str]) -> bool:
    return any(is_fatal_story_frame_reason(reason) for reason in reasons) or len(reasons) >= 2


def _has_bad_terminal_punctuation(value: str) -> bool:
    return value.endswith(".,") or value.endswith(",.") or value.endswith("..")


def _has_repeated_locative_intro(value: str) -> bool:
    normalized = _normalize(value)
    return bool(re.search(r"\bIn\s+\w[\w\s'-]*\s+in\s+", normalized, flags=re.IGNORECASE))


def _has_finite_action(value: str) -> bool:
    normalized = _normalize(value).casefold()
    finite_markers = (
        " must ",
        " keeps ",
        " keep ",
        " coordinates ",
        " coordinate ",
        " forces ",
        " force ",
        " turns ",
        " turn ",
        " while ",
    )
    return any(marker in f" {normalized} " for marker in finite_markers)


def story_frame_quality_reasons(
    story_frame: StoryFrameDraft,
    focused_brief: FocusedBrief,
) -> list[str]:
    reasons: list[str] = []
    if focused_brief.language == "zh":
        normalized_premise = _normalize(story_frame.premise)
        if len(re.findall(r"[A-Za-z]{4,}", normalized_premise)) >= 2:
            reasons.append("premise_mixed_language_noise")
        kernel_prefix = _normalize(focused_brief.story_kernel)[:20]
        if kernel_prefix and normalized_premise.count(kernel_prefix) >= 2:
            reasons.append("premise_repeats_story_kernel_multiple_times")
    if _normalize(story_frame.premise).casefold() == _normalize(focused_brief.story_kernel).casefold():
        reasons.append("premise_echoes_story_kernel")
    if story_frame.stakes.casefold().startswith("if the player fails"):
        reasons.append("stakes_uses_player_fail_template")
    if any(_normalize(rule).casefold() == _normalize(focused_brief.setting_signal).casefold() for rule in story_frame.world_rules):
        reasons.append("world_rule_repeats_setting_signal")
    truth_texts = {_normalize(item.text).casefold() for item in story_frame.truths}
    if truth_texts <= {
        _normalize(focused_brief.core_conflict).casefold(),
        _normalize(focused_brief.setting_signal).casefold(),
    }:
        reasons.append("truths_only_restate_brief")
    if _normalize(story_frame.title).casefold() in {"untitled crisis", _normalize(focused_brief.story_kernel).casefold()}:
        reasons.append("title_generic_or_brief_echo")
    if focused_brief.language == "zh" and _normalize(story_frame.title) in _GENERIC_ZH_TITLES:
        reasons.append("title_generic_or_brief_echo")
    if _has_bad_terminal_punctuation(story_frame.premise):
        reasons.append("premise_bad_terminal_punctuation")
    if _has_repeated_locative_intro(story_frame.premise):
        reasons.append("premise_repeated_locative_intro")
    if not _has_finite_action(story_frame.premise):
        reasons.append("premise_missing_finite_action")
    if _has_bad_terminal_punctuation(story_frame.stakes):
        reasons.append("stakes_bad_terminal_punctuation")
    title_tokens = {token for token in re.findall(r"[a-z0-9]+", story_frame.title.casefold()) if len(token) > 3}
    premise_tokens = {token for token in re.findall(r"[a-z0-9]+", story_frame.premise.casefold()) if len(token) > 3}
    generic_title_tokens = {"city", "crisis", "night", "day", "story"}
    if title_tokens and premise_tokens and not (title_tokens & premise_tokens) and title_tokens <= generic_title_tokens:
        reasons.append("title_premise_semantic_mismatch")
    return reasons
