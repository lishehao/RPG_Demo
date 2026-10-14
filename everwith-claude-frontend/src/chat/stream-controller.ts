/**
 * Private chat operation controller. Extends the frozen candidate
 * (reference/contracts/stream-candidate/private-stream-controller.ts) with explicit
 * Retry, unknown-result lookup and resume, keeping its guarantees:
 *  - every intent freezes its binding (account/friend/epoch/session/revision/head);
 *  - public frames are presentation only — history changes only from a verified receipt;
 *  - a generation counter retires every older run, stream and late response;
 *  - Stop calls the real cancel endpoint and reports the server's terminal state.
 */
import {CompanionRequestError} from '../contracts/companion'
import {parsePrivateOperation, parsePrivateSnapshot} from '../contracts/private-chat-client'
import type {PrivateOperation, PrivateSnapshot} from '../contracts/private-chat-client'
import {readPrivatePublicStream} from '../contracts/private-chat-recovery'
import {createPublicReceiver, parsePublicBinding} from '../contracts/public-events'
import type {PublicAdmission, PublicBinding, PublicSegment} from '../contracts/public-events'
import {randomId, sleep} from '../lib/util'
import type {Lang} from '../lib/util'

export type ChatPhase = 'idle' | 'sending' | 'starting' | 'generating' | 'awaiting_commit' | 'cancelling' | 'cancelled' | 'committed' | 'interrupted' | 'failed' | 'unknown' | 'stale'
export type ChatNoticeKind = 'commit_won' | 'cancelled' | 'retryable' | 'failed' | 'stale' | 'epoch_changed' | 'unknown' | 'read_only' | 'auth' | 'forbidden' | 'lookup_missing' | 'not_retryable' | 'network'
export type ChatView = {
  phase: ChatPhase
  history: PrivateSnapshot
  provisional: PublicSegment[]
  /** Frozen text of the in-flight / unconfirmed command (shown as the sent receipt). */
  input: string
  pendingKey: string | null
  language: Lang
  notice: {kind: ChatNoticeKind; at: number} | null
  ignoredFrames: number
  /** Text to put back into the composer after a cancel/stale/failure (never auto-sent). */
  restore: {text: string; at: number} | null
}
export type ChatTransport = {
  send(command: {key: string; text: string; language: Lang; presented_turn_id: string; expected_revision: number}, signal?: AbortSignal): Promise<{operation: PrivateOperation; admission: PublicAdmission}>
  stream(admission: PublicAdmission, signal: AbortSignal): Promise<Response>
  cancel(operationId: string): Promise<PrivateOperation>
  receipt(operationId: string): Promise<{owner_id: string; operation: unknown; snapshot: unknown; admission: PublicAdmission | null}>
  retry(operationId: string): Promise<{operation: PrivateOperation; admission: PublicAdmission}>
  lookup(key: string): Promise<{operation: PrivateOperation; admission: PublicAdmission | null; text: string}>
  read(): Promise<PrivateSnapshot>
}
const ACTIVE: ChatPhase[] = ['sending', 'starting', 'generating', 'awaiting_commit', 'cancelling']

export function createChatController(initial: PrivateSnapshot, base: Omit<PublicBinding, 'revision' | 'head_turn_id'>, transport: ChatTransport) {
  const friendId = initial.conversation.friend_id, epoch = initial.conversation.friend_epoch
  let view: ChatView = {phase: initial.pending_operation ? 'interrupted' : 'idle', history: initial, provisional: [], input: initial.pending_expression ?? '', pendingKey: null, language: 'zh', notice: null, ignoredFrames: 0, restore: null}
  const listeners = new Set<() => void>()
  let generation = 0, disposed = false, admission: PublicAdmission | null = null, abort: AbortController | null = null
  let ticket: {run: number; cancelRequested: boolean; dispatched: boolean; cancelRun: number | null} | null = null
  const live = (run: number) => !disposed && run === generation
  const publish = (patch: Partial<ChatView>) => { if (!disposed) { view = {...view, ...patch}; listeners.forEach(fn => fn()) } }
  const note = (kind: ChatNoticeKind) => ({kind, at: Date.now()})
  const frozen = (): PublicBinding => parsePublicBinding({...base, revision: view.history.history.position.revision, head_turn_id: view.history.history.position.head_turn_id})
  const same = (a: PublicBinding, b: PublicBinding) => JSON.stringify(a) === JSON.stringify(b)

  async function refresh(run: number) {
    try { const snapshot = await transport.read(); if (live(run)) publish({history: snapshot}) } catch { /* keep the last valid history */ }
  }
  function fail(error: unknown, run: number, input: string) {
    if (!live(run)) return
    const code = error instanceof CompanionRequestError ? error.code : 'network_error'
    const restore = input ? {text: input, at: Date.now()} : null
    if (code === 'network_error') { publish({phase: 'unknown', provisional: [], notice: note('unknown')}); return }
    if (code === 'stale_revision' || code === 'operation_pending') { publish({phase: 'stale', provisional: [], input: '', pendingKey: null, notice: note('stale'), restore}); void refresh(run); return }
    if (code === 'friend_epoch_changed' || code === 'account_changed') { publish({phase: 'failed', provisional: [], input: '', pendingKey: null, notice: note('epoch_changed'), restore}); return }
    if (code === 'conversation_read_only') { publish({phase: 'failed', provisional: [], input: '', pendingKey: null, notice: note('read_only'), restore}); void refresh(run); return }
    if (code === 'auth_session_required') { publish({phase: 'failed', provisional: [], input: '', pendingKey: null, notice: note('auth'), restore}); return }
    if (code === 'forbidden') { publish({phase: 'failed', provisional: [], input: '', pendingKey: null, notice: note('forbidden'), restore}); return }
    publish({phase: 'interrupted', provisional: [], notice: note('network')})
  }

  async function verify(expected: PublicAdmission, run: number, attempts = 0): Promise<void> {
    const receipt = await transport.receipt(expected.operation_id)
    if (!live(run)) return
    if (receipt.owner_id !== expected.binding.account_id) throw new CompanionRequestError('account_changed')
    const operation = parsePrivateOperation(receipt.operation)
    if (operation.operation_id !== expected.operation_id) throw new CompanionRequestError('invalid_response')
    const snapshot = parsePrivateSnapshot(receipt.snapshot, friendId, epoch)
    if (operation.status === 'committed') {
      if (snapshot.conversation.id !== expected.binding.session_id || snapshot.history.position.revision <= expected.binding.revision
        || !snapshot.history.turns.some(t => t.turn_id === operation.turn_id)) throw new CompanionRequestError('checkpoint_changed')
      publish({phase: 'committed', history: snapshot, provisional: [], input: '', pendingKey: null})
    } else if (operation.status === 'cancelled') {
      publish({phase: 'cancelled', history: snapshot, provisional: [], input: '', pendingKey: null, notice: note('cancelled'), restore: view.input ? {text: view.input, at: Date.now()} : null})
    } else if (operation.status === 'retryable_failed') {
      publish({phase: 'interrupted', history: snapshot, provisional: [], notice: note('retryable')})
    } else if (operation.status === 'failed_final' || operation.status === 'stale') {
      publish({phase: 'failed', history: snapshot, provisional: [], input: '', pendingKey: null, notice: note(operation.status === 'stale' ? 'stale' : 'failed'), restore: view.input ? {text: view.input, at: Date.now()} : null})
    } else {
      // A `complete` frame is not a commit. Ask the authority again (bounded), never assume.
      publish({phase: 'awaiting_commit'})
      if (attempts > 60) { publish({phase: 'unknown', notice: note('unknown')}); return }
      await sleep(250)
      if (live(run)) await verify(expected, run, attempts + 1)
    }
  }

  async function runStream(expected: PublicAdmission, run: number) {
    admission = expected
    const receiver = createPublicReceiver(expected)
    publish({phase: 'starting', provisional: []})
    abort = new AbortController()
    const response = await transport.stream(expected, abort.signal)
    let ignored = 0
    const finished = await readPrivatePublicStream(response, abort.signal, () => live(run), event => {
      if (!live(run)) return
      const outcome = receiver.receive(event)
      if (outcome === 'ignored') { ignored++; publish({ignoredFrames: view.ignoredFrames + 1}); return }
      const snap = receiver.snapshot()
      // Public terminal frames retire presentation; they never unlock a write by themselves.
      const phase: ChatPhase = snap.phase === 'waiting_start' ? 'starting' : snap.phase === 'generating' ? 'generating' : 'awaiting_commit'
      publish({phase, provisional: snap.segments})
    })
    void ignored
    if (finished && live(run)) { receiver.finish(); await verify(expected, run) }
  }

  async function cancelKnown(expected: PublicAdmission, run: number) {
    const result = await transport.cancel(expected.operation_id)
    if (!live(run)) return
    if (result.operation_id !== expected.operation_id) throw new CompanionRequestError('invalid_response')
    if (result.status === 'cancelled') { await verify(expected, run) }
    else if (result.status === 'committed') { await verify(expected, run); if (live(run)) publish({notice: note('commit_won')}) }
    else publish({phase: 'interrupted', provisional: []})
  }

  return {
    subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn) } },
    getSnapshot: () => view,
    /** Explicit send. One intent → one key; the caller decides nothing else. */
    async start(input: string, language: Lang, key = randomId('cmd', 10)) {
      if (disposed || view.history.conversation.status !== 'active' || view.history.pending_operation) return false
      if (ACTIVE.includes(view.phase) || view.phase === 'unknown' || !input.trim() || input.length > 2000) return false
      const binding = frozen()
      const run = ++generation, current = {run, cancelRequested: false, dispatched: false, cancelRun: null as number | null}
      ticket = current; admission = null; abort = new AbortController()
      publish({phase: 'sending', provisional: [], input, pendingKey: key, language, notice: null, restore: null})
      try {
        current.dispatched = true
        // The send itself is never aborted: leaving the page (dispose) must not turn an
        // already-sent message into an unknown one. Only the presentation stream is aborted.
        const started = await transport.send({key, text: input, language, presented_turn_id: binding.head_turn_id, expected_revision: binding.revision})
        if (!same(started.admission.binding, binding)) throw new CompanionRequestError('checkpoint_changed')
        if (!disposed && ticket === current) admission = started.admission
        if (!live(run)) {
          // Stop won the race against the receipt: cancel the now-known operation once.
          if (!disposed && ticket === current && current.cancelRequested && current.cancelRun !== null) await cancelKnown(started.admission, current.cancelRun)
          return true
        }
        await runStream(started.admission, run)
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return true
        fail(error, live(run) ? run : current.cancelRun ?? -1, input)
      }
      return true
    },
    async cancel() {
      if (disposed || !['sending', 'starting', 'generating', 'awaiting_commit'].includes(view.phase)) return
      if (ticket) ticket.cancelRequested = true
      const run = ++generation
      if (ticket) ticket.cancelRun = run
      if (admission) abort?.abort()
      publish({phase: 'cancelling', provisional: []})
      if (!admission) return // The receipt is still in flight; it will be cancelled once known.
      try { await cancelKnown(admission, run) } catch (error) { fail(error, run, view.input) }
    },
    /** Explicit retry of the SAME operation/key/input/baseline. Never automatic. */
    async retry() {
      const op = view.history.pending_operation
      if (disposed || !op || op.status !== 'retryable_failed') return
      const run = ++generation
      publish({phase: 'starting', notice: null, provisional: [], input: view.history.pending_expression ?? view.input})
      try {
        const started = await transport.retry(op.operation_id)
        if (!live(run)) return
        if (started.operation.operation_id !== op.operation_id) throw new CompanionRequestError('invalid_response')
        await runStream(started.admission, run)
      } catch (error) {
        if (error instanceof CompanionRequestError && error.code === 'operation_not_retryable') { publish({notice: note('not_retryable')}); void refresh(run); return }
        fail(error, run, view.input)
      }
    },
    /** Result unknown: ask about the ORIGINAL key before anything else. */
    async lookup() {
      if (disposed || view.phase !== 'unknown' || !view.pendingKey) return
      const run = ++generation, key = view.pendingKey
      try {
        const found = await transport.lookup(key)
        if (!live(run)) return
        if (found.admission) { await runStream(found.admission, run); return }
        const fake: PublicAdmission = {version: 'private-public-segments.v1', operation_id: found.operation.operation_id, run_epoch: 1, binding: frozen()}
        await verify(fake, run)
      } catch (error) {
        if (!live(run)) return
        if (error instanceof CompanionRequestError && error.code === 'operation_not_found') { publish({notice: note('lookup_missing')}); return }
        publish({notice: note('unknown')})
      }
    },
    /** After a confirmed “not found”, resend with the SAME key (server stays idempotent). */
    async resendSameKey() {
      if (view.phase !== 'unknown' || !view.pendingKey) return
      const key = view.pendingKey, text = view.input
      view = {...view, phase: 'idle'}
      await this.start(text, view.language, key)
    },
    /** Re-attach to an operation that was pending when this page (re)loaded. */
    async resume() {
      const op = view.history.pending_operation
      if (disposed || !op) return
      const run = ++generation
      try {
        const receipt = await transport.receipt(op.operation_id)
        if (!live(run)) return
        const status = parsePrivateOperation(receipt.operation).status
        if (status === 'retryable_failed') { publish({phase: 'interrupted', input: view.history.pending_expression ?? '', notice: note('retryable')}); return }
        if (receipt.admission) { publish({input: view.history.pending_expression ?? ''}); await runStream(receipt.admission, run); return }
        const fake: PublicAdmission = {version: 'private-public-segments.v1', operation_id: op.operation_id, run_epoch: 1, binding: frozen()}
        await verify(fake, run)
      } catch (error) { fail(error, run, view.input) }
    },
    /** Replace history after an out-of-band authority action (rollback, correction, reread). */
    replaceHistory(snapshot: PrivateSnapshot) { if (!ACTIVE.includes(view.phase)) { ++generation; publish({history: snapshot, phase: snapshot.pending_operation ? 'interrupted' : 'idle', provisional: []}) } },
    dismissNotice() { publish({notice: null}) },
    consumeRestore() { const r = view.restore; if (r) publish({restore: null}); return r },
    suspend() { ++generation; abort?.abort(); if (ACTIVE.includes(view.phase)) publish({phase: 'interrupted', provisional: []}) },
    dispose() { disposed = true; ++generation; abort?.abort(); listeners.clear() },
  }
}
export type ChatController = ReturnType<typeof createChatController>
