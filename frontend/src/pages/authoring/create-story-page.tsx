import type { StoryLanguage } from "../../index"
import { useCreateStoryFlow } from "../../features/authoring/create-story/model/use-create-story-flow"
import { CreateStoryWorkspace } from "../../widgets/authoring/create-story-workspace"

export function CreateStoryPage({
  uiLanguage,
  onOpenAuthorJob,
  onOpenLibrary,
  onPrefetchAuthorLoading,
  onDraftStateChange,
}: {
  uiLanguage: StoryLanguage
  onOpenAuthorJob: (jobId: string) => void
  onOpenLibrary: () => void
  onPrefetchAuthorLoading: () => void
  onDraftStateChange: (isDirty: boolean) => void
}) {
  const flow = useCreateStoryFlow(uiLanguage, uiLanguage, onDraftStateChange)

  const handleCreateAuthorJob = async () => {
    const jobId = await flow.createAuthorJob()
    if (jobId) {
      onOpenAuthorJob(jobId)
    }
  }

  return (
    <main className="editorial-page-shell">
      <CreateStoryWorkspace
        error={flow.error}
        jobLoading={flow.jobLoading}
        sparkRevealActive={flow.sparkRevealActive}
        sparkRevealVisibleText={flow.sparkRevealVisibleText}
        sparkLoading={flow.sparkLoading}
        onCreateAuthorJob={() => {
          void handleCreateAuthorJob()
        }}
        onPrefetchAuthorLoading={onPrefetchAuthorLoading}
        onRequestSpark={() => {
          void flow.requestSpark()
        }}
        onRequestPreview={() => {
          void flow.requestPreview()
        }}
        uiLanguage={uiLanguage}
        onSeedChange={flow.updateSeed}
        language={flow.language}
        preview={flow.preview}
        previewLoading={flow.previewLoading}
        seed={flow.seed}
        onOpenLibrary={onOpenLibrary}
      />
    </main>
  )
}
