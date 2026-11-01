import test from 'node:test'
import assert from 'node:assert/strict'
import {comprehensiveSteps} from '../src/utils/assessmentSteps.ts'
test('left and right readiness become one finger-tapping entry',()=>{
 const items=[{key:'micro_expression',label:'面部分析',state:'COMPLETED'},{key:'finger_tapping_left',label:'左手',state:'COMPLETED'},{key:'finger_tapping_right',label:'右手',state:'PENDING'}]
 const rows=comprehensiveSteps(items)
 assert.deepEqual(rows,[items[0],{key:'finger_tapping',label:'手指敲击',state:'PENDING'}])
 assert.equal(items.length,3)
})
test('the combined entry completes only when both hands are saved',()=>{
 const hand=(key:string,state:string)=>({key,label:key,state})
 assert.equal(comprehensiveSteps([hand('finger_tapping_left','COMPLETED'),hand('finger_tapping_right','COMPLETED')])[0]?.state,'COMPLETED')
 assert.equal(comprehensiveSteps([hand('finger_tapping_left','COMPLETED')])[0]?.state,'PENDING')
})
