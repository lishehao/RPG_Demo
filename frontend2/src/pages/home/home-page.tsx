import { type CSSProperties, useEffect, useState } from "react"
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
  getCoverForTemplate,
  getEmptyPlazaImage,
} from "../../shared/lib/webtoon-assets"
import { friendlyError } from "../../shared/lib/friendly-error"
import { ENDING_LABEL_DISPLAY, useLanguage, useT } from "../../shared/lib/i18n"
import { itemTransition, itemVariants, tapPress, transitions } from "../../shared/lib/motion-presets"

type Tab = "plaza" | "my-templates"

export function HomePage({
  onOpenCreate,
  onOpenTemplate,
  onOpenPlay,
}: {
  onOpenCreate: () => void
  onOpenTemplate: (templateId: string) => void
  onOpenPlay: (sessionId: string) => void
}) {
  const api = useApi()
  const auth = useAuth()
  const t = useT()
  const compactHome = useCompactLayout()
  const [tab, setTab] = useState<Tab>("plaza")
  const [publicTemplates, setPublicTemplates] = useState<NarrativeTemplateSummary[] | null>(null)
  const [myTemplates, setMyTemplates] = useState<NarrativeTemplateSummary[] | null>(null)
  const [mySessions, setMySessions] = useState<NarrativeSessionSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const showTemplateTabs = !auth.isAnonymous
  const activeTemplateTab: Tab = showTemplateTabs ? tab : "plaza"

  useEffect(() => {
    let cancelled = false
    setError(null)
    api
      .listPublicNarrativeTemplates()
      .then((res) => {
        if (cancelled) return
        setPublicTemplates(res.items)
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
            <motion.p
              variants={itemVariants}
              transition={itemTransition}
              style={{ ...hpStyles.heroSub, ...(compactHome ? hpStyles.heroSubCompact : null) }}
            >
              {t("home.hero_sub")}
            </motion.p>
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
              {!compactHome ? (
                <motion.button
                  style={hpStyles.heroSecondaryAction}
                  onClick={() => {
                    window.location.hash = "#/portfolio"
                  }}
                  type="button"
                  whileHover={{ x: 2 }}
                  whileTap={tapPress}
                >
                  {t("home.cta_portfolio")}
                </motion.button>
              ) : null}
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
                <TemplateGrid
                  templates={publicTemplates}
                  error={error}
                  emptyText={t("home.empty_plaza")}
                  compact={compactHome}
                  onOpenTemplate={onOpenTemplate}
                />
              ) : (
                <TemplateGrid
                  templates={myTemplates}
                  error={null}
                  emptyText={t("home.empty_my")}
                  compact={compactHome}
                  onOpenTemplate={onOpenTemplate}
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
  const safeBudget = Math.max(session.turn_budget, 1)
  const turnsPlayed = Math.min(Math.max(session.turn_count, 0), safeBudget)
  const progress = Math.min(1, Math.max(0, turnsPlayed / safeBudget))
  const roleLabel = session.player_role?.label ? t("home.resume_role", { role: session.player_role.label }) : null
  return (
    <motion.button
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
        <span style={hpStyles.resumeKicker}>{t("home.resume_kicker")}</span>
        <Truncated lines={2} style={hpStyles.resumeTitle}>{session.template_title}</Truncated>
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
        {t("home.resume_cta")}
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
  const completed = Boolean(session.ending_label)
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
      <Truncated style={hpStyles.sessionTitle}>{session.template_title}</Truncated>
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
            {t("home.session_completed_meta")} · {formatRelative(session.last_active_at, t)}
          </div>
        </>
      ) : (
        <div style={hpStyles.sessionMeta}>
          {t("home.session_progress_meta", {
            current: turnsPlayed,
            total: session.turn_budget,
          })}{" "}
          · {formatRelative(session.last_active_at, t)}
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
  onOpenTemplate,
}: {
  templates: NarrativeTemplateSummary[] | null
  error: string | null
  emptyText: string
  compact: boolean
  onOpenTemplate: (templateId: string) => void
}) {
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
        <div style={hpStyles.emptyBody}>{emptyText}</div>
      </motion.div>
    )
  }
  return (
    <div style={{ ...hpStyles.grid, ...(compact ? hpStyles.gridCompact : null) }}>
      {templates.map((t, idx) => (
        <TemplateCard
          key={t.template_id}
          template={t}
          index={idx}
          compact={compact}
          onClick={() => onOpenTemplate(t.template_id)}
        />
      ))}
    </div>
  )
}

function TemplateCard({
  template,
  onClick,
  index = 0,
  compact,
}: {
  template: NarrativeTemplateSummary
  onClick: () => void
  index?: number
  compact: boolean
}) {
  const t = useT()
  const cover = getCoverForTemplate(template)
  return (
    <motion.button
      style={{ ...hpStyles.card, ...(compact ? hpStyles.cardCompact : null) }}
      onClick={onClick}
      type="button"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, ...itemTransition }}
      whileHover={{ x: 2 }}
      whileTap={tapPress}
    >
      <div
        style={{
          ...hpStyles.cardCover,
          ...(compact ? hpStyles.cardCoverCompact : null),
          backgroundImage: `url(${cover})`,
        }}
      />
      <div style={{ ...hpStyles.cardBody, ...(compact ? hpStyles.cardBodyCompact : null) }}>
        <div>
          <Truncated lines={2} style={hpStyles.cardTitle}>
            {template.title}
          </Truncated>
          <Truncated style={hpStyles.cardCast}>
            {template.cast.map((c) => c.display_name).join(" · ")}
          </Truncated>
        </div>
        <Truncated
          lines={compact ? 3 : 2}
          style={{ ...hpStyles.cardSeed, ...(compact ? hpStyles.cardSeedCompact : null) }}
        >
          {`"${template.seed}"`}
        </Truncated>
        <div style={{ ...hpStyles.cardFooter, ...(compact ? hpStyles.cardFooterCompact : null) }}>
          <span style={hpStyles.cardBadge}>{visibilityLabel(template.visibility, t)}</span>
          <span style={hpStyles.cardPlays}>{t("home.played_count", { count: template.play_count })}</span>
          {template.is_owner ? (
            <span style={hpStyles.cardOwnerBadge}>{t("home.is_owner")}</span>
          ) : null}
          <span style={{ ...hpStyles.cardAction, ...(compact ? hpStyles.cardActionCompact : null) }}>
            {t("home.card_action")}
          </span>
        </div>
      </div>
    </motion.button>
  )
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
  sessionMeta: { fontSize: 12, color: "var(--text-faint)", marginTop: 6 },
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

  grid: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: 18,
  },
  gridCompact: {
    gap: 28,
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
