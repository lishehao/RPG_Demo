/**
 * Artwork assignment for Splendor cards and nobles — a TypeScript port of the reference
 * `art-catalog.js` (handoff reference/component-excerpts/gem-court/splendor). It maps a
 * PUBLIC card/noble id to a crop of an approved package image. It holds no rule values,
 * no randomness and never receives hidden reserve identities.
 */
import type {SplendorCard} from '../../../games/engines/splendor/src/data'
import {GAME_ASSETS} from './shared'

const DIR = `${GAME_ASSETS}/splendor`
export type ArtSpec = {src: string; w: number; h: number; rect: [number, number, number, number]}

const FILES: Record<number, {file: string; w: number; h: number}> = {
  6: {file: 'nobles-a.jpg', w: 1024, h: 1536}, 7: {file: 'nobles-b.jpg', w: 1024, h: 1536},
  11: {file: 'renaissance-tier3-20261007.png', w: 1536, h: 1024}, 12: {file: 'renaissance-tier2-20261007.png', w: 1536, h: 1024}, 13: {file: 'renaissance-tier1-20261007.png', w: 1536, h: 1024},
  15: {file: 'renaissance-tier2-warehouse-round3-20261007.png', w: 1024, h: 1536}, 16: {file: 'renaissance-tier2-ledger-round3-20261007.png', w: 1024, h: 1536},
  17: {file: 'renaissance-tier2-caravan-round3-20261007.png', w: 1024, h: 1536}, 18: {file: 'renaissance-tier3-cathedral-round4-20261007.png', w: 1024, h: 1536},
  19: {file: 'renaissance-tier3-harbor-round4-20261007.png', w: 1024, h: 1536},
}
const cells = (xs: [number, number][], ys: [number, number][]) => ys.flatMap(([top, bottom]) => xs.map(([left, right]) => [left + 6, top + 6, right - left - 12, bottom - top - 12] as [number, number, number, number]))
// Measured gutters of the noble sheets (pixels in 1024×1536), copied from the reference.
const NOBLE_RECTS: Record<6 | 7, [number, number, number, number][]> = {
  6: cells([[0, 507], [516, 1024]], [[0, 496], [505, 1008], [1017, 1536]]),
  7: cells([[0, 507], [518, 1024]], [[0, 499], [510, 1011], [1022, 1536]]),
}
const mix = (input: number) => { let x = input; x = Math.imul(x ^ (x >>> 16), 0x45d9f3b); x = Math.imul(x ^ (x >>> 16), 0x45d9f3b); return (x ^ (x >>> 16)) >>> 0 }
// Fixed, balanced art-only ordering (does not follow the six-card bonus blocks).
const VARIANTS: Record<1 | 2 | 3, number[]> = Object.fromEntries(([1, 2, 3] as const).map(tier => {
  const size = [0, 40, 30, 20][tier]
  const order = Array.from({length: size}, (_, i) => i).sort((a, b) => mix(a + 999 + tier * 97) - mix(b + 999 + tier * 97) || a - b)
  const result: number[] = Array(size)
  order.forEach((ordinal, rank) => { result[ordinal] = rank % 6 })
  return [tier, result]
})) as Record<1 | 2 | 3, number[]>

const spec = (source: number, rect: [number, number, number, number]): ArtSpec => ({src: `${DIR}/${FILES[source].file}`, w: FILES[source].w, h: FILES[source].h, rect})

export function cardArt(card: Pick<SplendorCard, 'id' | 'tier'>): ArtSpec {
  const source = card.tier === 3 ? 11 : card.tier === 2 ? 12 : 13
  const ordinal = Number(card.id.slice(1)) - [0, 0, 40, 70][card.tier]
  const cell = card.id === 'c51' ? 1 : VARIANTS[card.tier][ordinal]
  if (card.tier === 3 && (cell === 0 || cell === 2)) return spec(cell === 0 ? 18 : 19, [0, 0, 1, 1])
  if (card.tier === 2 && (cell === 0 || cell === 1 || cell === 4)) return spec(({0: 15, 1: 16, 4: 17} as Record<number, number>)[cell], [0, 0, 1, 1])
  return spec(source, [(cell % 3) / 3 + .002, Math.floor(cell / 3) / 2 + .003, 1 / 3 - .004, 1 / 2 - .006])
}
export function nobleArt(id: string): ArtSpec {
  const n = Number(id.slice(1)), source = n < 6 ? 6 : 7, cell = n < 6 ? n : n - 6
  const [x, y, w, h] = NOBLE_RECTS[source][cell]
  return spec(source, [x / 1024, y / 1536, w / 1024, h / 1536])
}
export const GEM_IMAGES: Record<string, string> = {
  diamond: `${DIR}/gem-diamond-finish-round4-20261007.png`, sapphire: `${DIR}/gem-sapphire-finish-round4-20261007.png`, emerald: `${DIR}/gem-emerald-polish-round4-20261007.png`,
  ruby: `${DIR}/gem-ruby-polish-round4-20261007.png`, onyx: `${DIR}/gem-onyx-polish-round4-20261007.png`, gold: `${DIR}/gem-gold-finish-round4-20261007.png`,
}
export const TIER_BACKS: Record<1 | 2 | 3, string> = {1: `${DIR}/tier-back-1-20261005.png`, 2: `${DIR}/tier-back-2-20261005.png`, 3: `${DIR}/tier-back-3-20261005.png`}
export const TABLE_CLOTH = `${DIR}/teal-velour-calm-round4-20261007.png`
export const SALON = `${DIR}/backgrounds/salon.png`
/** Ink tones per gem (from the reference gem material) for code-drawn pips and labels. */
export const GEM_TONES: Record<string, {bg: string; ink: string}> = {
  diamond: {bg: '#eef3fa', ink: '#1d2430'}, sapphire: {bg: '#1f5fc4', ink: '#ffffff'}, emerald: {bg: '#11834f', ink: '#ffffff'},
  ruby: {bg: '#b8142f', ink: '#ffffff'}, onyx: {bg: '#262b36', ink: '#ffffff'}, gold: {bg: '#d2a43d', ink: '#22190a'},
}
