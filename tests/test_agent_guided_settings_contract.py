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
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "<details" not in source
    assert "settingsDetails" not in source
    assert "privacyRecordedVisibility" in source
    assert 'useState<NarrativeTemplateVisibility | null>("private")' in source
    assert "privacyIntroComplete" in source
    assert "appendPrivacyRecordedTurn" in source
    assert 'data-create-privacy-settings="true"' in source
    assert 'data-create-privacy-mode={privacyPromptVisible ? "confirmation" : "setup"}' in source
    assert "privacySetupVisible" in source
    assert "setPrivacySetupVisible(false)" in source
    assert "VISIBILITY_OPTION_IDS.map" in source
    assert "handleVisibilityChoice(id)" in source
    assert "handleVisibilityChoice(visibility)" in source
    assert "data-create-privacy-choice={id}" in source
    assert 'data-create-privacy-choice-desc="true"' in source
    assert "privacySetupChoiceLabel" in source
    assert "privacySetupChoiceDesc" in source
    assert "BusyBuildPreview" in source
    assert '<BusyBuildPreview activeIndex={busyStageIndex} compact={compactLayout} />' in source
    assert 'id: "guide-opening"' in source
    assert 't("create.guide_greeting")' in source
    assert 't("create.privacy_recorded_user"' in source
    assert 't("create.privacy_recorded_reply"' in source
    assert 'rows={1}' in source

    assert '"create.privacy_intro_question": "Who can play this story? Pick explicitly before changing it."' in strings
    assert '"create.privacy_setup_desc": "Default is {value}. You can start writing now, or switch it to link-only or public here."' in strings
    assert '"create.visibility_private_desc": "Only you can play this story."' in strings
    assert '"create.visibility_unlisted_desc": "Send the link to friends' in strings
    assert '"create.visibility_public_desc": "Anyone can find and play your story."' in strings
    assert '"create.privacy_recorded_reply": "I’ve recorded {value}.' in strings

    checkpoint_start = source.index('data-create-privacy-settings="true"')
    checkpoint_end = source.index('{briefBusy ? (', checkpoint_start)
    checkpoint_segment = source[checkpoint_start:checkpoint_end]
    assert 't("create.field_visibility")' in checkpoint_segment
    assert 'data-create-privacy-choice={id}' in checkpoint_segment
    assert 'data-create-privacy-choice-desc="true"' in checkpoint_segment
    assert "style={cpStyles.privacySetupChoiceDesc}" in checkpoint_segment
    assert "BUDGET_OPTIONS.map" not in checkpoint_segment
    assert "DIFFICULTY_OPTIONS.map" not in checkpoint_segment
    assert "STORY_LANGUAGE_OPTIONS[uiLang].map" not in checkpoint_segment
    assert "TENSION_PROFILE_OPTIONS.map" not in checkpoint_segment

    composer_start = source.index("{privacyIntroComplete ? (")
    composer_end = source.index("{error ? <div style={cpStyles.error}>", composer_start)
    composer_segment = source[composer_start:composer_end]
    assert "...cpStyles.textareaWrap" in composer_segment
    assert "appendGuideTurn(draftTurn)" in composer_segment


def test_prebrief_chat_hides_dashboards_and_brief_payload_still_uses_values() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()
    panels_source = (ROOT / "frontend2/src/pages/create/components/create-flow-panels.tsx").read_text()
    styles_source = (ROOT / "frontend2/src/pages/create/create-styles.ts").read_text()
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
    assert "runLengthDetail" in source
    assert "pressureModeDetail" in source
    assert "storyLanguageDetail" in source
    assert "toneDetail" in source
    assert "t(selectedBudget.descKey)" in source
    assert "t(selectedDifficulty.descKey)" in source
    assert "selectedLanguage.desc" in source
    assert "t(selectedTension.descKey)" in source
    assert 'data-create-shape-read-row={row.id}' in panels_source
    assert 'data-create-shape-read-detail={row.id}' in panels_source
    assert "storyShapeLedgerValue" in styles_source
    assert "storyShapeLedgerDetail" in styles_source
    assert 'data-create-brief-handoff-note="true"' in panels_source
    assert 'data-create-brief-play-plan="true"' in panels_source
    assert 't("create.brief_handoff_note_ready")' in panels_source
    assert 't("create.brief_handoff_note_blocked")' in panels_source
    assert 't("create.brief_play_plan_label")' in panels_source
    assert "briefHandoffNote" in styles_source
    assert "briefPlayPlanItems" in styles_source

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
        '"create.budget_medium_desc": "A full episode, complete arc."',
        '"create.difficulty_story_desc": "You can\'t really lose. The story always lands on a complete ending."',
        '"create.tension_auto_desc": "Infer the profile from the seed."',
        '"create.setting_run_length": "时长"',
        '"create.setting_pressure_mode": "压力模式"',
        '"create.setting_story_language": "故事语言"',
        '"create.setting_tone": "语气"',
        '"create.budget_medium_desc": "一集短剧，起承转合完整"',
        '"create.difficulty_story_desc": "你不会真正失败，故事一定会走到一个完整结局。"',
        '"create.tension_auto_desc": "根据种子自动判断张力类型"',
        '"create.brief_handoff_note_ready": "Next, I’ll generate role cards, the opening passage, and playable choices, then send you into Play."',
        '"create.brief_handoff_note_blocked": "Tighten the Brief first; once ready, I’ll build the first scene and playable choices."',
        '"create.brief_play_plan_label": "Ready for Play"',
        '"create.brief_handoff_note_ready": "下一步会生成角色身份、第一段叙事和可选择行动，然后直接进入 Play。"',
        '"create.brief_handoff_note_blocked": "先补强 Brief；准备好后再生成第一幕和可玩选择。"',
        '"create.brief_play_plan_label": "可进入 Play"',
    ):
        assert key in strings


def test_story_brief_revision_actions_explain_click_effect() -> None:
    panels_source = (ROOT / "frontend2/src/pages/create/components/create-flow-panels.tsx").read_text()
    styles_source = (ROOT / "frontend2/src/pages/create/create-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert 'data-create-brief-revision-hint="true"' in panels_source
    assert 't("create.brief_revision_hint")' in panels_source
    assert 'data-create-brief-revision-action-desc="true"' in panels_source
    assert "briefRevisionActionLabel" in styles_source
    assert "briefRevisionActionDesc" in styles_source
    assert "briefRevisionHint" in styles_source
    assert '"create.brief_revision_hint": "点一条会把修正加入对话，再重新整理 Brief。"' in strings
    assert '"create.brief_revision_hint": "Choose one to add that correction to the chat, then reshape the Brief."' in strings


def test_empty_create_composer_teaches_seed_recipe_before_examples() -> None:
    source = (ROOT / "frontend2/src/pages/create/create-page.tsx").read_text()
    styles = (ROOT / "frontend2/src/pages/create/create-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    recipe_idx = source.index('data-create-seed-recipe="true"')
    examples_idx = source.index("visibleSeedExamples.map")
    assert recipe_idx < examples_idx
    assert 't("create.seed_recipe_label")' in source
    assert 't("create.seed_recipe_people_label")' in source
    assert 't("create.seed_recipe_pressure_label")' in source
    assert 't("create.seed_recipe_secret_label")' in source
    assert 'hasSeed ? t("create.guide_add_correction") : t("create.guide_add_opening")' in source
    assert "seedRecipe:" in styles
    assert "seedRecipeLine:" in styles
    assert 'gridTemplateColumns: "minmax(0, 1fr) 148px"' in styles
    assert 'composerHint: {\n    display: "block"' in styles
    assert 'composerBar: {\n    gridColumn: "2"' in styles
    assert 'flexDirection: "column" as const' in styles
    for key in (
        '"create.seed_recipe_label": "A strong seed needs"',
        '"create.seed_recipe_people_label": "Who is present"',
        '"create.seed_recipe_pressure_label": "Why now"',
        '"create.seed_recipe_secret_label": "What can break"',
        '"create.guide_add_opening": "Send opening"',
        '"create.guide_add_correction": "Send correction"',
        '"create.seed_recipe_label": "好种子需要"',
        '"create.seed_recipe_people_label": "谁在场"',
        '"create.seed_recipe_pressure_label": "为什么现在"',
        '"create.seed_recipe_secret_label": "什么会爆"',
        '"create.guide_add_opening": "发送开场"',
        '"create.guide_add_correction": "发送修正"',
    ):
        assert key in strings


def test_opening_generation_wait_state_explains_playable_outputs() -> None:
    panels_source = (ROOT / "frontend2/src/pages/create/components/create-flow-panels.tsx").read_text()
    styles_source = (ROOT / "frontend2/src/pages/create/create-styles.ts").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    assert "export function BusyBuildPreview" in panels_source
    assert 'data-create-opening-build-preview="true"' in panels_source
    assert "BUSY_BUILD_PREVIEW" in panels_source
    assert 'data-create-opening-build-preview-item={state}' in panels_source
    assert "BUSY_PREVIEW_STATE_LABEL_KEYS" in panels_source
    assert '"create.busy_preview_role"' in panels_source
    assert '"create.busy_preview_opening"' in panels_source
    assert '"create.busy_preview_choices"' in panels_source
    assert "busyPreviewGridCompact" in styles_source
    assert "busyPreviewItemActive" in styles_source
    assert "busyPreviewItemDone" in styles_source
    assert "busyPreviewStatusCurrent" in styles_source

    for key in (
        '"create.busy_preview_role": "Player role"',
        '"create.busy_preview_opening": "First scene"',
        '"create.busy_preview_choices": "First moves"',
        '"create.busy_preview_done": "Ready"',
        '"create.busy_preview_current": "Building"',
        '"create.busy_preview_pending": "Next"',
        '"create.busy_preview_role": "玩家身份"',
        '"create.busy_preview_opening": "第一幕"',
        '"create.busy_preview_choices": "首轮行动"',
        '"create.busy_preview_done": "已准备"',
        '"create.busy_preview_current": "正在做"',
        '"create.busy_preview_pending": "接下来"',
    ):
        assert key in strings
