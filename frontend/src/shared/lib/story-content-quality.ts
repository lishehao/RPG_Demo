import type { AuthorPreviewResponse, StoryLanguage } from "../../index"
import { normalizeStoryLanguage } from "./story-language"

function containsCjk(text: string) {
  return /[\u3400-\u9fff]/.test(text)
}

function englishWordCount(text: string) {
  return (text.match(/[A-Za-z][A-Za-z'-]*/g) ?? []).length
}

function normalizedKey(text: string) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\u3400-\u9fff]+/g, " ")
    .trim()
}

function looksSerializedObject(text: string) {
  return /[{[]\s*['"][a-z_]+['"]\s*:/.test(text)
}

function looksTemplateGlue(text: string) {
  return /\bwhile\b/.test(text) || /\bkeep civic order\b/i.test(text)
}

const PLAY_RENDER_WRAPPER_PATTERNS = [
  /SCENE_REACTION\s*[:：]\s*/gi,
  /AXIS_PAYOFF\s*[:：]\s*/gi,
  /STANCE_PAYOFF\s*[:：]\s*/gi,
  /IMMEDIATE_CONSEQUENCE\s*[:：]\s*/gi,
  /CLOSING_PRESSURE\s*[:：]\s*/gi,
  /Requested output\s*[:：]\s*/gi,
  /Here is the JSON requested\s*[:：]\s*/gi,
]

const PLAY_META_LINE_PATTERNS = [
  /^requested output\b/i,
  /^here is the json requested\b/i,
  /^you keep the scene moving with\b/i,
]

function stripPlayRenderWrapper(text: string) {
  let cleaned = text
  for (const pattern of PLAY_RENDER_WRAPPER_PATTERNS) {
    cleaned = cleaned.replace(pattern, "\n")
  }
  return cleaned
    .replace(/\r/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

function splitNarrationChunks(text: string) {
  return text
    .split(/\n+/)
    .flatMap((line) => line.match(/[^。！？.!?\n]+[。！？.!?]?/g) ?? [])
    .map((chunk) => chunk.trim())
    .filter(Boolean)
}

function isPlayMetaChunk(text: string) {
  const normalized = text.trim()
  if (!normalized) {
    return true
  }
  if (/^[A-Z_]+\s*[:：]?$/.test(normalized)) {
    return true
  }
  return PLAY_META_LINE_PATTERNS.some((pattern) => pattern.test(normalized))
}

function cleanPlayNarrationChunks(chunks: string[], language?: StoryLanguage | string | null) {
  const resolvedLanguage = normalizeStoryLanguage(language)
  const hasAnyCjk = chunks.some((chunk) => containsCjk(chunk))

  return chunks.filter((chunk) => {
    if (isPlayMetaChunk(chunk)) {
      return false
    }
    if (looksSerializedObject(chunk)) {
      return false
    }
    if (resolvedLanguage === "zh" && hasAnyCjk && !containsCjk(chunk) && englishWordCount(chunk) >= 4) {
      return false
    }
    return true
  })
}

export function sanitizePlayTranscriptText(value: string | null | undefined, language?: StoryLanguage | string | null) {
  const rawText = stripPlayRenderWrapper(String(value ?? "").trim())
  const cleanedChunks = cleanPlayNarrationChunks(splitNarrationChunks(rawText), language)
  return cleanedChunks
    .join(" ")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([。！？.!?])/g, "$1")
    .trim()
}

export function isMalformedStoryText(value: string | null | undefined, language?: StoryLanguage | string | null) {
  const text = sanitizePlayTranscriptText(value, language)
  if (!text) {
    return true
  }
  const resolvedLanguage = normalizeStoryLanguage(language)
  if (looksSerializedObject(text)) {
    return true
  }
  if (resolvedLanguage === "zh") {
    if (/^in\s+\{/.test(text.toLowerCase())) {
      return true
    }
    if (!containsCjk(text) && englishWordCount(text) >= 5) {
      return true
    }
    if (containsCjk(text) && englishWordCount(text) >= 4) {
      return true
    }
    if (containsCjk(text) && looksTemplateGlue(text.toLowerCase())) {
      return true
    }
  }
  return false
}

export function isMalformedStoryLabel(value: string | null | undefined, language?: StoryLanguage | string | null) {
  const text = (value ?? "").trim()
  if (!text) {
    return true
  }
  if (looksSerializedObject(text)) {
    return true
  }
  const resolvedLanguage = normalizeStoryLanguage(language)
  if (resolvedLanguage === "zh" && containsCjk(text) && englishWordCount(text) >= 2) {
    return true
  }
  if (resolvedLanguage === "zh" && !containsCjk(text) && englishWordCount(text) >= 2) {
    return true
  }
  return false
}

export function pickHealthyText(
  language: StoryLanguage | string | null | undefined,
  candidates: Array<string | null | undefined>,
  fallback: string,
) {
  for (const candidate of candidates) {
    const text = (candidate ?? "").trim()
    if (!text) {
      continue
    }
    if (!isMalformedStoryText(text, language)) {
      return text
    }
  }
  return fallback
}

export function pickHealthyLabel(
  language: StoryLanguage | string | null | undefined,
  candidates: Array<string | null | undefined>,
  fallback: string,
) {
  for (const candidate of candidates) {
    const text = (candidate ?? "").trim()
    if (!text) {
      continue
    }
    if (!isMalformedStoryLabel(text, language)) {
      return text
    }
  }
  return fallback
}

export function isPreviewOutputHealthy(preview: AuthorPreviewResponse | null | undefined) {
  if (!preview) {
    return false
  }
  const language = normalizeStoryLanguage(preview.language)
  const themeValue = preview.flashcards.find((card) => card.card_id === "theme")?.value ?? ""
  return (
    !isMalformedStoryLabel(preview.story.title, language)
    && !isMalformedStoryText(preview.story.premise, language)
    && !isMalformedStoryLabel(preview.story.tone, language)
    && !isMalformedStoryLabel(themeValue, language)
  )
}

export function isDistinctSupportCopy(
  summary: string | null | undefined,
  primary: string | null | undefined,
  language?: StoryLanguage | string | null,
) {
  const summaryText = (summary ?? "").trim()
  const primaryText = (primary ?? "").trim()
  if (!summaryText || isMalformedStoryText(summaryText, language)) {
    return false
  }
  if (!primaryText) {
    return true
  }
  const summaryKey = normalizedKey(summaryText)
  const primaryKey = normalizedKey(primaryText)
  if (!summaryKey || !primaryKey) {
    return true
  }
  return !summaryKey.includes(primaryKey) && !primaryKey.includes(summaryKey)
}
