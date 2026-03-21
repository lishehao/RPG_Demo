import type { PlaySuggestedAction } from "../../../index"

export function SuggestedActions({
  actions,
  selectedSuggestionId,
  onSelect,
}: {
  actions: PlaySuggestedAction[]
  selectedSuggestionId: string | null
  onSelect: (action: PlaySuggestedAction) => void
}) {
  if (actions.length === 0) {
    return <p className="editorial-support">No more prompts because this session has reached an ending.</p>
  }

  return (
    <div className="play-suggestion-list">
      {actions.map((action) => (
        <button
          className={`play-suggestion ${selectedSuggestionId === action.suggestion_id ? "is-selected" : ""}`}
          key={action.suggestion_id}
          onClick={() => onSelect(action)}
          type="button"
        >
          <span className="material-symbols-outlined">arrow_forward</span>
          <div>
            <strong>{action.label}</strong>
            <span>{action.prompt}</span>
          </div>
        </button>
      ))}
    </div>
  )
}
