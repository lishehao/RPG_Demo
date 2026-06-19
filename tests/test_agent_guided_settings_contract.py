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
    assert "const [privacySetupVisible, setPrivacySetupVisible] = useState(false)" in source
    assert 'data-create-privacy-summary="true"' in source
    assert 'data-create-privacy-change="true"' in source
    assert "setPrivacySetupVisible(true)" in source
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
    assert '"create.privacy_summary_label": "Visibility"' in strings
    assert '"create.privacy_summary_change": "Change"' in strings
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

    summary_start = source.index('data-create-privacy-summary="true"')
    summary_end = source.index('{briefBusy ? (', summary_start)
    summary_segment = source[summary_start:summary_end]
    assert 't("create.privacy_summary_label")' in summary_segment
    assert 't(selectedVisibility.labelKey)' in summary_segment
    assert 't("create.privacy_summary_change")' in summary_segment
    assert "VISIBILITY_OPTION_IDS.map" not in summary_segment

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
    assert '"create.brief_revision_actions": "让第一幕更稳"' in strings
    assert '"create.brief_revision_hint": "点一条补进草稿，我会重新整理这张计划。"' in strings
    assert '"create.brief_revision_actions": "Ways to strengthen"' in strings
    assert '"create.brief_revision_hint": "Pick one to add it to your notes, then I’ll reshape this plan."' in strings
    assert "Choose one to add that correction to the chat" not in strings
    assert "Revision actions" not in strings


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
    assert "const composerActionLabel = !hasSeed" in source
    assert 't("create.guide_add_opening")' in source
    assert 't("create.guide_add_answer")' in source
    assert 't("create.guide_add_correction")' in source
    assert "activeBrief || guideReadyToBrief" in source
    assert 'hasSeed ? t("create.guide_add_correction") : t("create.guide_add_opening")' not in source
    assert 't("create.char_count", { n: draftTurn.length })' in source
    assert 't("create.char_count", { n: seed.length })' not in source
    assert "const composerProgressHint =" in source
    assert 't("create.guide_next_prompt_hint")' in source
    assert 't("create.guide_ready_brief_hint")' in source
    assert "create.submit_shortcut" not in source
    assert "create.submit_shortcut" not in strings
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
        '"create.placeholder_short": "Who is present / why now / what unlocks moves"',
        '"create.guide_input_placeholder_short": "Who / why now / what unlocks moves"',
        '"create.seed_recipe_secret_detail": "Evidence, objects, lies, or a decision that unlocks moves."',
        '"create.guide_add_opening": "Send opening"',
        '"create.guide_add_answer": "Send answer"',
        '"create.guide_add_correction": "Send update"',
        '"create.brief_keep_correcting": "Add more detail"',
        '"create.guide_revision_count": "{n} follow-ups"',
        '"create.guide_next_prompt_hint": "Answer the Story Butler prompt next."',
        '"create.guide_ready_brief_hint": "The Story Brief will shape itself once ready."',
        '"create.seed_recipe_label": "好种子需要"',
        '"create.seed_recipe_people_label": "谁在场"',
        '"create.seed_recipe_pressure_label": "为什么现在"',
        '"create.seed_recipe_secret_label": "什么会爆"',
        '"create.placeholder_short": "谁在场 / 为什么现在 / 什么会解锁行动"',
        '"create.guide_input_placeholder_short": "谁在场 / 为什么现在 / 什么会解锁行动"',
        '"create.seed_recipe_secret_detail": "会解锁行动的证据、物品、谎言或选择。"',
        '"create.guide_add_opening": "发送开场"',
        '"create.guide_add_answer": "发送回答"',
        '"create.guide_add_correction": "发送补充"',
        '"create.brief_keep_correcting": "补更多细节"',
        '"create.guide_revision_count": "{n} 条补充"',
        '"create.guide_next_prompt_hint": "继续回答 Story Butler 的追问"',
        '"create.guide_ready_brief_hint": "信息足够后会自动整理 Brief"',
    ):
        assert key in strings


def test_create_story_brief_card_uses_player_facing_plan_language() -> None:
    panels_source = (ROOT / "frontend2/src/pages/create/components/create-flow-panels.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()
    brief_source = (ROOT / "rpg_backend/narrative/brief.py").read_text()
    contracts_source = (ROOT / "rpg_backend/narrative/contracts.py").read_text()

    assert "FIT_REASON_LABEL_KEYS" in panels_source
    assert 't("create.brief_plan_note")' in panels_source
    assert "{brief.adaptation_note}" not in panels_source
    assert "{brief.runtime_fit_rationale}" not in panels_source
    assert '"create.brief_card_label": "Scene plan · Story Brief"' in strings
    assert '"create.brief_fit": "Ready for Play"' in strings
    assert '"create.brief_plan_note": "This is the plan for the first playable scene.' in strings
    assert '"create.brief_fit_reason_fit": "This has enough cast, pressure, and player focus' in strings
    assert '"create.brief_profile": "Story feel"' in strings
    assert '"create.brief_primary_cast": "Main cast"' in strings
    assert '"create.brief_kernel": "Core tension"' in strings
    assert '"create.brief_constraints": "Must keep"' in strings
    assert '"create.brief_card_mechanic": "Player hook"' in strings
    assert '"create.brief_card_label": "场景计划 · Brief"' in strings
    assert '"create.brief_fit": "可进入故事"' in strings
    assert '"create.brief_plan_note": "这是接下来生成第一幕会使用的计划。' in strings
    assert '"create.brief_profile": "故事气质"' in strings
    assert '"create.brief_primary_cast": "主要人物"' in strings
    assert '"create.brief_kernel": "核心冲突"' in strings
    assert '"create.brief_constraints": "必须保留"' in strings
    assert '"create.brief_card_mechanic": "玩家抓手"' in strings
    for stale_copy in (
        "Production slate · Story Brief",
        "Ready to try generation",
        "Beta planner draft",
        "current multi-party runtime",
        '"create.brief_profile": "Profile"',
        '"create.brief_kernel": "Tension kernel"',
        '"create.brief_card_mechanic": "Intervention card"',
        '"create.brief_constraints": "Preserved constraints"',
    ):
        assert stale_copy not in strings
        assert stale_copy not in brief_source
        assert stale_copy not in contracts_source


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
