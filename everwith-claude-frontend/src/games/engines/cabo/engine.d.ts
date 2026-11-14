import type {CaboAbility} from './rule-evidence'
export {ability} from './rule-evidence'
export type {CaboAbility}
export type CaboPhase = 'setup' | 'reveal' | 'turn' | 'drawn' | 'exchange' | 'ability' | 'roundEnd' | 'ended'
export type CaboAction =
  | {type: 'initialPeek'; cards: string[]}
  | {type: 'ack'}
  | {type: 'call'}
  | {type: 'draw'; source: 'deck' | 'discard'}
  | {type: 'exchange'; cards: string[]}
  | {type: 'discard'; useAbility?: boolean}
  | {type: 'cancelAbility'}
  | {type: 'swap'; own: string; other: string}
  | {type: 'peek'; card: string}
  | {type: 'nextRound'}
/** Full authoritative state. Only the local mock authority may hold it. */
export type CaboState = {
  game: 'cabo'; version: 3; edition: string; rng: number
  players: {id: number; total: number; resetUsed: boolean; cards: string[]; roundGain: number; positions: Record<string, number>}[]
  round: number; starter: number; current: number; phase: CaboPhase
  deck: string[]; discard: string[]; truth: Record<string, number>; up: Record<string, boolean>; knowledge: Record<string, number>[]
  setupDone: number[]; drawn: string | null; drawnFrom: 'deck' | 'discard' | null; caller: number | null; finalQueue: number[]
  privateReveal: {player: number; cards: string[]; reason: string} | null; activeAbility: CaboAbility | null
  ended: boolean; winners: number[]; events: CaboEvent[]; history: unknown[]; revision: number; roundResults: CaboScoreRow[]
}
export type CaboEvent = {type: string; [key: string]: unknown}
export type CaboScoreRow = {player: number; values: number[]; sum: number; gain: number; reason: 'shootingTheMoon' | 'lowest' | 'caboFailed' | 'cardSum'; before?: number; rawAfter?: number; reset?: boolean; after?: number}
export type CaboCardView = {id: string; slot: number; faceUp: boolean; value: number | null}
/** Allowlisted observer projection (what a seat may see). */
export type CaboObservation = {
  game: 'cabo'; version: 3; edition: string; ruleEvidence: Record<string, unknown>; observer: number | null
  round: number; current: number; starter: number; phase: CaboPhase; revision: number
  deck: null[]; discard: {id: string; value: number}[]
  players: {id: number; total: number; resetUsed: boolean; roundGain: number; cards: CaboCardView[]}[]
  knowledge: Record<string, number>
  drawn: {id: string; value: number | null} | null; drawnFrom: 'deck' | 'discard' | null
  privateReveal: {player: number; reason: string; cards: {id: string; value: number}[]} | null
  activeAbility: CaboAbility | null; caller: number | null; finalQueue: number[]; ended: boolean; winners: number[]
  roundResults: CaboScoreRow[]; events: CaboEvent[]
}
export const DECK: number[]
export function create(options?: {players?: number; seed?: number}): CaboState
export function roundScores(s: CaboState): CaboScoreRow[]
export function act(state: CaboState, actor: number, action: CaboAction): CaboState
export function observe(s: CaboState, id?: number | null): CaboObservation
export function assertState(s: CaboState): true
export function decide(o: CaboObservation, difficulty?: 'easy' | 'medium' | 'hard', options?: {seed?: number}): CaboAction
