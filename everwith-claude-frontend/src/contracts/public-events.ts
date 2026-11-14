/** Candidate only. Complete typed NDJSON frames, never fields scraped from provider JSON. */
export const PUBLIC_VERSION = "private-public-segments.v1"
export type PublicBinding = {account_id:string;friend_id:string;friend_epoch:number;session_id:string;revision:number;head_turn_id:string;allow_fictional_thought:boolean}
export type PublicAdmission = {version:typeof PUBLIC_VERSION;operation_id:string;run_epoch:number;binding:PublicBinding}
export type PublicSegment = {segment_id:string;kind:"spoken"|"action"|"narration"|"fictional_thought";text:string}
type Envelope = {version:typeof PUBLIC_VERSION;operation_id:string;run_epoch:number;seq:number}
export type PublicEvent = Envelope & (
  {type:"start";binding:PublicBinding} | {type:"segment";segment:PublicSegment} |
  {type:"complete"} | {type:"cancelled"} | {type:"failed";reason:"generation_failed"|"permission_changed"})
export class PublicProtocolError extends Error {constructor(){super("invalid_public_stream");this.name="PublicProtocolError"}}
const invalid=():never=>{throw new PublicProtocolError()}
function object(value:unknown):Record<string,unknown>{if(!value||typeof value!=="object"||Array.isArray(value))return invalid();return value as Record<string,unknown>}
function exact(value:Record<string,unknown>,keys:string[]){if(Object.keys(value).sort().join("|")!==[...keys].sort().join("|"))invalid()}
function integer(value:unknown,min=1):number{if(!Number.isSafeInteger(value)||Number(value)<min)return invalid();return Number(value)}
function id(value:unknown):string{if(typeof value!=="string"||!value.length||value.length>128||!/^[A-Za-z0-9_.:-]+$/.test(value))return invalid();return value}
function publicText(value:unknown):string{
  if(typeof value!=="string"||!value.trim()||value.length>2000)return invalid()
  for(let i=0;i<value.length;i++){
    const c=value.charCodeAt(i)
    if(c<32&&c!==9&&c!==10||c===127)return invalid()
    if(c>=0xd800&&c<=0xdbff){const next=value.charCodeAt(++i);if(!(next>=0xdc00&&next<=0xdfff))return invalid()}
    else if(c>=0xdc00&&c<=0xdfff)return invalid()
  }
  return value
}
export function parsePublicBinding(value:unknown):PublicBinding{
  const row=object(value);exact(row,["account_id","friend_id","friend_epoch","session_id","revision","head_turn_id","allow_fictional_thought"])
  if(typeof row.allow_fictional_thought!=="boolean")return invalid()
  return {account_id:id(row.account_id),friend_id:id(row.friend_id),friend_epoch:integer(row.friend_epoch),session_id:id(row.session_id),
    revision:integer(row.revision),head_turn_id:id(row.head_turn_id),allow_fictional_thought:row.allow_fictional_thought}
}
export function parsePublicAdmission(value:unknown):PublicAdmission{
  const row=object(value);exact(row,["version","operation_id","run_epoch","binding"])
  if(row.version!==PUBLIC_VERSION)return invalid()
  return {version:PUBLIC_VERSION,operation_id:id(row.operation_id),run_epoch:integer(row.run_epoch),binding:parsePublicBinding(row.binding)}
}
export function parsePublicEvent(value:unknown):PublicEvent{
  const row=object(value),base=["version","operation_id","run_epoch","seq","type"]
  if(row.version!==PUBLIC_VERSION)return invalid()
  const envelope={version:PUBLIC_VERSION,operation_id:id(row.operation_id),run_epoch:integer(row.run_epoch),seq:integer(row.seq,0)} as Envelope
  if(row.type==="start"){exact(row,[...base,"binding"]);return {...envelope,type:"start",binding:parsePublicBinding(row.binding)}}
  if(row.type==="segment"){
    exact(row,[...base,"segment"]);const segment=object(row.segment);exact(segment,["segment_id","kind","text"])
    if(typeof segment.kind!=="string"||!["spoken","action","narration","fictional_thought"].includes(segment.kind))return invalid()
    return {...envelope,type:"segment",segment:{segment_id:id(segment.segment_id),kind:segment.kind as PublicSegment["kind"],text:publicText(segment.text)}}
  }
  if(row.type==="complete"||row.type==="cancelled"){exact(row,base);return {...envelope,type:row.type}}
  if(row.type==="failed"){
    exact(row,[...base,"reason"]);if(row.reason!=="generation_failed"&&row.reason!=="permission_changed")return invalid()
    return {...envelope,type:"failed",reason:row.reason}
  }
  return invalid()
}

/** fatal UTF-8 decoder + LF framing + JSON.parse of a full frame. No regex extraction. */
export class PublicEventDecoder {
  private decoder=new TextDecoder("utf-8",{fatal:true})
  private buffer=""
  private bytes=0
  private ended=false
  constructor(private receive:(event:PublicEvent)=>void){}
  push(chunk:Uint8Array){
    if(this.ended)return invalid()
    this.bytes+=chunk.byteLength;if(this.bytes>65536)return invalid()
    try{this.buffer+=this.decoder.decode(chunk,{stream:true});this.frames()}catch{this.ended=true;return invalid()}
  }
  private frames(){
    for(let end=this.buffer.indexOf("\n");end>=0;end=this.buffer.indexOf("\n")){
      let frame=this.buffer.slice(0,end);this.buffer=this.buffer.slice(end+1)
      if(frame.endsWith("\r"))frame=frame.slice(0,-1)
      if(!frame.length||new TextEncoder().encode(frame).length>16384)return invalid()
      this.receive(parsePublicEvent(JSON.parse(frame)))
    }
    if(new TextEncoder().encode(this.buffer).length>16384)return invalid()
  }
  finish(){
    if(this.ended)return invalid()
    this.ended=true
    try{this.buffer+=this.decoder.decode();this.frames();if(this.buffer.length)return invalid()}catch{return invalid()}
  }
}

/** Provisional view state. Terminal events have no storage/reducer/control capability. */
export function createPublicReceiver(admission:PublicAdmission){
  const expected=parsePublicAdmission(admission),seen=new Map<number,string>(),segments:PublicSegment[]=[]
  let phase:"waiting_start"|"generating"|"awaiting_commit"|"cancelled"|"failed"="waiting_start",last=-1,total=0
  const snapshot=()=>({phase,segments:segments.map(s=>({...s})),lastSeq:last})
  return {
    snapshot,
    receive(value:PublicEvent){
      const event=parsePublicEvent(value)
      if(event.operation_id!==expected.operation_id)return invalid()
      if(event.run_epoch<expected.run_epoch)return "ignored" as const
      if(event.run_epoch!==expected.run_epoch)return invalid()
      const fingerprint=JSON.stringify(event),previous=seen.get(event.seq)
      if(previous!==undefined){if(previous!==fingerprint)return invalid();return "ignored" as const}
      if(event.seq!==last+1||event.seq>8)return invalid()
      if(event.type==="start"){
        if(phase!=="waiting_start"||event.seq!==0||JSON.stringify(event.binding)!==JSON.stringify(expected.binding))return invalid()
        phase="generating"
      }else{
        if(phase!=="generating")return invalid()
        if(event.type==="segment"){
          const segment=event.segment
          if(segments.length>=6||segments.some(s=>s.segment_id===segment.segment_id)||total+segment.text.length>6000
            ||segment.kind==="fictional_thought"&&!expected.binding.allow_fictional_thought)return invalid()
          total+=segment.text.length;segments.push({...segment})
        }else if(event.type==="complete"){
          if(!segments.some(s=>s.kind==="spoken"))return invalid();phase="awaiting_commit"
        }else{phase=event.type==="cancelled"?"cancelled":"failed";segments.length=0}
      }
      last=event.seq;seen.set(last,fingerprint);return "applied" as const
    },
    finish(){if(phase==="waiting_start"||phase==="generating")return invalid();return snapshot()},
  }
}
