import { useEffect, useMemo, useState } from "react"
import type { NarrativeStoryOption } from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"
import type { ActionCommitmentSummary } from "../play-types"
import { ActionArea } from "./play-flow-panels"
import { PlayLongHistoryFixture } from "./play-long-history-fixture"

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

type RehearsalOutcome = {
  title: string
  summary: string
  nextReason: string
  items: Array<{
    label: string
    value: string
    tone: "safe" | "tense" | "gold"
  }>
}

function rehearsalOutcomeForMove(action: string): RehearsalOutcome {
  const normalized = action.toLowerCase()
  if (normalized.includes("producer") || normalized.includes("freeze")) {
    return {
      title: "Time bought",
      summary: "The countdown stops long enough for the next move to use a concrete clue.",
      nextReason: "The room is stable now, so Reveal and Deflect are about spending that pause.",
      items: [
        { label: "Room", value: "producer holding", tone: "safe" },
        { label: "Clue", value: "badge can surface", tone: "gold" },
        { label: "Next", value: "reveal or deflect", tone: "tense" },
      ],
    }
  }
  if (normalized.includes("sponsor") || normalized.includes("control")) {
    return {
      title: "Pressure moved",
      summary: "The sponsor is now part of the room's attention instead of background noise.",
      nextReason: "The sponsor is exposed, so the new choices either show proof or move pressure private.",
      items: [
        { label: "Pressure", value: "public answer forced", tone: "tense" },
        { label: "Trust", value: "producer watching", tone: "safe" },
        { label: "Next", value: "private hallway opens", tone: "gold" },
      ],
    }
  }
  if (normalized.includes("dancer") || normalized.includes("crowd")) {
    return {
      title: "Crowd steadied",
      summary: "The room stays playable, but the search now depends on proof instead of noise control.",
      nextReason: "The crowd is held, so the next menu shifts toward evidence and risk control.",
      items: [
        { label: "Crowd", value: "panic contained", tone: "safe" },
        { label: "Evidence", value: "badge route clearer", tone: "gold" },
        { label: "Risk", value: "rumor still rising", tone: "tense" },
      ],
    }
  }
  return {
    title: "Custom move registered",
    summary: "The room accepted the move; the next choices are now shaped by that pressure.",
    nextReason: "The next actions are built from the pressure your custom move created.",
    items: [
      { label: "Room", value: "attention shifted", tone: "safe" },
      { label: "Pressure", value: "new angle created", tone: "tense" },
      { label: "Next", value: "choices updated", tone: "gold" },
    ],
  }
}

export function PlayActionStateFixture({
  onBackHome,
  scenario,
}: {
  onBackHome: () => void
  scenario?: "long-history"
}) {
  if (scenario === "long-history") {
    return <PlayLongHistoryFixture onBackHome={onBackHome} />
  }

  return <PlayActionStateFixtureBase onBackHome={onBackHome} />
}

function PlayActionStateFixtureBase({ onBackHome }: { onBackHome: () => void }) {
  const t = useT()
  const [turn, setTurn] = useState(0)
  const [busy, setBusy] = useState(false)
  const [showFreeInput, setShowFreeInput] = useState(false)
  const [freeInput, setFreeInput] = useState("")
  const [diary, setDiary] = useState("")
  const [showDiary, setShowDiary] = useState(false)
  const [status, setStatus] = useState("Action surface rehearsal.")
  const [commitmentSummary, setCommitmentSummary] = useState<ActionCommitmentSummary | null>(null)
  const [submittedMove, setSubmittedMove] = useState("")
  const [outcome, setOutcome] = useState<RehearsalOutcome | null>(null)
  const [showNextOptions, setShowNextOptions] = useState(false)
  const options = useMemo(() => (showNextOptions ? NEXT_OPTIONS : FIRST_OPTIONS), [showNextOptions])

  useEffect(() => {
    if (!busy) return
    const timer = window.setTimeout(() => {
      setBusy(false)
      setShowFreeInput(false)
      setFreeInput("")
      setDiary("")
      setShowDiary(false)
      setShowNextOptions(true)
      setTurn((value) => value + 1)
      setOutcome(rehearsalOutcomeForMove(submittedMove))
      setStatus("What changed")
    }, 720)
    return () => window.clearTimeout(timer)
  }, [busy, submittedMove])

  const submitMove = (label: string) => {
    if (busy) return
    setSubmittedMove(label)
    setOutcome(null)
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
        {!outcome ? (
          <p
            style={{ margin: 0, color: "rgba(255,245,230,0.76)", lineHeight: 1.5 }}
            aria-live="polite"
          >
            {status}
          </p>
        ) : null}
        {commitmentSummary ? (
          <p
            style={{ margin: 0, color: "rgba(246,221,176,0.74)", fontSize: 12.5, lineHeight: 1.45 }}
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
            aria-label={`What changed: ${outcome.title}`}
            data-play-action-result-feedback="true"
          >
            <span style={ppStyles.outcomeReceiptHeader}>
              <span style={ppStyles.outcomeReceiptKicker} data-play-action-result-title="true">
                What changed
              </span>
              <span style={ppStyles.outcomeReceiptHint}>
                Your last move changed the next action menu.
              </span>
            </span>
            <span style={ppStyles.outcomeReceiptPhrase} data-play-action-result-move="true">
              <span style={ppStyles.outcomeReceiptItemLabel}>Your move:</span>
              <strong
                style={{
                  ...ppStyles.outcomeReceiptValue,
                  ...ppStyles.outcomeReceiptValueMobile,
                }}
                title={shortActionLabel(submittedMove)}
              >
                {shortActionLabel(submittedMove)}
              </strong>
            </span>
            <strong
              style={{
                color: "rgba(255,248,232,0.96)",
                fontSize: 16,
                lineHeight: 1.25,
              }}
            >
              {outcome.title}
            </strong>
            <span style={{ color: "rgba(246,239,222,0.74)", fontSize: 13, lineHeight: 1.45 }}>
              {outcome.summary}
            </span>
            <span style={ppStyles.outcomeReceiptSentence}>
              {outcome.items.map((item) => (
                <span
                  key={`${item.label}:${item.value}`}
                  style={ppStyles.outcomeReceiptPhrase}
                  data-play-action-result-item="true"
                  data-play-action-result-tone={item.tone}
                >
                  <span style={ppStyles.outcomeReceiptItemLabel}>{item.label}:</span>
                  <strong
                    style={{
                      ...ppStyles.outcomeReceiptValue,
                      ...(item.tone === "safe" ? ppStyles.outcomeReceiptChipSafe : null),
                      ...(item.tone === "tense" ? ppStyles.outcomeReceiptChipTense : null),
                      ...(item.tone === "gold" ? ppStyles.outcomeReceiptChipGold : null),
                    }}
                  >
                    {item.value}
                  </strong>
                </span>
              ))}
            </span>
            <span style={ppStyles.outcomeReceiptNextFocus} data-play-action-result-next-bridge="true">
              <span style={ppStyles.outcomeReceiptItemLabel}>Next actions:</span>
              <strong style={ppStyles.outcomeReceiptNextValue}>
                {outcome.nextReason}
              </strong>
            </span>
          </section>
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
          onPickOption={(idx) => submitMove(options[idx]?.label ?? "selected move")}
          onPlayLeverage={() => {}}
          onSubmitFree={() => submitMove(freeInput.trim() || "custom move")}
        />
      </section>
    </main>
  )
}
