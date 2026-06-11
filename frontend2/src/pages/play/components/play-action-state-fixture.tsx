import { useEffect, useMemo, useState } from "react"
import type { NarrativeStoryOption } from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"
import type { ActionCommitmentSummary } from "../play-types"
import { ActionArea } from "./play-flow-panels"

const FIRST_OPTIONS: NarrativeStoryOption[] = [
  {
    label: "[Hold] Ask the producer to freeze the livestream countdown.",
    hint: "Buys one breath without surrendering the room.",
    handle: "freeze",
  },
  {
    label: "[Press] Tell the sponsor the missing singer was last seen near control.",
    hint: "Sharp pressure; the sponsor must respond publicly.",
    handle: "sponsor",
  },
  {
    label: "[Cover] Signal the backup dancer to keep the crowd calm.",
    hint: "Stabilizes the room while you search for proof.",
    handle: "cover",
  },
]

const NEXT_OPTIONS: NarrativeStoryOption[] = [
  {
    label: "[Reveal] Show the producer the empty green-room badge.",
    hint: "A concrete clue enters the scene.",
    handle: "badge",
  },
  {
    label: "[Deflect] Move the sponsor into a private hallway.",
    hint: "Cuts public pressure but risks rumor.",
    handle: "hall",
  },
]

function shortActionLabel(action: string): string {
  return action.replace(/^\[[^\]]+\]\s*/, "").trim()
}

export function PlayActionStateFixture({ onBackHome }: { onBackHome: () => void }) {
  const t = useT()
  const [turn, setTurn] = useState(0)
  const [busy, setBusy] = useState(false)
  const [showFreeInput, setShowFreeInput] = useState(false)
  const [freeInput, setFreeInput] = useState("")
  const [diary, setDiary] = useState("")
  const [showDiary, setShowDiary] = useState(false)
  const [status, setStatus] = useState("Choose a move, confirm it, then watch the next action set appear.")
  const [commitmentSummary, setCommitmentSummary] = useState<ActionCommitmentSummary | null>(null)
  const options = useMemo(() => (turn % 2 === 0 ? FIRST_OPTIONS : NEXT_OPTIONS), [turn])

  useEffect(() => {
    if (!busy) return
    const timer = window.setTimeout(() => {
      setBusy(false)
      setShowFreeInput(false)
      setFreeInput("")
      setDiary("")
      setShowDiary(false)
      setTurn((value) => value + 1)
      setStatus("Result landed. The next action set is ready.")
    }, 720)
    return () => window.clearTimeout(timer)
  }, [busy])

  const submitMove = (label: string) => {
    if (busy) return
    setStatus(`Move held: ${shortActionLabel(label)}`)
    setBusy(true)
  }

  return (
    <main
      style={{
        ...ppStyles.page,
        minHeight: "100vh",
        padding: "32px",
        gap: 18,
      }}
      data-play-action-fixture="true"
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
          maxWidth: 840,
          display: "grid",
          gap: 12,
        }}
        aria-label="Play action rehearsal"
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
          >
            {commitmentSummary.kicker}: {commitmentSummary.title}
          </p>
        ) : null}
        <ActionArea
          key={turn}
          options={options}
          leverageCards={[]}
          roleHasNoLeverage={false}
          latestNpcPulses={[]}
          castNameById={{}}
          turnsCompleted={turn}
          turnsRemaining={Math.max(1, 12 - turn)}
          turnBudget={12}
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
          onOpenAdvisor={() => setStatus("Advisor stays closed in this rehearsal. Choose or write a move.")}
          onPickOption={(idx) => submitMove(options[idx]?.label ?? "selected move")}
          onPlayLeverage={() => {}}
          onSubmitFree={() => submitMove(freeInput.trim() || "custom move")}
        />
      </section>
    </main>
  )
}
