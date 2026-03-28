import type { StoryLanguage } from "../../index"
import { getStudioBrandName } from "../../shared/lib/studio-brand"
import { uiText } from "../../shared/lib/ui-language"

export function StudioFooter({
  uiLanguage = "en",
  hidden = false,
}: {
  uiLanguage?: StoryLanguage
  hidden?: boolean
}) {
  if (hidden) {
    return null
  }

  const studioBrandName = getStudioBrandName(uiLanguage)

  return (
    <footer className="studio-footer">
      <div className="studio-footer-line" />
      <p className="studio-footer-copy">
        {uiText(uiLanguage, {
          en: "Narrative Studio keeps creation, library review, and play in one continuous story workflow.",
          zh: "叙事会馆把创作、找故事和试玩放在同一条线上。",
        })}
      </p>
      <p className="studio-footer-copy studio-footer-copy--meta">
        {uiText(
          uiLanguage,
          {
            en: `© 2026 ${studioBrandName}. `,
            zh: `© 2026 ${studioBrandName}。`,
          },
        )}
        <span>{uiText(uiLanguage, { en: "Story-first, ready to play.", zh: "以故事为先，准备好就能试玩。" })}</span>
      </p>
    </footer>
  )
}
