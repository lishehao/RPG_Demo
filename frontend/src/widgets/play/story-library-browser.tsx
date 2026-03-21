import type { PublishedStoryCard, PublishedStoryListView } from "../../index"
import { StoryLibraryCard } from "../../entities/story/ui/story-library-card"
import { LibraryRail } from "../chrome/library-rail"
import { StudioFooter } from "../chrome/studio-footer"

export function StoryLibraryBrowser({
  authenticated,
  stories,
  selectedStory,
  selectedStoryId,
  query,
  theme,
  selectedTheme,
  selectedView,
  themeFacets,
  total,
  hasMore,
  loading,
  loadingMore,
  error,
  onSelectStory,
  onOpenStoryDetail,
  onOpenCreateStory,
  onThemeChange,
  onViewChange,
  onLoadMore,
}: {
  authenticated: boolean
  stories: PublishedStoryCard[]
  selectedStory: PublishedStoryCard | null
  selectedStoryId: string | null
  query: string
  theme: string | null
  selectedTheme: string | null
  selectedView: PublishedStoryListView
  themeFacets: Array<{ theme: string; count: number }>
  total: number
  hasMore: boolean
  loading: boolean
  loadingMore: boolean
  error: string | null
  onSelectStory: (storyId: string) => void
  onOpenStoryDetail: (storyId: string) => void
  onOpenCreateStory: () => void
  onThemeChange: (theme: string | null) => void
  onViewChange: (view: PublishedStoryListView) => void
  onLoadMore: () => void
}) {
  const hasActiveFilters = query.length > 0 || Boolean(theme)
  const viewLabel =
    selectedView === "mine"
      ? "my stories"
      : selectedView === "public"
        ? "public stories"
        : "stories visible to me"
  const createLabel = authenticated ? "New Dossier" : "Sign In to Create"

  return (
    <div className="editorial-page editorial-page--library">
      <div className="library-layout">
        <LibraryRail />

        <section className="library-content">
          <header className="library-header">
            <div>
              <p className="editorial-kicker">The Collections</p>
              <h1 className="editorial-display editorial-display--library">Library</h1>
              <p className="library-subtitle">A curated repository of speculative worlds, character studies, and structural narrative dossiers.</p>
            </div>

            <div className="library-controls">
              <label className="library-filter">
                <span className="editorial-metadata-label">View</span>
                <select
                  onChange={(event) => onViewChange(event.target.value as PublishedStoryListView)}
                  value={selectedView}
                >
                  {authenticated ? <option value="accessible">Accessible</option> : null}
                  {authenticated ? <option value="mine">Mine</option> : null}
                  <option value="public">Public</option>
                </select>
              </label>
              <label className="library-filter">
                <span className="editorial-metadata-label">Filter by Theme</span>
                <select
                  onChange={(event) => onThemeChange(event.target.value || null)}
                  value={selectedTheme ?? ""}
                >
                  <option value="">All Themes</option>
                  {themeFacets.map((facet) => (
                    <option key={facet.theme} value={facet.theme}>
                      {facet.theme} ({facet.count})
                    </option>
                  ))}
                </select>
              </label>

              <button className="studio-button studio-button--primary" onClick={onOpenCreateStory} type="button">
                {createLabel}
              </button>
            </div>
          </header>

          {error ? <p className="editorial-error">{error}</p> : null}
          {!loading ? (
            <div className="library-results-meta">
              <p className="editorial-metadata-label">Results: {total}</p>
              <p className="library-results-meta__summary">Showing {viewLabel}</p>
              {hasActiveFilters ? (
                <div className="detail-header__chips">
                  {query ? <span className="editorial-muted-chip">Query: {query}</span> : null}
                  {theme ? <span className="editorial-chip">{theme}</span> : null}
                  <span className="editorial-muted-chip">View: {selectedView}</span>
                </div>
              ) : null}
            </div>
          ) : null}

          {loading ? (
            <div className="editorial-empty-state">
              <h3>Loading library</h3>
              <p>Fetching published stories from the library.</p>
            </div>
          ) : stories.length === 0 ? (
            <div className="editorial-empty-state">
              <h3>
                {hasActiveFilters
                  ? "No stories match the current library search"
                  : selectedView === "mine"
                    ? "No owned stories yet"
                    : selectedView === "public"
                      ? "No public stories available"
                      : "No visible stories yet"}
              </h3>
              <p>
                {hasActiveFilters
                  ? "Try a different keyword, change the view, or clear the active theme filter."
                  : !authenticated
                    ? "Sign in to create and manage your own stories. Public stories remain visible while logged out."
                    : selectedView === "mine"
                    ? "Publish a story under this account to build your private and public library."
                    : selectedView === "public"
                      ? "No public stories are visible to this account right now."
                      : "This account does not currently have any visible stories."}
              </p>
            </div>
          ) : (
            <>
              <div className="library-grid">
                {stories.map((story) => (
                  <StoryLibraryCard
                    key={story.story_id}
                    onSelect={() => {
                      onSelectStory(story.story_id)
                      onOpenStoryDetail(story.story_id)
                    }}
                    selected={selectedStoryId === story.story_id}
                    story={story}
                  />
                ))}

                <button className="library-placeholder-card" onClick={onOpenCreateStory} type="button">
                  <span className="material-symbols-outlined">note_add</span>
                  <span>{authenticated ? "Initiate New Narrative Chain" : "Sign In to Initiate a Narrative Chain"}</span>
                </button>
              </div>

              {hasMore ? (
                <div className="library-pagination">
                  <button className="studio-button studio-button--secondary" disabled={loadingMore} onClick={onLoadMore} type="button">
                    {loadingMore ? "Loading More..." : "Load More from Library"}
                  </button>
                </div>
              ) : null}
            </>
          )}

          <StudioFooter />
        </section>
      </div>
    </div>
  )
}
