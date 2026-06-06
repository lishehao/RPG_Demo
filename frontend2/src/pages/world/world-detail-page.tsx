import { type CSSProperties, useEffect, useRef, useState } from "react"
import { motion } from "motion/react"
import type {
  NarrativeEndingDistributionResponse,
  NarrativePlayerRole,
  NarrativeTemplateSummary,
  NarrativeTemplateVisibility,
} from "../../api/contracts"
import { useApi } from "../../app/api-context"
import { Header } from "../../shared/ui/header"
import { friendlyError } from "../../shared/lib/friendly-error"
import { LoadingShim } from "../../shared/ui/loading-shim"
import { Truncated } from "../../shared/ui/truncated"
import { EmptyState } from "../../shared/ui/empty-state"
import { ENDING_LABEL_DISPLAY, useLanguage, useT } from "../../shared/lib/i18n"
import { cascadeDelay, hoverLift, itemTransition, tapPress, transitions } from "../../shared/lib/motion-presets"
import {
  getTemplateDisplaySummary,
  getTemplateDisplayTitle,
} from "../../shared/lib/localized-story-metadata"
import {
  getAdvisorAvatar,
  getAvatarForCastMember,
  getCoverForTemplate,
} from "../../shared/lib/webtoon-assets"

export function TemplateDetailPage({
  templateId,
  onBackHome,
  onOpenCreate,
  onSessionStarted,
}: {
  templateId: string
  onBackHome: () => void
  onOpenCreate: () => void
  onSessionStarted: (sessionId: string) => void
}) {
  const api = useApi()
  const t = useT()
  const { lang } = useLanguage()
  const compactLayout = useCompactLayout()
  const [template, setTemplate] = useState<NarrativeTemplateSummary | null>(null)
  const [distribution, setDistribution] = useState<NarrativeEndingDistributionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [visBusy, setVisBusy] = useState(false)
  const [selectedRoleIndex, setSelectedRoleIndex] = useState<number | null>(null)
  const startInflightRef = useRef(false)

  useEffect(() => {
    let cancelled = false
    setError(null)
    setSelectedRoleIndex(null)
    api
      .getNarrativeTemplate(templateId)
      .then((res) => {
        if (cancelled) return
        setTemplate(res)
        setSelectedRoleIndex(res.player_role_options?.length ? 0 : null)
      })
      .catch((err) => {
        if (cancelled) return
        setError(friendlyError(err, t("world.error_template_missing")))
      })
    api
      .getNarrativeEndingDistribution(templateId)
      .then((res) => {
        if (cancelled) return
        setDistribution(res)
      })
      .catch(() => {
        // Distribution failure is non-fatal — just skip rendering it.
      })
    return () => {
      cancelled = true
    }
  }, [api, templateId, t])

  const handleStart = async (roleIndex?: number) => {
    if (startInflightRef.current || !template) return
    startInflightRef.current = true
    setSelectedRoleIndex(roleIndex ?? null)
    setBusy(true)
    setError(null)
    try {
      const res = await api.startNarrativeSession(
        templateId,
        roleIndex !== undefined ? { player_role_index: roleIndex } : undefined,
      )
      onSessionStarted(res.session.session_id)
    } catch (err) {
      setError(friendlyError(err, t("world.error_start_failed")))
      setBusy(false)
      startInflightRef.current = false
    }
  }

  const handleVisibility = async (next: NarrativeTemplateVisibility) => {
    if (visBusy || !template) return
    setVisBusy(true)
    try {
      const updated = await api.updateNarrativeTemplateVisibility(templateId, {
        visibility: next,
      })
      setTemplate(updated)
    } catch (err) {
      setError(friendlyError(err, t("world.error_visibility_failed")))
    } finally {
      setVisBusy(false)
    }
  }

  if (!template) {
    return (
      <div style={tdStyles.page}>
        <Header onHome={onBackHome} onCreate={onOpenCreate} createVariant="link" />
        {error ? (
          <EmptyState
            title={t("world.empty_title")}
            hint={error}
            action={
              <button
                style={tdStyles.emptyAction}
                type="button"
                onClick={onBackHome}
              >
                {t("world.empty_back")}
              </button>
            }
          />
        ) : (
          <LoadingShim label={t("world.loading")} />
        )}
      </div>
    )
  }

  const cover = getCoverForTemplate(template)
  const displayTitle = getTemplateDisplayTitle(template, lang)
  const advisorAvatar = getAdvisorAvatar(template.template_id, template.advisor_persona)
  const selectedRole =
    selectedRoleIndex !== null
      ? template.player_role_options?.[selectedRoleIndex] ?? null
      : null
  const roleOptions = template.player_role_options ?? []
  const hasMultipleRoles = roleOptions.length > 1

  return (
    <div style={tdStyles.page}>
      <Header onHome={onBackHome} onCreate={onOpenCreate} createVariant="link" />

      {/* Hero: shell cover with title overlay */}
      <div
        style={{
          ...tdStyles.hero,
          backgroundImage: `linear-gradient(180deg, rgba(20,16,12,0.18) 0%, rgba(20,16,12,0.6) 60%, var(--bg) 100%), url(${cover})`,
        }}
      >
        <div style={tdStyles.heroInner}>
          <button style={tdStyles.crumb} onClick={onBackHome} type="button">
            {t("world.crumb_back_home")}
          </button>
          <h1 style={tdStyles.title}>{displayTitle}</h1>
          <div style={tdStyles.metaRow}>
            <span style={tdStyles.badge}>{visibilityLabel(template.visibility, t)}</span>
            <span style={tdStyles.metaItem}>
              {t("world.played_count", { count: template.play_count })}
            </span>
            {template.is_owner ? (
              <span style={{ ...tdStyles.badge, ...tdStyles.ownerBadge }}>
                {t("world.is_owner")}
              </span>
            ) : null}
          </div>
        </div>
      </div>

      <main style={tdStyles.main}>
        {error ? <div style={tdStyles.errorBox}>{error}</div> : null}

        <div style={{
          ...tdStyles.launchGrid,
          ...(compactLayout ? tdStyles.launchGridCompact : {}),
        }}>
          <div style={tdStyles.launchPrimary}>
            {roleOptions.length > 0 ? (
              <section style={tdStyles.roleSection}>
                <div style={tdStyles.sectionLabel}>
                  {hasMultipleRoles ? t("world.section_roles") : t("world.section_role_single")}
                </div>
                <p style={tdStyles.roleHint}>
                  {hasMultipleRoles ? t("world.roles_hint") : t("world.role_single_hint")}
                </p>
                {hasMultipleRoles ? (
                  <div
                    style={{
                      ...tdStyles.roleChooserLayout,
                      ...(compactLayout ? tdStyles.roleChooserLayoutCompact : null),
                    }}
                  >
                    <div
                      style={{
                        ...tdStyles.roleChoiceList,
                        ...(compactLayout ? tdStyles.roleChoiceListCompact : null),
                      }}
                      aria-label={t("world.section_roles")}
                    >
                      {roleOptions.map((role, idx) => {
                        const isActive = idx === selectedRoleIndex
                        return (
                          <button
                            key={role.role_id}
                            type="button"
                            style={{
                              ...tdStyles.roleChoiceButton,
                              ...(compactLayout ? tdStyles.roleChoiceButtonCompact : null),
                              ...(isActive ? tdStyles.roleChoiceButtonActive : null),
                            }}
                            onClick={() => setSelectedRoleIndex(idx)}
                            disabled={busy}
                            aria-pressed={isActive}
                          >
                            <span
                              style={{
                                ...tdStyles.roleChoiceIndex,
                                ...(isActive ? tdStyles.roleChoiceIndexActive : null),
                              }}
                            >
                              {idx + 1}.
                            </span>
                            <span style={tdStyles.roleChoiceCopy}>
                              <span style={tdStyles.roleChoiceTopline}>
                                <Truncated style={tdStyles.roleChoiceName}>{role.label}</Truncated>
                                {isActive ? (
                                  <span style={tdStyles.roleChoiceSelected}>
                                    {t("world.role_chosen_badge")}
                                  </span>
                                ) : null}
                              </span>
                              <span style={tdStyles.roleChoiceMeta}>
                                {t("world.role_launch_stats", {
                                  cards: role.leverages_over_npcs.length,
                                  items: role.starting_assets.length,
                                })}
                              </span>
                              <Truncated
                                lines={2}
                                style={{
                                  ...tdStyles.roleChoiceObjective,
                                  ...(isActive ? tdStyles.roleChoiceObjectiveActive : null),
                                }}
                              >
                                {role.hidden_objective}
                              </Truncated>
                            </span>
                          </button>
                        )
                      })}
                    </div>
                    {selectedRole && selectedRoleIndex !== null ? (
                      <SelectedRoleLaunchPanel
                        role={selectedRole}
                        cast={template.cast}
                        busy={busy}
                        hasAlternates
                        onStart={() => void handleStart(selectedRoleIndex)}
                      />
                    ) : null}
                  </div>
                ) : null}
                {!hasMultipleRoles && selectedRole && selectedRoleIndex !== null ? (
                  <SelectedRoleLaunchPanel
                    role={selectedRole}
                    cast={template.cast}
                    busy={busy}
                    hasAlternates={false}
                    onStart={() => void handleStart(selectedRoleIndex)}
                  />
                ) : null}
              </section>
            ) : (
              <div style={tdStyles.actions}>
                <motion.button
                  onClick={() => void handleStart()}
                  disabled={busy}
                  style={{
                    ...tdStyles.startAction,
                    opacity: busy ? 0.5 : 1,
                    pointerEvents: busy ? "none" : "auto",
                  }}
                  type="button"
                  whileHover={busy ? undefined : hoverLift}
                  whileTap={busy ? undefined : tapPress}
                >
                  {busy ? t("world.start_busy") : t("world.start_cta")}
                </motion.button>
                <p style={tdStyles.actionHint}>
                  {t("world.start_hint")}
                </p>
              </div>
            )}
          </div>

          <StoryBriefingRail
            template={template}
            advisorAvatar={advisorAvatar}
            distribution={distribution}
            lang={lang}
          />
        </div>

        {/* Owner-only: visibility controls */}
        {template.is_owner ? (
          <section style={tdStyles.ownerSection}>
            <div style={tdStyles.sectionLabel}>{t("world.section_visibility")}</div>
            <div style={tdStyles.visControls}>
              {(["private", "unlisted", "public"] as NarrativeTemplateVisibility[]).map((v) => (
                <button
                  key={v}
                  style={{
                    ...tdStyles.visBtn,
                    ...(template.visibility === v ? tdStyles.visBtnActive : {}),
                  }}
                  onClick={() => void handleVisibility(v)}
                  disabled={visBusy || template.visibility === v}
                  type="button"
                >
                  {visibilityLabel(v, t)}
                </button>
              ))}
            </div>
          </section>
        ) : null}
      </main>
    </div>
  )
}

function visibilityLabel(v: NarrativeTemplateVisibility, t: ReturnType<typeof useT>): string {
  if (v === "public") return t("world.visibility_public")
  if (v === "unlisted") return t("home.visibility_unlisted")
  return t("home.visibility_private")
}

function useCompactLayout(query = "(max-width: 900px)") {
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

function displayEndingLabel(label: string, lang: ReturnType<typeof useLanguage>["lang"]): string {
  const translated = ENDING_LABEL_DISPLAY[lang][label]
  if (translated) return translated
  return label
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase())
}

function StoryBriefingRail({
  template,
  advisorAvatar,
  distribution,
  lang,
}: {
  template: NarrativeTemplateSummary
  advisorAvatar: string
  distribution: NarrativeEndingDistributionResponse | null
  lang: ReturnType<typeof useLanguage>["lang"]
}) {
  const t = useT()
  const displaySummary = getTemplateDisplaySummary(template, lang)
  const npcNameById = new Map(template.cast.map((c) => [c.character_id, c.display_name]))
  const edges: Array<{ holder: string; target: string; leverage: string }> = []
  for (const c of template.cast) {
    for (const lev of c.leverages_over_other_npcs ?? []) {
      edges.push({
        holder: c.display_name,
        target: npcNameById.get(lev.target_npc_id) ?? lev.target_npc_id,
        leverage: lev.leverage,
      })
    }
  }

  return (
    <aside style={tdStyles.launchRail}>
      <section style={tdStyles.briefingRail}>
        <div style={tdStyles.sectionLabel}>{t("world.section_briefing")}</div>
        <div style={tdStyles.seedQuote}>"{displaySummary}"</div>

        <div style={tdStyles.railDivider} />

        <div style={tdStyles.briefingSubhead}>{t("world.section_cast")}</div>
        <div style={tdStyles.castList}>
          {template.cast.map((c) => {
            const interLevs = c.leverages_over_other_npcs ?? []
            return (
              <div key={c.character_id} style={tdStyles.castRow}>
                <img
                  src={getAvatarForCastMember(template.template_id, c)}
                  alt={c.display_name}
                  style={tdStyles.castAvatar}
                  loading="lazy"
                />
                <div style={tdStyles.castInfo}>
                  <Truncated style={tdStyles.castName}>{c.display_name}</Truncated>
                  <Truncated style={tdStyles.castRole}>{c.role}</Truncated>
                  <span style={tdStyles.castRelation}>{c.relation_to_protagonist}</span>
                  {interLevs.length > 0 ? (
                    <div style={tdStyles.castLevChip}>
                      {t("world.cast_holds_leverage", { count: interLevs.length })}
                    </div>
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>

        <div style={tdStyles.advisorBlock}>
          <img src={advisorAvatar} alt="" style={tdStyles.advisorAvatar} loading="lazy" />
          <span style={tdStyles.advisorText}>{template.advisor_persona}</span>
        </div>

        <div style={tdStyles.railDetailsGroup}>
          {edges.length > 0 ? (
            <details style={tdStyles.railDetails}>
              <summary style={tdStyles.railDetailsSummary}>{t("world.network_label")}</summary>
              <p style={tdStyles.networkHint}>
                {t("world.network_hint")}
              </p>
              <ul style={tdStyles.networkList}>
                {edges.map((e, i) => (
                  <li key={i} style={tdStyles.networkRow}>
                    <Truncated style={tdStyles.networkHolder}>{e.holder}</Truncated>
                    <span style={tdStyles.networkArrow}>→</span>
                    <Truncated style={tdStyles.networkTarget}>{e.target}</Truncated>
                    <span style={tdStyles.networkColon}>:</span>
                    <Truncated lines={2} style={tdStyles.networkLeverage}>{e.leverage}</Truncated>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          {template.failure_conditions && template.failure_conditions.length > 0 ? (
            <details style={tdStyles.railDetails}>
              <summary style={tdStyles.railDetailsSummary}>{t("world.section_failure")}</summary>
              <p style={tdStyles.failureHint}>
                {t("world.failure_hint")}
              </p>
              <ul style={tdStyles.failureList}>
                {template.failure_conditions.map((fc, i) => (
                  <li key={i} style={tdStyles.failureRow}>
                    <Truncated style={tdStyles.failureLabel}>{`! ${fc.label}`}</Truncated>
                    <Truncated lines={2} style={tdStyles.failureDesc}>{fc.description}</Truncated>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          {distribution && distribution.total_completed > 0 ? (
            <details style={tdStyles.railDetails}>
              <summary style={tdStyles.railDetailsSummary}>
                {t("world.section_endings", { count: distribution.total_completed })}
              </summary>
              <div style={tdStyles.distributionList}>
                {distribution.entries.map((entry, idx) => {
                  const pct = (entry.count / distribution.total_completed) * 100
                  return (
                    <motion.div
                      key={entry.label}
                      style={tdStyles.distributionRow}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.05 * idx + 0.15, ...itemTransition }}
                    >
                      <Truncated style={tdStyles.distributionLabel}>
                        {displayEndingLabel(entry.label, lang)}
                      </Truncated>
                      <div style={tdStyles.distributionBarTrack}>
                        <motion.div
                          style={tdStyles.distributionBarFill}
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ delay: cascadeDelay(idx, 0.05, 0.25), ...transitions.slow }}
                        />
                      </div>
                      <div style={tdStyles.distributionCount}>x{entry.count}</div>
                    </motion.div>
                  )
                })}
              </div>
              <p style={tdStyles.distributionHint}>
                {t("world.endings_hint")}
              </p>
            </details>
          ) : null}
        </div>
      </section>
    </aside>
  )
}

function SelectedRoleLaunchPanel({
  role,
  cast,
  busy,
  hasAlternates,
  onStart,
}: {
  role: NarrativePlayerRole
  cast: NarrativeTemplateSummary["cast"]
  busy: boolean
  hasAlternates: boolean
  onStart: () => void
}) {
  const t = useT()
  const compactLayout = useCompactLayout()
  const npcNameById = new Map(cast.map((c) => [c.character_id, c.display_name]))
  const previewLeverage = role.leverages_over_npcs[0]
  const previewAsset = role.starting_assets[0]
  const hiddenPreviewCount =
    Math.max(0, role.leverages_over_npcs.length - (previewLeverage ? 1 : 0)) +
    Math.max(0, role.starting_assets.length - (previewAsset ? 1 : 0))
  const previewLeverageText = previewLeverage
    ? `${npcNameById.get(previewLeverage.npc_id) ?? previewLeverage.npc_id}: ${previewLeverage.leverage}`
    : ""
  const previewAssetText = previewAsset ?? ""
  const briefLines = [
    role.public_persona
      ? {
          label: t("world.role_launch_persona_label"),
          text: role.public_persona,
          tone: "public" as const,
        }
      : null,
    {
      label: t("world.role_launch_private_label"),
      text: role.hidden_objective,
      tone: "private" as const,
    },
    previewLeverage
      ? {
          label: t("world.role_loadout_leverage_label"),
          text: previewLeverageText,
          tone: "leverage" as const,
        }
      : null,
    previewAsset
      ? {
          label: t("world.role_loadout_asset_label"),
          text: previewAssetText,
          tone: "asset" as const,
        }
      : null,
  ].filter((line): line is { label: string; text: string; tone: "public" | "private" | "leverage" | "asset" } => Boolean(line))

  return (
    <motion.div
      style={{
        ...tdStyles.roleLaunchPanel,
        ...(compactLayout ? tdStyles.roleLaunchPanelCompact : null),
      }}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={transitions.snap}
    >
      <div style={tdStyles.roleLaunchMain}>
        <div style={tdStyles.roleLaunchKicker}>{t("world.role_launch_kicker")}</div>
        <div style={tdStyles.roleLaunchTitleRow}>
          <Truncated style={tdStyles.roleLaunchTitle}>{role.label}</Truncated>
          <span style={tdStyles.roleLaunchStat}>
            {t("world.role_launch_stats", {
              cards: role.leverages_over_npcs.length,
              items: role.starting_assets.length,
            })}
          </span>
        </div>
        <div style={tdStyles.roleLaunchBrief}>
          {briefLines.map((line, index) => (
            <p key={`${line.label}-${index}`} style={tdStyles.roleLaunchBriefLine}>
              <span style={tdStyles.roleLaunchBriefLabel}>{line.label}</span>
              <span
                style={{
                  ...tdStyles.roleLaunchBriefText,
                  ...(line.tone === "private" ? tdStyles.roleLaunchBriefPrivate : null),
                  ...(line.tone === "leverage" ? tdStyles.roleLaunchBriefLeverage : null),
                }}
              >
                {line.text}
              </span>
            </p>
          ))}
          {hiddenPreviewCount > 0 ? (
            <div style={tdStyles.roleLaunchMore}>
              {t("world.role_loadout_more", { count: hiddenPreviewCount })}
            </div>
          ) : null}
        </div>
      </div>
      <div
        style={{
          ...tdStyles.roleLaunchActions,
          ...(compactLayout ? tdStyles.roleLaunchActionsCompact : null),
        }}
      >
        <motion.button
          type="button"
          style={tdStyles.roleLaunchButton}
          onClick={onStart}
          disabled={busy}
          whileHover={busy ? undefined : hoverLift}
          whileTap={busy ? undefined : tapPress}
        >
          {busy ? t("world.role_starting_cta") : t("world.role_launch_cta")}
        </motion.button>
        <span
          style={{
            ...tdStyles.roleLaunchHint,
            ...(compactLayout ? tdStyles.roleLaunchHintCompact : null),
          }}
        >
          {hasAlternates ? t("world.role_launch_hint") : t("world.start_hint")}
        </span>
      </div>
    </motion.div>
  )
}

const tdStyles: Record<string, CSSProperties> = {
  page: { minHeight: "100%", background: "var(--bg)" },
  center: { padding: 80, textAlign: "center", color: "var(--text-muted)" },
  main: { maxWidth: 1040, margin: "-48px auto 0", padding: "0 32px 80px", position: "relative", zIndex: 2 },

  hero: {
    width: "100%",
    minHeight: 280,
    backgroundSize: "cover",
    backgroundPosition: "center",
    color: "white",
    display: "flex",
    alignItems: "flex-end",
  },
  heroInner: {
    width: "100%",
    maxWidth: 1040,
    margin: "0 auto",
    padding: "32px 32px 56px",
  },
  crumb: {
    background: "transparent",
    borderTop: "none",
    borderRight: "none",
    borderLeft: "none",
    borderBottom: "1px solid rgba(255,255,255,0.22)",
    color: "white",
    fontSize: 12.5,
    cursor: "pointer",
    padding: "0 0 4px",
    borderRadius: 0,
    marginBottom: 18,
  },
  title: {
    fontFamily: "var(--font-narrative)",
    fontSize: 38,
    lineHeight: 1.18,
    fontWeight: 400,
    margin: "0 0 16px",
    color: "white",
    textShadow: "0 2px 18px rgba(0,0,0,0.5)",
  },
  metaRow: { display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" },
  badge: {
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
    fontSize: 12,
    color: "var(--accent)",
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  ownerBadge: {
    background: "transparent",
    color: "var(--accent)",
    borderColor: "transparent",
  },
  metaItem: { fontSize: 12, color: "rgba(255,255,255,0.78)" },

  section: { marginBottom: 28 },
  launchGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(300px, 360px)",
    gap: 22,
    alignItems: "start",
  },
  launchGridCompact: {
    gridTemplateColumns: "1fr",
  },
  launchPrimary: {
    minWidth: 0,
  },
  launchRail: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 24,
  },
  briefingRail: {
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 18,
  },
  railDetails: {
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
  },
  railDetailsSummary: {
    cursor: "pointer",
    fontSize: 12.5,
    color: "var(--accent)",
    letterSpacing: 0,
    textTransform: "none" as const,
    fontWeight: 680,
  },
  railDetailsGroup: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 12,
  },
  railDivider: {
    height: 1,
    background: "rgba(255,255,255,0.075)",
  },
  briefingSubhead: {
    fontSize: 11.5,
    color: "var(--text-faint)",
    letterSpacing: 0,
    textTransform: "none" as const,
    fontWeight: 680,
    marginBottom: -4,
  },
  sectionLabel: {
    fontSize: 11.5,
    color: "var(--text-faint)",
    letterSpacing: 0,
    textTransform: "none",
    fontWeight: 680,
    marginBottom: 10,
  },
  seedQuote: {
    fontFamily: "var(--font-narrative)",
    fontSize: 15.5,
    lineHeight: 1.6,
    color: "var(--text-muted)",
    fontStyle: "italic",
    padding: 0,
    border: "none",
    background: "transparent",
    borderRadius: 0,
  },

  castList: { display: "flex", flexDirection: "column", gap: 14 },
  castRow: {
    display: "flex",
    alignItems: "center",
    gap: 11,
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
  },
  castAvatar: {
    width: 44,
    height: 44,
    borderRadius: "50%",
    objectFit: "cover",
    border: "1px solid var(--line)",
    flexShrink: 0,
  },
  castInfo: { flex: 1, minWidth: 0 },
  castName: { display: "block", fontSize: 13.5, fontWeight: 600 },
  castRole: { display: "block", fontSize: 11.5, color: "var(--accent)", marginTop: 2 },
  castRelation: {
    display: "block",
    fontSize: 12,
    color: "var(--text-muted)",
    lineHeight: 1.45,
    marginTop: 3,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  castLevChip: {
    display: "inline-block",
    marginTop: 6,
    fontSize: 11,
    color: "rgba(245,200,120,0.92)",
    background: "transparent",
    border: "none",
    padding: 0,
    borderRadius: 0,
    letterSpacing: 0,
  },

  failureHint: {
    fontSize: 13,
    color: "var(--text-muted)",
    lineHeight: 1.6,
    margin: "0 0 12px",
  },
  failureList: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 10,
  },
  failureRow: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
  },
  failureLabel: {
    fontFamily: "var(--font-narrative)",
    fontSize: 14,
    fontWeight: 500,
    color: "rgba(245,180,170,0.96)",
    letterSpacing: 0,
  },
  failureDesc: {
    fontSize: 13,
    color: "var(--text-muted)",
    lineHeight: 1.6,
  },

  networkHint: {
    fontSize: 12.5,
    color: "var(--text-muted)",
    lineHeight: 1.55,
    margin: "0 0 12px",
  },
  networkList: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
  },
  networkRow: {
    fontSize: 13,
    lineHeight: 1.55,
    color: "var(--text)",
    display: "flex",
    flexWrap: "wrap" as const,
    alignItems: "baseline",
    gap: 4,
  },
  networkHolder: {
    fontWeight: 600,
    color: "rgba(245,200,120,0.95)",
  },
  networkArrow: {
    color: "var(--text-faint)",
    fontSize: 12,
    margin: "0 2px",
  },
  networkTarget: {
    fontWeight: 600,
    color: "var(--accent)",
  },
  networkColon: {
    color: "var(--text-faint)",
  },
  networkLeverage: {
    color: "var(--text-muted)",
    flex: "1 1 100%",
    paddingLeft: 0,
    fontStyle: "italic" as const,
    fontSize: 12.5,
  },

  advisorBlock: {
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: "var(--radius-sm)",
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  advisorAvatar: {
    width: 40,
    height: 40,
    borderRadius: "50%",
    objectFit: "cover",
    border: "1px solid var(--line)",
    flexShrink: 0,
  },
  advisorText: {
    display: "-webkit-box",
    WebkitLineClamp: 3,
    WebkitBoxOrient: "vertical" as const,
    overflow: "hidden",
    fontSize: 12.5,
    lineHeight: 1.5,
    color: "var(--text)",
  },

  actions: { marginTop: 40, display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 8 },
  emptyAction: {
    width: "fit-content",
    minHeight: 32,
    padding: "4px 0",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.34)",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(255,226,178,0.96)",
    fontSize: 13.5,
    fontWeight: 850,
    lineHeight: 1.25,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  startAction: {
    width: "fit-content",
    minHeight: 34,
    minWidth: 0,
    padding: "4px 0",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.34)",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(255,226,178,0.96)",
    fontSize: 14,
    fontWeight: 880,
    lineHeight: 1.25,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  actionHint: { fontSize: 12, color: "var(--text-faint)", margin: 0 },

  errorBox: {
    padding: "10px 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    fontSize: 13,
    color: "var(--warn)",
    marginBottom: 16,
  },

  distributionList: { display: "flex", flexDirection: "column", gap: 6 },
  distributionRow: {
    display: "grid",
    gridTemplateColumns: "minmax(94px, 1fr) 92px 28px",
    alignItems: "center",
    gap: 9,
  },
  distributionLabel: { fontSize: 12.5, color: "var(--text)", fontWeight: 600 },
  distributionBarTrack: {
    height: 8,
    background: "rgba(255,255,255,0.08)",
    borderRadius: 4,
    overflow: "hidden",
  },
  distributionBarFill: {
    height: "100%",
    background: "var(--accent)",
    borderRadius: 4,
    transition: "width 480ms ease-out",
  },
  distributionCount: {
    fontSize: 12,
    color: "var(--text-muted)",
    textAlign: "right",
  },
  distributionHint: {
    fontSize: 12.5,
    color: "var(--text-muted)",
    fontStyle: "italic",
    margin: "12px 0 0",
  },

  ownerSection: { marginTop: 56, paddingTop: 0 },
  visControls: { display: "flex", gap: 8, flexWrap: "wrap" },
  visBtn: {
    padding: "0 0 5px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid var(--line)",
    borderRadius: 0,
    fontSize: 13,
    color: "var(--text-muted)",
    cursor: "pointer",
  },
  visBtnActive: {
    background: "transparent",
    color: "var(--accent)",
    borderBottomColor: "var(--accent)",
  },

  roleSection: { marginTop: 24, marginBottom: 28 },
  roleHint: {
    fontSize: 13.5,
    color: "var(--text-muted)",
    margin: "0 0 14px",
    lineHeight: 1.6,
  },
  roleChooserLayout: {
    display: "grid",
    gridTemplateColumns: "minmax(220px, 0.58fr) minmax(0, 1fr)",
    gap: 28,
    alignItems: "start",
    marginTop: 2,
  },
  roleChooserLayoutCompact: {
    gridTemplateColumns: "1fr",
    gap: 8,
  },
  roleChoiceList: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
    borderTop: "none",
    minWidth: 0,
  },
  roleChoiceListCompact: {
    flexDirection: "column" as const,
    borderBottom: "none",
  },
  roleChoiceButton: {
    width: "100%",
    minWidth: 0,
    padding: "9px 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    color: "rgba(232,218,205,0.74)",
    display: "grid",
    gridTemplateColumns: "24px minmax(0, 1fr)",
    gap: 10,
    cursor: "pointer",
    fontFamily: "inherit",
    textAlign: "left" as const,
  },
  roleChoiceButtonCompact: {
    width: "100%",
    minWidth: 0,
    flex: "0 0 auto",
    padding: "10px 0",
  },
  roleChoiceButtonActive: {
    color: "rgba(255,245,230,0.98)",
    boxShadow: "none",
  },
  roleChoiceIndex: {
    color: "rgba(246,221,176,0.54)",
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: 0,
    lineHeight: 1.2,
  },
  roleChoiceIndexActive: {
    color: "rgba(255,226,178,0.94)",
  },
  roleChoiceCopy: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 5,
  },
  roleChoiceTopline: {
    minWidth: 0,
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  roleChoiceName: {
    minWidth: 0,
    flex: "0 1 auto",
    fontFamily: "var(--font-narrative)",
    fontSize: 16,
    lineHeight: 1.2,
  },
  roleChoiceSelected: {
    flexShrink: 0,
    color: "rgba(255,226,178,0.9)",
    fontSize: 10.5,
    fontWeight: 820,
    lineHeight: 1,
  },
  roleChoiceMeta: {
    color: "rgba(246,221,176,0.58)",
    fontSize: 10.5,
    lineHeight: 1.2,
    fontWeight: 750,
    whiteSpace: "nowrap" as const,
  },
  roleChoiceObjective: {
    color: "rgba(232,218,205,0.58)",
    fontSize: 12,
    lineHeight: 1.42,
    fontFamily: "var(--font-narrative)",
  },
  roleChoiceObjectiveActive: {
    color: "rgba(255,245,230,0.76)",
  },
  roleLaunchPanel: {
    marginTop: 0,
    marginBottom: 14,
    padding: "18px 0 18px",
    borderTopWidth: 1,
    borderTopStyle: "solid",
    borderTopColor: "rgba(255,255,255,0.08)",
    borderRadius: 0,
    background: "transparent",
    boxShadow: "none",
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: 10,
    alignItems: "start",
  },
  roleLaunchPanelCompact: {
    marginTop: 8,
    gap: 10,
    padding: "18px 0 18px",
  },
  roleLaunchMain: {
    minWidth: 0,
  },
  roleLaunchKicker: {
    color: "rgba(212,168,83,0.92)",
    fontSize: 11.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    marginBottom: 6,
  },
  roleLaunchTitleRow: {
    display: "flex",
    alignItems: "baseline",
    flexWrap: "wrap" as const,
    gap: 9,
  },
  roleLaunchTitle: {
    color: "rgba(255,245,230,0.98)",
    fontFamily: "var(--font-narrative)",
    fontSize: 20,
    lineHeight: 1.25,
    fontWeight: 500,
  },
  roleLaunchStat: {
    color: "rgba(246,221,176,0.72)",
    fontSize: 11.5,
    fontWeight: 700,
    whiteSpace: "nowrap" as const,
  },
  roleLaunchBrief: {
    marginTop: 0,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "stretch",
    gap: 5,
  },
  roleLaunchBriefLine: {
    margin: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 8,
    rowGap: 5,
    flexWrap: "wrap" as const,
    color: "rgba(232,218,205,0.78)",
    fontSize: 12.6,
    lineHeight: 1.45,
  },
  roleLaunchBriefLabel: {
    color: "rgba(246,221,176,0.62)",
    fontSize: 10.8,
    fontWeight: 760,
    letterSpacing: 0,
    lineHeight: 1.35,
    textTransform: "none" as const,
    flexShrink: 0,
  },
  roleLaunchBriefText: {
    minWidth: 0,
    color: "rgba(232,218,205,0.78)",
    fontFamily: "var(--font-narrative)",
    flex: "1 1 180px",
  },
  roleLaunchBriefPrivate: {
    color: "rgba(255,245,230,0.88)",
    fontWeight: 560,
  },
  roleLaunchBriefLeverage: {
    color: "rgba(255,230,184,0.86)",
  },
  roleLaunchMore: {
    paddingLeft: 0,
    color: "rgba(246,221,176,0.62)",
    fontSize: 11.5,
    fontWeight: 700,
  },
  roleLaunchActions: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "flex-start",
    justifyContent: "flex-start",
    flexWrap: "nowrap" as const,
    gap: 4,
  },
  roleLaunchActionsCompact: {
    flexDirection: "column" as const,
    alignItems: "flex-start",
  },
  roleLaunchButton: {
    alignSelf: "flex-start",
    width: "fit-content",
    minHeight: 34,
    minWidth: 0,
    padding: "4px 0",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.34)",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(255,226,178,0.96)",
    fontSize: 13.5,
    fontWeight: 880,
    lineHeight: 1.25,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap" as const,
  },
  roleLaunchHint: {
    maxWidth: 340,
    color: "var(--text-faint)",
    fontSize: 11.5,
    lineHeight: 1.4,
    textAlign: "left" as const,
  },
  roleLaunchHintCompact: {
    maxWidth: "none",
  },
}
