from __future__ import annotations

import re

from rpg_backend.narrative.contracts import (
    DEFAULT_TEMPLATE_LANGUAGE,
    Difficulty,
    StoryGuideInlineLedger,
    StoryGuideLoopState,
    StoryGuideNodeName,
    StoryGuideSettingDeltas,
    StoryGuideSlot,
    StoryGuideSlotId,
    StoryGuideTurnResponse,
    TemplateLanguage,
    TemplateVisibility,
    TensionProfile,
)


SLOT_ORDER: tuple[StoryGuideSlotId, ...] = (
    "player_role",
    "active_cast",
    "pressure",
    "tone",
    "boundaries",
    "first_scene_hook",
)

SLOT_LABELS: dict[TemplateLanguage, dict[StoryGuideSlotId, str]] = {
    "zh": {
        "player_role": "玩家身份",
        "active_cast": "在场人物/阵营",
        "pressure": "争议物/压力",
        "tone": "类型语气",
        "boundaries": "禁用项/边界",
        "first_scene_hook": "第一幕钩子",
    },
    "en": {
        "player_role": "player role",
        "active_cast": "active cast/factions",
        "pressure": "contested object/pressure",
        "tone": "tone/genre",
        "boundaries": "boundaries",
        "first_scene_hook": "first-scene hook",
    },
}

UNSAFE_RE = re.compile(
    r"\b(drugs?|addiction|addicted|cocaine|heroin|meth|opioids?|overdose|narcotics?)\b|毒品|吸毒|成瘾|上瘾|药物滥用|海洛因|可卡因|冰毒",
    re.I,
)
PARTICIPANT_RE = re.compile(
    r"\b(parent|parents|teen|volunteer|customer|attendant|cofounder|investor|rival|assistant|manager|committee|witness|publicist|producer|dancer|sponsor|singer|audience|fans|bride|groom|family|lawyer|host|guest|chef|judge)\b|角色|家人|父母|志愿者|顾客|店员|合伙人|投资人|对手|见证人|制作人|公关|舞者|赞助|歌手|观众|新娘|新郎|家庭|律师|主持人|客人|评委",
    re.I,
)
PRESSURE_RE = re.compile(
    r"\b(secret|vote|deadline|decision|rumou?r|recording|letter|photo|ring|wedding ring|contract|merger|inheritance|mystery|clue|artifact|oxygen|show|livestream|public|pressure|conflict|disappearance|scandal|betrayal|goes wrong)\b|争议|决定|秘密|投票|期限|录音|照片|戒指|婚戒|合约|并购|继承|谜团|线索|神器|氧气|表演|直播|公开|压力|冲突|失踪|丑闻|背叛",
    re.I,
)
TONE_RE = re.compile(
    r"\b(high drama|drama|dramatic|cozy|comedy|comic|funny|mystery|fantasy|sci[- ]?fi|science fiction|social|slice of life|quiet|family|romance|thriller)\b|高戏剧|戏剧|轻松|温和|喜剧|悬疑|奇幻|科幻|社交|日常|安静|家庭|恋爱|惊悚",
    re.I,
)
BOUNDARY_RE = re.compile(
    r"\b(no |without |avoid |must not|do not|don't|never|not happen|boundary|boundaries)\b|禁止|不要|不能|避免|不许|别|边界",
    re.I,
)
HOOK_RE = re.compile(
    r"\b(at |during |before |after |when |inside |on stage|gala|meeting|laundromat|library|bake sale|boardroom|colony|talent show|table|dinner|opening|first scene|backstage|control room)\b|第一幕|开场|当|在|期间|晚宴|会议|洗衣店|图书馆|义卖|董事会|殖民地|才艺秀|桌上|后台|控制室",
    re.I,
)
TINY_GREETING_RE = re.compile(r"^(hi|hello|hey|yo|ok|okay|你好|嗨|哈喽|哈罗)[.!。！?？]*$", re.I)
AMBIGUOUS_WHO_RE = re.compile(r"^(who\?|who|谁|谁？)$", re.I)
SELF_ROLE_RE = re.compile(r"^(me|myself|i do|i am|i'm in|i'll play|我|我来|我自己|我扮演)$", re.I)

STORY_BUTLER_VOICE_SKILLS: dict[str, dict[str, object]] = {
    "opening_scene_prompt": {
        "job": "ask for one concrete opening scene spark when the seed is empty, tiny, or missing a first-shot anchor",
        "response_shape": "micro-hook from the desk, then one question about where trouble first appears",
        "tone_anchors": ["quiet writing desk", "opening scene", "first trouble"],
        "example_moves": [
            "You are at the writing desk. Give me one scene to open on: where are we when trouble first appears?",
            "Start with the camera. Where are we when the first problem enters the room?",
        ],
    },
    "role_focus": {
        "job": "identify the player's role or point of view in the first playable scene",
        "response_shape": "echo the seed's concrete setting or pressure, then ask who the player is closest to",
        "tone_anchors": ["player lens", "first room", "closest to trouble"],
        "example_moves": [
            "A gala with the floor about to crack. Who is closest to the trouble when it starts?",
            "That has a public spark. Who are you when the room first turns?",
        ],
    },
    "cast_focus": {
        "job": "collect two or three people, groups, or factions that must be present",
        "response_shape": "acknowledge the player lens if known, then ask for who else must be in the room",
        "tone_anchors": ["cast in the room", "pressure holder", "witness or opposition"],
        "example_moves": [
            "Got it: you are in the scene. Who else must be in the room when trouble starts?",
            "If you mean cast, give me two people or factions who cannot be missing from the first scene.",
        ],
    },
    "pressure_focus": {
        "job": "find the first pressure, decision, contested object, or public consequence",
        "response_shape": "name the live setting, then ask what pressure hits first",
        "tone_anchors": ["public pressure", "decision", "thing that goes wrong"],
        "example_moves": [
            "The room is set. What pressure hits first: an accusation, disappearance, decision, or exposed secret?",
            "Whoever is there needs a live problem. What goes wrong before anyone can leave?",
        ],
    },
    "tone_focus": {
        "job": "select the story feel only after scene, role, cast, and pressure are clear enough",
        "response_shape": "summarize the playable ingredients, then ask for one tonal direction",
        "tone_anchors": ["high drama", "mystery", "social rupture", "comedy edge"],
        "example_moves": [
            "The crisis has a room and pressure. Should it cut as high drama, mystery, comedy, or social rupture?",
        ],
    },
    "boundary_redirect": {
        "job": "redirect unsafe or contradictory input into a playable social, investigative, or public-pressure alternative",
        "response_shape": "calm refusal or clarification, then one safer question",
        "tone_anchors": ["safe pressure", "public choice", "misread evidence"],
        "example_moves": [
            "I cannot build that scene as requested. Keep the pressure social or investigative: who is trying to stop harm before it escalates?",
        ],
    },
    "brief_readiness": {
        "job": "confirm enough story material exists and invite either Story Brief shaping or one last correction",
        "response_shape": "short confidence line grounded in scene nouns, then one optional correction question",
        "tone_anchors": ["playable promise", "ready to shape", "last correction"],
        "example_moves": [
            "That has a stage, witness, and pressure. Want me to shape the Story Brief now, or add one boundary first?",
        ],
    },
}


def create_initial_story_guide_state(language: TemplateLanguage = DEFAULT_TEMPLATE_LANGUAGE) -> StoryGuideLoopState:
    labels = SLOT_LABELS[language]
    return StoryGuideLoopState(
        status="empty",
        lastNode="parse_message",
        slots={slot: StoryGuideSlot(id=slot, filled=False, label=labels[slot], evidence="") for slot in SLOT_ORDER},
        acceptedTurns=[],
        blockedTurns=[],
        nextMissing="pressure",
    )


def can_shape_story_brief(state: StoryGuideLoopState) -> bool:
    filled = [slot for slot in SLOT_ORDER if state.slots[slot].filled]
    return bool(
        state.slots["active_cast"].filled
        and state.slots["pressure"].filled
        and state.slots["first_scene_hook"].filled
        and len(filled) >= 4
    )


def build_story_guide_ledger(
    state: StoryGuideLoopState,
    language: TemplateLanguage = DEFAULT_TEMPLATE_LANGUAGE,
) -> StoryGuideInlineLedger:
    labels = SLOT_LABELS[language]
    known = [labels[slot] for slot in SLOT_ORDER if state.slots[slot].filled]
    missing = [labels[slot] for slot in SLOT_ORDER if not state.slots[slot].filled]
    return StoryGuideInlineLedger(
        knownLabel="已知" if language == "zh" else "Known",
        stillNeedLabel="还需要" if language == "zh" else "Still need",
        nextQuestionLabel="下一问" if language == "zh" else "Next question",
        known=" · ".join(known) if known else ("先等你的第一句" if language == "zh" else "waiting for your first line"),
        stillNeed=" · ".join(missing[:3]) if missing else ("已足够整理 Brief" if language == "zh" else "enough to shape the Brief"),
        nextQuestion=_next_question(state.nextMissing, language),
    )


def story_butler_voice_policy(
    turn: StoryGuideTurnResponse,
    *,
    message: str,
    current_seed: str = "",
    previous_assistant_reply: str = "",
) -> dict[str, object]:
    skill_id = _select_story_butler_voice_skill(turn, message)
    policy = STORY_BUTLER_VOICE_SKILLS[skill_id]
    return {
        "id": skill_id,
        "job": policy["job"],
        "response_shape": policy["response_shape"],
        "tone_anchors": policy["tone_anchors"],
        "example_moves": policy["example_moves"],
        "focus_slot": turn.state.nextMissing,
        "node": turn.node,
        "conversation_status": turn.status,
        "grounding_terms": _extract_grounding_terms(" ".join([current_seed, message])),
        "previous_assistant_reply": _short_evidence(previous_assistant_reply),
        "variation_instruction": (
            "Do not repeat the previous assistant reply or sentence shape. "
            "Use the selected skill's job and current scene nouns to phrase a fresh, concise one-question response."
        ),
    }


def advance_story_guide_loop(
    previous_state: StoryGuideLoopState | None,
    raw_text: str,
    language: TemplateLanguage = DEFAULT_TEMPLATE_LANGUAGE,
) -> StoryGuideTurnResponse:
    text = raw_text.strip()
    previous = _sync_labels(previous_state or create_initial_story_guide_state(language), language)
    settings = infer_story_guide_settings(text, language)
    if not text:
        state = previous.model_copy(update={"status": "needs_field", "lastNode": "ask_missing_slot"})
        return _response(state, "ask_missing_slot", _next_question(state.nextMissing, language), False, False, settings, language)

    if UNSAFE_RE.search(text):
        state = previous.model_copy(
            update={
                "status": "redirect",
                "lastNode": "redirect_out_of_spec",
                "blockedTurns": [*previous.blockedTurns, text],
            }
        )
        reply = (
            "这个 beta 不会围绕毒品使用或成瘾来搭故事。我们可以把它改成公开压力、被误读的证据、或一个必须当场决定的物件。"
            if language == "zh"
            else "I can’t build this beta around drug use or addiction. We can redirect it into public pressure, misunderstood evidence, or a contested decision in the room."
        )
        return _response(state, "redirect_out_of_spec", reply, False, True, settings, language, include_ledger=False)

    if settings.privacyIntent and _is_privacy_only(text):
        ready = can_shape_story_brief(previous)
        state = previous.model_copy(
            update={
                "status": "ready_to_brief" if ready else "needs_field",
                "lastNode": "ready_to_shape" if ready else "ask_missing_slot",
            }
        )
        reply = (
            "发布范围我不会从聊天里偷偷改。你现在还是按上面的「谁能玩」设置来保存；要公开，点那一行改成「广场公开」。"
            if language == "zh"
            else "I will not silently change publishing from chat. This story still uses the explicit “Who can play this” row above the composer; switch that row to Public if you want everyone to play it."
        )
        return _response(state, state.lastNode, reply, False, False, settings, language)

    if _is_tiny_non_story_input(text) and not previous.acceptedTurns:
        state = previous.model_copy(update={"status": "needs_field", "lastNode": "ask_missing_slot", "nextMissing": "pressure"})
        return _response(state, "ask_missing_slot", _tiny_seed_reply(language), False, False, settings, language)

    if _is_ambiguous_who_question(text):
        state = previous.model_copy(update={"status": "needs_field", "lastNode": "ask_missing_slot"})
        return _response(state, "ask_missing_slot", _who_clarification_reply(language), False, False, settings, language)

    if _detects_hard_conflict(text):
        state = previous.model_copy(update={"status": "clarify_conflict", "lastNode": "clarify_conflict"})
        reply = (
            "我看到你同时要求回避这类动作、又让它成为主要推进。先选一个方向：要不要把冲突改成公开选择或误会证据？"
            if language == "zh"
            else "I’m seeing a conflict: the note forbids a kind of action while also making it drive the scene. Should we convert that pressure into a public choice or misunderstood evidence instead?"
        )
        return _response(state, "clarify_conflict", reply, False, False, settings, language)

    self_role_answer = _is_self_role_answer(text) and previous.nextMissing == "player_role" and bool(previous.acceptedTurns)
    extracted = _extract_slots(text)
    if self_role_answer:
        extracted["player_role"] = "player as themselves" if language == "en" else "玩家自己"
    updated = _merge_slots(previous, extracted, language)
    if _detects_unsupported_small_cast_direction(text):
        slots = dict(updated.slots)
        slots["active_cast"] = slots["active_cast"].model_copy(update={"filled": False, "evidence": ""})
        slots["pressure"] = slots["pressure"].model_copy(update={"filled": False, "evidence": ""})
        state = updated.model_copy(
            update={
                "acceptedTurns": [*previous.acceptedTurns, text],
                "slots": slots,
                "status": "needs_field",
                "lastNode": "ask_missing_slot",
                "nextMissing": "active_cast",
            }
        )
        reply = (
            "我看到的是两人、低冲突、物件线索。这个 beta 需要至少第三方在场压力或公开后果，才能变成可玩的 Story Brief。加一个旁观者、阵营或必须当场选择的压力。"
            if language == "zh"
            else "I’m reading this as two people, low conflict, and an object-only thread. This beta needs a third active pressure or public consequence before I shape a Story Brief. Add one watcher, faction, or decision that must be handled in the room."
        )
        return _response(state, "ask_missing_slot", reply, True, False, settings, language)

    next_missing = _find_next_missing(updated)
    ready = can_shape_story_brief(updated.model_copy(update={"nextMissing": next_missing}))
    state = updated.model_copy(
        update={
            "acceptedTurns": [*previous.acceptedTurns, text],
            "status": "ready_to_brief" if ready else "needs_field",
            "lastNode": "ready_to_shape" if ready else "ask_missing_slot",
            "nextMissing": next_missing,
        }
    )
    return _response(
        state,
        state.lastNode,
        _ready_reply(language) if ready else _self_role_reply(state.nextMissing, language) if self_role_answer else _missing_reply(state.nextMissing, language, state),
        True,
        False,
        settings,
        language,
    )


def infer_story_guide_settings(text: str, language: TemplateLanguage) -> StoryGuideSettingDeltas:
    settings: dict[str, object] = {}
    if re.search(r"\b(short|quick|shorter|10\s*(min|minute|minutes)|short run)\b|短一点|短篇|十分钟|10分钟", text, re.I):
        settings["turnBudget"] = 8
    elif re.search(r"\b(long|longer|25\s*(min|minute|minutes)|epic)\b|长一点|长篇|史诗|25分钟|二十五分钟", text, re.I):
        settings["turnBudget"] = 20
    elif re.search(r"\b(15\s*(min|minute|minutes)|one sitting)\b|15分钟|十五分钟|一口气|一坐", text, re.I):
        settings["turnBudget"] = 12

    difficulty: Difficulty | None = None
    if re.search(r"\b(hard mode|npc(?:s)? fight back|make it dangerous|can i lose|gauntlet)\b|博弈|反击|会输|高难|危险一点", text, re.I):
        difficulty = "gauntlet"
    elif re.search(r"\b(story mode|easy mode|gentle mode|can't lose|cannot lose)\b|故事模式|不要输", text, re.I):
        difficulty = "story"
    if difficulty:
        settings["difficulty"] = difficulty

    if re.search(r"\b(make it chinese|switch (?:it )?to chinese|in chinese|write in chinese)\b|中文|改成中文|切到中文|用中文|简体中文", text, re.I):
        settings["language"] = "zh"
    elif re.search(r"\b(make it english|switch (?:it )?to english|in english|write in english)\b|英文|英语|改成英文|切到英文|用英文写|用英语写", text, re.I):
        settings["language"] = "en"
    else:
        cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
        latin_count = len(re.findall(r"[A-Za-z]", text))
        if cjk_count >= 6 and cjk_count > latin_count / 2:
            settings["language"] = "zh"
        elif latin_count >= 16 and latin_count > cjk_count * 2:
            settings["language"] = "en"
        else:
            settings["language"] = language

    profile: TensionProfile | None = None
    if re.search(r"\b(mars|colony|artifact|relic|auction|faction|clan|dragon|eclipse|star-?map|sci[- ]?fi|science fiction)\b|火星|殖民地|神器|拍卖|阵营|氏族|龙族|日食|星图|科幻|奇幻", text, re.I):
        profile = "fantasy_sci_fi"
    elif re.search(r"\b(backstage|disappearance|public scandal|livestream|awards?|idol|singer|producer|public fallout|high drama|dramatic|thriller|pressure)\b|后台|失踪|直播|颁奖|偶像|主唱|制作人|舆论|高戏剧|惊悚|压力", text, re.I):
        profile = "high_drama"
    elif re.search(r"\b(funny|awkward|misunderstanding|comedy|comic)\b|喜剧|搞笑|尴尬|误会", text, re.I):
        profile = "comedy"
    elif re.search(r"\b(cozy|clues?|small town|gentle mystery)\b|轻悬疑|温和悬疑|线索|小镇", text, re.I):
        profile = "cozy_mystery"
    elif re.search(r"\b(family|banquet|wedding|relationship rupture|inheritance|will reading)\b|家庭|家宴|婚礼|继承|遗嘱|关系破裂", text, re.I):
        profile = "high_drama" if re.search(r"\b(betrayal|scandal|deadline|public|disappearance|blackmail)\b|背叛|丑闻|期限|公开|失踪", text, re.I) else "family_social"
    elif re.search(r"\b(slice of life|social pressure|social)\b|日常|社交", text, re.I):
        profile = "family_social"
    if profile:
        settings["tensionProfile"] = profile

    privacy = _detect_privacy_intent(text)
    if privacy:
        settings["privacyIntent"] = privacy
    return StoryGuideSettingDeltas.model_validate(settings)


def _response(
    state: StoryGuideLoopState,
    node: StoryGuideNodeName,
    reply: str,
    accepted: bool,
    blocked: bool,
    settings: StoryGuideSettingDeltas,
    language: TemplateLanguage,
    *,
    include_ledger: bool = True,
) -> StoryGuideTurnResponse:
    return StoryGuideTurnResponse(
        state=state,
        node=node,
        status=state.status,
        reply=reply,
        acceptedText=accepted,
        blocked=blocked,
        canShapeBrief=can_shape_story_brief(state),
        settings=settings,
        ledger=build_story_guide_ledger(state, language) if include_ledger else None,
        source="deterministic_fallback",
    )


def _sync_labels(state: StoryGuideLoopState, language: TemplateLanguage) -> StoryGuideLoopState:
    labels = SLOT_LABELS[language]
    slots = {slot: state.slots[slot].model_copy(update={"label": labels[slot]}) for slot in SLOT_ORDER}
    return state.model_copy(update={"slots": slots})


def _merge_slots(
    previous: StoryGuideLoopState,
    extracted: dict[StoryGuideSlotId, str],
    language: TemplateLanguage,
) -> StoryGuideLoopState:
    synced = _sync_labels(previous, language)
    slots = dict(synced.slots)
    for slot, evidence in extracted.items():
        if evidence:
            slots[slot] = slots[slot].model_copy(update={"filled": True, "evidence": evidence[:220]})
    return synced.model_copy(update={"status": "collecting", "lastNode": "update_slots", "slots": slots})


def _extract_slots(text: str) -> dict[StoryGuideSlotId, str]:
    slots: dict[StoryGuideSlotId, str] = {}
    if re.search(r"\b(i am|i'm|my role|i play|as the|as a|player is|protagonist is)\b|我(是|扮演)|玩家|主角", text, re.I):
        slots["player_role"] = _short_evidence(text)
    participants = _find_terms(PARTICIPANT_RE, text)
    if len(participants) >= 2 or re.search(r"\b(with|between|against|and|versus|vs\.?)\b|和|与|对上|之间", text, re.I):
        slots["active_cast"] = " / ".join(participants[:5]) if participants else _short_evidence(text)
    pressures = _find_terms(PRESSURE_RE, text)
    if pressures or re.search(r"\bmust decide\b|\bgoes wrong\b|\babout to\b|\bfalls apart\b|必须|快要|失控|当众|逼近", text, re.I):
        slots["pressure"] = " / ".join(pressures[:4]) if pressures else _short_evidence(text)
    tones = _find_terms(TONE_RE, text)
    if tones:
        slots["tone"] = " / ".join(tones[:3])
    if BOUNDARY_RE.search(text):
        slots["boundaries"] = _short_evidence(text)
    if HOOK_RE.search(text):
        slots["first_scene_hook"] = _short_evidence(text)
    return slots


def _find_terms(pattern: re.Pattern[str], text: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        value = next((group for group in match.groups() if group), match.group(0))
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(value.strip())
    return terms


def _find_next_missing(state: StoryGuideLoopState) -> StoryGuideSlotId | None:
    for slot in SLOT_ORDER:
        if not state.slots[slot].filled:
            return slot
    return None


def _select_story_butler_voice_skill(turn: StoryGuideTurnResponse, message: str) -> str:
    if turn.blocked or turn.node in {"redirect_out_of_spec", "clarify_conflict"}:
        return "boundary_redirect"
    if turn.status == "ready_to_brief" or turn.node == "ready_to_shape":
        return "brief_readiness"
    if _is_tiny_non_story_input(message):
        return "opening_scene_prompt"
    if _is_ambiguous_who_question(message):
        return "cast_focus"
    slot = turn.state.nextMissing
    if slot == "player_role":
        return "role_focus"
    if slot == "active_cast":
        return "cast_focus"
    if slot == "pressure":
        return "pressure_focus"
    if slot == "tone":
        return "tone_focus"
    if slot == "boundaries":
        return "boundary_redirect"
    if slot == "first_scene_hook":
        return "opening_scene_prompt"
    return "opening_scene_prompt"


def _extract_grounding_terms(text: str) -> list[str]:
    normalized = re.sub(r"[^\w\s\u3400-\u9fff-]", " ", text.casefold())
    words = [word.strip("-_") for word in normalized.split()]
    stopwords = {
        "the",
        "and",
        "with",
        "that",
        "this",
        "where",
        "what",
        "who",
        "when",
        "before",
        "after",
        "into",
        "from",
        "story",
        "scene",
        "goes",
        "wrong",
        "there",
        "their",
        "your",
        "you",
        "are",
        "will",
        "must",
        "need",
        "needs",
        "first",
        "room",
    }
    terms: list[str] = []
    for word in words:
        if len(word) < 3 or word in stopwords:
            continue
        if word not in terms:
            terms.append(word)
        if len(terms) >= 8:
            break
    return terms


def _next_question(slot: StoryGuideSlotId | None, language: TemplateLanguage) -> str:
    if language == "zh":
        mapping = {
            "player_role": "玩家在第一幕里是谁？",
            "active_cast": "第一幕里至少还有哪两个人或阵营在场？",
            "pressure": "他们必须当场处理的争议、物件或公开压力是什么？",
            "tone": "你想要高戏剧、喜剧、悬疑、科幻奇幻，还是关系压力？",
            "boundaries": "有什么必须保留或不能发生的边界？",
            "first_scene_hook": "第一幕从哪个具体场面开始？",
        }
    else:
        mapping = {
            "player_role": "Who is the player in the first scene?",
            "active_cast": "Who else is in the room, and who can push back?",
            "pressure": "What contested object, secret, decision, or public pressure must be handled now?",
            "tone": "Should this feel like high drama, comedy, mystery, speculative pressure, or social rupture?",
            "boundaries": "What must be preserved or avoided?",
            "first_scene_hook": "Where exactly does the first playable scene begin?",
        }
    return mapping.get(slot or "pressure", mapping["pressure"])


def _missing_reply(slot: StoryGuideSlotId | None, language: TemplateLanguage, state: StoryGuideLoopState | None = None) -> str:
    if not slot:
        return _ready_reply(language)
    context = _guide_state_context(state)
    if language == "zh":
        mapping = {
            "player_role": "已经有开端了。玩家在第一幕里是谁？",
            "active_cast": "把房间补齐。谁必须在场？两个名字、身份或阵营就够。",
            "pressure": "先给我第一道压力：指控、失踪、决定，还是被曝光的秘密？",
            "tone": "这版要偏高戏剧、喜剧、悬疑、科幻奇幻，还是关系压力？",
            "boundaries": "这版需要避开什么？给我一条边界就够。",
            "first_scene_hook": "第一幕从哪里开？给我一个地点、时刻或即将发生的动作。",
        }
    else:
        if slot == "player_role" and "gala" in context:
            return "A gala with the floor about to crack. Who is closest to the trouble when it starts?"
        if slot == "player_role" and ("livestream" in context or "stage" in context or "awards" in context):
            return "That has a stage and public pressure. Who is closest to the trouble when it starts?"
        mapping = {
            "player_role": "Good, we have the trouble. Who are you when it starts?",
            "active_cast": "Who must be in the room? Two names, roles, or factions are enough.",
            "pressure": "What public pressure hits first: an accusation, disappearance, decision, or exposed secret?",
            "tone": "Should this cut as high drama, comedy, mystery, speculative pressure, or social rupture?",
            "boundaries": "What should this version avoid? One boundary is enough.",
            "first_scene_hook": "Where does the first scene open before the room turns?",
        }
    return mapping[slot]


def _guide_state_context(state: StoryGuideLoopState | None) -> str:
    if state is None:
        return ""
    return " ".join(
        slot.evidence.casefold()
        for slot in state.slots.values()
        if slot.evidence
    )


def _tiny_seed_reply(language: TemplateLanguage) -> str:
    return (
        "你已经到写作桌前了。给我一个开场画面：麻烦第一次出现时，我们在哪里？"
        if language == "zh"
        else "You are at the writing desk. Give me one scene to open on: where are we when trouble first appears?"
    )


def _who_clarification_reply(language: TemplateLanguage) -> str:
    return (
        "如果你是在问阵容，给我两个必须在场的人或阵营。第一幕里谁不能缺席？"
        if language == "zh"
        else "If you mean cast, give me two people or factions who must be present. Who cannot be missing from the first scene?"
    )


def _self_role_reply(slot: StoryGuideSlotId | None, language: TemplateLanguage) -> str:
    if language == "zh":
        if slot == "active_cast":
            return "记下：玩家就是你。第一幕里谁还必须在场？"
        if slot == "pressure":
            return "记下：玩家就是你。这个房间里第一道压力是什么？"
        return f"记下：玩家就是你。{_next_question(slot, language)}"
    if slot == "active_cast":
        return "Noted: you are the player in the scene. Who else must be in the room?"
    if slot == "pressure":
        return "Noted: you are the player in the scene. What pressure hits you first in that room?"
    return f"Noted: you are the player in the scene. {_next_question(slot, language)}"


def _ready_reply(language: TemplateLanguage) -> str:
    return (
        "这些已经足够整理成 Story Brief。你也可以继续补充一个边界或第一幕细节。"
        if language == "zh"
        else "That is enough to shape a Story Brief. You can still add one boundary or first-scene detail before I do."
    )


def _short_evidence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    return cleaned[:160]


def _detects_hard_conflict(text: str) -> bool:
    lower = text.lower()
    return bool(("no conflict" in lower and re.search(r"\b(public pressure|fight|betrayal|blackmail)\b", lower)) or ("no mystery" in lower and "clue" in lower))


def _detects_unsupported_small_cast_direction(text: str) -> bool:
    lower = text.lower()
    has_two_person = bool(re.search(r"\btwo[- ]person\b|\bone customer\b.*\bone attendant\b|两人|两个人", lower, re.I))
    no_pressure = bool(re.search(r"\bno public pressure\b|\bno conflict\b|\bno mystery\b|没有公开压力|没有冲突|没有悬疑", lower, re.I))
    object_only = bool(re.search(r"\bwedding ring\b|\bring on a table\b|婚戒|戒指", lower, re.I))
    return has_two_person and no_pressure and object_only


def _is_tiny_non_story_input(text: str) -> bool:
    return bool(TINY_GREETING_RE.match(text.strip()))


def _is_ambiguous_who_question(text: str) -> bool:
    return bool(AMBIGUOUS_WHO_RE.match(text.strip()))


def _is_self_role_answer(text: str) -> bool:
    return bool(SELF_ROLE_RE.match(text.strip()))


def _detect_privacy_intent(text: str) -> TemplateVisibility | None:
    lower = text.lower()
    if re.search(r"\b(just me|only me|private|keep it private|no one else)\b|只有我|仅自己|私有|不要公开", lower):
        return "private"
    if re.search(r"\b(link only|unlisted|share by link|only by link|with the link)\b|链接可见|凭链接|仅链接", lower):
        return "unlisted"
    if re.search(r"\b(make it public|publish it|everyone can play|publicly visible|put it on the plaza)\b|公开发布|广场公开|所有人能玩|大家都能玩", lower):
        return "public"
    return None


def _is_privacy_only(text: str) -> bool:
    normalized = re.sub(r"[^\w\s\u3400-\u9fff]", " ", text.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized or len(normalized) > 64:
        return False
    if re.search(r"\b(public pressure|public scandal|public fallout|publicist)\b", normalized):
        return False
    return _detect_privacy_intent(normalized) is not None
