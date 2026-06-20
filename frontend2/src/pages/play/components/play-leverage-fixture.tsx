import { useEffect, useMemo, useState } from "react"
import type { NarrativeStoryOption } from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"
import type { ActionCommitmentSummary, LeverageCardView } from "../play-types"
import { ActionArea } from "./play-flow-panels"

const LEVERAGE_OPTIONS: NarrativeStoryOption[] = [
  {
    label: "[Hold] Ask the producer to keep the rehearsal doors sealed.",
    hint: "Preserves the room while you decide whether to reveal proof.",
    handle: "seal-doors",
  },
  {
    label: "[Press] Make the sponsor explain the missing pass on the table.",
    hint: "Keeps pressure public without spending the leverage card.",
    handle: "sponsor-pass",
  },
]

const INITIAL_LEVERAGE_CARDS: LeverageCardView[] = [
  {
    card_id: "qa-leverage-badge",
    npc_id: "producer",
    target_name: "Producer Mara",
    leverage: "The empty green-room badge was scanned after Mara claimed the door stayed locked.",
    used: false,
  },
  {
    card_id: "qa-leverage-sponsor-call",
    npc_id: "sponsor",
    target_name: "Sponsor Vale",
    leverage: "The sponsor's call log shows three urgent calls to control before the singer vanished.",
    used: false,
  },
]

type LeverageOutcome = {
  title: string
  detail: string
}

function cloneLeverageCards(): LeverageCardView[] {
  return INITIAL_LEVERAGE_CARDS.map((card) => ({ ...card }))
}

function leverageOutcomeFor(card: LeverageCardView): LeverageOutcome {
  return {
    title: `${card.target_name} exposed`,
    detail: "The room has one shared fact now. Choose the next move from the pressure it creates.",
  }
}

export function PlayLeverageFixture({ onBackHome }: { onBackHome: () => void }) {
  const t = useT()
  const [turn, setTurn] = useState(0)
  const [busy, setBusy] = useState(false)
  const [showFreeInput, setShowFreeInput] = useState(false)
  const [freeInput, setFreeInput] = useState("")
  const [diary, setDiary] = useState("")
  const [showDiary, setShowDiary] = useState(false)
  const [status, setStatus] = useState("Leverage surface rehearsal.")
  const [commitmentSummary, setCommitmentSummary] = useState<ActionCommitmentSummary | null>(null)
  const [leverageCards, setLeverageCards] = useState<LeverageCardView[]>(cloneLeverageCards)
  const [playedCard, setPlayedCard] = useState<LeverageCardView | null>(null)
  const [outcome, setOutcome] = useState<LeverageOutcome | null>(null)
  const playableCount = useMemo(() => leverageCards.filter((card) => !card.used).length, [leverageCards])

  useEffect(() => {
    if (!busy || !playedCard) return
    const timer = window.setTimeout(() => {
      setBusy(false)
      setShowDiary(false)
      setDiary("")
      setShowFreeInput(false)
      setFreeInput("")
      setLeverageCards((cards) =>
        cards.map((card) => (card.card_id === playedCard.card_id ? { ...card, used: true } : card)),
      )
      setOutcome(leverageOutcomeFor(playedCard))
      setStatus("Leverage resolved.")
      setTurn((value) => value + 1)
    }, 720)
    return () => window.clearTimeout(timer)
  }, [busy, playedCard])

  const submitOption = (index: number) => {
    if (busy) return
    setOutcome({
      title: "Move held",
      detail: LEVERAGE_OPTIONS[index]?.hint ?? "The room is waiting for the next move.",
    })
    setStatus("Move held.")
  }

  const resolveLeverage = (card: LeverageCardView) => {
    if (busy) return
    setPlayedCard(card)
    setOutcome(null)
    setStatus(`Revealing leverage against ${card.target_name}.`)
    setBusy(true)
  }

  const resetCards = () => {
    if (busy) return
    setLeverageCards(cloneLeverageCards())
    setPlayedCard(null)
    setOutcome(null)
    setStatus("Leverage surface rehearsal.")
    setTurn((value) => value + 1)
  }

  return (
    <main
      style={{
        ...ppStyles.page,
        minHeight: "100vh",
        padding: "32px",
        gap: 18,
      }}
      data-play-leverage-fixture="true"
      data-play-leverage-fixture-state={busy ? "resolving" : outcome ? "resolved" : "ready"}
      data-play-leverage-fixture-playable-count={playableCount}
    >
      <button
        type="button"
        style={ppStyles.backBtn}
        onClick={onBackHome}
      >
        {t("action.back_home")}
      </button>
      <section
        style={{
          width: "min(100%, 880px)",
          display: "grid",
          gap: 12,
        }}
        aria-label="Leverage rehearsal"
      >
        <p
          style={{ margin: 0, color: "rgba(255,245,230,0.76)", lineHeight: 1.5 }}
          aria-live="polite"
        >
          {status}
        </p>
        {commitmentSummary ? (
          <p
            style={{ margin: 0, color: "rgba(246,221,176,0.74)", fontSize: 12.5, lineHeight: 1.45 }}
            data-play-leverage-fixture-commitment="true"
          >
            {commitmentSummary.kicker}: {commitmentSummary.title}
          </p>
        ) : null}
        {outcome ? (
          <section
            style={{
              ...ppStyles.outcomeReceipt,
              gap: 10,
            }}
            aria-label={`Leverage result: ${outcome.title}`}
            data-play-leverage-fixture-result="true"
          >
            <span style={ppStyles.outcomeReceiptKicker}>What changed</span>
            <strong style={{ color: "rgba(255,248,232,0.96)", fontSize: 16, lineHeight: 1.25 }}>
              {outcome.title}
            </strong>
            <span style={{ color: "rgba(246,239,222,0.74)", fontSize: 13, lineHeight: 1.45 }}>
              {outcome.detail}
            </span>
            <button
              type="button"
              style={ppStyles.commitTextButton}
              onClick={resetCards}
              disabled={busy}
            >
              Reset leverage cards
            </button>
          </section>
        ) : null}
        <ActionArea
          key={turn}
          options={LEVERAGE_OPTIONS}
          leverageCards={leverageCards}
          roleHasNoLeverage={false}
          latestNpcPulses={[]}
          castNameById={{ producer: "Producer Mara", sponsor: "Sponsor Vale" }}
          turnsCompleted={turn}
          turnsRemaining={Math.max(1, 7 - turn)}
          turnBudget={7}
          hasRecentImpact={!!outcome}
          showFreeInput={showFreeInput}
          freeInput={freeInput}
          setFreeInput={setFreeInput}
          setShowFreeInput={setShowFreeInput}
          diary={diary}
          setDiary={setDiary}
          showDiary={showDiary}
          setShowDiary={setShowDiary}
          busy={busy}
          onCommitmentActiveChange={() => {}}
          onCommitmentSummaryChange={setCommitmentSummary}
          onPickOption={submitOption}
          onPlayLeverage={(card) => resolveLeverage(card)}
          onSubmitFree={() => {}}
        />
      </section>
    </main>
  )
}
