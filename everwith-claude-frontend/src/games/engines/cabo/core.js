export const check=(ok,message)=>{if(!ok)throw Error(message);};
export function random(s){s.rng=(Math.imul(s.rng,1664525)+1013904223)>>>0;return s.rng/4294967296;}
export function shuffle(s,input){const a=[...input];for(let i=a.length-1;i>0;i--){const j=Math.floor(random(s)*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
export const sum=a=>a.reduce((n,x)=>n+x,0);
export const emit=(s,type,details={})=>s.events.push({type,...details});
export function record(s,old,actor,a){s.revision++;s.history.push({id:s.revision,round:old.round,actor,action:structuredClone(a),events:structuredClone(s.events)});return s;}
export function seeded(seed){let x=seed>>>0;return()=>{x=(Math.imul(x,1664525)+1013904223)>>>0;return x/4294967296;};}
