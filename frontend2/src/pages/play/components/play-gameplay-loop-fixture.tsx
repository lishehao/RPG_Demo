import { useEffect, useMemo, useState, type CSSProperties } from "react"
import { useT } from "../../../shared/lib/i18n"
import { actionPalette, ppStyles } from "../play-styles"

type FixturePhase = "choosing" | "pending" | "resolved"

type Track = {
  id: string
  label: string
  value: string
  note: string
}

type FixtureDelta = {
  id: string
  label: string
  tone: "gain" | "cost" | "unlock" | "shift"
}

type FixtureAction = {
  id: string
  number: number
  title: string
  body: string
  forecast: FixtureDelta[]
  resolved: FixtureDelta[]
  unlocksClue?: boolean
}

type CommittedMove = {
  action: FixtureAction
  motive: string
}

const INITIAL_TRACKS: Track[] = [
  { id: "time", label: "Time", value: "8 min", note: "Countdown before the live award reveal." },
  { id: "pressure", label: "Public pressure", value: "2 / 5", note: "The room is restless, but not breaking." },
  { id: "lena", label: "Lena trust", value: "1 / 5", note: "Lena will help if the ask feels specific." },
  { id: "evidence", label: "Evidence", value: "0 / 3", note: "No concrete proof has landed yet." },
]

const RESOLVED_TRACKS: Track[] = [
  { id: "time", label: "Time", value: "7 min", note: "One minute spent forcing the room to answer." },
  { id: "pressure", label: "Public pressure", value: "3 / 5", note: "The sponsor notices the challenge." },
  { id: "lena", label: "Lena trust", value: "2 / 5", note: "Lena sees a concrete path to help." },
  { id: "evidence", label: "Evidence", value: "1 / 3", note: "A badge clue can now shape the next move." },
]

const PEOPLE = [
  {
    id: "lena",
    name: "Lena",
    role: "Stage manager",
    state: "Watching the countdown and the side doors.",
    action: "Ask Lena to hold the crowd.",
    advice: "Lena can keep the room steady if you give her a specific job.",
    suggestedMove: "Ask Lena to hold the crowd",
  },
  {
    id: "arthur",
    name: "Arthur",
    role: "Producer",
    state: "Trying to keep the sponsor calm.",
    action: "Press Arthur for the last confirmed timestamp.",
    advice: "Arthur reacts when the question is public and tied to a concrete gap.",
    suggestedMove: "Pressure Arthur on the missing badge",
  },
  {
    id: "marcus",
    name: "Marcus",
    role: "Sponsor rep",
    state: "Smiling too hard for the cameras.",
    action: "Read Marcus before the next public answer.",
    advice: "Marcus can buy time, but asking him costs trust with the people backstage.",
    suggestedMove: "Send Marcus to stall sponsors",
  },
  {
    id: "dana",
    name: "Dana Vale",
    role: "Crisis confidant",
    state: "Frames the move without taking control.",
    action: "Ask Dana which pressure point matters.",
    advice: "Dana points out the tradeoff, but the decision still stays with you.",
    suggestedMove: "Pick the move whose cost you can afford.",
  },
]

const INITIAL_ACTIONS: FixtureAction[] = [
  {
    id: "lena-hold",
    number: 1,
    title: "Ask Lena to hold the crowd",
    body: "Give Lena a narrow job: keep the fans busy while you check the green-room path.",
    forecast: [
      { id: "time-cost", label: "Time -1", tone: "cost" },
      { id: "trust-gain", label: "Lena trust +1", tone: "gain" },
      { id: "pressure-down", label: "Pressure -1", tone: "gain" },
    ],
    resolved: [
      { id: "time-spent", label: "Time -1", tone: "cost" },
      { id: "lena-helps", label: "Lena trust +1", tone: "gain" },
      { id: "room-held", label: "Crowd held", tone: "shift" },
    ],
  },
  {
    id: "arthur-badge",
    number: 2,
    title: "Pressure Arthur on the missing badge",
    body: "Name the green-room access gap and make Arthur answer before the room drifts.",
    forecast: [
      { id: "pressure-up", label: "Pressure +1", tone: "cost" },
      { id: "evidence-unlock", label: "Evidence unlocked", tone: "unlock" },
      { id: "arthur-attention", label: "Arthur attention locked", tone: "shift" },
    ],
    resolved: [
      { id: "pressure-rises", label: "Public pressure +1", tone: "cost" },
      { id: "badge-found", label: "Green-room badge discovered", tone: "unlock" },
      { id: "arthur-cornered", label: "Arthur must answer", tone: "shift" },
    ],
    unlocksClue: true,
  },
  {
    id: "marcus-stall",
    number: 3,
    title: "Send Marcus to stall sponsors",
    body: "Move the sponsor pressure away from the stage while you find a cleaner opening.",
    forecast: [
      { id: "time-gain", label: "Time +1", tone: "gain" },
      { id: "lena-cost", label: "Lena trust -1", tone: "cost" },
      { id: "opportunity-open", label: "Hallway opportunity", tone: "unlock" },
    ],
    resolved: [
      { id: "more-time", label: "Time +1", tone: "gain" },
      { id: "lena-doubt", label: "Lena trust -1", tone: "cost" },
      { id: "hall-open", label: "Private hallway open", tone: "unlock" },
    ],
  },
]

const UNLOCKED_ACTIONS: FixtureAction[] = [
  {
    id: "show-badge",
    number: 1,
    title: "Show Lena the green-room badge",
    body: "Use the badge as proof and ask Lena to point you toward the last person with access.",
    forecast: [
      { id: "evidence-use", label: "Use badge clue", tone: "unlock" },
      { id: "lena-trust", label: "Lena trust +1", tone: "gain" },
      { id: "next-door", label: "Control door opens", tone: "unlock" },
    ],
    resolved: [
      { id: "badge-active", label: "Badge spent for access", tone: "unlock" },
      { id: "door-open", label: "Control door opens", tone: "unlock" },
    ],
  },
  {
    id: "trap-answer",
    number: 2,
    title: "Let Arthur contradict Marcus",
    body: "Hold the badge back and make the two public stories collide in front of the room.",
    forecast: [
      { id: "pressure-risk", label: "Pressure +1", tone: "cost" },
      { id: "leverage-gain", label: "Leverage +1", tone: "gain" },
    ],
    resolved: [
      { id: "leverage-live", label: "Sponsor leverage live", tone: "gain" },
      { id: "room-shifts", label: "Room watches Marcus", tone: "shift" },
    ],
  },
]

const toneStyle: Record<FixtureDelta["tone"], CSSProperties> = {
  gain: {
    borderColor: "rgba(126, 204, 164, 0.28)",
    color: "rgba(196, 246, 216, 0.92)",
    background: "rgba(62, 134, 96, 0.16)",
  },
  cost: {
    borderColor: "rgba(229, 176, 100, 0.30)",
    color: "rgba(244, 210, 153, 0.92)",
    background: "rgba(141, 92, 36, 0.16)",
  },
  unlock: {
    borderColor: "rgba(216, 177, 99, 0.34)",
    color: "rgba(249, 226, 174, 0.95)",
    background: "rgba(151, 107, 40, 0.18)",
  },
  shift: {
    borderColor: "rgba(172, 178, 196, 0.24)",
    color: "rgba(224, 226, 235, 0.88)",
    background: "rgba(101, 108, 128, 0.14)",
  },
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("")
}

function DeltaChip({ delta, hook }: { delta: FixtureDelta; hook?: string }) {
  return (
    <span
      style={{ ...styles.chip, ...toneStyle[delta.tone] }}
      data-gameplay-forecast-chip={hook === "forecast" ? "true" : undefined}
      data-gameplay-delta={hook === "delta" ? "true" : undefined}
    >
      {delta.label}
    </span>
  )
}

export function PlayGameplayLoopFixture({ onBackHome }: { onBackHome: () => void }) {
  const t = useT()
  const [phase, setPhase] = useState<FixturePhase>("choosing")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [motiveOpen, setMotiveOpen] = useState(false)
  const [motive, setMotive] = useState("")
  const [committed, setCommitted] = useState<CommittedMove | null>(null)
  const [unlockedClue, setUnlockedClue] = useState(false)
  const [tracks, setTracks] = useState(INITIAL_TRACKS)
  const [resolvedDeltas, setResolvedDeltas] = useState<FixtureDelta[]>([])
  const [consultedPersonId, setConsultedPersonId] = useState<string | null>(null)
  const actions = useMemo(() => (unlockedClue ? UNLOCKED_ACTIONS : INITIAL_ACTIONS), [unlockedClue])
  const selectedAction = actions.find((action) => action.id === selectedId) ?? null
  const consultedPerson = PEOPLE.find((person) => person.id === consultedPersonId) ?? null
  const isPending = phase === "pending"

  useEffect(() => {
    if (!isPending || !committed) return
    const timer = window.setTimeout(() => {
      setResolvedDeltas(committed.action.resolved)
      if (committed.action.unlocksClue) {
        setUnlockedClue(true)
      }
      setTracks(committed.action.unlocksClue ? RESOLVED_TRACKS : INITIAL_TRACKS)
      setPhase("resolved")
      setSelectedId(null)
      setMotiveOpen(false)
      setMotive("")
    }, 780)
    return () => window.clearTimeout(timer)
  }, [committed, isPending])

  const selectAction = (action: FixtureAction) => {
    if (isPending) return
    setSelectedId((current) => (current === action.id ? current : action.id))
    setMotiveOpen(false)
  }

  const collapseSelection = () => {
    if (isPending) return
    setSelectedId(null)
    setMotiveOpen(false)
  }

  const confirmAction = (action: FixtureAction, motiveText = "") => {
    if (isPending) return
    setCommitted({ action, motive: motiveText.trim() })
    setResolvedDeltas([])
    setPhase("pending")
  }

  return (
    <main
      style={{
        ...ppStyles.page,
        minHeight: "100vh",
        padding: "24px clamp(16px, 4vw, 34px) 72px",
        gap: 18,
        overflowX: "hidden",
      }}
      data-gameplay-loop-fixture="true"
    >
      <button type="button" style={ppStyles.backBtn} onClick={onBackHome}>
        {t("action.back_home")}
      </button>

      <section style={styles.shell} aria-label="Gameplay loop rehearsal">
        <div style={styles.mainColumn}>
          <section style={styles.objectivePanel} data-gameplay-objective="true">
            <span style={styles.kicker}>Episode goal</span>
            <h1 style={styles.title}>Find the singer before the countdown ends</h1>
            <p style={styles.bodyCopy}>
              The awards livestream is still running. Every move should buy time, expose proof, or move a person into position.
            </p>
          </section>

          <section style={styles.trackGrid} aria-label="Scene pressure">
            {tracks.map((track) => (
              <article
                key={track.id}
                style={styles.trackCard}
                data-gameplay-pressure-track={track.id}
              >
                <span style={styles.trackLabel}>{track.label}</span>
                <strong style={styles.trackValue}>{track.value}</strong>
                <span style={styles.trackNote}>{track.note}</span>
              </article>
            ))}
          </section>

          {phase === "pending" && committed ? (
            <section style={styles.pendingStack} data-gameplay-reaction-panel="true">
              <article style={styles.receiptPanel} data-play-move-receipt="true">
                <span style={styles.kicker}>Your move</span>
                <strong style={styles.receiptTitle}>{committed.action.title}</strong>
                {committed.motive ? <span style={styles.receiptMotive}>Motive: {committed.motive}</span> : null}
              </article>
              <article style={styles.reactionPanel} data-play-room-reacting="true">
                <span style={styles.reactionPulse} aria-hidden="true" />
                <div>
                  <strong style={styles.reactionTitle}>The room is reacting</strong>
                  <p style={styles.reactionCopy}>Lena turns toward Arthur. The sponsor smiles for the camera and waits to see who breaks first.</p>
                </div>
              </article>
            </section>
          ) : (
            <section
              style={styles.actionArea}
              data-gameplay-action-area="true"
              onPointerDown={(event) => {
                if (event.target === event.currentTarget) {
                  collapseSelection()
                }
              }}
            >
              <div style={styles.sectionHeader}>
                <span style={styles.kicker}>Choose a move</span>
                <span style={styles.headerNote}>{unlockedClue ? "Badge clue has changed the action set." : "Forecasts show likely tradeoffs."}</span>
              </div>
              <div style={styles.actionGrid}>
                {actions.map((action) => {
                  const selected = selectedId === action.id
                  return (
                    <article
                      key={action.id}
                      style={{
                        ...styles.actionCard,
                        ...(selected ? styles.actionCardSelected : null),
                      }}
                      data-gameplay-action-card="true"
                      data-gameplay-unlocked-action={unlockedClue ? "true" : undefined}
                      data-gameplay-selected-action={selected ? "true" : undefined}
                      onClick={() => selectAction(action)}
                    >
                      <span style={styles.actionMeta}>Move {action.number}</span>
                      <strong style={styles.actionTitle}>{action.title}</strong>
                      <p style={styles.actionBody}>{action.body}</p>
                      <div style={styles.chipRow} aria-label="Forecast">
                        {action.forecast.map((delta) => (
                          <DeltaChip key={delta.id} delta={delta} hook="forecast" />
                        ))}
                      </div>
                      {selected ? (
                        <div style={styles.expandedPanel}>
                          {motiveOpen ? (
                            <div style={styles.motivePanel} data-gameplay-motive-panel="true">
                              <label style={styles.motiveLabel} htmlFor="gameplay-loop-motive">
                                Add the motive behind your move.
                              </label>
                              <textarea
                                id="gameplay-loop-motive"
                                value={motive}
                                onChange={(event) => setMotive(event.target.value)}
                                style={styles.motiveInput}
                                rows={2}
                                maxLength={240}
                                placeholder="Keep the room watching Arthur, not you."
                              />
                              <div style={styles.confirmRow}>
                                <button
                                  type="button"
                                  style={styles.primaryButton}
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    confirmAction(action, motive)
                                  }}
                                  data-gameplay-confirm="true"
                                >
                                  Take action with motive
                                </button>
                                <button
                                  type="button"
                                  style={styles.quietButton}
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    setMotiveOpen(false)
                                  }}
                                >
                                  Back to move
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div style={styles.confirmRow}>
                              <button
                                type="button"
                                style={styles.primaryButton}
                                onClick={(event) => {
                                  event.stopPropagation()
                                  confirmAction(action)
                                }}
                                data-gameplay-confirm="true"
                              >
                                Take this action
                              </button>
                              <button
                                type="button"
                                style={styles.secondaryButton}
                                onClick={(event) => {
                                  event.stopPropagation()
                                  setMotiveOpen(true)
                                }}
                                data-gameplay-inner-motive="true"
                              >
                                Use inner motive
                              </button>
                            </div>
                          )}
                        </div>
                      ) : null}
                    </article>
                  )
                })}
              </div>
            </section>
          )}

          {phase === "resolved" ? (
            <section style={styles.resolvedPanel} data-gameplay-resolved="true">
              <div style={styles.sectionHeader}>
                <span style={styles.kicker}>Changed</span>
                <span style={styles.headerNote}>The next moves now respond to the clue.</span>
              </div>
              <div style={styles.chipRow}>
                {resolvedDeltas.map((delta) => (
                  <DeltaChip key={delta.id} delta={delta} hook="delta" />
                ))}
              </div>
            </section>
          ) : null}
        </div>

        <aside style={styles.rail} aria-label="People and clues">
          <section style={styles.railSection}>
            <div style={styles.sectionHeader}>
              <span style={styles.kicker}>In the room</span>
              <span style={styles.headerNote}>People are resources.</span>
            </div>
            <div style={styles.personList}>
              {PEOPLE.map((person) => {
                const consulted = consultedPersonId === person.id
                return (
                  <article
                    key={person.name}
                    style={{
                      ...styles.personRow,
                      ...(consulted ? styles.personRowConsulted : null),
                    }}
                    data-gameplay-person-consulted={consulted ? "true" : undefined}
                  >
                    <span style={styles.avatarFrame}>{initials(person.name)}</span>
                    <span style={styles.personText}>
                      <strong style={styles.personName}>{person.name}</strong>
                      <span style={styles.personRole}>{person.role}</span>
                      <span style={styles.personState}>{person.state}</span>
                    </span>
                    <button
                      type="button"
                      style={{
                        ...styles.personAction,
                        ...(consulted ? styles.personActionActive : null),
                      }}
                      data-gameplay-person-action="true"
                      aria-label={person.action}
                      title={person.action}
                      onClick={() => setConsultedPersonId(person.id)}
                    >
                      {consulted ? "Asked" : "Ask"}
                    </button>
                  </article>
                )
              })}
            </div>
            {consultedPerson ? (
              <article style={styles.personAdvice} data-gameplay-person-advice="true">
                <span style={styles.kicker}>Advice from {consultedPerson.name}</span>
                <strong style={styles.personAdviceTitle}>{consultedPerson.suggestedMove}</strong>
                <span style={styles.personAdviceBody}>{consultedPerson.advice}</span>
              </article>
            ) : null}
          </section>

          <section style={styles.railSection}>
            <div style={styles.sectionHeader}>
              <span style={styles.kicker}>Clues</span>
              <span style={styles.headerNote}>{unlockedClue ? "1 usable" : "None discovered"}</span>
            </div>
            <article
              style={{
                ...styles.clueCard,
                ...(unlockedClue ? styles.clueCardUnlocked : styles.clueCardLocked),
              }}
              data-gameplay-clue-card={unlockedClue ? "green-room-badge" : "locked"}
            >
              <span style={styles.clueStatus}>{unlockedClue ? "Discovered" : "Locked"}</span>
              <strong style={styles.clueTitle}>{unlockedClue ? "Green-room badge" : "Green-room clue"}</strong>
              <span style={styles.clueBody}>
                {unlockedClue
                  ? "Arthur has to explain why this access badge was missing."
                  : "A concrete clue will open a sharper next move."}
              </span>
            </article>
          </section>
        </aside>
      </section>
    </main>
  )
}

const styles: Record<string, CSSProperties> = {
  shell: {
    width: "100%",
    maxWidth: 1180,
    margin: "0 auto",
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))",
    gap: 18,
    alignItems: "start",
  },
  mainColumn: {
    minWidth: 0,
    display: "grid",
    gap: 14,
  },
  objectivePanel: {
    borderTop: "1px solid rgba(229,190,124,0.16)",
    borderRight: "1px solid rgba(229,190,124,0.16)",
    borderBottom: "1px solid rgba(229,190,124,0.16)",
    borderLeft: `3px solid ${actionPalette.selectedBorderLeft}`,
    background: "linear-gradient(145deg, rgba(24,24,22,0.86), rgba(8,9,10,0.90))",
    boxShadow: "0 20px 52px rgba(0,0,0,0.28)",
    padding: "18px",
    borderRadius: 8,
  },
  kicker: {
    display: "block",
    color: actionPalette.amberText,
    fontSize: 11,
    fontWeight: 780,
    letterSpacing: 0,
  },
  title: {
    margin: "7px 0 8px",
    color: actionPalette.ivoryText,
    fontFamily: "var(--font-narrative)",
    fontSize: "clamp(24px, 4vw, 38px)",
    lineHeight: 1.05,
  },
  bodyCopy: {
    margin: 0,
    color: actionPalette.mutedIvory,
    lineHeight: 1.55,
    maxWidth: 720,
  },
  trackGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(142px, 1fr))",
    gap: 10,
  },
  trackCard: {
    minWidth: 0,
    border: "1px solid rgba(229,190,124,0.13)",
    background: "rgba(12,13,14,0.76)",
    padding: "12px",
    borderRadius: 8,
    display: "grid",
    gap: 5,
  },
  trackLabel: {
    color: actionPalette.faintIvory,
    fontSize: 11,
    fontWeight: 760,
  },
  trackValue: {
    color: actionPalette.ivoryText,
    fontSize: 19,
    fontFamily: "var(--font-narrative)",
  },
  trackNote: {
    color: "rgba(229,219,199,0.62)",
    fontSize: 12,
    lineHeight: 1.35,
  },
  actionArea: {
    border: "1px solid rgba(229,190,124,0.14)",
    background: "rgba(6,7,8,0.58)",
    padding: 12,
    borderRadius: 8,
    display: "grid",
    gap: 12,
  },
  sectionHeader: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 10,
    flexWrap: "wrap",
  },
  headerNote: {
    color: actionPalette.faintIvory,
    fontSize: 12,
  },
  actionGrid: {
    display: "grid",
    gap: 10,
  },
  actionCard: {
    minWidth: 0,
    border: "1px solid rgba(229,190,124,0.14)",
    background: actionPalette.optionBackground,
    borderRadius: 8,
    padding: 14,
    display: "grid",
    gap: 8,
    cursor: "pointer",
    transition: "border-color 160ms ease, transform 160ms ease, background 160ms ease",
  },
  actionCardSelected: {
    borderColor: actionPalette.selectedBorderLeft,
    background: actionPalette.selectedBackground,
    boxShadow: actionPalette.selectedGlow,
  },
  actionMeta: {
    color: actionPalette.amberText,
    fontSize: 11,
    fontWeight: 800,
  },
  actionTitle: {
    color: actionPalette.ivoryText,
    fontSize: 18,
    lineHeight: 1.2,
    fontFamily: "var(--font-narrative)",
  },
  actionBody: {
    margin: 0,
    color: actionPalette.mutedIvory,
    lineHeight: 1.45,
    fontSize: 13.5,
  },
  chipRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: 7,
  },
  chip: {
    border: "1px solid",
    borderRadius: 6,
    padding: "5px 8px",
    fontSize: 12,
    fontWeight: 760,
    lineHeight: 1,
  },
  expandedPanel: {
    marginTop: 4,
    paddingTop: 12,
    borderTop: `1px solid ${actionPalette.champagneLine}`,
  },
  confirmRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 180px), 1fr))",
    gap: 9,
  },
  primaryButton: {
    minHeight: 40,
    border: "1px solid rgba(229,190,124,0.24)",
    borderRadius: 8,
    background: actionPalette.primaryBackground,
    color: "rgba(255,250,236,0.96)",
    fontWeight: 850,
    cursor: "pointer",
    boxShadow: actionPalette.primaryShadow,
  },
  secondaryButton: {
    minHeight: 40,
    border: "1px solid rgba(229,190,124,0.22)",
    borderRadius: 8,
    background: "rgba(32,28,21,0.72)",
    color: actionPalette.ivoryText,
    fontWeight: 820,
    cursor: "pointer",
  },
  quietButton: {
    minHeight: 40,
    border: "1px solid rgba(229,190,124,0.14)",
    borderRadius: 8,
    background: "rgba(255,255,255,0.03)",
    color: actionPalette.mutedIvory,
    fontWeight: 760,
    cursor: "pointer",
  },
  motivePanel: {
    display: "grid",
    gap: 8,
  },
  motiveLabel: {
    color: actionPalette.mutedIvory,
    fontSize: 13,
    fontWeight: 740,
  },
  motiveInput: {
    width: "100%",
    boxSizing: "border-box",
    resize: "vertical",
    minHeight: 68,
    borderRadius: 8,
    border: "1px solid rgba(229,190,124,0.18)",
    background: "rgba(0,0,0,0.25)",
    color: actionPalette.ivoryText,
    padding: 10,
    font: "inherit",
  },
  pendingStack: {
    display: "grid",
    gap: 10,
  },
  receiptPanel: {
    border: "1px solid rgba(229,190,124,0.17)",
    background: "rgba(13,14,15,0.86)",
    padding: 14,
    borderRadius: 8,
    display: "grid",
    gap: 6,
  },
  receiptTitle: {
    color: actionPalette.ivoryText,
    fontFamily: "var(--font-narrative)",
    fontSize: 20,
  },
  receiptMotive: {
    color: actionPalette.mutedIvory,
    fontSize: 13,
  },
  reactionPanel: {
    border: "1px solid rgba(229,190,124,0.18)",
    background: "linear-gradient(135deg, rgba(34,27,18,0.62), rgba(8,9,10,0.82))",
    padding: 16,
    borderRadius: 8,
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    gap: 12,
    alignItems: "center",
  },
  reactionPulse: {
    width: 12,
    height: 42,
    borderRadius: 999,
    background: "linear-gradient(180deg, rgba(231,184,98,0.88), rgba(231,184,98,0.18))",
    boxShadow: "0 0 28px rgba(231,184,98,0.24)",
  },
  reactionTitle: {
    color: actionPalette.ivoryText,
    fontSize: 18,
    fontFamily: "var(--font-narrative)",
  },
  reactionCopy: {
    margin: "5px 0 0",
    color: actionPalette.mutedIvory,
    lineHeight: 1.45,
  },
  resolvedPanel: {
    border: "1px solid rgba(126,204,164,0.18)",
    background: "rgba(10,17,14,0.70)",
    padding: 12,
    borderRadius: 8,
    display: "grid",
    gap: 10,
  },
  rail: {
    minWidth: 0,
    display: "grid",
    gap: 12,
  },
  railSection: {
    border: "1px solid rgba(229,190,124,0.14)",
    background: "rgba(10,11,12,0.78)",
    borderRadius: 8,
    padding: 12,
    display: "grid",
    gap: 10,
  },
  personList: {
    display: "grid",
    gap: 8,
  },
  personRow: {
    minWidth: 0,
    display: "grid",
    gridTemplateColumns: "42px minmax(0, 1fr) max-content",
    gap: 10,
    alignItems: "center",
    border: "1px solid rgba(229,190,124,0.10)",
    background: "rgba(255,255,255,0.025)",
    borderRadius: 8,
    padding: 8,
  },
  personRowConsulted: {
    borderColor: "rgba(229,190,124,0.26)",
    background: "rgba(64,46,21,0.20)",
  },
  avatarFrame: {
    width: 42,
    height: 42,
    display: "grid",
    placeItems: "center",
    color: actionPalette.ivoryText,
    fontWeight: 850,
    border: "1px solid rgba(229,190,124,0.18)",
    background: "rgba(0,0,0,0.24)",
    borderRadius: 6,
  },
  personText: {
    minWidth: 0,
    display: "grid",
    gap: 2,
  },
  personName: {
    color: actionPalette.ivoryText,
    fontSize: 13.5,
  },
  personRole: {
    color: actionPalette.amberText,
    fontSize: 11.5,
    fontWeight: 740,
  },
  personState: {
    color: actionPalette.faintIvory,
    fontSize: 11.5,
    lineHeight: 1.25,
  },
  personAction: {
    border: "1px solid rgba(229,190,124,0.18)",
    borderRadius: 6,
    background: "rgba(255,255,255,0.04)",
    color: actionPalette.mutedIvory,
    padding: "6px 8px",
    cursor: "pointer",
    fontWeight: 780,
  },
  personActionActive: {
    borderColor: "rgba(229,190,124,0.36)",
    background: "rgba(229,190,124,0.14)",
    color: actionPalette.ivoryText,
  },
  personAdvice: {
    border: "1px solid rgba(229,190,124,0.18)",
    borderRadius: 8,
    background: "linear-gradient(145deg, rgba(36,29,18,0.58), rgba(8,9,10,0.76))",
    padding: 12,
    display: "grid",
    gap: 5,
  },
  personAdviceTitle: {
    color: actionPalette.ivoryText,
    fontFamily: "var(--font-narrative)",
    fontSize: 17,
    lineHeight: 1.2,
  },
  personAdviceBody: {
    color: actionPalette.mutedIvory,
    fontSize: 12.5,
    lineHeight: 1.38,
  },
  clueCard: {
    border: "1px solid rgba(229,190,124,0.14)",
    borderRadius: 8,
    padding: 12,
    display: "grid",
    gap: 5,
  },
  clueCardLocked: {
    background: "rgba(255,255,255,0.025)",
    opacity: 0.72,
  },
  clueCardUnlocked: {
    background: "linear-gradient(145deg, rgba(61,45,21,0.54), rgba(11,12,12,0.78))",
    boxShadow: "0 14px 34px rgba(0,0,0,0.22)",
  },
  clueStatus: {
    color: actionPalette.amberText,
    fontSize: 11,
    fontWeight: 760,
  },
  clueTitle: {
    color: actionPalette.ivoryText,
    fontFamily: "var(--font-narrative)",
    fontSize: 17,
  },
  clueBody: {
    color: actionPalette.mutedIvory,
    fontSize: 12.5,
    lineHeight: 1.35,
  },
}
