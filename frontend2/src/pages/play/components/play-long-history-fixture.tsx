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
      setStatus("Result landed. The next action set is ready.")
    }, 720)
    return () => window.clearTimeout(timer)
  }, [busy])

  const submitMove = (label: string) => {
    if (busy) return
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
          {status}
        </p>
        <div style={{ display: "grid", gap: 12 }}>
          {HISTORY_BEATS.map((beat, index) => (
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
            >
              {beat}
            </article>
          ))}
        </div>
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
          onPickOption={(idx) => submitMove(options[idx]?.handle ?? "move")}
          onPlayLeverage={() => {}}
          onSubmitFree={() => submitMove(freeInput.trim() || "custom move")}
        />
      </section>
      {showActionJump ? (
        <PlayActionJumpButton
          detail={t("play.action_jump_detail_choose")}
          stage="choose"
          onClick={() => {
            scrollToPlayActionArea()
            window.setTimeout(() => updateLongHistoryJump(setShowActionJump), 360)
          }}
        />
      ) : null}
    </main>
  )
}
