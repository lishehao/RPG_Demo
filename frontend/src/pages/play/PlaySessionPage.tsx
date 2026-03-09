import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiService } from '@/shared/api/service';
import { ApiClientError } from '@/shared/api/client';
import { deriveRecommendedMoves } from '@/features/play-runtime/lib/sessionRecommendations';
import { cn } from '@/shared/lib/cn';
import { useSessionStore } from '@/features/play-runtime/store/sessionStore';
import type { ErrorPresentationContext } from '@/shared/lib/apiErrorPresentation';
import { Button } from '@/shared/ui/Button';
import { ErrorBanner } from '@/shared/ui/ErrorBanner';
import { Panel } from '@/shared/ui/Panel';
import { Pill } from '@/shared/ui/Pill';


function summarizeRiskHint(value: string) {
  const lower = value.toLowerCase();
  if (lower.includes('low')) return 'Low Risk';
  if (lower.includes('high')) return 'High Risk';
  if (lower.includes('medium')) return 'Medium Risk';
  if (lower.includes('fast but dirty')) return 'Fast / Risky';
  if (lower.includes('steady but slow')) return 'Steady';
  if (lower.includes('politically safe')) return 'Safe / Costly';
  return 'Suggested';
}

function TurnBubble({ title, children, tone }: { title: string; children: React.ReactNode; tone: 'player' | 'world' | 'system' }) {
  return (
    <div
      className={cn(
        'max-w-[92%] rounded-[24px] border px-4 py-4 shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_12px_30px_rgba(0,0,0,0.22)]',
        tone === 'player'
          ? 'ml-auto border-[rgba(255,209,102,0.3)] bg-[linear-gradient(180deg,rgba(255,209,102,0.16),rgba(255,138,61,0.12))]'
          : tone === 'system'
            ? 'mr-auto border-[rgba(120,220,170,0.24)] bg-[linear-gradient(180deg,rgba(120,220,170,0.12),rgba(120,220,170,0.06))]'
            : 'mr-auto border-[rgba(255,232,206,0.18)] bg-[linear-gradient(180deg,rgba(255,248,229,0.08),rgba(255,248,229,0.03))]',
      )}
    >
      <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--text-dim)]">{title}</div>
      <div className="mt-2 break-words text-sm leading-7 text-[var(--text-mist)]">{children}</div>
    </div>
  );
}

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-full border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-3 py-2 text-sm text-[var(--text-mist)]">
      <span className="font-bold uppercase tracking-[0.14em] text-[var(--text-dim)]">{label}</span>
      <span className="ml-2 text-[var(--text-ivory)]">{value}</span>
    </div>
  );
}

export function PlaySessionPage() {
  const { sessionId = '' } = useParams();
  const navigate = useNavigate();
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const [textInput, setTextInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiClientError | Error | null>(null);
  const [errorContext, setErrorContext] = useState<ErrorPresentationContext>('play-session-load');
  const [openingPromptSeeded, setOpeningPromptSeeded] = useState(false);
  const { sessionMeta, history, submitting, setSessionMeta, setHistoryResponse, setSubmitting, reset } = useSessionStore();

  async function loadSession() {
    if (!sessionId) {
      navigate('/play/library');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [meta, historyResponse] = await Promise.all([
        apiService.getSession(sessionId),
        apiService.getSessionHistory(sessionId),
      ]);
      setSessionMeta(meta);
      setHistoryResponse(historyResponse);
    } catch (caught) {
      setErrorContext('play-session-load');
      setError(caught as ApiClientError | Error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reset();
    setOpeningPromptSeeded(false);
    setTextInput('');
    void loadSession();
  }, [sessionId]);

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTo({ top: timelineRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [history.length]);

  const latestTurn = useMemo(() => history[history.length - 1] ?? null, [history]);
  const latestActions = latestTurn?.ui.moves ?? [];
  const recommendedMoves = useMemo(() => deriveRecommendedMoves(latestActions, 3), [latestActions]);
  const hiddenActionCount = Math.max(0, latestActions.length - recommendedMoves.length);
  const isComplete = Boolean(sessionMeta?.ended || latestTurn?.ended);
  const openingGuidance = sessionMeta?.opening_guidance ?? null;
  const starterPrompts = Array.isArray(openingGuidance?.starter_prompts)
    ? openingGuidance.starter_prompts.filter((prompt): prompt is string => typeof prompt === 'string')
    : [];

  useEffect(() => {
    if (!openingPromptSeeded && history.length === 0 && !textInput.trim() && starterPrompts[0]) {
      setTextInput(starterPrompts[0]);
      setOpeningPromptSeeded(true);
    }
  }, [history.length, openingPromptSeeded, starterPrompts, textInput]);

  async function submitButton(moveId: string) {
    if (!sessionId) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiService.stepSession(sessionId, {
        client_action_id: `btn-${Date.now()}`,
        input: { type: 'button', move_id: moveId },
        dev_mode: false,
      });
      await loadSession();
    } catch (caught) {
      setErrorContext('play-session-step');
      setError(caught as ApiClientError | Error);
    } finally {
      setSubmitting(false);
    }
  }

  async function submitText(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = textInput.trim();
    if (!trimmed || !sessionId) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiService.stepSession(sessionId, {
        client_action_id: `txt-${Date.now()}`,
        input: { type: 'text', text: trimmed },
        dev_mode: false,
      });
      setTextInput('');
      await loadSession();
    } catch (caught) {
      setErrorContext('play-session-step');
      setError(caught as ApiClientError | Error);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Panel
      eyebrow="Play Runtime"
      title={sessionMeta ? `Session ${sessionMeta.session_id.slice(0, 8)}` : 'Loading session'}
      subtitle="A chatbox-first play surface: the story stays in the center, while controls and signals stay close to your next move."
      className="min-h-[calc(100vh-10rem)]"
    >
      <ErrorBanner error={error} context={errorContext} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {sessionMeta ? <Pill tone={sessionMeta.ended ? 'neutral' : 'success'}>{sessionMeta.ended ? 'Completed' : 'Active'}</Pill> : null}
          {latestTurn ? <Pill tone="neutral">Scene {latestTurn.scene_id}</Pill> : null}
          {latestTurn ? <Pill tone={latestTurn.ended ? 'neutral' : 'success'}>{latestTurn.resolution.result}</Pill> : null}
          {latestTurn ? <Pill tone="neutral">{latestTurn.recognized.route_source}</Pill> : null}
        </div>
        <Button variant="secondary" type="button" onClick={() => navigate('/play/library')}>
          Back to Play Library
        </Button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-start">
        <div className="min-w-0 rounded-[26px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)]">
          <div ref={timelineRef} className="custom-scrollbar flex min-h-[58vh] max-h-[64vh] flex-col gap-4 overflow-y-auto px-5 py-5">
            {loading ? (
              <div className="rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-5 py-10 text-center text-[var(--text-mist)]">
                Rebuilding runtime history...
              </div>
            ) : history.length === 0 ? (
              <>
                <TurnBubble title="World" tone="world">
                  {openingGuidance?.intro_text || 'The session is ready. Use the opening guidance or type your own first move.'}
                </TurnBubble>
                {openingGuidance?.goal_hint ? (
                  <TurnBubble title="Goal" tone="system">
                    {openingGuidance.goal_hint}
                  </TurnBubble>
                ) : null}
              </>
            ) : (
              history.map((turn) => (
                <div key={turn.turn_index} className="space-y-3">
                  <TurnBubble title={`You · Turn ${turn.turn_index}`} tone="player">
                    {turn.recognized.interpreted_intent}
                  </TurnBubble>
                  <TurnBubble title="World" tone="world">
                    {turn.narration_text}
                  </TurnBubble>
                </div>
              ))
            )}
          </div>

          <div className="border-t border-[var(--line)] px-5 py-4">
            {history.length === 0 && starterPrompts.length > 0 ? (
              <div className="mb-4 space-y-2">
                <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--text-dim)]">Starter prompts</div>
                <div className="flex flex-wrap gap-2">
                  {starterPrompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => {
                        setTextInput(prompt);
                        setOpeningPromptSeeded(true);
                      }}
                      className="rounded-full border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-3 py-2 text-sm text-[var(--text-mist)] transition hover:border-[var(--line-strong)] hover:text-[var(--text-ivory)]"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <form className="space-y-4" onSubmit={(event) => void submitText(event)}>
              <label className="block space-y-2">
                <span className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Your move</span>
                <textarea
                  value={textInput}
                  onChange={(event) => {
                    setTextInput(event.target.value);
                    setOpeningPromptSeeded(true);
                  }}
                  placeholder="Describe what you do next..."
                  className="min-h-24 w-full rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-4 py-3 text-[var(--text-ivory)] outline-none transition placeholder:text-[var(--text-dim)] focus:border-[rgba(239,126,69,0.62)] focus:bg-[rgba(255,248,229,0.08)]"
                />
                <p className="text-sm text-[var(--text-dim)]">
                  {history.length === 0
                    ? (openingGuidance?.goal_hint || 'Use the opening guidance to choose your first move.')
                    : (latestTurn?.ui.input_hint ?? 'Free input is the main control surface; suggested moves are optional shortcuts.')} 
                </p>
              </label>
              <div className="flex flex-wrap gap-3">
                <Button type="submit" disabled={submitting || isComplete || !textInput.trim()}>
                  {submitting ? 'Sending...' : history.length === 0 ? 'Begin Session' : 'Send Directive'}
                </Button>
                {isComplete ? <Pill tone="neutral">Session sealed</Pill> : null}
              </div>
            </form>

            {history.length > 0 ? (
              <div className="mt-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--text-dim)]">Suggested Moves</div>
                  <div className="text-xs text-[var(--text-dim)]">
                    {hiddenActionCount > 0
                      ? `${hiddenActionCount} more hidden`
                      : 'Top shortlist only'}
                  </div>
                </div>
                {recommendedMoves.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {recommendedMoves.map((move) => (
                      <button
                        key={move.move_id}
                        type="button"
                        onClick={() => void submitButton(move.move_id)}
                        disabled={submitting || isComplete}
                        className="rounded-full border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-4 py-3 text-left transition hover:border-[rgba(239,126,69,0.36)] hover:bg-[rgba(239,126,69,0.08)] disabled:cursor-not-allowed disabled:opacity-45"
                      >
                        <div className="text-sm font-semibold text-[var(--text-ivory)]">{move.label}</div>
                        <div className="mt-1 text-xs text-[var(--text-mist)]">{summarizeRiskHint(move.risk_hint)}</div>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        <div className="space-y-4 lg:sticky lg:top-4">
          <div className="rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] p-4">
            <div className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Current Turn State</div>
            <div className="mt-3 grid gap-3">
              <MetricChip label="Scene" value={latestTurn?.scene_id ?? 'Opening'} />
              <MetricChip label="Result" value={latestTurn?.resolution.result ?? 'Awaiting first turn'} />
              <MetricChip label="Route" value={latestTurn?.recognized.route_source ?? 'Pending'} />
            </div>
          </div>
        </div>
      </div>
    </Panel>
  );
}
