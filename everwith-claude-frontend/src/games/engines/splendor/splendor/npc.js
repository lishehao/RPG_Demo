import {COLORS,ALL,cardById,nobleById,bonuses,score,legalActions,priceFor,missingFor,LABELS} from './rules.js';
function cardValue(view,p,card){const b=bonuses(p),missing=missingFor(p,card),price=priceFor(p,card),cost=Object.values(price).reduce((a,b)=>a+b,0);const noblePull=view.nobles.reduce((n,id)=>n+(nobleById(id).cost[card.bonus]>b[card.bonus]?1:0),0);const growth=p.cards.length<9?3:1.3;return card.points*4.2+growth+Math.min(2,noblePull)*.8-cost*.23-missing*1.65+(score(p)+card.points>=15?18:0);}
export function chooseBotAction(view,id=view.current,{level='medium',seed=1}={}){const p=view.players[id],legal=legalActions(view,id);if(!legal.length)return null;if(view.phase==='noble')return legal[0];const targets=[...Object.values(view.market).flat().filter(Boolean),...p.reserved.filter(Boolean)].map(cardById).sort((a,b)=>cardValue(view,p,b)-cardValue(view,p,a));
 if(view.phase==='return'){const target=targets[0],need=target?priceFor(p,target):{};return [...legal].sort((a,b)=>{const v=c=>(c==='gold'?100:Math.max(0,(need[c]||0)-(p.tokens[c]-1))*8)-(p.tokens[c]||0)*.2;return v(a.color)-v(b.color);})[0];}
 const scored=legal.map(a=>{let v=-100;if(a.type==='buy')v=cardValue(view,p,cardById(a.card))+8;if(a.type==='take'){const future={...p,tokens:{...p.tokens}};for(const c of a.colors)future.tokens[c]++;v=0;for(const target of targets.slice(0,5)){const gain=missingFor(p,target)-missingFor(future,target);v=Math.max(v,gain*2.8+cardValue(view,p,target)*.2);}v+=new Set(a.colors).size*.15;if(ALL.reduce((n,c)=>n+p.tokens[c],0)>=10)v-=2;}if(a.type==='reserve'&&a.card){const card=cardById(a.card),missing=missingFor(p,card);v=(view.bank.gold>0?1.6:0)+cardValue(view,p,card)*.23-(p.reserved.length>0?2:0);if(missing<=2&&card.points>=3)v+=2;}if(a.type==='reserve'&&a.tier)v=-5+a.tier*.1;return {a,v};});let randomSeed=seed>>>0;const random=()=>{randomSeed=(Math.imul(randomSeed,1664525)+1013904223)>>>0;return randomSeed/4294967296;};
 if(level==='easy')for(const item of scored)item.v+=random()*9;
 if(level==='hard')for(const item of scored){
   const a=item.a,opponents=view.players.filter(o=>o.id!==id);
   if(a.card){const card=cardById(a.card);const contest=opponents.reduce((n,o)=>n+(missingFor(o,card)===0?1:0),0);item.v+=contest*(a.type==='buy'?1.3:card.points>=3?1.4:0);}
   if(a.type==='buy'){
     const card=cardById(a.card),future={...p,cards:[...p.cards,card.id]},b=bonuses(future);
     const visit=view.nobles.some(n=>COLORS.every(c=>b[c]>=nobleById(n).cost[c]));
     if(visit)item.v+=10;
     const benefit=targets.filter(c=>c.id!==card.id).slice(0,6).reduce((n,c)=>n+Math.max(0,missingFor(p,c)-missingFor(future,c)),0);item.v+=benefit*.65;
   }
   if(a.type==='take'){
     const future={...p,tokens:{...p.tokens}};for(const c of a.colors)future.tokens[c]++;
     const best=targets.slice(0,7).map(c=>cardValue(view,future,c)+(missingFor(future,c)===0?4:0)).sort((a,b)=>b-a);
     item.v+=(best[0]||0)*.15+(best[1]||0)*.05;
     item.v-=Math.max(0,ALL.reduce((n,c)=>n+future.tokens[c],0)-10)*1.8;
   }
 }
 scored.sort((a,b)=>b.v-a.v);return scored[0].a;
}

export const LEVELS={easy:{name:'简单'},medium:{name:'普通'},hard:{name:'困难'}};
export function decide(view,level='medium',{seed=1}={}){if(!LEVELS[level])throw Error('Unknown difficulty');return {action:chooseBotAction(view,view.current,{level,seed})};}
