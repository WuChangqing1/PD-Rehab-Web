/** Cancellation wins over a late dialog response, including route exit. */
export function confirmCalibration(signal:AbortSignal,ask:()=>Promise<unknown>,close:()=>void):Promise<boolean>{
  if(signal.aborted)return Promise.resolve(false)
  return new Promise(resolve=>{
    let settled=false
    const done=(accepted:boolean)=>{
      if(settled)return
      settled=true;signal.removeEventListener('abort',abort)
      resolve(accepted&&!signal.aborted)
    }
    const abort=()=>{done(false);close()}
    signal.addEventListener('abort',abort,{once:true})
    Promise.resolve().then(()=>signal.aborted?false:ask()).then(()=>done(true),()=>done(false))
  })
}
