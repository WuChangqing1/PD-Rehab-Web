import type {Channel} from './session'

/** Browser transport, independent of microphone capture and HTTP ticket creation. */
export function openSpeechChannel(socket:WebSocket,ticket:string,onText:(text:string)=>void,onFailure:()=>void,signal:AbortSignal):Promise<Channel>{
 return new Promise((resolve,reject)=>{
  let ready=false,closed=false,stopping=false,receivedDone=false,doneTimer:ReturnType<typeof setTimeout>|null=null
  let finishResolve:()=>void=()=>{},finishReject:(e:Error)=>void=()=>{}
  const timer=setTimeout(()=>fail(),15000)
  const close=()=>{
   if(closed)return;closed=true;clearTimeout(timer);if(doneTimer)clearTimeout(doneTimer)
   signal.removeEventListener('abort',cancel)
   if(socket.readyState===WebSocket.OPEN){socket.send(JSON.stringify({type:'cancel'}));socket.close()}
   else if(socket.readyState===WebSocket.CONNECTING)socket.close()
   finishReject(Error('closed'))
  }
  const fail=()=>{if(closed)return;const wasReady=ready;close();reject(Error('ASR stream failed'));if(wasReady)onFailure()}
  const cancel=()=>{close();reject(Error('cancelled'))}
  signal.addEventListener('abort',cancel,{once:true})
  if(signal.aborted){cancel();return}
  socket.onopen=()=>{if(!closed)socket.send(JSON.stringify({type:'auth',ticket}))}
  socket.onmessage=e=>{
   if(closed)return
   try{
    const event=JSON.parse(e.data)
    if(event.type==='ready'&&!ready){
     ready=true;clearTimeout(timer)
     resolve({
      send(bytes){if(closed||stopping||socket.readyState!==WebSocket.OPEN||socket.bufferedAmount>128000)throw Error('backpressure');socket.send(bytes)},
      finish(){if(stopping||closed)return Promise.reject(Error('closed'));stopping=true;return new Promise<void>((yes,no)=>{finishResolve=yes;finishReject=no;doneTimer=setTimeout(fail,12000);socket.send(JSON.stringify({type:'stop'}))})},
      close
     })
    }else if(event.type==='transcript'&&ready&&typeof event.text==='string')onText(event.text.slice(0,3000))
    else if(event.type==='done'&&stopping){receivedDone=true}
    else if(event.type==='error')fail()
   }catch{fail()}
  }
  socket.onerror=fail;socket.onclose=()=>{
   if(closed)return
   if(receivedDone&&stopping){
    // Server releases its per-user slot before closing this socket.
    closed=true;clearTimeout(timer);if(doneTimer)clearTimeout(doneTimer)
    signal.removeEventListener('abort',cancel);finishResolve()
   }else fail()
  }
 })
}
