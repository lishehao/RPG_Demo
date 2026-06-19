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
  isComplete = false,
}: {
  story: NarrativeStoryHistoryResponse
  coverUrl: string
  sceneUrl?: string
  turnsCompleted: number
  turnBudget: number
  turnsRemaining: number
  compact: boolean
  isComplete?: boolean
}) {
  const imageUrl = sceneUrl || coverUrl
  const progress = `Turn ${turnsCompleted} of ${turnBudget}`
  const stage = isComplete ? "Complete" : turnsRemaining <= 2 ? "Coda" : turnsCompleted <= 0 ? "Opening" : "In motion"
  const context = isComplete
    ? "This run is finished. Review the ending, then replay or share it."
    : turnsCompleted <= 0
    ? "First shot is live. Choose the pressure you step into."
    : turnsRemaining <= 2
      ? "The room is close to its final break."
      : "The room is waiting."

  return (
    <section
      data-play-primitive="MoodPlate"
      data-play-mood-state={isComplete ? "complete" : "active"}
      style={{
        ...primitiveStyles.moodPlate,
        ...(compact ? primitiveStyles.moodPlateCompact : null),
        ...(isComplete ? primitiveStyles.moodPlateComplete : null),
      }}
    >
      {!isComplete ? (
        <>
          <div
            aria-hidden
            style={{
              ...primitiveStyles.moodPlateImage,
              backgroundImage: `linear-gradient(90deg, rgba(12,12,16,0.98) 0%, rgba(12,12,16,0.72) 42%, rgba(12,12,16,0.18) 100%), linear-gradient(180deg, rgba(12,12,16,0.18) 0%, rgba(12,12,16,0.78) 100%), url(${imageUrl})`,
            }}
          />
          <div style={primitiveStyles.moodPlateRule} aria-hidden />
        </>
      ) : null}
      <div
        style={{
          ...primitiveStyles.moodPlateCopy,
          ...(isComplete ? primitiveStyles.moodPlateCopyComplete : null),
        }}
      >
        <h1
          style={{
            ...primitiveStyles.moodTitle,
            ...(compact ? primitiveStyles.moodTitleCompact : null),
            ...(isComplete ? primitiveStyles.moodTitleComplete : null),
          }}
        >
          {story.template.title}
        </h1>
        <div
          style={{
            ...primitiveStyles.moodDeck,
            ...(isComplete ? primitiveStyles.moodDeckComplete : null),
          }}
        >
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
  focusedActorId,
  actorActionCounts,
  onFocusActor,
  onAskAdvisor,
}: {
  story: NarrativeStoryHistoryResponse
  lastNarrator: NarrativeStoryMessage | null
  compact: boolean
  advisorAvatarUrl: string
  advisorPersona: string
  focusedActorId?: string | null
  actorActionCounts?: Record<string, number>
  onFocusActor?: (actor: { id: string; name: string }) => void
  onAskAdvisor: () => void
}) {
  const t = useT()
  const playerRole = story.session.player_role
  const role = playerRole?.label || playerRole?.public_persona || "You"
  const playerPortraitUrl = playerPortraitForStory(story)
  const pressure = scenePressureText(story, lastNarrator)
  const actors = sceneActors(story, lastNarrator?.npc_pulse ?? [])
  const advisorName = advisorDisplayName(advisorPersona, t("play.advisor_card_name"))
  const advisorAskTitle = t("play.advisor_card_ask_title", { name: advisorName })
  const advisorAskDetail = t("play.advisor_card_ask_detail")
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
      <PrimitiveSection title="People you can involve">
        <div style={primitiveStyles.actorList}>
          {actors.map((actor) => {
            const focused = focusedActorId === actor.id
            const actionCount = actorActionCounts?.[actor.id] ?? 0
            const focusCue = focused
              ? actionCount === 1
                ? t("play.actor_focus_active_count_one")
                : actionCount > 1
                  ? t("play.actor_focus_active_count_many", { count: actionCount })
                  : t("play.actor_focus_active_none")
              : actionCount === 1
                ? t("play.actor_focus_cta_count_one")
                : actionCount > 1
                  ? t("play.actor_focus_cta_count_many", { count: actionCount })
                  : t("play.actor_focus_cta_none")
            return (
              <button
                key={actor.id}
                type="button"
                style={{
                  ...primitiveStyles.actorRow,
                  ...primitiveStyles.actorRowButton,
                  ...(focused ? primitiveStyles.actorRowFocused : null),
                }}
                data-play-cast-resource="true"
                data-play-cast-resource-id={actor.id}
                data-play-cast-focus={focused ? "true" : undefined}
                data-play-cast-action-count={actionCount}
                aria-pressed={focused}
                aria-label={`${actor.name}. ${actor.role}. ${focusCue}. ${t("play.actor_focus_title", { name: actor.name })}`}
                title={t("play.actor_focus_title", { name: actor.name })}
                onClick={() => onFocusActor?.({ id: actor.id, name: actor.name })}
              >
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
                  <span style={primitiveStyles.actorFocusCue} data-play-cast-focus-cue="true">
                    {focusCue}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
      </PrimitiveSection>
      <PrimitiveSection title={t("play.advisor_card_title")}>
        <div
          style={{
            ...primitiveStyles.advisorRow,
            ...(compact ? primitiveStyles.advisorRowCompact : null),
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
            <span style={primitiveStyles.advisorHeaderRow}>
              <strong style={primitiveStyles.advisorName}>{advisorName}</strong>
              <button
                type="button"
                style={{
                  ...primitiveStyles.advisorAskButton,
                  ...(compact ? primitiveStyles.advisorAskButtonCompact : null),
                }}
                data-play-advisor-ask="true"
                title={`${advisorAskTitle} · ${advisorAskDetail}`}
                aria-label={`${advisorAskTitle}: ${advisorAskDetail}. ${advisorPersona}`}
                onClick={onAskAdvisor}
              >
                {t("play.advisor_card_ask")}
              </button>
            </span>
            <span style={primitiveStyles.advisorRole}>{t("play.advisor_card_role")}</span>
            <span style={primitiveStyles.advisorBackground}>
              <Truncated lines={2}>{t("play.advisor_card_background")}</Truncated>
            </span>
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
    borderTopWidth: 1,
    borderTopStyle: "solid",
    borderTopColor: "rgba(212,168,83,0.50)",
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "rgba(212,168,83,0.25)",
    background: "rgba(12,12,16,0.82)",
    marginBottom: 16,
  },
  moodPlateCompact: {
    minHeight: 188,
    marginBottom: 12,
  },
  moodPlateComplete: {
    minHeight: 0,
    marginBottom: 12,
    overflow: "visible",
    background: "transparent",
    borderTopWidth: 1,
    borderTopStyle: "solid",
    borderTopColor: "rgba(212,168,83,0.24)",
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "rgba(255,255,255,0.07)",
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
  moodPlateCopyComplete: {
    width: "100%",
    padding: "13px 36px 14px",
    gap: 5,
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
  moodTitleComplete: {
    fontSize: 18,
    lineHeight: 1.25,
    fontWeight: 560,
    textShadow: "none",
    color: "rgba(255,246,232,0.94)",
  },
  moodDeck: {
    color: "rgba(244,239,230,0.78)",
    fontSize: 14.5,
    lineHeight: 1.55,
    maxWidth: 540,
  },
  moodDeckComplete: {
    color: "rgba(244,239,230,0.66)",
    fontSize: 13,
    maxWidth: "none",
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
    borderTopWidth: 1,
    borderTopStyle: "solid",
    borderTopColor: "rgba(212,168,83,0.48)",
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "rgba(255,255,255,0.06)",
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
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "rgba(245,200,120,0.12)",
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
    borderTopWidth: 2,
    borderTopStyle: "solid",
    borderTopColor: "rgba(245,200,120,0.82)",
    borderRightWidth: 1,
    borderRightStyle: "solid",
    borderRightColor: "rgba(245,200,120,0.48)",
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "rgba(245,200,120,0.48)",
    borderLeftWidth: 1,
    borderLeftStyle: "solid",
    borderLeftColor: "rgba(245,200,120,0.48)",
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
  actorRowButton: {
    width: "100%",
    minWidth: 0,
    padding: "2px 0",
    borderTopWidth: 0,
    borderTopStyle: "none",
    borderRightWidth: 0,
    borderRightStyle: "none",
    borderBottomWidth: 0,
    borderBottomStyle: "none",
    borderLeftWidth: 0,
    borderLeftStyle: "none",
    borderRadius: 0,
    background: "transparent",
    color: "inherit",
    font: "inherit",
    textAlign: "left",
    cursor: "pointer",
  },
  actorRowFocused: {
    background: "linear-gradient(90deg, rgba(213,154,62,0.12), transparent 70%)",
  },
  actorFrame: {
    width: 44,
    aspectRatio: "4 / 5",
    borderTopWidth: 2,
    borderTopStyle: "solid",
    borderTopColor: "rgba(245,200,120,0.70)",
    borderRightWidth: 1,
    borderRightStyle: "solid",
    borderRightColor: "rgba(245,200,120,0.36)",
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "rgba(245,200,120,0.36)",
    borderLeftWidth: 1,
    borderLeftStyle: "solid",
    borderLeftColor: "rgba(245,200,120,0.36)",
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
  actorFocusCue: {
    width: "fit-content",
    color: "rgba(229,190,124,0.72)",
    fontSize: 10.5,
    lineHeight: 1.15,
    fontWeight: 760,
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "rgba(229,190,124,0.20)",
  },
  advisorRow: {
    display: "grid",
    gridTemplateColumns: "44px minmax(0, 1fr)",
    gap: 9,
    alignItems: "center",
    padding: "2px 0",
    borderLeftWidth: 1,
    borderLeftStyle: "solid",
    borderLeftColor: "rgba(213,154,62,0.22)",
  },
  advisorRowCompact: {
    gridTemplateColumns: "44px minmax(0, 1fr)",
    alignItems: "start",
  },
  advisorFrame: {
    width: 44,
    aspectRatio: "4 / 5",
    display: "block",
    overflow: "hidden",
    borderTopWidth: 2,
    borderTopStyle: "solid",
    borderTopColor: "rgba(230,170,76,0.74)",
    borderRightWidth: 1,
    borderRightStyle: "solid",
    borderRightColor: "rgba(245,200,120,0.40)",
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "rgba(245,200,120,0.40)",
    borderLeftWidth: 1,
    borderLeftStyle: "solid",
    borderLeftColor: "rgba(245,200,120,0.40)",
    background: "linear-gradient(135deg, rgba(245,200,120,0.14), rgba(18,19,19,0.48))",
    boxShadow: "0 8px 16px rgba(0,0,0,0.24)",
  },
  advisorText: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  advisorHeaderRow: {
    minWidth: 0,
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) max-content",
    alignItems: "center",
    gap: 8,
  },
  advisorName: {
    minWidth: 0,
    color: "rgba(255,246,232,0.94)",
    fontSize: 13,
    lineHeight: 1.2,
    fontWeight: 680,
  },
  advisorRole: {
    color: "rgba(230,170,76,0.78)",
    fontSize: 11.5,
    lineHeight: 1.22,
    fontWeight: 760,
  },
  advisorBackground: {
    color: "rgba(244,239,230,0.52)",
    fontSize: 11.2,
    lineHeight: 1.25,
  },
  advisorAskButton: {
    justifySelf: "end",
    alignSelf: "center",
    width: "fit-content",
    minWidth: 38,
    maxWidth: 64,
    minHeight: 28,
    padding: "4px 9px",
    border: "1px solid rgba(229,190,124,0.22)",
    borderRadius: 4,
    background: "rgba(18,19,19,0.48)",
    color: "rgba(246,221,176,0.86)",
    boxShadow: "inset 0 1px 0 rgba(255,238,198,0.06)",
    fontFamily: "inherit",
    fontSize: 11.5,
    fontWeight: 820,
    lineHeight: 1.2,
    whiteSpace: "nowrap" as const,
    cursor: "pointer",
  },
  advisorAskButtonCompact: {
    minHeight: 26,
    padding: "3px 8px",
  },
  progressLine: {
    color: "rgba(244,239,230,0.72)",
    fontSize: 12.5,
  },
}
