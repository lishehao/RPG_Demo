import type {SplendorCard, SplendorColor, SplendorNoble} from './data'
export type {SplendorCard, SplendorColor, SplendorNoble}
export type SplendorGem = SplendorColor | 'gold'
export type SplendorTokens = Record<SplendorGem, number>
export type SplendorPlayer = {id: number; name: string; tokens: SplendorTokens; cards: string[]; reserved: (string | null)[]; nobles: string[]}
export type SplendorEvent = {id: number; round: number; player: number; type: string; [key: string]: unknown}
export type SplendorState = {
  version: 1 | 2; rulesProfile?: string; seed?: string
  players: SplendorPlayer[]; decks: Record<1 | 2 | 3, string[] | number>; market: Record<1 | 2 | 3, (string | null)[]>
  nobles: string[]; bank: SplendorTokens; current: number; round: number; phase: 'action' | 'return' | 'noble' | 'ended'
  ending: boolean; ended: boolean; winners: number[]; events: SplendorEvent[]; mainMoves: number; pendingNobles: string[]; lastAction?: unknown
}
export type SplendorAction =
  | {type: 'take'; colors: SplendorColor[]}
  | {type: 'reserve'; card: string; tier?: undefined}
  | {type: 'reserve'; tier: 1 | 2 | 3; card?: undefined}
  | {type: 'buy'; card: string; payment?: Partial<SplendorTokens>}
  | {type: 'return'; color: SplendorGem}
  | {type: 'noble'; noble: string}
export const COLORS: SplendorColor[]
export const ALL: SplendorGem[]
export const LABELS: Record<SplendorGem, string>
export function cardById(id: string): SplendorCard
export function nobleById(id: string): SplendorNoble
export function emptyTokens(): SplendorTokens
export function total(t: Partial<SplendorTokens>): number
export function bonuses(player: Pick<SplendorPlayer, 'cards'>): Record<SplendorColor, number>
export function score(player: Pick<SplendorPlayer, 'cards' | 'nobles'>): number
export function createGame(options?: {players?: number; seed?: string}): SplendorState
export function priceFor(player: SplendorPlayer, card: SplendorCard): Record<SplendorColor, number>
export function paymentFor(player: SplendorPlayer, card: SplendorCard): SplendorTokens | null
export function missingFor(player: SplendorPlayer, card: SplendorCard): number
export function eligibleNobles(state: SplendorState, player: SplendorPlayer): string[]
export function legalActions(state: SplendorState, id?: number): SplendorAction[]
export function applyAction(state: SplendorState, actor: number, action: SplendorAction): SplendorState
export function playerView(state: SplendorState, id: number): SplendorState
export function assertInvariants(state: SplendorState): true
