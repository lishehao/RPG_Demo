import type { PlayStateBar, StoryLanguage } from "../../../index"
import { progressWidth } from "../../../shared/lib/formatting"
import { formatPlayStateBarLabel } from "../../../shared/lib/play-formatting"

export function StateBarList({ bars, language = "en" }: { bars: PlayStateBar[]; language?: StoryLanguage }) {
  return (
    <div className="play-state-list">
      {bars.map((bar) => (
        <div className="play-state-row" key={bar.bar_id}>
          <div className="play-state-row__header">
            <strong>{formatPlayStateBarLabel(bar, language)}</strong>
            <span>
              {bar.current_value} / {bar.max_value}
            </span>
          </div>
          <div className="play-state-row__track">
            <div className="play-state-row__fill" style={{ width: progressWidth(bar.current_value, bar.min_value, bar.max_value) }} />
          </div>
        </div>
      ))}
    </div>
  )
}
