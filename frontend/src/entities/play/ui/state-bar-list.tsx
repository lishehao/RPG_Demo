import type { PlayStateBar } from "../../../index"
import { progressWidth } from "../../../shared/lib/formatting"

export function StateBarList({ bars }: { bars: PlayStateBar[] }) {
  return (
    <div className="play-state-list">
      {bars.map((bar) => (
        <div className="play-state-row" key={bar.bar_id}>
          <div className="play-state-row__header">
            <strong>{bar.label}</strong>
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
