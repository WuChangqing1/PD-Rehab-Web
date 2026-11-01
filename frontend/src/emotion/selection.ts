import {validKeyframes,type VideoFrameInfo} from './keyframes.ts'

export interface FaceCandidate {
 id:string
 onset_frame:number
 apex_frame:number
 offset_frame:number
 onset_time:number
 apex_time:number
 offset_time:number
 selection_token:string
 duration_seconds?:number
}
export interface SpottingResponse {
 algorithm_version:string
 review_required:boolean
 status:string
 reason:string|null
 message:string
 candidates:FaceCandidate[]
 video_info:VideoFrameInfo
 quality:Record<string,unknown>
}
export interface SelectionMetadata {
 selection_source:'MANUAL'|'AUTO_REVIEWED'
 selection_token?:string
 review_confirmed?:boolean
}
export interface SelectionState {
 request:number
 status:'idle'|'loading'|'ready'|'error'
 mode:'auto'|'manual'
 info:VideoFrameInfo|null
 response:SpottingResponse|null
 candidateId:string|null
 confirmed:boolean
 onset:number
 apex:number|null
 offset:number|null
}
export function newSelection():SelectionState {
 return {request:0,status:'idle',mode:'auto',info:null,response:null,candidateId:null,confirmed:false,onset:1,apex:null,offset:null}
}
export function resetSelection(state:SelectionState) {
 const request=state.request+1
 Object.assign(state,newSelection(),{request})
}
export function beginSelection(state:SelectionState):number {
 resetSelection(state);state.status='loading'
 return state.request
}
export function finishSelection(state:SelectionState,ticket:number,response:SpottingResponse):boolean {
 if(ticket!==state.request||state.status!=='loading')return false
 state.response=response;state.info=response.video_info;state.status='ready'
 if(response.candidates.length===1)chooseCandidate(state,response.candidates[0]!.id)
 return true
}
export function chooseCandidate(state:SelectionState,id:string) {
 state.confirmed=false;state.candidateId=null;state.mode='auto'
 const candidate=state.response?.candidates.find(c=>c.id===id)
 if(!candidate)return
 state.candidateId=id;state.onset=candidate.onset_frame;state.apex=candidate.apex_frame;state.offset=candidate.offset_frame
}
function valid(state:SelectionState) {
 return state.info!==null&&validKeyframes(state.onset,state.apex,state.offset,true,state.info.frame_count)
}
export function confirmSelection(state:SelectionState,previewReady:boolean):boolean {
 const candidate=state.response?.candidates.find(c=>c.id===state.candidateId)
 if(state.status!=='ready'||state.mode!=='auto'||!previewReady||!valid(state)||!candidate?.selection_token)return false
 if(candidate.onset_frame!==state.onset||candidate.apex_frame!==state.apex||candidate.offset_frame!==state.offset)return false
 state.confirmed=true;return true
}
export function editManual(state:SelectionState,onset:number,apex:number|null,offset:number|null) {
 state.mode='manual';state.confirmed=false;state.candidateId=null
 state.onset=onset;state.apex=apex;state.offset=offset
}
export function selectionReady(state:SelectionState):boolean {
 return state.status==='ready'&&valid(state)&&(state.mode==='manual'||state.confirmed)
}
export function selectionMetadata(state:SelectionState):SelectionMetadata|undefined {
 if(!selectionReady(state))return undefined
 if(state.mode==='manual')return {selection_source:'MANUAL'}
 return {selection_source:'AUTO_REVIEWED',selection_token:state.response!.candidates.find(c=>c.id===state.candidateId)!.selection_token,review_confirmed:true}
}
