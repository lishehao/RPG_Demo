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
    assert 'VITE_PUBLIC_LAB_DEFAULT !== "true"' in page
    assert "getNarrativeEvaluationBundle" in page


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


def test_live_session_export_connects_create_memory_play_and_reviewer_lab() -> None:
    create_page = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text(encoding="utf-8")
    routes = (ROOT / "frontend2/src/api/route-map.ts").read_text(encoding="utf-8")
    client = (ROOT / "frontend2/src/api/http-client.ts").read_text(encoding="utf-8")
    page = (ROOT / "frontend2/src/pages/evaluation/rpg-evaluation-page.tsx").read_text(encoding="utf-8")
    inspector = (ROOT / "frontend2/src/pages/play/components/runtime-inspector.tsx").read_text(encoding="utf-8")
    backend = (ROOT / "rpg_backend/main.py").read_text(encoding="utf-8")
    repository = (ROOT / "rpg_backend/narrative/repository.py").read_text(encoding="utf-8")

    assert "story_guide_context: guideLoopState.context" in create_page
    assert "story_brief_json" in repository
    assert "story_guide_context_json" in repository
    assert "/narrative/sessions/:session_id/evaluation-bundle" in routes
    assert '"/research/rpg-evaluations"' in routes
    assert "getNarrativeEvaluationBundle(sessionId" in client
    assert 'data-rpg-live-session-loader="true"' in page
    assert 'VITE_PUBLIC_LAB_DEFAULT !== "true"' in page
    assert 'data-reviewer-open-portable-evaluation="true"' in inspector
    assert '"/narrative/sessions/{session_id}/evaluation-bundle"' in backend
    assert '"/research/rpg-evaluations"' in backend
    vite_config = (ROOT / "frontend2/vite.config.ts").read_text(encoding="utf-8")
    assert "narrative|research" in vite_config


def test_frontend_evaluator_handles_terminal_turns_and_progress_provenance() -> None:
    contract = (ROOT / "frontend2/src/pages/evaluation/rpg-evaluation-contract.ts").read_text(encoding="utf-8")

    assert "terminal?: boolean" in contract
    assert '"turn_budget_proxy"' in contract
    assert "!turn.terminal" in contract
    assert "nonTerminalTurns" in contract
    assert "Progress basis:" in contract
