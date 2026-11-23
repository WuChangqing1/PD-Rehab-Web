import {API_BASE,http} from '@/api/client'
import type {Capture,Channel} from './session'

export async function microphone(signal:AbortSignal):Promise<Capture>{
 const context=new AudioContext({sampleRate:16000})
 let stream:MediaStream|null=null,node:AudioWorkletNode|null=null,source:MediaStreamAudioSourceNode|null=null,gain:GainNode|null=null,closed=false
 const close=()=>{if(closed)return;closed=true;stream?.getTracks().forEach(t=>t.stop());node?.disconnect();source?.disconnect();gain?.disconnect();void context.close().catch(()=>{});signal.removeEventListener('abort',close)}
 signal.addEventListener('abort',close,{once:true})
 try{
  if(signal.aborted)throw Error('cancelled')
  await context.resume()
  stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false})
  if(closed||signal.aborted){stream.getTracks().forEach(t=>t.stop());throw Error('cancelled')}
  await context.audioWorklet.addModule(`${import.meta.env.BASE_URL}audio/asr-capture.js`)
  if(closed||signal.aborted)throw Error('cancelled')
  source=context.createMediaStreamSource(stream);gain=context.createGain();gain.gain.value=0
  node=new AudioWorkletNode(context,'asr-capture')
  let send:(b:ArrayBuffer)=>void=()=>{},ack:()=>void=()=>{},limit:()=>void=()=>{}
  node.port.onmessage=e=>{if(e.data==='flushed')ack();else if(e.data==='limit')limit();else if(e.data instanceof ArrayBuffer)send(e.data)}
  return {
   start(callback,onLimit){if(closed)throw Error('closed');send=callback;limit=onLimit;source!.connect(node!);node!.connect(gain!);gain!.connect(context.destination)},
   async flush(){
    stream?.getTracks().forEach(t=>t.stop())
    await new Promise<void>((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('flush timeout')),1500);ack=()=>{clearTimeout(timeout);resolve()};node!.port.postMessage('flush')})
   },close
  }
 }catch(e){close();throw e}
}

export async function channel(onText:(text:string)=>void,onFailure:()=>void,signal:AbortSignal):Promise<Channel>{
 const {data}=await http.post<{ticket:string}>('/asr/tickets',{}, {signal})
 if(signal.aborted)throw Error('cancelled')
 const url=new URL(`${API_BASE}/asr/stream`,location.href);url.protocol=location.protocol==='https:'?'wss:':'ws:'
 const socket=new WebSocket(url)
 return await new Promise((resolve,reject)=>{
  let ready=false,closed=false,stopping=false,doneTimer:ReturnType<typeof setTimeout>|null=null
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
  socket.onopen=()=>{if(!closed)socket.send(JSON.stringify({type:'auth',ticket:data.ticket}))}
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
    else if(event.type==='done'&&stopping){finishResolve();close()}
    else if(event.type==='error')fail()
   }catch{fail()}
  }
  socket.onerror=fail;socket.onclose=()=>{if(!closed)fail()}
 })
}
