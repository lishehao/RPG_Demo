from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_story_guide_loop_infers_shape_settings_from_chat_phrases() -> None:
    source = (ROOT / "frontend2/src/shared/lib/story-guide-loop.ts").read_text()

    assert "export type StoryGuideSettingDeltas" in source
    assert "inferStoryGuideSettings" in source
    assert "settings.turnBudget = 8" in source
    assert "settings.turnBudget = 12" in source
    assert "settings.turnBudget = 20" in source
    assert "npc(?:s)? fight back" in source
    assert 'settings.difficulty = "gauntlet"' in source
    assert "make it english" in source
    assert "switch (?:it )?to english" in source
    assert "用英文写" in source
    assert 'settings.language = "en"' in source
    assert "make it chinese" in source
    assert "switch (?:it )?to chinese" in source
    assert "中文" in source
    assert 'settings.language = "zh"' in source
    assert "backstage" in source
    assert "disappearance" in source
    assert 'settings.tensionProfile = "high_drama"' in source


def test_privacy_chat_intent_is_guidance_not_silent_publish() -> None:
    loop_source = (ROOT / "frontend2/src/shared/lib/story-guide-loop.ts").read_text()
    create_source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()

    assert "privacyIntent" in loop_source
    assert "detectPrivacyIntent" in loop_source
    assert "isPrivacyOnlyRequest" in loop_source
    assert "make it public" in loop_source
    assert "public pressure" in loop_source
    assert "I will not silently change publishing from chat" in loop_source

    apply_start = create_source.index("const applyStoryGuideSettings")
    apply_end = create_source.index("const ensureAuthorSession", apply_start)
    apply_segment = create_source[apply_start:apply_end]
    assert "setTurnBudget" in apply_segment
    assert "setDifficulty" in apply_segment
    assert "setStoryLanguage" in apply_segment
    assert "setDesiredTensionProfile" in apply_segment
    assert "setVisibility" not in apply_segment


def test_create_settings_panel_only_exposes_visibility_control() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()

    details_start = source.index("<details")
    details_end = source.index("</details>", details_start)
    details_segment = source[details_start:details_end]

    assert 'data-create-privacy-settings="true"' in details_segment
    assert 't("create.field_visibility")' in details_segment
    assert "VISIBILITY_OPTION_IDS.map" in details_segment
    assert "BUDGET_OPTIONS.map" not in details_segment
    assert "DIFFICULTY_OPTIONS.map" not in details_segment
    assert "STORY_LANGUAGE_OPTIONS[uiLang].map" not in details_segment
    assert "TENSION_PROFILE_OPTIONS.map" not in details_segment


def test_butler_read_surfaces_in_transcript_and_brief_payload_still_uses_values() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert 'data-guide-node="story_shape_read"' in source
    assert "StoryShapeReadLedger" in source
    assert 't("create.butler_read_label")' in source
    assert "shapeRead={storyShapeRead}" in source
    assert 't("create.setting_run_length")' in source
    assert 't("create.setting_pressure_mode")' in source
    assert 't("create.setting_story_language")' in source
    assert 't("create.setting_tone")' in source

    template_payload = source[source.index("api.createNarrativeTemplate") : source.index("const openingElapsedMs")]
    assert "turn_budget: turnBudget" in template_payload
    assert "difficulty" in template_payload
    assert "language: storyLanguage" in template_payload

    brief_payload = source[source.index("api.createNarrativeStoryBrief") : source.index("setBriefResponse(response)")]
    assert "language: storyLanguage" in brief_payload
    assert "desiredTensionProfile === \"auto\" ? null : desiredTensionProfile" in brief_payload

    for key in (
        '"create.butler_read_label": "Butler read"',
        '"create.setting_run_length": "Run length"',
        '"create.setting_pressure_mode": "Pressure mode"',
        '"create.setting_story_language": "Story language"',
        '"create.setting_tone": "Tone"',
        '"create.butler_read_label": "管家判断"',
        '"create.setting_run_length": "时长"',
        '"create.setting_pressure_mode": "压力模式"',
        '"create.setting_story_language": "故事语言"',
        '"create.setting_tone": "语气"',
    ):
        assert key in strings
