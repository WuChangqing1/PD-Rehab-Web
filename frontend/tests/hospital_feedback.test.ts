import test from 'node:test'
import assert from 'node:assert/strict'
import { ReviewOffers } from '../src/training/reviewOffers.ts'
import { toggleChoice } from '../src/patients/historyChoices.ts'

test('offers only saved, uninterrupted training once and clears on account switch',()=>{
 const offers=new ReviewOffers();const row={kind:'piano' as const,id:'one'}
 assert.equal(offers.offer(row,false,false),false)
 assert.equal(offers.offer(row,true,true),false)
 assert.equal(offers.offer(row,true,false),true)
 assert.equal(offers.offer(row,true,false),false)
 assert.deepEqual(offers.take(),row)
 assert.equal(offers.take(),null)
 offers.clear();assert.equal(offers.offer(row,true,false),true)
})
test('structured history choices preserve unrelated original wording',()=>{
 assert.equal(toggleChoice('旧病史含自由描述','高血压',true),'旧病史含自由描述；高血压')
 assert.equal(toggleChoice('旧病史含自由描述；高血压','高血压',false),'旧病史含自由描述')
 assert.equal(toggleChoice('有高血压家族史','高血压',false),'有高血压家族史')
})
