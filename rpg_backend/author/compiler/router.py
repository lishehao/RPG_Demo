from __future__ import annotations

from rpg_backend.author.contracts import DesignBundle, FocusedBrief, StoryFrameDraft
from rpg_backend.story_profiles import (
    AuthorThemeDecision as StoryThemeDecision,
    author_theme_from_brief,
    author_theme_from_bundle,
    author_theme_from_story,
)


def plan_brief_theme(
    focused_brief: FocusedBrief,
) -> StoryThemeDecision:
    return author_theme_from_brief(focused_brief)


def plan_story_theme(
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
) -> StoryThemeDecision:
    return author_theme_from_story(focused_brief, story_frame)


def plan_bundle_theme(
    bundle: DesignBundle,
) -> StoryThemeDecision:
    return author_theme_from_bundle(bundle)
