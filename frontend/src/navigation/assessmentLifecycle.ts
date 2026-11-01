import { assessmentApi } from '@/api'
import { API_BASE,TOKEN_STORAGE_KEY } from '@/api/client'
import { assessmentSessionId,shouldDiscard,createExitCleanup } from '@/utils/assessmentExit'
function controller(owner:string){
 const key='pd-assessment-exit:'+owner
 let fallback:string[]=[]
 return createExitCleanup({
  read:()=>{try{const value=JSON.parse(localStorage.getItem(key)??'[]');return Array.isArray(value)?value.filter((v:unknown):v is string=>typeof v==='string'):[]}catch{return fallback}},
  write:ids=>{fallback=ids;try{localStorage.setItem(key,JSON.stringify(ids))}catch{/* request still runs */}},
  discard:id=>assessmentApi.discardSession(id),
 })
}
let owner='',active:string|null=null,cleanup=controller('')
let heartbeatTimer:ReturnType<typeof setInterval>|null=null
let expiryHandler:()=>void=()=>{}
export function onAssessmentExpired(handler:()=>void){expiryHandler=handler}
function stopHeartbeat(){if(heartbeatTimer)clearInterval(heartbeatTimer);heartbeatTimer=null}
async function heartbeat(){
 const id=active;if(!id||!owner)return
 try{
  const result=await assessmentApi.heartbeatSession(id)
  if(active!==id)return
  if(!result.active)stopHeartbeat()
  if(result.deleted){active=null;expiryHandler()}
 }catch{/* temporary disconnection is tolerated for the server lease */}
}
export function setAssessmentOwner(id:string){const changed=owner!==id;if(changed)cleanup=controller(id);owner=id;return changed}
export async function retryAssessmentCleanup(){if(owner)await cleanup.retry()}
export async function discardAfterNavigation(from:Parameters<typeof shouldDiscard>[0],to:Parameters<typeof shouldDiscard>[1]){
 const id=shouldDiscard(from,to);if(id&&owner)await cleanup.leave(id)
}
export async function canEnterAssessment(route:Parameters<typeof assessmentSessionId>[0]){
 const id=assessmentSessionId(route);return !id||await cleanup.canEnter(id)
}
export function trackAssessment(route:Parameters<typeof assessmentSessionId>[0]){
 const next=assessmentSessionId(route)
 if(next===active)return
 stopHeartbeat();active=next
 if(active&&owner){void heartbeat();heartbeatTimer=setInterval(()=>void heartbeat(),15000)}
}
export function captureAssessmentCleanup(){const current=cleanup;return (id:string)=>current.leave(id)}
export async function discardActiveAssessment(){if(active&&owner){const id=active;active=null;await cleanup.leave(id)}}
window.addEventListener('pagehide',()=>{
 stopHeartbeat()
 const token=localStorage.getItem(TOKEN_STORAGE_KEY)
 if(!active||!owner||!token)return
 cleanup.remember(active)
 void fetch(API_BASE+'/assessment-sessions/'+encodeURIComponent(active)+'/discard',{
  method:'POST',keepalive:true,headers:{Authorization:'Bearer '+token},
 }).catch(()=>{})
})

window.addEventListener('pageshow',()=>{if(active&&owner&&!heartbeatTimer){void heartbeat();heartbeatTimer=setInterval(()=>void heartbeat(),15000)}})
