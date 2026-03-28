from __future__ import annotations

import re

from pypinyin import Style, lazy_pinyin

_CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")
_TOKEN_PATTERN = re.compile(r"[a-z0-9']+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_search_text(value: str | None) -> str:
    normalized = _WHITESPACE_PATTERN.sub(" ", str(value or "").strip())
    return normalized.strip()


def contains_cjk(value: str | None) -> bool:
    return bool(_CJK_PATTERN.search(str(value or "")))


def build_pinyin_document(value: str | None) -> str:
    normalized = normalize_search_text(value)
    if not normalized or not contains_cjk(normalized):
        return ""
    syllables = [
        item.casefold()
        for item in lazy_pinyin(
            normalized,
            style=Style.NORMAL,
            errors=lambda _item: [],
        )
        if item and _TOKEN_PATTERN.fullmatch(item.casefold())
    ]
    if not syllables:
        return ""
    initials = [item[0] for item in syllables if item]
    variants = (
        " ".join(syllables),
        "".join(syllables),
        " ".join(initials),
        "".join(initials),
    )
    unique_variants: list[str] = []
    seen: set[str] = set()
    for item in variants:
        compact = normalize_search_text(item)
        if not compact or compact in seen:
            continue
        seen.add(compact)
        unique_variants.append(compact)
    return " ".join(unique_variants)
