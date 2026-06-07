from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_create_page_has_top_left_back_and_no_buried_bottom_back() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    styles = (ROOT / "frontend2/src/pages/create/create-styles.ts").read_text()

    header_start = source.index("<header")
    main_start = source.index("<main", header_start)
    header_segment = source[header_start:main_start]

    assert "cpStyles.topBackButton" in header_segment
    assert 't("create.cta_back")' in header_segment
    assert "onClick={onBackHome}" in header_segment
    assert "const showBackAction" not in source
    assert "cpStyles.backAction" not in source
    assert "backAction:" not in source
    assert '"create.cta_back": "← Story Desk"' in strings
    assert '"create.cta_back": "← 故事入口"' in strings

    top_back = styles[styles.index("topBackButton: {") : styles.index("topBackButtonCompact:", styles.index("topBackButton: {"))]
    assert "padding:" not in top_back
    assert "paddingBottom: 5" in top_back
    assert "paddingLeft: 0" in top_back


def test_shared_header_supports_explicit_back_for_secondary_pages() -> None:
    header = (ROOT / "frontend2/src/shared/ui/header.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()
    about = (ROOT / "frontend2/src/pages/about/about-page.tsx").read_text()
    portfolio = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()
    reviewer = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()
    login = (ROOT / "frontend2/src/pages/auth/login-page.tsx").read_text()

    assert "showBackButton = false" in header
    assert "topbar--with-back" in header
    assert 'className="topbar-back"' in header
    assert 't("action.back_home")' in header
    assert ".topbar-back" in theme
    assert ".topbar--with-back .brand strong" in theme
    assert ".topbar--with-back .topbar-create-link" in theme
    assert "showBackButton" in about
    assert "showBackButton" in portfolio
    assert "showBackButton" in reviewer
    assert "backToHome" not in about
    assert "apStyles.backAction" not in about
    assert "lpStyles.backLink" in login
    assert 't("action.back_home")' in login
    assert '"action.back_home": "← Story Desk"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    assert '"action.back_home": "← 故事入口"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()


def test_existing_play_world_replay_page_navigation_stays_top_level() -> None:
    play = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    play_panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    world = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()
    replay = (ROOT / "frontend2/src/pages/replay/replay-page.tsx").read_text()

    assert 't("play.back_home")' in play_panels
    assert 't("play.back_home_short")' in play_panels
    assert 'createVariant="link" showBackButton' in world
    hero_start = world.index("{/* Hero:")
    main_start = world.index("<main", hero_start)
    assert 't("world.crumb_back_home")' not in world[hero_start:main_start]
    assert 't("replay.crumb_back_home")' in replay


def test_home_distinguishes_premise_starters_from_published_playable_stories() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    helper = home[home.index("export function getHomeTileCopy") : home.index("function starterPremiseView")]
    curated_start = home.index("function CuratedStoryTile")
    template_start = home.index("function TemplateCard")
    curated = home[curated_start:template_start]
    template = home[template_start:home.index("function visibilityLabel")]

    assert "type HomeStoryObjectKind" in home
    assert "type HomeStoryObjectView" in home
    assert 'kind === "starter_premise"' in helper
    assert 'kind === "published_story"' in helper
    assert 't("home.card_action")' in helper
    published_helper = helper[helper.index('kind === "published_story"') : helper.index('kind === "in_progress_run"')]
    preset_helper = helper[helper.index('kind === "starter_premise"') : helper.index('kind === "published_story"')]
    assert "Story Butler" not in preset_helper
    assert "Story Butler" not in published_helper
    assert 'data-story-card-kind="preset-story"' in curated
    assert "view.copy.typeLabel" not in curated
    assert "view.copy.primaryAction" in curated
    assert "saveCreateDraftHandoff" not in template
    assert 'data-story-card-kind="published-story"' in template
    assert 'data-home-tile-span={span}' in template
    assert "displayView.copy.primaryAction" in template
    assert "view.copy.typeLabel" not in template
    assert 'data-home-tile-text-body="title-deck-only"' in home
    assert "Story Butler" not in curated
    assert '"home.card_action": "Enter story →"' in strings
