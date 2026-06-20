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
    assert '<a className="portfolio-action portfolio-action--primary" href={YOUTUBE_DEMO_URL}' in portfolio
    assert "Watch 75s demo" in portfolio[portfolio.index("portfolio-hero__actions") : portfolio.index('data-portfolio-review-order="true"')]
    assert "portfolio-action portfolio-action--secondary" in portfolio
    assert "Launch reviewer route" in portfolio[portfolio.index("portfolio-action portfolio-action--secondary") : portfolio.index('data-portfolio-review-order="true"')]
    assert 'data-portfolio-review-order="true"' in portfolio
    assert "data-portfolio-review-step={item.step}" in portfolio
    assert "If the preview does not play" in portfolio
    assert "open the MP4 demo" in portfolio
    assert "Muted autoplay is best-effort" not in portfolio
    assert "MP4 fallback" not in portfolio
    assert ".portfolio-review-order" in theme
    assert "grid-template-columns: 34px minmax(0, 1fr)" in theme


def test_root_readme_matches_portfolio_review_path_and_bounds_claims() -> None:
    readme = (ROOT / "README.md").read_text()

    assert "Watch 75s demo" in readme
    assert "Open MP4 demo" in readme
    assert "Inspect source evidence" in readme
    assert "MP4 fallback" not in readme
    assert "offline/fallback" not in readme
    assert "## Reviewer Path" in readme
    assert "Run locally and open `#/portfolio`" in readme
    assert "Launch the reviewer route from the portfolio page" in readme
    assert "Verify source evidence" in readme
    assert "[Current System Map](./docs/CURRENT_SYSTEM_MAP.md)" in readme
    assert "[Case Study](./docs/CASE_STUDY.md)" in readme
    assert "`tests/test_navigation_mental_model_contract.py`" in readme
    assert "`tests/test_play_direction_a_editorial_primitives_contract.py`" in readme
    assert "portfolio-grade AI product-system evidence" in readme
    assert "It is not claimed as a launched consumer" in readme
    assert "game or broad adoption proof" in readme


def test_public_pages_landing_matches_reviewer_evidence_path() -> None:
    landing = (ROOT / "docs/index.html").read_text()

    assert "75s reviewer cut" in landing
    assert "Watch 75s demo" in landing
    assert "Open MP4 demo" in landing
    assert "Source evidence" in landing
    assert "docs/CURRENT_SYSTEM_MAP.md" in landing
    assert "MP4 fallback" not in landing
    assert "Muted preview is best-effort" not in landing
    assert "portfolio-grade AI product-system evidence" in landing
    assert "not a" in landing
    assert "launched consumer game or broad adoption proof" in landing
    assert "system map, reviewer path, contracts, and tests" in landing
    assert ".evidence-boundary" in landing
    assert ".video-actions span:last-child" in landing


def test_source_evidence_docs_are_reviewable_and_bound_claims() -> None:
    case_study = (ROOT / "docs/CASE_STUDY.md").read_text()
    system_map = (ROOT / "docs/CURRENT_SYSTEM_MAP.md").read_text()

    assert "Read this as source evidence after the 75s demo and `#/portfolio` page" in case_study
    assert "bounded 12-turn session" in case_study
    assert "8-20 turn" not in case_study
    assert "## Evidence To Inspect" in case_study
    assert "`docs/CURRENT_SYSTEM_MAP.md`" in case_study
    assert "`frontend2/src/pages/portfolio/`, `#/portfolio`, `#/reviewer`" in case_study
    assert "`rpg_backend/narrative/contracts.py`, `frontend2/src/api/contracts.ts`" in case_study
    assert "`tests/test_navigation_mental_model_contract.py`, `tests/test_play_direction_a_editorial_primitives_contract.py`" in case_study
    assert "portfolio-grade AI product-system evidence" in case_study
    assert "not a validated consumer" in case_study
    assert "broad adoption proof" in case_study

    assert "source-evidence companion to the README, GitHub Pages demo" in system_map
    assert "what path is current, what code backs it" in system_map
    assert "provenance rather than the demo being claimed" in system_map
    assert "current" in system_map
    assert "portfolio-facing product path is intentionally narrow" in system_map
    assert "not required to run or review the demo" in system_map


def test_chinese_readme_matches_portfolio_evidence_framing() -> None:
    readme = (ROOT / "README.zh.md").read_text()

    assert "status-portfolio_case_study" in readme
    assert "Status: Paused" not in readme
    assert "status-paused" not in readme
    assert "alpha / open-source preview" not in readme
    assert "portfolio-grade AI product-system evidence" in readme
    assert "不是已经验证过的消费级游戏或大规模用户增长案例" in readme
    assert "真实用户需求、复玩、留存和自然分享没有被证明" in readme
    assert "## Demo" in readme
    assert "[观看 75 秒 demo](https://youtu.be/RRJ7uyjW_nA)" in readme
    assert "[打开 MP4 备份](./docs/demo-video/tiny-stories-admissions-demo-readme.mp4)" in readme
    assert "[打开 GitHub Pages 展示页](https://lishehao.github.io/RPG_Demo/)" in readme
    assert "视频用于快速理解玩家看到的 loop" in readme
    assert "真正的申请材料证据仍然在 source、tests" in readme
    assert "## 申请 / 作品集审阅路径" in readme
    assert "`#/portfolio`" in readme
    assert "`#/reviewer`" in readme
    assert "[Current System Map](./docs/CURRENT_SYSTEM_MAP.md)" in readme
    assert "[Case Study](./docs/CASE_STUDY.md)" in readme
    assert "portfolio case study / open-source preview" in readme
    assert "consumer traction" in readme
    assert "Play 容器 + StoryBeat / ActionArea / Advisor / Ending 等模块" in readme
    assert "play-page.tsx (~2400 行,所有 turn UI 在这)" not in readme


def test_portfolio_page_separates_public_and_local_evidence_claims() -> None:
    portfolio = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    assert "PORTFOLIO_EVIDENCE_BOUNDARY" in portfolio
    assert 'data-portfolio-evidence-boundary="true"' in portfolio
    assert 'data-portfolio-source-evidence="true"' in portfolio
    assert "Public artifact" in portfolio
    assert "Live reviewer path" in portfolio
    assert "Not claimed" in portfolio
    assert "Source evidence" in portfolio
    assert "review code, docs, tests, and the narrow runtime path" in portfolio
    assert "GitHub repo" in portfolio
    assert "System map" in portfolio
    assert 'PUBLIC_REPO_URL = "https://github.com/lishehao/RPG_Demo"' in data
    assert 'SYSTEM_MAP_URL = "https://github.com/lishehao/RPG_Demo/blob/main/docs/CURRENT_SYSTEM_MAP.md"' in data
    assert "not proof of a launched consumer product or broad user adoption" in portfolio
    assert "product-system evidence, not" in portfolio
    assert "story generation" in portfolio
    assert "raw generation" not in portfolio
    assert "reliable AI product surface" not in portfolio
    assert ".portfolio-evidence-boundary" in theme
    assert ".portfolio-evidence-boundary__grid" in theme
    assert ".portfolio-source-evidence" in theme


def test_portfolio_proofbar_uses_reviewer_verifiable_metrics() -> None:
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()

    assert "Locked seed" in data
    assert "same premise for every reviewer run" in data
    assert "12-turn cap" in data
    assert "bounded episode budget visible in Play" in data
    assert "3 proofs" in data
    assert "playable state, state change, archived checks" in data
    assert "Replay loop" in data
    assert "ending can be shared or restarted" in data
    assert "5 layers" not in data
    assert "EN first" not in data


def test_portfolio_inspector_uses_reviewer_verifiable_capability_labels() -> None:
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()

    for expected in (
        "Seed becomes setup",
        "Role creates stakes",
        "Choices change state",
        "Advisor stays separate",
        "Ending becomes replay",
        "playable state, state change, and archived checks",
    ):
        assert expected in data

    for old_internal_label in (
        "Seed Router",
        "Playable Role Model",
        "Stateful Consequences",
        "Advisor Channel",
        "Ending Compiler",
        "LLM-mediated",
    ):
        assert old_internal_label not in data


def test_portfolio_loop_maps_each_state_to_visible_evidence() -> None:
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()
    portfolio = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()

    for expected in (
        "visible evidence: locked seed and generated opening",
        "visible evidence: role panel, objective, assets",
        "visible evidence: next moves, pulse, inventory",
        "visible evidence: ending, highlights, replay link",
        "artifact each state leaves behind",
    ):
        assert expected in data or expected in portfolio

    assert "not just admire generated images" not in portfolio
    assert "secret merger · awards livestream · ex with proof" not in data


def test_portfolio_case_study_points_are_evidence_oriented() -> None:
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()

    for expected in (
        "player role, state changes, and ending proof",
        "designed product system",
        "locked setup, playable role, visible state changes",
        "advisor boundary, and replayable ending",
        "product-system evidence",
        "typed state, persistent sessions, reviewer evidence hooks",
        "mobile-checked surfaces without claiming broad adoption",
    ):
        assert expected in data

    for overclaim_or_weak_frame in (
        "random text generator",
        "Product Thesis",
        "Engineering Angle",
        "prompt novelty",
        "fully validated consumer product",
    ):
        assert overclaim_or_weak_frame not in data


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
    assert 'data-home-hero-sub="true"' in home
    assert 't("home.hero_sub")' in home
    assert '"home.hero_tagline": "Story Desk · Pick, resume, or write a run"' in strings
    assert '"home.hero_sub": "Choose a playable story, reopen saved runs, or write a new opening; each 15 min episode branches through role, pressure, and visible consequences."' in strings
    assert '"home.hero_bullet_2": "Each turn shows pressure, clues, and character state before you choose a move with tradeoffs."' in strings
    assert 'setError(t("home.error_plaza"))' in home
    assert '"home.error_plaza": "The story list did not open. You can still write a new story above, or come back in a moment."' in strings

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


def test_world_role_launch_explains_first_turn_reading() -> None:
    world = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert 'data-world-role-launch-read="true"' in world
    assert 'data-world-role-launch-read-item="goal"' in world
    assert 'data-world-role-launch-read-item="resources"' in world
    assert 'data-world-role-launch-read-item="opening"' in world
    assert 't("world.role_launch_read_title")' in world
    assert 't("world.role_launch_read_goal")' in world
    assert 't("world.role_launch_read_resources"' in world
    assert 't("world.role_launch_read_opening")' in world
    assert '"world.role_launch_read_title": "第一回合这样读"' in strings
    assert '"world.role_launch_read_goal": "先看暗线目标：它决定你为什么要选这一步。"' in strings
    assert '"world.role_launch_read_resources": "你带着 {cards} 张反将牌、{items} 件物品；普通选择不够时再亮出来。"' in strings
    assert '"world.role_launch_read_opening": "开场相同，但房间会按这个身份的压力回应你。"' in strings
    assert '"world.role_launch_read_title": "How to read turn one"' in strings
    assert '"world.role_launch_read_goal": "Read the private goal first; it explains why one move matters."' in strings
    assert '"world.role_launch_read_resources": "You bring {cards} leverage cards and {items} items; reveal them when normal moves are not enough."' in strings
    assert '"world.role_launch_read_opening": "The opening is the same, but the room reacts to this identity\'s pressure."' in strings


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

    assert 'data-replay-view-mode-hint="true"' in replay
    assert 't("replay.view_mode_hint")' in replay
    assert "viewModeHint" in replay
    assert 'data-replay-preview-why="true"' in replay
    assert 't("replay.preview_why_label")' in replay
    assert "previewRecordWhyLabel" in replay
    assert '"replay.view_mode_hint": "先看关键转折；想细读时切到完整故事。"' in strings
    assert '"replay.view_mode_hint": "Start with the key turns; switch to full when you want every beat."' in strings
    assert '"replay.preview_why_label": "为什么关键"' in strings
    assert '"replay.preview_why_label": "Why it mattered"' in strings


def test_replay_hero_preserves_player_role_context() -> None:
    replay = (ROOT / "frontend2/src/pages/replay/replay-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "replay.player_role?.label" in replay
    assert 't("replay.role_meta", { role: replay.player_role.label })' in replay
    assert 'data-replay-hero-role="true"' in replay
    assert '"replay.role_meta": "扮演 {role}"' in strings
    assert '"replay.role_meta": "Played as {role}"' in strings


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
