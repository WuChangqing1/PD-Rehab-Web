import test from 'node:test'
import assert from 'node:assert/strict'
import { keyCenterX, staffY } from '../src/piano/guided-song/geometry.ts'
test('all seven marker centers align with equal-width keys at every viewport',()=>{
 for(const width of [320,390,820,1440]) for(let index=0;index<7;index++){
  assert.equal(keyCenterX(index,width),(index+.5)*width/7)
  assert.ok(staffY(index)>20 && staffY(index)<80)
 }
})
