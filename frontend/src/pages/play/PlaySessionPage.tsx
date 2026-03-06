import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiService } from '@/shared/api/service';
import { ApiClientError } from '@/shared/api/client';
import { useSessionStore } from '@/shared/store/sessionStore';
import { Button } from '@/shared/ui/Button';
import { EmptyState } from '@/shared/ui/EmptyState';
import { ErrorBanner } from '@/shared/ui/ErrorBanner';
import { Field } from '@/shared/ui/Field';
import { Panel } from '@/shared/ui/Panel';
import { Pill } from '@/shared/ui/Pill';

type RiskTone = 'low' | 'medium' | 'high';

function normalizeRisk(value: string): RiskTone {
  if (value.includes('low')) return 'low';
  if (value.includes('high')) return 'high';
  return 'medium';
}

export function PlaySessionPage() {
  const { sessionId = '' } = useParams();
  const navigate = useNavigate();
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const [textInput, setTextInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiClientError | Error | null>(null);
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
      setError(caught as ApiClientError | Error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reset();
    void loadSession();
  }, [sessionId]);

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTo({ top: timelineRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [history.length]);

  const latestTurn = useMemo(() => history[history.length - 1] ?? null, [history]);
  const latestActions = latestTurn?.ui.moves ?? [];
  const isComplete = Boolean(sessionMeta?.ended || latestTurn?.ended);

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
      setError(caught as ApiClientError | Error);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
      <Panel
        eyebrow="Play Runtime"
        title={sessionMeta ? `Session ${sessionMeta.session_id.slice(0, 8)}` : 'Loading session'}
        subtitle="Play mode reconstructs the full runtime timeline from the public session history endpoint."
        className="min-h-[72vh]"
      >
        <ErrorBanner error={error} />
        <div ref={timelineRef} className="custom-scrollbar mt-4 max-h-[62vh] space-y-4 overflow-y-auto pr-2">
          {loading ? (
            <div className="rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-5 py-10 text-center text-[var(--text-mist)]">
              Rebuilding runtime history...
            </div>
          ) : history.length === 0 ? (
            <EmptyState
              title="Session ready to ignite"
              body="No turns yet. Kick off the first step from the control deck on the right."
            />
          ) : (
            history.map((turn) => (
              <article key={turn.turn_index} className="rounded-[26px] border border-[var(--line)] bg-[linear-gradient(180deg,rgba(255,248,229,0.07),rgba(255,248,229,0.03))] p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Turn {turn.turn_index}</p>
                    <h3 className="mt-2 font-[var(--font-title)] text-lg tracking-[0.05em] text-[var(--text-ivory)]">
                      {turn.recognized.interpreted_intent}
                    </h3>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Pill tone={turn.ended ? 'neutral' : 'success'}>{turn.ended ? 'Ended' : 'Active'}</Pill>
                    <Pill tone="neutral">{turn.recognized.route_source}</Pill>
                  </div>
                </div>
                <p className="mt-5 whitespace-pre-wrap text-base leading-8 text-[var(--text-ivory)]">{turn.narration_text}</p>
                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  <div className="rounded-[20px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Resolution</div>
                    <div className="mt-2 text-sm leading-7 text-[var(--text-mist)]">{turn.resolution.result}</div>
                  </div>
                  <div className="rounded-[20px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Scene</div>
                    <div className="mt-2 break-all text-sm leading-7 text-[var(--text-mist)]">{turn.scene_id}</div>
                  </div>
                </div>
              </article>
            ))
          )}
        </div>
      </Panel>

      <div className="space-y-4">
        <Panel
          eyebrow="Action Deck"
          title={isComplete ? 'Session sealed' : 'Drive the next turn'}
          subtitle={isComplete ? 'This session has ended.' : latestTurn?.ui.input_hint ?? 'Choose a surfaced move or write a custom directive.'}
        >
          {sessionMeta ? <Pill tone={sessionMeta.ended ? 'neutral' : 'success'}>{sessionMeta.ended ? 'Completed' : 'Active'}</Pill> : null}
          <div className="mt-5 space-y-4">
            {latestActions.length > 0 ? (
              latestActions.map((move) => (
                <button
                  key={move.move_id}
                  type="button"
                  onClick={() => void submitButton(move.move_id)}
                  disabled={submitting || isComplete}
                  className="w-full rounded-[22px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-4 py-4 text-left transition hover:border-[rgba(239,126,69,0.36)] hover:bg-[rgba(239,126,69,0.08)] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-[var(--font-title)] text-lg tracking-[0.05em] text-[var(--text-ivory)]">{move.label}</div>
                      <div className="mt-2 break-all text-xs uppercase tracking-[0.12em] text-[var(--text-dim)]">{move.move_id}</div>
                    </div>
                    <Pill tone={normalizeRisk(move.risk_hint)}>{move.risk_hint}</Pill>
                  </div>
                </button>
              ))
            ) : (
              <div className="rounded-[22px] border border-dashed border-[var(--line)] px-4 py-5 text-sm text-[var(--text-dim)]">
                No surfaced actions yet. Use free text to begin or continue the session.
              </div>
            )}

            <form className="space-y-4" onSubmit={(event) => void submitText(event)}>
              <Field
                label="Free Text Directive"
                multiline
                placeholder="Describe what the player attempts next..."
                value={textInput}
                onChange={(event) => setTextInput(event.target.value)}
                hint="This goes through the real route-intent + narration pipeline."
              />
              <div className="flex flex-wrap gap-3">
                <Button type="submit" disabled={submitting || isComplete || !textInput.trim()}>
                  {submitting ? 'Sending...' : 'Send Directive'}
                </Button>
                <Button variant="secondary" type="button" onClick={() => navigate('/play/library')}>
                  Back to Play Library
                </Button>
              </div>
            </form>
          </div>
        </Panel>
      </div>
    </div>
  );
}
