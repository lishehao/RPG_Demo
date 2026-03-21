import type { PublishedStoryCard } from "../../../index"
import { formatPublishedAt } from "../../../shared/lib/formatting"

export function StoryLibraryCard({
  story,
  selected,
  onSelect,
}: {
  story: PublishedStoryCard
  selected: boolean
  onSelect: () => void
}) {
  const ownershipLabel = story.viewer_can_manage
    ? story.visibility === "private"
      ? "My Private Story"
      : "My Public Story"
    : "Public Story"

  return (
    <button className={`story-card ${selected ? "is-selected" : ""}`} onClick={onSelect} type="button">
      <div className="story-card-header">
        <h4>{story.title}</h4>
        <span>{formatPublishedAt(story.published_at)}</span>
      </div>
      <div className="story-card__ownership">
        <span className={`story-card__ownership-badge ${story.viewer_can_manage ? "is-owned" : "is-public"}`}>{ownershipLabel}</span>
      </div>
      <p>{story.one_liner}</p>
      <div className="chip-row">
        <span className="chip">{story.theme}</span>
        <span className="chip">{story.tone}</span>
        <span className="chip">
          {story.npc_count} NPCs / {story.beat_count} beats
        </span>
      </div>
    </button>
  )
}
