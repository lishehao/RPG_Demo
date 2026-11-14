export function check(ok: unknown, message: string): void
export function random(s: {rng: number}): number
export function shuffle<T>(s: {rng: number}, input: T[]): T[]
export function sum(a: number[]): number
export function emit(s: unknown, type: string, details?: Record<string, unknown>): number
export function record(s: unknown, old: unknown, actor: number, a: unknown): unknown
export function seeded(seed: number): () => number
