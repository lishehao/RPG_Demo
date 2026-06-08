from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_story_guide_loop_infers_shape_settings_from_chat_phrases() -> None:
    loop_source = (ROOT / "frontend2/src/shared/lib/story-guide-loop.ts").read_text()
    source = (ROOT / "frontend2/src/shared/lib/story-guide-settings.ts").read_text()

    assert 'from "./story-guide-settings"' in loop_source
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
    settings_source = (ROOT / "frontend2/src/shared/lib/story-guide-settings.ts").read_text()
    create_source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()

    assert "privacyIntent" in settings_source
    assert "detectPrivacyIntent" in settings_source
    assert "isPrivacyOnlyRequest" in settings_source
    assert "make it public" in settings_source
    assert "public pressure" in settings_source
    assert "I will not silently change publishing from chat" in loop_source
    assert "privacy checkpoint" in loop_source

    apply_start = create_source.index("const applyStoryGuideSettings")
    apply_end = create_source.index("const ensureAuthorSession", apply_start)
    apply_segment = create_source[apply_start:apply_end]
    assert "setTurnBudget" in apply_segment
    assert "setDifficulty" in apply_segment
    assert "setStoryLanguage" in apply_segment
    assert "setDesiredTensionProfile" in apply_segment
    assert "setVisibility" not in apply_segment
    assert "setPrivacyPromptVisible(true)" in create_source


def test_create_privacy_checkpoint_replaces_persistent_settings_footer() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()

    assert "<details" not in source
    assert "settingsDetails" not in source
    assert 'data-create-privacy-settings="true"' in source
    assert 'data-create-privacy-mode={privacyPromptVisible ? "confirmation" : "setup"}' in source
    assert "privacySetupVisible" in source
    assert "setPrivacySetupVisible(false)" in source
    assert "VISIBILITY_OPTION_IDS.map" in source
    assert "handleVisibilityChoice(id)" in source

    checkpoint_start = source.index('data-create-privacy-settings="true"')
    checkpoint_end = source.index('{briefBusy ? (', checkpoint_start)
    checkpoint_segment = source[checkpoint_start:checkpoint_end]
    assert 't("create.field_visibility")' in checkpoint_segment
    assert "BUDGET_OPTIONS.map" not in checkpoint_segment
    assert "DIFFICULTY_OPTIONS.map" not in checkpoint_segment
    assert "STORY_LANGUAGE_OPTIONS[uiLang].map" not in checkpoint_segment
    assert "TENSION_PROFILE_OPTIONS.map" not in checkpoint_segment


def test_prebrief_chat_hides_dashboards_and_brief_payload_still_uses_values() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()
    panels_source = (ROOT / "frontend2/src/pages/create/components/create-flow-panels.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "GuideInlineLedger" not in source
    assert 'data-guide-node="story_shape_read"' not in source
    assert 't("create.butler_read_label")' not in source
    assert "shapeRead={storyShapeRead}" in source
    assert "StoryShapeReadLedger" in panels_source
    assert 't("create.setting_run_length")' in panels_source
    assert 't("create.setting_pressure_mode")' in panels_source
    assert 't("create.setting_story_language")' in panels_source
    assert 't("create.setting_tone")' in panels_source

    template_payload = source[source.index("api.createNarrativeTemplate") : source.index("const openingElapsedMs")]
    assert "turn_budget: turnBudget" in template_payload
    assert "difficulty" in template_payload
    assert "language: storyLanguage" in template_payload

    brief_payload = source[source.index("api.createNarrativeStoryBrief") : source.index("setBriefResponse(response)")]
    assert "language: storyLanguage" in brief_payload
    assert "desiredTensionProfile === \"auto\" ? null : desiredTensionProfile" in brief_payload

    for key in (
        '"create.setting_run_length": "Run length"',
        '"create.setting_pressure_mode": "Pressure mode"',
        '"create.setting_story_language": "Story language"',
        '"create.setting_tone": "Tone"',
        '"create.setting_run_length": "时长"',
        '"create.setting_pressure_mode": "压力模式"',
        '"create.setting_story_language": "故事语言"',
        '"create.setting_tone": "语气"',
    ):
        assert key in strings
