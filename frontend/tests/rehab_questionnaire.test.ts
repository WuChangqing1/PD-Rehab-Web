import {test} from 'node:test'
import assert from 'node:assert/strict'
import {composeRehabHistory,emptyRehabAnswers,parseRehabHistory,rehabSummary} from '../src/patients/rehabQuestionnaire.ts'

test('legacy free text is preserved verbatim and never gains an envelope',()=>{
 const legacy='2019年住院康复两周；在家做拉伸'
 const parsed=parseRehabHistory(legacy)
 assert.equal(parsed.text,legacy)
 assert.deepEqual(parsed.answers,emptyRehabAnswers())
 assert.equal(composeRehabHistory(legacy,emptyRehabAnswers()),legacy)
})

test('structured answers round trip without touching the free text',()=>{
 const text='奶奶记得在市医院做过训练\n后来在家练'
 const stored=composeRehabHistory(text,{contact:'YES',types:['HOME','HOSPITAL'],frequency:'WEEKLY'})
 assert.match(stored,/结构化问卷记录/)
 assert.match(stored,/\[\[PD_REHAB_V1\]\]/)
 const parsed=parseRehabHistory(stored)
 assert.equal(parsed.text,text)
 assert.deepEqual(parsed.answers,{contact:'YES',types:['HOME','HOSPITAL'],frequency:'WEEKLY'})
})

test('trailing newlines survive the envelope round trip',()=>{
 const text='旧记录\n\n'
 const parsed=parseRehabHistory(composeRehabHistory(text,{contact:'NO',types:[],frequency:null}))
 assert.equal(parsed.text,text)
})

test('unrecorded stays null instead of becoming "no"',()=>{
 const parsed=parseRehabHistory('旧文字')
 assert.equal(parsed.answers.contact,null)
 assert.equal(parsed.answers.frequency,null)
 assert.deepEqual(parsed.answers.types,[])
 const stored=composeRehabHistory('旧文字',emptyRehabAnswers())
 assert.equal(stored,'旧文字')
 assert.doesNotMatch(stored,/PD_REHAB_V1/)
})

test('partial answers are kept and missing ones stay null',()=>{
 const parsed=parseRehabHistory(composeRehabHistory('',{contact:null,types:['OTHER'],frequency:null}))
 assert.equal(parsed.text,'')
 assert.equal(parsed.answers.contact,null)
 assert.deepEqual(parsed.answers.types,['OTHER'])
 assert.equal(parsed.answers.frequency,null)
})

test('malformed or truncated envelopes fall back to plain text',()=>{
 const broken='旧文字\n\n[结构化问卷记录，请使用新版网页查看]\n[[PD_REHAB_V1]]{"v":1,"contact":"YE'
 const parsed=parseRehabHistory(broken)
 assert.equal(parsed.text,broken)
 assert.deepEqual(parsed.answers,emptyRehabAnswers())
 const unknownCode='旧文字\n\n[结构化问卷记录，请使用新版网页查看]\n[[PD_REHAB_V1]]{"v":1,"contact":"MAYBE","types":["HOSPITAL"],"frequency":"SOMETIMES"}[[/PD_REHAB_V1]]'
 const normalized=parseRehabHistory(unknownCode)
 assert.equal(normalized.answers.contact,null)
 assert.deepEqual(normalized.answers.types,['HOSPITAL'])
 assert.equal(normalized.answers.frequency,null)
})

test('markers typed into the free text never create a nested envelope',()=>{
 const stored=composeRehabHistory('用户手打的 [[PD_REHAB_V1]] 和 [[/PD_REHAB_V1]]',{contact:'YES',types:[],frequency:null})
 assert.equal(stored.match(/\[\[PD_REHAB_V1\]\]/g)?.length,1)
 assert.equal(stored.match(/\[\[\/PD_REHAB_V1\]\]/g)?.length,1)
 assert.equal(parseRehabHistory(stored).answers.contact,'YES')
})

test('detail summary renders unrecorded as empty and keeps unknown distinct',()=>{
 assert.equal(rehabSummary(emptyRehabAnswers()),null)
 assert.equal(rehabSummary({contact:null,types:[],frequency:'UNKNOWN'}),'频次：记不清')
 assert.equal(
  rehabSummary({contact:'UNKNOWN',types:['HOME','HOSPITAL'],frequency:'DAILY'}),
  '接触过康复：不清楚；训练类型：居家锻炼、医院康复训练；频次：每天',
 )
})
