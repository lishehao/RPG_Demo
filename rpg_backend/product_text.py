from __future__ import annotations

import re

from rpg_backend.author.contracts import FocusedBrief
from rpg_backend.author.compiler.story import sanitize_story_sentence
from rpg_backend.author.normalize import normalize_whitespace, trim_ellipsis


_REPEATED_LOCATIVE_INTRO = re.compile(
    r"(?P<intro>\bIn\s+[^,]{2,120},)\s+(?P=intro)\s+",
    flags=re.IGNORECASE,
)

_REPEATED_CONDITIONAL_CLAUSE = re.compile(
    r"(?P<clause>\b(?:When|If|While|After|Before|As)\b[^.]{12,160}?)\s+"
    r"(?P<link>while|before|after|as)\s+"
    r"(?P=clause)\s+(?P=link)\s+",
    flags=re.IGNORECASE,
)

_SEED_ECHO_PREFIX = re.compile(
    r"\b(?:When|If|While|After|Before|As)\b[^.]{24,180}\b(?:while|before|after|as)\s+"
    r"\b(?:When|If|While|After|Before|As)\b",
    flags=re.IGNORECASE,
)

_ROLE_DISCOVERY_PATTERN = re.compile(
    r"^(?P<subject>(?:a|an|the)\s+(?:[a-z0-9-]+\s+){0,5}"
    r"(?:mediator|envoy|engineer|inspector|archivist|keeper|priest|councilor|guard|messenger|scholar|mayor|agent|negotiator|"
    r"auditor|superintendent|liaison|ombudsman|clerk|marshal|officer|delegate|steward))\s+"
    r"(?P<verb>discovers|finds|uncovers|learns|realizes|spots|proves|reveals|exposes)\s+"
    r"(?P<rest>.+)$",
    flags=re.IGNORECASE,
)


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = {token for token in re.findall(r"[a-z0-9']+", left.casefold()) if len(token) >= 3}
    right_tokens = {token for token in re.findall(r"[a-z0-9']+", right.casefold()) if len(token) >= 3}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(right_tokens), 1)


def _duplicate_window_ratio(text: str, *, window_size: int = 4) -> float:
    tokens = [token for token in re.findall(r"[a-z0-9']+", text.casefold()) if token]
    if len(tokens) < window_size * 2:
        return 0.0
    windows = [" ".join(tokens[index : index + window_size]) for index in range(len(tokens) - window_size + 1)]
    if not windows:
        return 0.0
    duplicate_count = len(windows) - len(set(windows))
    return duplicate_count / len(windows)


def _dedupe_sentences(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", normalize_whitespace(text))
    ordered: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        cleaned = sentence.strip()
        if not cleaned:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", cleaned.casefold()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return " ".join(ordered).strip()


def _collapse_repeated_clauses(text: str) -> str:
    updated = normalize_whitespace(text)
    previous = None
    while updated != previous:
        previous = updated
        updated = _REPEATED_LOCATIVE_INTRO.sub(r"\g<intro> ", updated)
        updated = _REPEATED_CONDITIONAL_CLAUSE.sub(r"\g<clause> \g<link> ", updated)
    return updated.strip()


def _looks_noisy_product_copy(text: str, *, echo_reference: str | None = None) -> bool:
    normalized = normalize_whitespace(text)
    if not normalized:
        return True
    lowered = normalized.casefold()
    if re.search(r"^in [^,]{2,120},\s+(when|if|while|after|before|as)\b", lowered):
        return True
    if _SEED_ECHO_PREFIX.search(normalized):
        return True
    if _duplicate_window_ratio(normalized) >= 0.18:
        return True
    if echo_reference and _token_overlap_ratio(normalized, echo_reference) >= 0.82 and " must " not in f" {lowered} ":
        return True
    return False


def sanitize_product_story_sentence(
    value: str,
    *,
    fallback: str,
    limit: int,
    echo_reference: str | None = None,
) -> str:
    cleaned_value = _dedupe_sentences(_collapse_repeated_clauses(value))
    cleaned_fallback = _dedupe_sentences(_collapse_repeated_clauses(fallback))
    sanitized = sanitize_story_sentence(
        cleaned_value,
        fallback=cleaned_fallback or fallback,
        limit=limit,
    )
    if _looks_noisy_product_copy(sanitized, echo_reference=echo_reference):
        fallback_sanitized = sanitize_story_sentence(
            cleaned_fallback or fallback,
            fallback=cleaned_fallback or fallback,
            limit=limit,
        )
        if fallback_sanitized:
            return fallback_sanitized
    return sanitized


def sanitize_product_one_liner(*, premise: str, title: str, limit: int = 220) -> str:
    first_sentence = re.split(r"(?<=[.!?])\s+", normalize_whitespace(premise), maxsplit=1)[0].strip()
    if not first_sentence:
        return trim_ellipsis(title, limit)
    return trim_ellipsis(first_sentence.rstrip(".!?"), limit)


def sanitize_product_identity_summary(value: str, *, limit: int = 320) -> str:
    cleaned = _dedupe_sentences(_collapse_repeated_clauses(value))
    return trim_ellipsis(cleaned, limit)


def sanitize_product_opening_narration(value: str, *, limit: int = 4000) -> str:
    cleaned = _dedupe_sentences(_collapse_repeated_clauses(value))
    return trim_ellipsis(cleaned, limit)


def _product_setting_frame(*, primary_theme: str, prompt_seed: str, focused_brief: FocusedBrief) -> str:
    lowered = f"{prompt_seed} {focused_brief.setting_signal} {focused_brief.core_conflict}".casefold()
    if primary_theme == "logistics_quarantine_crisis":
        if any(keyword in lowered for keyword in ("bridge", "flood", "ration", "ward", "district", "convoy", "infrastructure")):
            return "a city under ration strain and infrastructure pressure"
        if any(keyword in lowered for keyword in ("harbor", "port", "quarantine", "dock", "shipping")):
            return "a harbor city strained by quarantine politics and supply fear"
        return "a city where scarcity and emergency logistics keep turning relief into leverage"
    if primary_theme == "truth_record_crisis":
        return "a city of archives where civic order depends on trusted records"
    if primary_theme == "public_order_crisis":
        return "a city under blackout strain and escalating public panic"
    if primary_theme == "legitimacy_crisis":
        return "a civic system where emergency authority is starting to outrun public legitimacy"
    return normalize_whitespace(focused_brief.setting_signal)


def _product_mandate(*, primary_theme: str, prompt_seed: str, focused_brief: FocusedBrief) -> str:
    normalized_kernel = normalize_whitespace(focused_brief.story_kernel or prompt_seed)
    match = _ROLE_DISCOVERY_PATTERN.match(normalized_kernel)
    if match:
        subject = normalize_whitespace(match.group("subject"))
        verb = match.group("verb").casefold()
        rest = normalize_whitespace(match.group("rest")).rstrip(".")
        if rest:
            if verb in {"discovers", "finds", "uncovers", "learns", "realizes", "spots"}:
                connector = "must prove" if rest.casefold().startswith("that ") else "must prove that"
            elif verb == "proves":
                connector = "must prove"
            else:
                connector = "must force into the open" if rest.casefold().startswith("that ") else "must force into the open that"
            return trim_ellipsis(f"{subject} {connector} {rest}".strip(), 220)
    lowered = normalized_kernel.casefold()
    if "archivist" in lowered or "clerk" in lowered or "auditor" in lowered:
        return "an archivist must verify one binding public record before the official story hardens"
    if "superintendent" in lowered or "engineer" in lowered:
        return "a superintendent must expose the staged logistics failure before emergency rule hardens into habit"
    if "inspector" in lowered or "officer" in lowered:
        return "an inspector must expose the hidden breach before emergency authority becomes private leverage"
    if "mediator" in lowered or "liaison" in lowered or "ombudsman" in lowered:
        return "a mediator must hold rival institutions in one room long enough to force a binding answer"
    if re.match(r"^(when|if|while|after|before|as)\b", lowered):
        if primary_theme == "truth_record_crisis":
            return "an archivist must verify one binding public record before the official story hardens"
        if primary_theme == "legitimacy_crisis":
            return "a civic mediator must force one binding public answer before emergency authority outruns consent"
        if primary_theme == "logistics_quarantine_crisis":
            return "a civic lead must keep relief moving before scarcity turns into leverage"
        if primary_theme == "public_order_crisis":
            return "a civic lead must keep public order from hardening into panic rule"
        return "a civic lead must force a binding answer before delay turns into fracture"
    return trim_ellipsis(normalized_kernel, 220)


def _product_opposition_force(*, primary_theme: str, prompt_seed: str, focused_brief: FocusedBrief) -> str:
    lowered = f"{prompt_seed} {focused_brief.setting_signal} {focused_brief.core_conflict}".casefold()
    if primary_theme == "logistics_quarantine_crisis":
        if any(keyword in lowered for keyword in ("bridge", "flood", "ration", "ward", "district", "convoy", "infrastructure")):
            return "scarcity politics and emergency command keep turning logistics into political leverage"
        return "trade pressure and quarantine politics keep turning relief into factional leverage"
    if primary_theme == "truth_record_crisis":
        return "forged records and procedural denial keep reshaping the public story"
    if primary_theme == "public_order_crisis":
        return "panic, rumor, and emergency messaging keep pushing the city toward open disorder"
    if primary_theme == "legitimacy_crisis":
        return "institutional panic and mandate politics turn every delay into leverage"
    return "public pressure keeps turning delay into civic fracture"


def build_product_premise_fallback(
    *,
    primary_theme: str,
    focused_brief: FocusedBrief,
    prompt_seed: str = "",
    limit: int = 320,
) -> str:
    return trim_ellipsis(
        (
            f"In {_product_setting_frame(primary_theme=primary_theme, prompt_seed=prompt_seed, focused_brief=focused_brief)}, "
            f"{_product_mandate(primary_theme=primary_theme, prompt_seed=prompt_seed, focused_brief=focused_brief)} "
            f"while {_product_opposition_force(primary_theme=primary_theme, prompt_seed=prompt_seed, focused_brief=focused_brief)}."
        ),
        limit,
    )
