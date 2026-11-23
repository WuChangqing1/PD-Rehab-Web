<script setup lang="ts">
import {onBeforeUnmount,ref,shallowRef} from 'vue'
import {Microphone} from '@element-plus/icons-vue'
import {VoiceRecorder,type VoiceState} from '@/voice/recorder'
const state=shallowRef<VoiceState>({status:'idle',blob:null,error:''})
const preview=ref(''),elapsed=ref(0)
const supported=typeof MediaRecorder!=='undefined' && !!navigator.mediaDevices?.getUserMedia
let ticker:ReturnType<typeof setInterval>|null=null
const recorder=new VoiceRecorder({media:()=>navigator.mediaDevices.getUserMedia({audio:true,video:false}),recorder:stream=>new MediaRecorder(stream)},value=>{
 state.value=value
 if(preview.value){URL.revokeObjectURL(preview.value);preview.value=''}
 if(value.blob)preview.value=URL.createObjectURL(value.blob)
 if(value.status!=='recording'&&ticker){clearInterval(ticker);ticker=null}
 if(value.status==='recording'&&!ticker){elapsed.value=0;ticker=setInterval(()=>elapsed.value++,1000)}
})
async function start(){await recorder.start()}
onBeforeUnmount(()=>{recorder.cancel();if(ticker)clearInterval(ticker)})
</script>
<template>
 <div class="voice-input">
  <el-button :icon="Microphone" :disabled="!supported || state.status==='requesting'" :aria-pressed="state.status==='recording'" @click="state.status==='recording'?recorder.stop():start()">{{ $t(state.status==='recording'?'停止录音':state.status==='requesting'?'等待麦克风授权…':state.status==='ready'?'重新录制':'语音输入') }}</el-button>
  <el-button v-if="['requesting','recording','ready'].includes(state.status)" @click="recorder.cancel()">{{ $t('取消录音') }}</el-button>
  <p v-if="!supported" role="status">{{ $t('此浏览器无法录音，请继续使用文字输入。') }}</p>
  <p v-if="state.status==='recording'" role="status">{{ $t('正在录音') }} {{ elapsed }} / 60 {{ $t('秒') }}</p>
  <p v-if="state.error" role="alert">{{ $t(state.error) }}</p>
  <div v-if="preview" class="voice-preview"><audio :src="preview" controls :aria-label="$t('回听本次录音')"/><p>{{ $t('录音仅在本机回听，尚未接入语音转文字。请使用文字输入发送问题。') }}</p></div>
 </div>
</template>
<style scoped>
.voice-input{margin-top:12px}.voice-input p{font-size:15px;line-height:1.6;margin:8px 0;color:var(--pd-text-secondary)}.voice-preview audio{max-width:100%;margin-top:12px}.voice-input :deep(.el-button){min-height:44px}
</style>
