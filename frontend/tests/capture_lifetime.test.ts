import test from 'node:test'
import assert from 'node:assert/strict'
import {newCaptureLifetime,beginCapture,invalidateCapture,disposeCapture,isCurrentCapture} from '../src/utils/captureLifetime.ts'

test('unmount invalidates a delayed recorder stop callback',()=>{
 const lifetime=newCaptureLifetime();const ticket=beginCapture(lifetime)
 let published=false
 const onstop=()=>{if(isCurrentCapture(lifetime,ticket))published=true}
 disposeCapture(lifetime);onstop()
 assert.equal(published,false)
})
test('discard or another recording cannot restore the old clip',()=>{
 const lifetime=newCaptureLifetime();const old=beginCapture(lifetime)
 invalidateCapture(lifetime);const current=beginCapture(lifetime)
 assert.equal(isCurrentCapture(lifetime,old),false)
 assert.equal(isCurrentCapture(lifetime,current),true)
})
test('normal stopped recording can publish until discarded',()=>{
 const lifetime=newCaptureLifetime();const ticket=beginCapture(lifetime)
 assert.equal(isCurrentCapture(lifetime,ticket),true)
})
