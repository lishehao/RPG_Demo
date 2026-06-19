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


def test_portfolio_hero_gives_reviewer_a_clear_consumption_order() -> None:
    portfolio = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    assert "PORTFOLIO_REVIEW_ORDER" in portfolio
    assert "Watch 75s demo" in portfolio
    assert "Launch reviewer run" in portfolio
    assert "Inspect evidence" in portfolio
    assert 'data-portfolio-review-order="true"' in portfolio
    assert "data-portfolio-review-step={item.step}" in portfolio
    assert ".portfolio-review-order" in theme
    assert "grid-template-columns: 34px minmax(0, 1fr)" in theme


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


def test_create_entry_guest_path_explains_temporary_pen_name() -> None:
    login = (ROOT / "frontend2/src/pages/auth/login-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "CREATE_GUEST_PLAN_KEYS" in login
    assert 'data-login-guest-plan="true"' in login
    assert "data-login-guest-plan-item={key}" in login
    assert 't("login.guest_plan_label")' in login
    assert '"login.guest_plan_editor": "Opens the story editor without email or password."' in strings
    assert '"login.guest_plan_saved": "Saves this draft and later runs under the same pen name."' in strings
    assert '"login.guest_plan_custom": "You can still choose your own pen name when it matters."' in strings
    assert '"login.guest_plan_editor": "进入故事编辑器，不需要邮箱或密码。"' in strings
    assert '"login.guest_plan_saved": "这次创作和之后的游玩会挂在这个笔名下。"' in strings
    assert '"login.guest_plan_custom": "想认真命名时，也可以改成自己的笔名。"' in strings


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
    assert 'data-replay-hero-fork-hint="true"' in replay
    assert 't("replay.cta_hint")' in replay
    assert "heroCtaHint" in replay


def test_world_role_launch_has_ready_and_starting_feedback() -> None:
    world = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()

    assert 'data-world-role-launch-state={busy ? "starting" : "ready"}' in world
    assert 'data-world-role-launch-cta={busy ? "starting" : "ready"}' in world
    assert "roleLaunchPanelStarting" in world
    assert "roleLaunchButtonStarting" in world
    assert "cursor: \"progress\"" in world


def test_world_owner_visibility_explains_current_reach() -> None:
    world = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "visibilityDescription(template.visibility, t)" in world
    assert 'data-world-visibility-current="true"' in world
    assert "data-world-visibility-option={v}" in world
    assert '"world.visibility_current": "当前：{label}"' in strings
    assert '"world.visibility_private_desc": "只有你能看到并继续测试这个故事。"' in strings
    assert '"world.visibility_unlisted_desc": "拿到链接的人可以打开并玩出自己的版本。"' in strings
    assert '"world.visibility_public_desc": "故事会出现在广场，任何玩家都能开始一局。"' in strings
    assert '"world.visibility_current": "Current: {label}"' in strings
    assert '"world.visibility_private_desc": "Only you can see and keep testing this story."' in strings
    assert '"world.visibility_unlisted_desc": "People with the link can open it and play their own run."' in strings
    assert '"world.visibility_public_desc": "The story appears in the plaza so anyone can start a run."' in strings


def test_world_advisor_preview_explains_playtime_use() -> None:
    world = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert 'data-world-advisor-preview="true"' in world
    assert 't("world.section_advisor")' in world
    assert 't("world.advisor_hint")' in world
    assert "advisorLabel" in world
    assert "advisorHint" in world
    assert '"world.advisor_hint": "进局后可以向 TA 要一次低风险读局建议。"' in strings
    assert '"world.advisor_hint": "During play, ask them for a low-risk read before choosing."' in strings


def test_replay_preview_labels_why_highlights_matter() -> None:
    replay = (ROOT / "frontend2/src/pages/replay/replay-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert 'data-replay-preview-why="true"' in replay
    assert 't("replay.preview_why_label")' in replay
    assert "previewRecordWhyLabel" in replay
    assert '"replay.preview_why_label": "为什么关键"' in strings
    assert '"replay.preview_why_label": "Why it mattered"' in strings


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
    assert 'data-home-tile-text-body="title-deck-action"' in home
    assert "Story Butler" not in template
    assert '"home.card_action": "Start episode →"' in strings
