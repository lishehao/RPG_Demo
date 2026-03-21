import type { AuthorPreviewResponse, PublishedStoryCard } from "../../index"

export function buildDossierRef(story: PublishedStoryCard): string {
  return `Dossier N° ${story.story_id.slice(0, 3).toUpperCase()}`
}

export function buildClassificationLabel(preview: AuthorPreviewResponse): string {
  return preview.theme.primary_theme.replace(/_/g, " ")
}
