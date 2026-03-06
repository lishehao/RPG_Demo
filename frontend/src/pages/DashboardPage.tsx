import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '@/shared/api/service';
import { ApiClientError } from '@/shared/api/client';
import type { StoryListItem } from '@/shared/api/types';
import { Button } from '@/shared/ui/Button';
import { EmptyState } from '@/shared/ui/EmptyState';
import { ErrorBanner } from '@/shared/ui/ErrorBanner';
import { Field } from '@/shared/ui/Field';
import { Panel } from '@/shared/ui/Panel';
import { Pill } from '@/shared/ui/Pill';
import { titleCase } from '@/shared/lib/format';

const themeOptions = ['fantasy', 'sci-fi', 'mystery', 'horror'];
const difficultyOptions = ['easy', 'medium', 'hard'];

export function DashboardPage() {
  const navigate = useNavigate();
  const [theme, setTheme] = useState('fantasy');
  const [difficulty, setDifficulty] = useState('medium');
  const [stories, setStories] = useState<StoryListItem[]>([]);
  const [loadingStories, setLoadingStories] = useState(true);
  const [creating, setCreating] = useState(false);
  const [creatingSessionId, setCreatingSessionId] = useState<string | null>(null);
  const [error, setError] = useState<ApiClientError | Error | null>(null);

  async function loadStories() {
    setLoadingStories(true);
    try {
      const response = await apiService.listStories();
      setStories(response.stories);
    } catch (caught) {
      setError(caught as ApiClientError | Error);
    } finally {
      setLoadingStories(false);
    }
  }

  useEffect(() => {
    void loadStories();
  }, []);

  async function handleGenerateStory() {
    setCreating(true);
    setError(null);

    try {
      await apiService.generateStory({ theme, difficulty });
      await loadStories();
    } catch (caught) {
      setError(caught as ApiClientError | Error);
    } finally {
      setCreating(false);
    }
  }

  async function handleCreateSession(storyId: string) {
    setCreatingSessionId(storyId);
    setError(null);
    try {
      const response = await apiService.createSession({ story_id: storyId });
      navigate(`/sessions/${response.session_id}`);
    } catch (caught) {
      setError(caught as ApiClientError | Error);
    } finally {
      setCreatingSessionId(null);
    }
  }

  const storyCountLabel = useMemo(() => `${stories.length.toString().padStart(2, '0')} stories`, [stories.length]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
      <Panel
        eyebrow="Forge Stories"
        title="Signal a new campaign"
        subtitle="Dial in tone and difficulty, then mint a new story packet straight into the command library."
      >
        <div className="grid gap-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="Theme"
              value={theme}
              onChange={(event) => setTheme(event.target.value)}
              list="theme-presets"
              hint="You can choose a preset or type your own world flavor."
            />
            <datalist id="theme-presets">
              {themeOptions.map((option) => (
                <option key={option} value={option} />
              ))}
            </datalist>

            <div className="space-y-3 md:col-span-2">
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--text-dim)]">Difficulty</div>
              <div className="grid gap-3 md:grid-cols-3">
                {difficultyOptions.map((option) => {
                  const active = difficulty === option;
                  return (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setDifficulty(option)}
                      className={`rounded-[22px] border px-4 py-4 text-left transition ${
                        active
                          ? 'border-[rgba(239,126,69,0.42)] bg-[linear-gradient(135deg,rgba(239,126,69,0.18),rgba(245,179,111,0.08))]'
                          : 'border-[var(--line)] bg-[rgba(255,248,229,0.04)] hover:border-[var(--line-strong)]'
                      }`}
                    >
                      <div className="font-[var(--font-title)] text-lg tracking-[0.06em]">{titleCase(option)}</div>
                      <div className="mt-2 text-sm leading-6 text-[var(--text-mist)]">
                        {option === 'easy'
                          ? 'Warm onboarding, gentle tension, readable tempo.'
                          : option === 'medium'
                            ? 'Balanced pressure with clear dramatic turns.'
                            : 'Sharper consequences and a darker pulse.'}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <ErrorBanner error={error} />

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={handleGenerateStory} disabled={creating}>
              {creating ? 'Forging Story...' : 'Generate Story'}
            </Button>
            <Button variant="secondary" onClick={() => void loadStories()} disabled={loadingStories}>
              Refresh Library
            </Button>
          </div>
        </div>
      </Panel>

      <Panel
        eyebrow="Story Library"
        title="Published missions"
        subtitle="Every generated story appears here and can be launched immediately into a fresh session."
      >
        <div className="mb-5 flex items-center justify-between gap-3">
          <Pill tone="neutral">{storyCountLabel}</Pill>
          <p className="text-sm text-[var(--text-dim)]">Mock backend memory resets on restart.</p>
        </div>

        {loadingStories ? (
          <div className="rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-5 py-10 text-center text-[var(--text-mist)]">
            Reading archive...
          </div>
        ) : stories.length === 0 ? (
          <EmptyState
            title="No stories forged yet"
            body="Generate your first campaign packet from the panel on the left, then launch it into a live session."
          />
        ) : (
          <div className="space-y-4">
            {stories.map((story, index) => (
              <article
                key={story.story_id}
                className="fade-rise rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] p-5"
                style={{ animationDelay: `${index * 40}ms` }}
              >
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Story ID</p>
                    <h3 className="mt-2 font-[var(--font-title)] text-xl tracking-[0.06em] text-[var(--text-ivory)]">
                      {story.title}
                    </h3>
                    <p className="mt-2 break-all text-sm leading-6 text-[var(--text-dim)]">{story.story_id}</p>
                  </div>

                  <div className="flex items-center gap-3">
                    <Pill tone="success">Published</Pill>
                    <Button
                      variant="secondary"
                      onClick={() => void handleCreateSession(story.story_id)}
                      disabled={creatingSessionId === story.story_id}
                    >
                      {creatingSessionId === story.story_id ? 'Opening...' : 'Create Session'}
                    </Button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
