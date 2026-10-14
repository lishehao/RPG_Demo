/**
 * Adopter implementation of the reference's missing `./chat-timing` dependency.
 * Presentation-side timing only: in-memory, no network, no message text.
 */
type Trace = {surface: string; mode: string; started: number; operationId?: string; status?: string; received?: number; failed?: boolean}
const traces: Trace[] = []
export function startChatTiming(surface: string, mode: string): Trace {
  const trace = {surface, mode, started: performance.now()}
  traces.push(trace); if (traces.length > 200) traces.shift()
  return trace
}
export function receivedChatTiming(trace: Trace, operationId: string, status: string, _turnId?: string | null) {
  trace.operationId = operationId; trace.status = status; trace.received = performance.now()
}
export function failedChatTiming(trace: Trace) { trace.failed = true; trace.received = performance.now() }
export function observeChatOperation(_surface: string, _operationId: string, _status: string, _turnId?: string | null, _polled = false) { /* no-op */ }
export function observeChatPaint(_turnId: string | undefined, _node: Element | null) { /* no-op */ }
export function chatTimingSnapshot() { return traces.map(t => ({surface: t.surface, mode: t.mode, ms: t.received ? Math.round(t.received - t.started) : null, status: t.status ?? null, failed: !!t.failed})) }
