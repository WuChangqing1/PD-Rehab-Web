import test from 'node:test'
import assert from 'node:assert/strict'
import {openSpeechChannel} from '../src/voice/channel.ts'
class Socket {
 readyState=0;bufferedAmount=0;sent:unknown[]=[];onopen:any;onmessage:any;onclose:any;onerror:any
 send(data:unknown){this.sent.push(data)}
 open(){this.readyState=1;this.onopen?.()}
 event(data:unknown){this.onmessage?.({data:JSON.stringify(data)})}
 close(){this.readyState=3;this.onclose?.()}
}
async function ready(){
 const socket=new Socket(),abort=new AbortController();let errors=0
 const promise=openSpeechChannel(socket as unknown as WebSocket,'one-time-ticket',()=>{},()=>errors++,abort.signal)
 socket.open();socket.event({type:'ready'});return{socket,abort,channel:await promise,errors:()=>errors}
}
test('done keeps input busy until server closes and releases its connection slot',async()=>{
 const {socket,channel,errors}=await ready();let finished=false
 const done=channel.finish().then(()=>{finished=true})
 socket.event({type:'done'});await new Promise(r=>setTimeout(r,0))
 assert.equal(finished,false,'receiving final text must not enable another session before socket cleanup')
 socket.close();await done;assert.equal(errors(),0)
 assert.equal(socket.sent.some(x=>typeof x==='string'&&JSON.parse(x).type==='cancel'),false)
})
test('socket failure before done rejects finalization and reports one failure',async()=>{
 const {socket,channel,errors}=await ready();const result=assert.rejects(channel.finish())
 socket.close();await result;assert.equal(errors(),1)
})
test('explicit cancellation rejects pending finish without reporting a network error',async()=>{
 const {abort,channel,errors}=await ready();const result=assert.rejects(channel.finish())
 abort.abort();await result;assert.equal(errors(),0)
})
