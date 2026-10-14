import type {SplendorAction, SplendorState} from '../src/engine'
export type {SplendorAction, SplendorState, SplendorPlayer, SplendorTokens, SplendorGem, SplendorColor, SplendorCard, SplendorNoble, SplendorEvent} from '../src/engine'
export {COLORS, ALL, LABELS, cardById, nobleById, emptyTokens, total, bonuses, score, priceFor, paymentFor, missingFor, eligibleNobles} from '../src/engine'
export const LEGACY_RULES_PROFILE: 'splendor-legacy-v1'
export const NEW_RULES_PROFILE: 'splendor-base-2024-v2'
export function rulesProfileFor(state: unknown): 'splendor-legacy-v1' | 'splendor-base-2024-v2'
export function createGame(options?: {rulesProfile?: string; players?: number; seed?: string}): SplendorState
export function legalActions(state: SplendorState, id?: number): SplendorAction[]
export function applyAction(state: SplendorState, actor: number, action: SplendorAction): SplendorState
export function assertInvariants(state: SplendorState): true
export function playerView(state: SplendorState, id: number): SplendorState
