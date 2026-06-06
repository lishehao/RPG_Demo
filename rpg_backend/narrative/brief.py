from __future__ import annotations

import re
from typing import Any

from rpg_backend.narrative.contracts import (
    CastPlan,
    CastPlanEntity,
    ConstraintDisposition,
    StoryBrief,
    StoryBriefAdvisorResponse,
    StoryBriefConsistencyCheck,
    StoryBriefConsistencyViolation,
    StoryBriefPlanItem,
    StoryBriefRevisionAction,
    TemplateLanguage,
    TensionProfile,
)


_PROFILE_KERNELS: dict[TensionProfile, tuple[str, str, str]] = {
    "high_drama": (
        "High drama",
        "secret -> leverage -> confrontation -> relationship shift -> ending",
        "Leverage card",
    ),
    "cozy_mystery": (
        "Cozy mystery",
        "clues -> suspicion -> gentle stakes -> reveal -> repaired trust",
        "Clue card",
    ),
    "comedy": (
        "Comedy",
        "misunderstanding -> embarrassment -> escalation -> reversal -> callback/payoff",
        "Callback card",
    ),
    "fantasy_sci_fi": (
        "Fantasy / sci-fi",
        "world rule -> faction pressure -> artifact complication -> reveal -> rule payoff",
        "Artifact card",
    ),
    "family_social": (
        "Family/social",
        "old wound -> misread intent -> loyalty test -> reconciliation/rupture",
        "Loyalty card",
    ),
}

_PROFILE_KEYWORDS: tuple[tuple[TensionProfile, tuple[str, ...]], ...] = (
    (
        "comedy",
        (
            "talent show",
            "prank",
        ),
    ),
    (
        "cozy_mystery",
        (
            "cozy",
            "mystery",
            "missing",
            "detective",
            "noir",
            "clue",
            "museum",
            "locked room",
            "lost ring",
            "cupcake",
            "bake sale",
        ),
    ),
    (
        "fantasy_sci_fi",
        (
            "fantasy",
            "sci-fi",
            "sci fi",
            "mars",
            "colony",
            "spell",
            "magic",
            "wizard",
            "dragon",
            "artifact",
            "robot",
            "ai core",
            "spaceship",
        ),
    ),
    (
        "family_social",
        (
            "family",
            "dinner",
            "wedding",
            "sibling",
            "parent",
            "mother",
            "father",
            "inheritance",
            "loyalty",
            "reconcile",
        ),
    ),
)

_EXPLICIT_SMALL_CAST_MARKERS = (
    "two-person",
    "two person",
    "two people",
    "two characters",
    "just two",
    "only two",
    "small cast",
)

_LOW_CONFLICT_MARKERS = (
    "low conflict",
    "quiet",
    "gentle",
)

_ENTITY_SPLIT_RE = re.compile(r"\s*(?:,|;|/|\||\+|\band\b|\bvs\.?\b|\bversus\b|\bagainst\b)\s*", re.I)
_STOPWORDS = {
    "a",
    "an",
    "the",
    "one",
    "public",
    "secret",
    "time",
    "pressure",
    "story",
    "scene",
    "premise",
}

_EXPLICIT_COMEDY_MARKERS = (
    "comedy",
    "comic",
    "funny",
    "sitcom",
    "absurd",
    "awkward",
)

_SETTING_PREFIX_RE = re.compile(r"^(?:at|in|on|during)\b", re.I)
_LIST_MARKER_RE = re.compile(
    r"\b(?:involves?|involving|features?|featuring|including|includes?|with|where|departments?|factions?|cast)\b[: ]+",
    re.I,
)
_ENTITY_TRAILING_RE = re.compile(
    r"\b(?:argue|argues|fight|fights|investigate|investigates|perform|performs|claim|claims|need|needs|"
    r"handle|handles|represent|represents|should|try|tries|find|finds|without|before|after|during|over|because|while|when|where|around|at midnight)\b.*$",
    re.I,
)
_ENTITY_LEADING_NOISE_RE = re.compile(
    r"^(?:ten|\d+)\s+(?:groups?|departments?|factions?|parties?|entities?)\s*[-:]\s*",
    re.I,
)
_PLANNER_NOTE_LINE_RE = re.compile(r"^\s*(?:planner note|revision guidance)\s*:", re.I | re.M)
_NON_ENTITY_EXACT = {
    "at",
    "in",
    "on",
    "keep",
    "no blackmail",
    "blackmail",
    "misunderstandings",
    "misunderstanding",
    "callback joke",
    "callback",
    "embarrassment",
    "embarrassed parents",
    "revenge",
    "hacking",
    "security footage",
    "board",
    "board vote",
    "talent show",
    "mars",
    "minutes",
    "no violence",
    "no betrayal",
    "no public pressure",
    "no mystery",
    "no conflict",
    "no villains",
    "betrayal",
    "public pressure",
    "or public pressure",
    "conflict",
    "tense but playful",
    "fantastical",
    "playful",
    "funny",
    "cozy",
    "move",
    "add",
    "lower",
    "use",
    "include",
    "make",
    "ensure",
    "represent",
    "planner",
    "without",
    "villains",
    "villain",
    "conflict",
    "betrayal",
    "pressure",
    "tense",
    "playful",
    "fantastical",
    "funny",
    "style",
}
_NON_ENTITY_WORDS = {
    "tone",
    "kernel",
    "joke",
    "misunderstanding",
    "misunderstandings",
    "blackmail",
    "callback",
    "embarrassment",
    "embarrassed",
    "proof",
    "constraint",
    "stakes",
    "talent",
    "show",
    "colony",
    "broadcast",
    "eclipse",
    "library",
    "vote",
    "each",
    "group",
    "groups",
    "concern",
    "concerns",
    "move",
    "extra",
    "extras",
    "add",
    "lower",
    "include",
    "ensure",
    "represent",
    "planner",
}
_EVENT_CONSTRAINT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\btalent show\b", "talent show"),
    (r"\bfinal broadcast\b", "final broadcast"),
    (r"\bboard vote\b", "board vote"),
    (r"\bmidnight\b", "midnight deadline"),
    (r"\beclipse\b", "eclipse"),
    (r"\bbake sale\b", "bake sale"),
    (r"\bcursed index\b", "cursed index"),
    (r"\boxygen supply\b", "oxygen supply"),
    (r"\bpublic reveal\b", "public reveal"),
    (r"\bmissing cupcake\b", "missing cupcake"),
)
_NEGATED_CONSTRAINT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bno blackmail\b", "no blackmail"),
    (r"\bno betrayal\b", "no betrayal"),
    (r"\bno violence\b", "no violence"),
)
_WORLD_SETTING_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bmars colony\b", "Mars colony"),
    (r"\bmars\b", "Mars setting"),
    (r"\bfantasy library\b", "fantasy library"),
    (r"\bpreschool bake sale\b", "preschool bake sale"),
    (r"\blibrary\b", "library setting"),
    (r"\bcolony\b", "colony setting"),
)
_HIGH_STAKES_PATTERNS = (
    "oxygen supply",
    "oxygen tank",
    "backup oxygen",
    "oxygen heist",
    "life-or-death",
    "life or death",
    "heist",
    "scapegoat",
    "permanent position",
    "career-ending",
    "career ending",
    "criminal",
    "security footage",
    "hack",
    "hacking",
    "murder",
    "kill",
    "deadly",
    "revenge",
    "fatal",
)
_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_FORBIDDEN_TERMS_BY_CONSTRAINT: dict[str, tuple[str, ...]] = {
    "no blackmail": ("blackmail", "leverage threat", "extort", "extortion"),
    "no betrayal": ("betray", "betrayal", "backstab", "double-cross", "double cross"),
    "no violence": ("violence", "violent", "murder", "kill", "blood", "gun", "knife", "assault"),
}
_LOWER_STAKES_OPENING_ESCALATION_PATTERNS = (
    *_HIGH_STAKES_PATTERNS,
    "governor arrives",
    "governor deadline",
)
_PROFILE_TONE_TABOO_TERMS: dict[TensionProfile, tuple[str, ...]] = {
    "comedy": (
        "accuse",
        "accuses",
        "fight",
        "start a fight",
        "scapegoat",
        "takes the fall",
        "take the fall",
        "blackmail",
        "betrayal",
        "revenge",
        "hacking",
        "security footage",
        "permanent position",
        "permanent job",
        "heist",
    ),
    "cozy_mystery": (
        "accuse",
        "accuses",
        "fight",
        "start a fight",
        "confront",
        "scapegoat",
        "takes the fall",
        "take the fall",
        "blackmail",
        "betrayal",
        "revenge",
        "hacking",
        "security footage",
        "permanent position",
        "permanent job",
        "heist",
    ),
    "fantasy_sci_fi": (
        "the scapegoat",
        "scapegoat",
        "takes the fall",
        "take the fall",
        "blackmail",
        "security footage",
        "hacking",
        "permanent position",
        "permanent job",
        "expulsion-level",
        "expulsion level",
    ),
    "family_social": (),
    "high_drama": (),
}
_EMPHASIS_ENTITY_PATTERNS = (
    re.compile(
        r"\b(?:represent|focus on|include|preserve|must include|should include|keep)\b\s+([^.!?;]+)",
        re.I,
    ),
    re.compile(
        r"\b(?:central|important)\s+(?:entities?|factions?|groups?|cast)\s*[:\-]\s*([^.!?;]+)",
        re.I,
    ),
)


def build_story_brief(
    *,
    seed: str,
    language: TemplateLanguage = "en",
    desired_tension_profile: TensionProfile | None = None,
) -> StoryBriefAdvisorResponse:
    """Plan a supported story shape before spending opening-generation budget.

    This is intentionally deterministic. It gives users transparent guidance
    and gives tests a stable contract; an LLM-backed brief agent can later
    fill the same `StoryBrief` schema through the existing gateway.
    """
    del language
    clean_seed = " ".join(seed.strip().split())
    profile = desired_tension_profile or infer_tension_profile(clean_seed)
    title, kernel, intervention = _PROFILE_KERNELS[profile]
    mentioned_entities = _extract_entities(clean_seed)
    cast_plan = _build_cast_plan(clean_seed, mentioned_entities, profile)
    warnings: list[str] = []
    revision_suggestions: list[str] = []
    preserved = _preserved_constraints(clean_seed, profile)
    constraints = _constraint_items(clean_seed)
    time_event_anchors = _time_event_anchor_items(clean_seed)
    tone_constraints = _tone_constraint_items(clean_seed, profile)
    world_setting_pressure = _world_setting_items(clean_seed)
    compressed: list[str] = []
    dropped: list[str] = []
    softened: list[str] = []

    if len(mentioned_entities) > 5:
        compressed.append(
            "Only 3-5 entities should be active in a turn; extra entities become secondary/background pressure."
        )
    if len(mentioned_entities) > 10:
        dropped.append("Entities beyond the first 10 are outside this runtime pass and should be merged.")

    explicit_small_cast = has_explicit_small_cast_mismatch(clean_seed)
    if explicit_small_cast:
        warnings.append("This reads like a two-person or no-villain premise; the current runtime needs 3+ active parties.")
        revision_suggestions.append(
            "Add a third party with a concrete stake: witness, rival, family member, faction, or owner of the contested object."
        )
    if not _has_pressure_signal(clean_seed):
        warnings.append("The premise does not clearly include time pressure or a public conflict yet.")
        revision_suggestions.append("Add a deadline, audience, vote, ceremony, missing object, or public reveal window.")

    if profile == "comedy":
        softened.append("Treat embarrassment, timing, and callback payoff as the tension engine instead of default blackmail.")
    if profile == "cozy_mystery":
        softened.append("Keep stakes inspectable and clue-driven; avoid forcing every reveal into betrayal melodrama.")
    if "no blackmail" in clean_seed.lower():
        softened.append("Avoid blackmail escalation; preserve the no-blackmail constraint.")
    if profile in {"comedy", "cozy_mystery"} and _has_high_stakes_conflict(clean_seed):
        warnings.append(
            "This premise asks for a lower-stakes profile but includes life-or-death or revenge-scale stakes."
        )
        revision_suggestions.append(
            "Lower the stakes to embarrassment, missing props, social pressure, or clue payoff if you want comedy/cozy fidelity."
        )
        softened.append("Keep the profile lower-stakes; do not escalate into life-or-death betrayal unless the user revises the brief.")

    fit_status = "fit"
    if explicit_small_cast:
        fit_status = "not_fit"
    elif warnings:
        fit_status = "needs_revision"

    dispositions = _constraint_dispositions(preserved, compressed, dropped, softened)
    revision_actions = _revision_actions(warnings, profile)
    fit_rationale = _fit_rationale(fit_status, profile)
    brief = StoryBrief(
        original_seed=clean_seed,
        premise_summary=_premise_summary(
            clean_seed,
            cast_plan=cast_plan,
            profile=profile,
            time_event_anchors=time_event_anchors,
            world_setting_pressure=world_setting_pressure,
        ),
        genre_tone=title,
        tension_profile=profile,
        story_kernel=kernel,
        intervention_card_label=intervention,
        cast_plan=cast_plan,
        constraints=constraints,
        time_event_anchors=time_event_anchors,
        tone_constraints=tone_constraints,
        world_setting_pressure=world_setting_pressure,
        preserved_constraints=preserved,
        compressed_constraints=compressed,
        dropped_constraints=dropped,
        softened_constraints=softened,
        constraint_dispositions=dispositions,
        warnings=warnings,
        revision_suggestions=revision_suggestions,
        revision_actions=revision_actions,
        adaptation_note=(
            "Beta planner draft: this card shows how Tiny Stories will adapt the premise before generation."
        ),
        runtime_fit_status=fit_status,
        runtime_fit_rationale=fit_rationale,
    )
    can_generate = fit_status != "not_fit"
    next_step = (
        "Revise the premise before generation."
        if not can_generate
        else "Review the brief, then generate the story from this plan."
    )
    return StoryBriefAdvisorResponse(brief=brief, can_generate=can_generate, next_step=next_step)


def check_story_brief_opening_consistency(
    *,
    brief: StoryBrief,
    opening: Any,
    language: TemplateLanguage,
) -> StoryBriefConsistencyCheck:
    """Conservatively compare a confirmed brief against generated opening output."""
    searchable = _opening_search_text(opening)
    lowered = searchable.lower()
    violations: list[StoryBriefConsistencyViolation] = []

    if language == "en" and _CJK_RE.search(searchable):
        violations.append(
            StoryBriefConsistencyViolation(
                code="english_cjk_artifact",
                severity="fail",
                rationale="English opening contains visible CJK characters.",
                evidence=_cjk_evidence(searchable),
            )
        )

    for item in [*brief.constraints, *brief.tone_constraints]:
        constraint_key = item.label.lower()
        for forbidden_key, forbidden_terms in _FORBIDDEN_TERMS_BY_CONSTRAINT.items():
            if forbidden_key not in constraint_key:
                continue
            found = [term for term in forbidden_terms if term in lowered]
            if found:
                violations.append(
                    StoryBriefConsistencyViolation(
                        code=f"forbidden_{forbidden_key.replace(' ', '_')}_contradiction",
                        severity="fail",
                        rationale=f"Opening contradicts preserved constraint `{item.label}`.",
                        evidence=found[:4],
                    )
                )

    if brief.tension_profile in {"comedy", "cozy_mystery"} and not _brief_preserves_high_stakes(brief):
        found_high_stakes = [term for term in _LOWER_STAKES_OPENING_ESCALATION_PATTERNS if term in lowered]
        if found_high_stakes:
            violations.append(
                StoryBriefConsistencyViolation(
                    code="lower_stakes_profile_escalated",
                    severity="fail",
                    rationale="Opening appears to escalate a comedy/cozy brief into high-stakes danger.",
                    evidence=found_high_stakes[:4],
                )
            )

    tone_taboo = _profile_tone_taboo_matches(brief, lowered)
    if tone_taboo:
        violations.append(
            StoryBriefConsistencyViolation(
                code="profile_tone_taboo",
                severity="fail",
                rationale="Opening uses high-drama vocabulary that conflicts with the selected tension profile.",
                evidence=tone_taboo[:6],
            )
        )

    missing_emphasized = _missing_emphasized_entities(brief, lowered)
    if missing_emphasized:
        violations.append(
            StoryBriefConsistencyViolation(
                code="brief_emphasized_entity_absent",
                severity="fail",
                rationale="Entities explicitly requested in the prompt/brief are not visible in the generated opening.",
                evidence=missing_emphasized[:5],
            )
        )

    missing_primary = _missing_primary_entities(brief, lowered)
    if missing_primary:
        violations.append(
            StoryBriefConsistencyViolation(
                code="brief_primary_entity_absent",
                severity="warn",
                rationale="Some planned active entities are not visible in the generated opening text/cast.",
                evidence=missing_primary[:5],
            )
        )

    missing_anchors = _missing_event_anchors(brief, lowered)
    if missing_anchors:
        violations.append(
            StoryBriefConsistencyViolation(
                code="brief_event_anchor_absent",
                severity="warn",
                rationale="Some event/time anchors from the brief are not visible in the generated opening.",
                evidence=missing_anchors[:5],
            )
        )

    if any(v.severity == "fail" for v in violations):
        status = "fail"
    elif any(v.severity == "warn" for v in violations):
        status = "warn"
    else:
        status = "pass"
    should_retry = any(v.code in {"english_cjk_artifact"} or v.severity == "fail" for v in violations)
    summary = (
        "Opening matches the reviewed brief at a conservative contract level."
        if status == "pass"
        else "Opening has brief-consistency warnings or repairable contract issues."
    )
    return StoryBriefConsistencyCheck(status=status, violations=violations, summary=summary, should_retry=should_retry)


def infer_tension_profile(seed: str) -> TensionProfile:
    lowered = seed.lower()
    if any(marker in lowered for marker in _EXPLICIT_COMEDY_MARKERS):
        return "comedy"
    for profile, keywords in _PROFILE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return profile
    return "high_drama"


def has_explicit_small_cast_mismatch(seed: str) -> bool:
    lowered = seed.lower()
    has_small_cast = any(marker in lowered for marker in _EXPLICIT_SMALL_CAST_MARKERS)
    has_no_villain = "no villain" in lowered or "no villains" in lowered
    has_low_conflict = any(marker in lowered for marker in _LOW_CONFLICT_MARKERS)
    return has_small_cast or (has_no_villain and has_low_conflict)


def _extract_entities(seed: str) -> list[str]:
    entity_seed = _strip_planner_note_lines(seed)
    candidates: list[str] = []
    parts = _entity_source_parts(entity_seed)
    if ":" in entity_seed:
        parts.insert(0, entity_seed.split(":", 1)[1])
    for part in parts:
        for raw in _ENTITY_SPLIT_RE.split(part):
            candidate = _clean_entity(raw)
            if candidate:
                candidates.append(candidate)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _canonical_entity_key(candidate)
        if key in seen:
            continue
        if any(_is_sub_entity(key, existing) for existing in seen):
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _entity_source_parts(seed: str) -> list[str]:
    seed = _strip_entity_exclusion_segments(seed)
    parts: list[str] = []
    for match in _LIST_MARKER_RE.finditer(seed):
        parts.append(seed[match.end() :])
    # Keep the full seed as a fallback, but cleanup aggressively filters
    # setting openers and clauses that are not cast/faction names.
    parts.append(seed)
    return parts


def _clean_entity(raw: str) -> str:
    text = re.sub(r"\([^)]*\)", "", raw).strip(" .!?\"'“”‘’")
    if ":" in text:
        prefix, suffix = text.rsplit(":", 1)
        if re.search(r"\b(?:story|premise|scene|prompt|no villains?)\b", prefix, re.I):
            text = suffix
    text = re.sub(r"^\s*no\s+villains?\s*:\s*", "", text, flags=re.I)
    text = _LIST_MARKER_RE.sub("", text)
    text = _ENTITY_LEADING_NOISE_RE.sub("", text)
    text = re.sub(r"\b(the|a|an|one|with|featuring|including|departments?|factions?|cast)\b", "", text, flags=re.I)
    text = re.sub(r"^\s*(?:or|and)\s+", "", text, flags=re.I)
    text = _ENTITY_TRAILING_RE.sub("", text)
    text = " ".join(text.split())
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith("no "):
        return ""
    if re.match(r"^just\s+(?:a\s+|an\s+|the\s+)?(?:lost\s+)?wedding\s+ring\b", lowered):
        return ""
    if lowered in _NON_ENTITY_EXACT:
        return ""
    if re.match(r"^(?:comedy|cozy|mystery|fantasy|sci-fi|sci fi)\s+on\b", lowered):
        return ""
    if _SETTING_PREFIX_RE.match(lowered):
        return ""
    words = text.split()
    if len(words) > 5:
        return ""
    if words and words[0].lower() in {
        "at",
        "in",
        "on",
        "during",
        "before",
        "after",
        "keep",
        "move",
        "add",
        "lower",
        "use",
        "include",
        "make",
        "ensure",
        "represent",
        "planner",
    }:
        return ""
    if all(word.lower() in _STOPWORDS for word in words):
        return ""
    if any(word.lower().strip(".,:;!?") in _NON_ENTITY_WORDS for word in words):
        return ""
    if len(text) < 2 or len(text) > 80:
        return ""
    return text[:80]


def _build_cast_plan(seed: str, entities: list[str], profile: TensionProfile) -> CastPlan:
    emphasized_keys = _emphasized_entity_keys(seed, entities)
    planned = _select_planned_entities(entities, emphasized_keys)
    if len(planned) < 3 and not has_explicit_small_cast_mismatch(seed):
        planned = _dedupe_preserving_order([*planned, *_fallback_entities(seed, profile)])[:10]
    primary = [
        _entity(
            name,
            idx,
            role="Primary active party",
            rationale=(
                "Protected because the prompt explicitly emphasized this entity; kept in the 3-5 entity focus window."
                if _canonical_entity_key(name) in emphasized_keys
                else "Kept in the 3-5 entity focus window."
            ),
        )
        for idx, name in enumerate(planned[:5])
    ]
    secondary = [
        _entity(
            name,
            idx + 5,
            role="Secondary/background pressure",
            rationale=(
                "Protected because the prompt explicitly emphasized this entity; kept as background within the 10-entity cap."
                if _canonical_entity_key(name) in emphasized_keys
                else "Kept as context, not active every turn."
            ),
        )
        for idx, name in enumerate(planned[5:10])
    ]
    selected_keys = {_canonical_entity_key(name) for name in planned}
    omitted_names = [name for name in entities if _canonical_entity_key(name) not in selected_keys]
    has_cap_pressure = len(entities) > 10
    omitted = [
        _entity(
            name,
            idx + 10,
            role="Omitted/merge candidate",
            rationale=(
                "Explicitly requested but still beyond the current cap; reduce required entities or move it into a constraint."
                if _canonical_entity_key(name) in emphasized_keys and has_cap_pressure
                else "Beyond the 10-entity planning cap."
                if has_cap_pressure
                else "Kept as prompt context outside the first focus window; revise if it must be represented."
            ),
        )
        for idx, name in enumerate(omitted_names[:5])
    ]
    return CastPlan(
        input_entity_count=len(entities),
        primary_active_entities=primary,
        secondary_background_entities=secondary,
        omitted_entities=omitted,
        active_focus_window="Director should keep 3-5 entities readable per turn; others remain background pressure.",
    )


def _select_planned_entities(entities: list[str], emphasized_keys: set[str]) -> list[str]:
    planned = entities[:10]
    planned_keys = {_canonical_entity_key(name) for name in planned}
    for entity in entities[10:]:
        key = _canonical_entity_key(entity)
        if key in planned_keys or key not in emphasized_keys:
            continue
        replace_idx = None
        for idx in range(len(planned) - 1, -1, -1):
            planned_key = _canonical_entity_key(planned[idx])
            if planned_key in emphasized_keys:
                continue
            replace_idx = idx
            if idx >= 5:
                break
        if replace_idx is None:
            continue
        planned_keys.discard(_canonical_entity_key(planned[replace_idx]))
        planned[replace_idx] = entity
        planned_keys.add(key)
    return planned


def _entity(name: str, idx: int, *, role: str, rationale: str) -> CastPlanEntity:
    return CastPlanEntity(
        entity_id=_slugify(name) or f"entity_{idx + 1}",
        display_name=name[:80],
        kind=_entity_kind(name),
        role=role,
        rationale=rationale,
    )


def _entity_kind(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("department", "council", "faction", "team", "sponsors")):
        return "faction"
    if any(token in lowered for token in ("ring", "cupcake", "artifact", "contract", "recording", "clue")):
        return "object"
    return "character"


def _fallback_entities(seed: str, profile: TensionProfile) -> list[str]:
    lowered = seed.lower()
    if "wedding" in lowered:
        return ["player", "partner", "family elder", "unexpected witness"]
    if "family" in lowered or "dinner" in lowered:
        return ["host", "estranged relative", "loyal witness", "outside claimant"]
    if profile == "cozy_mystery":
        return ["player", "keeper of the clue", "gentle witness", "outside witness"]
    if profile == "comedy":
        return ["player", "mix-up witness", "embarrassed helper", "deadline host"]
    return ["player", "rival", "witness", "deadline holder"]


def _preserved_constraints(seed: str, profile: TensionProfile) -> list[str]:
    constraints = ["core premise"]
    lowered = seed.lower()
    has_wedding_ring = bool(re.search(r"\bwedding\s+ring\b", lowered))
    if profile != "high_drama":
        constraints.append(f"{profile.replace('_', ' ')} tone")
    for pattern, label in _EVENT_CONSTRAINT_PATTERNS:
        if re.search(pattern, lowered):
            constraints.append(label)
    for pattern, label in _NEGATED_CONSTRAINT_PATTERNS:
        if re.search(pattern, lowered):
            constraints.append(label)
    for token in ("missing", "secret", "vote", "deadline", "artifact"):
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            constraints.append(token)
    if has_wedding_ring:
        constraints.append("wedding ring")
    else:
        if re.search(r"\bwedding\b", lowered):
            constraints.append("wedding")
        if re.search(r"\bring\b", lowered):
            constraints.append("ring")
    constraints = _dedupe_preserving_order(constraints)
    return constraints[:8]


def _constraint_dispositions(
    preserved: list[str],
    compressed: list[str],
    dropped: list[str],
    softened: list[str],
) -> list[ConstraintDisposition]:
    rows: list[ConstraintDisposition] = []
    for label in preserved:
        rows.append(ConstraintDisposition(label=label, disposition="preserved", rationale="Kept as a core brief constraint."))
    for label in compressed:
        rows.append(ConstraintDisposition(label=label, disposition="compressed", rationale="Compressed to keep turns readable."))
    for label in dropped:
        rows.append(ConstraintDisposition(label=label, disposition="dropped", rationale="Outside the current runtime cap."))
    for label in softened:
        rows.append(ConstraintDisposition(label=label, disposition="softened", rationale="Adjusted to fit the selected tension profile."))
    return rows[:16]


def _constraint_items(seed: str) -> list[StoryBriefPlanItem]:
    items = [StoryBriefPlanItem(label="core premise", rationale="Preserved as the main premise to adapt.")]
    if re.search(r"\bno villains?\b", seed, re.I):
        items.append(
            StoryBriefPlanItem(
                label="no villains",
                rationale="Preserved as an exclusion; it should not become active cast.",
            )
        )
    if re.search(r"\b(?:without\b[^.!?;]*\bpublic pressure|no\s+public pressure)\b", seed, re.I):
        items.append(
            StoryBriefPlanItem(
                label="avoid public pressure",
                rationale="Preserved as a low-pressure constraint; it should not become active cast.",
            )
        )
    for pattern, label in _NEGATED_CONSTRAINT_PATTERNS:
        if re.search(pattern, seed, re.I):
            items.append(
                StoryBriefPlanItem(
                    label=label,
                    rationale="Preserved as a constraint; it should not become active cast.",
                )
            )
    for pattern, label in (
        (r"\bmissing cupcake\b", "missing cupcake"),
        (r"\bcursed index\b", "cursed index"),
        (r"\bleaked contract\b", "leaked contract"),
        (r"\bcolony oxygen supply\b", "colony oxygen supply"),
        (r"\bwedding\s+ring\b", "wedding ring"),
        (r"\bring\b", "ring"),
    ):
        if label == "ring" and re.search(r"\bwedding\s+ring\b", seed, re.I):
            continue
        if re.search(pattern, seed, re.I):
            items.append(StoryBriefPlanItem(label=label, rationale="Preserved as a contested object or premise constraint."))
    return _dedupe_plan_items(items)[:10]


def _time_event_anchor_items(seed: str) -> list[StoryBriefPlanItem]:
    items: list[StoryBriefPlanItem] = []
    for pattern, label in _EVENT_CONSTRAINT_PATTERNS:
        if re.search(pattern, seed, re.I):
            items.append(
                StoryBriefPlanItem(
                    label=label,
                    rationale="Used as event/time pressure, not active cast.",
                )
            )
    if re.search(r"\bminutes?\s+before\b", seed, re.I):
        items.append(StoryBriefPlanItem(label="minutes-before deadline", rationale="Used as a time-pressure anchor."))
    return _dedupe_plan_items(items)[:10]


def _tone_constraint_items(seed: str, profile: TensionProfile) -> list[StoryBriefPlanItem]:
    items = [
        StoryBriefPlanItem(
            label=f"{profile.replace('_', ' ')} profile",
            rationale="Guides the story kernel and payoff style.",
        )
    ]
    if profile in {"comedy", "cozy_mystery"}:
        items.append(
            StoryBriefPlanItem(
                label="lower-stakes tension",
                rationale="Prefer social pressure, clues, props, callbacks, and gentle reveals over blackmail or violence.",
            )
        )
    if re.search(r"\bno blackmail\b", seed, re.I):
        items.append(StoryBriefPlanItem(label="avoid blackmail", rationale="Keep this as a tone constraint."))
    if re.search(r"\bno betrayal\b", seed, re.I):
        items.append(StoryBriefPlanItem(label="avoid betrayal", rationale="Keep this as a tone constraint."))
    if re.search(r"\bno violence\b", seed, re.I):
        items.append(StoryBriefPlanItem(label="avoid violence", rationale="Keep this as a tone constraint."))
    if re.search(r"\btense but playful\b", seed, re.I):
        items.append(StoryBriefPlanItem(label="tense but playful", rationale="Keep this as tone guidance, not active cast."))
    if re.search(r"\bkeep it\b[^.!?;]*\b(?:funny|cozy|playful|fantastical)\b", seed, re.I):
        items.append(StoryBriefPlanItem(label="tone/style guidance", rationale="Treat `keep it` wording as tone guidance, not cast."))
    return _dedupe_plan_items(items)[:10]


def _world_setting_items(seed: str) -> list[StoryBriefPlanItem]:
    items: list[StoryBriefPlanItem] = []
    matched_labels: set[str] = set()
    for pattern, label in _WORLD_SETTING_PATTERNS:
        if re.search(pattern, seed, re.I):
            if label in {"Mars setting", "colony setting"} and "Mars colony" in matched_labels:
                continue
            if label == "library setting" and "fantasy library" in matched_labels:
                continue
            matched_labels.add(label)
            items.append(
                StoryBriefPlanItem(
                    label=label,
                    rationale="Used as world/setting pressure, not active cast.",
                )
            )
    return _dedupe_plan_items(items)[:10]


def _revision_actions(warnings: list[str], profile: TensionProfile) -> list[StoryBriefRevisionAction]:
    actions = [
        StoryBriefRevisionAction(
            action_id="add_witness",
            label="Add witness",
            description="Add a third party who can observe, pressure, or misread the conflict.",
            seed_append="Planner note: Add a witness with a concrete stake in the outcome.",
        ),
        StoryBriefRevisionAction(
            action_id="add_deadline",
            label="Add deadline",
            description="Give the scene a public decision window or event deadline.",
            seed_append="Planner note: Add a clear deadline or public event that forces action now.",
        ),
        StoryBriefRevisionAction(
            action_id="add_audience",
            label="Add audience",
            description="Make the tension visible through a room, crowd, board, class, or faction.",
            seed_append="Planner note: Add an audience or faction that will react to the reveal.",
        ),
    ]
    if profile in {"comedy", "cozy_mystery"} or any("life-or-death" in warning.lower() for warning in warnings):
        actions.append(
            StoryBriefRevisionAction(
                action_id="lower_stakes",
                label="Lower stakes",
                description="Keep comedy/cozy tension in props, clues, embarrassment, or social pressure.",
                seed_append="Planner note: Lower the stakes to embarrassment, missing props, social pressure, or clue payoff.",
            )
        )
    actions.append(
        StoryBriefRevisionAction(
            action_id="move_extra_to_background",
            label="Move extras to background",
            description="Keep the named group as context instead of making everyone active at once.",
            seed_append="Planner note: Move extra factions to background pressure so only 3-5 parties are active.",
        )
    )
    return actions[:8]


def _has_pressure_signal(seed: str) -> bool:
    lowered = seed.lower()
    return any(
        token in lowered
        for token in (
            "deadline",
            "before",
            "vote",
            "ceremony",
            "livestream",
            "launch",
            "public",
            "missing",
            "accused",
            "contest",
            "show",
            "talent show",
            "broadcast",
            "eclipse",
            "board vote",
            "midnight",
            "pressure",
            "secret",
            "conflict",
        )
    )


def _premise_summary(
    seed: str,
    *,
    cast_plan: CastPlan | None = None,
    profile: TensionProfile | None = None,
    time_event_anchors: list[StoryBriefPlanItem] | None = None,
    world_setting_pressure: list[StoryBriefPlanItem] | None = None,
) -> str:
    if cast_plan is not None and profile is not None:
        cast_names = [
            entity.display_name
            for entity in [*cast_plan.primary_active_entities, *cast_plan.secondary_background_entities]
        ]
        pressure_labels = [
            item.label
            for item in [*(time_event_anchors or []), *(world_setting_pressure or [])]
            if item.label.lower() != "core premise"
        ]
        summary = f"{_PROFILE_KERNELS[profile][0]} brief with {', '.join(cast_names[:6])}"
        if pressure_labels:
            summary += f"; pressure: {', '.join(pressure_labels[:3])}"
        return summary[:257].rstrip(" ,;") + "."
    if len(seed) <= 240:
        cleaned = _ENTITY_LEADING_NOISE_RE.sub("", seed)
        return cleaned
    return seed[:237].rstrip() + "..."


def _fit_rationale(status: str, profile: TensionProfile) -> str:
    if status == "not_fit":
        return "The current runtime is locked to 3+ active parties; this premise should add another stakeholder before generation."
    if status == "needs_revision":
        return "The runtime can attempt this, but the brief recommends clearer public conflict, pressure, or cast shape first."
    return f"This fits the current multi-party runtime using the {profile.replace('_', ' ')} tension profile."


def _has_high_stakes_conflict(seed: str) -> bool:
    lowered = seed.lower()
    return any(pattern in lowered for pattern in _HIGH_STAKES_PATTERNS)


def _strip_planner_note_lines(seed: str) -> str:
    kept: list[str] = []
    for line in seed.splitlines():
        if _PLANNER_NOTE_LINE_RE.match(line):
            continue
        line = re.sub(r"\s+(?:planner note|revision guidance)\s*:.*$", "", line, flags=re.I)
        kept.append(line)
    return "\n".join(kept)


def _strip_entity_exclusion_segments(seed: str) -> str:
    text = re.sub(r"\bwithout\b[^.!?;]*", "", seed, flags=re.I)
    text = re.sub(r"\bkeep it\b[^.!?;]*", "", text, flags=re.I)
    text = re.sub(r"\bmake it\b[^.!?;]*", "", text, flags=re.I)
    text = re.sub(
        r"(?:^|[,\n;])\s*no\s+(?:public pressure|betrayal|blackmail|violence|villains?|mystery|conflict)\b[^,.;!?]*",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(?:^|[,\n;])\s*just\s+(?:a\s+|an\s+|the\s+)?(?:lost\s+)?wedding\s+ring\b[^,.;!?]*",
        "",
        text,
        flags=re.I,
    )
    return text


def _canonical_entity_key(value: str) -> str:
    cleaned = _ENTITY_LEADING_NOISE_RE.sub("", value).lower()
    cleaned = re.sub(r"\bconcerns?\b", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return " ".join(cleaned.split())


def _emphasized_entity_keys(seed: str, entities: list[str]) -> set[str]:
    keys = {_canonical_entity_key(name) for name in _emphasized_entity_names(seed)}
    for entity in entities:
        escaped = re.escape(entity)
        if len(re.findall(rf"\b{escaped}\b", seed, flags=re.I)) > 1:
            keys.add(_canonical_entity_key(entity))
    return {key for key in keys if key}


def _opening_search_text(opening: Any) -> str:
    chunks: list[str] = []
    for attr in ("title", "advisor_persona"):
        value = getattr(opening, attr, "")
        if value:
            chunks.append(str(value))
    message = getattr(opening, "opening_message", None)
    if message is not None:
        chunks.append(str(getattr(message, "content", "")))
        for option in getattr(message, "options", []) or []:
            chunks.append(str(getattr(option, "label", "")))
            chunks.append(str(getattr(option, "hint", "")))
    for cast_member in getattr(opening, "cast", []) or []:
        for attr in ("display_name", "role", "relation_to_protagonist", "hidden_objective", "leverage_over_player"):
            chunks.append(str(getattr(cast_member, attr, "")))
    for player_role in getattr(opening, "player_role_options", []) or []:
        for attr in ("label", "public_persona", "hidden_objective"):
            chunks.append(str(getattr(player_role, attr, "")))
        for leverage in getattr(player_role, "leverages_over_npcs", []) or []:
            chunks.append(str(getattr(leverage, "leverage", "")))
        for asset in getattr(player_role, "starting_assets", []) or []:
            chunks.append(str(asset))
    return "\n".join(chunk for chunk in chunks if chunk)


def _cjk_evidence(text: str) -> list[str]:
    evidence: list[str] = []
    for line in text.splitlines():
        if _CJK_RE.search(line):
            evidence.append(line[:120])
    return evidence[:4] or ["CJK characters detected"]


def _brief_preserves_high_stakes(brief: StoryBrief) -> bool:
    labels = " ".join(
        [
            *brief.preserved_constraints,
            *(item.label for item in brief.constraints),
            *(item.label for item in brief.time_event_anchors),
        ]
    ).lower()
    return any(pattern in labels for pattern in _HIGH_STAKES_PATTERNS)


def _profile_tone_taboo_matches(brief: StoryBrief, lowered_opening_text: str) -> list[str]:
    matches: list[str] = []
    for term in _PROFILE_TONE_TABOO_TERMS.get(brief.tension_profile, ()):
        if term not in lowered_opening_text:
            continue
        if _term_explicitly_requested(brief.original_seed, term):
            continue
        matches.append(term)
    return _dedupe_preserving_order(matches)[:8]


def _term_explicitly_requested(seed: str, term: str) -> bool:
    lowered = seed.lower()
    candidates = [term]
    if term.endswith("s"):
        candidates.append(term[:-1])
    if term in {"start a fight", "fight"}:
        candidates.append("fight")
    if term in {"takes the fall", "take the fall"}:
        candidates.extend(["takes the fall", "take the fall"])
    if term in {"hacking", "hack"}:
        candidates.extend(["hacking", "hack"])
    for candidate in _dedupe_preserving_order(candidates):
        for match in re.finditer(re.escape(candidate), lowered):
            prefix = lowered[max(0, match.start() - 28) : match.start()]
            if re.search(r"\b(?:no|not|avoid|without|never)\b[^.!?;]{0,28}$", prefix):
                continue
            return True
    return False


def _missing_primary_entities(brief: StoryBrief, lowered_opening_text: str) -> list[str]:
    missing: list[str] = []
    for entity in brief.cast_plan.primary_active_entities:
        if entity.kind == "setting":
            continue
        label = entity.display_name.lower()
        if label and label not in lowered_opening_text:
            missing.append(entity.display_name)
    return missing


def _emphasized_entity_names(seed: str) -> list[str]:
    entity_seed = _strip_planner_note_lines(seed)
    names: list[str] = []
    for pattern in _EMPHASIS_ENTITY_PATTERNS:
        for match in pattern.finditer(entity_seed):
            segment = re.sub(r"\bconcerns?\b", "", match.group(1), flags=re.I)
            if re.match(r"\s*it\b", segment, re.I):
                continue
            for raw in _ENTITY_SPLIT_RE.split(segment):
                candidate = _clean_entity(raw)
                if candidate:
                    names.append(candidate)
    return _dedupe_preserving_order(names)[:8]


def _missing_emphasized_entities(brief: StoryBrief, lowered_opening_text: str) -> list[str]:
    missing: list[str] = []
    for name in _emphasized_entity_names(brief.original_seed):
        if name.lower() not in lowered_opening_text:
            missing.append(name)
    return missing


def _missing_event_anchors(brief: StoryBrief, lowered_opening_text: str) -> list[str]:
    missing: list[str] = []
    for anchor in brief.time_event_anchors:
        label = anchor.label.lower()
        if label in {"core premise"}:
            continue
        if label and label not in lowered_opening_text:
            missing.append(anchor.label)
    return missing


def _dedupe_plan_items(items: list[StoryBriefPlanItem]) -> list[StoryBriefPlanItem]:
    result: list[StoryBriefPlanItem] = []
    seen: set[str] = set()
    for item in items:
        key = item.label.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _is_sub_entity(candidate_key: str, existing_key: str) -> bool:
    if len(candidate_key) <= 4 and re.search(rf"\b{re.escape(candidate_key)}\b", existing_key):
        return True
    return False


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:64]
