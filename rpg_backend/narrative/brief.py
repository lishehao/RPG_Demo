from __future__ import annotations

import re

from rpg_backend.narrative.contracts import (
    CastPlan,
    CastPlanEntity,
    ConstraintDisposition,
    StoryBrief,
    StoryBriefAdvisorResponse,
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
            "comedy",
            "comic",
            "funny",
            "sitcom",
            "absurd",
            "awkward",
            "embarrass",
            "talent show",
            "prank",
            "cupcake",
            "bake sale",
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

    fit_status = "fit"
    if explicit_small_cast:
        fit_status = "not_fit"
    elif warnings:
        fit_status = "needs_revision"

    dispositions = _constraint_dispositions(preserved, compressed, dropped, softened)
    fit_rationale = _fit_rationale(fit_status, profile)
    brief = StoryBrief(
        original_seed=clean_seed,
        premise_summary=_premise_summary(clean_seed),
        genre_tone=title,
        tension_profile=profile,
        story_kernel=kernel,
        intervention_card_label=intervention,
        cast_plan=cast_plan,
        preserved_constraints=preserved,
        compressed_constraints=compressed,
        dropped_constraints=dropped,
        softened_constraints=softened,
        constraint_dispositions=dispositions,
        warnings=warnings,
        revision_suggestions=revision_suggestions,
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


def infer_tension_profile(seed: str) -> TensionProfile:
    lowered = seed.lower()
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
    candidates: list[str] = []
    parts = [seed]
    if ":" in seed:
        parts.insert(0, seed.split(":", 1)[1])
    for part in parts:
        for raw in _ENTITY_SPLIT_RE.split(part):
            candidate = _clean_entity(raw)
            if candidate:
                candidates.append(candidate)
    # Proper-noun fallback catches compact prompts without comma lists.
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", seed):
        candidate = _clean_entity(match.group(1))
        if candidate:
            candidates.append(candidate)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _clean_entity(raw: str) -> str:
    text = re.sub(r"\([^)]*\)", "", raw).strip(" .!?\"'“”‘’")
    text = re.sub(r"\b(the|a|an|with|featuring|including|departments?|factions?|cast)\b", "", text, flags=re.I)
    text = " ".join(text.split())
    if not text:
        return ""
    words = text.split()
    if len(words) > 5:
        return ""
    if all(word.lower() in _STOPWORDS for word in words):
        return ""
    if len(text) < 2 or len(text) > 80:
        return ""
    return text[:80]


def _build_cast_plan(seed: str, entities: list[str], profile: TensionProfile) -> CastPlan:
    planned = entities[:10]
    if len(planned) < 3 and not has_explicit_small_cast_mismatch(seed):
        planned = _fallback_entities(seed, profile)
    primary = [
        _entity(name, idx, role="Primary active party", rationale="Kept in the 3-5 entity focus window.")
        for idx, name in enumerate(planned[:5])
    ]
    secondary = [
        _entity(name, idx + 5, role="Secondary/background pressure", rationale="Kept as context, not active every turn.")
        for idx, name in enumerate(planned[5:10])
    ]
    omitted = [
        _entity(name, idx + 10, role="Omitted/merge candidate", rationale="Beyond the 10-entity planning cap.")
        for idx, name in enumerate(entities[10:15])
    ]
    return CastPlan(
        input_entity_count=len(entities),
        primary_active_entities=primary,
        secondary_background_entities=secondary,
        omitted_entities=omitted,
        active_focus_window="Director should keep 3-5 entities readable per turn; others remain background pressure.",
    )


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
        return ["player", "keeper of the clue", "gentle suspect", "outside witness"]
    if profile == "comedy":
        return ["player", "mistaken accuser", "embarrassed witness", "deadline enforcer"]
    return ["player", "rival", "witness", "deadline holder"]


def _preserved_constraints(seed: str, profile: TensionProfile) -> list[str]:
    constraints = ["core premise"]
    lowered = seed.lower()
    if profile != "high_drama":
        constraints.append(f"{profile.replace('_', ' ')} tone")
    for token in ("missing", "secret", "vote", "deadline", "wedding", "talent show", "artifact", "ring"):
        if token in lowered:
            constraints.append(token)
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
            "pressure",
            "secret",
            "conflict",
        )
    )


def _premise_summary(seed: str) -> str:
    if len(seed) <= 240:
        return seed
    return seed[:237].rstrip() + "..."


def _fit_rationale(status: str, profile: TensionProfile) -> str:
    if status == "not_fit":
        return "The current runtime is locked to 3+ active parties; this premise should add another stakeholder before generation."
    if status == "needs_revision":
        return "The runtime can attempt this, but the brief recommends clearer public conflict, pressure, or cast shape first."
    return f"This fits the current multi-party runtime using the {profile.replace('_', ' ')} tension profile."


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:64]
