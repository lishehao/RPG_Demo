import type { PlayEnding, StoryLanguage } from "../../../index"
import { uiText } from "../../../shared/lib/ui-language"

type OutcomeStat = {
  label: string
  value: string
}

export function EndingSummary({
  ending,
  uiLanguage = "en",
  aftertaste,
  contextStats = [],
  ledgerStats = [],
}: {
  ending: PlayEnding
  uiLanguage?: StoryLanguage
  aftertaste?: string | null
  contextStats?: OutcomeStat[]
  ledgerStats?: OutcomeStat[]
}) {
  const outcomeLabel = uiText(uiLanguage, { en: "Outcome", zh: "结局" })

  return (
    <section className={`play-ending-card play-ending-card--hero is-${ending.ending_id}`}>
      <div className="play-ending-card__headline">
        <p className="editorial-kicker">{outcomeLabel}</p>
        <h2>{ending.label}</h2>
        <p className="play-ending-card__summary">{ending.summary}</p>
        {aftertaste ? <p className="play-ending-card__aftertaste">{aftertaste}</p> : null}
      </div>

      {contextStats.length > 0 ? (
        <div className="play-ending-card__context">
          {contextStats.map((item) => (
            <div className="play-ending-card__context-item" key={`${item.label}:${item.value}`}>
              <span className="editorial-metadata-label">{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      ) : null}

      {ledgerStats.length > 0 ? (
        <div className="play-ending-card__ledger">
          {ledgerStats.map((item) => (
            <div className="play-ending-card__ledger-item" key={`${item.label}:${item.value}`}>
              <span className="editorial-metadata-label">{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  )
}
