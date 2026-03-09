import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '@/shared/api/service';
import { ApiClientError } from '@/shared/api/client';
import { useAuthorStoryStore } from '@/features/author-review/store/authorStoryStore';
import type { AuthorRunGetResponse } from '@/shared/api/types';
import type { ErrorPresentationContext } from '@/shared/lib/apiErrorPresentation';
import { Button } from '@/shared/ui/Button';
import { EmptyState } from '@/shared/ui/EmptyState';
import { ErrorBanner } from '@/shared/ui/ErrorBanner';
import { Field } from '@/shared/ui/Field';
import { Panel } from '@/shared/ui/Panel';
import { Pill } from '@/shared/ui/Pill';
import { formatDateTime } from '@/shared/lib/format';

const POLL_INTERVAL_MS = 2000;
const POLL_LIMIT = 120;


function runTone(status: string | null | undefined) {
  if (status === 'failed') return 'high' as const;
  if (status === 'review_ready') return 'success' as const;
  if (status === 'pending' || status === 'running') return 'medium' as const;
  return 'neutral' as const;
}

function storyStateSummary(story: { latest_run_status: string | null; latest_run_current_node: string | null; latest_published_version: number | null }) {
  if (story.latest_published_version !== null) {
    return `Published for Play as version ${story.latest_published_version}.`;
  }
  if (story.latest_run_status === 'failed') {
    return `Workflow stopped${story.latest_run_current_node ? ` at ${story.latest_run_current_node}` : ''}. Re-run before review or publish.`;
  }
  if (story.latest_run_status === 'review_ready') {
    return 'Draft is review-ready and waiting for publish.';
  }
  if (story.latest_run_status === 'pending' || story.latest_run_status === 'running') {
    return `Author workflow still running${story.latest_run_current_node ? ` at ${story.latest_run_current_node}` : ''}.`;
  }
  return 'Draft shell exists, but no completed author run is attached yet.';
}

function storyCardClasses(status: string | null | undefined) {
  if (status === 'failed') {
    return 'border-[rgba(239,126,69,0.28)] bg-[rgba(239,126,69,0.08)] hover:border-[rgba(239,126,69,0.45)] hover:bg-[rgba(239,126,69,0.12)]';
  }
  if (status === 'review_ready') {
    return 'border-[rgba(120,192,156,0.24)] bg-[rgba(120,192,156,0.07)] hover:border-[rgba(120,192,156,0.4)] hover:bg-[rgba(120,192,156,0.1)]';
  }
  return 'border-[var(--line)] bg-[rgba(255,248,229,0.05)] hover:border-[var(--line-strong)] hover:bg-[rgba(255,248,229,0.08)]';
}

export function AuthorStoriesPage() {
  const navigate = useNavigate();
  const { stories, setStories } = useAuthorStoryStore();
  const [rawBrief, setRawBrief] = useState('Design a political fantasy thriller about a forest city under ritual siege.');
  const [loadingStories, setLoadingStories] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [pendingRun, setPendingRun] = useState<AuthorRunGetResponse | null>(null);
  const [error, setError] = useState<ApiClientError | Error | null>(null);
  const [errorContext, setErrorContext] = useState<ErrorPresentationContext>('author-stories-load');

  async function loadStories() {
    setLoadingStories(true);
    try {
      const response = await apiService.listAuthorStories();
      setStories(response.stories);
    } catch (caught) {
      setErrorContext('author-stories-load');
      setError(caught as ApiClientError | Error);
    } finally {
      setLoadingStories(false);
    }
  }

  useEffect(() => {
    void loadStories();
  }, []);

  async function pollRun(runId: string, storyId: string) {
    for (let attempt = 0; attempt < POLL_LIMIT; attempt += 1) {
      const run = await apiService.getAuthorRun(runId);
      setPendingRun(run);
      if (run.status === 'review_ready') {
        await loadStories();
        navigate(`/author/stories/${storyId}`);
        return;
      }
      if (run.status === 'failed') {
        throw new Error(run.error_message || run.error_code || 'Author run failed');
      }
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }
    throw new Error('Author run polling timed out');
  }

  async function handleGenerate() {
    setGenerating(true);
    setPendingRun(null);
    setError(null);
    try {
      const created = await apiService.createAuthorRun({ raw_brief: rawBrief.trim() });
      const initialRun = await apiService.getAuthorRun(created.run_id);
      setPendingRun(initialRun);
      await pollRun(created.run_id, created.story_id);
    } catch (caught) {
      setErrorContext('author-generate');
      setError(caught as ApiClientError | Error);
      await loadStories();
    } finally {
      setGenerating(false);
    }
  }

  const publishedCount = useMemo(
    () => stories.filter((story) => story.latest_published_version !== null).length,
    [stories],
  );

  return (
    <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
      <Panel
        eyebrow="Author Flow"
        title="Launch a new author run"
        subtitle="Submit a raw brief, let the LangGraph workflow synthesize the draft, then review and publish it."
      >
        <div className="space-y-5">
          <Field
            label="Raw Brief"
            multiline
            value={rawBrief}
            onChange={(event) => setRawBrief(event.target.value)}
            hint="Write one or more sentences. The backend will turn this directly into StoryOverview and beat generation runs."
          />

          {pendingRun ? (
            <div className={`rounded-[24px] border p-4 ${pendingRun.status === 'failed' ? 'border-[rgba(239,126,69,0.3)] bg-[rgba(239,126,69,0.08)]' : pendingRun.status === 'review_ready' ? 'border-[rgba(120,192,156,0.24)] bg-[rgba(120,192,156,0.08)]' : 'border-[rgba(245,179,111,0.24)] bg-[rgba(245,179,111,0.08)]'}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Current author run</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Pill tone={runTone(pendingRun.status)}>{pendingRun.status === 'failed' ? 'Run failed' : pendingRun.status}</Pill>
                    {pendingRun.current_node ? <Pill tone="neutral">{pendingRun.current_node}</Pill> : null}
                  </div>
                </div>
                <div className="text-sm text-[var(--text-dim)]">Created {formatDateTime(pendingRun.created_at)}</div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,0.8fr)]">
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--text-dim)]">Current brief</div>
                  <p className="mt-2 break-words text-sm leading-7 text-[var(--text-mist)]">{pendingRun.raw_brief}</p>
                </div>
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--text-dim)]">Latest status</div>
                  <p className="mt-2 break-words text-sm leading-7 text-[var(--text-mist)]">{pendingRun.error_message || storyStateSummary({ latest_run_status: pendingRun.status, latest_run_current_node: pendingRun.current_node, latest_published_version: null })}</p>
                </div>
              </div>
            </div>
          ) : null}

          <ErrorBanner error={error} context={errorContext} />

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={handleGenerate} disabled={generating || !rawBrief.trim()}>
              {generating ? 'Running Author Graph...' : 'Create Author Run'}
            </Button>
            <Button variant="secondary" onClick={() => void loadStories()} disabled={loadingStories}>
              Refresh Story Index
            </Button>
          </div>
        </div>
      </Panel>

      <Panel
        eyebrow="Story Index"
        title="Author stories"
        subtitle="Stories now track the latest author run directly; publish only after a run reaches review_ready."
      >
        <div className="mb-5 flex flex-wrap gap-2">
          <Pill tone="neutral">{stories.length.toString().padStart(2, '0')} total</Pill>
          <Pill tone="success">{publishedCount.toString().padStart(2, '0')} published</Pill>
        </div>

        {loadingStories ? (
          <div className="rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-5 py-10 text-center text-[var(--text-mist)]">
            Reading story index...
          </div>
        ) : stories.length === 0 ? (
          <EmptyState
            title="No author stories yet"
            body="Create an author run from the left panel. Successful runs will materialize a draft pack that can later be published into Play Mode."
          />
        ) : (
          <div className="space-y-3">
            {stories.map((story) => (
              <button
                key={story.story_id}
                type="button"
                onClick={() => navigate(`/author/stories/${story.story_id}`)}
                className={`w-full rounded-[24px] border p-4 text-left transition ${storyCardClasses(story.latest_run_status)}`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="font-[var(--font-title)] text-lg tracking-[0.04em] text-[var(--text-ivory)]">{story.title}</div>
                    <div className="mt-1 text-sm text-[var(--text-dim)]">Created {formatDateTime(story.created_at)}</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {story.latest_run_status ? (
                      <Pill tone={runTone(story.latest_run_status)}>
                        {story.latest_run_status === 'failed' ? 'Run failed' : story.latest_run_status}
                      </Pill>
                    ) : null}
                    {story.latest_published_version !== null ? (
                      <Pill tone="success">Published v{story.latest_published_version}</Pill>
                    ) : story.latest_run_status === 'failed' ? (
                      <Pill tone="high">No valid draft</Pill>
                    ) : story.latest_run_status === 'review_ready' ? (
                      <Pill tone="medium">Unpublished</Pill>
                    ) : (
                      <Pill tone="neutral">Draft shell</Pill>
                    )}
                  </div>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                  <div className="min-w-0">
                    <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--text-dim)]">State summary</div>
                    <p className="mt-2 break-words text-sm leading-7 text-[var(--text-mist)]">{storyStateSummary(story)}</p>
                  </div>
                  <div className="flex flex-col items-start gap-1 text-sm md:items-end">
                    <span className="font-semibold text-[var(--text-ivory)]">Open detail →</span>
                    {story.latest_run_updated_at ? <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--text-dim)]">Updated {formatDateTime(story.latest_run_updated_at)}</span> : null}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
