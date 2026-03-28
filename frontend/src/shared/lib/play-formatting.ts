import type { PlayStateBar, StoryLanguage } from "../../index"
import { normalizeUiLanguage } from "./ui-language"

const PLAY_LEDGER_LABELS: Record<string, { en: string; zh: string }> = {
  inventory: { en: "Inventory", zh: "物品栏" },
  map: { en: "Map", zh: "地图" },
  proof_progress: { en: "Proof progress", zh: "证据推进" },
  coalition_progress: { en: "Coalition progress", zh: "联盟推进" },
  order_progress: { en: "Order progress", zh: "秩序推进" },
  settlement_progress: { en: "Settlement progress", zh: "结算推进" },
  public_cost: { en: "Public cost", zh: "公众代价" },
  relationship_cost: { en: "Relationship cost", zh: "关系代价" },
  procedural_cost: { en: "Procedural cost", zh: "程序代价" },
  coercion_cost: { en: "Coercion cost", zh: "强制代价" },
  external_pressure: { en: "External pressure", zh: "外部压力" },
  public_panic: { en: "Public panic", zh: "公众恐慌" },
  political_leverage: { en: "Political leverage", zh: "政治筹码" },
  resource_strain: { en: "Resource strain", zh: "资源紧张" },
  system_integrity: { en: "System integrity", zh: "制度完整性" },
  ally_trust: { en: "Ally trust", zh: "盟友信任" },
  exposure_risk: { en: "Exposure risk", zh: "曝光风险" },
  time_window: { en: "Time window", zh: "时间窗口" },
  truth_exposed: { en: "Truth exposed", zh: "真相曝光" },
  pressure_shifted: { en: "Pressure shifted", zh: "压力变化" },
}

const SURFACE_DISABLED_REASON_LABELS: Record<string, { en: string; zh: string }> = {
  "Inventory is not authored for this runtime yet.": {
    en: "Inventory is not authored for this runtime yet.",
    zh: "当前运行时还没有编排物品栏。",
  },
  "Map data is not available for this runtime yet.": {
    en: "Map data is not available for this runtime yet.",
    zh: "当前运行时还没有可用的地图数据。",
  },
}

function titleCase(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function containsChinese(value: string) {
  return /[\u3400-\u9fff]/.test(value)
}

function looksLikeProperName(value: string) {
  return /^[A-Z][A-Za-z.'-]*(?: [A-Z][A-Za-z.'-]*)+$/.test(value.trim())
}

export function formatPlayLedgerLabel(key: string, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  const mapped = PLAY_LEDGER_LABELS[key]?.[language]
  if (mapped) {
    return mapped
  }
  if (language === "zh") {
    if (containsChinese(key) || looksLikeProperName(key)) {
      return key
    }
    return "状态项"
  }
  return titleCase(key)
}

export function formatPlayStateBarLabel(bar: PlayStateBar, uiLanguage: StoryLanguage | string = "en") {
  const language = normalizeUiLanguage(uiLanguage)
  const mapped = PLAY_LEDGER_LABELS[bar.bar_id]?.[language]
  if (mapped) {
    return mapped
  }
  if (language === "zh") {
    if (/ stance$/i.test(bar.label)) {
      return bar.label.replace(/ stance$/i, " 立场")
    }
    if (containsChinese(bar.label) || looksLikeProperName(bar.label)) {
      return bar.label
    }
    return "状态指标"
  }
  return bar.label
}

export function formatSupportSurfaceDisabledReason(
  surfaceKey: "inventory" | "map",
  reason: string | null | undefined,
  uiLanguage: StoryLanguage | string = "en",
) {
  const language = normalizeUiLanguage(uiLanguage)
  if (!reason) {
    return language === "zh"
      ? `${formatPlayLedgerLabel(surfaceKey, language)}当前不可用。`
      : `${formatPlayLedgerLabel(surfaceKey, language)} is unavailable right now.`
  }

  const mapped = SURFACE_DISABLED_REASON_LABELS[reason]?.[language]
  if (mapped) {
    return mapped
  }

  if (language === "zh") {
    if (containsChinese(reason)) {
      return reason
    }
    return `${formatPlayLedgerLabel(surfaceKey, language)}当前不可用。`
  }

  return reason
}
