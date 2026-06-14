from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rpg_backend.narrative.contracts import (
    CreateTemplateRequest,
    Difficulty,
    NarrativeTemplateSummary,
    StoryBriefAdvisorRequest,
    StoryGuideTurnRequest,
    TemplateLanguage,
    TensionProfile,
    TemplateVisibility,
)

if TYPE_CHECKING:
    from rpg_backend.narrative.service import NarrativeService


DEFAULT_HOME_STORY_OWNER_ID = "system_home_story_library"


@dataclass(frozen=True)
class DefaultHomeStorySpec:
    """Seed instructions for durable Home story objects.

    These are generation prompts, not Home-visible card copy. The visible
    title, intro, cast, opening, and options are produced by the normal
    Story Butler -> Story Brief -> template chain and persisted as public
    templates.
    """

    library_key: str
    seed: str
    language: TemplateLanguage = "en"
    desired_tension_profile: TensionProfile = "high_drama"
    turn_budget: int = 12
    difficulty: Difficulty = "story"
    visibility: TemplateVisibility = "public"


DEFAULT_HOME_STORY_SPECS: tuple[DefaultHomeStorySpec, ...] = (
    DefaultHomeStorySpec(
        library_key="awards_disappearance",
        seed=(
            "Ten minutes before an awards livestream, an anxious publicist, "
            "a producer, a backup dancer, and a sponsor representative discover "
            "that a famous singer has disappeared. The backup dancer saw the "
            "singer leave the control room, fans are panicking outside, and the "
            "player must decide who to protect, what to reveal, and what to hide "
            "before the show goes live. There is no gore."
        ),
        desired_tension_profile="high_drama",
    ),
    DefaultHomeStorySpec(
        library_key="board_gala_recording",
        seed=(
            "At a board gala before a merger vote, a cofounder, an investor, "
            "a legal chief, and the player's ex fight over a recording that proves "
            "someone made a secret deal. The player must decide who gets the "
            "recording, whether the company survives, and who falls in public "
            "before the gala ends."
        ),
        desired_tension_profile="high_drama",
    ),
    DefaultHomeStorySpec(
        library_key="wedding_account_note",
        seed=(
            "Minutes before a wedding procession, the groom, bride, best man, "
            "maid of honor, and both mothers wait near the aisle. The best man "
            "hands the player a note with the bride's old account and an "
            "unexplained transfer. Guests are seated, and the player must decide "
            "whether to investigate quietly, confront someone publicly, or let "
            "the wedding continue."
        ),
        desired_tension_profile="family_social",
    ),
    DefaultHomeStorySpec(
        library_key="campus_scholarship_card",
        seed=(
            "At a city library just before closing, three students, a former "
            "mentor, and the archivist argue over a glowing library card. The "
            "card can prove a scholarship application was switched, but it can "
            "also ruin one person's future. The player must decide who to believe, "
            "who to protect, and whether to hand over the evidence."
        ),
        desired_tension_profile="cozy_mystery",
    ),
)


@dataclass(frozen=True)
class DefaultHomeStoryResult:
    library_key: str
    created: bool
    template: NarrativeTemplateSummary


def ensure_default_home_story_library(
    service: "NarrativeService",
    *,
    owner_user_id: str = DEFAULT_HOME_STORY_OWNER_ID,
    specs: tuple[DefaultHomeStorySpec, ...] = DEFAULT_HOME_STORY_SPECS,
    limit: int | None = None,
) -> list[DefaultHomeStoryResult]:
    """Ensure default Home story templates exist as persisted public templates.

    The helper is intentionally explicit/job-like. Home reads templates through
    the normal public list endpoint; it does not generate on page load.
    """

    selected_specs = specs[: max(0, int(limit))] if limit is not None else specs
    existing = {
        _normalized_seed(template.seed): template
        for template in service.list_my_templates(owner_user_id=owner_user_id).items
        if template.visibility == "public"
    }
    results: list[DefaultHomeStoryResult] = []
    for spec in selected_specs:
        existing_template = existing.get(_normalized_seed(spec.seed))
        if existing_template is not None:
            results.append(
                DefaultHomeStoryResult(
                    library_key=spec.library_key,
                    created=False,
                    template=existing_template,
                )
            )
            continue

        guide = service.create_story_guide_turn(
            StoryGuideTurnRequest(
                message=spec.seed,
                language=spec.language,
                current_seed="",
                previous_assistant_reply="",
                state=None,
            ),
            owner_user_id=owner_user_id,
        )
        accepted_seed = spec.seed
        if guide.acceptedText and guide.state.acceptedTurns:
            accepted_seed = "\n".join(guide.state.acceptedTurns)

        brief_response = service.create_story_brief(
            StoryBriefAdvisorRequest(
                seed=accepted_seed,
                language=spec.language,
                desired_tension_profile=spec.desired_tension_profile,
            ),
            owner_user_id=owner_user_id,
        )
        if not brief_response.can_generate:
            raise RuntimeError(
                f"default Home story seed did not produce a playable Brief: {spec.library_key}"
            )
        template_response = service.create_template(
            CreateTemplateRequest(
                seed=accepted_seed,
                visibility=spec.visibility,
                turn_budget=spec.turn_budget,
                difficulty=spec.difficulty,
                language=spec.language,
                story_brief=brief_response.brief,
            ),
            owner_user_id=owner_user_id,
        )
        existing[_normalized_seed(spec.seed)] = template_response.template
        results.append(
            DefaultHomeStoryResult(
                library_key=spec.library_key,
                created=True,
                template=template_response.template,
            )
        )
    return results


def _normalized_seed(seed: str) -> str:
    return " ".join(str(seed or "").strip().split())
