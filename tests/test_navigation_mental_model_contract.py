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
    assert "showBackButton" in about
    assert "showBackButton" in portfolio
    assert "showBackButton" in reviewer
    assert "backToHome" not in about
    assert "apStyles.backAction" not in about
    assert "lpStyles.backLink" in login
    assert 't("action.back_home")' in login
    assert '"action.back_home": "← Story Desk"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    assert '"action.back_home": "← 故事入口"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()


def test_home_topbar_account_ia_keeps_creation_in_hero() -> None:
    header = (ROOT / "frontend2/src/shared/ui/header.tsx").read_text()
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert 't("header.write_story")' not in header
    assert "topbar-create-link" not in header
    assert ".topbar-create-link" not in theme
    assert 't("home.cta_create")' in home
    assert "onClick={onOpenCreate}" in home

    assert 't("header.login")' in header
    assert 't("header.account")' in header
    assert "topbar-login-link" in header
    assert "topbar-account__label" in header
    assert "topbar-lang" in header
    assert "topbar-account" in header
    assert '"header.account": "Account"' in strings
    assert '"header.account": "账号"' in strings


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


def test_home_story_entries_are_generated_playable_template_objects() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    template_start = home.index("function TemplateCard")
    template = home[template_start:home.index("function visibilityLabel")]

    assert "type HomeStoryObjectKind" in home
    assert "type HomeStoryObjectView" in home
    assert 'kind === "published_story"' in home
    assert "starter_premise" not in home
    assert "CuratedPlazaStory" not in home
    assert "handleStartCuratedStory" not in home
    assert "api.createNarrativeStoryBrief" not in home
    assert "api.createNarrativeTemplate" not in home
    assert "listPublicNarrativeTemplates" in home
    assert "api.startNarrativeSession(templateId)" in home
    assert "saveCreateDraftHandoff" not in template
    assert 'data-story-card-kind="published-story"' in template
    assert 'data-home-tile-span={span}' in template
    assert "displayView.copy.primaryAction" in template
    assert "view.copy.typeLabel" not in template
    assert 'data-home-tile-text-body="title-deck-only"' in home
    assert "Story Butler" not in template
    assert '"home.card_action": "Enter story →"' in strings
