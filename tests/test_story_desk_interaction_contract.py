from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_story_start_intents_are_typed_and_cover_existing_world_doors() -> None:
    intents = _read("frontend2/src/shared/lib/story-start-intents.ts")

    for intent_id in [
        "cozy-social",
        "fantasy-library",
        "mars-colony",
        "slow-mystery",
        "slice-of-life",
        "high-drama",
    ]:
        assert intent_id in intents

    assert "StoryStartIntentId" in intents
    assert "getStoryStartIntent" in intents
    assert "cover-cozy" not in intents
    assert "GENERATED_ASSETS.coverCozy" in intents
    assert "GENERATED_ASSETS.coverFantasy" in intents
    assert "GENERATED_ASSETS.coverSciFiMars" in intents
    assert "GENERATED_ASSETS.coverHighDrama" in intents


def test_story_door_navigation_prefills_create_without_auto_generation() -> None:
    routes = _read("frontend2/src/app/routes.ts")
    app = _read("frontend2/src/app/app.tsx")
    home = _read("frontend2/src/pages/home/home-page.tsx")
    create = _read("frontend2/src/pages/create/create-page.tsx")

    assert 'params.get("intent")' in routes
    assert "startIntentId?: StoryStartIntentId" in routes
    assert "startIntentId={route.startIntentId}" in app
    assert "STORY_START_INTENTS.map" in home
    assert "onOpenCreate(intent.id)" in home
    assert "data-story-start-intent" in create
    assert "selectedStartIntent.seedDraft" in create
    assert "setDesiredTensionProfile(selectedStartIntent.tensionProfile)" in create
    assert "handlePlanStory()" in create
    assert "handleCreate()" not in create[create.index("presetPanel"):create.index("messageStack")]


def test_player_facing_language_uses_story_desk_and_hides_proof_nav() -> None:
    i18n = _read("frontend2/src/shared/lib/i18n.ts")
    home = _read("frontend2/src/pages/home/home-page.tsx")
    header = _read("frontend2/src/shared/ui/header.tsx")

    assert '"home.tab_plaza": "Plaza"' not in i18n
    assert "广场公开" not in i18n
    assert "Failed to load the plaza" not in i18n
    assert "AI is building the story" not in i18n
    assert "current Tiny Stories runtime" not in i18n
    assert "Story Desk" in i18n
    assert "故事桌面" in i18n
    assert "home.grammar_label" in i18n
    assert "home.story_door_action" in i18n
    assert "showCaseStudy = false" in header
    assert 't("home.cta_pick_world")' in home
