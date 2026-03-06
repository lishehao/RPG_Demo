import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiService } from '@/shared/api/service';
import { ApiClientError } from '@/shared/api/client';
import { useAuthorStoryStore } from '@/shared/store/authorStoryStore';
import { Button } from '@/shared/ui/Button';
import { ErrorBanner } from '@/shared/ui/ErrorBanner';
import { Panel } from '@/shared/ui/Panel';
import { Pill } from '@/shared/ui/Pill';
import { formatDateTime } from '@/shared/lib/format';

export function AuthorStoryDetailPage() {
  const { storyId = '' } = useParams();
  const navigate = useNavigate();
  const { currentStory, setCurrentStory } = useAuthorStoryStore();
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<ApiClientError | Error | null>(null);

  async function loadStory() {
    if (!storyId) {
      navigate('/author/stories');
      return;
    }
    setLoading(true);
    try {
      const response = await apiService.getStoryDraft(storyId);
      setCurrentStory(response);
    } catch (caught) {
      setError(caught as ApiClientError | Error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStory();
  }, [storyId]);

  async function handlePublish() {
    if (!storyId) {
      return;
    }
    setPublishing(true);
    setError(null);
    try {
      await apiService.publishStory(storyId);
      await loadStory();
    } catch (caught) {
      setError(caught as ApiClientError | Error);
    } finally {
      setPublishing(false);
    }
  }

  const draftStats = useMemo(() => {
    const draft = currentStory?.draft_pack ?? {};
    const scenes = Array.isArray(draft.scenes) ? draft.scenes.length : 0;
    const moves = Array.isArray(draft.moves) ? draft.moves.length : 0;
    const beats = Array.isArray(draft.beats) ? draft.beats.length : 0;
    return { scenes, moves, beats };
  }, [currentStory]);

  return (
    <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
      <Panel
        eyebrow="Story Detail"
        title={currentStory?.title ?? 'Loading draft'}
        subtitle={
          currentStory
            ? `Draft created ${formatDateTime(currentStory.created_at)}. Publish from here to make it available to Play Mode.`
            : 'Loading draft payload from the author API.'
        }
      >
        <ErrorBanner error={error} />

        {loading || !currentStory ? (
          <div className="rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-5 py-10 text-center text-[var(--text-mist)]">
            Loading draft detail...
          </div>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-2">
              <Pill tone="medium">Draft</Pill>
              {currentStory.latest_published_version !== null ? (
                <Pill tone="success">Published v{currentStory.latest_published_version}</Pill>
              ) : (
                <Pill tone="neutral">Not Published Yet</Pill>
              )}
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-[22px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Scenes</div>
                <div className="mt-2 font-[var(--font-title)] text-2xl">{draftStats.scenes}</div>
              </div>
              <div className="rounded-[22px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Moves</div>
                <div className="mt-2 font-[var(--font-title)] text-2xl">{draftStats.moves}</div>
              </div>
              <div className="rounded-[22px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Beats</div>
                <div className="mt-2 font-[var(--font-title)] text-2xl">{draftStats.beats}</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button onClick={handlePublish} disabled={publishing}>
                {publishing ? 'Publishing...' : 'Publish For Play'}
              </Button>
              {currentStory.latest_published_version !== null ? (
                <Button variant="secondary" onClick={() => navigate('/play/library')}>
                  Open Play Library
                </Button>
              ) : null}
              <Button variant="ghost" onClick={() => navigate('/author/stories')}>
                Back to Story Index
              </Button>
            </div>
          </div>
        )}
      </Panel>

      <Panel
        eyebrow="Draft Payload"
        title="Structured draft preview"
        subtitle="This MVP author line does not include a visual editor yet. The JSON preview is the current source of truth before publish."
      >
        {currentStory ? (
          <pre className="custom-scrollbar max-h-[72vh] overflow-auto rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] p-4 text-xs leading-6 text-[var(--text-mist)]">
            {JSON.stringify(currentStory.draft_pack, null, 2)}
          </pre>
        ) : null}
      </Panel>
    </div>
  );
}
