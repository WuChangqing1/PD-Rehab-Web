type Route = {name?:unknown;query?:Record<string,unknown>;params?:Record<string,unknown>}
const names=new Set(['assessment-comprehensive','assessment-results','assessment-micro-expression','assessment-finger-tapping'])
export function assessmentSessionId(route:Route):string|null {
 if(!names.has(String(route.name)))return null
 const value=route.params?.sessionId??route.query?.sessionId
 return typeof value==='string'&&value ? value:null
}
export function shouldDiscard(from:Route,to:Route):string|null {
 const id=assessmentSessionId(from)
 return id&&id!==assessmentSessionId(to)?id:null
}
export function createExitCleanup(port:{read:()=>string[];write:(ids:string[])=>void;discard:(id:string)=>Promise<{deleted:boolean}>}){
 const running=new Map<string,Promise<{deleted:boolean}>>()
 const deleted=new Set<string>()
 function remember(id:string){port.write([...new Set([...port.read(),id])])}
 function leave(id:string):Promise<{deleted:boolean}>{
  const existing=running.get(id);if(existing)return existing
  remember(id)
  const operation=port.discard(id).then(result=>{
   if(result.deleted)deleted.add(id)
   port.write(port.read().filter(value=>value!==id))
   return result
  }).finally(()=>running.delete(id))
  running.set(id,operation)
  return operation
 }
 async function retry(){for(const id of port.read())await leave(id)}
 async function canEnter(id:string){
  const operation=running.get(id)
  if(operation)await operation
  return !deleted.has(id)
 }
 return {remember,leave,retry,canEnter}
}
