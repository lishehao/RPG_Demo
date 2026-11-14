/** Bodyless display cues. Identity/checkpoint are checked again by the server. */
export type DialogueCheckpoint={session_id:string;branch_id:string;revision:number;head_turn_id:string;content_revision:number;invalidation_epoch:number;access_epoch:number}
export type DialoguePresentation={checkpoint:DialogueCheckpoint;turn_id:string;message_id:string;actor_id:string}
export type DialogueCall={schema:"dialogue-expression-call-v1";call_id:string;provider_mode:"local_deterministic";provider_version:string;character_id:string;character_version:string;friend_id:string;friend_epoch:number;role_id:string;actor_id:string;source_kind:"private"|"story";source_session_id:string;checkpoint:DialogueCheckpoint;turn_id:string;message_id:string;message_sequence:number;expression:"neutral"|"happy"|"surprised";degradation:null|"unsupported_expression"}
export type DialogueLedger={has:(key:string)=>boolean;add:(key:string)=>void}
export function presentationKey(p:DialoguePresentation){return `${p.actor_id}:${p.turn_id}:${p.message_id}`}
export function createDialogueLedger(binding:{accountId:string;friendId:string;friendEpoch:number;kind:string;sourceSessionId:string}):DialogueLedger{
 const key=`tiny-stories-expression:${binding.accountId}:${binding.friendId}:${binding.friendEpoch}:${binding.kind}:${binding.sourceSessionId}`
 let seen=new Set<string>()
 try{const saved=JSON.parse(sessionStorage.getItem(key)||"[]");if(!Array.isArray(saved)||saved.length>256||saved.some(v=>typeof v!=="string"||v.length>400))throw Error();seen=new Set(saved)}catch{throw Error("visual_ledger_unavailable")}
 return {has:value=>seen.has(value),add(value){seen.add(value);seen=new Set([...seen].slice(-256));sessionStorage.setItem(key,JSON.stringify([...seen]))}}
}
