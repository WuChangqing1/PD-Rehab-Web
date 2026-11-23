<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,shallowRef,ref} from 'vue'
import {Microphone} from '@element-plus/icons-vue'
import {SpeechSession,type SpeechState} from '@/voice/session'
import {microphone,channel} from '@/voice/streaming'
import {http} from '@/api/client'
const props=defineProps<{modelValue:string;disabled?:boolean}>()
const emit=defineEmits<{'update:modelValue':[string];busy:[boolean]}>()
const state=shallowRef<SpeechState>({phase:'idle',text:'',error:''})
const available=ref(false),loading=ref(true)
const supported=!!navigator.mediaDevices?.getUserMedia&&typeof AudioWorkletNode!=='undefined'
const session=new SpeechSession({capture:microphone,channel},value=>{
 state.value=value;emit('update:modelValue',value.text);emit('busy',session.busy)
})
const busy=computed(()=>['connecting','listening','finishing'].includes(state.value.phase))
const request=new AbortController()
onMounted(async()=>{try{const {data}=await http.get('/asr/capabilities',{signal:request.signal});available.value=data.available===true}catch{}finally{loading.value=false}})
const hidden=()=>{if(document.hidden)session.cancel()}
document.addEventListener('visibilitychange',hidden)
onBeforeUnmount(()=>{request.abort();session.cancel();document.removeEventListener('visibilitychange',hidden)})
</script>
<template>
 <div class="voice-input">
  <el-button :icon="Microphone" :disabled="disabled || !supported || !available || loading || ['connecting','finishing'].includes(state.phase)" :aria-pressed="state.phase==='listening'" @click="state.phase==='listening'?session.stop():session.start(modelValue)">{{ $t(state.phase==='listening'?'停止语音输入':state.phase==='connecting'?'正在连接麦克风…':state.phase==='finishing'?'正在确认文字…':'语音输入') }}</el-button>
  <el-button v-if="busy" @click="session.cancel()">{{ $t('取消本次输入') }}</el-button>
  <p v-if="!supported" role="status">{{ $t('此浏览器不支持实时语音输入，请使用文字输入。') }}</p>
  <p v-else-if="!loading&&!available" role="status">{{ $t('语音输入暂未开通，请继续使用文字输入。') }}</p>
  <p v-else-if="state.phase==='listening'" role="status">{{ $t('正在识别，最长60秒；停止后可修改文字。') }}</p>
  <p v-else-if="available" class="voice-privacy">{{ $t('点击后语音将发送至阿里百炼转文字，本平台不保存录音。') }}</p>
  <p v-if="state.error" role="alert">{{ $t(state.error) }}</p>
 </div>
</template>
<style scoped>
.voice-input{margin-top:12px}.voice-input p{font-size:15px;line-height:1.6;margin:8px 0;color:var(--pd-text-secondary)}.voice-input :deep(.el-button){min-height:44px}
</style>
