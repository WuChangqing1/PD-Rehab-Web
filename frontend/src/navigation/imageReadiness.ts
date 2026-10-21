type ImageLoader=(url:string,signal:AbortSignal)=>Promise<void>

export function createImagePreloader(load:ImageLoader,timeoutMs=15000){
  const ready=new Set<string>()
  return async(urls:readonly string[],signal?:AbortSignal)=>{
    if(signal?.aborted)throw new DOMException('Navigation cancelled','AbortError')
    const missing=[...new Set(urls)].filter(url=>!ready.has(url))
    if(!missing.length)return
    const operation=new AbortController()
    let rejectStop!:(error:unknown)=>void
    const stopped=new Promise<never>((_,reject)=>rejectStop=reject)
    const abort=()=>{operation.abort();rejectStop(new DOMException('Navigation cancelled','AbortError'))}
    signal?.addEventListener('abort',abort,{once:true})
    const timer=setTimeout(()=>{operation.abort();rejectStop(new Error('图片加载超时，请重试。'))},timeoutMs)
    try{
      await Promise.race([Promise.all(missing.map(async url=>{
        await load(url,operation.signal)
        if(!operation.signal.aborted)ready.add(url)
      })),stopped])
    }finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);operation.abort()}
  }
}

export const preloadImages=createImagePreloader((url,signal)=>new Promise<void>((resolve,reject)=>{
  const image=new Image()
  const cleanup=()=>{image.onload=null;image.onerror=null;signal.removeEventListener('abort',abort)}
  const abort=()=>{cleanup();image.src='';reject(new DOMException('Navigation cancelled','AbortError'))}
  image.onload=()=>{cleanup();resolve()}
  image.onerror=()=>{cleanup();reject(new Error('图片加载失败，请检查网络后重试。'))}
  signal.addEventListener('abort',abort,{once:true})
  image.src=url
}))
