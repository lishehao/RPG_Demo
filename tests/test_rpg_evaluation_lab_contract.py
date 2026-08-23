from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_rpg_evaluation_lab_is_backend_free_and_routable() -> None:
    routes = (ROOT / "frontend2/src/app/routes.ts").read_text(encoding="utf-8")
    app = (ROOT / "frontend2/src/app/app.tsx").read_text(encoding="utf-8")
    auth = (ROOT / "frontend2/src/app/auth-context.tsx").read_text(encoding="utf-8")
    page = (ROOT / "frontend2/src/pages/evaluation/rpg-evaluation-page.tsx").read_text(encoding="utf-8")

    assert 'name: "rpgEvaluation"' in routes
    assert '#/lab/rpg-evaluation' in routes
    assert 'VITE_PUBLIC_LAB_DEFAULT === "true"' in routes
    assert "<RpgEvaluationPage" in app
    assert 'route.startsWith("/lab/rpg-evaluation")' in auth
    assert 'data-rpg-evaluation-lab="true"' in page
    assert "useApi" not in page


def test_rpg_evaluation_lab_exposes_portable_memory_and_evidence_views() -> None:
    page = (ROOT / "frontend2/src/pages/evaluation/rpg-evaluation-page.tsx").read_text(encoding="utf-8")
    contracts = (ROOT / "frontend2/src/pages/evaluation/rpg-evaluation-contract.ts").read_text(encoding="utf-8")
    styles = (ROOT / "frontend2/src/app/theme.css").read_text(encoding="utf-8")

    for hook in (
        "data-rpg-evaluation-summary",
        "data-rpg-evaluation-criterion",
        "data-rpg-evaluation-turn",
        "data-rpg-evaluation-memory",
        "data-rpg-evaluation-comparison",
        "data-rpg-evaluation-boundary",
    ):
        assert hook in page

    assert '"rpg_evaluation_bundle.v1"' in contracts
    assert '"rpg_memory.v1"' in contracts
    assert "memory_continuity" in contracts
    assert "consequence_visibility" in contracts
    assert "player_agency" in contracts
    assert "boundary_hygiene" in contracts
    assert "@media (max-width: 760px)" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


def test_vercel_build_defaults_to_static_evaluation_lab() -> None:
    config = (ROOT / "frontend2/vercel.json").read_text(encoding="utf-8")

    assert '"framework": "vite"' in config
    assert "VITE_PUBLIC_LAB_DEFAULT=true npm run build" in config
    assert '"outputDirectory": "dist"' in config
