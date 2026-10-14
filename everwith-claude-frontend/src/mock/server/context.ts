import {db, save} from '../db'
import type {AccountRow} from '../db'
import {fail} from '../http'
import {scenarios} from '../scenarios'

/** Current owner id: the signed-in local mock account, otherwise this browser's guest id. */
export function actor(): string { const d = db(); return d.session_account ?? d.guest_id }
export function account(): AccountRow | null { const d = db(); return d.session_account ? d.accounts[d.session_account] ?? null : null }
export function requireAccount(): AccountRow {
  if (scenarios.consume('auth.expired')) fail(401, 'auth_session_required')
  if (scenarios.consume('auth.forbidden')) fail(403, 'forbidden')
  const a = account()
  if (!a) fail(401, 'auth_session_required')
  return a as AccountRow
}
export function expectAccount(body: Record<string, unknown> | null) {
  const expected = body?.expected_account_id
  if (expected !== undefined && expected !== actor()) fail(409, 'account_changed')
}
export function owned<T extends {owner: string}>(row: T | undefined | null): T {
  if (!row) fail(404, 'not_found')
  if ((row as T).owner !== actor()) fail(404, 'not_found') // Never reveal another owner's record exists.
  return row as T
}
export {save}
