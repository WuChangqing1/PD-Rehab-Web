import test from 'node:test'
import assert from 'node:assert/strict'
import {newSelection,resetSelection,beginSelection,finishSelection,chooseCandidate,confirmSelection,editManual,selectionReady,selectionMetadata} from '../src/emotion/selection.ts'
const candidate={id:'one',onset_frame:2,apex_frame:5,offset_frame:9,onset_time:.1,apex_time:.4,offset_time:.8,selection_token:'signed'}
const response={algorithm_version:'face-displacement-multiscale-v1',review_required:true,status:'REVIEW_REQUIRED',reason:null,message:'review',candidates:[candidate],video_info:{fps:10,frame_count:10,duration_seconds:1,frame_timestamps:Array.from({length:10},(_,i)=>i/10),timestamp_basis:'decoded'},quality:{}}

test('single automatic candidate stays disabled until preview and operator confirmation',()=>{
 const state=newSelection();const ticket=beginSelection(state)
 assert.equal(finishSelection(state,ticket,response),true)
 assert.equal(selectionReady(state),false)
 assert.equal(confirmSelection(state,false),false)
 assert.equal(confirmSelection(state,true),true)
 assert.equal(selectionReady(state),true)
 assert.deepEqual(selectionMetadata(state),{selection_source:'AUTO_REVIEWED',selection_token:'signed',review_confirmed:true})
})
test('old clip response cannot replace current selection',()=>{
 const state=newSelection();const old=beginSelection(state)
 resetSelection(state);const current=beginSelection(state)
 assert.equal(finishSelection(state,old,response),false)
 assert.equal(finishSelection(state,current,response),true)
 assert.equal(state.candidateId,'one')
})
test('another request on the same clip supersedes the previous response',()=>{
 const state=newSelection();const old=beginSelection(state);const next=beginSelection(state)
 assert.equal(finishSelection(state,old,response),false)
 assert.equal(finishSelection(state,next,response),true)
})
test('multiple candidates require selection, and switching invalidates confirmation',()=>{
 const state=newSelection();finishSelection(state,beginSelection(state),{...response,candidates:[candidate,{...candidate,id:'two',selection_token:'signed-two'}]})
 assert.equal(state.candidateId,null)
 chooseCandidate(state,'one');confirmSelection(state,true)
 chooseCandidate(state,'two')
 assert.equal(selectionReady(state),false)
 assert.equal(selectionMetadata(state),undefined)
})
test('manual edits never retain an automatic receipt',()=>{
 const state=newSelection();finishSelection(state,beginSelection(state),response);confirmSelection(state,true)
 editManual(state,1,4,8)
 assert.equal(selectionReady(state),true)
 assert.deepEqual(selectionMetadata(state),{selection_source:'MANUAL'})
 editManual(state,1,8,4)
 assert.equal(selectionReady(state),false)
})
test('starting new selection immediately invalidates previous review',()=>{
 const state=newSelection();finishSelection(state,beginSelection(state),response);confirmSelection(state,true)
 beginSelection(state)
 assert.equal(selectionReady(state),false)
 assert.equal(selectionMetadata(state),undefined)
})
test('patient or recording reset removes all clip-associated state',()=>{
 const state=newSelection();finishSelection(state,beginSelection(state),response);confirmSelection(state,true)
 resetSelection(state)
 assert.equal(state.info,null);assert.equal(state.candidateId,null);assert.equal(selectionReady(state),false)
})
