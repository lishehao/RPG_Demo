import type { PlaySuggestedAction, StoryLanguage } from "../../../index"
import { uiText } from "../../../shared/lib/ui-language"
import { StudioIcon } from "../../../shared/ui/studio-icon"

export function SuggestedActions({
  actions,
  selectedSuggestionId,
  onSelect,
  uiLanguage = "en",
  variant = "stack",
}: {
  actions: PlaySuggestedAction[]
  selectedSuggestionId: string | null
  onSelect: (action: PlaySuggestedAction) => void
  uiLanguage?: StoryLanguage
  variant?: "stack" | "tray"
}) {
  if (actions.length === 0) {
    return (
      <p className="editorial-support">
        {uiText(uiLanguage, {
          en: "No more prompts because this session has reached an ending.",
          zh: "这次会话已经进入结局，因此不会再给出新的建议行动。",
        })}
      </p>
    )
  }

  return (
    <div className={`play-suggestion-list ${variant === "tray" ? "play-suggestion-list--tray" : ""}`}>
      {actions.map((action) => (
        <button
          className={`play-suggestion ${selectedSuggestionId === action.suggestion_id ? "is-selected" : ""}`}
          key={action.suggestion_id}
          onClick={() => onSelect(action)}
          type="button"
        >
          <StudioIcon name="arrow_forward" />
          <div className="play-suggestion__copy">
            <span className="play-suggestion__label">{action.label}</span>
            <strong>{action.prompt}</strong>
          </div>
        </button>
      ))}
    </div>
  )
}
