import {check,random,shuffle,sum,emit,record,seeded} from './core.js';
import {RULE_EVIDENCE,PROVISIONAL_COMPONENT_PROFILE,ability} from './rule-evidence.js';
export {ability};
export const DECK=PROVISIONAL_COMPONENT_PROFILE.counts.flatMap((count,v)=>Array(count).fill(v));
export function create({players=4,seed=711}={}){check(Number.isInteger(players)&&players>=2&&players<=5,'players');const s={game:'cabo',version:3,edition:'Shareful 2025 English procedures / provisional components',rng:seed>>>0,players:Array.from({length:players},(_,id)=>({id,total:0,resetUsed:false,cards:[],roundGain:0})),round:1,starter:0,current:0,phase:'setup',deck:[],discard:[],truth:{},up:{},knowledge:[],setupDone:[],drawn:null,drawnFrom:null,caller:null,finalQueue:[],privateReveal:null,activeAbility:null,ended:false,winners:[],events:[],history:[],revision:0,roundResults:[]};s.starter=Math.floor(random(s)*players);setup(s);return s;}
function setup(s){s.truth={};s.up={};s.roundResults=[];let ids=shuffle(s,DECK).map((value,i)=>{const id=`c${s.round}-${i}`;s.truth[id]=value;return id;});s.deck=shuffle(s,ids);s.players.forEach(p=>{p.cards=s.deck.splice(-4);p.positions=Object.fromEntries(p.cards.map((id,i)=>[id,i]));});s.discard=[s.deck.pop()];s.up[s.discard[0]]=true;s.knowledge=s.players.map(()=>({}));s.setupDone=[];s.current=s.starter;s.phase='setup';s.drawn=null;s.drawnFrom=null;s.caller=null;s.finalQueue=[];s.privateReveal=null;s.activeAbility=null;emit(s,'deal',{round:s.round,count:4});assertState(s);}
function expose(s,ids){for(const id of ids){s.up[id]=true;for(const k of s.knowledge)k[id]=s.truth[id];}}
function finishTurn(s){s.drawn=null;s.drawnFrom=null;s.privateReveal=null;s.activeAbility=null;if(s.caller!==null)s.finalQueue=s.finalQueue.filter(id=>id!==s.current);if(s.caller!==null&&!s.finalQueue.length){scoreRound(s);return;}s.current=(s.current+1)%s.players.length;s.phase='turn';emit(s,'turn',{player:s.current});}
function recycle(s){
 const top=s.discard.pop();
 check(top&&s.discard.length,'emptyPile');
 s.deck=shuffle(s,s.discard);s.discard=[top];
 for(const id of s.deck){s.up[id]=false;for(const k of s.knowledge)delete k[id];}
 emit(s,'reshuffle',{count:s.deck.length});
}
export function roundScores(s){
 const totals=s.players.map(p=>sum(p.cards.map(id=>s.truth[id]))),low=Math.min(...totals);
 const moon=s.players.find(p=>p.cards.length===4&&p.cards.map(id=>s.truth[id]).sort((a,b)=>a-b).join(',')==='12,12,13,13')?.id;
 const callerWins=s.caller!==null&&totals[s.caller]===low;
 return s.players.map(p=>{
 const winner=totals[p.id]===low&&(!callerWins||p.id===s.caller);
 const failed=p.id===s.caller&&!callerWins;
 return {player:p.id,values:p.cards.map(id=>s.truth[id]),sum:totals[p.id],gain:moon!==undefined?(p.id===moon?0:50):winner?0:totals[p.id]+(failed?5:0),reason:moon!==undefined?'shootingTheMoon':winner?'lowest':failed?'caboFailed':'cardSum'};
 });
}
function scoreRound(s){const rows=roundScores(s);expose(s,s.players.flatMap(p=>p.cards));for(const r of rows){const p=s.players[r.player];r.before=p.total;r.rawAfter=p.total+r.gain;p.total=r.rawAfter;p.roundGain=r.gain;r.reset=p.total===100&&!p.resetUsed;if(r.reset){p.total=50;p.resetUsed=true;}r.after=p.total;}s.roundResults=rows;emit(s,'roundScore',{rows});s.phase='roundEnd';s.drawn=null;s.privateReveal=null;if(s.players.some(p=>p.total>100)){s.ended=true;s.phase='ended';const sorted=[...s.players].sort((a,b)=>a.total-b.total),best=sorted[0];s.winners=sorted.filter(p=>p.total===best.total).map(p=>p.id);emit(s,'end',{winners:s.winners});}}
export function act(state,actor,a){check(!state.ended,'ended');check(Number.isInteger(actor)&&actor>=0&&actor<state.players.length,'actor');check(a&&typeof a.type==='string','action');check(actor===state.current||state.phase==='roundEnd','turn');const s=structuredClone(state);s.events=[];const p=s.players[actor];
 if(a.type==='nextRound'){check(s.phase==='roundEnd','phase');const low=Math.min(...s.players.map(p=>p.roundGain));for(let i=1;i<=s.players.length;i++){const id=(s.starter+i)%s.players.length;if(s.players[id].roundGain===low){s.starter=id;break;}}s.round++;setup(s);}
 else if(s.phase==='setup'){check(a.type==='initialPeek'&&a.cards?.length===2&&new Set(a.cards).size===2&&a.cards.every(id=>p.cards.includes(id)),'peekTwo');for(const id of a.cards)s.knowledge[actor][id]=s.truth[id];s.privateReveal={player:actor,cards:a.cards,reason:'setup'};s.phase='reveal';emit(s,'peek',{player:actor,count:2,target:actor});}
 else if(s.phase==='reveal'){check(a.type==='ack','ack');const setupPeek=s.privateReveal.reason==='setup';s.privateReveal=null;if(setupPeek){s.setupDone.push(actor);if(s.setupDone.length===s.players.length){s.current=s.starter;s.phase='turn';}else{s.current=(actor+1)%s.players.length;s.phase='setup';}}else finishTurn(s);}
 else if(s.phase==='turn'){
  if(a.type==='call'){check(s.caller===null,'called');s.caller=actor;s.finalQueue=Array.from({length:s.players.length-1},(_,i)=>(actor+i+1)%s.players.length);emit(s,'call',{player:actor,remaining:s.finalQueue.length});s.current=(actor+1)%s.players.length;}
  else{check(a.type==='draw'&&['deck','discard'].includes(a.source),'draw');if(a.source==='deck'&&!s.deck.length)recycle(s);const pile=a.source==='deck'?s.deck:s.discard;check(pile.length,'emptyPile');s.drawn=pile.pop();s.drawnFrom=a.source;s.knowledge[actor][s.drawn]=s.truth[s.drawn];if(a.source==='discard')expose(s,[s.drawn]);s.phase=a.source==='deck'?'drawn':'exchange';emit(s,'draw',{player:actor,source:a.source,card:s.drawn});if(a.source==='deck'&&!s.deck.length)recycle(s);}
 }
 else if(s.phase==='drawn'||s.phase==='exchange'){
  if(a.type==='exchange'){check(a.cards?.length&&new Set(a.cards).size===a.cards.length&&a.cards.every(id=>p.cards.includes(id)),'selectCards');const ordered=p.cards.filter(id=>a.cards.includes(id)),values=ordered.map(id=>s.truth[id]),match=new Set(values).size===1,drawn=s.drawn,from=s.drawnFrom;expose(s,ordered);if(match){const first=p.cards.indexOf(ordered[0]);p.cards=p.cards.flatMap((id,i)=>i===first?[drawn]:ordered.includes(id)?[]:[id]);s.discard.push(...ordered);const slot=p.positions[ordered[0]];for(const id of ordered)delete p.positions[id];p.positions[drawn]=slot;s.up[drawn]=false;emit(s,'exchange',{player:actor,removed:ordered,values,card:drawn,from,count:p.cards.length});}else{s.discard.push(drawn);s.up[drawn]=true;for(const id of ordered)s.up[id]=false;emit(s,'matchFailed',{player:actor,cards:ordered,values,card:drawn,count:p.cards.length});}finishTurn(s);}
  else{check(s.phase==='drawn'&&a.type==='discard','mustExchange');const drawn=s.drawn,v=s.truth[drawn];s.discard.push(drawn);expose(s,[drawn]);emit(s,'discard',{player:actor,card:drawn,value:v});s.drawn=null;const ab=ability(v);if(a.useAbility&&ab){s.activeAbility=ab;s.phase='ability';const targetExists=ab==='swap'||s.players.some(q=>(ab==='peek'?q.id===actor:q.id!==actor)&&q.cards.some(id=>!s.up[id]));if(!targetExists)finishTurn(s);}else finishTurn(s);}
 }
 else if(s.phase==='ability'){
  if(a.type==='cancelAbility'){emit(s,'abilityDeclined',{player:actor,ability:s.activeAbility});finishTurn(s);}
  else if(s.activeAbility==='swap'){check(a.type==='swap'&&p.cards.includes(a.own),'swapOwn');const other=s.players.find(q=>q.id!==actor&&q.cards.includes(a.other));check(other,'swapOther');const i=p.cards.indexOf(a.own),j=other.cards.indexOf(a.other);const ownSlot=p.positions[a.own],otherSlot=other.positions[a.other];delete p.positions[a.own];delete other.positions[a.other];p.positions[a.other]=ownSlot;other.positions[a.own]=otherSlot;p.cards[i]=a.other;other.cards[j]=a.own;emit(s,'swap',{player:actor,otherPlayer:other.id,own:a.own,other:a.other});finishTurn(s);}
  else{check(a.type==='peek','peek');const owner=s.players.find(q=>q.cards.includes(a.card));check(owner&&!s.up[a.card]&&(s.activeAbility==='peek'?owner.id===actor:owner.id!==actor),'peekTarget');s.knowledge[actor][a.card]=s.truth[a.card];s.privateReveal={player:actor,cards:[a.card],reason:s.activeAbility};s.phase='reveal';emit(s,'peek',{player:actor,target:owner.id,count:1});}
 }else check(false,'phase');record(s,state,actor,a);assertState(s);return s;
}
// Allowlisted observer projection. Private state never crosses the HTTP boundary.
export function observe(s,id=null){
 const authorized=Number.isInteger(id)&&id>=0&&id<s.players.length;
 const publicValue=card=>s.up[card]||s.phase==='roundEnd'||s.ended?s.truth[card]:null;
 return {
 game:s.game,version:s.version,edition:s.edition,ruleEvidence:{...RULE_EVIDENCE},observer:authorized?id:null,
 round:s.round,current:s.current,starter:s.starter,phase:s.phase,revision:s.revision,
 deck:Array(s.deck.length).fill(null),discard:s.discard.map(card=>({id:card,value:s.truth[card]})),
 players:s.players.map(p=>({id:p.id,total:p.total,resetUsed:p.resetUsed,roundGain:p.roundGain,cards:p.cards.map(card=>({id:card,slot:p.positions[card],faceUp:!!s.up[card],value:publicValue(card)}))})),
 knowledge:authorized?Object.fromEntries(Object.entries(s.knowledge[id]).filter(([card,value])=>typeof value==='number'&&s.truth[card]!==undefined)):{},
 drawn:s.drawn?{id:s.drawn,value:s.current===id||s.drawnFrom==='discard'?s.truth[s.drawn]:null}:null,drawnFrom:s.drawnFrom,
 privateReveal:authorized&&s.privateReveal?.player===id?{player:s.privateReveal.player,reason:s.privateReveal.reason,cards:s.privateReveal.cards.map(card=>({id:card,value:s.truth[card]}))}:null,
 activeAbility:s.activeAbility,caller:s.caller,finalQueue:[...s.finalQueue],ended:s.ended,winners:[...s.winners],roundResults:['roundEnd','ended'].includes(s.phase)?publicScoreRows(s.roundResults):[],
 // Events contain only public commits; failed matches were shown to the table.
 events:s.events.map(publicRuleEvent).filter(Boolean)
 };
}
const EVENT_FIELDS=Object.freeze({deal:['round','count'],turn:['player'],reshuffle:['count'],call:['player','remaining'],exchange:['player','removed','values','card','from','count'],matchFailed:['player','cards','values','card','count'],discard:['player','card','value'],swap:['player','otherPlayer','own','other'],abilityDeclined:['player','ability'],roundScore:['rows'],end:['winners']});
function publicScoreRows(rows){return rows.map(r=>Object.fromEntries(['player','values','sum','gain','reason','before','rawAfter','reset','after'].filter(k=>r[k]!==undefined).map(k=>[k,structuredClone(r[k])])));}
function publicRuleEvent(e){const fields=EVENT_FIELDS[e.type];if(!fields)return null;const projected={type:e.type};for(const key of fields)if(e[key]!==undefined)projected[key]=structuredClone(e[key]);if(e.type==='roundScore')projected.rows=publicScoreRows(e.rows);return projected;}
export function assertState(s){const ids=[...s.deck,...s.discard,...s.players.flatMap(p=>p.cards),...(s.drawn?[s.drawn]:[])];check(ids.length===52&&new Set(ids).size===52,'cardsConservation');check(DECK.every((_,i)=>Object.values(s.truth).sort((a,b)=>a-b)[i]===DECK[i]),'valuesConservation');check(s.players.every(p=>p.cards.length>=1&&p.cards.length<=4&&p.total>=0&&new Set(p.cards.map(id=>p.positions[id])).size===p.cards.length),'playersState');return true;}
export function decide(o,difficulty='medium',{seed=1}={}){const p=o.players[o.current],rng=seeded(seed),known=c=>c.value??o.knowledge[c.id],estimate=c=>known(c)??6.5;
 if(o.phase==='setup')return{type:'initialPeek',cards:[p.cards[0].id,p.cards.at(-1).id]};if(o.phase==='reveal')return{type:'ack'};if(o.phase==='roundEnd')return{type:'nextRound'};
 const high=[...p.cards].sort((a,b)=>estimate(b)-estimate(a)),groups=new Map();for(const c of p.cards)if(known(c)!==undefined){const v=known(c);groups.set(v,[...(groups.get(v)||[]),c.id]);}
 if(o.phase==='turn'){const own=sum(p.cards.map(estimate)),other=Math.min(...o.players.filter(q=>q.id!==p.id).map(q=>sum(q.cards.map(estimate)))),threshold=difficulty==='easy'?12:difficulty==='hard'?9:10;if(o.caller===null&&(own<=threshold||own<other-7&&p.cards.every(c=>known(c)!==undefined)))return{type:'call'};const top=o.discard.at(-1),matches=[...groups.entries()].find(([v,g])=>g.length>1&&v*g.length>(top?.value??99)+2);if(top&&(top.value<estimate(high[0])-2||matches))return{type:'draw',source:'discard'};return{type:'draw',source:'deck'};}
 if(o.phase==='drawn'||o.phase==='exchange'){const v=o.drawn.value,match=[...groups.entries()].filter(([value,g])=>g.length>1).sort((a,b)=>b[0]*b[1].length-a[0]*a[1].length)[0];if(match&&(o.phase==='exchange'||match[0]*match[1].length>v))return{type:'exchange',cards:match[1]};const target=difficulty==='easy'&&rng()<.2?p.cards[Math.floor(rng()*p.cards.length)]:high[0];if(o.phase==='exchange'||v<estimate(target)-.7)return{type:'exchange',cards:[target.id]};return{type:'discard',useAbility:!!ability(v)};}
 if(o.phase==='ability'){if(o.activeAbility==='swap'){const opponents=o.players.filter(q=>q.id!==p.id).flatMap(q=>q.cards),low=opponents.sort((a,b)=>estimate(a)-estimate(b))[0];return{type:'swap',own:high[0].id,other:low.id};}const targets=o.players.filter(q=>o.activeAbility==='peek'?q.id===p.id:q.id!==p.id).flatMap(q=>q.cards).filter(c=>!c.faceUp);targets.sort((a,b)=>(known(a)!==undefined)-(known(b)!==undefined));return{type:'peek',card:targets[0].id};}throw Error('phase');}
