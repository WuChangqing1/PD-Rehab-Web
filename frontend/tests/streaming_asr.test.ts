import test from 'node:test'
import assert from 'node:assert/strict'
import {SpeechSession} from '../src/voice/session.ts'
// @ts-ignore browser worklet also exports its pure PCM encoder
import {PcmEncoder} from '../public/audio/asr-capture.js'

const tick=()=>new Promise(r=>setTimeout(r,0))
test('PCM resampling preserves fractional block state and little endian samples',()=>{
 for(const rate of [16000,44100,48000]){
  const chunks:ArrayBuffer[]=[];const encoder=new PcmEncoder(rate,(b:ArrayBuffer)=>chunks.push(b))
  const count=rate;for(let i=0;i<count;i+=128)encoder.push(new Float32Array(Math.min(128,count-i)).fill(.5))
  encoder.flush();const bytes=chunks.reduce((n,b)=>n+b.byteLength,0)
  assert.equal(bytes,32000);assert.equal(new DataView(chunks[0]!).getInt16(0,true),16383)
 }
})
test('cancel pending permission releases a late microphone without opening channel',async()=>{
 let resolve:any;let closed=0,opened=0
 const session=new SpeechSession({capture:()=>new Promise(r=>resolve=r),channel:async()=>{opened++;throw Error()}},()=>{})
 const start=session.start('original');session.cancel();resolve({close(){closed++}});await start
 assert.equal(closed,1);assert.equal(opened,0)
})
test('draft revisions replace the voice suffix and cancel restores original',async()=>{
 let transcript:any;let value='',closed=0
 const session=new SpeechSession({capture:async()=>({start(){},flush:async()=>{},close(){closed++}}),channel:async(cb:any)=>{transcript=cb;return {send(){},finish:async()=>{},close(){}}}},s=>value=s.text)
 await session.start('已有文字');transcript('左');transcript('左手训练')
 assert.equal(value,'已有文字左手训练');session.cancel();assert.equal(value,'已有文字');assert.equal(closed,1)
})
test('stop waits for final text; repeated start is ignored and failures release capture',async()=>{
 let calls=0,closed=0,transcript:any,value=''
 const session=new SpeechSession({capture:async()=>{calls++;return{start(){},flush:async()=>{},close(){closed++}}},channel:async(cb:any)=>{transcript=cb;return{send(){},finish:async()=>{await tick();cb('最终结果')},close(){}}}},s=>value=s.text)
 await session.start('');await session.start('');assert.equal(calls,1)
 transcript('最终');await session.stop();assert.equal(value,'最终结果');assert.equal(closed,1);assert.equal(session.busy,false)
 const bad=new SpeechSession({capture:async()=>({start(){},flush:async()=>{},close(){closed++}}),channel:async()=>{throw Error('fail')}},()=>{})
 await bad.start('');assert.equal(bad.busy,false);assert.equal(closed,2)
})

test('sample budget caps PCM exactly even when the page stop timer is delayed',()=>{
 const chunks:ArrayBuffer[]=[];let limited=0
 const encoder=new PcmEncoder(16000,(b:ArrayBuffer)=>chunks.push(b),1600,()=>limited++)
 encoder.push(new Float32Array(5000));encoder.flush();encoder.push(new Float32Array(5000));encoder.flush()
 assert.equal(chunks.reduce((n,b)=>n+b.byteLength,0),3200);assert.equal(limited,1)
})
