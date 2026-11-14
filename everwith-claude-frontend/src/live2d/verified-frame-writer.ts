import {applyCarrierSurprise, CARRIER_SP_PARAMETER} from './carrier-parameter-units';

/** Internal final-write boundary, after a character's guarded contract/visual adapter.
 * This does not add a public raw-parameter, head, hair, blink or viseme route.
 * Call once for this model's composed frame, then model.update()/official drawModel().
 */
export type Character = 'arthur' | 'lena' | 'marcus' | 'nora' | 'iris';
export interface CoreModel {
  getParameterCount(): number;
  getDrawableCount(): number;
  getParameterId(index: number): {getString(): string};
  getParameterDefaultValue(index: number): number;
  getParameterMinimumValue(index: number): number;
  getParameterMaximumValue(index: number): number;
  getParameterValueByIndex(index: number): number;
  setParameterValueByIndex(index: number, value: number, weight?: number): void;
}
const heads = {arthur:[8,4,2.5],lena:[8,2,1.5],marcus:[8,2,1.5],nora:[3,1,1],iris:[3,1,1]} as const;
const drawables = {arthur:25,lena:24,marcus:23,nora:36,iris:36} as const;
const defaults:Record<string,number> = {
  ParamAngleX:0,ParamAngleY:0,ParamAngleZ:0,ParamEyeLOpen:1,ParamEyeROpen:1,
  ParamBrowLY:0,ParamBrowRY:0,ParamMouthForm:0,ParamMouthOpenY:0,
  ParamExpressionHappy:0,ParamExpressionSurprised:0,
};
export function bindVerifiedFrameWriter(character:Character, model:CoreModel) {
  const count=model.getParameterCount();
  if(count!==(character==='iris'?23:22)||model.getDrawableCount()!==drawables[character])
    throw Error('Frozen model inventory mismatch; validate registry MOC SHA before binding');
  const index=new Map<string,number>();
  for(let i=0;i<count;i++) {
    const id=model.getParameterId(i).getString();
    if(index.has(id))throw Error('Duplicate Core parameter '+id);
    index.set(id,i);
  }
  const caps:Record<string,readonly[number,number]>={
    ParamAngleX:[-heads[character][0],heads[character][0]],
    ParamAngleY:[-heads[character][1],heads[character][1]],
    ParamAngleZ:[-heads[character][2],heads[character][2]],
    ParamEyeLOpen:[0,1],ParamEyeROpen:[0,1],ParamBrowLY:[0,1],ParamBrowRY:[0,1],
    ParamMouthForm:[0,.45],ParamMouthOpenY:[0,1],ParamExpressionHappy:[0,1],ParamExpressionSurprised:[0,1],
  };
  for(const [id,range] of Object.entries(caps)) {
    const i=index.get(id);
    if(i===undefined||model.getParameterMinimumValue(i)>range[0]||model.getParameterMaximumValue(i)<range[1])
      throw Error('Verified Core parameter missing/range mismatch '+id);
  }
  const originalSP=index.get('ParamExpressionSurprised')!, carrier=index.get(CARRIER_SP_PARAMETER);
  if(character==='iris'&&(carrier!==22||model.getParameterMinimumValue(carrier)!==0||model.getParameterMaximumValue(carrier)!==16384))
    throw Error('Iris carrier units mismatch');
  return (canonical:Readonly<Record<string,number>>) => {
    for(const id of Object.keys(canonical))if(!(id in caps))throw Error('Unverified channel '+id);
    const requested={...defaults,...canonical};
    for(const [id,value] of Object.entries(requested))if(!Number.isFinite(value))throw Error('Nonfinite '+id);
    const happy=requested.ParamExpressionHappy, surprise=requested.ParamExpressionSurprised;
    if(character==='arthur'&&((happy!==0&&happy!==1)||(surprise!==0&&surprise!==1)))
      throw Error('Arthur requires discrete authored face materials');
    if(character!=='arthur'&&character!=='iris'&&((happy>0&&happy<1)||(surprise>0&&surprise<1))&&
      (requested.ParamEyeLOpen!==0||requested.ParamEyeROpen!==0||requested.ParamMouthOpenY!==0))
      throw Error('Reference fractional face swap requires closed eyes and mouth');
    // Validate the whole frame before touching the live model.
    const values=Object.fromEntries(Object.entries(caps).map(([id,[lo,hi]])=>{
      const raw=character==='iris'&&id==='ParamMouthForm'&&surprise>0?0:requested[id];
      return [id,Math.max(lo,Math.min(hi,raw))];
    }));
    for(let i=0;i<count;i++)model.setParameterValueByIndex(i,model.getParameterDefaultValue(i),1);
    for(const [id,value] of Object.entries(values))model.setParameterValueByIndex(index.get(id)!,value,1);
    const units=character==='iris'?applyCarrierSurprise(model,originalSP,carrier!,values.ParamExpressionSurprised):null;
    return {effective:Object.fromEntries(Object.keys(caps).map(id=>[id,model.getParameterValueByIndex(index.get(id)!)])),carrierUnits:units};
  };
}
