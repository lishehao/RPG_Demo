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
    assert ".topbar--with-back .brand { display: none; }" in theme
    assert ".topbar--with-back .brand strong" not in theme
    mobile_topbar_start = theme.index("  .topbar {\n    min-height: 54px;")
    mobile_topbar_end = theme.index("  .topbar-actions > .btn", mobile_topbar_start)
    mobile_topbar = theme[mobile_topbar_start:mobile_topbar_end]
    assert "padding: 5px 18px" in mobile_topbar
    assert ".topbar-back { flex: 0 0 auto; min-height: 44px; height: auto;" in mobile_topbar
    assert "min-height: 44px" in mobile_topbar[mobile_topbar.index(".topbar-login-link") :]
    assert "min-height: 44px" in mobile_topbar[mobile_topbar.index(".topbar-lang {") :]
    assert "min-height: 44px" in mobile_topbar[mobile_topbar.index(".topbar-lang__pill") :]
    assert "min-width: 44px" in mobile_topbar[mobile_topbar.index(".topbar-lang__pill") :]
    assert "showBackButton" in about
    assert "showBackButton" in portfolio
    assert "showBackButton" in reviewer
    assert "backToHome" not in about
    assert "apStyles.backAction" not in about
    assert "lpStyles.backLink" in login
    assert 't("action.back_home")' in login
    assert '"action.back_home": "← Story Desk"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    assert '"action.back_home": "← 故事入口"' in (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()


def test_about_page_matches_portfolio_case_study_boundaries() -> None:
    about = (ROOT / "frontend2/src/pages/about/about-page.tsx").read_text()

    assert 'data-about-page="true"' in about
    assert "data-about-section={section.id}" in about
    assert 'title: "About / Privacy"' in about
    assert 'title: "关于 / 隐私"' in about
    assert "portfolio case study" in about
    assert "application evidence" in about
    assert "not as a launched consumer service" in about
    assert "local-only evidence" in about
    assert "Do not put real secrets" in about
    assert "playable state, visible change after a move, and evidence limits" in about
    assert "作品集/申请材料证据" in about
    assert "不是已经上线的" in about
    assert "作品集案例里的互动短剧演示" in about
    assert "AI 互动短剧系统" in about
    assert "AI 叙事运行系统" not in about
    assert "compact AI interactive story" in about
    assert "compact AI story game" not in about
    assert "compact AI narrative runtime" not in about
    assert "类型化数据约束、持久化状态、评审证据" in about
    assert "公开证据预检失败" in about
    assert "标成本地证据" in about
    assert "不要在开场设定、自由输入或私下动机里写真实秘密" in about
    assert "可游玩状态、一次行动后的可见变化和证据边界" in about
    chinese_block = about[about.index("const aboutContentZh") : about.index("const aboutContentEn")]
    for stale in (
        "portfolio case study",
        "AI narrative runtime",
        "typed contracts",
        "reviewer evidence",
        "recovery path",
        "local-only evidence",
        "playable state",
        "visible change",
        "evidence limits",
        "Current System Map",
        "Case Study",
        "inner motive",
        "story seed",
    ):
        assert stale not in chinese_block
    assert "commercial launch" not in about
    assert "hello@tinystories.app" not in about
    assert "Aliyun" not in about
    assert "Qwen" not in about
    assert "DeepSeek" not in about
    assert "provider" not in about
    assert "sell your data" not in about
    assert "出售你的数据" not in about
    assert "legal review" not in about


def test_portfolio_hero_gives_reviewer_a_clear_consumption_order() -> None:
    portfolio = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    hero_copy = portfolio[portfolio.index("<h1>Tiny Stories") : portfolio.index('className="portfolio-hero__actions"')]

    assert "short," in hero_copy
    assert "story-first mobile episode" in hero_copy
    assert "players read a scene" in hero_copy
    assert "compare a" in hero_copy and "few meaningful moves" in hero_copy
    assert "act once" in hero_copy
    assert "follow the consequence" in hero_copy
    assert "75s reviewer cut" in hero_copy
    assert "Reviewer path" in portfolio
    assert "#/reviewer" in portfolio
    assert "portfolio-grade AI" in portfolio
    assert "product-system evidence, not a launched consumer adoption" in portfolio
    assert "claim" in portfolio
    assert "PORTFOLIO_REVIEW_LENS" in portfolio
    assert 'data-portfolio-hero-lens="true"' in portfolio
    assert "data-portfolio-hero-lens-item={item.label}" in portfolio
    assert "Player loop" in portfolio
    assert "Claim boundary" in portfolio
    assert ".portfolio-hero__lens" in theme
    assert 'aria-label="Portfolio evidence points"' in portfolio
    assert 'aria-label="Portfolio proof points"' not in portfolio
    assert "PORTFOLIO_REVIEW_ORDER" in portfolio
    assert "Watch 75s reviewer cut" in portfolio
    assert "Open Reviewer path" in portfolio
    assert "Use #/portfolio -> #/reviewer" in portfolio
    assert "Verify Story Desk start" in portfolio
    assert "Local build only: open a populated Story Desk card" in portfolio
    assert 'localHref: "#/qa/home-start"' in portfolio
    assert "Open local Story Desk start check" in portfolio
    assert "Open local Story Desk start fixture" not in portfolio
    assert "Inspect evidence" in portfolio
    assert 'localHref: "#/qa/play-reviewer-evidence"' in portfolio
    assert "Open local evidence check" in portfolio
    assert "Open local evidence fixture" not in portfolio
    assert "Verify replay artifact" in portfolio
    assert "Local build only: inspect a completed memory" in portfolio
    assert 'localHref: "#/qa/replay"' in portfolio
    assert "Open local replay check" in portfolio
    assert "Open local replay fixture" not in portfolio
    assert "canOpenLocalQaRoute" in portfolio
    assert 'data-portfolio-review-local-evidence={item.step}' in portfolio
    assert ".portfolio-review-order a" in theme
    assert ".portfolio-review-order code" in theme
    assert '<a className="portfolio-action portfolio-action--primary" href={YOUTUBE_DEMO_URL}' in portfolio
    assert "Watch 75s reviewer cut" in portfolio[portfolio.index("portfolio-hero__actions") : portfolio.index('data-portfolio-review-order="true"')]
    assert "portfolio-action portfolio-action--secondary" in portfolio
    assert "Launch reviewer route" in portfolio[portfolio.index("portfolio-action portfolio-action--secondary") : portfolio.index('data-portfolio-review-order="true"')]
    assert 'data-portfolio-hero-evidence-note="true"' in portfolio
    hero_note = portfolio[portfolio.index('data-portfolio-hero-evidence-note="true"') : portfolio.index('className="portfolio-hero__video"')]
    assert "Use the reviewer cut for orientation only" in hero_note
    assert "do not cite the current local route as public evidence until preflight passes" in hero_note
    assert ".portfolio-hero__evidence-note" in theme
    assert 'data-portfolio-review-order="true"' in portfolio
    assert "data-portfolio-review-step={item.step}" in portfolio
    video_idx = portfolio.index('className="portfolio-hero__video"')
    gate_idx = portfolio.index('data-portfolio-public-evidence-gate="true"')
    assert portfolio.index('className="portfolio-hero__actions"') < video_idx < gate_idx
    assert 'data-portfolio-hero-review-frame="true"' in portfolio
    gate_before_order = portfolio[portfolio.index('data-portfolio-public-evidence-gate="true"') : portfolio.index('data-portfolio-review-order="true"')]
    assert 'data-portfolio-public-evidence-gate-summary="true"' in gate_before_order
    assert 'data-portfolio-public-evidence-gate-details="true"' in gate_before_order
    assert "How to verify public links" in gate_before_order
    assert "PORTFOLIO_REVIEWER_CUT_POSTER" in portfolio
    assert "/portfolio/admissions-trailer-contact.jpg" in portfolio
    assert (ROOT / "frontend2/public/portfolio/admissions-trailer-contact.jpg").exists()
    assert "portfolio-video-card" in portfolio
    assert "<iframe" not in portfolio
    assert "YOUTUBE_DEMO_EMBED_URL" not in portfolio
    assert "Start with the reviewer cut" in portfolio
    assert "Open MP4 backup" in portfolio
    assert 'data-portfolio-video-links="true"' in portfolio
    assert 'data-portfolio-video-link="youtube"' in portfolio
    assert 'data-portfolio-video-link="mp4"' in portfolio
    assert "Muted autoplay is best-effort" not in portfolio
    assert "MP4 fallback" not in portfolio
    assert ".portfolio-hero__review" in theme
    assert ".portfolio-review-order" in theme
    assert ".portfolio-video-card" in theme
    assert ".portfolio-video-card__links" in theme
    assert ".portfolio-video-card__links a" in theme
    video_link_style = theme[
        theme.index(".portfolio-video-card__links a {") : theme.index(
            "}", theme.index(".portfolio-video-card__links a {")
        )
    ]
    assert "min-height: 44px" in video_link_style
    assert "display: inline-flex" in video_link_style
    assert "align-items: center" in video_link_style
    assert ".portfolio-video-card__badge" in theme
    assert "grid-template-columns: 34px minmax(0, 1fr)" in theme


def test_root_readme_matches_portfolio_review_path_and_bounds_claims() -> None:
    readme = (ROOT / "README.md").read_text()
    hero_block = readme.split("</p>", 1)[0]

    assert "./docs/demo-video/admissions-trailer-contact.jpg" in hero_block
    assert "product UI and reviewer evidence" in hero_block
    assert "./docs/images/social-preview.jpg" not in hero_block
    readme_top = readme[:readme.index("<table>")]
    assert "short, story-first mobile episode" in readme_top
    assert "read a scene" in readme_top
    assert "compare a few meaningful moves" in readme_top
    assert "act once" in readme_top
    assert "follow visible" in readme_top
    assert "playable 12-turn ending path" in readme_top
    assert "Watch 75s demo" in readme
    assert "Open MP4 demo" in readme
    assert "Inspect source evidence" in readme
    assert "MP4 fallback" not in readme
    assert "offline/fallback" not in readme
    assert "An inspectable AI interactive story, not another story chatbot." in readme
    assert "An inspectable AI story game, not another story chatbot." not in readme
    assert "An inspectable AI narrative runtime" not in readme
    assert "<strong>State-shaped</strong>" in readme
    assert "<strong>Runtime-driven</strong>" not in readme
    assert "## Reviewer Path" in readme
    assert "Run locally and open `#/portfolio`" in readme
    assert "Launch the reviewer route from the portfolio page" in readme
    assert "state/consequence evidence hooks" in readme
    assert "runtime evidence hooks" not in readme
    assert "open `#/qa/replay`" in readme
    assert "deterministic evidence" in readme
    assert "Verify source evidence" in readme
    assert "## Target Player And Content Model" in readme
    assert "story-first players who want a compact mobile" in readme
    assert "not a blank writing canvas, infinite fiction feed, or systems" in readme
    assert "read the current scene, compare a few" in readme
    assert "selected moves preserve the \"why now\" reason" in readme
    assert "inner" in readme and "motive drafting stays attached to the chosen move" in readme
    assert "reviewer evidence stays" in readme
    assert "outside the normal player surface" in readme
    assert "[Current System Map](./docs/CURRENT_SYSTEM_MAP.md)" in readme
    assert "[Case Study](./docs/CASE_STUDY.md)" in readme
    assert "`tests/test_navigation_mental_model_contract.py`" in readme
    assert "`tests/test_play_direction_a_editorial_primitives_contract.py`" in readme
    assert "portfolio-grade AI product-system evidence" in readme
    assert "It is not claimed as a launched consumer" in readme
    assert "game or broad adoption proof" in readme
    reviewer_path = readme[readme.index("## Reviewer Path") : readme.index("## Target Player And Content Model")]
    assert "Evidence visibility gate" in reviewer_path
    assert "before sending a public GitHub Pages or repository" in reviewer_path
    assert "If it fails, use the demo video for orientation" in reviewer_path
    assert "`#/portfolio`" in reviewer_path
    assert "`#/reviewer`" in reviewer_path
    assert "`#/qa/home-start`" in reviewer_path
    assert "`#/qa/replay`" in reviewer_path
    assert "four checks to keep consistent" in reviewer_path
    assert "playable state, one-move" in reviewer_path
    assert "consequence, evidence limits, and replay artifact" in reviewer_path
    assert "local QA routes such as `#/qa/home-start` and `#/qa/replay`" in reviewer_path
    assert "local-only evidence" in reviewer_path
    assert "pushed, deployed, and rechecked" in reviewer_path
    assert "python3 tools/narrative_release_gate.py --mode fake" in readme
    assert "python3 tools/portfolio_public_evidence_preflight.py" in readme
    assert "python3 tools/http_product_smoke.py --base-url http://127.0.0.1:8000" in readme
    assert "python3 -m pip install -e" in readme
    assert "python3 -m pytest -q" in readme
    assert "\npip install -e" not in readme
    assert "\npytest -q" not in readme
    assert "python tools/" not in readme
    assert "python -m tools.rpg_eval" not in readme
    assert "## Engineering Evidence" in readme
    assert "## Engineering Proof" not in readme
    assert "designed game loop" in readme
    assert "designed game runtime" not in readme
    assert "product system around it" in readme
    assert "runtime around it" not in readme
    assert "| Play UI | `frontend2/src/pages/play/`" in readme
    assert "StoryBeat, ActionArea, Advisor, Ending, and reviewer inspector modules" in readme


def test_public_pages_landing_matches_reviewer_evidence_path() -> None:
    landing = (ROOT / "docs/index.html").read_text()
    app_index = (ROOT / "frontend2/index.html").read_text()

    assert "75s reviewer cut" in landing
    assert "Watch 75s demo" in landing
    assert "Open MP4 demo" in landing
    assert "Reviewer path" in landing
    assert "RPG_Demo#reviewer-path" in landing
    assert "#/portfolio -> #/reviewer" in landing
    assert "inspect the checked evidence path" in landing
    assert "Source evidence" in landing
    assert "What reviewers can inspect" in landing
    assert "Four reviewer evidence checks" in landing
    assert "Playable state" in landing
    assert "Locked seed, generated role, turn budget, assets, and first choices." in landing
    assert "Consequence" in landing
    assert "One move should visibly change the room, assets, or next-choice pressure." in landing
    assert "Evidence limits" in landing
    assert "Reviewer evidence stays separate from normal play and public claims need preflight." in landing
    assert "Replay artifact" in landing
    assert "A finished run should become highlights, full read, share, and same-opening restart." in landing
    assert "What the demo proves" not in landing
    assert "docs/CURRENT_SYSTEM_MAP.md" in landing
    assert "MP4 fallback" not in landing
    assert "Muted preview is best-effort" not in landing
    hero_copy = landing[landing.index("<h1>One seed") : landing.index('<div class="tag-row"')]
    assert "short, story-first mobile episode" in hero_copy
    assert "players read one scene" in hero_copy
    assert "compare a few meaningful moves" in hero_copy
    assert "act once" in hero_copy
    assert "follow the visible" in hero_copy
    assert "reviewer path then exposes" in hero_copy
    assert "portfolio-grade AI product-system evidence" in landing
    assert "not a" in landing
    assert "launched consumer game or broad adoption proof" in landing
    assert "Who this loop is for" in landing
    assert "story-first players who want a compact" in landing
    assert "read the scene, compare a few meaningful moves, act" in landing
    assert "Target player" in landing
    assert "Content rhythm" in landing
    assert "UI promise" in landing
    assert "not a blank writing canvas or a dashboard" in landing
    assert "Keep story context near decisions" in landing
    assert "system map, reviewer path, contracts, and tests" in landing
    assert "python3 tools/portfolio_public_evidence_preflight.py" in landing
    assert "local commits ahead of public main" in landing
    assert "missing Pages" in landing
    assert "use the demo video for orientation only" in landing
    assert "Do not cite the" in landing
    assert "current Portfolio, Reviewer, Story Desk, Create, Play, or Replay" in landing
    assert "routes as public evidence" in landing
    assert "deployed" in landing and "rechecked" in landing and "preflight passes" in landing
    assert ".proof-checks" in landing
    assert ".proof-check" in landing
    assert ".audience-model" in landing
    assert ".audience-model__grid" in landing
    assert ".evidence-boundary" in landing
    assert ".video-actions span:last-child" in landing
    assert '<meta property="og:image" content="/og-share.jpg" />' in app_index
    assert '<meta name="twitter:image" content="/og-share.jpg" />' in app_index
    assert "product UI and reviewer evidence contact sheet" in app_index
    assert 'og:image:alt" content="Tiny Stories — interactive drama in 12 turns"' not in app_index


def test_source_evidence_docs_are_reviewable_and_bound_claims() -> None:
    case_study = (ROOT / "docs/CASE_STUDY.md").read_text()
    system_map = (ROOT / "docs/CURRENT_SYSTEM_MAP.md").read_text()
    evidence_packet = (ROOT / "docs/tiny-stories-engineering-evidence-packet.md").read_text()

    assert "Read this as source evidence after the 75s demo and `#/portfolio` page" in case_study
    assert "what reviewers can inspect" in case_study
    assert "where that evidence lives" in case_study
    assert "what the project proves" not in case_study
    assert "bounded 12-turn session" in case_study
    assert "8-20 turn" not in case_study
    assert "playable, inspectable story system" in case_study
    assert "playable, inspectable runtime" not in case_study
    assert "evidence path to see the state machine" in case_study
    assert "inspector path to see the state machine" not in case_study
    assert "## Evidence To Inspect" in case_study
    assert "`docs/CURRENT_SYSTEM_MAP.md`" in case_study
    assert "`frontend2/src/pages/portfolio/`, `#/portfolio`, `#/reviewer`" in case_study
    assert "guided evidence surface" in case_study
    assert "guided proof surface" not in case_study
    assert "Is the play contract typed and inspectable?" in case_study
    assert "Is the runtime contract typed and inspectable?" not in case_study
    assert "`rpg_backend/narrative/contracts.py`, `frontend2/src/api/contracts.ts`" in case_study
    assert "`tests/test_navigation_mental_model_contract.py`, `tests/test_play_direction_a_editorial_primitives_contract.py`" in case_study
    assert "portfolio-grade AI product-system evidence" in case_study
    assert "inspect state and consequence decisions quickly" in case_study
    assert "inspect runtime decisions quickly" not in case_study
    assert "not a validated consumer" in case_study
    assert "broad adoption proof" in case_study

    assert "source-evidence companion to the README, GitHub Pages demo" in system_map
    assert "what path is current, what code backs it" in system_map
    assert "provenance rather than the demo being claimed" in system_map
    assert "current" in system_map
    assert "portfolio-facing product path is intentionally narrow" in system_map
    assert "not required to run or review the demo" in system_map
    assert "python3 tools/narrative_release_gate.py --mode fake" in system_map
    assert "python3 -m pytest -q" in system_map

    assert "`frontend2/src/pages/play/components/runtime-inspector.tsx`" in evidence_packet
    assert "These were local" in evidence_packet
    assert "not public links shipped in this repository" in evidence_packet
    assert "Current source/local-reviewable evidence" in evidence_packet
    assert "`docs/CURRENT_SYSTEM_MAP.md`" in evidence_packet
    assert "`docs/CASE_STUDY.md`" in evidence_packet
    assert "`#/portfolio`" in evidence_packet
    assert "`#/reviewer`" in evidence_packet
    assert "Treat these as public" in evidence_packet
    assert "evidence only after the public visibility preflight passes" in evidence_packet
    assert "Public visibility check" in evidence_packet
    assert "python3 tools/portfolio_public_evidence_preflight.py" in evidence_packet
    assert "local `HEAD` is ahead of `origin/main`" in evidence_packet
    assert "GitHub Pages is missing" in evidence_packet
    assert "current markers" in evidence_packet
    assert "treat the evidence as local-only" in evidence_packet
    assert "pushed, deployed, and rechecked" in evidence_packet
    assert "/tmp/tiny-stories-opening-live-reliability" not in evidence_packet
    assert "snapshot/story-brief-opening-live-reliability" not in evidence_packet
    evidence_contracts = evidence_packet[
        evidence_packet.index("Judge and reviewer evidence contracts:")
        : evidence_packet.index("- Live evaluation harness:")
    ]
    assert "play-flow-panels.tsx" not in evidence_contracts


def test_chinese_readme_matches_portfolio_evidence_framing() -> None:
    readme = (ROOT / "README.zh.md").read_text()
    hero_block = readme.split("</p>", 1)[0]

    assert "./docs/demo-video/admissions-trailer-contact.jpg" in hero_block
    assert "product UI and reviewer evidence" in hero_block
    assert "./docs/images/hero.jpg" not in hero_block
    readme_top = readme[:readme.index("## 项目状态")]
    assert "移动端短篇互动剧情" in readme_top
    assert "先读场景" in readme_top
    assert "比较少量选择" in readme_top
    assert "行动一次" in readme_top
    assert "跟随后果" in readme_top
    assert "status-portfolio_case_study" in readme
    assert "Status: Paused" not in readme
    assert "status-paused" not in readme
    assert "alpha / open-source preview" not in readme
    assert "portfolio-grade AI product-system evidence" in readme
    assert "类型化契约、持久化游玩记录、可检查评审路径" in readme
    assert "typed contracts、持久化 session" not in readme[: readme.index("## 60 秒 Quickstart")]
    assert "不是已经验证过的消费级游戏或大规模用户增长案例" in readme
    assert "真实用户需求、复玩、留存和自然分享没有被证明" in readme
    assert "## Demo" in readme
    assert "[观看 75 秒 demo](https://youtu.be/RRJ7uyjW_nA)" in readme
    assert "[打开 MP4 备份](./docs/demo-video/tiny-stories-admissions-demo-readme.mp4)" in readme
    assert "[preflight 通过后再打开 GitHub Pages 展示页](https://lishehao.github.io/RPG_Demo/)" in readme
    assert "视频用于快速理解玩家看到的 loop" in readme
    assert "真正的申请材料证据仍然在 source、tests" in readme
    assert "engineering evidence packet" in readme
    assert "python3 tools/portfolio_public_evidence_preflight.py" in readme
    assert "本地 `HEAD`" in readme
    assert "GitHub Pages 缺少当前 marker" in readme
    assert "local-only" in readme
    assert "目标分支 push、部署并重新检查通过" in readme
    assert "## 申请 / 作品集审阅路径" in readme
    assert "一个可检查的 AI 互动短剧" in readme
    assert "An inspectable AI interactive story" in readme
    assert "An inspectable AI story game" not in readme
    assert "LLM 驱动的 12 回合互动博弈剧引擎" not in readme
    assert "`#/portfolio`" in readme
    assert "`#/reviewer`" in readme
    assert "`#/qa/home-start`" in readme
    assert "`#/qa/replay`" in readme
    assert "四个检查点要保持一致" in readme
    assert "状态/后果证据钩子" in readme
    assert "runtime evidence hooks" not in readme
    assert "可游玩状态、一次行动后的后果、证据边界、回放作品" in readme
    assert "可游玩状态、一次行动后的后果、证据边界、回放 artifact" not in readme
    assert "已完成局的回放作品" in readme
    assert "completed-run replay artifact" not in readme
    assert "local QA evidence" in readme
    assert "不要当作公开链接证据" in readme
    assert "## 目标玩家 / 内容消费模型" in readme
    assert "短篇互动剧情的 story-first player" in readme
    assert "不是空白写作工具用户、无限小说流用户或系统 dashboard 用户" in readme
    assert "先读当前场景,比较少量但有意义的选择" in readme
    assert "普通 Play 页面要把剧情上下文和决策上下文放近" in readme
    assert "内心动机要贴在已选行动上" in readme
    assert "inner motive 要贴在已选 move 上" not in readme
    assert "reviewer" in readme and "普通玩家界面之外" in readme
    assert "Tiny Stories 会把它整理成一个可玩的短篇互动剧" in readme
    assert "一次行动后的后果" in readme
    assert "可检查证据边界" in readme
    assert "ending + highlights/replay + reviewer 可检查证据边界" in readme
    assert "申请材料价值不在于声称已经有 consumer traction" in readme
    assert "可运行的 player loop" in readme
    assert "类型化契约、持久化游玩记录、评审证据和回放作品能互相对上" in readme
    assert "typed contracts、持久化 session、reviewer evidence 和 replay artifact 能互相对上" not in readme
    assert "系统先整理故事计划" in readme
    assert "系统先整理 Story Brief" not in readme[: readme.index("## 60 秒 Quickstart")]
    assert "seed → 故事计划 → role + scene + choices" in readme
    assert "replay artifact" not in readme[: readme.index("## 60 秒 Quickstart")]
    assert "人物压力、行动后果" in readme
    assert "NPC 压力" not in readme[: readme.index("## 60 秒 Quickstart")]
    assert "scene → choice → consequence → replay flow" in readme
    assert "具体机制和数量边界放在下面的架构章节里" in readme
    assert "可复制分享的结局标签" in readme
    assert "可发朋友圈" not in readme
    top_sections = readme[: readme.index("## 60 秒 Quickstart")]
    assert "9 层机制" not in top_sections
    assert "15 ending labels" not in top_sections
    assert "15 种 label" not in top_sections
    assert "3-5 张玩家身份卡" not in top_sections
    assert "2-3 张\"你没走过的路\"" not in top_sections
    assert "[Current System Map](./docs/CURRENT_SYSTEM_MAP.md)" in readme
    assert "[Case Study](./docs/CASE_STUDY.md)" in readme
    assert "[Engineering Evidence Packet](./docs/tiny-stories-engineering-evidence-packet.md)" in readme
    assert "portfolio case study / open-source preview" in readme
    assert "机制链路完整" in readme
    assert "机制层面成熟" not in readme
    assert "consumer traction" in readme
    assert "Play 容器 + StoryBeat / ActionArea / Advisor / Ending 等模块" in readme
    assert "play-page.tsx (~2400 行,所有 turn UI 在这)" not in readme


def test_portfolio_page_separates_public_and_local_evidence_claims() -> None:
    portfolio = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    assert "PORTFOLIO_TARGET_USER_MODEL" in portfolio
    assert 'data-portfolio-target-user-model="true"' in portfolio
    assert "Who this loop is for" in portfolio
    assert "Target player" in portfolio
    assert "story-first players who want a compact mobile drama" in portfolio
    assert "not a blank writing canvas or a dashboard" in portfolio
    assert "Content rhythm" in portfolio
    assert "Read the current scene, compare a few meaningful moves" in portfolio
    assert "UI promise" in portfolio
    assert "Keep narrative context and decision context together" in portfolio
    assert "reviewer evidence separate from the normal player surface" in portfolio
    assert "PORTFOLIO_EVIDENCE_BOUNDARY" in portfolio
    assert 'data-portfolio-evidence-boundary="true"' in portfolio
    assert 'data-portfolio-source-evidence="true"' in portfolio
    assert "Public artifact" in portfolio
    assert "Checked reviewer path" in portfolio
    assert "Live reviewer path" not in portfolio
    assert "live Reviewer path" not in portfolio
    assert "Not claimed" in portfolio
    assert "Source evidence" in portfolio
    assert "review code, docs, tests, and the" in portfolio
    assert "narrow product path behind this demo" in portfolio
    assert "public-main" in portfolio
    assert "may lag the current local build" in portfolio
    assert "Public repo and Pages links can lag this local build" in portfolio
    assert "In the checked build, the Reviewer route lets evaluators inspect" in portfolio
    assert "If preflight fails, use the reviewer cut for orientation only" in portfolio
    assert "Before relying on" in portfolio
    assert "public links" in portfolio
    assert "run the public-evidence preflight" in portfolio
    assert "python3 tools/portfolio_public_evidence_preflight.py" in portfolio
    assert "do not cite the current Portfolio, Reviewer path, Story Desk, Create, Play, or Replay" in portfolio
    assert "routes as public evidence until the intended branch is pushed, deployed, rechecked, and the preflight passes" in portfolio
    assert "use the reviewer cut for orientation only" in portfolio
    assert "do not cite the" in portfolio and "current local route as public evidence until preflight passes" in portfolio
    assert "label this Portfolio" not in portfolio
    assert "local route as local-only evidence" not in portfolio
    assert "GitHub repo" in portfolio
    assert "System map" in portfolio
    assert "Evidence packet" in portfolio
    assert 'PUBLIC_REPO_URL = "https://github.com/lishehao/RPG_Demo"' in data
    assert 'SYSTEM_MAP_URL = "https://github.com/lishehao/RPG_Demo/blob/main/docs/CURRENT_SYSTEM_MAP.md"' in data
    assert "EVIDENCE_PACKET_URL" in data
    assert "https://github.com/lishehao/RPG_Demo/blob/main/docs/tiny-stories-engineering-evidence-packet.md" in data
    assert "portfolio-grade AI product-system evidence" in portfolio
    assert "Evidence map" in portfolio
    assert "System Inspector" not in portfolio
    assert "portfolio-grade AI product-system case study" in portfolio
    assert "portfolio-grade AI runtime case study" not in portfolio
    assert "not proof of a launched consumer product or broad user adoption" in portfolio
    assert "product-system evidence, not" in portfolio
    assert "story generation" in portfolio
    assert "raw generation" not in portfolio
    assert "reliable AI product surface" not in portfolio
    assert ".portfolio-target-user" in theme
    assert ".portfolio-target-user__grid" in theme
    assert ".portfolio-target-user__item" in theme
    assert ".portfolio-target-user__grid" in theme[theme.index("@media (max-width: 720px)") :]
    assert ".portfolio-evidence-boundary" in theme
    assert ".portfolio-evidence-boundary__grid" in theme
    assert ".portfolio-source-evidence" in theme
    assert 'data-portfolio-hero-review-frame="true"' in portfolio
    assert portfolio.index('className="portfolio-hero__video"') < portfolio.index('data-portfolio-public-evidence-gate="true"')
    assert ".portfolio-public-evidence-gate details" in theme
    assert ".portfolio-public-evidence-gate summary" in theme
    assert ".portfolio-public-evidence-gate code" in theme


def test_case_study_states_target_player_and_content_model() -> None:
    case_study = (ROOT / "docs/CASE_STUDY.md").read_text()

    assert "## Target Player And Content Model" in case_study
    assert "story-first players who want a short interactive drama" in case_study
    assert "especially on mobile" in case_study
    assert "blank writing tool" in case_study
    assert "read the current scene, compare a few meaningful moves, act once" in case_study
    assert "use that consequence to choose the next beat" in case_study
    assert "make the \"why now\" reason visible" in case_study
    assert "private motive drafting attached to the selected move" in case_study
    assert "reviewer evidence separate from the normal player surface" in case_study
    assert "not proof" in case_study
    assert "validated retention or broad demand" in case_study


def test_portfolio_proofbar_uses_reviewer_verifiable_metrics() -> None:
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()

    assert "Locked seed" in data
    assert "same premise for every reviewer run" in data
    assert "12-turn episode" in data
    assert "bounded story budget visible in Play" in data
    assert "12-turn cap" not in data
    assert "4 review checks" in data
    assert "playable state, consequence, evidence limits, replay artifact" in data
    assert "4 checks" not in data
    assert "3 checks" not in data
    assert "playable state, state change, checks boundary" not in data
    assert "playable state, state change, archived checks" not in data
    assert "playable state, visible change after a move, and the evidence limits" in data
    assert "whether archived judge checks exist" not in data
    assert "Replay loop" in data
    assert "ending can be shared or restarted" in data
    assert "5 layers" not in data
    assert "EN first" not in data


def test_portfolio_reviewer_seed_framing_matches_locked_seed() -> None:
    portfolio = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()
    reviewer = (ROOT / "frontend2/src/pages/portfolio/reviewer-page.tsx").read_text()
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()

    assert 'REVIEWER_DEMO_TITLE = "The Missing Singer Broadcast"' in data
    assert "awards livestream" in data
    assert "singer Seo Mina disappears" in data
    assert "sponsor director" in data
    assert "no violence and no blackmail" in data
    assert "Missing singer, live awards stream, sponsor pressure" in reviewer
    assert "Prepares a temporary reviewer session when the demo needs one" in reviewer
    assert "evidence summary reviewers inspect beside play" in reviewer
    assert "playable state and the first" in reviewer
    assert "consequence after a move" in reviewer
    assert 'aria-label="Reviewer evidence path"' in reviewer
    assert "Reviewer proof path" not in reviewer
    assert "playable state and consequences" not in reviewer
    assert "reviewer-only evidence summary beside the normal story UI" in reviewer
    assert 'data-reviewer-local-evidence-note="true"' in reviewer
    assert "Public evidence boundary: inspect the current local build here" in reviewer
    assert "application links, cite this route only after Portfolio preflight" in reviewer
    assert "passes; otherwise use the reviewer cut" in reviewer
    local_note_idx = reviewer.index('data-reviewer-local-evidence-note="true"')
    launch_cta_idx = reviewer.index('data-reviewer-launch-cta={busy ? "starting" : "ready"}')
    assert local_note_idx < launch_cta_idx
    assert "canOpenLocalQaRoute" in reviewer
    assert 'data-reviewer-local-evidence-fixture-link="true"' in reviewer
    assert 'data-reviewer-launch-error-local-proof="true"' in reviewer
    assert "Open local evidence check" in reviewer
    assert "Open local evidence fixture" not in reviewer
    assert "evidence-enabled reviewer account" not in reviewer
    assert "inspector data" not in reviewer
    assert "Evidence limits" in reviewer
    assert "Consequence after one move" in reviewer
    assert "The opening shows playable setup; consequence evidence waits until the run produces it" in reviewer
    assert "Replay artifact" in reviewer
    assert "A completed run should become highlights, Full read, and same-opening restart evidence." in reviewer
    assert "Live state is visible immediately" not in reviewer
    assert "Checks boundary" not in reviewer
    assert "archived judge checks" not in reviewer
    launch_error_block = reviewer[
        reviewer.index("if (!error) return")
        : reviewer.index("}, [error])")
    ]
    assert 'data-reviewer-launch-error="true"' in reviewer
    assert 'behavior: "auto"' in launch_error_block
    assert 'block: "center"' in launch_error_block
    assert 'behavior: prefersReducedMotion ? "auto" : "smooth"' not in launch_error_block
    assert "live awards stakes" in portfolio
    assert "missing singer" in portfolio
    assert "sponsor pressure" in portfolio
    assert "witness and reporter tension" in portfolio

    stale_seed_terms = (
        "The Merger Betrayal",
        "business betrayal",
        "an ex with proof",
        "secret merger",
    )
    for stale in stale_seed_terms:
        assert stale not in portfolio
        assert stale not in data


def test_demo_video_script_separates_trailer_seed_from_live_reviewer_seed() -> None:
    script = (ROOT / "docs/demo-video/portfolio-demo-script.md").read_text()

    assert "Demo Story Seed And Live Reviewer Seed" in script
    assert "The recorded trailer and the live reviewer route serve different review jobs" in script
    assert "Use one polished English seed throughout the recorded video" in script
    assert "Use the current live reviewer route seed for `#/portfolio` / `#/reviewer`" in script
    assert "At my wedding, the groom asks me to sign away my shares before the ceremony starts." in script
    assert "singer Seo Mina disappears" in script
    assert "no violence and no blackmail" in script
    assert "the Missing Singer Broadcast seed matches the live" in script
    assert "reviewer route and current portfolio page" in script
    assert "`#/portfolio`, launch `#/reviewer`" in script
    assert "clear product evidence" in script
    assert "Portfolio evidence:" in script
    assert "### 1:18-1:28 - Ending Evidence" in script
    assert "Small evidence line:" in script
    assert "ending evidence" in script
    assert "opening evidence" in script

    for stale in (
        "my cofounder announces a secret merger",
        "secret merger that cuts me out",
        "Backup seed if the live run",
        "clear product proof",
        "Portfolio proof:",
        "### 1:18-1:28 - Ending Proof",
        "Small proof line:",
        "ending proof",
        "opening proof",
    ):
        assert stale not in script


def test_portfolio_inspector_uses_reviewer_verifiable_capability_labels() -> None:
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()

    for expected in (
        "Seed becomes setup",
        "Role creates stakes",
        "Choices change state",
        "Advisor stays separate",
        "Ending becomes replay",
        "playable state, visible change after a move, and the evidence limits",
    ):
        assert expected in data

    for old_internal_label in (
        "Seed Router",
        "Playable Role Model",
        "Stateful Consequences",
        "Advisor Channel",
        "Ending Compiler",
        "LLM-mediated",
        "playable state, state change, and whether archived judge checks exist",
    ):
        assert old_internal_label not in data


def test_portfolio_loop_maps_each_state_to_visible_evidence() -> None:
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()
    portfolio = (ROOT / "frontend2/src/pages/portfolio/portfolio-page.tsx").read_text()

    for expected in (
        "visible evidence: locked seed and generated opening",
        "visible evidence: role panel, objective, assets",
        "visible evidence: next moves, character reactions, story items",
        "visible evidence: ending, highlights, replay link",
        "artifact each state leaves behind",
    ):
        assert expected in data or expected in portfolio

    assert "visible evidence: next moves, pulse, inventory" not in data

    assert "not just admire generated images" not in portfolio
    assert "secret merger · awards livestream · ex with proof" not in data


def test_portfolio_inspector_tabs_keep_mobile_touch_targets() -> None:
    theme = (ROOT / "frontend2/src/app/theme.css").read_text()

    tab_rule = theme[
        theme.index(".portfolio-inspector__tabs button {") : theme.index(
            ".portfolio-inspector__tabs button span {"
        )
    ]

    assert "min-height: 44px;" in tab_rule
    assert "align-items: center;" in tab_rule


def test_portfolio_case_study_points_are_evidence_oriented() -> None:
    data = (ROOT / "frontend2/src/pages/portfolio/portfolio-data.ts").read_text()

    for expected in (
        "player role, state changes, and ending evidence",
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
    assert '"home.hero_sub": "Choose a playable story, reopen saved runs, or write a new opening; each compact episode branches through role, pressure, and visible consequences."' in strings
    assert "each 15 min episode" not in strings
    assert "每局约 15 分钟" not in strings
    assert "home.hero_bullet_" not in home
    assert "home.hero_bullet_" not in strings
    assert "home.cta_portfolio" not in home
    assert "home.cta_portfolio" not in strings
    assert 'data-home-footer="true"' in home
    assert 'data-home-footer-link="portfolio"' in home
    assert 'data-home-footer-link="source"' in home
    footer_style = home[home.index("footer: {") : home.index("footerBrand:", home.index("footer: {"))]
    footer_link_style = home[home.index("footerLink: {") : home.index("},", home.index("footerLink: {"))]
    assert 'flexWrap: "wrap"' in footer_style
    assert "minHeight: 44" in footer_link_style
    assert "minWidth: 44" in footer_link_style
    assert 'display: "inline-flex"' in footer_link_style
    assert 'alignItems: "center"' in footer_link_style
    assert "onOpenCreate={onOpenCreate}" in home
    assert 'data-home-empty-create="true"' in home
    assert "SOURCE_REPO_URL" in home
    assert "https://github.com/lishehao/RPG_Demo" in home
    assert 't("home.footer_source")' in home
    assert "mailto:hello@tinystories.app" not in home
    assert "home.footer_contact" not in home
    assert "home.footer_contact" not in strings
    assert '"home.footer_source": "Source"' in strings
    assert '"home.footer_source": "源码"' in strings
    assert 'data-home-empty-my-create="true"' in home
    assert 'data-home-plaza-error-create="true"' in home
    assert 'data-home-start-error-create="true"' in home
    assert 'data-home-my-stories-error-create="true"' in home
    assert 'data-home-saved-runs-error-create="true"' in home
    assert "setMySessionsError(t(\"home.error_saved_runs\"))" in home
    assert "setMyTemplatesError(t(\"home.error_my_stories\"))" in home
    assert "error={myTemplatesError}" in home
    assert "hpStyles.errorRecovery" in home
    assert "hpStyles.emptyAction" in home
    assert 'height: "clamp(118px, 18vw, 180px)"' in home
    assert 'setError(t("home.error_plaza"))' in home
    assert '"home.tab_plaza": "Playable stories"' in strings
    assert '"home.tab_plaza": "可玩故事"' in strings
    assert '"home.tab_plaza": "Plaza"' not in strings
    assert '"home.tab_plaza": "广场"' not in strings
    assert '"home.empty_plaza": "No playable stories yet. Write a new opening to start your own episode, or come back when more stories are available."' in strings
    assert "come back when the plaza has one" not in strings
    assert '"home.empty_plaza": "No public stories yet. Write one for everyone to play?"' not in strings
    assert '"home.empty_plaza": "还没有可玩的故事。可以先写一个新开场，开始自己的这一集；也可以稍后回来继续选。"' in strings
    assert '"home.empty_plaza": "还没有公开作品.写一个让所有人来玩?"' not in strings
    assert '"home.empty_my": "No stories of your own yet. Write a new opening to start one here."' in strings
    assert "\"home.empty_my\": \"You haven't created a story yet.\"" not in strings
    assert '"home.empty_my": "你还没有自己的故事。写一个新开场，就会从这里开始。"' in strings
    assert '"home.empty_my": "你还没有创建过故事."' not in strings
    assert '"home.error_my_stories": "Your stories did not open this time. You can still write a new opening, or come back in a moment."' in strings
    assert '"home.error_my_stories": "你的故事暂时没有打开。可以先写一个新开场，或稍后回来继续看。"' in strings
    assert '"home.error_saved_runs": "Saved runs did not open this time. You can still choose a story below, or write a new opening."' in strings
    assert '"home.error_saved_runs": "已保存的局这次没有打开。下面仍可选故事，也可以先写一个新开场。"' in strings
    assert '"home.error_plaza": "The story list did not open. You can still write a new story, or come back in a moment."' in strings
    assert '"home.error_plaza": "The story list did not open. You can still write a new story above, or come back in a moment."' not in strings
    assert '"home.error_start_story": "This story did not open this time. The card is still here; press Start episode again, or write a new story."' in strings
    assert '"home.error_start_story": "This story did not open this time. The card is still here; press Start episode again, or write a new story above."' not in strings

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
    back_link_style = login[login.index("backLink: {") : login.index("brandLink:", login.index("backLink: {"))]
    brand_link_style = login[login.index("brandLink: {") : login.index("main:", login.index("brandLink: {"))]
    quick_start_style = login[
        login.index("quickStartButton: {") : login.index("quickStartButtonCompact:", login.index("quickStartButton: {"))
    ]
    custom_name_style = login[login.index("customNameToggle: {") : login.index("orLine:", login.index("customNameToggle: {"))]
    submit_style = login[login.index("submitAction: {") : login.index("note:", login.index("submitAction: {"))]

    assert "CREATE_GUEST_PLAN_KEYS" in login
    assert 'isCreateEntry ? t("login.tag_create") : t("login.tag")' in login
    assert 'data-login-guest-plan="true"' in login
    assert "data-login-guest-plan-item={key}" in login
    assert 't("login.guest_plan_label")' in login
    assert '"login.tag": "Sign in"' in strings
    assert '"login.tag_create": "Pen name"' in strings
    assert '"login.tag": "登录"' in strings
    assert '"login.tag_create": "保存笔名"' in strings
    assert '"login.guest_plan_editor": "Opens the story editor without email or password."' in strings
    assert '"login.guest_plan_saved": "Saves this draft and later runs under the same pen name."' in strings
    assert '"login.guest_plan_custom": "You can still choose your own pen name when it matters."' in strings
    assert '"login.guest_plan_editor": "进入故事编辑器，不需要邮箱或密码。"' in strings
    assert '"login.guest_plan_saved": "这次创作和之后的游玩会挂在这个笔名下。"' in strings
    assert '"login.guest_plan_custom": "想认真命名时，也可以改成自己的笔名。"' in strings
    assert '"login.note": "Local demo pen name only — no password, no email; it saves stories and runs on this device."' in strings
    assert '"login.note": "这是本地 Demo 笔名,没有密码、没有邮箱;用来保存你在这个设备上的故事和游玩记录."' in strings
    assert '"login.error_generic": "This pen name did not open. It is still here; retry, or go back to Story Desk."' in strings
    assert '"login.error_generic": "这次没有进入。笔名还在这里；可以重试，或回 Story Desk。"' in strings
    assert "Real auth coming next month" not in strings
    assert "下个月会改成正式登录" not in strings
    for style in (back_link_style, brand_link_style, custom_name_style, submit_style):
        assert "minHeight: 44" in style
        assert 'display: "inline-flex"' in style
        assert 'alignItems: "center"' in style
    assert "minWidth: 44" in submit_style
    assert "minHeight: 54" in quick_start_style
    assert 'alignItems: "center"' in quick_start_style


def test_existing_play_world_replay_page_navigation_stays_top_level() -> None:
    play = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    play_panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    world = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()
    replay = (ROOT / "frontend2/src/pages/replay/replay-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert 't("play.back_home")' in play_panels
    assert 't("play.back_home_short")' in play_panels
    assert '"play.back_home": "← Story Desk"' in strings
    assert '"play.back_home_short": "← Story Desk"' in strings
    assert '"play.back_home": "← 故事入口"' in strings
    assert '"play.back_home_short": "← 故事入口"' in strings
    assert '"play.back_home_short": "← Home"' not in strings
    assert '"world.crumb_back_home": "← Story Desk"' in strings
    assert '"world.crumb_back_home": "← 故事入口"' in strings
    assert 'data-world-template-error="true"' in world
    assert 'data-world-template-error-back="true"' in world
    assert 'hint={t("world.empty_detail")}' in world
    assert "hint={error}" not in world
    world_empty_action_start = world.index("emptyAction: {")
    world_empty_action_end = world.index("startAction:", world_empty_action_start)
    world_empty_action = world[world_empty_action_start:world_empty_action_end]
    assert 'display: "inline-flex"' in world_empty_action
    assert 'alignItems: "center"' in world_empty_action
    assert "minHeight: 44" in world_empty_action
    assert '"world.empty_detail": "This story may be private, deleted, or temporarily unavailable. Return to Story Desk to find saved runs, choose another story, or write a new opening."' in strings
    assert '"world.empty_back": "Story Desk"' in strings
    assert '"world.empty_back": "Back to plaza"' not in strings
    assert '"world.empty_detail": "这个故事可能已变为私有、被删除，或暂时没有打开。回到故事入口后，可以找已保存的局、选别的故事，或写一个新开场。"' in strings
    assert '"world.empty_back": "故事入口"' in strings
    assert 'createVariant="link" showBackButton' in world
    hero_start = world.index("{/* Hero:")
    main_start = world.index("<main", hero_start)
    assert 't("world.crumb_back_home")' not in world[hero_start:main_start]
    assert 't("replay.crumb_back_home")' in replay
    assert '"replay.crumb_back_home": "← Story Desk"' in strings
    assert '"replay.crumb_back_home": "← 故事入口"' in strings
    assert '"replay.crumb_back_home": "← Back home"' not in strings
    assert '"replay.crumb_back_home": "← 回到首页"' not in strings
    assert 'data-replay-error="true"' in replay
    assert 'data-replay-error-back="true"' in replay
    assert 't("replay.error_detail")' in replay
    assert "hint={error}" not in replay
    assert "friendlyError" not in replay
    replay_primary_action_start = replay.index("primaryAction: {")
    replay_primary_action_end = replay.index("main:", replay_primary_action_start)
    replay_primary_action = replay[replay_primary_action_start:replay_primary_action_end]
    assert 'display: "inline-flex"' in replay_primary_action
    assert 'alignItems: "center"' in replay_primary_action
    assert "minHeight: 44" in replay_primary_action
    for style_name in ("crumb", "viewModeAction", "readModeAction", "ctaTextButton", "ctaTextButtonMuted"):
        style_start = replay.index(f"{style_name}: {{")
        style_end = replay.index("},", style_start)
        style_block = replay[style_start:style_end]
        assert 'display: "inline-flex"' in style_block
        assert 'alignItems: "center"' in style_block
        assert "minHeight: 44" in style_block
        assert "minWidth: 44" in style_block
    assert '"replay.error_detail": "This shared memory may be private, deleted, or temporarily unavailable. Return to Story Desk to find saved runs, choose another story, or write a new opening."' in strings
    assert '"replay.error_back_plaza": "Story Desk"' in strings
    assert '"replay.error_back_plaza": "Back to plaza"' not in strings
    assert '"replay.error_detail": "这条回放可能已变为私有、被删除，或暂时没有打开。回到故事入口后，可以找已保存的局、选别的故事，或写一个新开场。"' in strings
    assert '"replay.error_back_plaza": "故事入口"' in strings
    assert 'data-replay-hero-fork-hint="true"' in replay
    assert 't("replay.cta_hint")' in replay
    assert "heroCtaHint" in replay


def test_world_role_launch_has_ready_and_starting_feedback() -> None:
    world = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert 'type TemplateErrorContext = "load" | "start" | "visibility" | null' in world
    assert 'setErrorContext("start")' in world
    assert 'data-world-role-launch-state={busy ? "starting" : "ready"}' in world
    assert 'data-world-role-launch-cta={busy ? "starting" : "ready"}' in world
    assert 'startError={errorContext === "start" ? error : null}' in world
    assert 'data-world-role-launch-recovery="true"' in world
    assert 't("world.role_start_error_title")' in world
    assert 't("world.role_start_error_detail")' in world
    assert "roleLaunchPanelStarting" in world
    assert "roleLaunchButtonStarting" in world
    role_launch_button = world[
        world.index("roleLaunchButton: {"):
        world.index("roleLaunchButtonStarting: {")
    ]
    assert "minHeight: 44" in role_launch_button
    assert "roleLaunchRecovery" in world
    assert "cursor: \"progress\"" in world
    assert '"world.role_start_error_title": "The story did not open this time"' in strings
    assert '"world.role_start_error_detail": "The same opening and selected role are still here. Press Start this run again, or choose another identity first."' in strings
    assert '"world.role_start_error_title": "这次没有进入故事"' in strings
    assert '"world.role_start_error_detail": "同一个开场和已选身份还在；可以再次点击「开始这一局」，或先换一个身份。"' in strings


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
    assert 'data-world-visibility-recovery="true"' in world
    assert 't("world.visibility_error_title")' in world
    assert 't("world.visibility_error_detail")' in world
    assert 'errorContext !== "visibility"' in world
    assert '"world.visibility_current": "当前：{label}"' in strings
    assert '"world.visibility_private_desc": "只有你能看到并继续测试这个故事。"' in strings
    assert '"world.visibility_unlisted_desc": "拿到链接的人可以打开并玩出自己的版本。"' in strings
    assert '"world.visibility_public": "公开展示"' in strings
    assert '"world.visibility_public_desc": "故事会出现在故事入口的可玩故事列表，任何玩家都能开始一局。"' in strings
    assert "故事会出现在广场" not in strings
    assert '"world.visibility_error_title": "这次没有改成新的可见性"' in strings
    assert '"world.visibility_error_detail": "当前设置没有变化；可以再点一次目标可见性，或先保留现在的设置。"' in strings
    assert '"world.visibility_current": "Current: {label}"' in strings
    assert '"world.visibility_private_desc": "Only you can see and keep testing this story."' in strings
    assert '"world.visibility_unlisted_desc": "People with the link can open it and play their own run."' in strings
    assert '"world.visibility_public": "Public on Story Desk"' in strings
    assert '"world.visibility_public_desc": "The story appears in Story Desk\'s playable stories list so anyone can start a run."' in strings
    assert "appears in the plaza" not in strings
    assert '"world.visibility_error_title": "Visibility did not change"' in strings
    assert '"world.visibility_error_detail": "The current setting is unchanged. Try the same visibility choice again, or keep the current setting."' in strings


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
    assert 'data-replay-advisor-archive-hint="true"' in replay
    assert 't("replay.advisor_archive_hint")' in replay
    assert "replay.advisor_messages.length > 0" in replay
    assert 'data-replay-advisor-track="true"' in replay
    assert "data-replay-advisor-exchanges={replay.advisor_messages.length}" in replay
    assert "data-replay-advisor-message-role={m.role}" in replay
    assert "viewModeHint" in replay
    assert "viewModeAdvisorHint" in replay
    assert 'data-replay-preview-why="true"' in replay
    assert 't("replay.preview_why_label")' in replay
    assert "previewRecordWhyLabel" in replay
    assert '"replay.view_mode_hint": "先看关键转折；想细读时切到完整故事。"' in strings
    assert '"replay.view_mode_hint": "Start with the key turns; switch to full when you want every beat."' in strings
    assert '"replay.advisor_archive_hint": "完整阅读也保留玩家和顾问的私聊。"' in strings
    assert '"replay.advisor_archive_hint": "Full read also keeps the player and advisor side-chat."' in strings
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
    assert '"replay.cta_back_plaza": "回到故事入口"' in strings
    assert '"replay.cta_back_plaza": "Back to Story Desk"' in strings
    assert '"replay.cta_back_plaza": "回到广场"' not in strings
    assert '"replay.cta_back_plaza": "Back to plaza"' not in strings


def test_replay_fixture_uses_real_replay_page_for_local_evidence() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    replay = (ROOT / "frontend2/src/pages/replay/replay-page.tsx").read_text()
    fixture = (ROOT / "frontend2/src/pages/replay/replay-fixture.tsx").read_text()
    world = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()
    play = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    frontend_readme = (ROOT / "frontend2/src/README.md").read_text()
    code_map = (ROOT / "docs/tiny-stories-code-map.md").read_text()

    assert 'apiClient?: Pick<FrontendApiClient, "getNarrativePublicReplay">' in replay
    assert "const defaultApi = useApi()" in replay
    assert "const api = apiClient ?? defaultApi" in replay
    assert 'data-replay-page="true"' in replay

    assert 'apiClient?: TemplateDetailApiClient' in world
    assert 'type TemplateDetailApiClient = Pick<' in world
    assert '"getNarrativeTemplate"' in world
    assert '"startNarrativeSession"' in world
    assert "const defaultApi = useApi()" in world
    assert "const api = apiClient ?? defaultApi" in world

    assert 'apiClient?: PlayPageApiClient' in play
    assert 'type PlayPageApiClient = Pick<' in play
    assert '"getNarrativeStory"' in play
    assert '"advanceNarrativeTurn"' in play
    assert "const defaultApi = useApi()" in play
    assert "const api = apiClient ?? defaultApi" in play

    assert '| { name: "replayFixture" }' in routes
    assert "replayFixture: 1" in routes
    assert 'segments[1] === "replay"' in routes
    assert '{ name: "replayFixture" }' in routes
    assert 'return "#/qa/replay"' in routes

    assert 'import { ReplayFixture } from "../pages/replay/replay-fixture"' in app
    assert 'case "replayFixture"' in app
    assert "<ReplayFixture" in app
    assert "onOpenTemplate={(templateId) => navigate({ name: \"template\", templateId })}" in app

    assert 'import { ReplayPage } from "./replay-page"' in fixture
    assert 'import { TemplateDetailPage } from "../world/world-detail-page"' in fixture
    assert 'import { PlayPage } from "../play/play-page"' in fixture
    assert "QA_REPLAY" in fixture
    assert "QA_REPLAY_TEMPLATE" in fixture
    assert "QA_REPLAY_OPENING" in fixture
    assert 'data-replay-fixture="true"' in fixture
    assert "apiClient={qaReplayApi}" in fixture
    assert "apiClient={qaTemplateApi}" in fixture
    assert "apiClient={qaPlayApi}" in fixture
    assert "const freeInput = request.free_input?.trim()" in fixture
    assert "const selectedOptionText = selectedOption.label.replace" in fixture
    assert "const submittedMove = freeInput || selectedOptionText" in fixture
    assert "content: submittedMove" in fixture
    assert "chosen_option_index: freeInput ? null : selectedIndex" in fixture
    assert "handleOpenTemplate" in fixture
    assert 'setFixtureView("template")' in fixture
    assert 'setFixtureView("play")' in fixture
    assert "<ReplayPage" in fixture
    assert "<TemplateDetailPage" in fixture
    assert "<PlayPage" in fixture
    assert 'data-replay-view-mode-hint="true"' not in fixture
    assert 'data-replay-advisor-archive-hint="true"' not in fixture
    assert 'data-replay-advisor-track="true"' not in fixture
    assert 'data-replay-preview-why="true"' not in fixture
    assert 'data-world-role-launch-read="true"' not in fixture
    assert 'data-play-action-option-card="true"' not in fixture
    assert 't("replay.cta_hint")' not in fixture

    assert "`#/qa/replay` fixture" in frontend_readme
    assert "chain must stay locally runnable without backend data" in frontend_readme
    assert "`#/qa/replay` mounts the real ReplayPage" in code_map
    assert "same-opening restart path stays on real TemplateDetailPage / PlayPage components" in code_map


def test_home_story_entries_are_generated_playable_template_objects() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    fixture = (ROOT / "frontend2/src/pages/home/home-start-fixture.tsx").read_text()
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    frontend_readme = (ROOT / "frontend2/src/README.md").read_text()
    code_map = (ROOT / "docs/tiny-stories-code-map.md").read_text()

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
    assert "type HomePageApiClient = Pick<" in home
    assert "apiClient?: HomePageApiClient" in home
    assert "const defaultApi = useApi()" in home
    assert "const api = apiClient ?? defaultApi" in home
    assert "listPublicNarrativeTemplates" in home
    assert "api.startNarrativeSession(templateId)" in home
    assert "saveCreateDraftHandoff" not in template
    assert 'data-story-card-kind="published-story"' in template
    assert 'data-home-tile-span={span}' in template
    assert "displayView.copy.primaryAction" in template
    assert 'data-home-tile-type-label="true"' in template
    assert "{view.copy.typeLabel}" in template
    assert 'data-home-tile-title="true"' in template
    assert 'data-home-tile-deck="true"' in template
    assert "deckLines = compact ? 3 : isSingleRowHomeTileSpan(span) ? 2 : 3" in template
    assert 'data-home-tile-text-body="title-deck-action"' in home
    assert "minHeight: 300" in home
    assert "fontSize: 44" in home
    assert "section: { marginTop: 24 }" in home
    assert "heroCompact: {" in home
    assert "minHeight: 344" in home
    assert "heroTitleCompact: {" in home
    assert "fontSize: 30" in home
    assert "heroSubCompact: {" in home
    assert "maxWidth: 312" in home
    assert "sectionCompact: { marginTop: 10 }" in home
    assert "plazaHeaderCompact" in home
    assert "compactHome ? hpStyles.plazaHeaderCompact : null" in home
    assert "Story Butler" not in template
    assert '"home.card_action": "Start episode →"' in strings

    assert '| { name: "homeStartFixture" }' in routes
    assert 'if (segments[1] === "home-start") return { name: "homeStartFixture" }' in routes
    assert 'return "#/qa/home-start"' in routes
    assert "import { HomeStartFixture }" in app
    assert 'case "homeStartFixture":' in app
    assert "<HomeStartFixture" in app

    assert "import { HomePage } from \"./home-page\"" in fixture
    assert "import { PlayPage } from \"../play/play-page\"" in fixture
    assert 'data-home-start-fixture="true"' in fixture
    assert "listPublicNarrativeTemplates: async () => ({ items: [QA_HOME_TEMPLATE] })" in fixture
    assert "startNarrativeSession: async" in fixture
    assert 'setView("play")' in fixture
    assert 'data-story-card-kind="published-story"' not in fixture
    assert 'data-play-action-option-card="true"' not in fixture
    assert "`#/qa/home-start` populated-card-to-first-turn fixture" in frontend_readme
    assert "`#/qa/home-start` mounts the real HomePage" in code_map
