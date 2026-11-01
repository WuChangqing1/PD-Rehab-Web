<script setup lang="ts">
import {computed,nextTick,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {assessmentApi} from '@/api'
import {notifyError} from '@/api/client'

import MicroFlowKeyframes from '@/components/MicroFlowKeyframes.vue'
import {newSelection,resetSelection,beginSelection,finishSelection,chooseCandidate,confirmSelection,editManual,selectionReady,selectionMetadata,type SelectionMetadata} from '@/emotion/selection'
import type {VideoFrameInfo} from '@/emotion/keyframes'

const props=defineProps<{blob:Blob|null;filename:string;disabled?:boolean}>()
const emit=defineEmits<{change:[value:{onset:number;apex:number|null;offset:number|null;info:VideoFrameInfo|null;ready:boolean;busy:boolean;metadata?:SelectionMetadata}]}>()
const state=reactive(newSelection())
const url=ref('')
const preview=ref<HTMLVideoElement|null>(null)
const thumbnails=ref<string[]>([])
const thumbnailError=ref(false)
const manual=ref(false)
const error=ref(false)
const manualOnset=ref(1),manualApex=ref<number|null>(null),manualOffset=ref<number|null>(null)
let controller:AbortController|null=null
let thumbnailController:AbortController|null=null
let alive=true
const candidate=computed(()=>state.response?.candidates.find(c=>c.id===state.candidateId))
const busy=computed(()=>state.status==='loading')
const reason=computed(()=>({
 NO_CLEAR_MOVEMENT:'未找到清晰的完整面部变化，请重新录制或由医生手动选择。',
 INCOMPLETE_EXPRESSION:'表情变化缺少平稳的开始或结束，请完整录制后重试。',
 HEAD_MOTION:'头部变化较大，请保持正对镜头后重新录制。',
 FACE_NOT_VISIBLE:'请保持单人面部完整入镜后重新录制。',
}[state.response?.reason??'']??'未找到可确认的片段，请重新录制或使用手动选帧。'))

function publish(){
 emit('change',{onset:state.onset,apex:state.apex,offset:state.offset,info:state.info,
  ready:selectionReady(state),busy:busy.value,metadata:selectionMetadata(state)})
}
function file(){return new File([props.blob!],props.filename||'recording.webm',{type:props.blob!.type})}
async function find(){
 if(!props.blob||props.disabled)return
 controller?.abort();controller=new AbortController()
 manual.value=false;error.value=false
 const ticket=beginSelection(state);publish()
 try{
  const response=await assessmentApi.spotFaceKeyframes(file(),controller.signal)
  if(alive&&finishSelection(state,ticket,response))publish()
 }catch(err){
  if(!alive||ticket!==state.request)return
  state.status='error';error.value=true;notifyError(err,'片段查找失败，请重试或使用手动选帧。')
 }finally{if(alive&&ticket===state.request)publish()}
}
function choose(id:string){chooseCandidate(state,id);publish()}
function confirm(){confirmSelection(state,thumbnails.value.length===3);publish()}
async function enableManual(){
 controller?.abort()
 state.request++;state.status='ready';manual.value=true
 manualOnset.value=state.onset;manualApex.value=state.apex;manualOffset.value=state.offset
 editManual(state,manualOnset.value,manualApex.value,manualOffset.value);publish()
 if(state.info||!props.blob)return
 controller=new AbortController()
 const ticket=state.request;state.status='loading';publish()
 try{
  const info=await assessmentApi.inspectFaceVideo(file(),controller.signal)
  if(alive&&ticket===state.request){state.info=info;state.status='ready'}
 }catch(err){
  if(alive&&ticket===state.request){state.status='error';notifyError(err,'无法读取视频。')}
 }finally{if(alive&&ticket===state.request)publish()}
}
watch([manualOnset,manualApex,manualOffset],()=>{
 if(manual.value){editManual(state,manualOnset.value,manualApex.value,manualOffset.value);publish()}
})
watch(()=>props.blob,async blob=>{
 controller?.abort();thumbnailController?.abort()
 resetSelection(state);manual.value=false;error.value=false;thumbnails.value=[]
 if(url.value)URL.revokeObjectURL(url.value)
 url.value=blob?URL.createObjectURL(blob):''
 publish()
 if(blob){await nextTick();if(alive&&props.blob===blob)void find()}
},{immediate:true})

function seek(video:HTMLVideoElement,time:number,signal:AbortSignal):Promise<void>{
 return new Promise((resolve,reject)=>{
  let timer=0
  function done(){cleanup();resolve()}
  function fail(){cleanup();reject(new Error('Preview unavailable'))}
  function cleanup(){window.clearTimeout(timer);video.removeEventListener('seeked',done);video.removeEventListener('error',fail);signal.removeEventListener('abort',fail)}
  if(signal.aborted){fail();return}
  video.addEventListener('seeked',done,{once:true});video.addEventListener('error',fail,{once:true})
  signal.addEventListener('abort',fail,{once:true});timer=window.setTimeout(fail,6000)
  video.currentTime=time+.00001
  if(Math.abs(video.currentTime-time)<.002&&!video.seeking&&video.readyState>=2)done()
 })
}
async function makeThumbnails(){
 thumbnailController?.abort();thumbnailController=new AbortController()
 const signal=thumbnailController.signal
 thumbnails.value=[];thumbnailError.value=false
 await nextTick()
 const chosen=candidate.value,video=preview.value
 if(!chosen||!video)return
 if(video.error){thumbnailError.value=true;return}
 if(video.readyState<1)return
 try{
  video.pause()
  const images:string[]=[]
  for(const time of [chosen.onset_time,chosen.apex_time,chosen.offset_time]){
   await seek(video,time,signal)
   if(signal.aborted)return
   const canvas=document.createElement('canvas')
   canvas.width=224;canvas.height=168
   const context=canvas.getContext('2d')!
   context.fillStyle='#14202a';context.fillRect(0,0,224,168)
   const scale=Math.min(224/video.videoWidth,168/video.videoHeight)
   const width=video.videoWidth*scale,height=video.videoHeight*scale
   context.drawImage(video,(224-width)/2,(168-height)/2,width,height)
   images.push(canvas.toDataURL('image/jpeg',.82))
  }
  if(!signal.aborted&&alive)thumbnails.value=images
 }catch{if(!signal.aborted&&alive)thumbnailError.value=true}
}
watch(()=>candidate.value,()=>void makeThumbnails())
onBeforeUnmount(()=>{
 alive=false;state.request++;controller?.abort();thumbnailController?.abort()
 if(url.value)URL.revokeObjectURL(url.value)
})
</script>

<template>
 <section class="face-selection" :aria-label="$t('片段选择')" :aria-busy="busy">
  <div v-if="!blob" class="selection-empty">{{ $t('录制结束后，将自动查找可分析的片段。') }}</div>
  <template v-else>
   <video ref="preview" :src="url" controls playsinline preload="metadata" class="clip-preview" :aria-label="$t('表情片段预览')" @loadedmetadata="makeThumbnails" @error="thumbnailError=true"/>
   <div v-if="busy" role="status" class="selection-status">{{ $t('正在查找面部变化，请稍候…') }}</div>
   <el-alert v-if="error" type="warning" :closable="false" :title="$t('片段查找失败，请重试或使用手动选帧。')"/>
   <template v-if="!manual&&!busy&&state.response">
    <el-alert v-if="!state.response.candidates.length" type="warning" :closable="false" :title="$t(reason)"/>
    <template v-else>
     <p class="review-title">{{ $t('确认分析片段') }}</p>
     <div v-if="state.response.candidates.length>1" class="candidate-options" role="group" :aria-label="$t('候选片段')">
      <el-button v-for="(item,index) in state.response.candidates" :key="item.id" :type="state.candidateId===item.id?'primary':'default'" :disabled="disabled" @click="choose(item.id)">
       {{ $t('片段') }} {{ index+1 }} · {{ item.onset_time.toFixed(1) }}–{{ item.offset_time.toFixed(1) }} s
      </el-button>
     </div>
     <p v-if="!candidate">{{ $t('检测到多段变化，请选择本次要分析的片段。') }}</p>
     <template v-if="candidate">
      <div class="candidate-frames">
       <figure v-for="(label,index) in ['开始','变化最明显','结束']" :key="label">
        <img v-if="thumbnails[index]" :src="thumbnails[index]" :alt="$t(label)"/>
        <div v-else class="thumbnail-placeholder">{{ $t('正在读取画面…') }}</div>
        <figcaption>{{ $t(label) }}</figcaption>
       </figure>
      </div>
      <p v-if="thumbnailError" role="alert">{{ $t('画面预览失败，请重新查找片段或使用手动选帧。') }}</p>
      <el-button v-if="!state.confirmed" class="confirm-selection" type="primary" :disabled="disabled||thumbnails.length!==3" @click="confirm">{{ $t('确认使用此片段') }}</el-button>
      <el-tag v-else type="success" size="large">{{ $t('片段已确认') }}</el-tag>
     </template>
    </template>
   </template>
   <MicroFlowKeyframes v-if="manual" v-model:onset="manualOnset" v-model:apex="manualApex" v-model:offset="manualOffset" :require-offset="true" :info="state.info" :blob="blob" :disabled="disabled||busy"/>
   <div class="selection-actions">
    <el-button :disabled="disabled||busy" @click="find">{{ $t('重新查找片段') }}</el-button>
    <el-button v-if="!manual" text :disabled="disabled||busy" @click="enableManual">{{ $t('手动选帧（医生）') }}</el-button>
   </div>
  </template>
 </section>
</template>

<style scoped>
.face-selection{margin:16px 0;padding:16px;border:1px solid #dce5df;border-radius:12px;min-width:0;background:#fbfdfb}
.selection-empty,.selection-status{padding:16px 0;color:#526653;line-height:1.6}
.clip-preview{display:block;width:100%;max-height:240px;border-radius:8px;background:#14202a}
.review-title{font-weight:600;color:#263c30;margin:18px 0 12px}
.candidate-frames{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}
.candidate-frames figure{margin:0;min-width:0}
.candidate-frames img,.thumbnail-placeholder{display:block;width:100%;aspect-ratio:4/3;object-fit:contain;border-radius:8px;background:#eaf0eb}
.thumbnail-placeholder{display:grid;place-content:center;font-size:12px;color:#536b59}
.candidate-frames figcaption{text-align:center;padding-top:8px;font-size:14px;color:#314c3b}
.candidate-options,.selection-actions{display:flex;flex-wrap:wrap;gap:8px}
.candidate-options .el-button,.selection-actions .el-button{margin-left:0;min-height:44px}
.selection-actions{margin-top:16px;border-top:1px solid #e0e8e2;padding-top:12px}
.confirm-selection{min-height:44px;width:100%;margin-bottom:8px}
@media(max-width:767px){.face-selection{padding:12px}.candidate-frames{gap:6px}.candidate-frames figcaption{font-size:12px}.selection-actions .el-button{flex:1 1 auto}}
</style>
