import * as legacy from '../src/engine.js';
import * as current from './rules-v2.js';

export const LEGACY_RULES_PROFILE='splendor-legacy-v1';
export const NEW_RULES_PROFILE=current.RULES_PROFILE;
export const {COLORS,ALL,LABELS,cardById,nobleById,emptyTokens,total,bonuses,score,priceFor,paymentFor,missingFor,eligibleNobles}=legacy;

// Saved games select their own immutable rules. Never infer an upgrade from UI.
export function rulesProfileFor(state){
 if(state?.version===1&&!Object.hasOwn(state,'rulesProfile'))return LEGACY_RULES_PROFILE;
 if(state?.version===2&&state.rulesProfile===NEW_RULES_PROFILE)return NEW_RULES_PROFILE;
 throw Error('未知或不匹配的规则版本；保留原存档，不自动升级。');
}
const engine=state=>rulesProfileFor(state)===LEGACY_RULES_PROFILE?legacy:current;
export function createGame({rulesProfile=NEW_RULES_PROFILE,...options}={}){
 if(rulesProfile===LEGACY_RULES_PROFILE)return legacy.createGame(options);
 if(rulesProfile===NEW_RULES_PROFILE)return current.createGame(options);
 throw Error('不能用未知规则版本创建新局');
}
export const legalActions=(state,id=state.current)=>engine(state).legalActions(state,id);
export const applyAction=(state,actor,action)=>engine(state).applyAction(state,actor,action);
export const assertInvariants=state=>engine(state).assertInvariants(state);
export const playerView=(state,id)=>engine(state).playerView(state,id);
