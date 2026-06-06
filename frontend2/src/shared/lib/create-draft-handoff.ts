import type {
  NarrativeTemplateLanguage,
  NarrativeTensionProfile,
} from "../../api/contracts"

export const CREATE_DRAFT_HANDOFF_KEY = "tiny-stories.createDraft.v1"

export type CreateDraftHandoff = {
  seed: string
  language?: NarrativeTemplateLanguage
  tensionProfile?: NarrativeTensionProfile
  source?: "plaza_curated"
}

export function saveCreateDraftHandoff(payload: CreateDraftHandoff): void {
  if (typeof window === "undefined") return
  window.sessionStorage.setItem(CREATE_DRAFT_HANDOFF_KEY, JSON.stringify(payload))
}

export function takeCreateDraftHandoff(): CreateDraftHandoff | null {
  if (typeof window === "undefined") return null
  const raw = window.sessionStorage.getItem(CREATE_DRAFT_HANDOFF_KEY)
  if (!raw) return null
  window.sessionStorage.removeItem(CREATE_DRAFT_HANDOFF_KEY)
  try {
    const parsed = JSON.parse(raw) as Partial<CreateDraftHandoff>
    if (typeof parsed.seed !== "string" || !parsed.seed.trim()) return null
    return {
      seed: parsed.seed,
      language: parsed.language,
      tensionProfile: parsed.tensionProfile,
      source: parsed.source,
    }
  } catch {
    return null
  }
}
