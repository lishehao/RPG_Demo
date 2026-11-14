/**
 * Images from the user-provided GPT batch v2-batch-01 — NOT part of the handoff package.
 * Rights: 用户经 GPT 生成并提供；商用/再分发权未核实. Files are resized copies in
 * public/generated/batch-01; originals, hashes, prompts and the chosen variants are in
 * docs/GENERATED_ASSETS.json (`npm run assets:generated` re-checks them).
 * Presentation only: a backdrop or cover never stands in for a character's face, and
 * every image has a plain fallback when it is missing.
 */
import type {CharacterKey} from '../live2d/characters'

export const GENERATED_RIGHTS = '用户经 GPT 生成并提供；商用/再分发权未核实'
export const GEN = '/generated/batch-01'

/** Room behind a character's stage. Characters without their own (user-created works) get the generic room. */
export const backdropFor = (key: CharacterKey | null | undefined): string => `${GEN}/backdrop-${key ?? 'generic'}.webp`

export type SpotArtKind = 'friends' | 'recent' | 'create' | 'not-found' | 'load-error' | 'signin'
export const SPOT_ART: Record<SpotArtKind, string> = {
  friends: `${GEN}/empty-friends.webp`, recent: `${GEN}/empty-recent.webp`, create: `${GEN}/empty-create.webp`,
  'not-found': `${GEN}/state-not-found.webp`, 'load-error': `${GEN}/state-load-error.webp`, signin: `${GEN}/state-signin.webp`,
}
/** “Not found”, “sign in” and “failed to load” are different states with different pictures. */
export const errorArt = (code: string | null | undefined): SpotArtKind =>
  code === 'not_found' ? 'not-found' : code === 'auth_session_required' ? 'signin' : 'load-error'

export const CREATE_TYPE_ART = {story: `${GEN}/create-type-story.webp`, character: `${GEN}/create-type-character.webp`} as const

/** Cover choices for the user's own works (stored in the draft as the id, never as a URL). */
export const WORK_COVERS = ['work-cover-01', 'work-cover-02', 'work-cover-03', 'work-cover-04', 'work-cover-05', 'work-cover-06'] as const
export type WorkCoverId = (typeof WORK_COVERS)[number]
export const isWorkCover = (v: unknown): v is WorkCoverId => typeof v === 'string' && (WORK_COVERS as readonly string[]).includes(v)
export const workCoverUrl = (id: unknown): string | null => isWorkCover(id) ? `${GEN}/${id}.webp` : null

/** Persona avatars are objects, not people, so they are never mistaken for a character. */
export const PERSONA_AVATARS = ['persona-avatar-01', 'persona-avatar-02', 'persona-avatar-03', 'persona-avatar-04', 'persona-avatar-05', 'persona-avatar-06', 'persona-avatar-07', 'persona-avatar-08'] as const
export type PersonaAvatarId = (typeof PERSONA_AVATARS)[number]
export const isPersonaAvatar = (v: unknown): v is PersonaAvatarId => typeof v === 'string' && (PERSONA_AVATARS as readonly string[]).includes(v)
export const personaAvatarUrl = (id: unknown): string | null => isPersonaAvatar(id) ? `${GEN}/${id}.webp` : null
export const PERSONA_AVATAR_LABELS: Record<PersonaAvatarId, {zh: string; en: string}> = {
  'persona-avatar-01': {zh: '雨伞', en: 'Umbrella'}, 'persona-avatar-02': {zh: '灯笼', en: 'Lantern'}, 'persona-avatar-03': {zh: '茶杯', en: 'Teacup'},
  'persona-avatar-04': {zh: '狐狸', en: 'Fox'}, 'persona-avatar-05': {zh: '睡着的猫', en: 'Sleeping cat'}, 'persona-avatar-06': {zh: '猫头鹰', en: 'Owl'},
  'persona-avatar-07': {zh: '纸船', en: 'Paper boat'}, 'persona-avatar-08': {zh: '月亮', en: 'Crescent moon'},
}

export const BRAND_EMBLEM = `${GEN}/brand-emblem.png`
