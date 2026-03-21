import { useStoryLibrary } from "../../features/play/library/model/use-story-library"
import type { PublishedStoryListView } from "../../index"
import { StoryLibraryBrowser } from "../../widgets/play/story-library-browser"

export function StoryLibraryPage({
  authenticated,
  initialStoryId,
  searchQuery,
  selectedTheme,
  selectedView,
  onOpenCreateStory,
  onRequireAuth,
  onOpenStoryDetail,
  onThemeChange,
  onViewChange,
}: {
  authenticated: boolean
  initialStoryId?: string
  searchQuery?: string
  selectedTheme?: string | null
  selectedView?: PublishedStoryListView
  onOpenCreateStory: () => void
  onRequireAuth: () => void
  onOpenStoryDetail: (storyId: string) => void
  onThemeChange: (theme: string | null) => void
  onViewChange: (view: PublishedStoryListView) => void
}) {
  const library = useStoryLibrary(initialStoryId, searchQuery, selectedTheme, selectedView ?? "accessible")

  return (
    <main className="editorial-page-shell">
      <StoryLibraryBrowser
        authenticated={authenticated}
        error={library.error}
        hasMore={library.hasMore}
        loading={library.loading}
        loadingMore={library.loadingMore}
        onLoadMore={() => {
          void library.loadMore()
        }}
        onOpenCreateStory={authenticated ? onOpenCreateStory : onRequireAuth}
        onOpenStoryDetail={onOpenStoryDetail}
        onSelectStory={library.selectStory}
        onThemeChange={onThemeChange}
        onViewChange={onViewChange}
        query={library.query}
        selectedStory={library.selectedStory}
        selectedStoryId={library.selectedStoryId}
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
