<script setup lang="ts">
import { useId,ref,watch,onBeforeUnmount } from 'vue'
import {previewTime,type VideoFrameInfo} from '@/emotion/keyframes'
const onset = defineModel<number>('onset', {required:true})
const apex = defineModel<number | null>('apex', {required:true})
const offset = defineModel<number|null>('offset',{default:null})
const props=defineProps<{disabled?:boolean;requireOffset?:boolean;blob?:Blob|null;info?:VideoFrameInfo|null;inspecting?:boolean}>()
const id = useId()
const previewUrl=ref('')
const video=ref<HTMLVideoElement|null>(null)
const selected=ref(1)
watch(()=>props.blob,(blob)=>{
 if(previewUrl.value)URL.revokeObjectURL(previewUrl.value)
 previewUrl.value=blob?URL.createObjectURL(blob):''
 selected.value=1
},{immediate:true})
onBeforeUnmount(()=>{if(previewUrl.value)URL.revokeObjectURL(previewUrl.value)})
function seek(){if(video.value&&props.info)video.value.currentTime=previewTime(props.info,selected.value)+.00001}
</script>
<template>
 <fieldset class="microflow-keyframes" :disabled="disabled">
  <legend>{{ $t("视频关键帧") }}</legend>
  <div v-if="previewUrl" class="keyframe-preview">
   <video ref="video" :src="previewUrl" controls playsinline preload="auto" :aria-label="$t('表情片段预览')"/>
   <p v-if="inspecting" role="status">{{ $t('正在读取视频帧数…') }}</p>
   <template v-if="info">
    <p>{{ info.fps.toFixed(2) }} FPS · {{ info.frame_count }} {{ $t('帧') }}</p>
    <label :for="`${id}-preview`">{{ $t('预览帧') }} {{ selected }}
     <input :id="`${id}-preview`" v-model.number="selected" type="range" min="1" :max="info.frame_count" step="1" @input="seek"/>
    </label>
    <div class="frame-actions">
     <button type="button" @click="onset=selected">{{ $t('设为起始帧') }}</button>
     <button type="button" @click="apex=selected">{{ $t('设为峰值帧') }}</button>
     <button v-if="requireOffset" type="button" @click="offset=selected">{{ $t('设为结束帧') }}</button>
    </div>
   </template>
  </div>
  <div class="keyframe-fields">
   <label :for="`${id}-onset`">{{ $t("起始帧") }}<input :id="`${id}-onset`" v-model.number="onset" type="number" min="1" max="1799" step="1" required/></label>
   <label :for="`${id}-apex`">{{ $t("峰值帧") }}<input :id="`${id}-apex`" :value="apex??''" type="number" min="2" max="1800" step="1" required @input="apex=($event.target as HTMLInputElement).value?Number(($event.target as HTMLInputElement).value):null"/></label>
   <label v-if="requireOffset" :for="`${id}-offset`">{{ $t('结束帧') }}<input :id="`${id}-offset`" :value="offset??''" type="number" min="3" :max="info?.frame_count??1800" step="1" required @input="offset=($event.target as HTMLInputElement).value?Number(($event.target as HTMLInputElement).value):null"/></label>
  </div>
  <p>{{ $t(requireOffset?'请选择同一次表情的起始、峰值和结束帧，序号依次递增。':'帧序号从 1 开始，峰值帧须晚于起始帧。由操作者确认关键帧，模型不会自动定位峰值。') }}</p>
 </fieldset>
</template>
<style scoped>
.microflow-keyframes{border:1px solid #d8e3ec;border-radius:12px;padding:14px 16px;margin:16px 0;color:#35516c;min-width:0}.microflow-keyframes legend{font-weight:600;padding:0 6px}.keyframe-fields{display:grid;grid-template-columns:1fr 1fr;gap:14px}.keyframe-fields label{display:flex;flex-direction:column;gap:7px;font-size:14px}.keyframe-fields input{width:100%;box-sizing:border-box;padding:10px 12px;min-height:44px;border:1px solid #c5d4e2;border-radius:8px;font:inherit;color:#304d69;background:#fff}.keyframe-fields input:focus-visible{outline:3px solid #88b1dd;outline-offset:1px}.microflow-keyframes p{font-size:13px;line-height:1.7;margin:12px 0 0;color:#647b8f}.microflow-keyframes:disabled{opacity:.65}
</style>
<style scoped>
.keyframe-preview video{width:100%;max-height:260px;background:#18212b;border-radius:8px;object-fit:contain}.keyframe-preview input[type=range]{width:100%}.frame-actions{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.frame-actions button{border:1px solid #c5d4e2;border-radius:8px;background:white;color:#304d69;padding:9px 12px;min-height:44px;cursor:pointer}.frame-actions button:focus-visible{outline:3px solid #88b1dd}.keyframe-fields{grid-template-columns:repeat(auto-fit,minmax(110px,1fr))}
</style>
