export type CaboAbility = 'peek' | 'spy' | 'swap'
export const RULE_EVIDENCE: Readonly<Record<string, unknown> & {completePhysicalRulesVerified: false; components: string; abilityNumbers: string; chineseEdition: string; procedureScope: Readonly<Record<string, readonly string[]>>}>
export const PROVISIONAL_COMPONENT_PROFILE: Readonly<{name: string; verified: false; abilities: Readonly<Record<number, CaboAbility>>; counts: readonly number[]}>
export function ability(value: number): CaboAbility | null
