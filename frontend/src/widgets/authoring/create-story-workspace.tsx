import type { FormEvent } from "react"
import type { AuthorPreviewResponse, StoryLanguage } from "../../index"
import { formatThemeLabel } from "../../shared/lib/story-taxonomy"
import { uiText } from "../../shared/lib/ui-language"
import { isPreviewOutputHealthy, pickHealthyLabel, pickHealthyText } from "../../shared/lib/story-content-quality"
import { getCreateSurfaceCopy } from "../../shared/lib/story-surface-copy"
import { StudioIcon } from "../../shared/ui/studio-icon"
import { StreamingText } from "../../shared/ui/streaming-text"
import { StudioFooter } from "../chrome/studio-footer"

export function CreateStoryWorkspace({
  seed,
  uiLanguage,
  language,
  preview,
  previewLoading,
  sparkLoading,
  sparkRevealActive,
  sparkRevealVisibleText,
  jobLoading,
  error,
  onSeedChange,
  onRequestSpark,
  onRequestPreview,
  onCreateAuthorJob,
  onPrefetchAuthorLoading,
  onOpenLibrary,
}: {
  seed: string
  uiLanguage: StoryLanguage
  language: StoryLanguage
  preview: AuthorPreviewResponse | null
  previewLoading: boolean
  sparkLoading: boolean
  sparkRevealActive: boolean
  sparkRevealVisibleText: string
  jobLoading: boolean
  error: string | null
  onSeedChange: (value: string) => void
  onRequestSpark: () => void
  onRequestPreview: () => void
  onCreateAuthorJob: () => void
  onPrefetchAuthorLoading: () => void
  onOpenLibrary: () => void
}) {
  const copy = getCreateSurfaceCopy(uiLanguage)
  const sparkBusy = sparkLoading || sparkRevealActive
  const sparkButtonLabel = sparkBusy
    ? copy.sparkLoading
    : seed.trim().length > 0
      ? copy.sparkAgain
      : copy.sparkAction
  const previewHealthy = isPreviewOutputHealthy(preview)
  const primaryActionLabel = preview
    ? previewHealthy
      ? jobLoading
        ? uiText(uiLanguage, { en: "Generating Draft...", zh: "正在生成草稿..." })
        : uiText(uiLanguage, { en: "Generate Draft", zh: "生成草稿" })
      : previewLoading
        ? uiText(uiLanguage, { en: "Generating Preview...", zh: "正在生成预览..." })
        : uiText(uiLanguage, { en: "Refresh Preview", zh: "刷新预览" })
    : previewLoading
      ? uiText(uiLanguage, { en: "Generating Preview...", zh: "正在生成预览..." })
      : uiText(uiLanguage, { en: "Generate Preview", zh: "生成预览" })
  const primaryActionType: "button" | "submit" = preview && previewHealthy ? "button" : "submit"
  const healthyPremise = preview
    ? pickHealthyText(language, [preview.story.premise], uiText(uiLanguage, { en: "Preview needs cleanup before you can continue to authoring.", zh: "预览仍需整理，暂时不能继续生成故事。" }))
    : uiText(uiLanguage, { en: "Generate a preview to see what kind of story this seed becomes.", zh: "先生成一个预览，看看这个种子会被展开成怎样的故事。" })
  const healthyTone = preview && previewHealthy
    ? pickHealthyLabel(language, [preview.story.tone], uiText(uiLanguage, { en: "Preview still normalizing", zh: "预览整理中" }))
    : uiText(uiLanguage, { en: "Pending", zh: "待生成" })
  const healthyTheme = preview && previewHealthy
    ? formatThemeLabel(
        pickHealthyLabel(language, [preview.flashcards.find((card) => card.card_id === "theme")?.value], uiText(uiLanguage, { en: "Preview still normalizing", zh: "预览整理中" })),
        uiLanguage,
      )
    : uiText(uiLanguage, { en: "Pending", zh: "待生成" })
  const themeSignal = preview && previewHealthy ? healthyTheme : uiText(uiLanguage, { en: "Preview still normalizing", zh: "预览整理中" })
  const previewCastSlots = preview?.cast_slots ?? []
  const previewReady = Boolean(preview && previewHealthy)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (sparkRevealActive) {
      return
    }
    onRequestPreview()
  }

  const handleSpark = () => {
    if (sparkRevealActive) {
      return
    }
    if ((seed.trim().length > 0 || preview !== null) && !window.confirm(copy.sparkOverwriteConfirm)) {
      return
    }
    onRequestSpark()
  }

  return (
    <div className="editorial-page editorial-page--create">
      <div className="create-layout">
        <section className="create-main">
          <p className="editorial-kicker">{uiText(uiLanguage, { en: "New Project", zh: "新建项目" })}</p>
          <h1 className="editorial-display">{uiText(uiLanguage, { en: "Start with a story seed", zh: "从一个故事种子开始" })}</h1>

          <form className="create-form" onSubmit={handleSubmit}>
            <div className="create-spark-bar">
              <div className="create-spark-bar__copy">
                <span className="editorial-metadata-label">{copy.sparkLabel}</span>
                <p className="create-seed-help">{copy.sparkSupport}</p>
              </div>
              <button
                className="studio-button studio-button--secondary"
                disabled={sparkBusy || previewLoading || jobLoading}
                onClick={handleSpark}
                type="button"
              >
                {sparkButtonLabel}
              </button>
            </div>
            <div className={`create-seed-shell ${sparkRevealActive ? "is-revealing" : ""}`}>
              <textarea
                aria-label={uiText(uiLanguage, { en: "Story Seed", zh: "故事种子" })}
                className="create-seed-input"
                id="story-seed-input"
                onChange={(event) => onSeedChange(event.target.value)}
                placeholder={uiText(uiLanguage, {
                  en: "Example: A bridge superintendent discovers ration convoy diversions were staged to justify emergency command powers.",
                  zh: "示例：一名港口检查官发现检疫扣押其实是为了操纵紧急表决，于是必须在港区分裂前把证据公开。",
                })}
                readOnly={sparkRevealActive}
                rows={6}
                value={seed}
              />
              {sparkRevealActive ? (
                <div aria-hidden="true" className="create-seed-overlay">
                  {sparkRevealVisibleText}
                  <span className="streaming-text__cursor" />
                </div>
              ) : null}
            </div>

            <div className={`create-actions ${previewReady ? "is-preview-ready" : ""}`}>
              <button
                className="studio-button studio-button--primary"
                disabled={sparkBusy || (preview ? (previewHealthy ? jobLoading : previewLoading) : previewLoading)}
                onClick={preview && previewHealthy ? onCreateAuthorJob : undefined}
                onFocus={preview && previewHealthy ? onPrefetchAuthorLoading : undefined}
                onMouseEnter={preview && previewHealthy ? onPrefetchAuthorLoading : undefined}
                type={primaryActionType}
              >
                {primaryActionLabel}
              </button>
              <button
                className={`studio-button ${previewReady ? "studio-button--ghost" : "studio-button--secondary"}`}
                onClick={previewReady ? () => onRequestPreview() : onOpenLibrary}
                type="button"
              >
                {previewReady
                  ? uiText(uiLanguage, { en: "Refresh Preview", zh: "刷新预览" })
                  : uiText(uiLanguage, { en: "Browse Library", zh: "浏览故事库" })}
              </button>
            </div>
            {previewReady ? (
              <div className="create-actions__aux">
                <button className="studio-button studio-button--ghost" onClick={onOpenLibrary} type="button">
                  {uiText(uiLanguage, { en: "Browse Library", zh: "浏览故事库" })}
                </button>
              </div>
            ) : null}

            {error ? <p className="editorial-error">{error}</p> : null}
            {preview && !previewHealthy ? (
              <p className="editorial-error">{uiText(uiLanguage, { en: "Preview needs cleanup before authoring. Refresh it instead of starting the job.", zh: "预览还不够稳定，请先刷新预览，不要直接开始生成。" })}</p>
            ) : null}
          </form>

          <div className="create-footnotes">
            <div>
              <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "What makes a strong seed", zh: "什么样的种子更有效" })}</span>
              <p>{uiText(uiLanguage, { en: "Name the pressure, who must act, and what could break if they fail. Two clear sentences are enough.", zh: "写清楚压力是什么、谁必须行动、如果失败会坏掉什么。两句清楚的话就够了。" })}</p>
            </div>
            <div>
              <span className="editorial-metadata-label">{copy.whatHappensNext}</span>
              <p>{uiText(uiLanguage, { en: "We turn the seed into a quick preview first, then expand it into a full draft that opens directly in Author Copilot before publish.", zh: "系统会先把种子扩成一个快速预览，再生成完整草稿，并直接进入 Author Copilot 继续修改后再发布。" })}</p>
            </div>
          </div>
        </section>

        <aside className="create-preview-pane">
          <div className="create-preview-pane__header">
            <h2>{copy.previewHeading}</h2>
            <div className="create-preview-pane__badges">
              <span className={`editorial-badge ${previewLoading ? "is-loading" : preview ? "is-ready" : ""}`}>
                {previewLoading
                  ? uiText(uiLanguage, { en: "Generating", zh: "生成中" })
                  : preview
                    ? uiText(uiLanguage, { en: "Preview Ready", zh: "预览已生成" })
                    : copy.awaitingInput}
              </span>
            </div>
          </div>

          <div className={`preview-card ${previewLoading ? "is-loading" : ""}`}>
            <div className="preview-title-lockup">
              <div className="preview-title-lockup__rule" />
              <div>
                <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "Working Title", zh: "暂定标题" })}</span>
                <h3>
                  {previewLoading && !preview ? (
                    uiText(uiLanguage, { en: "Building the story", zh: "正在搭建故事" })
                  ) : preview?.story.title && previewHealthy ? (
                    <StreamingText delayMs={80} speedMs={18} text={preview.story.title} variant="headline" />
                  ) : preview?.story.title ? (
                    uiText(uiLanguage, { en: "Preview needs cleanup", zh: "预览仍需整理" })
                  ) : (
                    uiText(uiLanguage, { en: "No story drafted yet", zh: "还没有生成故事" })
                  )}
                </h3>
              </div>
            </div>

            {previewLoading ? (
              <div className="preview-loading-shell" aria-hidden="true">
                <span className="preview-loading-shell__line preview-loading-shell__line--lead" />
                <span className="preview-loading-shell__line preview-loading-shell__line--body" />
                <span className="preview-loading-shell__line preview-loading-shell__line--body" />
                <span className="preview-loading-shell__line preview-loading-shell__line--tail" />
                <div className="preview-loading-shell__grid">
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            ) : (
              <>
                <div className="preview-detail-list">
                  <div>
                    <span className="editorial-metadata-label">{copy.premiseArchetype}</span>
                    <p>{preview?.story.premise && previewHealthy ? <StreamingText delayMs={140} speedMs={8} text={healthyPremise} variant="body" /> : healthyPremise}</p>
                  </div>
                  <div>
                    <span className="editorial-metadata-label">{copy.toneProfile}</span>
                    <p>{healthyTone}</p>
                  </div>
                </div>

                <div className="preview-stat-grid preview-stat-grid--minimal">
                  <div>
                    <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "Core Theme", zh: "核心主题" })}</span>
                    <p>{healthyTheme}</p>
                  </div>
                </div>

                {previewCastSlots.length > 0 ? (
                  <div className="preview-cast-section">
                    <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "Cast Sketch", zh: "角色草图" })}</span>
                    <div className="preview-cast-grid">
                      {previewCastSlots.map((slot, index) => (
                        <article className="preview-cast-card" key={`${slot.slot_label}-${index}`}>
                          <div className="preview-cast-card__copy">
                            {slot.name ? <strong>{slot.name}</strong> : null}
                            <span>{slot.public_role}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            )}

            <p className="preview-footnote">
              {uiText(uiLanguage, {
                en: "* This preview is a lightweight sketch. The full draft opens in Author Copilot once generation begins.",
                zh: "* 这只是一个轻量预览。开始正式生成后，完整草稿会直接进入 Author Copilot。",
              })}
            </p>
          </div>

          <div className="editorial-note">
            <StudioIcon name="history_edu" />
            <p>
              {copy.themeSignal} <span>{preview ? themeSignal : copy.noThemeSignal}</span>
            </p>
          </div>
        </aside>
      </div>

      <StudioFooter uiLanguage={uiLanguage} />
    </div>
  )
}
