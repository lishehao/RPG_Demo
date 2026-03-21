import type { PlayEnding } from "../../../index"

export function EndingSummary({ ending }: { ending: PlayEnding }) {
  return (
    <div className="play-ending-card">
      <p className="editorial-metadata-label">Ending</p>
      <h4>{ending.label}</h4>
      <p>{ending.summary}</p>
    </div>
  )
}
