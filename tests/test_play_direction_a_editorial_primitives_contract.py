from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_play_route_mounts_direction_a_editorial_primitives() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()

    assert "from \"./components/play-editorial-primitives\"" in play_page
    for component in (
        "PlayShell",
        "MoodPlate",
        "PlaySurfaceGrid",
        "StoryTimeline",
        "SceneSupportRail",
    ):
        assert component in play_page
        assert f"function {component}" in primitives

    assert 'data-play-direction="editorial-primitive-kit"' in primitives
    assert 'data-play-primitive="MoodPlate"' in primitives
    assert 'data-play-primitive="StoryTimeline"' in primitives
    assert 'data-play-primitive="SceneSupportRail"' in primitives
    assert "<RunContextPanel" not in play_page


def test_play_primitives_keep_story_world_mental_model() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    readme = (ROOT / "frontend2/src/pages/play/README.md").read_text()

    assert "ActionArea" in play_page
    assert "AdvisorSidechat" in play_page
    assert "MoodPlate" in primitives
    assert "SceneSupportRail" in primitives
    assert "Narrator/World" in readme
    assert "Story Butler is not the primary Play speaker" in readme
    assert "Story Butler" not in primitives


def test_scene_support_rail_uses_webtoon_portrait_images() -> None:
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    assets = (ROOT / "frontend2/src/shared/lib/webtoon-assets.ts").read_text()

    assert "getAvatarForCastMember" in primitives
    assert "getDefaultAvatar" in primitives
    assert 'data-play-player-portrait="true"' in primitives
    assert 'data-play-cast-portrait="true"' in primitives
    assert "<img" in primitives
    assert "avatarUrl: getAvatarForCastMember" in primitives
    assert "getAvatarForCastMember(story.template.template_id, member, story.template)" in primitives
    assert "playerPortraitForStory" in primitives
    assert "handlePortraitError" in primitives
    assert "initialsFor" not in primitives
    assert "actor.initials" not in primitives
    assert "{actor.initials}" not in primitives
    assert "/webtoons/avatars/" in assets
    assert "export function getAvatarForCastMember" in assets


def test_direction_a_uses_local_primitives_not_other_ui_kit_paths() -> None:
    package_json = (ROOT / "frontend2/package.json").read_text()
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()

    assert "@heroui" not in package_json
    assert "@mantine" not in package_json
    assert "@heroui" not in play_page
    assert "@mantine" not in play_page
    assert "@heroui" not in primitives
    assert "@mantine" not in primitives
    assert "borderRadius: 999" not in primitives


def test_reviewer_evaluation_drawer_is_gated_and_uses_persisted_evidence() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()
    route_map = (ROOT / "frontend2/src/api/route-map.ts").read_text()
    client = (ROOT / "frontend2/src/api/client.ts").read_text()

    assert "canRequestAgentTrace" in play_page
    assert "api.getNarrativeLLMEvents(sessionId)" in play_page
    assert "llmEvents={llmEvents}" in play_page
    assert 'data-play-primitive="EvaluationDrawer"' in panels
    assert 'data-reviewer-evidence="true"' in panels
    assert "evaluationCriteria" in panels
    assert "trajectoryEvidence" in panels
    assert "NarrativeLLMCallEvent" in panels
    assert "getNarrativeLLMEvents" in client
    assert "/narrative/sessions/:session_id/llm-events" in route_map


def test_normal_play_keeps_evaluation_terms_outside_default_surface() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()

    assert "reviewerMode ? (" in play_page
    assert "<RuntimeInspector" in play_page
    assert "Evaluation evidence" in panels
    assert "data-reviewer-evidence" in panels
    assert "token" not in (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text().casefold()


def test_finish_mode_normal_play_reduces_top_metadata_density() -> None:
    play_page = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()
    primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    panels = (ROOT / "frontend2/src/pages/play/components/play-flow-panels.tsx").read_text()

    mood_plate = primitives[primitives.index("export function MoodPlate") : primitives.index("export function SceneSupportRail")]
    scene_rail = primitives[primitives.index("export function SceneSupportRail") : primitives.index("function PrimitiveSection")]
    story_beat = panels[panels.index("export function StoryBeat") : panels.index("export function computeLiveInventory")]

    assert "cast={story.template.cast.map" not in play_page
    assert "const castLine" not in mood_plate
    assert "story.template.seed" not in mood_plate
    assert "First shot is live" in mood_plate
    assert '<PrimitiveSection title="Progress">' not in scene_rail
    assert ".slice(0, 3)" in primitives[primitives.index("function sceneActors") : primitives.index("function playerPortraitForStory")]
    assert "return items.slice(0, 3)" in panels
    assert "impactPulses.slice(0, 3).map" in story_beat
    assert "pulseImpactReason" not in story_beat
