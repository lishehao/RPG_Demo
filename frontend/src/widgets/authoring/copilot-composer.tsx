import type { StoryLanguage } from "../../index"
import { getAuthorUiCopy } from "../../shared/lib/author-ui-copy"

export function CopilotComposer({
  uiLanguage,
  messageDraft,
  activeSuggestionId,
  disabled,
  generatingProposal,
  suggestedInstructions,
  onMessageDraftChange,
  onUseSuggestion,
  onGenerateProposal,
}: {
  uiLanguage: StoryLanguage
  messageDraft: string
  activeSuggestionId: string | null
  disabled: boolean
  generatingProposal: boolean
  suggestedInstructions: Array<{ suggestion_id: string; label: string; instruction: string; rationale: string }>
  onMessageDraftChange: (value: string) => void
  onUseSuggestion: (suggestionId: string, instruction: string) => void
  onGenerateProposal: () => void
}) {
  const copy = getAuthorUiCopy(uiLanguage)
  const canGenerateProposal = Boolean(messageDraft.trim())

  return (
    <div className="copilot-composer">
      {suggestedInstructions.length > 0 ? (
        <div className="copilot-composer__suggestions">
          <span className="editorial-metadata-label">{copy.suggestedDirections}</span>
          <div className="author-copilot-suggestion-list">
            {suggestedInstructions.map((suggestion) => (
              <button
                aria-pressed={activeSuggestionId === suggestion.suggestion_id}
                className={`author-copilot-suggestion ${activeSuggestionId === suggestion.suggestion_id ? "is-active" : ""}`}
                key={suggestion.suggestion_id}
                onClick={() => onUseSuggestion(suggestion.suggestion_id, suggestion.instruction)}
                type="button"
              >
                <strong>{suggestion.label}</strong>
                <p>{suggestion.rationale}</p>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <label className="copilot-composer__field">
        <span className="editorial-metadata-label">{copy.instruction}</span>
        <textarea
          disabled={disabled}
          onChange={(event) => onMessageDraftChange(event.target.value)}
          placeholder={copy.instructionPlaceholder}
          rows={5}
          value={messageDraft}
        />
      </label>

      <div className="copilot-composer__actions">
        <button className="studio-button studio-button--primary" disabled={disabled || generatingProposal || !canGenerateProposal} onClick={onGenerateProposal} type="button">
          {generatingProposal ? copy.generatingSuggestion : copy.generateSuggestion}
        </button>
      </div>
    </div>
  )
}
