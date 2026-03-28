import type { StoryLanguage } from "../../../index"
import { isMalformedStoryText, sanitizePlayTranscriptText } from "../../../shared/lib/story-content-quality"
import { normalizeUiLanguage } from "../../../shared/lib/ui-language"

export function TranscriptView({
  entries,
  storyLanguage = "en",
  uiLanguage = "en",
  pendingPlayerText,
  submitting,
}: {
  entries: Array<{
    id: string
    speaker: "gm" | "player"
    text: string
  }>
  storyLanguage?: StoryLanguage
  uiLanguage?: StoryLanguage
  pendingPlayerText?: string | null
  submitting?: boolean
}) {
  const localized = normalizeUiLanguage(uiLanguage) === "zh"
  const gmFallback = localized ? "这一回合的叙述仍在整理中。" : "Narration for this turn is still being normalized."
  return (
    <div className="play-transcript">
      {entries.map((entry, index) => {
        const sanitizedText = entry.speaker === "gm" ? sanitizePlayTranscriptText(entry.text, storyLanguage) : entry.text
        const displayText =
          entry.speaker === "gm" && isMalformedStoryText(sanitizedText, storyLanguage)
            ? gmFallback
            : sanitizedText
        return (
          <article className={`play-transcript__entry speaker-${entry.speaker}`} key={entry.id}>
            <div className="play-transcript__marker">T{String(index + 1).padStart(2, "0")}</div>
            <div className="play-transcript__body">
              {entry.speaker === "player" ? <span className="play-transcript__speaker">{localized ? "玩家" : "Player"}</span> : null}
              <p>{displayText}</p>
            </div>
          </article>
        )
      })}

      {pendingPlayerText ? (
        <article className="play-transcript__entry play-transcript__entry--pending speaker-player" key={`pending-player-${pendingPlayerText}`}>
          <div className="play-transcript__marker">T{String(entries.length + 1).padStart(2, "0")}</div>
          <div className="play-transcript__body">
            <span className="play-transcript__speaker">{localized ? "玩家" : "Player"}</span>
            <p>{pendingPlayerText}</p>
          </div>
        </article>
      ) : null}

      {submitting ? (
        <article className="play-transcript__entry play-transcript__entry--pending play-transcript__entry--resolving speaker-gm" key="pending-gm">
          <div className="play-transcript__marker">T{String(entries.length + (pendingPlayerText ? 2 : 1)).padStart(2, "0")}</div>
          <div className="play-transcript__body play-transcript__body--pending" aria-live="polite">
            <span className="play-transcript__speaker">{localized ? "系统推进" : "Session Update"}</span>
            <div className="play-transcript__pending-copy">
              <strong>{localized ? "正在解析你的这一步行动。" : "Resolving your move through the chamber."}</strong>
              <div className="play-transcript__pending-lines" aria-hidden="true">
                <span className="play-transcript__pending-line play-transcript__pending-line--lead" />
                <span className="play-transcript__pending-line play-transcript__pending-line--mid" />
                <span className="play-transcript__pending-line play-transcript__pending-line--tail" />
              </div>
            </div>
          </div>
        </article>
      ) : null}
    </div>
  )
}
