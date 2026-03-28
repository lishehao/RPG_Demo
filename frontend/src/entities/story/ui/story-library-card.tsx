import type { PublishedStoryCard, StoryLanguage } from "../../../index"
import { formatPublishedAt } from "../../../shared/lib/formatting"
import { normalizeStoryLanguage } from "../../../shared/lib/story-language"
import { formatThemeLabel } from "../../../shared/lib/story-taxonomy"
import { uiText } from "../../../shared/lib/ui-language"
import { pickHealthyLabel, pickHealthyText } from "../../../shared/lib/story-content-quality"

export function StoryLibraryCard({
  story,
  uiLanguage,
  onSelect,
  onPrefetch,
}: {
  story: PublishedStoryCard
  uiLanguage: StoryLanguage
  onSelect: () => void
  onPrefetch?: () => void
}) {
  const storyLanguage = normalizeStoryLanguage(story.language)
  const ownershipLabel = story.viewer_can_manage
    ? story.visibility === "private"
      ? uiText(uiLanguage, { en: "My Private Story", zh: "我的私有故事" })
      : uiText(uiLanguage, { en: "My Public Story", zh: "我的公开故事" })
    : uiText(uiLanguage, { en: "Public Story", zh: "公开故事" })
  const summary = pickHealthyText(storyLanguage, [story.one_liner, story.premise], uiText(uiLanguage, { en: "Story summary is still being normalized.", zh: "故事摘要仍在整理中。" }))
  const theme = formatThemeLabel(
    pickHealthyLabel(storyLanguage, [story.theme], uiText(uiLanguage, { en: "Theme still normalizing", zh: "故事主题整理中" })),
    uiLanguage,
  )
  const tone = pickHealthyLabel(storyLanguage, [story.tone], uiText(uiLanguage, { en: "Tone still normalizing", zh: "语气整理中" }))

  return (
    <button className="story-card" onClick={onSelect} onFocus={onPrefetch} onMouseEnter={onPrefetch} type="button">
      <div className="story-card-header">
        <h4>{story.title}</h4>
        <span>{formatPublishedAt(story.published_at, uiLanguage)}</span>
      </div>
      <div className="story-card__ownership">
        <span className={`story-card__ownership-badge ${story.viewer_can_manage ? "is-owned" : "is-public"}`}>{ownershipLabel}</span>
      </div>
      <p className="story-card__summary">{summary}</p>
      <div className="chip-row">
        <span className="chip story-card__chip story-card__chip--theme">{theme}</span>
        <span className="chip story-card__chip story-card__chip--tone">{tone}</span>
        <span className="chip story-card__chip story-card__chip--counts">
          {uiText(uiLanguage, {
            en: `${story.npc_count} NPCs / ${story.beat_count} beats`,
            zh: `${story.npc_count} 个 NPC / ${story.beat_count} 个节拍`,
          })}
        </span>
      </div>
    </button>
  )
}
