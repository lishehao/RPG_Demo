import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiService } from '@/shared/api/service';
import { ApiClientError } from '@/shared/api/client';
import type { SessionStepRequest } from '@/shared/api/types';
import { useSessionStore } from '@/shared/store/sessionStore';
import { Button } from '@/shared/ui/Button';
import { EmptyState } from '@/shared/ui/EmptyState';
import { ErrorBanner } from '@/shared/ui/ErrorBanner';
import { Field } from '@/shared/ui/Field';
import { Panel } from '@/shared/ui/Panel';
import { Pill } from '@/shared/ui/Pill';
import { formatDateTime } from '@/shared/lib/format';

function riskTone(value: string) {
  if (value === 'low') {
    return 'low';
  }
  if (value === 'high') {
    return 'high';
  }
  return 'medium';
}

export function SessionPage() {
  const { sessionId = '' } = useParams();
  const navigate = useNavigate();
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const [textInput, setTextInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiClientError | Error | null>(null);
  const [latestRisk, setLatestRisk] = useState<'low' | 'medium' | 'high'>('medium');

  const {
    sessionMeta,
    history,
    submitting,
    setSessionMeta,
    setHistory,
    appendTurn,
    setSubmitting,
    reset,
  } = useSessionStore();

  useEffect(() => reset, [reset]);

  useEffect(() => {
    async function loadSession() {
      if (!sessionId) {
        navigate('/dashboard');
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
        setHistory(historyResponse.history);
      } catch (caught) {
        setError(caught as ApiClientError | Error);
      } finally {
        setLoading(false);
      }
    }

    void loadSession();
  }, [navigate, sessionId, setHistory, setSessionMeta]);

  useEffect(() => {
    if (!timelineRef.current) {
      return;
    }
    timelineRef.current.scrollTo({ top: timelineRef.current.scrollHeight, behavior: 'smooth' });
  }, [history.length]);

  const latestActions = useMemo(() => {
    return history.length > 0 ? history[history.length - 1].actions : [];
  }, [history]);

  async function submitTurn(payload: SessionStepRequest) {
    if (!sessionId) {
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const response = await apiService.stepSession(sessionId, payload);
      appendTurn(response);
      setLatestRisk(response.risk_hint);
      const meta = await apiService.getSession(sessionId);
      setSessionMeta(meta);
    } catch (caught) {
      setError(caught as ApiClientError | Error);
    } finally {
      setSubmitting(false);
    }
  }

  const isComplete = sessionMeta?.state === 'completed';

  return (
    <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
      <Panel
        eyebrow="Live Session"
        title={sessionMeta ? `Session ${sessionMeta.session_id.slice(0, 8)}` : 'Loading session'}
        subtitle={
          sessionMeta
            ? `Created ${formatDateTime(sessionMeta.created_at)}. Reload-safe history is restored from the backend timeline.`
            : 'Connecting to live session state.'
        }
        className="min-h-[72vh]"
      >
        <div ref={timelineRef} className="custom-scrollbar max-h-[62vh] space-y-4 overflow-y-auto pr-2">
          {loading ? (
            <div className="rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-5 py-10 text-center text-[var(--text-mist)]">
              Synchronizing the scene archive...
            </div>
          ) : history.length === 0 ? (
            <EmptyState
              title="The chamber is quiet"
              body="This session has no turns yet. Start with a custom intent, or use the ignition button to request the first narrated beat."
              action={
                <Button disabled={submitting || isComplete} onClick={() => void submitTurn({ free_text: 'Begin the story' })}>
                  {submitting ? 'Igniting...' : 'Ignite Opening Turn'}
                </Button>
              }
            />
          ) : (
            history.map((turn, index) => (
              <article
                key={turn.turn}
                className="fade-rise rounded-[26px] border border-[var(--line)] bg-[linear-gradient(180deg,rgba(255,248,229,0.07),rgba(255,248,229,0.03))] p-5"
                style={{ animationDelay: `${index * 38}ms` }}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-full border border-[rgba(239,126,69,0.34)] bg-[rgba(239,126,69,0.12)] font-[var(--font-title)] text-lg">
                      {turn.turn}
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Turn {turn.turn}</p>
                      <p className="mt-1 text-sm text-[var(--text-dim)]">Choices revealed: {turn.actions.length}</p>
                    </div>
                  </div>
                  {turn.turn === history[history.length - 1]?.turn ? <Pill tone={riskTone(latestRisk)}>Risk {latestRisk}</Pill> : null}
                </div>

                <p className="mt-5 whitespace-pre-wrap text-base leading-8 text-[var(--text-ivory)]">{turn.narration}</p>

                <div className="mt-5 flex flex-wrap gap-2">
                  {turn.actions.map((action) => (
                    <span
                      key={action.id}
                      className="rounded-full border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-3 py-2 text-xs uppercase tracking-[0.12em] text-[var(--text-mist)]"
                    >
                      {action.label}
                    </span>
                  ))}
                </div>
              </article>
            ))
          )}
        </div>
      </Panel>

      <div className="space-y-4">
        <Panel
          eyebrow="Control Deck"
          title={isComplete ? 'Session sealed' : 'Issue the next command'}
          subtitle={
            isComplete
              ? 'The backend marks this session as completed. Inputs are now locked for consistency.'
              : 'Use the surfaced actions when available, or type a custom instruction to steer the narrative.'
          }
        >
          {sessionMeta ? (
            <div className="mb-6 flex flex-wrap gap-2">
              <Pill tone={sessionMeta.state === 'completed' ? 'neutral' : 'success'}>{sessionMeta.state}</Pill>
              <Pill tone={riskTone(latestRisk)}>Current Risk {latestRisk}</Pill>
            </div>
          ) : null}

          <ErrorBanner error={error} />

          <div className="mt-5 space-y-5">
            <div>
              <p className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-[var(--text-dim)]">Recommended actions</p>
              {latestActions.length === 0 ? (
                <div className="rounded-[22px] border border-dashed border-[var(--line)] px-4 py-5 text-sm text-[var(--text-dim)]">
                  No surfaced actions yet. Start the session or send a free-form command.
                </div>
              ) : (
                <div className="grid gap-3">
                  {latestActions.map((action) => (
                    <button
                      key={action.id}
                      type="button"
                      onClick={() => void submitTurn({ move_id: action.id })}
                      disabled={submitting || isComplete}
                      className="rounded-[22px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-4 py-4 text-left transition hover:border-[rgba(239,126,69,0.36)] hover:bg-[rgba(239,126,69,0.08)] disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      <div className="font-[var(--font-title)] text-lg tracking-[0.05em] text-[var(--text-ivory)]">{action.label}</div>
                      <div className="mt-2 break-all text-xs uppercase tracking-[0.12em] text-[var(--text-dim)]">{action.id}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                const trimmed = textInput.trim();
                if (!trimmed) {
                  return;
                }
                void submitTurn({ free_text: trimmed });
                setTextInput('');
              }}
            >
              <Field
                label="Free Text Directive"
                multiline
                placeholder="Describe what the player tries next..."
                value={textInput}
                onChange={(event) => setTextInput(event.target.value)}
                hint="Useful for probing edge cases during live UI debugging."
              />

              <div className="flex flex-wrap gap-3">
                <Button type="submit" disabled={submitting || isComplete || !textInput.trim()}>
                  {submitting ? 'Sending...' : 'Send Directive'}
                </Button>
                <Button variant="secondary" type="button" onClick={() => navigate('/dashboard')}>
                  Back to Dashboard
                </Button>
              </div>
            </form>
          </div>
        </Panel>
      </div>
    </div>
  );
}
