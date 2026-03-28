import { useStoryLibrary } from "../../features/play/library/model/use-story-library"
import type { PublishedStoryListView, StoryLanguage } from "../../index"
import { StoryLibraryBrowser } from "../../widgets/play/story-library-browser"

export function StoryLibraryPage({
  authenticated,
  uiLanguage,
  searchQuery,
  selectedTheme,
  selectedView,
  onOpenCreateStory,
  onPrefetchCreateStory,
  onPrefetchStoryDetail,
  onRequireAuth,
  onOpenStoryDetail,
  onSearchChange,
  onThemeChange,
  onViewChange,
}: {
  authenticated: boolean
  uiLanguage: StoryLanguage
  searchQuery?: string
  selectedTheme?: string | null
  selectedView?: PublishedStoryListView
  onOpenCreateStory: () => void
  onPrefetchCreateStory: () => void
  onPrefetchStoryDetail: (storyId: string) => void
  onRequireAuth: () => void
  onOpenStoryDetail: (storyId: string) => void
  onSearchChange: (value: string) => void
  onThemeChange: (theme: string | null, queryOverride?: string) => void
  onViewChange: (view: PublishedStoryListView, queryOverride?: string) => void
}) {
  const library = useStoryLibrary(uiLanguage, searchQuery, selectedTheme, selectedView ?? "accessible")

  return (
    <main className="editorial-page-shell">
      <StoryLibraryBrowser
        authenticated={authenticated}
        uiLanguage={uiLanguage}
        error={library.error}
        hasMore={library.hasMore}
        loading={library.loading}
        refreshing={library.refreshing}
        loadingMore={library.loadingMore}
        onLoadMore={() => {
          void library.loadMore()
        }}
        onOpenCreateStory={authenticated ? onOpenCreateStory : onRequireAuth}
        onOpenStoryDetail={onOpenStoryDetail}
        onPrefetchCreateStory={onPrefetchCreateStory}
        onPrefetchStoryDetail={onPrefetchStoryDetail}
        onSearchChange={onSearchChange}
        onThemeChange={onThemeChange}
        onViewChange={onViewChange}
        query={searchQuery ?? library.query}
        selectedTheme={selectedTheme ?? null}
        selectedView={selectedView ?? "accessible"}
        stories={library.stories}
        theme={library.theme}
        themeFacets={library.themeFacets}
        total={library.total}
      />
    </main>
  )
}
