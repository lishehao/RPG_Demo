import {useLayoutEffect,useRef,useState,type RefObject} from "react"

function available(node:HTMLElement|null):node is HTMLElement {
 if(!node?.isConnected||node===document.body||node===document.documentElement||node.matches(":disabled")||node.closest('[hidden],[inert],dialog:not([open])')||!node.getClientRects().length)return false
 const visibility=window.getComputedStyle(node).visibility
 return visibility!=="hidden"&&visibility!=="collapse"
}

/** Restore a dismissed modal's owned focus, without overriding a later user choice. */
export function useModalFocusReturn(ref:RefObject<HTMLDialogElement|null>,options:{lockScroll?:boolean;initialFocusSelector?:string}={}){
 // Capture before committing the modal's children/native autofocus, not in a passive effect.
 const [origin]=useState(()=>{
  const opener=document.activeElement instanceof HTMLElement?document.activeElement:null
  return {opener,scope:opener?.closest<HTMLElement>('.ew-app')??null}
 })
 const pending=useRef<number|undefined>(undefined)
 useLayoutEffect(()=>{
  window.clearTimeout(pending.current) // StrictMode's second setup cancels its trial cleanup.
  const dialog=ref.current;if(!dialog)return
  const returnScope=origin.scope??dialog.closest<HTMLElement>('.ew-app')
  const overflow=document.body.style.overflow
  if(options.lockScroll)document.body.style.overflow="hidden"
  dialog.showModal()
  if(options.initialFocusSelector)dialog.querySelector<HTMLElement>(options.initialFocusSelector)?.focus({preventScroll:true})
  return()=>{
   const before=document.activeElement
   const owned=before===document.body||before===document.documentElement||dialog.contains(before)
   // Keep the node itself: React will clear ref.current when deleting the host node.
   dialog.close()
   if(options.lockScroll)document.body.style.overflow=overflow
   if(!owned){
    // Native close must not displace focus that already moved outside this modal.
    if(before instanceof HTMLElement&&available(before)&&document.activeElement!==before)before.focus({preventScroll:true})
    return
   }
   const after=document.activeElement
   pending.current=window.setTimeout(()=>{
    const current=document.activeElement
    // DOM removal may turn the modal's focused child into BODY. A different
    // connected control (including a newly opened modal) owns its own focus.
    if(current!==after&&!(after instanceof HTMLElement&&!after.isConnected&&current===document.body))return
    const scope=returnScope?.isConnected?returnScope:null
    const fallback=scope?Array.from(scope.querySelectorAll<HTMLElement>('.ew-back,.ew-nav a,.ew-main button,.ew-main a[href]')):[]
    for(const target of [origin.opener,...fallback]){
     if(!available(target))continue
     const beforeFocus=document.activeElement
     target.focus({preventScroll:true})
     // A refused focus tries the next candidate; a focus handler that chose
     // another control owns that choice and must not be overridden.
     if(document.activeElement===target||document.activeElement!==beforeFocus)return
    }
   },0)
  }
 },[])
}
