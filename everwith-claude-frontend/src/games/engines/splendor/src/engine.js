import {CARDS,NOBLES} from './data.js';
export const COLORS=['diamond','sapphire','emerald','ruby','onyx'];
export const ALL=[...COLORS,'gold'];
export const LABELS={diamond:'钻石',sapphire:'蓝宝石',emerald:'祖母绿',ruby:'红宝石',onyx:'缟玛瑙',gold:'黄金'};
export const cardById=id=>CARDS.find(c=>c.id===id);
export const nobleById=id=>NOBLES.find(n=>n.id===id);
export const emptyTokens=()=>Object.fromEntries(ALL.map(c=>[c,0]));
export const total=t=>ALL.reduce((sum,c)=>sum+(t[c]||0),0);
export function bonuses(player){const out=Object.fromEntries(COLORS.map(c=>[c,0]));for(const id of player.cards)out[cardById(id).bonus]++;return out;}
export const score=p=>p.cards.reduce((s,id)=>s+cardById(id).points,0)+3*p.nobles.length;
function rng(seed){let h=2166136261;for(const c of String(seed))h=Math.imul(h^c.charCodeAt(0),16777619);return()=>{h+=0x6d2b79f5;let t=h;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return ((t^t>>>14)>>>0)/4294967296;};}
function shuffled(a,r){a=[...a];for(let i=a.length-1;i>0;i--){const j=Math.floor(r()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
export function createGame({players=3,seed=String(Date.now())}={}){
 if(![2,3,4].includes(players))throw Error('需要 2–4 位玩家');const random=rng(seed),decks={},market={};
 for(const tier of [1,2,3]){decks[tier]=shuffled(CARDS.filter(c=>c.tier===tier).map(c=>c.id),random);market[tier]=decks[tier].splice(0,4);}
 const names=['玩家一','玩家二','玩家三','玩家四'];const bank=Object.fromEntries(COLORS.map(c=>[c,players===2?4:players===3?5:7]));bank.gold=5;
 return {version:1,seed,players:Array.from({length:players},(_,i)=>({id:i,name:names[i],tokens:emptyTokens(),cards:[],reserved:[],nobles:[]})),decks,market,nobles:shuffled(NOBLES.map(n=>n.id),random).slice(0,players+1),bank,current:0,round:1,phase:'action',ending:false,ended:false,winners:[],events:[],mainMoves:0,pendingNobles:[],lastAction:null};
}
export function priceFor(player,card){const discount=bonuses(player);return Object.fromEntries(COLORS.map(c=>[c,Math.max(0,card.cost[c]-discount[c])]));}
export function paymentFor(player,card){const cost=priceFor(player,card),pay=emptyTokens();for(const c of COLORS){pay[c]=Math.min(cost[c],player.tokens[c]);pay.gold+=cost[c]-pay[c];}return pay.gold<=player.tokens.gold?pay:null;}
export function missingFor(player,card){const cost=priceFor(player,card);return Math.max(0,COLORS.reduce((s,c)=>s+Math.max(0,cost[c]-player.tokens[c]),0)-player.tokens.gold);}
export function eligibleNobles(state,player){const b=bonuses(player);return state.nobles.filter(id=>COLORS.every(c=>b[c]>=nobleById(id).cost[c]));}
function subsets(a,n,start=0,prefix=[],out=[]){if(prefix.length===n){out.push([...prefix]);return out;}for(let i=start;i<a.length;i++)subsets(a,n,i+1,[...prefix,a[i]],out);return out;}
export function legalActions(s,id=s.current){if(s.ended||s.current!==id)return [];const p=s.players[id];if(s.phase==='return')return ALL.filter(c=>p.tokens[c]>0).map(color=>({type:'return',color}));if(s.phase==='noble')return s.pendingNobles.map(noble=>({type:'noble',noble}));if(s.phase!=='action')return [];
 const actions=[],available=COLORS.filter(c=>s.bank[c]>0);if(available.length)for(const selected of subsets(available,Math.min(3,available.length)))actions.push({type:'take',colors:selected});for(const c of COLORS)if(s.bank[c]>=4)actions.push({type:'take',colors:[c,c]});
 for(const tier of [1,2,3])for(const card of s.market[tier].filter(Boolean)){if(paymentFor(p,cardById(card)))actions.push({type:'buy',card});if(p.reserved.length<3)actions.push({type:'reserve',card});}
 for(const card of p.reserved.filter(Boolean))if(paymentFor(p,cardById(card)))actions.push({type:'buy',card});
 if(p.reserved.length<3)for(const tier of [1,2,3])if((Array.isArray(s.decks[tier])?s.decks[tier].length:s.decks[tier])>0)actions.push({type:'reserve',tier});return actions;
}
function check(condition,message){if(!condition)throw Error(message);}
function pushEvent(s,event){s.events.push({id:s.events.length,round:s.round,player:s.current,...event});}
function finishTurn(s){const p=s.players[s.current];if(score(p)>=15)s.ending=true;if(s.ending&&s.current===s.players.length-1){s.ended=true;s.phase='ended';let best=Math.max(...s.players.map(score));let eligible=s.players.filter(p=>score(p)===best);let fewest=Math.min(...eligible.map(p=>p.cards.length));s.winners=eligible.filter(p=>p.cards.length===fewest).map(p=>p.id);pushEvent(s,{type:'end',winners:[...s.winners]});return;}
 s.current=(s.current+1)%s.players.length;if(s.current===0)s.round++;s.phase='action';s.pendingNobles=[];
}
function resolveNobles(s){const ids=eligibleNobles(s,s.players[s.current]);if(ids.length>1){s.phase='noble';s.pendingNobles=ids;return;}if(ids.length===1){const id=ids[0];s.nobles=s.nobles.filter(n=>n!==id);s.players[s.current].nobles.push(id);pushEvent(s,{type:'noble',noble:id});}finishTurn(s);}
function afterAction(s){if(total(s.players[s.current].tokens)>10){s.phase='return';return;}resolveNobles(s);}
function popMarket(s,id){const card=cardById(id),row=s.market[card.tier],idx=row.indexOf(id);check(idx!==-1,'这张牌已经不在市场上了');row[idx]=s.decks[card.tier].shift()??null;}
export function applyAction(state,actor,action){const s=structuredClone(state);check(!s.ended,'本局已结束');check(s.current===actor,'还没轮到你');const p=s.players[actor];
 if(s.phase==='return'){check(action.type==='return','请先归还超额宝石');check(ALL.includes(action.color)&&p.tokens[action.color]>0,'不能归还没有的宝石');p.tokens[action.color]--;s.bank[action.color]++;pushEvent(s,{type:'return',color:action.color});if(total(p.tokens)<=10)resolveNobles(s);return s;}
 if(s.phase==='noble'){check(action.type==='noble'&&s.pendingNobles.includes(action.noble),'请选择一位满足条件的贵族');p.nobles.push(action.noble);s.nobles=s.nobles.filter(id=>id!==action.noble);pushEvent(s,{type:'noble',noble:action.noble});finishTurn(s);return s;}
 check(s.phase==='action','当前不能执行此动作');
 if(action.type==='take'){const chosen=action.colors;check(Array.isArray(chosen)&&chosen.length>0,'请选择宝石');check(chosen.every(c=>COLORS.includes(c)),'黄金只能通过预留获得');const same=chosen.length===2&&chosen[0]===chosen[1];if(same)check(s.bank[chosen[0]]>=4,'拿两枚同色前，公共池至少需要四枚');else{check(new Set(chosen).size===chosen.length,'请选择不同颜色');check(chosen.length===Math.min(3,COLORS.filter(c=>s.bank[c]>0).length),'有三种颜色时，必须拿三种不同宝石');check(chosen.every(c=>s.bank[c]>0),'公共池里没有这种宝石');}for(const c of chosen){s.bank[c]--;p.tokens[c]++;}pushEvent(s,{type:'take',colors:[...chosen]});
 }else if(action.type==='reserve'){check(p.reserved.length<3,'最多只能预留三张牌');let id=action.card,blind=false;if(id){check(CARDS.some(c=>c.id===id),'未知卡牌');popMarket(s,id);}else{check([1,2,3].includes(action.tier)&&s.decks[action.tier].length>0,'这叠牌已经抽完了');id=s.decks[action.tier].shift();blind=true;}p.reserved.push(id);const gold=s.bank.gold>0;if(gold){s.bank.gold--;p.tokens.gold++;}pushEvent(s,{type:'reserve',card:blind?null:id,tier:cardById(id).tier,blind,gold});
 }else if(action.type==='buy'){const card=cardById(action.card);check(card,'未知卡牌');const reserved=p.reserved.includes(card.id);check(reserved||s.market[card.tier].includes(card.id),'只能购买市场牌或自己的预留牌');const pay=action.payment??paymentFor(p,card);check(pay,'宝石和永久折扣还不够');check(Object.keys(pay).every(c=>ALL.includes(c)),'未知宝石');check(ALL.every(c=>Number.isInteger(pay[c]??0)&&(pay[c]??0)>=0&&(pay[c]??0)<=p.tokens[c]),'支付的宝石数量不正确');const cost=priceFor(p,card);check(COLORS.every(c=>(pay[c]??0)<=cost[c]),'无需多付宝石');check(COLORS.reduce((n,c)=>n+cost[c]-(pay[c]??0),0)===(pay.gold??0),'黄金替代数量不正确');for(const c of ALL){p.tokens[c]-=pay[c]??0;s.bank[c]+=pay[c]??0;}if(reserved)p.reserved=p.reserved.filter(id=>id!==card.id);else popMarket(s,card.id);p.cards.push(card.id);pushEvent(s,{type:'buy',card:card.id,payment:{...pay},points:card.points,bonus:card.bonus});
 }else throw Error('未知动作');s.mainMoves++;s.lastAction={player:actor,...Object.fromEntries(Object.entries(action).filter(([,value])=>value!==undefined))};afterAction(s);return s;
}
export function playerView(s,id){const view=structuredClone(s);view.decks=Object.fromEntries([1,2,3].map(t=>[t,s.decks[t].length]));view.players=view.players.map(p=>p.id===id?p:{...p,reserved:p.reserved.map(()=>null)});delete view.seed;delete view.lastAction;return view;}
export function assertInvariants(s){const count=s.players.length,per=count===2?4:count===3?5:7;for(const c of ALL)check(s.bank[c]+s.players.reduce((v,p)=>v+p.tokens[c],0)===(c==='gold'?5:per),'宝石总数不守恒');check(ALL.every(c=>s.bank[c]>=0),'公共池出现负数');const all=[...Object.values(s.decks).flat(),...Object.values(s.market).flat().filter(Boolean),...s.players.flatMap(p=>[...p.cards,...p.reserved])];check(all.length===90&&new Set(all).size===90,'卡牌数量或唯一性错误');for(const p of s.players){check(p.reserved.length<=3,'预留牌超限');check(ALL.every(c=>Number.isInteger(p.tokens[c])&&p.tokens[c]>=0),'玩家宝石非法');check(p.id===s.current&&s.phase==='return'||total(p.tokens)<=10,'玩家宝石超限');}const nobles=[...s.nobles,...s.players.flatMap(p=>p.nobles)];check(nobles.length===count+1&&new Set(nobles).size===count+1,'贵族数量异常');return true;}
