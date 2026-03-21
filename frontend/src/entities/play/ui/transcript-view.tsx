export function TranscriptView({
  entries,
  pendingPlayerText,
  submitting,
}: {
  entries: Array<{
    id: string
    speaker: "gm" | "player"
    text: string
  }>
  pendingPlayerText?: string | null
  submitting?: boolean
}) {
  return (
    <div className="play-transcript">
      {entries.map((entry, index) => (
        <article className={`play-transcript__entry speaker-${entry.speaker}`} key={entry.id}>
          <div className="play-transcript__marker">T{String(index + 1).padStart(2, "0")}</div>
          <div className="play-transcript__body">
            {entry.speaker === "player" ? <span className="play-transcript__speaker">Player</span> : null}
            <p>{entry.text}</p>
          </div>
        </article>
      ))}

      {pendingPlayerText ? (
        <article className="play-transcript__entry play-transcript__entry--pending speaker-player" key={`pending-player-${pendingPlayerText}`}>
          <div className="play-transcript__marker">T{String(entries.length + 1).padStart(2, "0")}</div>
          <div className="play-transcript__body">
            <span className="play-transcript__speaker">Player</span>
            <p>{pendingPlayerText}</p>
          </div>
        </article>
      ) : null}

      {submitting ? (
        <article className="play-transcript__entry play-transcript__entry--pending play-transcript__entry--resolving speaker-gm" key="pending-gm">
          <div className="play-transcript__marker">T{String(entries.length + (pendingPlayerText ? 2 : 1)).padStart(2, "0")}</div>
          <div className="play-transcript__body play-transcript__body--pending" aria-live="polite">
            <span className="play-transcript__speaker">Session Update</span>
            <div className="play-transcript__pending-copy">
              <strong>Resolving your move through the chamber.</strong>
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
