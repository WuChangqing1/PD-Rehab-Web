import test from 'node:test'
import assert from 'node:assert/strict'
import {validKeyframes,previewTime} from '../src/emotion/keyframes.ts'
test('CausalNet requires an ordered triple within the decoded frame count',()=>{
 assert.equal(validKeyframes(1,15,30,true,30),true)
 for(const triple of [[1,15,null],[1,15,15],[1,15,31],[0,15,30],[1,1,30],[1,1.5,30]] as const)
  assert.equal(validKeyframes(triple[0],triple[1],triple[2],true,30),false)
})
test('existing MicroFlow still uses a pair of keyframes',()=>{
 assert.equal(validKeyframes(1,15,null,false,30),true)
 assert.equal(validKeyframes(1,31,null,false,30),false)
})
test('preview follows decoded timestamps instead of assuming 30 FPS',()=>{
 const info={fps:25,frame_count:3,duration_seconds:.12,frame_timestamps:[0,.04,.085],timestamp_basis:'decoded'}
 assert.equal(previewTime(info,3),.085)
 assert.throws(()=>previewTime(info,4),RangeError)
})
