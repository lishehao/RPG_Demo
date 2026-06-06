import type {
  NarrativeLocalizedText,
  NarrativePublicReplayResponse,
  NarrativeSessionSummary,
  NarrativeTemplateSummary,
} from "../../api/contracts"
import type { Lang } from "./i18n"

function clean(value: string | null | undefined): string {
  return value?.trim() ?? ""
}

export function selectLocalizedText(
  metadata: NarrativeLocalizedText | null | undefined,
  lang: Lang,
  fallback: string | null | undefined,
): string {
  const localized = clean(metadata?.[lang])
  if (localized) return localized
  const primary = clean(fallback)
  if (primary) return primary
  return clean(lang === "zh" ? metadata?.en : metadata?.zh)
}

export function getTemplateDisplayTitle(template: NarrativeTemplateSummary, lang: Lang): string {
  return selectLocalizedText(template.title_i18n, lang, template.title)
}

export function getTemplateDisplaySummary(template: NarrativeTemplateSummary, lang: Lang): string {
  return selectLocalizedText(template.summary_i18n, lang, template.seed)
}

export function getSessionDisplayTitle(session: NarrativeSessionSummary, lang: Lang): string {
  return selectLocalizedText(session.template_title_i18n, lang, session.template_title)
}

export function getSessionDisplaySummary(session: NarrativeSessionSummary, lang: Lang): string {
  return selectLocalizedText(session.template_summary_i18n, lang, session.template_seed)
}

export function getReplayDisplayTitle(replay: NarrativePublicReplayResponse, lang: Lang): string {
  return selectLocalizedText(replay.template_title_i18n, lang, replay.template_title)
}

export function getReplayDisplaySummary(replay: NarrativePublicReplayResponse, lang: Lang): string {
  return selectLocalizedText(replay.template_summary_i18n, lang, replay.template_seed)
}
