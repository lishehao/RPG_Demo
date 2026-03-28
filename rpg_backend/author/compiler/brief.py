from __future__ import annotations

import re

from rpg_backend.content_language import normalize_content_language
from rpg_backend.author.contracts import FocusedBrief
from rpg_backend.author.normalize import normalize_whitespace, trim_ellipsis

_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def _extract_tail_after_about(text: str) -> str:
    match = re.search(r"\babout\b\s+(.*)", text, flags=re.IGNORECASE)
    if match:
        return normalize_whitespace(match.group(1))
    return text


def _split_at_first_marker(text: str, markers: tuple[str, ...]) -> tuple[str, str | None]:
    lowered = text.casefold()
    found: tuple[int, str] | None = None
    for marker in markers:
        index = lowered.find(f" {marker} ")
        if index >= 0 and (found is None or index < found[0]):
            found = (index, marker)
    if found is None:
        return text, None
    index, marker = found
    head = text[:index].strip(" ,.;:")
    tail = text[index + len(marker) + 2 :].strip(" ,.;:")
    return head, f"{marker} {tail}" if tail else marker


def _extract_location_phrase(text: str) -> str:
    tokens = re.findall(r"[a-zA-Z0-9-]+", text)
    if not tokens:
        return normalize_whitespace(text)
    location_nouns = {
        "city",
        "kingdom",
        "archive",
        "archives",
        "district",
        "station",
        "temple",
        "capital",
        "monastery",
        "harbor",
        "fortress",
        "republic",
    }
    stop_tokens = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "young",
        "mediator",
        "keeper",
        "envoy",
        "engineer",
        "detective",
        "pilot",
        "keeping",
        "preventing",
        "saving",
        "holding",
        "during",
        "while",
        "without",
        "before",
        "after",
    }
    for index, token in enumerate(tokens):
        lowered = token.casefold()
        if lowered not in location_nouns:
            continue
        start = index
        while start > 0 and tokens[start - 1].casefold() not in stop_tokens:
            start -= 1
        end = index
        while end + 1 < len(tokens) and tokens[end + 1].casefold() in location_nouns:
            end += 1
        phrase = " ".join(tokens[start : end + 1]).strip()
        temporal = re.search(r"\b(during|amid|under)\b\s+([^,.!?;]+)", text, flags=re.IGNORECASE)
        if temporal:
            phrase = f"{phrase} {temporal.group(1)} {temporal.group(2).strip()}"
        return normalize_whitespace(phrase)
    return normalize_whitespace(text)


def _extract_tone_signal(text: str) -> str:
    if _CJK_PATTERN.search(text):
        lowered = text.casefold()
        if any(term in lowered for term in ("程序", "档案", "记录", "账本", "证据", "舱单", "核实", "查清", "审计")):
            return "档案程序悬疑"
        if any(term in lowered for term in ("停电", "恐慌", "暴动", "宵禁", "疏散")):
            return "高压失序悬疑"
        if any(term in lowered for term in ("港口", "码头", "检疫", "配给", "物资", "桥", "洪水")):
            return "封线政治惊悚"
        return "城市压力剧"
    match = re.search(
        r"^(?:a|an|the)?\s*((?:hopeful|tense|grim|warm|political|civic|mystery|thriller|fantasy|science[- ]fiction|romantic|adventure|melancholic|optimistic|paranoid|urgent)(?:\s+(?:hopeful|tense|grim|warm|political|civic|mystery|thriller|fantasy|science[- ]fiction|romantic|adventure|melancholic|optimistic|paranoid|urgent))*)\s+about\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return normalize_whitespace(match.group(1))
    fallback_terms: list[str] = []
    for term in ("hopeful", "political", "civic", "mystery", "thriller", "fantasy", "urgent", "tense"):
        if term in text.casefold():
            fallback_terms.append(term)
    if fallback_terms:
        return " ".join(dict.fromkeys(fallback_terms))
    lowered = text.casefold()
    if any(term in lowered for term in ("archive", "record", "ledger", "audit", "vote", "council", "blackout")):
        return "Tense procedural thriller"
    if any(term in lowered for term in ("quarantine", "ration", "bridge", "flood", "harbor", "port", "convoy")):
        return "Tense bureaucratic thriller"
    return "Tense civic drama"


def _zh_setting_signal(text: str) -> str:
    lowered = text.casefold()
    if any(term in lowered for term in ("港口", "码头", "舱单", "检疫", "航运")):
        return "一座被检疫政治与物资压力撕扯的港口城市"
    if any(term in lowered for term in ("档案", "记录", "账本", "证词", "证据")):
        return "一座依赖公开记录维持秩序的城市"
    if any(term in lowered for term in ("停电", "黑暗", "宵禁")):
        return "一座在停电与公共不确定中运转的城市"
    if any(term in lowered for term in ("桥", "洪水", "配给", "街区")):
        return "一座被桥梁与配给压力撕扯的城市"
    return "一座公共秩序正在承压的城市"


def _zh_story_kernel(text: str) -> str:
    normalized = normalize_whitespace(text).strip("。.!? ")
    if not normalized:
        return "一名公共事务负责人必须在局势失控前采取行动"
    for marker in ("必须", "需要", "得", "要", "试图", "想要", "发现", "查清", "核实", "证明", "阻止", "恢复", "保护", "维持"):
        index = normalized.find(marker)
        if index > 0:
            return trim_ellipsis(normalized[: index + len(marker)] + normalized[index + len(marker):], 220)
    return trim_ellipsis(normalized, 220)


def _zh_core_conflict(text: str, *, setting_signal: str) -> str:
    lowered = text.casefold()
    if any(term in lowered for term in ("港口", "码头", "舱单", "检疫", "救济")):
        return "在救济投票前查清被篡改的舱单，阻止派系借检疫与物资分配操纵结果"
    if any(term in lowered for term in ("档案", "记录", "账本", "核验", "投票", "表决", "委员会")):
        return "在表决结果被宣布成定局前核清被改写的记录，把事实重新拉回公开程序"
    if any(term in lowered for term in ("档案", "记录", "账本", "证词", "证据")):
        return "在公众叙事彻底硬化前核实被篡改的记录，把事实重新拉回公开视野"
    if any(term in lowered for term in ("停电", "恐慌", "宵禁")):
        return "在停电与恐慌把城市彻底推向失序前，守住程序与公共信任"
    if any(term in lowered for term in ("桥", "洪水", "配给", "街区")):
        return "在配给与基础设施压力撕裂街区之前，查清被操纵的数据并稳住共同程序"
    return f"在{setting_signal}中守住公共正当性，避免危机演变成公开裂痕"


def _focus_brief_zh(raw_brief: str) -> FocusedBrief:
    normalized = normalize_whitespace(raw_brief)
    setting_signal = _zh_setting_signal(normalized)
    return FocusedBrief(
        language="zh",
        story_kernel=_zh_story_kernel(normalized),
        setting_signal=trim_ellipsis(setting_signal, 220),
        core_conflict=trim_ellipsis(_zh_core_conflict(normalized, setting_signal=setting_signal), 220),
        tone_signal=trim_ellipsis(_extract_tone_signal(normalized), 120),
        hard_constraints=[],
        forbidden_tones=["graphic cruelty", "sadistic evil"],
    )


def _split_protagonist_and_mission(text: str) -> tuple[str, str]:
    normalized = normalize_whitespace(text)
    if not normalized:
        return "", ""
    match = re.match(
        r"^((?:a|an|the)\s+(?:[a-z0-9-]+\s+){0,4}(?:mediator|envoy|engineer|captain|detective|pilot|archivist|keeper|priest|councilor|guard|messenger|scholar|mayor|agent|negotiator))\s+(.+)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if match:
        return normalize_whitespace(match.group(1)), normalize_whitespace(match.group(2))
    return "", normalized


def _to_infinitive(phrase: str) -> str:
    normalized = normalize_whitespace(phrase)
    if not normalized:
        return normalized
    parts = normalized.split(" ", 1)
    first = parts[0].casefold()
    rest = parts[1] if len(parts) > 1 else ""
    rewrites = {
        "keeping": "keep",
        "holding": "hold",
        "saving": "save",
        "protecting": "protect",
        "stabilizing": "stabilize",
        "preventing": "prevent",
        "brokering": "broker",
        "guiding": "guide",
        "maintaining": "maintain",
        "preserving": "preserve",
        "uncovering": "uncover",
        "exposing": "expose",
        "stopping": "stop",
    }
    rewritten = rewrites.get(first, parts[0])
    return normalize_whitespace(f"{rewritten} {rest}".strip())


def _extract_constraint_marker_phrase(text: str) -> tuple[str | None, str | None]:
    for marker in ("without", "during", "while", "before", "after", "amid"):
        match = re.search(rf"\b{marker}\b\s+([^,.!?;]+)", text, flags=re.IGNORECASE)
        if match:
            return marker, normalize_whitespace(match.group(1))
    return None, None


def _infer_pressure_phrase(*, setting_signal: str, constraint_marker: str | None, constraint_tail: str | None) -> str:
    if constraint_tail:
        if constraint_marker in {"during", "while", "amid"}:
            return normalize_whitespace(f"while {constraint_tail} strains civic order")
        if constraint_marker == "without":
            return normalize_whitespace(f"without {constraint_tail}")
        if constraint_marker == "before":
            return normalize_whitespace(f"before {constraint_tail} triggers open fracture")
        if constraint_marker == "after":
            return normalize_whitespace(f"after {constraint_tail} reshapes the balance of power")

    lowered = setting_signal.casefold()
    fragments: list[str] = []
    if "election" in lowered or "vote" in lowered:
        fragments.append("civic legitimacy starts to fracture")
    if "blackout" in lowered:
        fragments.append("coordination breaks down")
    if "flood" in lowered or "storm" in lowered:
        fragments.append("system pressure keeps rising")
    if "archive" in lowered or "record" in lowered:
        fragments.append("collective memory is at risk")
    if not fragments:
        return "while public order grows more fragile"
    if len(fragments) == 1:
        return f"while {fragments[0]}"
    return f"while {fragments[0]} and {fragments[1]}"


def _focus_brief_en(raw_brief: str, *, language: str = "en") -> FocusedBrief:
    normalized = normalize_whitespace(raw_brief)
    tail = _extract_tail_after_about(normalized)
    kernel_head, _kernel_tail = _split_at_first_marker(
        tail,
        ("during", "while", "without", "before", "after", "amid"),
    )
    story_kernel = normalize_whitespace(kernel_head or tail)
    setting_signal = _extract_location_phrase(tail if tail else normalized)
    _protagonist, mission_phrase = _split_protagonist_and_mission(story_kernel)
    mission_core = _to_infinitive(mission_phrase or story_kernel)
    constraint_marker, constraint_tail = _extract_constraint_marker_phrase(normalized)
    pressure_phrase = _infer_pressure_phrase(
        setting_signal=setting_signal,
        constraint_marker=constraint_marker,
        constraint_tail=constraint_tail,
    )
    core_conflict = normalize_whitespace(f"{mission_core} {pressure_phrase}".strip())
    tone_signal = _extract_tone_signal(normalized)
    hard_constraints = []
    for marker in ("without", "before", "while", "during", "after"):
        match = re.search(rf"\b{marker}\b\s+([^,.!?;]+)", normalized, flags=re.IGNORECASE)
        if match:
            hard_constraints.append(normalize_whitespace(f"{marker} {match.group(1)}"))
    unique_constraints = []
    for item in hard_constraints:
        if item and item.casefold() not in {existing.casefold() for existing in unique_constraints}:
            unique_constraints.append(item)
    return FocusedBrief(
        language=normalize_content_language(language),
        story_kernel=trim_ellipsis(story_kernel, 220),
        setting_signal=trim_ellipsis(setting_signal, 220),
        core_conflict=trim_ellipsis(core_conflict, 220),
        tone_signal=trim_ellipsis(tone_signal, 120),
        hard_constraints=[trim_ellipsis(item, 160) for item in unique_constraints[:4]],
        forbidden_tones=["graphic cruelty", "sadistic evil"],
    )


def focus_brief(raw_brief: str, *, language: str = "en") -> FocusedBrief:
    normalized_language = normalize_content_language(language)
    if normalized_language == "zh" and _CJK_PATTERN.search(raw_brief):
        return _focus_brief_zh(raw_brief)
    return _focus_brief_en(raw_brief, language=normalized_language)
