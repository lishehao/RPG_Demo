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
    assert "I can’t build this story around drug use or addiction" in source
    assert "这个故事不会围绕毒品使用或成瘾来展开" in source
    assert "this beta around drug use" not in source
    assert "这个 beta 不会" not in source
    assert "acceptedText: false" in source


def test_korean_agent_chat_slot_loop_blocks_small_cast_object_only_before_brief() -> None:
    source = (ROOT / "frontend2/src/shared/lib/story-guide-loop.ts").read_text()
    create_source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()

    assert "detectsUnsupportedSmallCastDirection" in source
    assert "two-person" in source
    assert "no public pressure" in source
    assert "wedding ring" in source
    assert "object-only thread" in source
    assert "This story needs a third active pressure or public consequence before I shape the story plan" in source
    assert "这个故事需要至少第三方在场压力或公开后果，才能变成可玩的故事计划" in source
    assert "This beta needs" not in source
    assert "这个 beta 需要" not in source
    assert "before I shape a Story Brief" not in source
    assert "可玩的 Story Brief" not in source
    assert "canShapeBrief: false" in source

    unsupported_guard = source.index("detectsUnsupportedSmallCastDirection(text)")
    ready_assignment = source.index("const ready = canShapeStoryBrief")
    assert unsupported_guard < ready_assignment

    auto_brief_guard = create_source.index("!guideReadyToBrief ||")
    assert create_source.index("!hasSeed ||", auto_brief_guard) > auto_brief_guard
    assert create_source.index("privacyPromptVisible ||", auto_brief_guard) > auto_brief_guard
    story_brief_call = create_source.index("void handlePlanStory()", auto_brief_guard)
    assert auto_brief_guard < story_brief_call


def test_create_page_uses_slot_loop_before_story_brief_generation() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/create/create-styles.ts").read_text()

    assert "advanceStoryGuideLoop" in source
    assert "canShapeStoryBrief" in source
    assert "guideReadyToBrief" in source
    assert 'data-guide-loop-state={guideLoopState.status}' in source
    assert 'data-guide-node={message.node ?? "static_opening"}' in source

    readiness_guard = source.index("if (!guideReadyToBrief)")
    story_brief_call = source.index("createNarrativeStoryBrief")
    assert readiness_guard < story_brief_call

    auto_brief_guard = source.index("!guideReadyToBrief ||")
    assert source.index("!hasSeed ||", auto_brief_guard) > auto_brief_guard
    assert source.index("privacyPromptVisible ||", auto_brief_guard) > auto_brief_guard
    auto_brief_call = source.index("void handlePlanStory()", auto_brief_guard)
    story_brief_call = source.index("createNarrativeStoryBrief")
    assert story_brief_call < auto_brief_guard < auto_brief_call
    assert "autoBriefKeyRef.current === currentBriefKey" in source
    assert "hasSeed && !activeBrief && guideReadyToBrief" not in source
    assert "{briefComposerLabel}" not in source
    assert 'rows={1}' in source
    assert "minHeight: 48" in styles
    assert 'resize: "none"' in styles


def test_create_page_keeps_long_generate_handoff_visible_before_navigation() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()
    options_source = (ROOT / "frontend2/src/pages/create/create-options.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "LONG_GENERATE_HANDOFF_THRESHOLD_MS = 30_000" in options_source
    assert "LONG_GENERATE_HANDOFF_MIN_MS = 2_000" in options_source
    assert "openingHandoffLabelKey" in source
    assert "setOpeningHandoffLabelKey(handoffLabelKey)" in source

    handoff_check = source.index("openingElapsedMs >= LONG_GENERATE_HANDOFF_THRESHOLD_MS")
    template_response = source.index("const response = await api.createNarrativeTemplate")
    route_start = source.index("onSessionStarted(response.session.session_id)")
    assert template_response < handoff_check < route_start
    assert "create.building_handoff_ready" in strings
    assert "create.building_handoff_ready_long" in strings
    assert "create.building_handoff_recovered" in strings
    assert "Opening tightened from the plan. Entering the scene..." in strings


def test_story_butler_ready_copy_uses_story_plan_language() -> None:
    source = (ROOT / "frontend2/src/shared/lib/story-guide-loop.ts").read_text()

    assert "That is enough to shape the final story plan." in source
    assert "The direction is clear enough. I can shape the final story plan now" in source
    assert "信息够了。要我整理最终故事计划吗？" in source
    assert "方向已经够清楚了。我可以把它整理成最终故事计划" in source
    assert "final Story Brief" not in source
    assert "最终 Story Brief" not in source
