import type { Lang } from "./i18n"
import { inferStoryGuideSettings, isPrivacyOnlyRequest, type StoryGuideSettingDeltas } from "./story-guide-settings"
export { inferStoryGuideSettings } from "./story-guide-settings"
export type { StoryGuideSettingDeltas, StoryGuideTensionProfile } from "./story-guide-settings"

export type StoryGuideConversationState =
  | "empty"
  | "collecting"
  | "needs_field"
  | "clarify_conflict"
  | "redirect"
  | "analyzing"
  | "ready_to_brief"
  | "brief_ready"
  | "brief_not_fit"

export type StoryGuideNodeName =
  | "parse_message"
  | "safety_gate"
  | "update_slots"
  | "ask_missing_slot"
  | "clarify_conflict"
  | "redirect_out_of_spec"
  | "ready_to_shape"
  | "shape_story_brief"
  | "brief_ready"
  | "brief_not_fit"

export type StoryGuideSlotId =
  | "player_role"
  | "active_cast"
  | "pressure"
  | "tone"
  | "boundaries"
  | "first_scene_hook"

export type StoryGuideSlot = {
  id: StoryGuideSlotId
  filled: boolean
  label: string
  evidence: string
}

export type StoryGuideLoopState = {
  status: StoryGuideConversationState
  lastNode: StoryGuideNodeName
  slots: Record<StoryGuideSlotId, StoryGuideSlot>
  acceptedTurns: string[]
  blockedTurns: string[]
  nextMissing: StoryGuideSlotId | null
}

export type StoryGuideInlineLedger = {
  knownLabel: string
  stillNeedLabel: string
  nextQuestionLabel: string
  known: string
  stillNeed: string
  nextQuestion: string
}

export type StoryGuideLoopDecision = {
  state: StoryGuideLoopState
  node: StoryGuideNodeName
  status: StoryGuideConversationState
  reply: string
  acceptedText: boolean
  blocked: boolean
  canShapeBrief: boolean
  settings?: StoryGuideSettingDeltas
  ledger?: StoryGuideInlineLedger
}

const SLOT_ORDER: StoryGuideSlotId[] = [
  "player_role",
  "active_cast",
  "pressure",
  "tone",
  "boundaries",
  "first_scene_hook",
]

const SLOT_LABELS: Record<Lang, Record<StoryGuideSlotId, string>> = {
  zh: {
    player_role: "玩家身份",
    active_cast: "在场人物/阵营",
    pressure: "争议物/压力",
    tone: "类型语气",
    boundaries: "禁用项/边界",
    first_scene_hook: "第一幕钩子",
  },
  en: {
    player_role: "player role",
    active_cast: "active cast/factions",
    pressure: "contested object/pressure",
    tone: "tone/genre",
    boundaries: "boundaries",
    first_scene_hook: "first-scene hook",
  },
}

const UNSAFE_PATTERNS = [
  /\bdrugs?\b/i,
  /\baddiction\b/i,
  /\baddict(?:ed|ion)?\b/i,
  /\bcocaine\b/i,
  /\bheroin\b/i,
  /\bmeth\b/i,
  /\bopioids?\b/i,
  /\boverdose\b/i,
  /\bnarcotics?\b/i,
  /毒品/,
  /吸毒/,
  /成瘾/,
  /上瘾/,
  /药物滥用/,
  /海洛因/,
  /可卡因/,
  /冰毒/,
]
const TINY_GREETING_PATTERN = /^(hi|hello|hey|yo|ok|okay|你好|嗨|哈喽|哈罗)[.!。！?？]*$/i
const AMBIGUOUS_WHO_PATTERN = /^(who\?|who|谁|谁？)$/i
const SELF_ROLE_PATTERN = /^(me|myself|i do|i am|i'm in|i'll play|我|我来|我自己|我扮演)$/i

const PARTICIPANT_TERMS = [
  "parent",
  "parents",
  "teen",
  "volunteer",
  "customer",
  "attendant",
  "cofounder",
  "investor",
  "investors",
  "rival",
  "assistant",
  "manager",
  "committee",
  "witness",
  "sister",
  "brother",
  "mother",
  "father",
  "wife",
  "husband",
  "bride",
  "groom",
  "club",
  "media",
  "faction",
  "clan",
  "librarian",
  "dragon",
  "council",
  "audience",
  "neighbor",
  "friend",
  "friends",
  "family",
  "families",
  "team",
  "lawyer",
  "host",
  "guest",
  "guests",
  "chef",
  "baker",
  "judge",
  "judges",
  "角色",
  "家人",
  "父母",
  "志愿者",
  "顾客",
  "店员",
  "合伙人",
  "投资人",
  "对手",
  "见证人",
  "姐姐",
  "妹妹",
  "哥哥",
  "弟弟",
  "母亲",
  "父亲",
  "妻子",
  "丈夫",
  "新娘",
  "新郎",
  "社团",
  "媒体",
  "阵营",
  "氏族",
  "图书管理员",
  "龙族",
  "长老会",
  "观众",
  "朋友",
  "家庭",
  "律师",
  "主持人",
  "客人",
  "评委",
]

const PRESSURE_TERMS = [
  "secret",
  "vote",
  "deadline",
  "decision",
  "rumor",
  "recording",
  "letter",
  "photo",
  "ring",
  "wedding ring",
  "cupcake",
  "label",
  "labels",
  "contract",
  "merger",
  "inheritance",
  "blackmail",
  "mystery",
  "clue",
  "eclipse",
  "star-map",
  "starmap",
  "spellbook",
  "artifact",
  "oxygen",
  "show",
  "talent show",
  "public",
  "pressure",
  "conflict",
  "争议",
  "决定",
  "秘密",
  "投票",
  "期限",
  "录音",
  "照片",
  "戒指",
  "婚戒",
  "标签",
  "合约",
  "并购",
  "继承",
  "谜团",
  "线索",
  "日食",
  "星图",
  "魔法书",
  "神器",
  "氧气",
  "表演",
  "才艺",
  "公开",
  "压力",
  "冲突",
]

const TONE_TERMS = [
  "high drama",
  "drama",
  "dramatic",
  "cozy",
  "comedy",
  "comic",
  "funny",
  "mystery",
  "fantasy",
  "sci-fi",
  "science fiction",
  "social",
  "slice of life",
  "quiet",
  "family",
  "romance",
  "高戏剧",
  "戏剧",
  "轻松",
  "温和",
  "喜剧",
  "悬疑",
  "奇幻",
  "科幻",
  "社交",
  "日常",
  "安静",
  "家庭",
  "恋爱",
]

const BOUNDARY_TERMS = [
  "no ",
  "without ",
  "avoid ",
  "must not",
  "do not",
  "don't",
  "never",
  "not happen",
  "boundary",
  "boundaries",
  "禁止",
  "不要",
  "不能",
  "避免",
  "不许",
  "别",
  "边界",
]

const HOOK_TERMS = [
  "at ",
  "during ",
  "before ",
  "after ",
  "when ",
  "inside ",
  "on stage",
  "gala",
  "meeting",
  "laundromat",
  "library",
  "bake sale",
  "boardroom",
  "colony",
  "talent show",
  "table",
  "dinner",
  "opening",
  "first scene",
  "第一幕",
  "开场",
  "当",
  "在",
  "期间",
  "晚宴",
  "会议",
  "洗衣店",
  "图书馆",
  "义卖",
  "董事会",
  "殖民地",
  "才艺秀",
  "桌上",
]

export function createInitialStoryGuideState(lang: Lang = "en"): StoryGuideLoopState {
  return {
    status: "empty",
    lastNode: "parse_message",
    slots: SLOT_ORDER.reduce((acc, id) => {
      acc[id] = { id, filled: false, label: SLOT_LABELS[lang][id], evidence: "" }
      return acc
    }, {} as Record<StoryGuideSlotId, StoryGuideSlot>),
    acceptedTurns: [],
    blockedTurns: [],
    nextMissing: "pressure",
  }
}

export function canShapeStoryBrief(state: StoryGuideLoopState): boolean {
  const filled = SLOT_ORDER.filter((id) => state.slots[id].filled)
  return Boolean(
    state.slots.active_cast.filled &&
      state.slots.pressure.filled &&
      state.slots.first_scene_hook.filled &&
      filled.length >= 4,
  )
}

export function buildStoryGuideLedger(
  state: StoryGuideLoopState,
  lang: Lang = "en",
): StoryGuideInlineLedger {
  const labels = SLOT_LABELS[lang]
  const known = SLOT_ORDER
    .filter((id) => state.slots[id].filled)
    .map((id) => labels[id])
  const missing = SLOT_ORDER
    .filter((id) => !state.slots[id].filled)
    .map((id) => labels[id])
  const nextQuestion = nextQuestionFor(state.nextMissing, lang)
  return {
    knownLabel: lang === "zh" ? "已知" : "Known",
    stillNeedLabel: lang === "zh" ? "还需要" : "Still need",
    nextQuestionLabel: lang === "zh" ? "下一问" : "Next question",
    known: known.length > 0 ? known.join(" · ") : lang === "zh" ? "先等你的第一句" : "waiting for your first line",
    stillNeed: missing.length > 0 ? missing.slice(0, 3).join(" · ") : lang === "zh" ? "已足够整理 Brief" : "enough to shape the Brief",
    nextQuestion,
  }
}

export function advanceStoryGuideLoop(
  previousState: StoryGuideLoopState,
  rawText: string,
  lang: Lang = "en",
): StoryGuideLoopDecision {
  const text = rawText.trim()
  const settings = inferStoryGuideSettings(text, lang)
  if (!text) {
    const state = {
      ...syncLabels(previousState, lang),
      status: "needs_field" as const,
      lastNode: "ask_missing_slot" as const,
    }
    return {
      state,
      node: "ask_missing_slot",
      status: "needs_field",
      reply: nextQuestionFor(state.nextMissing, lang),
      acceptedText: false,
      blocked: false,
      canShapeBrief: canShapeStoryBrief(state),
      settings,
      ledger: buildStoryGuideLedger(state, lang),
    }
  }

  const unsafe = UNSAFE_PATTERNS.some((pattern) => pattern.test(text))
  if (unsafe) {
    const state: StoryGuideLoopState = {
      ...syncLabels(previousState, lang),
      status: "redirect",
      lastNode: "redirect_out_of_spec",
      blockedTurns: [...previousState.blockedTurns, text],
    }
    return {
      state,
      node: "redirect_out_of_spec",
      status: "redirect",
      reply:
        lang === "zh"
          ? "这个 beta 不会围绕毒品使用或成瘾来搭故事。我们可以把它改成公开压力、被误读的证据、或一个必须当场决定的物件。"
          : "I can’t build this beta around drug use or addiction. We can redirect it into public pressure, misunderstood evidence, or a contested decision in the room.",
      acceptedText: false,
      blocked: true,
      canShapeBrief: false,
      settings,
    }
  }

  if (settings.privacyIntent && isPrivacyOnlyRequest(text)) {
    const state = {
      ...syncLabels(previousState, lang),
      status: canShapeStoryBrief(previousState) ? "ready_to_brief" as const : "needs_field" as const,
      lastNode: canShapeStoryBrief(previousState) ? "ready_to_shape" as const : "ask_missing_slot" as const,
    }
    return {
      state,
      node: state.lastNode,
      status: state.status,
      reply:
        lang === "zh"
          ? "发布范围我不会从聊天里偷偷改。你现在还是按上面的「谁能玩」设置来保存；要公开，点那一行改成「广场公开」。"
          : "I will not silently change publishing from chat. This story still uses the explicit “Who can play this” row above the composer; switch that row to Public if you want everyone to play it.",
      acceptedText: false,
      blocked: false,
      canShapeBrief: canShapeStoryBrief(state),
      settings,
      ledger: buildStoryGuideLedger(state, lang),
    }
  }

  if (isTinyNonStoryInput(text) && previousState.acceptedTurns.length === 0) {
    const state = {
      ...syncLabels(previousState, lang),
      status: "needs_field" as const,
      lastNode: "ask_missing_slot" as const,
      nextMissing: "pressure" as const,
    }
    return {
      state,
      node: "ask_missing_slot",
      status: "needs_field",
      reply: tinySeedReply(lang),
      acceptedText: false,
      blocked: false,
      canShapeBrief: canShapeStoryBrief(state),
      settings,
      ledger: buildStoryGuideLedger(state, lang),
    }
  }

  if (isAmbiguousWhoQuestion(text)) {
    const state = {
      ...syncLabels(previousState, lang),
      status: "needs_field" as const,
      lastNode: "ask_missing_slot" as const,
    }
    return {
      state,
      node: "ask_missing_slot",
      status: "needs_field",
      reply: whoClarificationReply(lang),
      acceptedText: false,
      blocked: false,
      canShapeBrief: canShapeStoryBrief(state),
      settings,
      ledger: buildStoryGuideLedger(state, lang),
    }
  }

  const conflict = detectsHardConflict(text)
  if (conflict) {
    const state: StoryGuideLoopState = {
      ...syncLabels(previousState, lang),
      status: "clarify_conflict",
      lastNode: "clarify_conflict",
    }
    return {
      state,
      node: "clarify_conflict",
      status: "clarify_conflict",
      reply:
        lang === "zh"
          ? "我看到你同时要求回避这类动作、又让它成为主要推进。先选一个方向：要不要把冲突改成公开选择或误会证据？"
          : "I’m seeing a conflict: the note forbids a kind of action while also making it drive the scene. Should we convert that pressure into a public choice or misunderstood evidence instead?",
      acceptedText: false,
      blocked: false,
      canShapeBrief: canShapeStoryBrief(state),
      settings,
      ledger: buildStoryGuideLedger(state, lang),
    }
  }

  if (detectsUnsupportedSmallCastDirection(text)) {
    const updated = mergeSlots(previousState, extractSlots(text, lang), lang)
    const slots = {
      ...updated.slots,
      active_cast: {
        ...updated.slots.active_cast,
        filled: false,
        evidence: "",
      },
      pressure: {
        ...updated.slots.pressure,
        filled: false,
        evidence: "",
      },
    }
    const state: StoryGuideLoopState = {
      ...updated,
      acceptedTurns: [...previousState.acceptedTurns, text],
      slots,
      status: "needs_field",
      lastNode: "ask_missing_slot",
      nextMissing: "active_cast",
    }
    return {
      state,
      node: "ask_missing_slot",
      status: "needs_field",
      reply:
        lang === "zh"
          ? "我看到的是两人、低冲突、物件线索。这个 beta 需要至少第三方在场压力或公开后果，才能变成可玩的 Story Brief。加一个旁观者、阵营或必须当场选择的压力。"
          : "I’m reading this as two people, low conflict, and an object-only thread. This beta needs a third active pressure or public consequence before I shape a Story Brief. Add one watcher, faction, or decision that must be handled in the room.",
      acceptedText: true,
      blocked: false,
      canShapeBrief: false,
      settings,
      ledger: buildStoryGuideLedger(state, lang),
    }
  }

  const selfRoleAnswer = isSelfRoleAnswer(text) && previousState.nextMissing === "player_role" && previousState.acceptedTurns.length > 0
  const extracted = extractSlots(text, lang)
  if (selfRoleAnswer) {
    extracted.player_role = lang === "zh" ? "玩家自己" : "player as themselves"
  }
  const updated = mergeSlots(previousState, extracted, lang)
  const nextMissing = findNextMissing(updated)
  const ready = canShapeStoryBrief({ ...updated, nextMissing })
  const state: StoryGuideLoopState = {
    ...updated,
    acceptedTurns: [...previousState.acceptedTurns, text],
    status: ready ? "ready_to_brief" : "needs_field",
    lastNode: ready ? "ready_to_shape" : "ask_missing_slot",
    nextMissing,
  }

  return {
    state,
    node: state.lastNode,
    status: state.status,
    reply: ready ? readyReply(lang) : selfRoleAnswer ? selfRoleReply(state.nextMissing, lang) : missingReply(state.nextMissing, lang, state),
    acceptedText: true,
    blocked: false,
    canShapeBrief: ready,
    settings,
    ledger: buildStoryGuideLedger(state, lang),
  }
}

export function markStoryGuideAnalyzing(state: StoryGuideLoopState, lang: Lang = "en"): StoryGuideLoopState {
  return {
    ...syncLabels(state, lang),
    status: "analyzing",
    lastNode: "shape_story_brief",
  }
}

export function markStoryGuideBriefResult(
  state: StoryGuideLoopState,
  canGenerate: boolean,
  lang: Lang = "en",
): StoryGuideLoopState {
  return {
    ...syncLabels(state, lang),
    status: canGenerate ? "brief_ready" : "brief_not_fit",
    lastNode: canGenerate ? "brief_ready" : "brief_not_fit",
  }
}

function syncLabels(state: StoryGuideLoopState, lang: Lang): StoryGuideLoopState {
  const labels = SLOT_LABELS[lang]
  return {
    ...state,
    slots: SLOT_ORDER.reduce((acc, id) => {
      acc[id] = { ...state.slots[id], label: labels[id] }
      return acc
    }, {} as Record<StoryGuideSlotId, StoryGuideSlot>),
  }
}

function mergeSlots(
  previousState: StoryGuideLoopState,
  extracted: Partial<Record<StoryGuideSlotId, string>>,
  lang: Lang,
): StoryGuideLoopState {
  const synced = syncLabels(previousState, lang)
  const nextSlots = { ...synced.slots }
  for (const id of SLOT_ORDER) {
    const evidence = extracted[id]
    if (!evidence) continue
    nextSlots[id] = {
      ...nextSlots[id],
      filled: true,
      evidence,
    }
  }
  return {
    ...synced,
    status: "collecting",
    lastNode: "update_slots",
    slots: nextSlots,
  }
}

function extractSlots(text: string, lang: Lang): Partial<Record<StoryGuideSlotId, string>> {
  const lower = text.toLowerCase()
  const slots: Partial<Record<StoryGuideSlotId, string>> = {}
  if (/\b(i am|i'm|my role|i play|as the|as a|player is|protagonist is)\b/i.test(text) || /我(是|扮演)|玩家|主角/.test(text)) {
    slots.player_role = shortEvidence(text)
  }
  const participants = findTerms(text, PARTICIPANT_TERMS)
  if (participants.length >= 2 || /\b(with|between|against|and|versus|vs\.?)\b/i.test(text) || /和|与|对上|之间/.test(text)) {
    slots.active_cast = participants.length > 0 ? participants.slice(0, 5).join(" / ") : shortEvidence(text)
  }
  const pressure = findTerms(text, PRESSURE_TERMS)
  if (pressure.length > 0 || /\bmust decide\b|\bgoes wrong\b|\babout to\b|\bfalls apart\b/i.test(text) || /必须|快要|失控|当众|逼近/.test(text)) {
    slots.pressure = pressure.length > 0 ? pressure.slice(0, 4).join(" / ") : shortEvidence(text)
  }
  const tone = findTerms(text, TONE_TERMS)
  if (tone.length > 0) {
    slots.tone = tone.slice(0, 3).join(" / ")
  } else if (lang === "en" && /\bgala|board|merger|inheritance|secret\b/i.test(text)) {
    slots.tone = "high drama"
  }
  if (BOUNDARY_TERMS.some((term) => lower.includes(term.toLowerCase()))) {
    slots.boundaries = shortEvidence(text)
  }
  if (HOOK_TERMS.some((term) => lower.includes(term.toLowerCase())) || text.length >= 72) {
    slots.first_scene_hook = shortEvidence(text)
  }
  return slots
}

function findTerms(text: string, terms: string[]): string[] {
  const lower = text.toLowerCase()
  const found: string[] = []
  for (const term of terms) {
    if (lower.includes(term.toLowerCase()) && !found.includes(term)) {
      found.push(term)
    }
  }
  return found
}

function shortEvidence(text: string): string {
  const firstLine = text.replace(/\s+/g, " ").trim()
  return firstLine.length > 86 ? `${firstLine.slice(0, 83).trim()}...` : firstLine
}

function findNextMissing(state: StoryGuideLoopState): StoryGuideSlotId | null {
  const priority: StoryGuideSlotId[] = [
    "player_role",
    "active_cast",
    "pressure",
    "first_scene_hook",
    "tone",
    "boundaries",
  ]
  return priority.find((id) => !state.slots[id].filled) ?? null
}

function nextQuestionFor(slot: StoryGuideSlotId | null, lang: Lang): string {
  if (!slot) {
    return lang === "zh"
      ? "信息够了。要我整理最终 Story Brief 吗？"
      : "That is enough to shape the final Story Brief."
  }
  const zh: Record<StoryGuideSlotId, string> = {
    player_role: "你希望玩家在这一幕里是谁？给我一句身份就够了。",
    active_cast: "谁必须在场？至少给我两三个角色、阵营或旁观压力。",
    pressure: "这一幕的争议物、决定或公开压力是什么？",
    tone: "你想要高戏剧、喜剧、轻悬疑、奇幻/科幻，还是温和社交？",
    boundaries: "有什么一定不要发生的事？例如不要背叛、不要暴力升级。",
    first_scene_hook: "第一幕从哪里开始？给我一个地点、时刻或马上要发生的动作。",
  }
  const en: Record<StoryGuideSlotId, string> = {
    player_role: "Who is the player in this scene? One role line is enough.",
    active_cast: "Who has to be in the room? Give me two or three people, factions, or watching pressures.",
    pressure: "What is the contested object, decision, or public pressure?",
    tone: "Should this play as high drama, comedy, cozy mystery, fantasy/sci-fi, or social pressure?",
    boundaries: "What must not happen? For example: no betrayal, no violence, no public humiliation.",
    first_scene_hook: "Where does the first scene begin? Give me a location, moment, or action about to happen.",
  }
  return (lang === "zh" ? zh : en)[slot]
}

function missingReply(
  slot: StoryGuideSlotId | null,
  lang: Lang,
  state?: StoryGuideLoopState,
): string {
  if (!slot) return readyReply(lang)
  const context = guideStateContext(state)
  const zh: Record<StoryGuideSlotId, string> = {
    player_role: "已经有开端了。玩家在第一幕里是谁？",
    active_cast: "把房间补齐。谁必须在场？两个名字、身份或阵营就够。",
    pressure: "先给我第一道压力：指控、失踪、决定，还是被曝光的秘密？",
    tone: "这版要偏高戏剧、喜剧、悬疑、科幻奇幻，还是关系压力？",
    boundaries: "这版需要避开什么？给我一条边界就够。",
    first_scene_hook: "第一幕从哪里开？给我一个地点、时刻或即将发生的动作。",
  }
  const en: Record<StoryGuideSlotId, string> = {
    player_role: "Good, we have the trouble. Who are you when it starts?",
    active_cast: "Who must be in the room? Two names, roles, or factions are enough.",
    pressure: "What public pressure hits first: an accusation, disappearance, decision, or exposed secret?",
    tone: "Should this cut as high drama, comedy, mystery, speculative pressure, or social rupture?",
    boundaries: "What should this version avoid? One boundary is enough.",
    first_scene_hook: "Where does the first scene open before the room turns?",
  }
  if (lang === "en" && slot === "player_role" && context.includes("gala")) {
    return "A gala with the floor about to crack. Who is closest to the trouble when it starts?"
  }
  if (lang === "en" && slot === "player_role" && (context.includes("livestream") || context.includes("stage") || context.includes("awards"))) {
    return "That has a stage and public pressure. Who is closest to the trouble when it starts?"
  }
  return (lang === "zh" ? zh : en)[slot]
}

function guideStateContext(state?: StoryGuideLoopState): string {
  if (!state) return ""
  return Object.values(state.slots)
    .map((slot) => slot.evidence.toLowerCase())
    .filter(Boolean)
    .join(" ")
}

function tinySeedReply(lang: Lang): string {
  return lang === "zh"
    ? "你已经到写作桌前了。给我一个开场画面：麻烦第一次出现时，我们在哪里？"
    : "You are at the writing desk. Give me one scene to open on: where are we when trouble first appears?"
}

function whoClarificationReply(lang: Lang): string {
  return lang === "zh"
    ? "如果你是在问阵容，给我两个必须在场的人或阵营。第一幕里谁不能缺席？"
    : "If you mean cast, give me two people or factions who must be present. Who cannot be missing from the first scene?"
}

function selfRoleReply(slot: StoryGuideSlotId | null, lang: Lang): string {
  if (lang === "zh") {
    if (slot === "active_cast") return "记下：玩家就是你。第一幕里谁还必须在场？"
    if (slot === "pressure") return "记下：玩家就是你。这个房间里第一道压力是什么？"
    return `记下：玩家就是你。${nextQuestionFor(slot, lang)}`
  }
  if (slot === "active_cast") return "Noted: you are the player in the scene. Who else must be in the room?"
  if (slot === "pressure") return "Noted: you are the player in the scene. What pressure hits you first in that room?"
  return `Noted: you are the player in the scene. ${nextQuestionFor(slot, lang)}`
}

function readyReply(lang: Lang): string {
  return lang === "zh"
    ? "方向已经够清楚了。我可以把它整理成最终 Story Brief；你也可以继续补一句规则或纠正。"
    : "The direction is clear enough. I can shape the final Story Brief now, or you can add one more rule or correction."
}

function isTinyNonStoryInput(text: string): boolean {
  return TINY_GREETING_PATTERN.test(text.trim())
}

function isAmbiguousWhoQuestion(text: string): boolean {
  return AMBIGUOUS_WHO_PATTERN.test(text.trim())
}

function isSelfRoleAnswer(text: string): boolean {
  return SELF_ROLE_PATTERN.test(text.trim())
}

function detectsHardConflict(text: string): boolean {
  const lower = text.toLowerCase()
  const forbidsViolence = /\b(no|without|avoid|never)\s+(violence|fight|fighting|killing|murder)\b/i.test(text) || /不要.*(暴力|打斗|杀)|避免.*(暴力|打斗|杀)/.test(text)
  const drivesViolence = /\bmust\s+(fight|kill|murder)\b|\bmain\s+(fight|murder)\b/i.test(text) || /必须.*(打|杀)|主要.*(打斗|杀人)/.test(text)
  return Boolean(forbidsViolence && drivesViolence && lower.length > 0)
}

function detectsUnsupportedSmallCastDirection(text: string): boolean {
  const lower = text.toLowerCase()
  const explicitSmallCast =
    /\b(two-person|two person|two people|two characters|only two|just two)\b/i.test(text) ||
    /\bone\s+[a-z-]+\s+and\s+one\s+[a-z-]+/.test(lower)
  const lowConflict =
    /\b(no public pressure|no mystery|no conflict|no villains?|low conflict|without conflict)\b/i.test(text) ||
    /没有公开压力|没有冲突|不要冲突|低冲突/.test(text)
  const objectOnly =
    /\b(wedding ring|ring on a table|lost ring)\b/i.test(text) ||
    /婚戒|戒指/.test(text)
  return Boolean(explicitSmallCast && lowConflict && objectOnly)
}
