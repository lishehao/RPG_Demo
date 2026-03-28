import type { StoryLanguage } from "../../index"
import { normalizeUiLanguage } from "./ui-language"

const MILESTONE_KIND_LABELS: Record<string, { en: string; zh: string }> = {
  reveal: { en: "Reveal", zh: "揭开" },
  exposure: { en: "Exposure", zh: "曝光" },
  fracture: { en: "Fracture", zh: "失控" },
  concession: { en: "Concession", zh: "让步" },
  containment: { en: "Containment", zh: "稳住局面" },
  commitment: { en: "Commitment", zh: "定案" },
}

const THEME_LABELS: Record<string, { en: string; zh: string }> = {
  legitimacy_crisis: { en: "Legitimacy crisis", zh: "合法性危机" },
  logistics_quarantine_crisis: { en: "Logistics quarantine crisis", zh: "物流与隔离危机" },
  truth_record_crisis: { en: "Truth and record crisis", zh: "真相与记录危机" },
  public_order_crisis: { en: "Public order crisis", zh: "公共秩序危机" },
  generic_civic_crisis: { en: "Civic crisis", zh: "城市危机" },
}

const TOPOLOGY_LABELS: Record<string, { en: string; zh: string }> = {
  three_slot: { en: "3-slot pressure triangle", zh: "三角压力结构" },
  four_slot: { en: "4-slot civic web", zh: "四节点公共网络" },
}

const RUNTIME_PROFILE_LABELS: Record<string, { en: string; zh: string }> = {
  warning_record_play: { en: "Warning Record Play", zh: "预警取证" },
  archive_vote_play: { en: "Archive Vote Play", zh: "档案表决" },
  bridge_ration_play: { en: "Bridge Ration Play", zh: "桥线配给" },
  harbor_quarantine_play: { en: "Harbor Quarantine Play", zh: "港口检疫" },
  blackout_council_play: { en: "Blackout Council Play", zh: "停电议会" },
  legitimacy_compact_play: { en: "Legitimacy Compact Play", zh: "合法性博弈" },
  public_order_play: { en: "Public Order Play", zh: "公共秩序" },
  generic_civic_play: { en: "Civic Crisis Play", zh: "城市危机" },
}

const PRESENTATION_STATUS_LABELS: Record<string, { en: string; zh: string }> = {
  open_for_play: { en: "Open for play", zh: "可以试玩" },
}

const AFFORDANCE_LABELS: Record<string, { en: string; zh: string }> = {
  reveal_truth: { en: "Reveal truth", zh: "揭开真相" },
  contain_chaos: { en: "Contain chaos", zh: "稳住局面" },
  build_trust: { en: "Build trust", zh: "建立信任" },
  shift_public_narrative: { en: "Shift public narrative", zh: "扭转舆论" },
  protect_civilians: { en: "Protect civilians", zh: "保护平民" },
  secure_resources: { en: "Secure resources", zh: "稳住资源" },
  unlock_ally: { en: "Unlock ally", zh: "争取盟友" },
  pay_cost: { en: "Pay the cost", zh: "承担代价" },
}

function titleCase(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function resolveTopologyKey(value: string) {
  const normalized = value.trim().toLowerCase()
  if (["three_slot", "3-slot pressure triangle", "三角压力结构"].includes(normalized)) {
    return "three_slot"
  }
  if (["four_slot", "4-slot civic web", "四节点公共网络"].includes(normalized)) {
    return "four_slot"
  }
  return null
}

function resolveThemeKey(value: string) {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/-/g, " ")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")

  if (["legitimacy crisis", "合法性危机"].includes(normalized)) {
    return "legitimacy_crisis"
  }
  if (["logistics quarantine crisis", "logistics and quarantine crisis", "物流与隔离危机"].includes(normalized)) {
    return "logistics_quarantine_crisis"
  }
  if (["truth and record crisis", "真相与记录危机"].includes(normalized)) {
    return "truth_record_crisis"
  }
  if (["public order crisis", "公共秩序危机"].includes(normalized)) {
    return "public_order_crisis"
  }
  if (["civic crisis", "generic civic crisis", "城市危机"].includes(normalized)) {
    return "generic_civic_crisis"
  }
  return null
}

export function formatMilestoneKind(value: string, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  return MILESTONE_KIND_LABELS[value]?.[language] ?? titleCase(value)
}

export function formatThemeLabel(value: string, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  const themeKey = resolveThemeKey(value)
  if (themeKey) {
    return THEME_LABELS[themeKey][language]
  }
  if (language === "zh" && !/[\u3400-\u9fff]/.test(value)) {
    return "故事主题"
  }
  return value
}

export function formatTopologyLabel(value: string, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  const topologyKey = resolveTopologyKey(value)
  return topologyKey ? TOPOLOGY_LABELS[topologyKey][language] : value
}

export function formatRuntimeProfileLabel(value: string, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  return RUNTIME_PROFILE_LABELS[value]?.[language] ?? titleCase(value)
}

export function formatPresentationStatusLabel(value: string, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  return PRESENTATION_STATUS_LABELS[value]?.[language] ?? titleCase(value)
}

export function formatAffordanceTag(value: string, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  return AFFORDANCE_LABELS[value]?.[language] ?? titleCase(value)
}
