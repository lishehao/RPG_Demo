import type {SplendorAction, SplendorState} from './rules'
export function chooseBotAction(view: SplendorState, id?: number, options?: {level?: 'easy' | 'medium' | 'hard'; seed?: number}): SplendorAction | null
export const LEVELS: Record<'easy' | 'medium' | 'hard', {name: string}>
export function decide(view: SplendorState, level?: 'easy' | 'medium' | 'hard', options?: {seed?: number}): {action: SplendorAction | null}
