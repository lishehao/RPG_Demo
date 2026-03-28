import { useState } from "react"
import { useAuthorCopilot } from "../../features/authoring/copilot/model/use-author-copilot"
import { useAuthorLoading } from "../../features/authoring/loading/model/use-author-loading"
import type { StoryLanguage, StoryVisibility } from "../../index"
import { AuthorLoadingDashboard } from "../../widgets/authoring/author-loading-dashboard"

export function AuthorLoadingPage({
  jobId,
  uiLanguage,
  onOpenStoryDetail,
}: {
  jobId: string
  uiLanguage: StoryLanguage
  onOpenStoryDetail: (storyId: string) => void
}) {
  const loading = useAuthorLoading(jobId, uiLanguage)
  const copilot = useAuthorCopilot(jobId, Boolean(loading.result?.summary) && loading.result?.publishable !== false, {
    onApplied: async () => {
      await loading.refreshCompletedState()
    },
    onUndone: async () => {
      await loading.refreshCompletedState()
    },
    uiLanguage,
  })
  const [publishVisibility, setPublishVisibility] = useState<StoryVisibility>("private")

  const handlePublish = async () => {
    const storyId = await loading.publishStory(publishVisibility)
    if (storyId) {
      onOpenStoryDetail(storyId)
    }
  }

  return (
    <main className="editorial-page-shell">
      <AuthorLoadingDashboard
        activeCard={loading.activeCard}
        cardPool={loading.cardPool}
        completionPercent={loading.completionPercent}
        copilot={copilot}
        error={loading.error}
        job={loading.job}
        onPublishVisibilityChange={setPublishVisibility}
        onPublish={() => {
          void handlePublish()
        }}
        publishVisibility={publishVisibility}
        publishLoading={loading.publishLoading}
        result={loading.result}
        uiLanguage={uiLanguage}
      />
    </main>
  )
}
