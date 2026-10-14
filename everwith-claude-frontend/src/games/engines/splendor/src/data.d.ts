// Typings for the frozen data file (new; the .js file is byte-identical to the handoff).
export type SplendorColor = 'diamond' | 'sapphire' | 'emerald' | 'ruby' | 'onyx'
export type SplendorCard = {id: string; tier: 1 | 2 | 3; bonus: SplendorColor; points: number; cost: Record<SplendorColor, number>; name: string; art: string}
export type SplendorNoble = {id: string; name: string; points: number; cost: Record<SplendorColor, number>; art: string}
export const CARDS: SplendorCard[]
export const NOBLES: SplendorNoble[]
