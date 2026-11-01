import test from 'node:test'
import assert from 'node:assert/strict'
import { readyCamera } from '../src/utils/cameraReady.ts'

test('device enumeration cannot block camera preview and recording readiness', async () => {
 const events:string[]=[]
 await readyCamera(async()=>{events.push('preview')},()=>{events.push('ready')},()=>new Promise(()=>{}))
 assert.deepEqual(events,['preview','ready'])
})
test('failed preview never reports camera ready', async () => {
 let ready=false
 await assert.rejects(readyCamera(async()=>{throw Error('play failed')},()=>{ready=true},async()=>{}))
 assert.equal(ready,false)
})
test('device enumeration rejection does not fail a working preview', async () => {
 let ready=false
 await readyCamera(async()=>{},()=>{ready=true},async()=>{throw Error('unsupported')})
 assert.equal(ready,true)
})

// Stop dispatches asynchronously; cancellation controls must stay locked until onstop.
test('saving a recording cannot expose destructive camera controls', async()=>{
 const {readFile}=await import('node:fs/promises')
 const source=await readFile(new URL('../src/components/VideoCapturePanel.vue',import.meta.url),'utf8')
 assert.match(source,/:disabled="recording \|\| stopping" @click="closeCamera"/)
 assert.match(source,/canSwitchCamera && !recording && !stopping && !opening/)
})
