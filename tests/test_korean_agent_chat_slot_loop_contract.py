from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_korean_agent_chat_slot_loop_has_explicit_states_and_slots() -> None:
    source = (ROOT / "frontend2/src/shared/lib/story-guide-loop.ts").read_text()

    for state in (
        "empty",
        "collecting",
        "needs_field",
        "clarify_conflict",
        "redirect",
        "analyzing",
        "ready_to_brief",
        "brief_ready",
        "brief_not_fit",
    ):
        assert f'"{state}"' in source

    for slot in (
        "player_role",
        "active_cast",
        "pressure",
        "tone",
        "boundaries",
        "first_scene_hook",
    ):
        assert f'"{slot}"' in source


def test_korean_agent_chat_slot_loop_blocks_drug_addiction_before_brief() -> None:
    source = (ROOT / "frontend2/src/shared/lib/story-guide-loop.ts").read_text()

    assert "UNSAFE_PATTERNS" in source
    assert "drug" in source
    assert "addiction" in source
    assert "redirect_out_of_spec" in source
    assert "acceptedText: false" in source


def test_create_page_uses_slot_loop_before_story_brief_generation() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()

    assert "advanceStoryGuideLoop" in source
    assert "canShapeStoryBrief" in source
    assert "guideReadyToBrief" in source
    assert 'data-guide-loop-state={guideLoopState.status}' in source
    assert 'data-guide-node={message.node ?? "static_opening"}' in source

    readiness_guard = source.index("if (!guideReadyToBrief)")
    story_brief_call = source.index("createNarrativeStoryBrief")
    assert readiness_guard < story_brief_call

    shape_button_guard = source.index("hasSeed && !activeBrief && guideReadyToBrief")
    shape_button_label = source.index("{briefComposerLabel}", shape_button_guard)
    assert shape_button_guard < shape_button_label


def test_create_page_keeps_long_generate_handoff_visible_before_navigation() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "LONG_GENERATE_HANDOFF_THRESHOLD_MS = 30_000" in source
    assert "LONG_GENERATE_HANDOFF_MIN_MS = 2_000" in source
    assert "openingHandoffLabelKey" in source
    assert "setOpeningHandoffLabelKey(handoffLabelKey)" in source

    handoff_check = source.index("openingElapsedMs >= LONG_GENERATE_HANDOFF_THRESHOLD_MS")
    template_response = source.index("const response = await api.createNarrativeTemplate")
    route_start = source.index("onSessionStarted(response.session.session_id)")
    assert template_response < handoff_check < route_start
    assert "create.building_handoff_ready" in strings
    assert "create.building_handoff_ready_long" in strings
    assert "create.building_handoff_recovered" in strings
    assert "Opening tightened from the Brief. Entering the scene..." in strings
