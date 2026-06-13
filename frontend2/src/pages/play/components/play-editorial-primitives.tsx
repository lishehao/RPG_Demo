import { type CSSProperties, type ReactNode, type RefObject, type SyntheticEvent } from "react"
import type {
  NarrativeNPCPulse,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
} from "../../../api/contracts"
import {
  getAvatarForCastMember,
  getDefaultAvatar,
} from "../../../shared/lib/webtoon-assets"
import { useT } from "../../../shared/lib/i18n"
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
  const progress = `Turn ${turnsCompleted} of ${turnBudget}`
  const stage = turnsRemaining <= 2 ? "Coda" : turnsCompleted <= 0 ? "Opening" : "In motion"
  const context = turnsCompleted <= 0
    ? "First shot is live. Choose the pressure you step into."
    : turnsRemaining <= 2
      ? "The room is close to its final break."
      : "The latest beat is ready for your next move."

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
        <h1 style={{ ...primitiveStyles.moodTitle, ...(compact ? primitiveStyles.moodTitleCompact : null) }}>
          {story.template.title}
        </h1>
        <div style={primitiveStyles.moodDeck}>
          <Truncated lines={1}>{context}</Truncated>
        </div>
        <div style={primitiveStyles.moodMetaRow}>
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
  compact,
  advisorAvatarUrl,
  advisorPersona,
  onAskAdvisor,
}: {
  story: NarrativeStoryHistoryResponse
  lastNarrator: NarrativeStoryMessage | null
  compact: boolean
  advisorAvatarUrl: string
  advisorPersona: string
  onAskAdvisor: () => void
}) {
  const t = useT()
  const playerRole = story.session.player_role
  const role = playerRole?.label || playerRole?.public_persona || "You"
  const playerPortraitUrl = playerPortraitForStory(story)
  const pressure = scenePressureText(story, lastNarrator)
  const actors = sceneActors(story, lastNarrator?.npc_pulse ?? [])
  const advisorName = advisorDisplayName(advisorPersona, t("play.advisor_card_name"))
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
        <div style={primitiveStyles.playerIdentityRow}>
          <span style={primitiveStyles.playerPortraitFrame}>
            <img
              data-play-player-portrait="true"
              src={playerPortraitUrl}
              alt=""
              style={primitiveStyles.portraitImage}
              onError={handlePortraitError}
            />
          </span>
          <span style={primitiveStyles.playerIdentityText}>
            <strong style={primitiveStyles.roleTitle}>{role}</strong>
            {playerRole?.public_persona && playerRole.public_persona !== role ? (
              <span style={primitiveStyles.roleDetail}>{playerRole.public_persona}</span>
            ) : null}
          </span>
        </div>
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
              <span style={primitiveStyles.actorFrame}>
                <img
                  data-play-cast-portrait="true"
                  src={actor.avatarUrl}
                  alt=""
                  style={primitiveStyles.portraitImage}
                  onError={handlePortraitError}
                />
              </span>
              <span style={primitiveStyles.actorText}>
                <strong style={primitiveStyles.actorName}>{actor.name}</strong>
                <span style={primitiveStyles.actorRole}>{actor.role}</span>
              </span>
            </div>
          ))}
        </div>
      </PrimitiveSection>
      <PrimitiveSection title={t("play.advisor_card_title")}>
        <div
          style={{
            ...primitiveStyles.advisorCard,
            ...(compact ? primitiveStyles.advisorCardCompact : null),
          }}
          data-play-advisor-card="true"
        >
          <span style={primitiveStyles.advisorFrame}>
            <img
              data-play-advisor-portrait="true"
              src={advisorAvatarUrl}
              alt=""
              style={primitiveStyles.portraitImage}
              onError={handlePortraitError}
            />
          </span>
          <span style={primitiveStyles.advisorText}>
            <strong style={primitiveStyles.advisorName}>{advisorName}</strong>
            <span style={primitiveStyles.advisorRole}>{t("play.advisor_card_role")}</span>
            <span style={primitiveStyles.advisorBackground}>
              <Truncated lines={2}>{t("play.advisor_card_background")}</Truncated>
            </span>
            <button
              type="button"
              style={primitiveStyles.advisorAskButton}
              data-play-advisor-ask="true"
              title={t("play.advisor_card_ask_title", { name: advisorName })}
              aria-label={`${t("play.advisor_card_ask_title", { name: advisorName })}: ${advisorPersona}`}
              onClick={onAskAdvisor}
            >
              {t("play.advisor_card_ask")}
            </button>
          </span>
        </div>
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

function advisorDisplayName(persona: string, fallback: string): string {
  const firstClause = persona
    .split(/[,.。；;:：—-]/)[0]
    .replace(/\s+/g, " ")
    .trim()
  if (firstClause.length >= 2 && firstClause.length <= 32) {
    return firstClause
  }
  return fallback
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
    .slice(0, 3)
    .map((member) => ({
      id: member.character_id,
      name: member.display_name,
      role: member.role || member.relation_to_protagonist || "Scene actor",
      avatarUrl: getAvatarForCastMember(story.template.template_id, member, story.template),
    }))
}

function playerPortraitForStory(story: NarrativeStoryHistoryResponse): string {
  const playerRole = story.session.player_role
  const roleText = `${playerRole?.label ?? ""} ${playerRole?.public_persona ?? ""}`.trim()
  const roleNeedle = roleText.toLowerCase()
  const matchedCast = roleNeedle
    ? story.template.cast.find((member) =>
        [
          member.character_id,
          member.display_name,
          member.role,
          member.relation_to_protagonist,
        ]
          .filter(Boolean)
          .some((value) => {
            const normalized = value.toLowerCase()
            return roleNeedle.includes(normalized) || normalized.includes(roleNeedle)
          }),
      )
    : null
  if (matchedCast) return getAvatarForCastMember(story.template.template_id, matchedCast, story.template)
  return getAvatarForCastMember(
    story.template.template_id,
    {
      character_id: playerRole?.role_id || "player",
      display_name: roleText || "Player",
      role: roleText || "Player",
      relation_to_protagonist: playerRole?.public_persona || "",
    },
    story.template,
  )
}

function handlePortraitError(event: SyntheticEvent<HTMLImageElement>) {
  const image = event.currentTarget
  if (image.dataset.portraitFallback === "true") return
  image.dataset.portraitFallback = "true"
  image.src = getDefaultAvatar()
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
  playerIdentityRow: {
    display: "grid",
    gridTemplateColumns: "58px minmax(0, 1fr)",
    gap: 11,
    alignItems: "center",
  },
  playerIdentityText: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  playerPortraitFrame: {
    width: 58,
    aspectRatio: "4 / 5",
    display: "block",
    overflow: "hidden",
    border: "1px solid rgba(245,200,120,0.48)",
    borderTop: "2px solid rgba(245,200,120,0.82)",
    background: "linear-gradient(135deg, rgba(245,200,120,0.16), rgba(112,24,28,0.36))",
    boxShadow: "0 12px 24px rgba(0,0,0,0.32)",
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
    gridTemplateColumns: "44px minmax(0, 1fr)",
    gap: 9,
    alignItems: "center",
  },
  actorFrame: {
    width: 44,
    aspectRatio: "4 / 5",
    border: "1px solid rgba(245,200,120,0.36)",
    borderTop: "2px solid rgba(245,200,120,0.70)",
    background: "linear-gradient(135deg, rgba(245,200,120,0.16), rgba(112,24,28,0.36))",
    display: "block",
    overflow: "hidden",
    boxShadow: "0 8px 16px rgba(0,0,0,0.24)",
  },
  portraitImage: {
    width: "100%",
    height: "100%",
    display: "block",
    objectFit: "cover",
    objectPosition: "center top",
    filter: "saturate(0.98) contrast(1.04)",
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
  advisorCard: {
    display: "grid",
    gridTemplateColumns: "54px minmax(0, 1fr)",
    gap: 10,
    alignItems: "start",
    padding: "8px 8px 9px",
    borderTop: "1px solid rgba(229,190,124,0.18)",
    borderRight: "1px solid rgba(229,190,124,0.09)",
    borderBottom: "1px solid rgba(229,190,124,0.13)",
    borderLeft: "1px solid rgba(213,154,62,0.30)",
    borderRadius: 5,
    background: "linear-gradient(145deg, rgba(28,27,24,0.88), rgba(8,9,10,0.92))",
    boxShadow: "0 12px 24px rgba(0,0,0,0.20), inset 0 1px 0 rgba(250,238,210,0.08)",
  },
  advisorCardCompact: {
    gridTemplateColumns: "48px minmax(0, 1fr)",
  },
  advisorFrame: {
    width: 54,
    aspectRatio: "4 / 5",
    display: "block",
    overflow: "hidden",
    border: "1px solid rgba(229,190,124,0.46)",
    borderTop: "2px solid rgba(230,170,76,0.76)",
    background: "linear-gradient(135deg, rgba(213,154,62,0.18), rgba(18,19,19,0.54))",
    boxShadow: "0 10px 18px rgba(0,0,0,0.28)",
  },
  advisorText: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: 3,
  },
  advisorName: {
    color: "rgba(255,246,232,0.96)",
    fontFamily: "var(--font-narrative)",
    fontSize: 15.5,
    lineHeight: 1.12,
    fontWeight: 560,
  },
  advisorRole: {
    color: "rgba(230,170,76,0.84)",
    fontSize: 11.5,
    lineHeight: 1.2,
    fontWeight: 760,
  },
  advisorBackground: {
    color: "rgba(244,239,230,0.62)",
    fontSize: 11.4,
    lineHeight: 1.32,
  },
  advisorAskButton: {
    width: "fit-content",
    marginTop: 4,
    minHeight: 28,
    padding: "5px 10px",
    borderTop: "1px solid rgba(250,226,180,0.28)",
    borderRight: "1px solid rgba(214,157,62,0.24)",
    borderBottom: "1px solid rgba(162,106,37,0.28)",
    borderLeft: "1px solid rgba(214,157,62,0.30)",
    borderRadius: 4,
    background: "linear-gradient(180deg, rgba(70,52,30,0.84), rgba(22,22,20,0.92))",
    color: "rgba(246,239,222,0.94)",
    boxShadow: "0 8px 18px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,238,198,0.10)",
    fontFamily: "inherit",
    fontSize: 12,
    fontWeight: 820,
    lineHeight: 1.2,
    cursor: "pointer",
  },
  progressLine: {
    color: "rgba(244,239,230,0.72)",
    fontSize: 12.5,
  },
}
