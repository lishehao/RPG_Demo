/** Tiny request/response helpers shared by the mock route handlers. */
export class HttpError extends Error {
  constructor(public status: number, public code: string, public detail: Record<string, unknown> | null = null) { super(code) }
}
export type MockRequest = {method: string; path: string; query: URLSearchParams; body: Record<string, unknown> | null; signal?: AbortSignal | null}
export type MockResult = {status: number; json: unknown} | {status: number; stream: ReadableStream<Uint8Array>; contentType: string} | {drop: true; afterCommit?: () => void}

export const ok = (json: unknown, status = 200): MockResult => ({status, json})
export const fail = (status: number, code: string, detail: Record<string, unknown> | null = null): never => { throw new HttpError(status, code, detail) }

export function str(body: Record<string, unknown> | null, key: string, max = 4000, optional = false): string {
  const v = body?.[key]
  if (v === undefined && optional) return ''
  if (typeof v !== 'string' || v.length > max) fail(400, 'invalid_request', {field: key})
  return v as string
}
export function int(body: Record<string, unknown> | null, key: string, optional = false): number {
  const v = body?.[key]
  if (v === undefined && optional) return -1
  if (!Number.isSafeInteger(v)) fail(400, 'invalid_request', {field: key})
  return v as number
}
export const fingerprint = (value: unknown) => JSON.stringify(value)
