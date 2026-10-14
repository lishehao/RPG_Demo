/** Royale introductory rules, separate from the preserved 2012 engine. */
export const EDITION = 'las-vegas-royale-broadway-zh-intro-v1';
export type Owner = number | 'neutral';
export type Phase = 'roll' | 'choose' | 'payout' | 'roundEnd' | 'ended';
export type Action = {type:'roll'} | {type:'place';face:number} | {type:'pass'} | {type:'payout'} | {type:'nextRound'};
export type Die = {id:string;owner:Owner;kind:'small'|'big';face:number|null;location:'supply'|'arena'|'casino'|'collected';casino:number|null};
export type Player = {id:number;earnings:string[];chips:number;roundGain:number;passes:number};
export type Casino = {id:number;notes:string[]};
export type Award = {owner:Owner;note:string;value:number};
export type Result = {casino:number;counts:{owner:Owner;count:number}[];excluded:Owner[];awards:Award[];returned:string[]};
export type PublicEvent = {type:string;actor?:Owner;casino?:number;face?:number;dice?:Die[];result?:Result;round?:number};
export type Entry = {revision:number;round:number;actor:number;requestId:string;action:Action;events:PublicEvent[]};
export type State = {
  edition:typeof EDITION;version:1;session:string;rng:number;round:number;starter:number;current:number;phase:Phase;
  players:Player[];dice:Die[];deck:string[];casinos:Casino[];chipPool:number;payoutIndex:number;
  results:Result[];roundHistory:Result[][];events:PublicEvent[];history:Entry[];revision:number;winners:number[];
};
export const MONEY = [11,11,13,15,13,11,9,7].flatMap((count,i)=>Array.from({length:count},(_,j)=>({id:`m${i}-${j}`,value:(i+3)*10000})));
const byId = new Map(MONEY.map(n=>[n.id,n]));
export const note = (id:string) => { const n=byId.get(id); ensure(n,'note');return n!; };
function ensure(ok:unknown, message:string):asserts ok { if(!ok) throw new Error(message); }
function random(s:State){s.rng=(Math.imul(s.rng,1664525)+1013904223)>>>0;return s.rng/4294967296;}
function shuffle(s:State, a:string[]){for(let i=a.length-1;i>0;i--){const j=Math.floor(random(s)*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
export const weight = (d:Pick<Die,'kind'>)=>d.kind==='big'?2:1;
export const remaining = (s:Pick<State,'dice'>,owner:Owner)=>s.dice.filter(d=>d.owner===owner&&['supply','arena'].includes(d.location));
export const cash = (p:Pick<Player,'earnings'>)=>p.earnings.reduce((n,id)=>n+note(id).value,0);
export const wealth = (p:Pick<Player,'earnings'|'chips'>)=>cash(p)+p.chips*10000;
function newDice(owner:Owner):Die[]{return Array.from({length:8},(_,i)=>({id:`d${owner}-${i}`,owner,kind:i===7?'big':'small',face:null,location:'supply',casino:null}));}
export function create({players=4,seed=917,starter=0,session:providedSession}: {players?:number;seed?:number;starter?:number;session?:string}={}):State {
  ensure(Number.isInteger(players)&&players>=2&&players<=5,'players');
  ensure(Number.isInteger(starter)&&starter>=0&&starter<players,'starter');
  const s:State={edition:EDITION,version:1,session:providedSession??`royale-${seed}`,rng:seed>>>0,round:1,starter,current:starter,phase:'roll',
    players:Array.from({length:players},(_,id)=>({id,earnings:[],chips:0,roundGain:0,passes:0})),
    dice:[],deck:[],casinos:[],chipPool:30,payoutIndex:0,results:[],roundHistory:[],events:[],history:[],revision:0,winners:[]};
  s.deck=shuffle(s,MONEY.map(n=>n.id)); setup(s);assertState(s);return s;
}
export function pairOrder(a:string[],b:string[]){const values=(ids:string[])=>ids.map(id=>note(id).value);return values(a).reduce((n,v)=>n+v,0)-values(b).reduce((n,v)=>n+v,0)||Math.max(...values(a))-Math.max(...values(b));}
function setup(s:State){
  ensure(s.deck.length>=12,'deck');
  const pairs=Array.from({length:6},()=>[s.deck.pop()!,s.deck.pop()!]).sort(pairOrder);
  s.casinos=pairs.map((notes,id)=>({id,notes:notes.sort((a,b)=>note(b).value-note(a).value)}));
  s.dice=s.players.flatMap(p=>newDice(p.id));
  for(const p of s.players){p.chips+=2;p.roundGain=0;s.chipPool-=2;}
  if(s.players.length===2){const neutral=newDice('neutral');for(const d of neutral){d.face=1+Math.floor(random(s)*6);d.location='casino';d.casino=d.face-1;}s.dice.push(...neutral);}
  s.current=s.starter;s.phase='roll';s.payoutIndex=0;s.results=[];s.events.push({type:'setup',round:s.round});
}
export function casinoResult(s:State,index:number):Result {
  const c=s.casinos[index];ensure(c,'casino');
  const owners:Owner[]=[...s.players.map(p=>p.id),...(s.players.length===2?['neutral' as const]:[])];
  const counts=owners.map(owner=>({owner,count:s.dice.filter(d=>d.owner===owner&&d.casino===index).reduce((n,d)=>n+weight(d),0)}));
  const excluded=counts.filter(p=>p.count>0&&counts.filter(q=>q.count===p.count).length>1).map(p=>p.owner);
  const eligible=counts.filter(p=>p.count>0&&!excluded.includes(p.owner)).sort((a,b)=>b.count-a.count);
  const notes=[...c.notes].sort((a,b)=>note(b).value-note(a).value);
  return {casino:index,counts,excluded,awards:eligible.slice(0,notes.length).map((p,i)=>({owner:p.owner,note:notes[i],value:note(notes[i]).value})),returned:notes.slice(eligible.length)};
}
export function nextStarter(results:Result[],fallback:number){
  for(const r of [...results].sort((a,b)=>b.casino-a.casino)){
    // A neutral winner cannot begin a turn; prefer the highest paid real player.
    const winner=r.awards.find(a=>a.owner!=='neutral');if(winner)return winner.owner as number;
  }
  return fallback; // Explicit deterministic fallback when nobody wins anywhere.
}
function advance(s:State){
  if(s.players.every(p=>remaining(s,p.id).length===0)){s.phase='payout';return;}
  do {s.current=(s.current+1)%s.players.length;}while(remaining(s,s.current).length===0);
  s.phase='roll';
}
export function legalActions(s:State):Action[]{
  if(s.phase==='roll')return [{type:'roll'}];
  if(s.phase==='choose')return [...new Set(remaining(s,s.current).map(d=>d.face!))].sort().map(face=>({type:'place' as const,face}));
  if(s.phase==='payout')return [{type:'payout'}];
  if(s.phase==='roundEnd')return [{type:'nextRound'}];
  return [];
}
export function actions(s:State):Action[]{const a=legalActions(s);if(s.phase==='choose'&&s.players[s.current].chips>0)a.push({type:'pass'});return a;}
function sameAction(a:Action,b:Action){return a.type===b.type&&(a.type!=='place'||b.type==='place'&&a.face===b.face);}
export function act(state:State,actor:number,action:Action,{expectedRevision=state.revision,requestId=`${state.session}:${state.revision}:${actor}`}={}):State {
  ensure(action&&typeof action.type==='string'&&Object.keys(action).sort().join(',')===(action.type==='place'?'face,type':'type'),'illegalAction');
  ensure(typeof requestId==='string'&&requestId.length>0&&requestId.length<=256,'requestId');
  const previous=state.history.find(h=>h.requestId===requestId);
  if(previous){ensure(previous.actor===actor&&sameAction(previous.action,action),'idempotencyConflict');return state;}
  ensure(expectedRevision===state.revision,'staleRevision');ensure(state.phase!=='ended','ended');ensure(actor===state.current,'turn');
  ensure(actions(state).some(a=>sameAction(a,action)),'illegalAction');
  const s=structuredClone(state);s.events=[];const p=s.players[actor];
  if(action.type==='roll'){
    for(const d of remaining(s,actor)){d.face=1+Math.floor(random(s)*6);d.location='arena';}
    s.phase='choose';s.events.push({type:'roll',actor,dice:structuredClone(remaining(s,actor))});
  }else if(action.type==='place'){
    const moved=remaining(s,actor).filter(d=>d.face===action.face);
    for(const d of remaining(s,actor)){if(d.face===action.face){d.location='casino';d.casino=action.face-1;}else {d.location='supply';d.face=null;}}
    s.events.push({type:'place',actor,face:action.face,casino:action.face-1,dice:structuredClone(moved)});advance(s);
  }else if(action.type==='pass'){
    p.chips--;p.passes++;s.chipPool++;
    for(const d of remaining(s,actor)){d.location='supply';d.face=null;}
    s.events.push({type:'pass',actor});advance(s);
  }else if(action.type==='payout'){
    const r=casinoResult(s,s.payoutIndex);s.results.push(r);s.events.push({type:'payout',result:r,casino:r.casino});
    for(const a of r.awards){if(a.owner==='neutral'){s.deck.unshift(a.note);}else {s.players[a.owner].earnings.push(a.note);s.players[a.owner].roundGain+=a.value;}}
    s.deck.unshift(...r.returned);s.casinos[s.payoutIndex].notes=[];
    for(const d of s.dice.filter(d=>d.casino===s.payoutIndex)){d.location='collected';d.casino=null;d.face=null;}
    s.payoutIndex++;
    if(s.payoutIndex===6){s.roundHistory.push(structuredClone(s.results));s.phase='roundEnd';
      if(s.round===3){s.phase='ended';const ranked=[...s.players].sort((a,b)=>wealth(b)-wealth(a)||(b.earnings.length+b.chips)-(a.earnings.length+a.chips));const top=ranked[0];s.winners=ranked.filter(p=>wealth(p)===wealth(top)&&p.earnings.length+p.chips===top.earnings.length+top.chips).map(p=>p.id);s.events.push({type:'end'});}
    }
  }else if(action.type==='nextRound'){
    s.starter=nextStarter(s.results,s.starter);s.round++;setup(s);
  }
  s.revision++;s.history.push({revision:s.revision,round:state.round,actor,action:structuredClone(action),requestId,events:structuredClone(s.events)});
  assertState(s);return s;
}
export function assertState(s:State):true {
  ensure(s&&s.edition===EDITION&&s.version===1,'edition');
  ensure(typeof s.session==='string'&&s.session.length>0,'session');ensure(Number.isInteger(s.rng)&&s.rng>=0&&s.rng<=4294967295,'rng');
  ensure(Number.isInteger(s.round)&&s.round>=1&&s.round<=3,'round');ensure(['roll','choose','payout','roundEnd','ended'].includes(s.phase),'phase');
  ensure(Array.isArray(s.players)&&s.players.length>=2&&s.players.length<=5,'players');
  ensure(s.players.every((p,i)=>p.id===i&&Number.isInteger(p.chips)&&p.chips>=0&&Number.isInteger(p.passes)&&p.passes>=0&&Number.isInteger(p.roundGain)&&p.roundGain>=0),'playerState');
  ensure(Number.isInteger(s.current)&&s.current>=0&&s.current<s.players.length&&Number.isInteger(s.starter)&&s.starter>=0&&s.starter<s.players.length,'current');
  ensure(s.casinos.length===6&&s.casinos.every((c,i)=>c.id===i&&c.notes.length<=2),'casinos');
  const ids=[...s.deck,...s.casinos.flatMap(c=>c.notes),...s.players.flatMap(p=>p.earnings)];
  ensure(ids.length===90&&new Set(ids).size===90&&ids.every(id=>byId.has(id)),'moneyConservation');
  ensure(Number.isInteger(s.chipPool)&&s.chipPool>=0&&s.chipPool+s.players.reduce((n,p)=>n+p.chips,0)===30,'chipConservation');
  ensure(s.players.every(p=>p.chips+p.passes===s.round*2),'chipHistory');
  const owners:Owner[]=[...s.players.map(p=>p.id),...(s.players.length===2?['neutral' as const]:[])];
  ensure(s.dice.length===owners.length*8&&new Set(s.dice.map(d=>d.id)).size===s.dice.length,'diceConservation');
  for(const owner of owners){const ds=s.dice.filter(d=>d.owner===owner);ensure(ds.length===8&&ds.every((d,i)=>d.id===`d${owner}-${i}`&&d.kind===(i===7?'big':'small')),'diceIdentity');}
  for(const d of s.dice){ensure(['supply','arena','casino','collected'].includes(d.location),'location');
    if(d.location==='supply'||d.location==='collected')ensure(d.face===null&&d.casino===null,'supply');
    else {ensure(Number.isInteger(d.face)&&d.face!>=1&&d.face!<=6,'face');if(d.location==='casino')ensure(d.casino===d.face!-1,'casinoFace');else ensure(d.casino===null&&d.owner===s.current&&s.phase==='choose','arena');}
    if(d.owner==='neutral')ensure(d.location==='casino'||d.location==='collected'&&s.payoutIndex>0,'neutral');
  }
  if(s.phase==='roll')ensure(remaining(s,s.current).length>0&&!s.dice.some(d=>d.location==='arena'),'rollPhase');
  if(s.phase==='choose')ensure(remaining(s,s.current).length>0&&remaining(s,s.current).every(d=>d.location==='arena'),'choosePhase');
  if(['payout','roundEnd','ended'].includes(s.phase))ensure(s.players.every(p=>remaining(s,p.id).length===0),'payoutPhase');
  ensure(Number.isInteger(s.payoutIndex)&&s.payoutIndex>=0&&s.payoutIndex<=6&&s.results.length===s.payoutIndex,'payoutIndex');
  ensure(s.casinos.every((c,i)=>c.notes.length===(i<s.payoutIndex?0:2)),'noteLocations');
  ensure(Number.isInteger(s.revision)&&s.revision>=0&&s.history.length===s.revision&&s.history.every((h,i)=>h.revision===i+1)&&new Set(s.history.map(h=>h.requestId)).size===s.history.length,'history');
  ensure(s.phase!=='ended'||s.round===3&&s.winners.length>0,'ended');return true;
}
export function observe(s:State,viewer:number){
  const {rng:_,deck,history,...v}=structuredClone(s);
  return {...v,bankCount:deck.length,history,players:s.players.map(p=>({id:p.id,chips:p.chips,roundGain:p.roundGain,passes:p.passes,
    earnings:p.id===viewer||s.phase==='ended'?p.earnings.map(id=>note(id)):p.earnings.map(()=>null),
    cash:p.id===viewer||s.phase==='ended'?cash(p):null,wealth:p.id===viewer||s.phase==='ended'?wealth(p):null}))};
}
/** Local deterministic heuristic: sees current public table, no provider calls. */
export function decide(s:State):Action {
  if(s.phase!=='choose')return actions(s)[0];
  const id=s.current,ds=remaining(s,id);
  const choices=actions(s).filter((a):a is {type:'place';face:number}=>a.type==='place').map(a=>{
    const next=structuredClone(s);const selected=ds.filter(d=>d.face===a.face);
    for(const d of next.dice.filter(d=>selected.some(q=>q.id===d.id))){d.location='casino';d.casino=a.face-1;}
    const result=casinoResult(next,a.face-1);const prize=result.awards.find(a=>a.owner===id)?.value??0;
    return {action:a,value:prize-selected.reduce((n,d)=>n+weight(d),0)*2000+note(s.casinos[a.face-1].notes[0]).value*0.08};
  }).sort((a,b)=>b.value-a.value||a.action.face-b.action.face);
  if(choices[0].value<10000&&s.players[id].chips>0&&ds.length>2)return {type:'pass'};
  return choices[0].action;
}
