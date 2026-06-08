import { type CSSProperties, type ReactNode, type RefObject } from "react"
import type {
  NarrativeNPCPulse,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
} from "../../../api/contracts"
import { Truncated } from "../../../shared/ui/truncated"

type PlayShellProps = {
  compact: boolean
  children: ReactNode
}

export function PlayShell({ compact, children }: PlayShellProps) {
  return (
    <main
      data-play-direction="editorial-primitive-kit"
      style={{
        ...primitiveStyles.shell,
        ...(compact ? primitiveStyles.shellCompact : null),
      }}
    >
      {children}
    </main>
  )
}

export function PlaySurfaceGrid({
  compact,
  children,
}: {
  compact: boolean
  children: ReactNode
}) {
  return (
    <section
      data-play-primitive="PlaySurfaceGrid"
      style={{
        ...primitiveStyles.surfaceGrid,
        ...(compact ? primitiveStyles.surfaceGridCompact : null),
      }}
    >
      {children}
    </section>
  )
}

export function StoryTimeline({
  innerRef,
  children,
}: {
  innerRef: RefObject<HTMLDivElement | null>
  children: ReactNode
}) {
  return (
    <div
      ref={innerRef}
      className="play-story-column"
      data-play-primitive="StoryTimeline"
      style={primitiveStyles.timeline}
    >
      {children}
    </div>
  )
}

export function MoodPlate({
  story,
  coverUrl,
  sceneUrl,
  turnsCompleted,
  turnBudget,
  turnsRemaining,
  compact,
}: {
  story: NarrativeStoryHistoryResponse
  coverUrl: string
  sceneUrl?: string
  turnsCompleted: number
  turnBudget: number
  turnsRemaining: number
  compact: boolean
}) {
  const imageUrl = sceneUrl || coverUrl
  const castLine = story.template.cast.map((member) => member.display_name).slice(0, 4).join(" · ")
  const roleLine = story.session.player_role?.label || story.session.player_role?.public_persona || "You"
  const progress = `${turnsCompleted}/${turnBudget}`
  const stage = turnsRemaining <= 2 ? "Final pressure" : turnsCompleted <= 0 ? "Opening beat" : "Scene in motion"

  return (
    <section
      data-play-primitive="MoodPlate"
      style={{
        ...primitiveStyles.moodPlate,
        ...(compact ? primitiveStyles.moodPlateCompact : null),
      }}
    >
      <div
        aria-hidden
        style={{
          ...primitiveStyles.moodPlateImage,
          backgroundImage: `linear-gradient(90deg, rgba(12,12,16,0.98) 0%, rgba(12,12,16,0.72) 42%, rgba(12,12,16,0.18) 100%), linear-gradient(180deg, rgba(12,12,16,0.18) 0%, rgba(12,12,16,0.78) 100%), url(${imageUrl})`,
        }}
      />
      <div style={primitiveStyles.moodPlateRule} aria-hidden />
      <div style={primitiveStyles.moodPlateCopy}>
        <span style={primitiveStyles.eyebrow}>Tiny Stories · Play</span>
        <h1 style={{ ...primitiveStyles.moodTitle, ...(compact ? primitiveStyles.moodTitleCompact : null) }}>
          {story.template.title}
        </h1>
        <div style={primitiveStyles.moodDeck}>
          <Truncated lines={2}>{story.template.seed}</Truncated>
        </div>
        <div style={primitiveStyles.moodMetaRow}>
          <span>{roleLine}</span>
          {castLine ? <span>{castLine}</span> : null}
          <span>{stage}</span>
          <span>{progress}</span>
        </div>
      </div>
    </section>
  )
}

export function SceneSupportRail({
  story,
  lastNarrator,
  turnsRemaining,
  compact,
}: {
  story: NarrativeStoryHistoryResponse
  lastNarrator: NarrativeStoryMessage | null
  turnsRemaining: number
  compact: boolean
}) {
  const playerRole = story.session.player_role
  const role = playerRole?.label || playerRole?.public_persona || "You"
  const pressure = scenePressureText(story, lastNarrator)
  const actors = sceneActors(story, lastNarrator?.npc_pulse ?? [])
  return (
    <aside
      data-play-primitive="SceneSupportRail"
      style={{
        ...primitiveStyles.supportRail,
        ...(compact ? primitiveStyles.supportRailCompact : null),
      }}
      aria-label="Scene support"
    >
      <PrimitiveSection title="You are">
        <strong style={primitiveStyles.roleTitle}>{role}</strong>
        {playerRole?.public_persona && playerRole.public_persona !== role ? (
          <span style={primitiveStyles.roleDetail}>{playerRole.public_persona}</span>
        ) : null}
      </PrimitiveSection>
      <PrimitiveSection title="Pressure now">
        <span style={primitiveStyles.pressureText}>
          <Truncated lines={3}>{pressure}</Truncated>
        </span>
      </PrimitiveSection>
      <PrimitiveSection title="In the room">
        <div style={primitiveStyles.actorList}>
          {actors.map((actor) => (
            <div key={actor.id} style={primitiveStyles.actorRow}>
              <span style={primitiveStyles.actorFrame} aria-hidden>{actor.initials}</span>
              <span style={primitiveStyles.actorText}>
                <strong style={primitiveStyles.actorName}>{actor.name}</strong>
                <span style={primitiveStyles.actorRole}>{actor.role}</span>
              </span>
            </div>
          ))}
        </div>
      </PrimitiveSection>
      <PrimitiveSection title="Progress">
        <span style={primitiveStyles.progressLine}>
          {story.session.turn_count} played · {turnsRemaining} left
        </span>
      </PrimitiveSection>
    </aside>
  )
}

function PrimitiveSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={primitiveStyles.supportSection}>
      <span style={primitiveStyles.supportTitle}>{title}</span>
      {children}
    </section>
  )
}

function scenePressureText(
  story: NarrativeStoryHistoryResponse,
  lastNarrator: NarrativeStoryMessage | null,
): string {
  const optionHint = lastNarrator?.options.find((option) => option.hint)?.hint
  if (optionHint) return optionHint
  if (lastNarrator?.content) {
    const firstSentence = lastNarrator.content.split(/(?<=[.!?。！？])\s+/)[0]
    if (firstSentence) return firstSentence
  }
  return story.template.seed
}

function sceneActors(story: NarrativeStoryHistoryResponse, pulses: NarrativeNPCPulse[]) {
  const pulseIds = pulses.map((pulse) => pulse.npc_id)
  const ordered = [
    ...pulseIds
      .map((id) => story.template.cast.find((member) => member.character_id === id))
      .filter((member): member is NarrativeStoryHistoryResponse["template"]["cast"][number] => Boolean(member)),
    ...story.template.cast,
  ]
  const seen = new Set<string>()
  return ordered
    .filter((member) => {
      if (seen.has(member.character_id)) return false
      seen.add(member.character_id)
      return true
    })
    .slice(0, 4)
    .map((member) => ({
      id: member.character_id,
      name: member.display_name,
      role: member.role || member.relation_to_protagonist || "Scene actor",
      initials: initialsFor(member.display_name),
    }))
}

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "?"
  if (/[\u3400-\u9fff]/.test(name)) return name.trim().slice(0, 1)
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("") || "?"
}

const primitiveStyles: Record<string, CSSProperties> = {
  shell: {
    width: "min(1180px, calc(100% - 48px))",
    margin: "0 auto",
    padding: "22px 0 76px",
  },
  shellCompact: {
    width: "100%",
    padding: "12px 12px 58px",
    boxSizing: "border-box",
  },
  moodPlate: {
    position: "relative",
    minHeight: 228,
    overflow: "hidden",
    borderTop: "1px solid rgba(212,168,83,0.50)",
    borderBottom: "1px solid rgba(212,168,83,0.25)",
    background: "rgba(12,12,16,0.82)",
    marginBottom: 16,
  },
  moodPlateCompact: {
    minHeight: 188,
    marginBottom: 12,
  },
  moodPlateImage: {
    position: "absolute",
    inset: 0,
    backgroundSize: "cover",
    backgroundPosition: "center",
    transform: "scale(1.015)",
  },
  moodPlateRule: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 1,
    background: "linear-gradient(90deg, transparent, rgba(245,200,120,0.85), transparent)",
  },
  moodPlateCopy: {
    position: "relative",
    zIndex: 1,
    width: "min(610px, 76%)",
    padding: "28px 36px 24px",
    display: "flex",
    flexDirection: "column",
    gap: 13,
  },
  eyebrow: {
    color: "rgba(245,200,120,0.88)",
    fontSize: 11,
    fontWeight: 760,
    letterSpacing: 0,
    textTransform: "none",
  },
  moodTitle: {
    margin: 0,
    color: "rgba(255,246,232,0.98)",
    fontFamily: "var(--font-narrative)",
    fontSize: 38,
    fontWeight: 450,
    lineHeight: 1.02,
    letterSpacing: 0,
    textShadow: "0 2px 32px rgba(0,0,0,0.66)",
  },
  moodTitleCompact: {
    fontSize: 28,
    lineHeight: 1.04,
  },
  moodDeck: {
    color: "rgba(244,239,230,0.78)",
    fontSize: 14.5,
    lineHeight: 1.55,
    maxWidth: 540,
  },
  moodMetaRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px 14px",
    color: "rgba(244,239,230,0.62)",
    fontSize: 12,
    lineHeight: 1.3,
  },
  surfaceGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) 286px",
    gap: 16,
    alignItems: "start",
  },
  surfaceGridCompact: {
    gridTemplateColumns: "1fr",
    gap: 12,
  },
  timeline: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  supportRail: {
    position: "sticky",
    top: 84,
    display: "flex",
    flexDirection: "column",
    gap: 0,
    borderTop: "1px solid rgba(212,168,83,0.48)",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    background: "linear-gradient(180deg, rgba(12,12,16,0.92), rgba(42,12,16,0.68))",
    boxShadow: "inset 1px 0 0 rgba(245,200,120,0.12)",
  },
  supportRailCompact: {
    position: "relative",
    top: "auto",
    display: "grid",
    gridTemplateColumns: "1fr",
    order: -1,
  },
  supportSection: {
    padding: "14px 14px 13px",
    borderBottom: "1px solid rgba(245,200,120,0.12)",
    display: "flex",
    flexDirection: "column",
    gap: 7,
  },
  supportTitle: {
    color: "rgba(245,200,120,0.74)",
    fontSize: 10.5,
    fontWeight: 760,
    letterSpacing: 0,
    textTransform: "none",
  },
  roleTitle: {
    color: "rgba(255,246,232,0.96)",
    fontFamily: "var(--font-narrative)",
    fontSize: 20,
    lineHeight: 1.14,
    fontWeight: 520,
  },
  roleDetail: {
    color: "rgba(244,239,230,0.68)",
    fontSize: 12.5,
    lineHeight: 1.42,
  },
  pressureText: {
    color: "rgba(244,239,230,0.76)",
    fontSize: 13,
    lineHeight: 1.46,
  },
  actorList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  actorRow: {
    display: "grid",
    gridTemplateColumns: "38px minmax(0, 1fr)",
    gap: 9,
    alignItems: "center",
  },
  actorFrame: {
    width: 38,
    aspectRatio: "1",
    border: "1px solid rgba(245,200,120,0.36)",
    background: "linear-gradient(135deg, rgba(245,200,120,0.16), rgba(112,24,28,0.36))",
    color: "rgba(245,200,120,0.92)",
    display: "grid",
    placeItems: "center",
    fontFamily: "var(--font-narrative)",
    fontSize: 15,
    lineHeight: 1,
  },
  actorText: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  actorName: {
    color: "rgba(255,246,232,0.94)",
    fontSize: 13,
    lineHeight: 1.2,
    fontWeight: 660,
  },
  actorRole: {
    color: "rgba(244,239,230,0.56)",
    fontSize: 11.5,
    lineHeight: 1.25,
  },
  progressLine: {
    color: "rgba(244,239,230,0.72)",
    fontSize: 12.5,
  },
}
