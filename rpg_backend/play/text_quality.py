from __future__ import annotations

import re

from rpg_backend.content_language import is_chinese_language
from rpg_backend.responses_transport import strip_model_meta_wrapper_text

_PLAY_META_LABEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bSCENE_REACTION\b\s*[:：]\s*", flags=re.IGNORECASE),
    re.compile(r"\bAXIS_PAYOFF\b\s*[:：]\s*", flags=re.IGNORECASE),
    re.compile(r"\bSTANCE_PAYOFF\b\s*[:：]\s*", flags=re.IGNORECASE),
    re.compile(r"\bIMMEDIATE_CONSEQUENCE\b\s*[:：]\s*", flags=re.IGNORECASE),
    re.compile(r"\bCLOSING_PRESSURE\b\s*[:：]\s*", flags=re.IGNORECASE),
    re.compile(r"\bRequested output\b\s*[:：]\s*", flags=re.IGNORECASE),
    re.compile(r"\bHere is the JSON requested\b\s*[:：]\s*", flags=re.IGNORECASE),
    re.compile(r"\bHere is the requested JSON\b\s*[:：]\s*", flags=re.IGNORECASE),
    re.compile(r"\bHere is the requested output\b\s*[:：]\s*", flags=re.IGNORECASE),
)

_PLAY_META_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*requested output\b", flags=re.IGNORECASE),
    re.compile(r"^\s*here is the json requested\b", flags=re.IGNORECASE),
    re.compile(r"^\s*here is the requested json\b", flags=re.IGNORECASE),
    re.compile(r"^\s*here is the requested output\b", flags=re.IGNORECASE),
    re.compile(r"^\s*```(?:json)?\s*$", flags=re.IGNORECASE),
    re.compile(r'^\s*"?(?:narration|input_text|input text)"?\s*:\s*', flags=re.IGNORECASE),
)

_ZH_META_TEMPLATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^\s*You keep the scene moving(?:\s+with\s+[^.!?。！？]+)?\s+as the room reacts in real time[.!?。！？]?\s*$",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^\s*The pressure visibly shifts around what you just forced into the open[.!?。！？]?\s*$",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^\s*A relationship shifted inside the coalition[.!?。！？]?\s*$",
        flags=re.IGNORECASE,
    ),
)

_JSONISH_PATTERN = re.compile(r"^[{\[]\s*['\"][A-Za-z0-9_]+['\"]\s*:")
_UPPERCASE_FIELD_PATTERN = re.compile(r"^[A-Z_]+\s*[:：]?$")


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def english_word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'-]*", text))


def cjk_visible_char_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def narration_sentence_count(text: str) -> int:
    return len(_split_narration_chunks(text))


def contains_play_meta_wrapper_text(text: str | None) -> bool:
    lowered = str(text or "").casefold()
    return any(
        marker in lowered
        for marker in (
            "here is the json requested",
            "here is the requested json",
            "here is the requested output",
            "requested output",
            "```json",
            "```",
            "json:",
            "scene_reaction",
            "axis_payoff",
            "stance_payoff",
            "immediate_consequence",
            "closing_pressure",
        )
    )


def has_second_person_reference(text: str | None, language: str | None) -> bool:
    cleaned = str(text or "").strip()
    if not cleaned:
        return False
    if is_chinese_language(language):
        return bool(re.search(r"[你您](?:们|的)?", cleaned))
    return bool(re.search(r"\b(?:you|your)\b", cleaned, flags=re.IGNORECASE))


def has_language_contamination(text: str | None, language: str | None) -> bool:
    cleaned = strip_model_meta_wrapper_text(str(text or "")).strip()
    if not cleaned:
        return False
    chunks = _split_narration_chunks(cleaned)
    if is_chinese_language(language):
        if not any(contains_cjk(chunk) for chunk in chunks):
            return False
        if any(
            not contains_cjk(chunk)
            and english_word_count(chunk) >= 4
            and not _is_meta_chunk(chunk, language=language)
            for chunk in chunks
        ):
            return True
        return english_word_count(cleaned) >= 8
    return contains_cjk(cleaned) and english_word_count(cleaned) >= 4


def visible_story_length(text: str | None, language: str | None) -> int:
    cleaned = str(text or "").strip()
    if is_chinese_language(language):
        return cjk_visible_char_count(cleaned)
    return len(cleaned)


def sanitize_persisted_narration(text: str | None, *, language: str | None) -> str:
    cleaned = strip_model_meta_wrapper_text(str(text or "")).replace("\r", "\n").strip()
    if not cleaned:
        return ""
    for pattern in _PLAY_META_LABEL_PATTERNS:
        cleaned = pattern.sub("\n", cleaned)
    chunks = _split_narration_chunks(cleaned)
    has_any_cjk = any(contains_cjk(chunk) for chunk in chunks)
    filtered: list[str] = []
    for chunk in chunks:
        normalized = chunk.strip().strip('"').strip()
        if not normalized:
            continue
        if _is_meta_chunk(normalized, language=language):
            continue
        if _JSONISH_PATTERN.search(normalized):
            continue
        if is_chinese_language(language) and has_any_cjk and not contains_cjk(normalized) and english_word_count(normalized) >= 4:
            continue
        filtered.append(normalized)
    sanitized = " ".join(filtered)
    if is_chinese_language(language):
        for pattern in _ZH_META_TEMPLATE_PATTERNS:
            sanitized = pattern.sub("", sanitized)
    return _normalize_narration_punctuation(sanitized, language=language)


def _split_narration_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    for line in re.split(r"\n+", text):
        stripped = line.strip()
        if not stripped:
            continue
        matches = re.findall(r"[^。！？.!?\n]+[。！？.!?]?", stripped)
        if matches:
            chunks.extend(match.strip() for match in matches if match.strip())
        else:
            chunks.append(stripped)
    return chunks


def _is_meta_chunk(text: str, *, language: str | None) -> bool:
    normalized = text.strip()
    if not normalized:
        return True
    if _UPPERCASE_FIELD_PATTERN.match(normalized):
        return True
    if any(pattern.search(normalized) for pattern in _PLAY_META_LINE_PATTERNS):
        return True
    if is_chinese_language(language) and any(pattern.match(normalized) for pattern in _ZH_META_TEMPLATE_PATTERNS):
        return True
    return False


def _normalize_narration_punctuation(text: str, *, language: str | None) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([。！？.!?,，、；：])", r"\1", cleaned)
    cleaned = re.sub(r"([。！？])(?:[.!?。！？])+", r"\1", cleaned)
    cleaned = re.sub(r"([.!?])(?:[.!?])+", r"\1", cleaned)
    cleaned = re.sub(r"[“”]{2,}", '"', cleaned)
    if is_chinese_language(language):
        cleaned = re.sub(r"([。！？])\s+", r"\1", cleaned)
    return cleaned.strip().strip('"').strip()
