import type { AuthorLoadingCard } from "../../../index"

export function LoadingCardSpotlight({
  activeCard,
  cardPool,
}: {
  activeCard: AuthorLoadingCard | null
  cardPool: AuthorLoadingCard[]
}) {
  if (!activeCard) {
    return null
  }

  const activeIndex = Math.max(
    cardPool.findIndex((card) => card.card_id === activeCard.card_id),
    0,
  )

  return (
    <div aria-live="polite" className="loading-spotlight">
      <div className={`loading-spotlight-card emphasis-${activeCard.emphasis}`} key={`${activeCard.card_id}:${activeCard.value}`}>
        <span className="loading-spotlight-label">{activeCard.label}</span>
        <strong>{activeCard.value}</strong>
      </div>
      <div className="loading-spotlight-meta">
        <span>
          Card {activeIndex + 1} / {cardPool.length}
        </span>
      </div>
    </div>
  )
}
