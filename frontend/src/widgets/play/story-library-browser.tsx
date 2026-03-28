import { useEffect, useRef, useState } from "react"
import type { PublishedStoryCard, PublishedStoryListView, StoryLanguage } from "../../index"
import { StoryLibraryCard } from "../../entities/story/ui/story-library-card"
import { formatThemeLabel } from "../../shared/lib/story-taxonomy"
import { uiText } from "../../shared/lib/ui-language"
import { getLibraryEmptyStateCopy, getLibraryResultsSummary, getLibraryViewOptionLabel } from "../../shared/lib/story-surface-copy"
import { StudioIcon } from "../../shared/ui/studio-icon"
import { StudioFooter } from "../chrome/studio-footer"

const LIBRARY_SEARCH_DEBOUNCE_MS = 280

export function StoryLibraryBrowser({
  authenticated,
  uiLanguage,
  stories,
  query,
  theme,
  selectedTheme,
  selectedView,
  themeFacets,
  total,
  hasMore,
  loading,
  refreshing,
  loadingMore,
  error,
  onOpenStoryDetail,
  onOpenCreateStory,
  onPrefetchCreateStory,
  onPrefetchStoryDetail,
  onSearchChange,
  onThemeChange,
  onViewChange,
  onLoadMore,
}: {
  authenticated: boolean
  uiLanguage: StoryLanguage
  stories: PublishedStoryCard[]
  query: string
  theme: string | null
  selectedTheme: string | null
  selectedView: PublishedStoryListView
  themeFacets: Array<{ theme: string; count: number }>
  total: number
  hasMore: boolean
  loading: boolean
  refreshing: boolean
  loadingMore: boolean
  error: string | null
  onOpenStoryDetail: (storyId: string) => void
  onOpenCreateStory: () => void
  onPrefetchCreateStory: () => void
  onPrefetchStoryDetail: (storyId: string) => void
  onSearchChange: (value: string) => void
  onThemeChange: (theme: string | null, queryOverride?: string) => void
  onViewChange: (view: PublishedStoryListView, queryOverride?: string) => void
  onLoadMore: () => void
}) {
  const [draftQuery, setDraftQuery] = useState(query)
  const [isComposing, setIsComposing] = useState(false)
  const debounceRef = useRef<number | null>(null)
  const hasActiveFilters = query.length > 0 || Boolean(theme)
  const viewLabel =
    getLibraryResultsSummary(selectedView, uiLanguage, uiLanguage)
  const emptyStateCopy = getLibraryEmptyStateCopy({
    authenticated,
    hasActiveFilters,
    language: uiLanguage,
    uiLanguage,
    view: selectedView,
  })
  const createLabel = authenticated ? uiText(uiLanguage, { en: "Create Story", zh: "新建故事" }) : uiText(uiLanguage, { en: "Sign In to Create", zh: "登录后创作" })
  const controlsHeading = uiText(uiLanguage, { en: "Pick a story", zh: "先选一篇故事" })
  const controlsSupport = uiText(uiLanguage, {
    en: "Search first, then narrow by shelf and theme.",
    zh: "先搜索，再按范围和主题收窄。",
  })
  const refreshingLabel = uiText(uiLanguage, { en: "Updating results", zh: "正在更新结果" })

  useEffect(() => {
    setDraftQuery(query)
  }, [query])

  useEffect(() => {
    if (isComposing || draftQuery === query) {
      return
    }
    debounceRef.current = window.setTimeout(() => {
      onSearchChange(draftQuery)
    }, LIBRARY_SEARCH_DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) {
        window.clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
    }
  }, [draftQuery, isComposing, onSearchChange, query])

  const flushDraftQuery = (nextValue: string) => {
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    if (nextValue !== query) {
      onSearchChange(nextValue)
    }
  }

  return (
    <div className="editorial-page editorial-page--library">
      <div className="library-layout">
        <section className="library-content">
          <header className="library-header">
            <div>
              <p className="editorial-kicker">{uiText(uiLanguage, { en: "The Collections", zh: "故事集合" })}</p>
              <h1 className="editorial-display editorial-display--library">{uiText(uiLanguage, { en: "Library", zh: "故事库" })}</h1>
              <p className="library-subtitle">{uiText(uiLanguage, { en: "Browse published stories, revisit your private work, and move straight into play when a world is ready.", zh: "浏览已发布故事，查看自己的作品，并在准备好时直接进入试玩。" })}</p>
            </div>

            <section aria-labelledby="library-controls-heading" className="library-controls">
              <div className="library-controls__header">
                <p className="editorial-metadata-label">{controlsHeading}</p>
                <p className="library-controls__support" id="library-controls-heading">{controlsSupport}</p>
              </div>
              <label className="library-search-inline">
                <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "Search", zh: "搜索" })}</span>
                <div className="library-search-inline__field">
                  <StudioIcon className="library-search-inline__icon" name="search" />
                  <input
                    onBlur={() => {
                      if (!isComposing) {
                        flushDraftQuery(draftQuery)
                      }
                    }}
                    onChange={(event) => {
                      setDraftQuery(event.target.value)
                    }}
                    onCompositionEnd={(event) => {
                      setIsComposing(false)
                      setDraftQuery(event.currentTarget.value)
                    }}
                    onCompositionStart={() => {
                      if (debounceRef.current) {
                        window.clearTimeout(debounceRef.current)
                        debounceRef.current = null
                      }
                      setIsComposing(true)
                    }}
                    placeholder={uiText(uiLanguage, { en: "Search library...", zh: "搜索故事库..." })}
                    type="text"
                    value={draftQuery}
                  />
                </div>
              </label>
              <div className="library-controls__filters">
                <label className="library-filter">
                  <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "View", zh: "视图" })}</span>
                  <select
                    onChange={(event) => onViewChange(event.target.value as PublishedStoryListView, draftQuery)}
                    value={selectedView}
                  >
                    {authenticated ? <option value="accessible">{getLibraryViewOptionLabel("accessible", uiLanguage)}</option> : null}
                    {authenticated ? <option value="mine">{getLibraryViewOptionLabel("mine", uiLanguage)}</option> : null}
                    <option value="public">{getLibraryViewOptionLabel("public", uiLanguage)}</option>
                  </select>
                </label>
                <label className="library-filter">
                  <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "Filter by Theme", zh: "按主题筛选" })}</span>
                  <select
                    onChange={(event) => onThemeChange(event.target.value || null, draftQuery)}
                    value={selectedTheme ?? ""}
                  >
                    <option value="">{uiText(uiLanguage, { en: "All Themes", zh: "全部主题" })}</option>
                    {themeFacets.map((facet) => (
                      <option key={facet.theme} value={facet.theme}>
                        {formatThemeLabel(facet.theme, uiLanguage)} ({facet.count})
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <button
                className="studio-button studio-button--primary"
                onClick={onOpenCreateStory}
                onFocus={onPrefetchCreateStory}
                onMouseEnter={onPrefetchCreateStory}
                type="button"
              >
                {createLabel}
              </button>
            </section>
          </header>

          {error ? <p className="editorial-error">{error}</p> : null}
          {!loading ? (
            <div className="library-results-meta">
              <p className="editorial-metadata-label">
                {uiText(uiLanguage, {
                  en: `${total} ${total === 1 ? "story" : "stories"}`,
                  zh: `共 ${total} 篇`,
                })}
              </p>
              <p className="library-results-meta__summary">{viewLabel}</p>
              {refreshing ? <span className="editorial-badge is-loading">{refreshingLabel}</span> : null}
              <div className="detail-header__chips">
                {selectedView === "mine" ? <span className="editorial-muted-chip">{uiText(uiLanguage, { en: "Private and published stories under this account", zh: "这个账号下的私有与已发布故事" })}</span> : null}
                {query ? <span className="editorial-muted-chip">{uiText(uiLanguage, { en: `Query: ${query}`, zh: `搜索：${query}` })}</span> : null}
                {theme ? <span className="editorial-chip">{formatThemeLabel(theme, uiLanguage)}</span> : null}
              </div>
            </div>
          ) : null}

          {loading ? (
            <div className="editorial-empty-state">
              <h3>{uiText(uiLanguage, { en: "Loading library", zh: "正在加载故事库" })}</h3>
              <p>{uiText(uiLanguage, { en: "Loading stories and filters for the current library view.", zh: "正在加载当前语言和视图下的故事与筛选项。" })}</p>
            </div>
          ) : stories.length === 0 ? (
            <div className="editorial-empty-state">
              <h3>{emptyStateCopy.title}</h3>
              <p>{emptyStateCopy.body}</p>
            </div>
          ) : (
            <>
              <div className="library-grid">
                {stories.map((story) => (
                  <StoryLibraryCard
                    key={story.story_id}
                    onSelect={() => onOpenStoryDetail(story.story_id)}
                    onPrefetch={() => onPrefetchStoryDetail(story.story_id)}
                    story={story}
                    uiLanguage={uiLanguage}
                  />
                ))}
              </div>

              {hasMore ? (
                <div className="library-pagination">
                  <button className="studio-button studio-button--secondary" disabled={loadingMore} onClick={onLoadMore} type="button">
                    {loadingMore ? uiText(uiLanguage, { en: "Loading More...", zh: "加载更多中..." }) : uiText(uiLanguage, { en: "Load More from Library", zh: "加载更多故事" })}
                  </button>
                </div>
              ) : null}
            </>
          )}

          <StudioFooter uiLanguage={uiLanguage} />
        </section>
      </div>
    </div>
  )
}
