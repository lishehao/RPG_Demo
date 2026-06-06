from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_home_published_template_cards_start_play_sessions_directly() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()

    assert "api.startNarrativeSession(templateId)" in home
    assert "onOpenPlay(response.session.session_id)" in home
    assert "startingTemplateRef.current" in home
    assert "onStartTemplate={handleStartPublishedTemplate}" in home
    assert "isStarting={startingTemplateId === t.template_id}" in home
    assert "createNarrativeStoryBrief" not in home
    assert "createNarrativeTemplate" not in home
    home_route = app[app.index('case "home":') : app.index('case "login":')]
    assert "onOpenTemplate" not in home_route


def test_home_curated_plaza_cards_remain_premise_starters() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()

    curated = home[
        home.index("const handleStartCuratedStory") : home.index("const handleStartPublishedTemplate")
    ]
    assert "saveCreateDraftHandoff" in curated
    assert "source: \"plaza_curated\"" in curated
    assert "onOpenCreate()" in curated
    assert "startNarrativeSession" not in curated
