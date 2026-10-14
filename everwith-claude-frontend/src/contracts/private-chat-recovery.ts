import {PublicEventDecoder,type PublicEvent} from "./public-events"

/** A reader owns presentation only. Disconnect/timeout never cancels or retries an operation. */
export async function readPrivatePublicStream(response:Response,signal:AbortSignal,
  live:()=>boolean,receive:(event:PublicEvent)=>void,idleTimeoutMs=45_000):Promise<boolean>{
  const retireBody=()=>{void response.body?.cancel().catch(()=>{})}
  if(signal.aborted||!live()){retireBody();return false}
  if(!response.ok||response.headers.get("content-type")?.split(";")[0].trim()!=="application/x-ndjson"||!response.body){
    retireBody();throw Error("stream_unavailable")
  }
  const reader=response.body.getReader(),decoder=new PublicEventDecoder(receive)
  let timeout:ReturnType<typeof setTimeout>|undefined,timedOut=false
  // Do not wait for a transport's potentially stalled cancellation acknowledgement.
  const cancel=()=>{void reader.cancel().catch(()=>{})}
  signal.addEventListener("abort",cancel,{once:true})
  try{
    while(live()&&!signal.aborted){
      timeout=setTimeout(()=>{timedOut=true;cancel()},idleTimeoutMs)
      const chunk=await reader.read()
      clearTimeout(timeout)
      if(signal.aborted||!live())return false
      if(timedOut)throw Error("stream_read_timeout")
      if(chunk.done){decoder.finish();return true}
      decoder.push(chunk.value)
    }
    return false
  }finally{
    clearTimeout(timeout);signal.removeEventListener("abort",cancel)
    cancel();reader.releaseLock()
  }
}
