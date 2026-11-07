<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { http, toApiError } from '@/api/client'

const question = ref('')
const waiting = ref(false)
const error = ref('')
const list = ref<Array<{question:string; answer:string;sources?:Array<{title:string;url:string}>}>>([])
const scrollEnd = ref<HTMLElement|null>(null)
function onQuestionKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229 ||
      event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return
  event.preventDefault()
  if (!event.repeat) void send()
}
async function send() {
  const q = question.value.trim()
  if (!q || waiting.value) return
  waiting.value = true; error.value = ''
  try {
    // Patient records are NOT sent to an external LLM by default.
    const {data} = await http.post<{answer: string;sources:Array<{title:string;url:string}>}>('/integration/v1/expert/chat', {question:q})
    list.value.push({question:q,answer:data.answer,sources:data.sources})
    if (question.value.trim() === q) question.value = ''
    await nextTick()
    scrollEnd.value?.scrollIntoView({behavior:'smooth',block:'end'})
  } catch (e) { error.value = toApiError(e).message }
  finally { waiting.value = false }
}
</script>
<template>
 <div class="pd-page expert-page">
   <div class="pd-page-header"><h1 class="pd-page-title">AI 康复问答</h1></div>
   <section class="pd-card expert-card">
    <p class="expert-intro">可以询问平台操作、钢琴与舞蹈康复知识。问答不读取个人病历，也不代替医生进行诊断或处方。</p>
    <div class="expert-messages" role="log" aria-live="polite">
      <div v-if="!list.length" class="pd-empty">请输入您想了解的问题</div>
      <template v-for="(turn,i) in list" :key="i">
        <div class="expert-user">{{ turn.question }}</div>
        <div class="expert-answer">{{ turn.answer }}<div v-if="turn.sources?.length" class="expert-sources"><a v-for="source in turn.sources" :key="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }}</a></div></div>
      </template>
      <div ref="scrollEnd"/>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false"/>
    <form class="expert-form" @submit.prevent="send">
      <el-input v-model="question" type="textarea" :rows="2" maxlength="3000" show-word-limit placeholder="例如：如何进行双手同时敲击？（Enter 发送，Shift+Enter 换行）" @keydown="onQuestionKeydown" />
      <el-button type="primary" native-type="submit" :disabled="waiting || !question.trim()" :loading="waiting">发送</el-button>
    </form>
   </section>
 </div>
</template>
<style scoped>
.expert-page{max-width:1100px;margin:auto}
.expert-card{padding:24px}
.expert-intro{color:var(--pd-text-secondary);font-size:14px;line-height:1.6}
.expert-messages{display:flex;flex-direction:column;gap:14px;min-height:300px;max-height:52vh;overflow-y:auto;padding:20px 0}
.expert-user{align-self:flex-end;max-width:80%;padding:12px 18px;background:#e9f0fc;border-radius:16px 16px 4px 16px;white-space:pre-wrap}
.expert-answer{align-self:flex-start;max-width:86%;padding:14px 18px;background:#f6f8fa;border-radius:16px 16px 16px 4px;white-space:pre-wrap;line-height:1.7}
.expert-sources{display:flex;flex-direction:column;gap:8px;margin-top:12px;font-size:14px}.expert-form{display:flex;align-items:flex-end;gap:14px}
.expert-form :deep(.el-textarea){flex:1}
@media(max-width:600px){.expert-card{padding:14px}.expert-form{flex-direction:column;align-items:stretch}}
</style>
