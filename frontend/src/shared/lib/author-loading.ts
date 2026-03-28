import type { AuthorLoadingCard, StoryLanguage } from "../../index"
import { normalizeUiLanguage } from "./ui-language"

const AUTHOR_STAGE_LABELS: Record<"en" | "zh", Record<string, string>> = {
  en: {
    queued: "Preparing the story build",
    running: "Starting the author pass",
    resume_from_preview_checkpoint: "Resuming from preview",
    generate_cast_members: "Drafting the cast",
    assemble_cast: "Assembling the cast",
    generate_beat_plan: "Mapping the major beats",
    build_design_bundle: "Building the story package",
    generate_route_opportunity_plan: "Planning live routes",
    compile_route_affordance_pack: "Compiling route rules",
    generate_ending_rules: "Preparing the endings",
    merge_rule_pack: "Merging the rule pack",
    repair_gameplay_semantics: "Finalizing play logic",
    failed: "Story generation failed",
  },
  zh: {
    queued: "正在准备故事生成",
    running: "正在启动创作流程",
    resume_from_preview_checkpoint: "正在接续预览草稿",
    generate_cast_members: "正在写出人物关系",
    assemble_cast: "正在整理人物名单",
    generate_beat_plan: "正在铺排主要节拍",
    build_design_bundle: "正在拼合故事包",
    generate_route_opportunity_plan: "正在规划可玩路线",
    compile_route_affordance_pack: "正在串联路线规则",
    generate_ending_rules: "正在准备结尾走向",
    merge_rule_pack: "正在合并路线与结局规则",
    repair_gameplay_semantics: "正在校正最终玩法逻辑",
    failed: "故事生成失败",
  },
}

const AUTHOR_STAGE_MESSAGES: Record<"en" | "zh", Record<string, string>> = {
  en: {
    queued: "Preparing the author flow and loading the first story materials.",
    running: "The author pass has started and the first story pieces are on the way.",
    resume_from_preview_checkpoint: "Loading the preview checkpoint before the full author pass continues.",
    generate_cast_members: "Drafting the cast and the tensions between them.",
    assemble_cast: "Assembling the cast into a usable story roster.",
    generate_beat_plan: "Mapping the major progression through the crisis.",
    build_design_bundle: "Building the story package from frame, cast, and beats.",
    generate_route_opportunity_plan: "Planning where live choices can open new routes.",
    compile_route_affordance_pack: "Connecting routes, affordances, and unlock rules.",
    generate_ending_rules: "Preparing how the story can close.",
    merge_rule_pack: "Merging route and ending rules into one playable pack.",
    repair_gameplay_semantics: "Finalizing play logic and edge-case consistency.",
    failed: "Something broke during authoring. Retry when you are ready.",
  },
  zh: {
    queued: "正在准备创作流程，并加载第一批故事材料。",
    running: "创作流程已经开始，第一批故事部件正在生成。",
    resume_from_preview_checkpoint: "正在接续预览草稿，把完整创作流程从上次的检查点继续往下跑。",
    generate_cast_members: "正在把关键人物和彼此间的张力写出来。",
    assemble_cast: "正在把人物整理成可直接进入故事的正式名单。",
    generate_beat_plan: "正在排出这篇故事的主要推进节拍。",
    build_design_bundle: "正在把框架、人物和节拍拼成完整故事包。",
    generate_route_opportunity_plan: "正在规划玩家推进时能打开哪些可玩路线。",
    compile_route_affordance_pack: "正在把路线、行动和解锁条件接起来。",
    generate_ending_rules: "正在准备这篇故事可能的收束方式。",
    merge_rule_pack: "正在把路线规则和结局规则并成一套可玩的规则包。",
    repair_gameplay_semantics: "正在做最后一轮玩法逻辑校正，补齐边角一致性。",
    failed: "创作过程中出了问题。准备好后可以再试一次。",
  },
}

const AUTHOR_LOADING_CARD_LABELS: Record<
  "en" | "zh",
  Partial<Record<AuthorLoadingCard["card_id"], string>>
> = {
  en: {
    theme: "Theme",
    structure: "Structure",
    working_title: "Working Title",
    tone: "Tone",
    story_premise: "Story Premise",
    story_stakes: "Core Stakes",
    cast_count: "Cast Count",
    cast_anchor: "Key Cast Anchor",
    beat_count: "Beat Count",
    opening_beat: "Opening Beat",
    final_beat: "Final Beat",
    generation_status: "Generation Status",
    token_budget: "Token Budget",
  },
  zh: {
    theme: "主题",
    structure: "结构",
    working_title: "暂定标题",
    tone: "语气",
    story_premise: "故事前提",
    story_stakes: "核心代价",
    cast_count: "人物数量",
    cast_anchor: "关键人物",
    beat_count: "节拍数量",
    opening_beat: "开场节拍",
    final_beat: "最终节拍",
    generation_status: "生成状态",
    token_budget: "内容预算",
  },
}

function normalizeStageKey(stage?: string | null) {
  return stage?.trim().toLowerCase().replace(/\s+/g, "_") ?? ""
}

function humanizeStageLabel(label?: string | null, uiLanguage: StoryLanguage | string = "en") {
  if (!label) {
    return normalizeUiLanguage(uiLanguage) === "zh" ? "正在准备故事生成" : "Preparing the story build"
  }
  return label
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function getAuthorStageLabel(stage?: string | null, label?: string | null, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  const normalizedStage = normalizeStageKey(stage)
  return AUTHOR_STAGE_LABELS[language][normalizedStage] ?? humanizeStageLabel(label, uiLanguage)
}

export function getAuthorStageMessage(stage?: string | null, label?: string | null, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  const normalizedStage = normalizeStageKey(stage)
  return AUTHOR_STAGE_MESSAGES[language][normalizedStage] ?? `${getAuthorStageLabel(stage, label, uiLanguage)}.`
}

export function getAuthorLoadingCardLabel(
  cardId: AuthorLoadingCard["card_id"],
  fallbackLabel: string,
  uiLanguage: StoryLanguage | string = "en",
) {
  const language = normalizeUiLanguage(uiLanguage)
  return AUTHOR_LOADING_CARD_LABELS[language][cardId] ?? fallbackLabel
}
