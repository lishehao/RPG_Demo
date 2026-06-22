from __future__ import annotations

from pathlib import Path

from tools.portfolio_public_evidence_preflight import (
    PUBLIC_PAGE_MARKERS,
    PublicEvidenceStatus,
    evidence_sensitive_paths,
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
            "docs/index.html",
            "frontend2/src/pages/home/home-page.tsx",
            "frontend2/src/pages/world/world-detail-page.tsx",
            "frontend2/src/pages/portfolio/reviewer-page.tsx",
            "frontend2/src/pages/play/components/play-flow-panels.tsx",
            "tools/internal_note.txt",
        ),
    )

    output = format_status(status)

    assert status_exit_code(status) == 1
    assert "Portfolio public evidence preflight: FAIL" in output
    assert "371 commit(s) ahead of origin/main" in output
    assert "public reviewers will not see those local changes" in output
    assert "Evidence-sensitive local changes not yet public" in output
    assert "- README.md" in output
    assert "- docs/index.html" in output
    assert "- frontend2/src/pages/home/home-page.tsx" in output
    assert "- frontend2/src/pages/world/world-detail-page.tsx" in output
    assert "- frontend2/src/pages/portfolio/reviewer-page.tsx" in output
    assert "- tools/internal_note.txt" not in output
    assert "push the intended branch" in output


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
    assert "Portfolio public evidence preflight: PASS" in output
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
        public_page_missing_markers=("Reviewer path", "#/portfolio -> #/reviewer", "Who this loop is for"),
    )

    output = format_status(status)

    assert status_exit_code(status) == 1
    assert "Deployed page https://lishehao.github.io/RPG_Demo/ is missing current portfolio evidence markers" in output
    assert "- Reviewer path" in output
    assert "- #/portfolio -> #/reviewer" in output
    assert "- Who this loop is for" in output
    assert "GitHub Pages may still be stale" in output


def test_public_evidence_preflight_is_documented_for_application_links() -> None:
    readme = (ROOT / "README.md").read_text()

    assert "python tools/portfolio_public_evidence_preflight.py" in readme
    assert "before sending application or recruiting" in readme
    assert "links. It should report" in readme
    assert "local `HEAD` matches `origin/main`" in readme
    assert "GitHub and GitHub Pages reviewers" in readme
    assert "live GitHub Pages marker check" in readme


def test_evidence_sensitive_path_filter_covers_portfolio_and_play_surfaces() -> None:
    paths = evidence_sensitive_paths(
        (
            "docs/CURRENT_SYSTEM_MAP.md",
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
        "frontend2/src/pages/home/home-page.tsx",
        "frontend2/src/pages/world/world-detail-page.tsx",
        "frontend2/src/pages/play/components/play-flow-panels.tsx",
        "frontend2/src/pages/portfolio/portfolio-page.tsx",
        "rpg_backend/narrative/service.py",
    )


def test_public_page_markers_cover_current_reviewer_path_language() -> None:
    assert PUBLIC_PAGE_MARKERS == (
        "75s reviewer cut",
        "Reviewer path",
        "#/portfolio -> #/reviewer",
        "Source evidence",
        "portfolio-grade AI product-system evidence",
        "Who this loop is for",
        "story-first players who want a compact",
        "not a blank writing canvas or a dashboard",
    )
