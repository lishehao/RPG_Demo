from __future__ import annotations

from pathlib import Path

from tools.portfolio_public_evidence_preflight import (
    PUBLIC_APP_MARKERS,
    PUBLIC_PAGE_MARKERS,
    PublicEvidenceStatus,
    evidence_sensitive_paths,
    evidence_sensitive_surfaces,
    format_status,
    status_exit_code,
)


ROOT = Path(__file__).resolve().parents[1]


def test_public_evidence_preflight_flags_local_commits_not_visible_to_reviewers() -> None:
    status = PublicEvidenceStatus(
        head="fe9d79258fa5b053607b84a17b64a6216650b40b",
        remote_ref="origin/main",
        remote_head="3f3b6048ba8e48788f65965d6e7b013a2ef828f5",
        ahead_count=371,
        behind_count=0,
        changed_paths=(
            "README.md",
            "artifacts/portfolio/tiny-stories-engineering-evidence-summary.json",
            "docs/index.html",
            "frontend2/src/pages/create/create-page.tsx",
            "frontend2/src/pages/home/home-page.tsx",
            "frontend2/src/pages/world/world-detail-page.tsx",
            "frontend2/src/pages/portfolio/reviewer-page.tsx",
            "frontend2/src/pages/play/components/play-flow-panels.tsx",
            "frontend2/src/pages/replay/replay-page.tsx",
            "rpg_backend/narrative/service.py",
            "tests/test_navigation_mental_model_contract.py",
            "tools/internal_note.txt",
        ),
    )

    output = format_status(status)

    assert status_exit_code(status) == 1
    assert "Portfolio public-link check: FAIL" in output
    assert "371 commit(s) ahead of origin/main" in output
    assert "public reviewers will not see those local changes" in output
    assert "Evidence-sensitive reviewer surfaces not yet public" in output
    assert "- README / public docs" in output
    assert "- Portfolio evidence artifacts" in output
    assert "- Story Desk / saved runs" in output
    assert "- Template detail / start-own-run" in output
    assert "- Create flow" in output
    assert "- Play loop / action feedback" in output
    assert "- Replay / shared memory" in output
    assert "- Portfolio / reviewer run" in output
    assert "- Narrative backend" in output
    assert "- Contract tests" in output
    assert "Evidence-sensitive local changes not yet public" in output
    assert "- README.md" in output
    assert "- artifacts/portfolio/tiny-stories-engineering-evidence-summary.json" in output
    assert "- docs/index.html" in output
    assert "- frontend2/src/pages/home/home-page.tsx" in output
    assert "- frontend2/src/pages/world/world-detail-page.tsx" in output
    assert "- frontend2/src/pages/portfolio/reviewer-page.tsx" in output
    assert "- tools/internal_note.txt" not in output
    assert "push the intended branch" in output
    assert "python3 tools/portfolio_public_evidence_preflight.py" in output
    assert "Application wording: use the demo video for orientation only" in output
    assert "do not cite the current Portfolio, public reviewer demo, Reviewer run, Story Desk, Create, Play, or Replay surfaces as public evidence" in output
    assert "Reviewer path" not in output
    assert "routes as public evidence" not in output
    assert "label the listed surfaces as local-only application evidence" in output


def test_public_evidence_preflight_passes_only_when_synced() -> None:
    status = PublicEvidenceStatus(
        head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        remote_ref="origin/main",
        remote_head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ahead_count=0,
        behind_count=0,
        changed_paths=(),
    )

    output = format_status(status)

    assert status_exit_code(status) == 0
    assert "Portfolio public-link check: PASS" in output
    assert "matches origin/main" in output
    assert "public reviewers will not see" not in output


def test_public_evidence_preflight_fails_when_deployed_page_is_stale() -> None:
    status = PublicEvidenceStatus(
        head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        remote_ref="origin/main",
        remote_head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ahead_count=0,
        behind_count=0,
        changed_paths=(),
        public_page_url="https://lishehao.github.io/RPG_Demo/",
        public_page_missing_markers=("Reviewer run guide", "Open public reviewer demo", "Who this loop is for"),
    )

    output = format_status(status)

    assert status_exit_code(status) == 1
    assert "Deployed page https://lishehao.github.io/RPG_Demo/ is missing current portfolio evidence markers" in output
    assert "- Reviewer run guide" in output
    assert "- Open public reviewer demo" in output
    assert "- Who this loop is for" in output
    assert "GitHub Pages may still be stale" in output
    assert "python3 tools/portfolio_public_evidence_preflight.py" in output
    assert "Application wording: use the demo video for orientation only" in output


def test_public_evidence_preflight_is_documented_for_application_links() -> None:
    readme = (ROOT / "README.md").read_text()

    assert '<a href="https://youtu.be/RRJ7uyjW_nA">' in readme
    assert '<a href="https://lishehao.github.io/RPG_Demo/">' not in readme
    assert "python3 tools/portfolio_public_evidence_preflight.py" in readme
    assert "Before citing a deployed route as application evidence" in readme
    assert "public branch and GitHub Pages deployment actually" in readme
    assert "contain the evidence being referenced" in readme
    assert "public reviewer demo is deterministic and backend-free" in readme
    assert "not presented as a live-generation" in readme
    assert "one reproducible system\ntrajectory" in readme
    assert "not population-level story quality, retention, or market demand" in readme


def test_evidence_sensitive_path_filter_covers_portfolio_and_play_surfaces() -> None:
    paths = evidence_sensitive_paths(
        (
            "docs/CURRENT_SYSTEM_MAP.md",
            "artifacts/portfolio/tiny-stories-engineering-evidence-summary.json",
            "frontend2/src/pages/home/home-page.tsx",
            "frontend2/src/pages/world/world-detail-page.tsx",
            "frontend2/src/pages/play/components/play-flow-panels.tsx",
            "frontend2/src/pages/portfolio/portfolio-page.tsx",
            "rpg_backend/narrative/service.py",
            "scratch/local.txt",
        )
    )

    assert paths == (
        "docs/CURRENT_SYSTEM_MAP.md",
        "artifacts/portfolio/tiny-stories-engineering-evidence-summary.json",
        "frontend2/src/pages/home/home-page.tsx",
        "frontend2/src/pages/world/world-detail-page.tsx",
        "frontend2/src/pages/play/components/play-flow-panels.tsx",
        "frontend2/src/pages/portfolio/portfolio-page.tsx",
        "rpg_backend/narrative/service.py",
    )


def test_evidence_sensitive_surface_summary_keeps_hidden_paths_legible() -> None:
    surfaces = evidence_sensitive_surfaces(
        (
            "README.zh.md",
            "artifacts/portfolio/tiny-stories-engineering-evidence-summary.json",
            "frontend2/src/pages/home/home-page.tsx",
            "frontend2/src/pages/world/world-detail-page.tsx",
            "frontend2/src/pages/create/create-page.tsx",
            "frontend2/src/pages/play/play-page.tsx",
            "frontend2/src/pages/replay/replay-page.tsx",
            "frontend2/src/pages/portfolio/portfolio-page.tsx",
            "rpg_backend/narrative/service.py",
            "tests/test_navigation_mental_model_contract.py",
            "scratch/local.txt",
        )
    )

    assert surfaces == (
        "README / public docs",
        "Portfolio evidence artifacts",
        "Story Desk / saved runs",
        "Template detail / start-own-run",
        "Create flow",
        "Play loop / action feedback",
        "Replay / shared memory",
        "Portfolio / reviewer run",
        "Narrative backend",
        "Contract tests",
    )


def test_public_page_markers_cover_current_reviewer_path_language() -> None:
    assert PUBLIC_PAGE_MARKERS == (
        "75s reviewer cut",
        "Public reviewer demo",
        "Reviewer run guide",
        "Open public reviewer demo",
        "Source evidence",
        "What reviewers can inspect",
        "portfolio-grade AI product-system evidence",
        "Who this loop is for",
        "story-first players who want a compact",
        "not a blank writing canvas or a dashboard",
    )
    assert PUBLIC_APP_MARKERS == (
        "demo/reviewer",
        "Public reviewer demo",
        "Static reviewer path for admissions review",
        "The Missing Singer Broadcast",
        "deterministic story state",
    )
