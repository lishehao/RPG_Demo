import { type CSSProperties, type ReactNode, useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import type {
  NarrativeSessionSummary,
  NarrativeTemplateSummary,
} from "../../api/contracts"
import { useApi } from "../../app/api-context"
import { useAuth } from "../../app/auth-context"
import { Header } from "../../shared/ui/header"
import { LoadingShim } from "../../shared/ui/loading-shim"
import { Truncated } from "../../shared/ui/truncated"
import {
  PAGE_BG,
  assignTemplateCovers,
  getCoverByStoryId,
  getEmptyPlazaImage,
} from "../../shared/lib/webtoon-assets"
import { friendlyError } from "../../shared/lib/friendly-error"
import { ENDING_LABEL_DISPLAY, useLanguage, useT } from "../../shared/lib/i18n"
import {
  getSessionDisplayTitle,
  getTemplateDisplaySummary,
  getTemplateDisplayTitle,
} from "../../shared/lib/localized-story-metadata"
import { itemTransition, itemVariants, tapPress, transitions } from "../../shared/lib/motion-presets"

type Tab = "plaza" | "my-templates"

type HomeStoryObjectKind =
  | "published_story"
  | "in_progress_run"
  | "completed_memory"
  | "draft_brief"
type HomeTileSpan = "feature-wide" | "feature-tall" | "feature-horizontal" | "dispatch" | "notice-wide"
type HomeTileArchetype =
  | "full_bleed_cinematic"
  | "framed_editorial"
type HomeTileAccentTone = "play" | "resume" | "memory" | "draft"
type HomeTileDeckMode = "premise" | "status" | "ending" | "brief"

type HomeTileCopy = {
  typeLabel: string
  primaryAction: string
  accentTone: HomeTileAccentTone
  deckMode: HomeTileDeckMode
}

type HomeStoryObjectView = {
  id: string
  kind: HomeStoryObjectKind
  title: string
  cover: string
  deck: string
  copy: HomeTileCopy
  metadata?: string[]
  themeKey?: string | null
  hasStrongCover: boolean
}

type HomeMosaicBase = {
  id: string
  kind: HomeStoryObjectKind
  title: string
  deck: string
  themeKey?: string | null
  hasStrongCover: boolean
}

type HomeMosaicTile<T> = T & {
  span: HomeTileSpan
  archetype: HomeTileArchetype
}

const HOME_MOSAIC_RHYTHM: readonly HomeTileSpan[] = [
  "feature-wide",
  "feature-tall",
  "dispatch",
  "feature-horizontal",
  "dispatch",
  "notice-wide",
  "feature-wide",
  "dispatch",
  "feature-horizontal",
  "feature-tall",
  "dispatch",
  "notice-wide",
]

export function homeTileSpanForItem(
  item: HomeMosaicBase,
  index: number,
  total: number,
  previousSpan?: HomeTileSpan,
  previousTheme?: string | null,
): HomeTileSpan {
  const rhythm =
    total <= 2
      ? (["feature-horizontal", "feature-horizontal"] as const)
      : total <= 6
        ? (["feature-wide", "feature-horizontal", "notice-wide", "dispatch", "feature-horizontal", "notice-wide"] as const)
        : HOME_MOSAIC_RHYTHM

  let span: HomeTileSpan = rhythm[index % rhythm.length]
  const longText = item.title.length > 42 || item.deck.length > 138

  if (item.kind === "in_progress_run") {
    span = "feature-horizontal"
  } else if (item.kind === "completed_memory") {
    span = "notice-wide"
  } else if (!item.hasStrongCover && (span === "feature-wide" || span === "feature-tall")) {
    span = "feature-horizontal"
  } else if (longText && span === "dispatch") {
    span = "notice-wide"
  } else if (item.kind === "published_story" && span === "feature-tall") {
    span = "feature-horizontal"
  }

  if (previousSpan === span && previousTheme && item.themeKey === previousTheme) {
    span = span === "dispatch" ? "feature-horizontal" : "dispatch"
  }

  return span
}

function assignHomeMosaicSpans<T extends HomeMosaicBase>(items: T[]): HomeMosaicTile<T>[] {
  let previousSpan: HomeTileSpan | undefined
  let previousTheme: string | null | undefined
  let previousArchetype: HomeTileArchetype | undefined
  let fullBleedCount = 0
  return items.map((item, index) => {
    const span = homeTileSpanForItem(item, index, items.length, previousSpan, previousTheme)
    const archetype = homeTileArchetypeForItem(item, span, fullBleedCount, previousArchetype)
    previousSpan = span
    previousTheme = item.themeKey
    previousArchetype = archetype
    if (archetype === "full_bleed_cinematic") fullBleedCount += 1
    return { ...item, span, archetype }
  })
}

export function homeTileArchetypeForItem(
  item: HomeMosaicBase,
  span: HomeTileSpan,
  fullBleedCount = 0,
  previousArchetype?: HomeTileArchetype,
): HomeTileArchetype {
  const canUseFullBleed =
    span === "feature-wide" &&
    item.hasStrongCover &&
    fullBleedCount < 2 &&
    previousArchetype !== "full_bleed_cinematic"

  if (canUseFullBleed) {
    return "full_bleed_cinematic"
  }
  return "framed_editorial"
}

export function getHomeTileCopy(
  kind: HomeStoryObjectKind,
  t: ReturnType<typeof useT>,
  state?: { isStarting?: boolean },
): HomeTileCopy {
  if (kind === "published_story") {
    return {
      typeLabel: t("home.published_label"),
      primaryAction: state?.isStarting ? t("home.card_starting") : t("home.card_action"),
      accentTone: "play",
      deckMode: "premise",
    }
  }
  if (kind === "in_progress_run") {
    return {
      typeLabel: t("home.run_label"),
      primaryAction: t("home.run_action"),
      accentTone: "resume",
      deckMode: "status",
    }
  }
  if (kind === "completed_memory") {
    return {
      typeLabel: t("home.memory_label"),
      primaryAction: t("home.memory_action"),
      accentTone: "memory",
      deckMode: "ending",
    }
  }
  return {
    typeLabel: t("home.draft_label"),
    primaryAction: t("home.draft_action"),
    accentTone: "draft",
    deckMode: "brief",
  }
}

function publishedStoryView(
  template: NarrativeTemplateSummary,
  cover: string,
  lang: "zh" | "en",
  t: ReturnType<typeof useT>,
  isStarting = false,
): HomeStoryObjectView {
  return {
    id: template.template_id,
    kind: "published_story",
    title: getTemplateDisplayTitle(template, lang),
    cover,
    deck: getTemplateDisplaySummary(template, lang),
    copy: getHomeTileCopy("published_story", t, { isStarting }),
    themeKey: template.cover_image_url ?? template.title,
    hasStrongCover: Boolean(cover),
  }
}

function normalizePlazaTemplateText(value: string | null | undefined): string {
  return (value ?? "").replace(/\s+/g, " ").trim().toLowerCase()
}

export function publicTemplateDisplayKey(template: NarrativeTemplateSummary): string {
  const title =
    template.title_i18n?.en ||
    template.title_i18n?.zh ||
    template.title
  const summary =
    template.summary_i18n?.en ||
    template.summary_i18n?.zh ||
    template.seed
  return [
    normalizePlazaTemplateText(title),
    normalizePlazaTemplateText(summary),
  ].join("::")
}

export function dedupePublicTemplatesForPlaza(
  templates: NarrativeTemplateSummary[],
): NarrativeTemplateSummary[] {
  const seen = new Set<string>()
  return templates.filter((template) => {
    const key = publicTemplateDisplayKey(template)
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function HomePage({
  onOpenCreate,
  onOpenPlay,
}: {
  onOpenCreate: () => void
  onOpenPlay: (sessionId: string) => void
}) {
  const api = useApi()
  const auth = useAuth()
  const t = useT()
  const { lang } = useLanguage()
  const compactHome = useCompactLayout()
  const [tab, setTab] = useState<Tab>("plaza")
  const [publicTemplates, setPublicTemplates] = useState<NarrativeTemplateSummary[] | null>(null)
  const [myTemplates, setMyTemplates] = useState<NarrativeTemplateSummary[] | null>(null)
  const [mySessions, setMySessions] = useState<NarrativeSessionSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [templateStartError, setTemplateStartError] = useState<string | null>(null)
  const [startingTemplateId, setStartingTemplateId] = useState<string | null>(null)
  const startingTemplateRef = useRef<string | null>(null)
  const showTemplateTabs = !auth.isAnonymous
  const activeTemplateTab: Tab = showTemplateTabs ? tab : "plaza"

  const handleStartPublishedTemplate = async (templateId: string) => {
    if (startingTemplateRef.current) return
    startingTemplateRef.current = templateId
    setStartingTemplateId(templateId)
    setTemplateStartError(null)
    try {
      const response = await api.startNarrativeSession(templateId)
      onOpenPlay(response.session.session_id)
    } catch (err) {
      setTemplateStartError(friendlyError(err, t("home.error_start_story")))
    } finally {
      startingTemplateRef.current = null
      setStartingTemplateId(null)
    }
  }

  useEffect(() => {
    let cancelled = false
    setError(null)
    api
      .listPublicNarrativeTemplates()
      .then((res) => {
        if (cancelled) return
        setPublicTemplates(dedupePublicTemplatesForPlaza(res.items))
      })
      .catch((err) => {
        if (cancelled) return
        setError(friendlyError(err, t("home.error_plaza")))
      })
    return () => {
      cancelled = true
    }
  }, [api, t])

  useEffect(() => {
    if (auth.loading || auth.isAnonymous) return
    let cancelled = false
    api
      .listMyNarrativeSessions()
      .then((res) => {
        if (cancelled) return
        setMySessions(res.items)
      })
      .catch(() => {
        if (cancelled) return
        setMySessions([])
      })
    api
      .listMyNarrativeTemplates()
      .then((res) => {
        if (cancelled) return
        setMyTemplates(res.items)
      })
      .catch(() => {
        if (cancelled) return
        setMyTemplates([])
      })
    return () => {
      cancelled = true
    }
  }, [api, auth.loading, auth.isAnonymous])

  return (
    <div style={hpStyles.page}>
      <Header onHome={() => {}} onCreate={onOpenCreate} createVariant="link" />

      <main style={{ ...hpStyles.main, ...(compactHome ? hpStyles.mainCompact : null) }}>
        {/* Webtoon-cinematic hero — full-bleed splash background, text
            left-aligned over a vertical fade. Style brief: like Naver
            webtoon / Solo Leveling landing — single sustained scene
            anchored by a serif title. Bullet list moved to a smaller
            "how it works" rail under plaza so the hero stays as a
            single dramatic beat. */}
        <motion.section
          style={{ ...hpStyles.hero, ...(compactHome ? hpStyles.heroCompact : null) }}
          initial="initial"
          animate="animate"
          transition={{ staggerChildren: 0.08, delayChildren: 0.05 }}
        >
          <div style={{ ...hpStyles.heroInner, ...(compactHome ? hpStyles.heroInnerCompact : null) }}>
            <motion.div
              variants={itemVariants}
              transition={itemTransition}
              style={{ ...hpStyles.heroTagline, ...(compactHome ? hpStyles.heroTaglineCompact : null) }}
            >
              {t("home.hero_tagline")}
            </motion.div>
            <motion.h1
              variants={itemVariants}
              transition={itemTransition}
              style={{ ...hpStyles.heroTitle, ...(compactHome ? hpStyles.heroTitleCompact : null) }}
            >
              {t("home.hero_title_l1")}
              <br />
              {t("home.hero_title_l2")}
            </motion.h1>
            <motion.div
              variants={itemVariants}
              transition={itemTransition}
              style={{ ...hpStyles.heroActions, ...(compactHome ? hpStyles.heroActionsCompact : null) }}
            >
              <motion.button
                style={hpStyles.heroPrimaryAction}
                onClick={onOpenCreate}
                type="button"
                whileHover={{ x: 2 }}
                whileTap={tapPress}
              >
                {t("home.cta_create")}
              </motion.button>
            </motion.div>
          </div>
        </motion.section>

        {/* My sessions split into in-progress + completed groups. Only
            shown when signed in and at least one exists. */}
        {!auth.isAnonymous && mySessions && mySessions.length > 0 ? (
          <MySessionsSection
            sessions={mySessions}
            compact={compactHome}
            onOpenPlay={onOpenPlay}
          />
        ) : null}

        <section style={{ ...hpStyles.section, ...(compactHome ? hpStyles.sectionCompact : null) }}>
          {showTemplateTabs ? (
            <div style={hpStyles.tabs} role="tablist">
              <button
                style={{ ...hpStyles.tab, ...(activeTemplateTab === "plaza" ? hpStyles.tabActive : {}) }}
                onClick={() => setTab("plaza")}
                type="button"
                role="tab"
                aria-selected={activeTemplateTab === "plaza"}
              >
                {t("home.tab_plaza")}
              </button>
              <button
                style={{
                  ...hpStyles.tab,
                  ...(activeTemplateTab === "my-templates" ? hpStyles.tabActive : {}),
                }}
                onClick={() => setTab("my-templates")}
                type="button"
                role="tab"
                aria-selected={activeTemplateTab === "my-templates"}
              >
                {t("home.tab_my")}
              </button>
            </div>
          ) : (
            <div style={hpStyles.plazaHeader}>
              <span style={hpStyles.plazaLabel}>{t("home.tab_plaza")}</span>
            </div>
          )}

          {templateStartError ? <div style={hpStyles.errorBox}>{templateStartError}</div> : null}

          {/* Cross-fade between plaza ↔ my-templates so switching feels
              like a sibling pivot, not a layout swap. mode="wait"
              keeps the height stable during the transition. */}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={activeTemplateTab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={transitions.snap}
            >
              {activeTemplateTab === "plaza" ? (
                <HomeEditorialMosaic
                  templates={publicTemplates}
                  error={error}
                  compact={compactHome}
                  lang={lang}
                  onStartTemplate={handleStartPublishedTemplate}
                  startingTemplateId={startingTemplateId}
                />
              ) : (
                <TemplateGrid
                  templates={myTemplates}
                  error={null}
                  emptyText={t("home.empty_my")}
                  compact={compactHome}
                  onStartTemplate={handleStartPublishedTemplate}
                  startingTemplateId={startingTemplateId}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </section>

        <footer style={hpStyles.footer}>
          <span style={hpStyles.footerBrand}>Tiny Stories</span>
          <span style={hpStyles.footerSep}>·</span>
          <a
            href="#/about"
            style={hpStyles.footerLink}
            onClick={(e) => {
              e.preventDefault()
              window.location.hash = "#/about"
            }}
          >
            {t("home.footer_about")}
          </a>
          <span style={hpStyles.footerSep}>·</span>
          <a
            href="#/portfolio"
            style={hpStyles.footerLink}
            onClick={(e) => {
              e.preventDefault()
              window.location.hash = "#/portfolio"
            }}
          >
            {t("home.footer_portfolio")}
          </a>
          <span style={hpStyles.footerSep}>·</span>
          <a
            href="mailto:hello@tinystories.app"
            style={hpStyles.footerLink}
          >
            {t("home.footer_contact")}
          </a>
        </footer>
      </main>
    </div>
  )
}

function useCompactLayout(query = "(max-width: 720px)") {
  const [compact, setCompact] = useState(false)
  useEffect(() => {
    if (typeof window === "undefined") return
    const media = window.matchMedia(query)
    const update = () => setCompact(media.matches)
    update()
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [query])
  return compact
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div style={hpStyles.sectionHeader}>
      <h2 style={hpStyles.sectionTitle}>{title}</h2>
    </div>
  )
}

function MySessionsSection({
  sessions,
  compact,
  onOpenPlay,
}: {
  sessions: NarrativeSessionSummary[]
  compact: boolean
  onOpenPlay: (sessionId: string) => void
}) {
  const t = useT()
  // Split: in-progress (no ending) above, completed (has ending) below.
  const inProgress = sessions.filter((s) => !s.ending_label)
  const completed = sessions.filter((s) => Boolean(s.ending_label))
  const primarySession = inProgress[0]
  const queuedSessions = inProgress.slice(1, 5)
  return (
    <>
      {inProgress.length > 0 ? (
        <section style={hpStyles.resumeSection}>
          <ContinueRunSpotlight
            session={primarySession}
            compact={compact}
            onClick={() => onOpenPlay(primarySession.session_id)}
          />
          {queuedSessions.length > 0 ? (
            <div style={hpStyles.resumeQueue} aria-label={t("home.more_in_progress")}>
              {queuedSessions.map((s, idx) => (
                <SessionCard
                  key={s.session_id}
                  session={s}
                  index={idx}
                  onClick={() => onOpenPlay(s.session_id)}
                />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
      {completed.length > 0 ? (
        <section style={hpStyles.section}>
          {/* Personal-archive header: title + accumulated count.
              Gives the user a sense of "this is mounting up." Without
              the count, every visit looks the same; with it, finishing
              a 7th run reads as crossing a threshold. */}
          <div style={hpStyles.archiveHeader}>
            <h2 style={hpStyles.sectionTitle}>{t("home.section_completed")}</h2>
            <span style={hpStyles.archiveCount}>
              {t("home.archive_count", { n: completed.length })}
            </span>
          </div>
          <div style={hpStyles.sessionRow}>
            {/* Chronological newest-first; reverse-index gives each
                entry a stable "#N" marker that increments as the user
                accumulates more runs. */}
            {completed.slice(0, 6).map((s, idx) => (
              <SessionCard
                key={s.session_id}
                session={s}
                index={idx}
                archiveNumber={completed.length - idx}
                onClick={() => onOpenPlay(s.session_id)}
              />
            ))}
          </div>
        </section>
      ) : null}
    </>
  )
}

function ContinueRunSpotlight({
  session,
  compact,
  onClick,
}: {
  session: NarrativeSessionSummary
  compact: boolean
  onClick: () => void
}) {
  const t = useT()
  const { lang } = useLanguage()
  const displayTitle = getSessionDisplayTitle(session, lang)
  const safeBudget = Math.max(session.turn_budget, 1)
  const turnsPlayed = Math.min(Math.max(session.turn_count, 0), safeBudget)
  const progress = Math.min(1, Math.max(0, turnsPlayed / safeBudget))
  const roleLabel = session.player_role?.label ? t("home.resume_role", { role: session.player_role.label }) : null
  const copy = getHomeTileCopy("in_progress_run", t)
  return (
    <motion.button
      data-home-story-object-kind="in-progress-run"
      style={{ ...hpStyles.resumeButton, ...(compact ? hpStyles.resumeButtonCompact : null) }}
      onClick={onClick}
      type="button"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={itemTransition}
      whileHover={{ x: 2 }}
      whileTap={tapPress}
    >
      <div style={hpStyles.resumeCopy}>
        <span style={hpStyles.resumeKicker}>{copy.typeLabel}</span>
        <Truncated lines={2} style={hpStyles.resumeTitle}>{displayTitle}</Truncated>
        <div style={hpStyles.resumeMeta}>
          {t("home.session_progress_meta", {
            current: turnsPlayed,
            total: session.turn_budget,
          })}
          {" · "}
          {formatRelative(session.last_active_at, t)}
          {roleLabel ? ` · ${roleLabel}` : ""}
        </div>
      </div>
      <div style={hpStyles.resumeProgress} aria-hidden>
        <span style={{ ...hpStyles.resumeProgressFill, width: `${progress * 100}%` }} />
      </div>
      <span style={{ ...hpStyles.resumeCta, ...(compact ? hpStyles.resumeCtaCompact : null) }}>
        {copy.primaryAction}
      </span>
    </motion.button>
  )
}

function SessionCard({
  session,
  onClick,
  index = 0,
  archiveNumber,
}: {
  session: NarrativeSessionSummary
  onClick: () => void
  index?: number
  /** When set, render the card as an archive entry — "#N" marker
   *  in the corner + tier-colored ending chip. Only completed runs
   *  receive this. */
  archiveNumber?: number
}) {
  const { lang } = useLanguage()
  const t = useT()
  const displayTitle = getSessionDisplayTitle(session, lang)
  const completed = Boolean(session.ending_label)
  const copy = getHomeTileCopy(completed ? "completed_memory" : "in_progress_run", t)
  const safeBudget = Math.max(session.turn_budget, 1)
  const turnsPlayed = Math.min(Math.max(session.turn_count, 0), safeBudget)
  const endingLabelDisplay = session.ending_label
    ? ENDING_LABEL_DISPLAY[lang]?.[session.ending_label] ?? session.ending_label
    : null
  // Tier drives the chip's color treatment so "Vengeance" reads
  // visually different from "Sink" — finished-runs grid becomes a
  // legible archive instead of a wall of identical pills.
  const tierChipStyle: CSSProperties =
    session.ending_tier === "victory"
      ? hpStyles.endingChipVictory
      : session.ending_tier === "collapsed"
        ? hpStyles.endingChipCollapsed
        : hpStyles.endingChipCompromised
  const tierGlyph =
    session.ending_tier === "victory"
      ? "✦"
      : session.ending_tier === "collapsed"
        ? "✕"
        : "◇"
  return (
    <motion.button
      data-home-story-object-kind={completed ? "completed-memory" : "in-progress-run"}
      style={{
        ...hpStyles.sessionCard,
        ...(archiveNumber != null ? hpStyles.sessionCardArchive : null),
      }}
      onClick={onClick}
      type="button"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, ...itemTransition }}
      whileHover={{ x: 2 }}
      whileTap={tapPress}
    >
      {archiveNumber != null ? (
        <span style={hpStyles.archiveBadge} aria-hidden>
          #{archiveNumber}
        </span>
      ) : null}
      <span style={hpStyles.sessionObjectLabel}>{copy.typeLabel}</span>
      <Truncated style={hpStyles.sessionTitle}>{displayTitle}</Truncated>
      {completed ? (
        <>
          <div style={hpStyles.sessionEndingLine}>
            <span style={{ ...hpStyles.sessionEndingLabel, ...tierChipStyle }}>
              <span style={hpStyles.endingChipGlyph} aria-hidden>{tierGlyph}</span>
              {endingLabelDisplay}
            </span>
            <Truncated style={hpStyles.sessionEndingSubtitle}>
              {`「${session.ending_subtitle ?? ""}」`}
            </Truncated>
          </div>
          <div style={hpStyles.sessionMeta}>
            {t("home.session_completed_meta")} · {formatRelative(session.last_active_at, t)} ·{" "}
            <span style={hpStyles.sessionAction}>{copy.primaryAction}</span>
          </div>
        </>
      ) : (
        <div style={hpStyles.sessionMeta}>
          {t("home.session_progress_meta", {
            current: turnsPlayed,
            total: session.turn_budget,
          })}{" "}
          · {formatRelative(session.last_active_at, t)} ·{" "}
          <span style={hpStyles.sessionAction}>{copy.primaryAction}</span>
        </div>
      )}
    </motion.button>
  )
}

function TemplateGrid({
  templates,
  error,
  emptyText,
  compact,
  onStartTemplate,
  startingTemplateId,
  hideEmpty = false,
}: {
  templates: NarrativeTemplateSummary[] | null
  error: string | null
  emptyText: string
  compact: boolean
  onStartTemplate: (templateId: string) => void
  startingTemplateId: string | null
  hideEmpty?: boolean
}) {
  const t = useT()
  const { lang } = useLanguage()
  if (error) {
    return <div style={hpStyles.errorBox}>{error}</div>
  }
  if (!templates) {
    return <LoadingShim variant="inline" />
  }
  if (templates.length === 0) {
    if (hideEmpty) return null
    return (
      <motion.div
        style={hpStyles.emptyCard}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={itemTransition}
      >
        <div
          style={{
            ...hpStyles.emptyHero,
            backgroundImage: `linear-gradient(180deg, rgba(20,16,12,0.05) 0%, rgba(20,16,12,0.55) 75%, var(--bg-elev) 100%), url(${getEmptyPlazaImage()})`,
          }}
        />
        <div style={hpStyles.emptyBody}>{emptyText}</div>
      </motion.div>
    )
  }
  const assignedCovers = assignTemplateCovers(templates)
  const assignedTiles = assignHomeMosaicSpans(templates.map((template) => ({
    ...publishedStoryView(
      template,
      assignedCovers[template.template_id],
      lang,
      t,
      startingTemplateId === template.template_id,
    ),
    id: template.template_id,
    kind: "published_story" as const,
    template,
  })))
  return (
    <div
      style={{ ...hpStyles.editorialMosaic, ...(compact ? hpStyles.editorialMosaicCompact : null) }}
      data-home-editorial-mosaic="true"
    >
      {assignedTiles.map((tile, idx) => (
        <TemplateCard
          key={tile.template.template_id}
          template={tile.template}
          view={tile}
          span={tile.span}
          archetype={tile.archetype}
          index={idx}
          compact={compact}
          isStarting={startingTemplateId === tile.template.template_id}
          onClick={() => onStartTemplate(tile.template.template_id)}
        />
      ))}
    </div>
  )
}

function HomeEditorialMosaic({
  templates,
  error,
  compact,
  lang,
  onStartTemplate,
  startingTemplateId,
}: {
  templates: NarrativeTemplateSummary[] | null
  error: string | null
  compact: boolean
  lang: "zh" | "en"
  onStartTemplate: (templateId: string) => void
  startingTemplateId: string | null
}) {
  const t = useT()
  if (error) {
    return <div style={hpStyles.errorBox}>{error}</div>
  }
  if (!templates) {
    return <LoadingShim variant="inline" />
  }
  if (templates.length === 0) {
    return (
      <motion.div
        style={hpStyles.emptyCard}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={itemTransition}
      >
        <div
          style={{
            ...hpStyles.emptyHero,
            backgroundImage: `linear-gradient(180deg, rgba(20,16,12,0.05) 0%, rgba(20,16,12,0.55) 75%, var(--bg-elev) 100%), url(${getEmptyPlazaImage()})`,
          }}
        />
        <div style={hpStyles.emptyBody}>{t("home.empty_plaza")}</div>
      </motion.div>
    )
  }
  const assignedCovers = templates ? assignTemplateCovers(templates) : {}
  const items = assignHomeMosaicSpans(
    templates.map((template) => ({
      ...publishedStoryView(
        template,
        assignedCovers[template.template_id],
        lang,
        t,
        startingTemplateId === template.template_id,
      ),
      id: template.template_id,
      kind: "published_story" as const,
      template,
    })),
  )

  return (
    <div
      style={{ ...hpStyles.editorialMosaic, ...(compact ? hpStyles.editorialMosaicCompact : null) }}
      data-home-editorial-mosaic="true"
    >
      {items.map((item, idx) => (
        <TemplateCard
          key={item.id}
          template={item.template}
          view={item}
          span={item.span}
          archetype={item.archetype}
          compact={compact}
          index={idx}
          isStarting={startingTemplateId === item.template.template_id}
          onClick={() => onStartTemplate(item.template.template_id)}
        />
      ))}
    </div>
  )
}

function TemplateCard({
  template,
  view,
  span,
  archetype,
  onClick,
  index = 0,
  compact,
  isStarting = false,
}: {
  template: NarrativeTemplateSummary
  view?: HomeStoryObjectView
  span: HomeTileSpan
  archetype: HomeTileArchetype
  onClick: () => void
  index?: number
  compact: boolean
  isStarting?: boolean
}) {
  const t = useT()
  const { lang } = useLanguage()
  const displayView = view ?? publishedStoryView(template, getCoverByStoryId(template.template_id, template.title), lang, t, isStarting)
  return (
    <motion.button
      data-story-card-kind="published-story"
      data-home-tile-span={span}
      data-home-tile-archetype={archetype}
      aria-label={`${displayView.title} · ${displayView.deck} · ${displayView.copy.primaryAction}`}
      style={{
        ...hpStyles.editorialTile,
        ...hpStyles.editorialTilePublished,
        ...homeTileSpanStyle(span, compact),
      }}
      onClick={onClick}
      type="button"
      disabled={isStarting}
      aria-busy={isStarting}
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, ...itemTransition }}
      whileHover={{ x: 2 }}
      whileTap={tapPress}
    >
      <PublishedTileComposition
        archetype={archetype}
        span={span}
        compact={compact}
        view={displayView}
      />
    </motion.button>
  )
}

function PublishedTileComposition({
  archetype,
  span,
  compact,
  view,
}: {
  archetype: HomeTileArchetype
  span: HomeTileSpan
  compact: boolean
  view: HomeStoryObjectView
}) {
  const standardBody = <HomeTileTextBody view={view} span={span} compact={compact} />

  if (archetype === "full_bleed_cinematic") {
    return (
      <FullBleedTileImage cover={view.cover}>
        {standardBody}
      </FullBleedTileImage>
    )
  }
  return (
    <span style={framedTileLayoutStyle(span, compact)} data-home-framed-editorial="true">
      <TileMediaWell cover={view.cover} variant={tileMediaVariantForSpan(span, compact)} />
      <span style={framedTextPanelStyle(span, compact)}>{standardBody}</span>
    </span>
  )
}

function HomeTileTextBody({
  view,
  span,
  compact,
}: {
  view: HomeStoryObjectView
  span: HomeTileSpan
  compact: boolean
}) {
  const tightTile = span === "notice-wide" || span === "dispatch"
  return (
    <span data-home-tile-text-body="title-deck-action" style={hpStyles.tileLowInfoBody}>
      <TileTitle span={span} compact={compact} lines={tightTile ? 2 : 3}>{view.title}</TileTitle>
      <span
        style={{
          ...hpStyles.editorialTileDeck,
          ...(compact ? hpStyles.editorialTileDeckCompact : null),
        }}
      >
        {view.deck}
      </span>
      <span style={hpStyles.editorialTileAction} data-home-tile-primary-action="true">
        {view.copy.primaryAction}
      </span>
    </span>
  )
}

function FullBleedTileImage({
  cover,
  children,
}: {
  cover: string
  children: ReactNode
}) {
  const overlay =
    "linear-gradient(180deg, rgba(12,12,16,0.04) 0%, rgba(12,12,16,0.32) 48%, rgba(12,12,16,0.88) 100%)"
  return (
    <span style={hpStyles.fullBleedLayout} data-home-full-bleed="true">
      <span
        aria-hidden
        style={{
          ...hpStyles.editorialTileImage,
          backgroundImage: `${overlay}, url(${cover})`,
        }}
      />
      <span style={hpStyles.fullBleedReadingBand} data-home-reading-band="true">
        {children}
      </span>
    </span>
  )
}

function TileMediaWell({
  cover,
  variant,
}: {
  cover: string
  variant: "framed" | "side"
}) {
  return (
    <span
      aria-hidden
      data-home-media-well={variant}
      style={{
        ...hpStyles.mediaWell,
        ...mediaWellVariantStyle(variant),
        backgroundImage: `linear-gradient(180deg, rgba(12,12,16,0.02) 0%, rgba(12,12,16,0.18) 58%, rgba(12,12,16,0.50) 100%), url(${cover})`,
      }}
    />
  )
}

function TileTitle({
  span,
  compact,
  lines,
  children,
}: {
  span: HomeTileSpan
  compact: boolean
  lines?: number
  children: string
}) {
  return (
    <span
      style={{
        ...hpStyles.editorialTileTitle,
        ...homeTileTitleStyle(span, compact),
        ...lineClampStyle(lines ?? 3),
      }}
    >
      {children}
    </span>
  )
}

function lineClampStyle(lines: number): CSSProperties {
  if (lines <= 1) {
    return {
      display: "block",
      maxWidth: "100%",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
    }
  }
  return {
    display: "-webkit-box",
    WebkitLineClamp: lines,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  }
}

function homeTileSpanStyle(span: HomeTileSpan, compact: boolean): CSSProperties {
  if (compact) {
    return {
      gridColumn: "auto",
      gridRow: "auto",
      minHeight: span === "feature-tall" ? 278 : span === "dispatch" ? 218 : 244,
    }
  }
  if (span === "feature-wide") return { gridColumn: "span 2", gridRow: "span 2" }
  if (span === "feature-tall") return { gridColumn: "span 1", gridRow: "span 3" }
  if (span === "feature-horizontal") return { gridColumn: "span 2", gridRow: "span 1" }
  if (span === "notice-wide") return { gridColumn: "span 2", gridRow: "span 1" }
  if (span === "dispatch") return { gridColumn: "span 2", gridRow: "span 1" }
  return { gridColumn: "span 2", gridRow: "span 1" }
}

function homeTileTitleStyle(span: HomeTileSpan, compact: boolean): CSSProperties {
  if (compact) return { fontSize: 24, lineHeight: 1.1 }
  if (span === "feature-wide") return { fontSize: 30, lineHeight: 1.05 }
  if (span === "feature-tall") return { fontSize: 25, lineHeight: 1.08 }
  if (span === "feature-horizontal" || span === "notice-wide") return { fontSize: 22, lineHeight: 1.12 }
  return { fontSize: 17.5, lineHeight: 1.16 }
}

function framedTileLayoutStyle(span: HomeTileSpan, compact: boolean): CSSProperties {
  if (compact) return hpStyles.framedTileStack
  if (isSingleRowHomeTileSpan(span)) return hpStyles.framedTileSplit
  return hpStyles.framedTileStack
}

function framedTextPanelStyle(span: HomeTileSpan, compact: boolean): CSSProperties {
  if (!compact && isSingleRowHomeTileSpan(span)) {
    return { ...hpStyles.framedTextPanel, ...hpStyles.framedTextPanelSplit }
  }
  return hpStyles.framedTextPanel
}

function tileMediaVariantForSpan(span: HomeTileSpan, compact: boolean): "framed" | "side" {
  if (!compact && isSingleRowHomeTileSpan(span)) return "side"
  return "framed"
}

function isSingleRowHomeTileSpan(span: HomeTileSpan): boolean {
  return span === "feature-horizontal" || span === "dispatch" || span === "notice-wide"
}

function mediaWellVariantStyle(variant: "framed" | "side"): CSSProperties {
  if (variant === "side") return hpStyles.mediaWellSide
  return hpStyles.mediaWellFramed
}

function visibilityLabel(v: NarrativeTemplateSummary["visibility"], t: ReturnType<typeof useT>): string {
  if (v === "public") return t("home.visibility_public")
  if (v === "unlisted") return t("home.visibility_unlisted")
  return t("home.visibility_private")
}

function formatRelative(isoString: string, t: ReturnType<typeof useT>): string {
  const date = new Date(isoString)
  const diffMs = Date.now() - date.getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return t("home.relative_just_now")
  if (minutes < 60) return t("home.relative_minutes", { n: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t("home.relative_hours", { n: hours })
  const days = Math.floor(hours / 24)
  if (days < 30) return t("home.relative_days", { n: days })
  return date.toLocaleDateString()
}

const hpStyles: Record<string, CSSProperties> = {
  page: { minHeight: "100%", background: "var(--bg)" },
  main: { maxWidth: 1100, margin: "0 auto", padding: "32px 32px 80px" },
  mainCompact: {
    padding: "18px 32px 64px",
  },

  hero: {
    position: "relative",
    minHeight: 360,
    padding: 0,
    borderRadius: 0,
    overflow: "hidden",
    // Vertical gradient: keep the upper half of the splash visible,
    // fade to product bg at the bottom so cards slide up underneath
    // without a hard seam. Horizontal gradient on the left so text
    // sits on solid darkness regardless of where the figures land
    // in the source painting.
    backgroundImage: `linear-gradient(90deg, rgba(12,12,16,0.92) 0%, rgba(12,12,16,0.55) 38%, rgba(12,12,16,0.18) 70%, rgba(12,12,16,0) 100%), linear-gradient(180deg, rgba(12,12,16,0.05) 0%, rgba(12,12,16,0.45) 80%, var(--bg) 100%), url(${PAGE_BG.splash})`,
    backgroundSize: "cover",
    backgroundPosition: "center 30%",
    color: "white",
    marginBottom: 22,
    display: "flex",
    alignItems: "center",
  },
  heroCompact: {
    minHeight: 392,
    marginBottom: 16,
    backgroundImage: `linear-gradient(90deg, rgba(12,12,16,0.94) 0%, rgba(12,12,16,0.62) 48%, rgba(12,12,16,0.16) 100%), linear-gradient(180deg, rgba(12,12,16,0.04) 0%, rgba(12,12,16,0.38) 72%, var(--bg) 100%), url(${PAGE_BG.splash})`,
    backgroundPosition: "center 33%",
    alignItems: "flex-end",
  },
  heroInner: {
    width: "100%",
    maxWidth: 640,
    padding: "58px 56px 64px",
    textAlign: "left" as const,
  },
  heroInnerCompact: {
    padding: "42px 28px 34px",
    maxWidth: 420,
  },
  heroTagline: {
    display: "inline-block",
    fontSize: 12.5,
    letterSpacing: 0,
    textTransform: "none" as const,
    color: "var(--accent)",
    marginBottom: 18,
    fontWeight: 650,
  },
  heroTaglineCompact: {
    fontSize: 11.5,
    letterSpacing: 0,
    marginBottom: 12,
    maxWidth: 250,
    lineHeight: 1.35,
  },
  heroTitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 52,
    lineHeight: 1.08,
    fontWeight: 400,
    margin: "0 0 18px",
    color: "white",
    textShadow: "0 2px 28px rgba(0,0,0,0.55)",
    letterSpacing: 0,
  },
  heroTitleCompact: {
    fontSize: 36,
    lineHeight: 1.03,
    margin: "0 0 14px",
  },
  heroSub: {
    fontSize: 16,
    lineHeight: 1.65,
    color: "rgba(244,239,230,0.82)",
    maxWidth: 540,
    margin: "0 0 24px",
    fontWeight: 400,
  },
  heroSubCompact: {
    fontSize: 14.5,
    lineHeight: 1.5,
    margin: "0 0 18px",
    maxWidth: 280,
  },
  heroActions: {
    display: "flex",
    justifyContent: "flex-start",
    alignItems: "baseline",
    columnGap: 18,
    rowGap: 8,
    flexWrap: "wrap",
  },
  heroActionsCompact: {
    columnGap: 0,
    rowGap: 0,
  },
  heroPrimaryAction: {
    width: "fit-content",
    minHeight: 34,
    padding: "4px 0",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.38)",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(255,226,178,0.98)",
    fontSize: 15,
    fontWeight: 880,
    lineHeight: 1.25,
    fontFamily: "inherit",
    cursor: "pointer",
  },
  heroSecondaryAction: {
    height: "auto",
    padding: "4px 0",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.18)",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(244,239,230,0.74)",
    fontSize: 14,
    fontWeight: 650,
    fontFamily: "inherit",
    cursor: "pointer",
  },

  section: { marginTop: 34 },
  sectionCompact: { marginTop: 18 },
  sectionHeader: { marginBottom: 20 },
  sectionTitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 22,
    fontWeight: 500,
    margin: 0,
  },
  plazaHeader: {
    marginBottom: 26,
    paddingBottom: 0,
    borderBottom: "none",
  },
  plazaLabel: {
    display: "inline-block",
    paddingBottom: 0,
    color: "var(--text-muted)",
    borderBottom: "none",
    fontSize: 13,
    lineHeight: 1.2,
    fontWeight: 650,
  },

  tabs: {
    display: "flex",
    gap: 4,
    borderBottom: "1px solid var(--line)",
    marginBottom: 28,
  },
  tab: {
    background: "none",
    border: "none",
    padding: "12px 18px",
    fontSize: 14,
    color: "var(--text-muted)",
    cursor: "pointer",
    borderBottom: "2px solid transparent",
    marginBottom: -1,
  },
  tabActive: {
    color: "var(--text)",
    borderBottom: "2px solid var(--accent)",
  },

  resumeSection: {
    marginTop: 28,
  },
  resumeButton: {
    width: "100%",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(90px, 18%) auto",
    alignItems: "center",
    gap: 18,
    padding: "22px 0",
    textAlign: "left",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    color: "var(--text)",
    cursor: "pointer",
    transition: "opacity 160ms, transform 160ms",
  },
  resumeButtonCompact: {
    gridTemplateColumns: "1fr",
    gap: 12,
    padding: "18px 0",
  },
  resumeCopy: {
    minWidth: 0,
  },
  resumeKicker: {
    display: "block",
    marginBottom: 6,
    color: "var(--accent)",
    fontSize: 12,
    fontWeight: 650,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  resumeTitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 24,
    lineHeight: 1.18,
    fontWeight: 500,
    color: "var(--text)",
  },
  resumeMeta: {
    marginTop: 7,
    color: "var(--text-faint)",
    fontSize: 12,
  },
  resumeProgress: {
    height: 1,
    background: "var(--line-strong)",
    overflow: "hidden",
  },
  resumeProgressFill: {
    display: "block",
    height: "100%",
    background: "var(--accent)",
  },
  resumeCta: {
    color: "var(--accent)",
    fontSize: 13,
    fontWeight: 700,
    whiteSpace: "nowrap",
  },
  resumeCtaCompact: {
    justifySelf: "start",
  },
  resumeQueue: {
    marginTop: 14,
  },

  sessionRow: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: 10,
  },
  sessionCard: {
    width: "100%",
    display: "block",
    textAlign: "left",
    padding: "10px 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    cursor: "pointer",
    transition: "opacity 160ms, transform 160ms",
    position: "relative",
  },
  sessionCardArchive: {
    paddingBottom: 12,
  },
  archiveHeader: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    marginBottom: 18,
    gap: 16,
  },
  archiveCount: {
    fontSize: 12,
    color: "var(--text-faint)",
    letterSpacing: 0,
    textTransform: "none" as const,
    fontVariantNumeric: "tabular-nums",
  },
  archiveBadge: {
    position: "absolute",
    top: 16,
    right: 18,
    fontSize: 10.5,
    color: "var(--text-faint)",
    fontVariantNumeric: "tabular-nums",
    letterSpacing: 0,
  },
  endingChipGlyph: {
    marginRight: 4,
    fontSize: 11,
  },
  endingChipVictory: {
    color: "rgba(245,210,140,0.96)",
  },
  endingChipCompromised: {
    color: "var(--text)",
  },
  endingChipCollapsed: {
    color: "rgba(245,180,170,0.95)",
  },
  sessionTitle: {
    fontSize: 14.5,
    fontWeight: 500,
    color: "var(--text)",
  },
  sessionObjectLabel: {
    display: "block",
    marginBottom: 6,
    color: "rgba(245,200,120,0.82)",
    fontSize: 10.8,
    fontWeight: 760,
    lineHeight: 1.12,
  },
  sessionMeta: { fontSize: 12, color: "var(--text-faint)", marginTop: 6 },
  sessionAction: {
    color: "rgba(245,200,120,0.86)",
    fontWeight: 760,
  },
  sessionEndingLine: {
    display: "flex",
    alignItems: "baseline",
    gap: 6,
    marginTop: 8,
    flexWrap: "wrap",
  },
  sessionEndingLabel: {
    padding: 0,
    background: "transparent",
    color: "var(--accent)",
    borderRadius: 0,
    fontSize: 11,
    fontWeight: 600,
    whiteSpace: "nowrap",
  },
  sessionEndingSubtitle: {
    fontSize: 12.5,
    color: "var(--text-muted)",
    fontFamily: "var(--font-narrative)",
    fontStyle: "italic",
    flex: "1 1 0",
    minWidth: 0,
  },

  editorialMosaic: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gridAutoRows: "clamp(172px, 12vw, 190px)",
    gridAutoFlow: "dense" as const,
    gap: 12,
    marginBottom: 22,
  },
  editorialMosaicCompact: {
    gridTemplateColumns: "1fr",
    gridAutoRows: "auto",
    gap: 14,
  },
  editorialTile: {
    position: "relative" as const,
    minHeight: "100%",
    padding: 0,
    background: "rgba(12,12,16,0.62)",
    borderTopWidth: 1,
    borderRightWidth: 0,
    borderBottomWidth: 0,
    borderLeftWidth: 0,
    borderTopStyle: "solid",
    borderRightStyle: "solid",
    borderBottomStyle: "solid",
    borderLeftStyle: "solid",
    borderTopColor: "rgba(212,168,83,0.40)",
    borderRightColor: "transparent",
    borderBottomColor: "transparent",
    borderLeftColor: "transparent",
    borderRadius: 0,
    color: "var(--text)",
    cursor: "pointer",
    overflow: "visible",
    textAlign: "left" as const,
    display: "block",
    isolation: "isolate" as const,
    boxShadow: "inset 0 -1px 0 rgba(255,255,255,0.055)",
    transition: "opacity 180ms, transform 180ms, filter 180ms",
  },
  editorialTilePublished: {
    borderTopColor: "rgba(212,168,83,0.58)",
  },
  editorialTileImage: {
    position: "absolute" as const,
    inset: 0,
    zIndex: 0,
    display: "block",
    backgroundSize: "cover",
    backgroundPosition: "center",
  },
  editorialTileBody: {
    position: "relative" as const,
    zIndex: 1,
    minHeight: "100%",
    maxHeight: "100%",
    boxSizing: "border-box" as const,
    overflow: "hidden",
    padding: "18px 18px 16px",
    display: "flex",
    flexDirection: "column" as const,
    justifyContent: "flex-end",
    gap: 7,
  },
  editorialTileKicker: {
    width: "fit-content",
    color: "rgba(245,200,120,0.82)",
    fontSize: 10.5,
    fontWeight: 780,
    lineHeight: 1.12,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  editorialTileTitle: {
    fontFamily: "var(--font-narrative)",
    color: "rgba(255,246,232,0.98)",
    fontWeight: 500,
    letterSpacing: 0,
    textShadow: "0 2px 18px rgba(0,0,0,0.44)",
  },
  editorialTileDeck: {
    color: "rgba(244,239,230,0.76)",
    fontSize: 13.1,
    lineHeight: 1.45,
    textShadow: "0 1px 12px rgba(0,0,0,0.56)",
    minHeight: 0,
  },
  editorialTileDeckCompact: {
    fontSize: 12.8,
    lineHeight: 1.42,
  },
  tileLowInfoBody: {
    display: "flex",
    minWidth: 0,
    minHeight: 0,
    flexDirection: "column" as const,
    justifyContent: "flex-end",
    gap: 9,
  },
  editorialTileAction: {
    width: "fit-content",
    marginTop: 2,
    paddingBottom: 3,
    borderBottom: "1px solid rgba(245,200,120,0.48)",
    color: "rgba(245,200,120,0.95)",
    fontSize: 11.6,
    fontWeight: 800,
    lineHeight: 1.2,
    flexShrink: 0,
    whiteSpace: "nowrap",
  },
  starterKicker: {
    color: "rgba(245,180,132,0.86)",
  },
  publishedKicker: {
    color: "rgba(245,200,120,0.86)",
  },
  resumeKickerTile: {
    color: "rgba(255,226,178,0.88)",
  },
  memoryKicker: {
    color: "rgba(244,239,230,0.78)",
  },
  starterAction: {
    borderBottomColor: "rgba(224,122,95,0.62)",
    color: "rgba(245,190,150,0.96)",
  },
  publishedAction: {
    borderBottomColor: "rgba(245,200,120,0.52)",
    color: "rgba(245,200,120,0.96)",
  },
  resumeAction: {
    borderBottomColor: "rgba(245,200,120,0.46)",
    color: "rgba(255,226,178,0.94)",
  },
  memoryAction: {
    borderBottomColor: "rgba(244,239,230,0.28)",
    color: "rgba(244,239,230,0.82)",
  },
  fullBleedLayout: {
    position: "relative" as const,
    display: "flex",
    alignItems: "flex-end",
    height: "100%",
    minHeight: "100%",
    overflow: "hidden",
  },
  fullBleedReadingBand: {
    position: "relative" as const,
    zIndex: 1,
    width: "100%",
    boxSizing: "border-box" as const,
    padding: "20px 20px 18px",
    display: "flex",
    flexDirection: "column" as const,
    justifyContent: "flex-end",
    gap: 9,
    background: "linear-gradient(180deg, rgba(12,12,16,0.16) 0%, rgba(12,12,16,0.82) 62%, rgba(12,12,16,0.94) 100%)",
    borderTop: "1px solid rgba(245,200,120,0.20)",
    boxShadow: "0 -22px 44px rgba(0,0,0,0.28)",
  },
  framedTileStack: {
    height: "100%",
    minHeight: "100%",
    display: "grid",
    gridTemplateRows: "minmax(120px, 42%) minmax(0, 1fr)",
    background: "linear-gradient(135deg, rgba(12,12,16,0.98), rgba(50,15,18,0.78))",
  },
  framedTileSplit: {
    height: "100%",
    minHeight: "100%",
    display: "grid",
    gridTemplateColumns: "minmax(136px, 38%) minmax(0, 1fr)",
    background: "linear-gradient(135deg, rgba(12,12,16,0.98), rgba(48,14,18,0.78))",
  },
  framedTextPanel: {
    minWidth: 0,
    boxSizing: "border-box" as const,
    padding: "18px 18px 17px",
    display: "flex",
    flexDirection: "column" as const,
    justifyContent: "center",
    gap: 9,
    borderTop: "1px solid rgba(245,200,120,0.13)",
  },
  framedTextPanelSplit: {
    justifyContent: "center",
    borderTop: "none",
    borderLeft: "1px solid rgba(245,200,120,0.13)",
  },
  mediaWell: {
    display: "block",
    minWidth: 0,
    boxSizing: "border-box" as const,
    backgroundSize: "cover",
    backgroundPosition: "center",
    overflow: "hidden",
    borderTopWidth: 1,
    borderRightWidth: 1,
    borderBottomWidth: 1,
    borderLeftWidth: 1,
    borderTopStyle: "solid",
    borderRightStyle: "solid",
    borderBottomStyle: "solid",
    borderLeftStyle: "solid",
    borderTopColor: "rgba(245,200,120,0.20)",
    borderRightColor: "rgba(245,200,120,0.20)",
    borderBottomColor: "rgba(245,200,120,0.20)",
    borderLeftColor: "rgba(245,200,120,0.20)",
    boxShadow: "inset 0 0 34px rgba(0,0,0,0.36)",
  },
  mediaWellFramed: {
    marginTop: 12,
    marginRight: 12,
    marginBottom: 0,
    marginLeft: 12,
    minHeight: 110,
  },
  mediaWellSide: {
    margin: 12,
    minHeight: 0,
    height: "calc(100% - 24px)",
  },

  grid: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: 18,
  },
  gridCompact: {
    gap: 28,
  },
  curatedGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 14,
    marginBottom: 24,
  },
  curatedGridCompact: {
    gridTemplateColumns: "1fr",
    gap: 16,
  },
  curatedStory: {
    display: "grid",
    gridTemplateColumns: "minmax(132px, 36%) minmax(0, 1fr)",
    minHeight: 148,
    padding: 0,
    background: "transparent",
    border: "none",
    borderTop: "1px solid rgba(245,200,120,0.34)",
    borderRadius: 0,
    color: "var(--text)",
    cursor: "pointer",
    overflow: "hidden",
    textAlign: "left",
  },
  curatedStoryCompact: {
    gridTemplateColumns: "1fr",
  },
  curatedCover: {
    minHeight: 148,
    backgroundSize: "cover",
    backgroundPosition: "center",
    display: "block",
  },
  curatedBody: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    minWidth: 0,
    padding: "18px 0 18px 16px",
    gap: 8,
  },
  curatedKicker: {
    width: "fit-content",
    color: "rgba(245,200,120,0.72)",
    fontSize: 10.5,
    fontWeight: 760,
    lineHeight: 1.15,
    letterSpacing: 0,
  },
  curatedTitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 20,
    lineHeight: 1.16,
    color: "var(--text)",
    fontWeight: 500,
  },
  curatedPressure: {
    fontSize: 12.5,
    lineHeight: 1.35,
    color: "var(--text-muted)",
  },
  curatedPromise: {
    fontSize: 11.5,
    color: "var(--text-faint)",
    lineHeight: 1.3,
  },
  curatedAction: {
    width: "fit-content",
    marginTop: 2,
    paddingBottom: 4,
    borderBottom: "1px solid rgba(245,200,120,0.4)",
    color: "rgba(245,200,120,0.92)",
    fontSize: 12,
    fontWeight: 760,
    lineHeight: 1.2,
  },
  card: {
    textAlign: "left",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    cursor: "pointer",
    transition: "opacity 180ms, transform 180ms",
    display: "grid",
    gridTemplateColumns: "clamp(132px, 22vw, 220px) minmax(0, 1fr)",
    minHeight: 158,
    overflow: "hidden",
    padding: 0,
  },
  cardCompact: {
    gridTemplateColumns: "1fr",
    minHeight: 0,
  },
  cardCover: {
    height: "100%",
    minHeight: 158,
    backgroundSize: "cover",
    backgroundPosition: "center",
    display: "block",
    padding: 0,
    position: "relative" as const,
  },
  cardCoverCompact: {
    height: "auto",
    minHeight: 0,
    aspectRatio: "16 / 9",
  },
  cardBody: {
    padding: "20px 0 18px 18px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    gap: 14,
    background: "transparent",
  },
  cardKicker: {
    display: "inline-block",
    marginBottom: 7,
    color: "rgba(245,200,120,0.72)",
    fontSize: 10.5,
    fontWeight: 760,
    lineHeight: 1.15,
    letterSpacing: 0,
  },
  cardBodyCompact: {
    padding: "12px 0 0",
    gap: 10,
    justifyContent: "flex-start",
  },
  cardTitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 20,
    lineHeight: 1.25,
    fontWeight: 500,
    color: "var(--text)",
    textShadow: "none",
    marginBottom: 5,
    letterSpacing: 0,
  },
  cardSeed: {
    fontSize: 12.5,
    color: "var(--text-muted)",
    fontStyle: "italic",
    lineHeight: 1.5,
  },
  cardSeedCompact: {
    fontSize: 13,
    lineHeight: 1.55,
  },
  cardCast: {
    fontSize: 11,
    color: "var(--text-faint)",
    textShadow: "none",
    letterSpacing: 0,
  },
  cardFooter: {
    display: "flex",
    alignItems: "center",
    columnGap: 8,
    rowGap: 5,
    flexWrap: "wrap" as const,
    fontSize: 11,
    color: "var(--text-faint)",
    paddingTop: 0,
    borderTop: "none",
  },
  cardFooterCompact: {
    rowGap: 7,
  },
  cardBadge: {
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
    textTransform: "none" as const,
    letterSpacing: 0,
  },
  cardPlays: { fontSize: 11 },
  cardOwnerBadge: {
    padding: 0,
    background: "transparent",
    color: "var(--accent)",
    fontSize: 11,
    textTransform: "none" as const,
    letterSpacing: 0,
  },
  cardAction: {
    marginLeft: 0,
    color: "rgba(245,200,120,0.88)",
    fontSize: 11.5,
    fontWeight: 720,
    letterSpacing: 0,
    whiteSpace: "nowrap" as const,
  },
  cardActionCompact: {
    flexBasis: "100%",
    marginTop: 1,
  },

  errorBox: {
    padding: "12px 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    color: "var(--warn)",
    fontSize: 14,
  },
  loading: { padding: 40, textAlign: "center", color: "var(--text-faint)", fontSize: 14 },
  empty: {
    padding: "28px 0",
    textAlign: "left",
    color: "var(--text-faint)",
    fontSize: 14,
    fontStyle: "italic",
    background: "transparent",
    borderRadius: 0,
    border: "none",
  },
  emptyCard: {
    background: "transparent",
    borderRadius: 0,
    border: "none",
    overflow: "hidden",
  },
  emptyHero: {
    width: "100%",
    height: 180,
    backgroundSize: "cover",
    backgroundPosition: "center",
  },
  emptyBody: {
    padding: "20px 24px 28px",
    textAlign: "center",
    color: "var(--text-muted)",
    fontSize: 14,
    fontStyle: "italic",
    fontFamily: "var(--font-narrative)",
  },

  footer: {
    marginTop: 80,
    paddingTop: 32,
    borderTop: "1px dashed var(--line)",
    textAlign: "center",
    fontSize: 12,
    color: "var(--text-faint)",
    display: "flex",
    justifyContent: "center",
    gap: 8,
    alignItems: "center",
  },
  footerBrand: { fontFamily: "var(--font-narrative)", color: "var(--text-muted)" },
  footerSep: { color: "var(--line-strong)" },
  footerLink: {
    color: "var(--text-muted)",
    textDecoration: "none",
    cursor: "pointer",
  },
}
