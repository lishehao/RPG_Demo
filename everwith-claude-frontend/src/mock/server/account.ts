/**
 * LOCAL MOCK ACCOUNT. Email + password only; no verification mail, no recovery
 * (business rule: the first phase offers no password recovery). Hashing here only
 * avoids keeping the typed password in localStorage; it is not production auth.
 */
import {db, now, save} from '../db'
import {fail, ok, str} from '../http'
import type {MockRequest, MockResult} from '../http'
import {account, actor} from './context'
import {randomId} from '../../lib/util'
import {isPersonaAvatar} from '../../art/generated'

async function digest(salt: string, password: string) {
  const bytes = new TextEncoder().encode(`${salt}:${password}`)
  const out = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(out), b => b.toString(16).padStart(2, '0')).join('')
}
export function accountJSON() {
  const d = db(), a = account()
  const persona = a ? a.persona : d.guest_personas[d.guest_id] ?? null
  return {mode: 'local_mock', authenticated: !!a, account: a ? {id: a.id, email: a.email} : null, guest_id: d.guest_id, persona, request_protection: 'none-local-mock'}
}
/** Attach this browser's guest progress to the account exactly once (idempotent). */
function mergeGuest(accountId: string) {
  const d = db(), guest = d.guest_id
  if (d.merged_guests[guest] && d.merged_guests[guest] !== accountId) return // Never re-assign to a second account.
  for (const table of [d.stories, d.games, d.works, d.previews] as Record<string, {owner: string}>[]) {
    for (const row of Object.values(table)) if (row.owner === guest) row.owner = accountId
  }
  d.merged_guests[guest] = accountId
  if (d.guest_personas[guest] && !d.accounts[accountId].persona) d.accounts[accountId].persona = d.guest_personas[guest]
}
const EMAIL = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/

export async function handleAccount(req: MockRequest): Promise<MockResult | null> {
  const d = db()
  if (req.path === '/account' && req.method === 'GET') return ok(accountJSON())
  if (req.path === '/account/login' && req.method === 'POST') {
    const email = str(req.body, 'email', 254).trim().toLowerCase(), password = str(req.body, 'password', 200)
    const row = Object.values(d.accounts).find(a => a.email === email)
    if (!row || await digest(row.salt, password) !== row.hash) fail(401, 'invalid_credentials')
    d.session_account = row!.id; mergeGuest(row!.id); save()
    return ok(accountJSON())
  }
  if (req.path === '/account/register' && req.method === 'POST') {
    const email = str(req.body, 'email', 254).trim().toLowerCase(), password = str(req.body, 'password', 200)
    if (!EMAIL.test(email)) fail(422, 'invalid_email')
    if (password.length < 8) fail(422, 'weak_password')
    if (Object.values(d.accounts).some(a => a.email === email)) fail(409, 'email_taken')
    const salt = randomId('salt', 12), id = randomId('acc', 10)
    d.accounts[id] = {id, email, salt, hash: await digest(salt, password), created_at: now(), persona: null}
    d.session_account = id; mergeGuest(id); save()
    return ok(accountJSON(), 201)
  }
  if (req.path === '/account/logout' && req.method === 'POST') {
    d.session_account = null
    // A fresh guest identity after sign-out: earlier guest progress already belongs to the account.
    if (d.merged_guests[d.guest_id]) d.guest_id = randomId('guest')
    save(); return ok(accountJSON())
  }
  if (req.path === '/account/persona' && req.method === 'PUT') {
    const a = account()
    const previous = a ? a.persona : d.guest_personas[actor()] ?? null
    // avatar: absent keeps the current one, null clears it, otherwise one of the preset ids.
    const raw = req.body?.avatar
    if (raw !== undefined && raw !== null && !isPersonaAvatar(raw)) fail(422, 'invalid_avatar')
    const avatar = raw === undefined ? previous?.avatar ?? null : raw as string | null
    const persona = {name: str(req.body, 'name', 40).trim(), bio: str(req.body, 'bio', 400, true).trim(), avatar}
    if (a) a.persona = persona; else d.guest_personas[actor()] = persona
    save(); return ok(accountJSON())
  }
  return null
}
