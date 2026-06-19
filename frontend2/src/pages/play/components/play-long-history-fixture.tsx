import { useEffect, useMemo, useState } from "react"
import type { NarrativeStoryOption } from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"
import { ActionArea } from "./play-flow-panels"
import { PlayActionJumpButton } from "./play-action-jump"
import { isPlayActionAreaAwayFromViewport, scrollToPlayActionArea } from "./play-action-jump-utils"

const LONG_HISTORY_OPTIONS: NarrativeStoryOption[] = [
  {
    label: "[Stabilize] Pull the producer beside you and ask for one honest timestamp.",
    hint: "Keeps the room from scattering while you regain control.",
    handle: "time",
  },
  {
    label: "[Pressure] Ask the sponsor why their assistant was near the control door.",
    hint: "Forces a public answer before the next announcement.",
    handle: "door",
  },
  {
    label: "[Signal] Send the backup dancer to watch the service hall.",
    hint: "Creates a second set of eyes without leaving the room.",
    handle: "hall",
  },
]

const HISTORY_BEATS = [
  "Opening beat: the awards floor realizes the singer is missing.",
  "You chose to keep the countdown running while looking for a witness.",
  "Changed: the producer starts watching the sponsor instead of the stage.",
  "Next beat: the backup dancer admits the control room was already empty.",
  "You chose to quiet the crowd before panic reached the livestream.",
  "Changed: the fans outside stop chanting and begin filming the hallway.",
  "Next beat: a badge from the green room turns up under the press table.",
  "You chose to hold the badge back until the sponsor contradicted themself.",
  "Changed: the sponsor's representative asks for a private word.",
]

function splitHistoryBeat(beat: string): { label: string; body: string } {
  if (beat.startsWith("You chose ")) {
    return { label: "You chose", body: beat.replace(/^You chose\s+/, "") }
  }
  const [label, ...rest] = beat.split(":")
  if (!rest.length) return { label: "Story", body: beat }
  return { label: label.trim(), body: rest.join(":").trim() }
}

type LongHistoryOutcome = {
  title: string
  summary: string
  nextFocus: string
  items: Array<{
    label: string
    value: string
    tone: "safe" | "tense" | "gold"
  }>
}

function longHistoryOutcomeForMove(action: string): LongHistoryOutcome {
  const normalized = action.toLowerCase()
  if (normalized.includes("timestamp") || normalized.includes("stabilize")) {
    return {
      title: "Timeline anchored",
      summary: "The long transcript now has one reliable timestamp, so the next move can test who is lying.",
      nextFocus: "Use the fixed timestamp to pressure the door story instead of asking broad questions.",
      items: [
        { label: "Time", value: "one timestamp fixed", tone: "safe" },
        { label: "People", value: "producer steadier", tone: "safe" },
        { label: "Next", value: "pressure the door story", tone: "gold" },
      ],
    }
  }
  if (normalized.includes("sponsor") || normalized.includes("control")) {
    return {
      title: "Sponsor exposed",
      summary: "The room can now connect the missing singer to the control door instead of guessing.",
      nextFocus: "Use the control-door clue while the sponsor is still answering in public.",
      items: [
        { label: "Pressure", value: "sponsor cornered", tone: "tense" },
        { label: "Clue", value: "control door matters", tone: "gold" },
        { label: "Risk", value: "public answer", tone: "tense" },
      ],
    }
  }
  return {
    title: "Second watcher placed",
    summary: "The service hall is covered, so the next choice can focus on evidence instead of chasing noise.",
    nextFocus: "Return to proof now that the hallway is watched.",
    items: [
      { label: "Coverage", value: "hall watched", tone: "safe" },
      { label: "Evidence", value: "badge route protected", tone: "gold" },
      { label: "Next", value: "return to proof", tone: "safe" },
    ],
  }
}

function updateLongHistoryJump(setShowActionJump: (show: boolean) => void) {
  const actionArea = document.querySelector<HTMLElement>("[data-play-action-area='true']")
  setShowActionJump(actionArea ? isPlayActionAreaAwayFromViewport(actionArea) : false)
}

export function PlayLongHistoryFixture({ onBackHome }: { onBackHome: () => void }) {
  const t = useT()
  const [turn, setTurn] = useState(0)
  const [busy, setBusy] = useState(false)
  const [showActionJump, setShowActionJump] = useState(false)
  const [showFreeInput, setShowFreeInput] = useState(false)
  const [freeInput, setFreeInput] = useState("")
  const [diary, setDiary] = useState("")
  const [showDiary, setShowDiary] = useState(false)
  const [status, setStatus] = useState("The current move is below a long transcript.")
  const [submittedMove, setSubmittedMove] = useState("")
  const [outcome, setOutcome] = useState<LongHistoryOutcome | null>(null)
  const options = useMemo(() => LONG_HISTORY_OPTIONS, [])

  useEffect(() => {
    if (!busy) return
    const timer = window.setTimeout(() => {
      setBusy(false)
      setShowFreeInput(false)
      setFreeInput("")
      setDiary("")
      setShowDiary(false)
      setTurn((value) => value + 1)
      setOutcome(longHistoryOutcomeForMove(submittedMove))
      setStatus("What changed")
      window.setTimeout(() => {
        document
          .querySelector<HTMLElement>("[data-play-long-history-result-feedback='true']")
          ?.scrollIntoView({ block: "start", behavior: "smooth" })
      }, 0)
    }, 720)
    return () => window.clearTimeout(timer)
  }, [busy, submittedMove])

  const submitMove = (label: string) => {
    if (busy) return
    setSubmittedMove(label)
    setOutcome(null)
    setStatus(`Move held: ${label}`)
    setBusy(true)
  }

  useEffect(() => {
    let frame = 0
    const requestUpdate = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => updateLongHistoryJump(setShowActionJump))
    }
    requestUpdate()
    const timer = window.setTimeout(() => updateLongHistoryJump(setShowActionJump), 220)
    window.addEventListener("scroll", requestUpdate, { passive: true })
    window.addEventListener("resize", requestUpdate)
    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(timer)
      window.removeEventListener("scroll", requestUpdate)
      window.removeEventListener("resize", requestUpdate)
    }
  }, [])

  return (
    <main
      style={{
        ...ppStyles.page,
        minHeight: "100vh",
        padding: "24px 28px 96px",
        gap: 18,
      }}
      data-play-long-history-fixture="true"
    >
      <button type="button" style={ppStyles.backBtn} onClick={onBackHome}>
        {t("action.back_home")}
      </button>
      <section
        style={{
          maxWidth: 860,
          display: "grid",
          gap: 14,
        }}
        aria-label="Long-history action rehearsal"
      >
        <p style={{ margin: 0, color: "rgba(255,245,230,0.74)", lineHeight: 1.5 }}>
          {outcome ? "Result ready below." : status}
        </p>
        <div style={{ display: "grid", gap: 12 }}>
          {HISTORY_BEATS.map((beat, index) => {
            const parsedBeat = splitHistoryBeat(beat)
            return (
              <article
                key={beat}
                style={{
                  minHeight: 118,
                  borderTop: "1px solid rgba(212,168,83,0.22)",
                  paddingTop: 12,
                  color: index % 2 === 0 ? "rgba(255,245,230,0.82)" : "rgba(232,218,205,0.66)",
                  fontFamily: "var(--font-narrative)",
                  lineHeight: 1.55,
                }}
                data-play-long-history-beat="true"
                data-play-long-history-beat-kind={parsedBeat.label.toLowerCase().replace(/\s+/g, "-")}
              >
                <span style={ppStyles.longHistoryBeatLabel}>{parsedBeat.label}</span>
                <span style={ppStyles.longHistoryBeatBody}>{parsedBeat.body}</span>
              </article>
            )
          })}
        </div>
        {outcome ? (
          <section
            style={{
              ...ppStyles.outcomeReceipt,
              gap: 10,
            }}
            aria-label={`What changed: ${outcome.title}`}
            data-play-long-history-result-feedback="true"
          >
            <span style={ppStyles.outcomeReceiptHeader}>
              <span style={ppStyles.outcomeReceiptKicker}>What changed</span>
              <span style={ppStyles.outcomeReceiptHint}>Use this before choosing the next move.</span>
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
                  data-play-long-history-result-item="true"
                  data-play-long-history-result-tone={item.tone}
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
            <span
              style={ppStyles.outcomeReceiptNextFocus}
              data-play-long-history-next-focus="true"
            >
              <span style={ppStyles.outcomeReceiptItemLabel}>Next choice:</span>
              <strong style={ppStyles.outcomeReceiptNextValue}>{outcome.nextFocus}</strong>
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
          turnsCompleted={9 + turn}
          turnsRemaining={3}
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
          onCommitmentSummaryChange={() => {}}
          onPickOption={(idx) => submitMove(options[idx]?.label ?? "move")}
          onPlayLeverage={() => {}}
          onSubmitFree={() => submitMove(freeInput.trim() || "custom move")}
        />
      </section>
      {showActionJump ? (
        <PlayActionJumpButton
          detail={outcome ? t("play.action_jump_detail_update") : t("play.action_jump_detail_choose")}
          compactDetail={outcome ? t("play.action_jump_detail_update_compact") : t("play.action_jump_detail_choose_compact")}
          stage={outcome ? "update" : "choose"}
          onClick={() => {
            scrollToPlayActionArea()
            window.setTimeout(() => updateLongHistoryJump(setShowActionJump), 360)
          }}
        />
      ) : null}
    </main>
  )
}
