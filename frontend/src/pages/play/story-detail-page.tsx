import { useEffect, useState } from "react"
import { useStoryDetail } from "../../features/play/story-detail/model/use-story-detail"
import type { StoryLanguage } from "../../index"
import { isDistinctSupportCopy, pickHealthyLabel, pickHealthyText } from "../../shared/lib/story-content-quality"
import { formatMilestoneKind, formatPresentationStatusLabel, formatRuntimeProfileLabel, formatThemeLabel, formatTopologyLabel } from "../../shared/lib/story-taxonomy"
import { getDetailSurfaceTerms, getLanguageMismatchCopy } from "../../shared/lib/story-surface-copy"
import { useCompactDesktop } from "../../shared/lib/use-compact-desktop"
import { EditorialMedia } from "../../shared/ui/editorial-media"
import { StudioFooter } from "../../widgets/chrome/studio-footer"

type DetailSwitcherPanel = "topology" | "protagonist" | "cast"
type DetailWorkbenchTab = "structure" | DetailSwitcherPanel

export function StoryDetailPage({
  isAuthenticated,
  storyId,
  uiLanguage,
  onUiLanguageChange,
  onPrefetchPlaySession,
  onOpenLibrary,
  onDeleteToLibrary,
  onOpenPlaySession,
  onRequireAuth,
}: {
  isAuthenticated: boolean
  storyId: string
  uiLanguage: StoryLanguage
  onUiLanguageChange: (language: StoryLanguage) => void
  onPrefetchPlaySession: () => void
  onOpenLibrary: () => void
  onDeleteToLibrary: () => void
  onOpenPlaySession: (sessionId: string) => void
  onRequireAuth: () => void
}) {
  const detailState = useStoryDetail(storyId, uiLanguage)
  const compactDesktop = useCompactDesktop()
  const [activeWorkbenchTab, setActiveWorkbenchTab] = useState<DetailWorkbenchTab>("structure")
  const terms = getDetailSurfaceTerms(uiLanguage)

  useEffect(() => {
    onPrefetchPlaySession()
  }, [onPrefetchPlaySession])

  const handleCreatePlaySession = async () => {
    if (!isAuthenticated) {
      onRequireAuth()
      return
    }
    const sessionId = await detailState.createPlaySession()
    if (sessionId) {
      onOpenPlaySession(sessionId)
    }
  }

  const handleDeleteStory = async () => {
    const confirmed = window.confirm(
      uiLanguage === "zh"
        ? "要从你的故事库中删除这篇故事吗？这个操作无法撤销。"
        : "Delete this story from your library? This cannot be undone.",
    )
    if (!confirmed) {
      return
    }
    const deleted = await detailState.deleteStory()
    if (deleted) {
      onDeleteToLibrary()
    }
  }

  const presentation = detailState.detail?.presentation
  const playOverview = detailState.detail?.play_overview
  const storyLanguage = detailState.detail?.story.language ?? "en"
  const languageMismatch = Boolean(detailState.detail && storyLanguage !== uiLanguage)
  const mismatchCopy = getLanguageMismatchCopy({
    storyLanguage,
    surface: "detail",
    uiLanguage,
  })
  const canManageVisibility = Boolean(presentation?.viewer_can_manage)
  const localized = uiLanguage === "zh"
  const detailLabels = localized
      ? {
        overview: "概览",
        structure: "结构",
        role: terms.roleBrief,
        cast: "人物",
        playSetup: "开始试玩前",
        storyGuide: "故事导读",
        ready: "随时可进入",
        opening: "开场引导",
        premise: "故事设定",
        theme: "主题",
        tone: "语气",
        narrativeStructure: "结构提要",
        castAndRole: "人物档案",
        worldShape: "人物关系",
        protagonistRole: terms.roleBrief,
        castList: terms.castFiles,
        structureNote: "当前可见的人物关系与压力结构。",
        beatNote: "这一版故事预计会沿这些主要节拍推进。",
        noRole: "当前还没有可用的主角设定。",
        playSetupBody: "开始前先确认角色、节奏和回合上限，然后直接从这张卡片进入试玩。",
        visibility: "可见性",
        readyToPlay: terms.readyToPlay,
        playStyle: terms.sessionFrame,
        turnBudget: terms.turnCap,
        startPlay: "开始试玩",
        signInToPlay: "登录后开始试玩",
        creatingSession: "正在创建会话...",
        deleteStory: "删除故事",
        deleting: "正在删除...",
        backToLibrary: "返回故事库",
        publicStory: "公开故事",
        missingOpening: "开场文案仍在整理中，但你已经可以从本页的试玩卡片直接进入试玩。",
        missingPremise: "故事正文仍在整理中，请先查看结构与试玩入口。",
        missingTone: "语气整理中",
        missingTheme: "主题整理中",
        noStructure: "结构信息仍在整理中。",
        noCast: "人物清单仍在整理中。",
        supportingCards: "故事档案分栏",
        loadingTitle: "正在加载故事详情",
        loadingBody: "正在获取这篇故事的正文、结构和试玩入口。",
        act: "第",
        actSuffix: "幕",
        majorBeatsAhead: (count: number) => `前方还有 ${count} 个主要节拍`,
        privateVisibility: "私有",
        publicVisibility: "公开",
        sessionEntry: terms.sessionEntry,
        startPlayBodyWithOverview: "开场引导、玩法形式和回合上限都已经准备好，想开始时可以直接试玩。",
        startPlayBodySimple: "这篇故事已经可以从阅读直接切进试玩。",
        storyUnavailable: "故事不可用",
        storyUnavailableBody: "当前故事无法从你的故事库中载入。",
      }
    : {
        overview: "Overview",
        structure: "Structure",
        role: terms.roleBrief,
        cast: "Cast",
        playSetup: "Play Setup",
        storyGuide: "Story Guide",
        ready: "Ready when you are",
        opening: "Opening Framing",
        premise: "Premise",
        theme: "Theme",
        tone: "Tone",
        narrativeStructure: "Narrative Structure",
        castAndRole: "Cast Dossier",
        worldShape: "World Shape",
        protagonistRole: terms.roleBrief,
        castList: terms.castFiles,
        structureNote: "How the story connects its central people and pressures.",
        beatNote: "The opening path is sketched before live play begins.",
        noRole: "No protagonist setup is available for this story.",
        playSetupBody: "This is the handoff from reading into action. Check the role, pacing, and turn budget, then launch the session from the play card on this page.",
        visibility: "Visibility",
        readyToPlay: terms.readyToPlay,
        playStyle: terms.sessionFrame,
        turnBudget: terms.turnCap,
        startPlay: "Start Play Session",
        signInToPlay: "Sign In to Start Play",
        creatingSession: "Creating Session...",
        deleteStory: "Delete Story",
        deleting: "Deleting...",
        backToLibrary: "Back to Library",
        publicStory: "Public story",
        missingOpening: "Opening framing is still being normalized, but you can already start play from the session card on this page.",
        missingPremise: "Story copy is still being normalized. Use the structure and play setup sections for now.",
        missingTone: "Tone still normalizing",
        missingTheme: "Theme still normalizing",
        noStructure: "Structure details are still being normalized.",
        noCast: "Cast details are still being normalized.",
        supportingCards: "Story dossier sections",
        loadingTitle: "Loading story detail",
        loadingBody: "Loading the published story, structure, and play setup for this library entry.",
        act: "Act",
        actSuffix: "",
        majorBeatsAhead: (count: number) => `${count} major beats ahead`,
        privateVisibility: "Private",
        publicVisibility: "Public",
        sessionEntry: terms.sessionEntry,
        startPlayBodyWithOverview: "You have the opening framing, runtime profile, and turn budget. Start when you are ready to move from story review into action.",
        startPlayBodySimple: "This story is ready to move from story review into a live play session.",
        storyUnavailable: "Story unavailable",
        storyUnavailableBody: "This story could not be loaded from the current library.",
      }
  const safeTheme = pickHealthyLabel(
    storyLanguage,
    [detailState.detail?.story.theme],
    localized ? "故事状态" : "Story state",
  )
  const displayTheme = formatThemeLabel(safeTheme, uiLanguage)
  const safeTone = pickHealthyLabel(storyLanguage, [detailState.detail?.story.tone], detailLabels.missingTone)
  const safeStatusLabel = presentation
    ? formatPresentationStatusLabel(presentation.status, uiLanguage)
    : detailLabels.readyToPlay
  const safeRuntimeProfileLabel = playOverview
    ? formatRuntimeProfileLabel(playOverview.runtime_profile, uiLanguage)
    : detailLabels.ready
  const safeTopologyLabel = formatTopologyLabel(detailState.detail?.structure.topology_label ?? detailState.detail?.story.topology ?? "", uiLanguage)
  const safeOpening = playOverview ? pickHealthyText(storyLanguage, [playOverview.opening_narration], detailLabels.missingOpening) : null
  const safePremise = pickHealthyText(storyLanguage, [detailState.detail?.story.premise, detailState.detail?.story.one_liner], detailLabels.missingPremise)
  const supportPremise = isDistinctSupportCopy(detailState.detail?.story.one_liner, safePremise, storyLanguage)
    ? pickHealthyText(storyLanguage, [detailState.detail?.story.one_liner], "")
    : ""
  const safeMandate = playOverview ? pickHealthyText(storyLanguage, [playOverview.protagonist.mandate], "") : ""
  const safeIdentity = playOverview && isDistinctSupportCopy(playOverview.protagonist.identity_summary, safeMandate, storyLanguage)
    ? pickHealthyText(storyLanguage, [playOverview.protagonist.identity_summary], "")
    : ""
  const startCardHeadingId = "story-detail-start-card-heading"
  const structureHeadingId = "story-detail-structure-heading"
  const workbenchHeadingId = "story-detail-workbench-heading"
  const castPanelId = "story-detail-cast-panel"
  const activeCastPanel: DetailSwitcherPanel = activeWorkbenchTab === "structure" ? "topology" : activeWorkbenchTab
  const activeWorkbenchTabId = `story-detail-tab-${activeWorkbenchTab}`

  const renderCastPanel = () => {
    if (!detailState.detail) {
      return null
    }

    if (activeCastPanel === "topology") {
      return (
        <div className="detail-side-list">
          <div className="detail-side-list__item">
            <div className="detail-side-list__rule" />
            <div>
              <strong>{safeTopologyLabel}</strong>
              <p>{detailLabels.structureNote}</p>
            </div>
          </div>
          <div className="detail-side-list__item">
            <div className="detail-side-list__rule is-muted" />
            <div>
              <strong>{detailLabels.majorBeatsAhead(detailState.detail.structure.beat_outline.length)}</strong>
              <p>{detailLabels.beatNote}</p>
            </div>
          </div>
        </div>
      )
    }

    if (activeCastPanel === "protagonist") {
      return playOverview ? (
        <div className="detail-side-list detail-anchor-target" id="story-detail-role">
          <div className="detail-side-list__item">
            <div className="detail-side-list__rule" />
            <div>
              <strong>{playOverview.protagonist.title}</strong>
              <p>{safeMandate || detailLabels.missingOpening}</p>
            </div>
          </div>
          {safeIdentity ? (
            <div className="detail-side-list__item">
              <div className="detail-side-list__rule is-muted" />
              <div>
                <strong>{safeRuntimeProfileLabel}</strong>
                <p>{safeIdentity}</p>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="detail-body-copy">{detailLabels.noRole}</p>
      )
    }

    return (
      <div className="detail-manifest">
        {detailState.detail.cast_manifest.entries.length > 0 ? detailState.detail.cast_manifest.entries.map((slot) => (
          <article className={`detail-manifest__row ${slot.portrait_url ? "detail-manifest__row--with-portrait" : ""}`} key={slot.npc_id}>
            {slot.portrait_url ? (
              <EditorialMedia
                alt={slot.name}
                className="detail-manifest__portrait"
                overlay
                ratio="4 / 5"
                src={slot.portrait_url}
              />
            ) : null}
            <div className="detail-manifest__content">
              <div className="detail-manifest__header">
                <strong>{slot.name}</strong>
                <span className="detail-manifest__role">{slot.role}</span>
              </div>
              {slot.roster_character_id ? (
                <div className="detail-header__chips">
                  <span className="editorial-muted-chip">{localized ? "角色库人物" : "Roster character"}</span>
                </div>
              ) : null}
              {slot.roster_public_summary ? <p className="detail-body-copy">{slot.roster_public_summary}</p> : null}
            </div>
          </article>
        )) : <p className="detail-body-copy">{detailLabels.noCast}</p>}
      </div>
    )
  }

  const renderStructurePanel = () => (
    <div className="detail-structure-list">
      {detailState.detail?.structure.beat_outline.length ? detailState.detail.structure.beat_outline.map((beat, index) => (
        <div className="detail-structure-row" key={beat.title}>
          <div>
            <strong>
              {localized ? `${detailLabels.act}${index + 1}${detailLabels.actSuffix}：${beat.title}` : `${detailLabels.act} ${index + 1}: ${beat.title}`}
            </strong>
            <p>{beat.goal}</p>
          </div>
          <span>{formatMilestoneKind(beat.milestone_kind, uiLanguage)}</span>
        </div>
      )) : <p className="detail-body-copy">{detailLabels.noStructure}</p>}
    </div>
  )

  const renderWorkbenchPanel = () => {
    if (activeWorkbenchTab === "structure") {
      return renderStructurePanel()
    }
    return renderCastPanel()
  }

  return (
    <main className={`editorial-page editorial-page--detail ${compactDesktop ? "is-compact-desktop" : ""}`}>
      <section className={`detail-canvas ${compactDesktop ? "detail-canvas--compact" : ""}`}>
        {detailState.loading ? (
          <div className="editorial-empty-state">
            <h3>{detailLabels.loadingTitle}</h3>
            <p>{detailLabels.loadingBody}</p>
          </div>
        ) : languageMismatch ? (
          <div className="editorial-empty-state">
            <h3>{mismatchCopy.title}</h3>
            <p>{mismatchCopy.body}</p>
            <button
              className="studio-button studio-button--primary"
              onClick={() => onUiLanguageChange(storyLanguage === "zh" ? "zh" : "en")}
              type="button"
            >
              {mismatchCopy.switchAction}
            </button>
            <button className="studio-button studio-button--secondary" onClick={onOpenLibrary} type="button">
              {mismatchCopy.backAction}
            </button>
          </div>
        ) : detailState.detail ? (
          <>
            <header className="detail-header">
              <div className="detail-header__title">
                <p className="editorial-kicker">{localized ? "来自故事库" : "From the Library"}</p>
                <h1>{detailState.detail.story.title}</h1>
                <div className="detail-header__chips">
                  <span className="editorial-chip">{displayTheme}</span>
                  <span className="editorial-chip">{safeTone}</span>
                  <span className="editorial-muted-chip">{safeStatusLabel}</span>
                </div>
              </div>
            </header>

            <section className="detail-hero-grid detail-anchor-target" id="story-detail-overview">
              <div className="detail-main-column detail-main-column--overview">
                {playOverview ? (
                  <div className="detail-block detail-block--opening">
                    <h2>{detailLabels.opening}</h2>
                    <p className="detail-premise">{safeOpening}</p>
                  </div>
                ) : null}

                <div className="detail-block detail-block--premise">
                  <h2>{detailLabels.premise}</h2>
                  <p className="detail-premise">{safePremise}</p>
                  {supportPremise ? <p className="detail-body-copy">{supportPremise}</p> : null}
                </div>

                <div className="detail-split-copy">
                  <div>
                    <span className="editorial-metadata-label">{detailLabels.theme}</span>
                    <p>{displayTheme}</p>
                  </div>
                  <div>
                    <span className="editorial-metadata-label">{detailLabels.tone}</span>
                    <p>{safeTone}</p>
                  </div>
                </div>
              </div>

              <aside className="detail-side-column detail-side-column--hero">
                <section aria-labelledby={startCardHeadingId} className="detail-start-card detail-anchor-target" id="story-detail-start-play">
                  <span className="editorial-metadata-label">{detailLabels.readyToPlay}</span>
                  <div className="detail-start-card__copy">
                    <h2 id={startCardHeadingId}>{playOverview?.protagonist.title ?? detailLabels.sessionEntry}</h2>
                    <p>
                      {playOverview
                        ? detailLabels.startPlayBodyWithOverview
                        : detailLabels.startPlayBodySimple}
                    </p>
                  </div>

                  <div className="detail-start-card__meta">
                    {playOverview ? (
                      <>
                        <div>
                          <span className="editorial-metadata-label">{detailLabels.playStyle}</span>
                          <p>{safeRuntimeProfileLabel}</p>
                        </div>
                        <div>
                          <span className="editorial-metadata-label">{detailLabels.turnBudget}</span>
                          <p>{playOverview.max_turns}</p>
                        </div>
                      </>
                    ) : null}
                  </div>

                  <p className="detail-start-card__bridge">{detailLabels.playSetupBody}</p>

                  <button
                    className="studio-button studio-button--primary studio-button--wide"
                    disabled={detailState.playLoading}
                    onClick={() => void handleCreatePlaySession()}
                    onFocus={onPrefetchPlaySession}
                    onMouseEnter={onPrefetchPlaySession}
                    type="button"
                  >
                    {detailState.playLoading ? detailLabels.creatingSession : isAuthenticated ? detailLabels.startPlay : detailLabels.signInToPlay}
                  </button>

                  <div className="detail-start-card__utility">
                    {canManageVisibility ? (
                      <label className="detail-visibility-control detail-visibility-control--compact">
                        <span className="editorial-metadata-label">{detailLabels.visibility}</span>
                        <select
                          disabled={detailState.visibilityLoading}
                          onChange={(event) => {
                            void detailState.updateVisibility(event.target.value as "private" | "public")
                          }}
                          value={detailState.detail.presentation?.visibility ?? detailState.detail.story.visibility}
                        >
                          <option value="private">{detailLabels.privateVisibility}</option>
                          <option value="public">{detailLabels.publicVisibility}</option>
                        </select>
                      </label>
                    ) : null}

                    <div className="detail-start-card__actions">
                      {canManageVisibility ? (
                        <button className="studio-button studio-button--secondary" disabled={detailState.deleteLoading} onClick={() => void handleDeleteStory()} type="button">
                          {detailState.deleteLoading ? detailLabels.deleting : detailLabels.deleteStory}
                        </button>
                      ) : null}
                      <button className="studio-button studio-button--ghost" onClick={onOpenLibrary} type="button">
                        {detailLabels.backToLibrary}
                      </button>
                    </div>
                  </div>
                </section>
              </aside>
            </section>

            {compactDesktop ? (
              <section aria-labelledby={workbenchHeadingId} className="detail-cast-switcher detail-workbench detail-anchor-target" id="story-detail-workbench">
                <div className="detail-cast-switcher__header">
                  <h2 className="editorial-metadata-label detail-section-heading" id={workbenchHeadingId}>{detailLabels.storyGuide}</h2>
                  <div className="detail-cast-switcher__tabs" role="tablist" aria-label={detailLabels.supportingCards}>
                    <button
                      aria-controls={castPanelId}
                      aria-selected={activeWorkbenchTab === "structure"}
                      className={`detail-cast-switcher__tab ${activeWorkbenchTab === "structure" ? "is-active" : ""}`}
                      id="story-detail-tab-structure"
                      onClick={() => setActiveWorkbenchTab("structure")}
                      role="tab"
                      tabIndex={activeWorkbenchTab === "structure" ? 0 : -1}
                      type="button"
                    >
                      {detailLabels.structure}
                    </button>
                    <button
                      aria-controls={castPanelId}
                      aria-selected={activeWorkbenchTab === "topology"}
                      className={`detail-cast-switcher__tab ${activeWorkbenchTab === "topology" ? "is-active" : ""}`}
                      id="story-detail-tab-topology"
                      onClick={() => setActiveWorkbenchTab("topology")}
                      role="tab"
                      tabIndex={activeWorkbenchTab === "topology" ? 0 : -1}
                      type="button"
                    >
                      {detailLabels.worldShape}
                    </button>
                    <button
                      aria-controls={castPanelId}
                      aria-selected={activeWorkbenchTab === "protagonist"}
                      className={`detail-cast-switcher__tab ${activeWorkbenchTab === "protagonist" ? "is-active" : ""}`}
                      id="story-detail-tab-protagonist"
                      onClick={() => setActiveWorkbenchTab("protagonist")}
                      role="tab"
                      tabIndex={activeWorkbenchTab === "protagonist" ? 0 : -1}
                      type="button"
                    >
                      {detailLabels.protagonistRole}
                    </button>
                    <button
                      aria-controls={castPanelId}
                      aria-selected={activeWorkbenchTab === "cast"}
                      className={`detail-cast-switcher__tab ${activeWorkbenchTab === "cast" ? "is-active" : ""}`}
                      id="story-detail-tab-cast"
                      onClick={() => setActiveWorkbenchTab("cast")}
                      role="tab"
                      tabIndex={activeWorkbenchTab === "cast" ? 0 : -1}
                      type="button"
                    >
                      {detailLabels.castList}
                    </button>
                  </div>
                </div>

                <div aria-labelledby={activeWorkbenchTabId} className="detail-cast-switcher__panel detail-workbench__panel" id={castPanelId} role="tabpanel">
                  <div className="detail-cast-switcher__viewport detail-workbench__viewport">
                    <div className="detail-cast-switcher__content" key={activeWorkbenchTab}>
                      {renderWorkbenchPanel()}
                    </div>
                  </div>
                </div>
              </section>
            ) : (
              <section className="detail-module-grid">
                <section aria-labelledby={structureHeadingId} className="detail-structure-card detail-anchor-target" id="story-detail-structure">
                  <h2 className="editorial-metadata-label detail-section-heading" id={structureHeadingId}>{detailLabels.narrativeStructure}</h2>
                  {renderStructurePanel()}
                </section>

                <section aria-labelledby={workbenchHeadingId} className="detail-cast-switcher detail-anchor-target" id="story-detail-cast">
                  <div className="detail-cast-switcher__header">
                    <h2 className="editorial-metadata-label detail-section-heading" id={workbenchHeadingId}>{detailLabels.castAndRole}</h2>
                    <div className="detail-cast-switcher__tabs" role="tablist" aria-label={detailLabels.supportingCards}>
                      <button
                        aria-controls={castPanelId}
                        aria-selected={activeCastPanel === "topology"}
                        className={`detail-cast-switcher__tab ${activeCastPanel === "topology" ? "is-active" : ""}`}
                        id="story-detail-tab-topology"
                        onClick={() => setActiveWorkbenchTab("topology")}
                        role="tab"
                        tabIndex={activeCastPanel === "topology" ? 0 : -1}
                        type="button"
                      >
                        {detailLabels.worldShape}
                      </button>
                      <button
                        aria-controls={castPanelId}
                        aria-selected={activeCastPanel === "protagonist"}
                        className={`detail-cast-switcher__tab ${activeCastPanel === "protagonist" ? "is-active" : ""}`}
                        id="story-detail-tab-protagonist"
                        onClick={() => setActiveWorkbenchTab("protagonist")}
                        role="tab"
                        tabIndex={activeCastPanel === "protagonist" ? 0 : -1}
                        type="button"
                      >
                        {detailLabels.protagonistRole}
                      </button>
                      <button
                        aria-controls={castPanelId}
                        aria-selected={activeCastPanel === "cast"}
                        className={`detail-cast-switcher__tab ${activeCastPanel === "cast" ? "is-active" : ""}`}
                        id="story-detail-tab-cast"
                        onClick={() => setActiveWorkbenchTab("cast")}
                        role="tab"
                        tabIndex={activeCastPanel === "cast" ? 0 : -1}
                        type="button"
                      >
                        {detailLabels.castList}
                      </button>
                    </div>
                  </div>

                  <div aria-labelledby={`story-detail-tab-${activeCastPanel}`} className="detail-cast-switcher__panel" id={castPanelId} role="tabpanel">
                    <div className="detail-cast-switcher__viewport">
                      <div className="detail-cast-switcher__content" key={activeCastPanel}>
                        {renderCastPanel()}
                      </div>
                    </div>
                  </div>
                </section>
              </section>
            )}

            {detailState.error ? <p className="editorial-error">{detailState.error}</p> : null}
          </>
        ) : (
          <div className="editorial-empty-state">
            <h3>{detailLabels.storyUnavailable}</h3>
            <p>{detailState.error ?? detailLabels.storyUnavailableBody}</p>
            <button className="studio-button studio-button--secondary" onClick={onOpenLibrary} type="button">
              {detailLabels.backToLibrary}
            </button>
          </div>
        )}

        <StudioFooter uiLanguage={uiLanguage} />
      </section>
    </main>
  )
}
