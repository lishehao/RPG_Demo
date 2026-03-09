import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiService } from '@/shared/api/service';
import { ApiClientError } from '@/shared/api/client';
import { deriveRecommendedMoves } from '@/features/play-runtime/lib/sessionRecommendations';
import { cn } from '@/shared/lib/cn';
import { useSessionStore } from '@/features/play-runtime/store/sessionStore';
import type { ErrorPresentationContext } from '@/shared/lib/apiErrorPresentation';
import type { SessionStateSummary } from '@/shared/api/types';
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

function titleCase(value: string) {
  return value
    .replace(/[_-]+/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((part) => {
      const lower = part.toLowerCase();
      if (lower === 'llm') return 'LLM';
      return part.charAt(0).toUpperCase() + part.slice(1);
    })
    .join(' ');
}

function humanizeIntent(value: string) {
  if (!value) return 'Take the next move.';
  const quoted = value.match(/[“"']([^"”']{8,})[”"']/);
  if (quoted?.[1]) return quoted[1].trim();
  const stripped = value.replace(/^The player intends to\s+/i, '').replace(/,?\s+as explicitly stated.*$/i, '').trim();
  return stripped ? stripped.charAt(0).toUpperCase() + stripped.slice(1) : value;
}

function humanizeResult(value: string) {
  switch (value) {
    case 'success':
      return 'Breakthrough';
    case 'partial':
      return 'Costly progress';
    case 'fail_forward':
      return 'Forward under pressure';
    default:
      return value ? titleCase(value) : 'Awaiting first turn';
  }
}

function trustProgress(value: number) {
  const clamped = Math.max(-4, Math.min(4, value));
  return ((clamped + 4) / 8) * 100;
}

function pressureProgress(value: number) {
  const clamped = Math.max(0, Math.min(5, value));
  return (clamped / 5) * 100;
}

function progressTone(tone: 'trust' | 'stress' | 'noise') {
  if (tone === 'trust') {
    return 'bg-[linear-gradient(90deg,rgba(120,220,170,0.9),rgba(255,209,102,0.92))]';
  }
  if (tone === 'stress') {
    return 'bg-[linear-gradient(90deg,rgba(255,209,102,0.92),rgba(255,138,61,0.95))]';
  }
  return 'bg-[linear-gradient(90deg,rgba(139,180,255,0.88),rgba(255,138,61,0.92))]';
}

function crewTone(stance: string) {
  if (stance === 'support') return 'border-[rgba(120,220,170,0.3)] bg-[rgba(120,220,170,0.1)]';
  if (stance === 'oppose') return 'border-[rgba(255,138,61,0.34)] bg-[rgba(255,138,61,0.12)]';
  return 'border-[rgba(255,209,102,0.26)] bg-[rgba(255,209,102,0.08)]';
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
    <div className="rounded-[18px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-3 py-3">
      <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--text-dim)]">{label}</div>
      <div className="mt-1 text-sm font-semibold text-[var(--text-ivory)]">{value}</div>
    </div>
  );
}

function PressureMeter({ label, valueLabel, progress, tone }: { label: string; valueLabel: string; progress: number; tone: 'trust' | 'stress' | 'noise' }) {
  return (
    <div className="rounded-[20px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--text-dim)]">{label}</span>
        <span className="text-sm font-semibold text-[var(--text-ivory)]">{titleCase(valueLabel)}</span>
      </div>
      <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-[rgba(255,248,229,0.08)]">
        <div className={cn('h-full rounded-full transition-[width] duration-500', progressTone(tone))} style={{ width: `${Math.max(8, Math.min(100, progress))}%` }} />
      </div>
    </div>
  );
}

function CrewSignalCard({ name, label, stance }: { name: string; label: string; stance: string }) {
  return (
    <div className={cn('rounded-[18px] border px-3 py-3', crewTone(stance))}>
      <div className="text-sm font-semibold text-[var(--text-ivory)]">{name}</div>
      <div className="mt-1 text-xs uppercase tracking-[0.14em] text-[var(--text-dim)]">{titleCase(label)}</div>
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
  const stateSummary = (sessionMeta?.state_summary ?? null) as SessionStateSummary | null;
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
          {latestTurn ? <Pill tone={latestTurn.ended ? 'neutral' : 'success'}>{humanizeResult(latestTurn.resolution.result)}</Pill> : null}
          {latestTurn ? <Pill tone="neutral">{titleCase(latestTurn.recognized.route_source)}</Pill> : null}
        </div>
        <Button variant="secondary" type="button" onClick={() => navigate('/play/library')}>
          Back to Play Library
        </Button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start">
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
                    {humanizeIntent(turn.recognized.interpreted_intent)}
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
                    {hiddenActionCount > 0 ? `${hiddenActionCount} more hidden` : 'Top shortlist only'}
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
                        className="group rounded-full border border-[rgba(255,232,206,0.18)] bg-[rgba(255,248,229,0.08)] px-4 py-3 text-left transition hover:-translate-y-[1px] hover:border-[rgba(255,138,61,0.38)] hover:bg-[rgba(255,138,61,0.12)] disabled:cursor-not-allowed disabled:opacity-45"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-[var(--text-ivory)]">{move.label}</span>
                          <span className="rounded-full bg-[rgba(255,255,255,0.06)] px-2 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-dim)] transition group-hover:text-[var(--text-ivory)]">{summarizeRiskHint(move.risk_hint)}</span>
                        </div>
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
            <div className="mt-3 grid gap-2">
              <MetricChip label="Scene" value={latestTurn?.scene_id ?? 'Opening'} />
              <MetricChip label="Result" value={humanizeResult(latestTurn?.resolution.result ?? '')} />
              <MetricChip label="Route" value={latestTurn?.recognized.route_source ? `${titleCase(latestTurn.recognized.route_source)} route` : 'Pending'} />
            </div>
          </div>

          {stateSummary ? (
            <div className="rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]">Player Signals</div>
              <div className="mt-3 grid gap-3">
                <PressureMeter
                  label="Trust"
                  valueLabel={stateSummary.pressure.public_trust.label}
                  progress={trustProgress(stateSummary.pressure.public_trust.value)}
                  tone="trust"
                />
                <PressureMeter
                  label="Stress"
                  valueLabel={stateSummary.pressure.resource_stress.label}
                  progress={pressureProgress(stateSummary.pressure.resource_stress.value)}
                  tone="stress"
                />
                <PressureMeter
                  label="Noise"
                  valueLabel={stateSummary.pressure.coordination_noise.label}
                  progress={pressureProgress(stateSummary.pressure.coordination_noise.value)}
                  tone="noise"
                />
                <MetricChip label="Cost" value={stateSummary.cost_total > 0 ? `${stateSummary.cost_total} total` : 'Minimal'} />
              </div>
              <p className="mt-3 text-sm leading-7 text-[var(--text-dim)]">
                These signals show public trust, operational strain, and coordination friction without exposing raw runtime internals.
              </p>
              {stateSummary.crew_signals.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--text-dim)]">Crew Signals</div>
                  <div className="grid gap-2">
                    {stateSummary.crew_signals.slice(0, 4).map((item) => (
                      <CrewSignalCard key={item.name} name={item.name} label={item.label} stance={item.stance} />
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}
