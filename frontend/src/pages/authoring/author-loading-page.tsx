import { useState } from "react"
import { useAuthorLoading } from "../../features/authoring/loading/model/use-author-loading"
import type { StoryVisibility } from "../../index"
import { AuthorLoadingDashboard } from "../../widgets/authoring/author-loading-dashboard"

export function AuthorLoadingPage({
  jobId,
  onOpenCreateStory,
  onOpenLibrary,
}: {
  jobId: string
  onOpenCreateStory: () => void
  onOpenLibrary: (storyId: string) => void
}) {
  const loading = useAuthorLoading(jobId)
  const [publishVisibility, setPublishVisibility] = useState<StoryVisibility>("private")

  const handlePublish = async () => {
    const storyId = await loading.publishStory(publishVisibility)
    if (storyId) {
      onOpenLibrary(storyId)
    }
  }

  return (
    <main className="editorial-page-shell">
      <AuthorLoadingDashboard
        activeCard={loading.activeCard}
        cardPool={loading.cardPool}
        completionPercent={loading.completionPercent}
        error={loading.error}
        job={loading.job}
        onPublishVisibilityChange={setPublishVisibility}
        onPublish={() => {
          void handlePublish()
        }}
        publishVisibility={publishVisibility}
        publishLoading={loading.publishLoading}
        result={loading.result}
      />
    </main>
  )
}
