import { useCreateStoryFlow } from "../../features/authoring/create-story/model/use-create-story-flow"
import { CreateStoryWorkspace } from "../../widgets/authoring/create-story-workspace"

export function CreateStoryPage({
  onOpenAuthorJob,
  onOpenLibrary,
}: {
  onOpenAuthorJob: (jobId: string) => void
  onOpenLibrary: () => void
}) {
  const flow = useCreateStoryFlow()

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
        onCreateAuthorJob={() => {
          void handleCreateAuthorJob()
        }}
        onRequestPreview={() => {
          void flow.requestPreview()
        }}
        onSeedChange={flow.updateSeed}
        preview={flow.preview}
        previewLoading={flow.previewLoading}
        seed={flow.seed}
        onOpenLibrary={onOpenLibrary}
      />
    </main>
  )
}
