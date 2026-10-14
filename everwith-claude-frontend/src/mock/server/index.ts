/**
 * In-process mock of `/api/companions/*`. The UI talks to it only through a
 * fetch-compatible function, so the same parsers/clients run against mock and real.
 */
import {HttpError} from '../http'
import type {MockRequest, MockResult} from '../http'
import {scenarios} from '../scenarios'
import {handleAccount} from './account'
import {handleCatalog} from './catalog'
import {handleFriends} from './friends'
import {handleChat, startChatTicker, tickOperations} from './chat'
import {handleStories, tickStories} from './stories'
import {handleGames} from './games'
import {handleRecords} from './records'
import {handleWorks} from './works'
import {hash32, sleep} from '../../lib/util'

export const API_BASE = '/api/companions'
type Handler = (req: MockRequest) => Promise<MockResult | null> | MockResult | null
const HANDLERS: Handler[] = [handleAccount, handleCatalog, handleFriends, handleChat, handleStories, handleGames, handleRecords, handleWorks]
let started = false
function start() {
  if (started) return
  started = true
  startChatTicker()
  setInterval(tickStories, 120)
}
let requestCount = 0
export const mockStats = {requests: 0, failures: 0, dropped: 0}

export async function mockFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  start()
  const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, 'http://mock.local')
  if (!url.pathname.startsWith(API_BASE)) return new Response(JSON.stringify({error: {code: 'not_found'}}), {status: 404, headers: {'content-type': 'application/json'}})
  const method = (init.method ?? 'GET').toUpperCase()
  const path = url.pathname.slice(API_BASE.length) || '/'
  let body: Record<string, unknown> | null = null
  if (typeof init.body === 'string' && init.body) {
    try { body = JSON.parse(init.body) } catch { return json(400, {error: {code: 'invalid_json'}}) }
  }
  const signal = init.signal ?? null
  const isStream = /\/public-stream$/.test(path)
  if (!isStream) {
    const jitter = 70 + hash32(`${path}|${++requestCount}`) % 140
    await sleep(jitter + (scenarios.isOn('net.slow') ? 1500 : 0), signal ?? undefined)
  }
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  mockStats.requests++
  const req: MockRequest = {method, path, query: url.searchParams, body, signal}
  try {
    tickOperations(); tickStories()
    for (const handler of HANDLERS) {
      const result = await handler(req)
      if (!result) continue
      if ('drop' in result) { mockStats.dropped++; throw new TypeError('Failed to fetch') }
      if ('stream' in result) return new Response(result.stream, {status: result.status, headers: {'content-type': result.contentType}})
      return json(result.status, result.json)
    }
    return json(404, {error: {code: 'not_found'}})
  } catch (error) {
    if (error instanceof HttpError) { mockStats.failures++; return json(error.status, {error: {code: error.code, detail: error.detail}}) }
    throw error
  }
}
function json(status: number, value: unknown) {
  return new Response(JSON.stringify(value), {status, headers: {'content-type': 'application/json'}})
}
