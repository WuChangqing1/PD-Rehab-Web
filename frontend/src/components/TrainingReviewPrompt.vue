<script setup lang="ts">
import {ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {t} from '@/i18n'
import {useRouter} from 'vue-router'
import {useAuthStore} from '@/stores/auth'
import {reviewOffer,prepareReview,takeReview,clearTrainingReviews} from '@/training/review'
import {DISCOMFORT_NOTE_LIMIT,hasTrainingFeedback,saveTrainingFeedback,trainingFeedbackKey,type TrainingDiscomfort,type TrainingEffort} from '@/training/trainingFeedback'
const router=useRouter(),auth=useAuthStore()
const asking=ref(false)
const effort=ref<TrainingEffort|''>('')
const discomfort=ref<TrainingDiscomfort|''>('')
const discomfortNote=ref('')
watch(()=>auth.user?.id,()=>clearTrainingReviews())
// A new session always starts blank; answers are never carried across rounds.
watch(()=>reviewOffer.value?trainingFeedbackKey(reviewOffer.value):null,()=>{effort.value='';discomfort.value='';discomfortNote.value=''})
function remember(){
 const row=reviewOffer.value
 if(!row)return
 // Best effort only: a skipped form or an unavailable localStorage must never block the dialog.
 const answers={effort:effort.value||null,discomfort:discomfort.value||null,discomfortNote:discomfortNote.value}
 if(hasTrainingFeedback(answers)&&!saveTrainingFeedback(row,answers,new Date(),auth.user?.id??''))ElMessage.warning(t('本次感受未能保存到本机，训练成绩不受影响。'))
}
function dismiss(){remember();reviewOffer.value=null}
async function ask(){
 if(asking.value||!reviewOffer.value)return
 remember()
 asking.value=true;const row=reviewOffer.value;prepareReview()
 try{const failure=await router.push({name:'expert'});if(failure){takeReview();reviewOffer.value=row}}
 catch{takeReview();reviewOffer.value=row}
 finally{asking.value=false}
}
</script>
<template>
 <el-dialog :model-value="!!reviewOffer" :title="$t('本次训练已完成')" width="min(460px, calc(100vw - 32px))" :close-on-click-modal="false" @update:model-value="(value:boolean)=>{if(!value)dismiss()}">
  <p class="review-question">{{ $t('是否询问 AI 本次训练表现？') }}</p>
  <p class="review-scope">{{ $t('点击后将发送本次训练项目、手别、速度或难度、完成情况及已有指标，不包含姓名、电话、病历或录像。') }}</p>
  <div class="review-feedback">
   <p class="review-hint">{{ $t('感受仅保存在当前浏览器的当前账号，不跨设备同步。') }}</p>
   <p class="review-hint">{{ $t('以下为选填，可跳过，不影响成绩保存与 AI 点评。') }}</p>
   <div class="review-field">
    <span class="review-label">{{ $t('训练后感觉') }}</span>
    <el-radio-group v-model="effort" :aria-label="$t('训练后感觉')">
     <el-radio value="EASY">{{ $t('轻松') }}</el-radio>
     <el-radio value="MODERATE">{{ $t('适中') }}</el-radio>
     <el-radio value="FATIGUE">{{ $t('疲劳') }}</el-radio>
     <el-radio value="">{{ $t('未记录') }}</el-radio>
    </el-radio-group>
   </div>
   <div class="review-field">
    <span class="review-label">{{ $t('是否有不适') }}</span>
    <el-radio-group v-model="discomfort" :aria-label="$t('是否有不适')">
     <el-radio value="NONE">{{ $t('无') }}</el-radio>
     <el-radio value="PRESENT">{{ $t('有') }}</el-radio>
     <el-radio value="">{{ $t('未记录') }}</el-radio>
    </el-radio-group>
   </div>
   <el-input v-if="discomfort==='PRESENT'" v-model="discomfortNote" :maxlength="DISCOMFORT_NOTE_LIMIT" show-word-limit :placeholder="$t('不适备注（选填，最多 50 字）')" />
  </div>
  <template #footer><el-button @click="dismiss">{{ $t('暂不询问') }}</el-button><el-button type="primary" :loading="asking" :disabled="asking" @click="ask">{{ $t('询问 AI') }}</el-button></template>
 </el-dialog>
</template>
<style scoped>
.review-question{font-size:20px;line-height:1.6;margin:0 0 12px}.review-scope{font-size:16px;line-height:1.7;color:var(--pd-text-secondary)}
.review-feedback{margin-top:16px;padding-top:12px;border-top:1px solid var(--el-border-color-lighter)}
.review-hint{font-size:13px;line-height:1.6;margin:0 0 10px;color:var(--pd-text-secondary)}
.review-field{display:flex;flex-direction:column;gap:6px;margin-bottom:12px}
.review-label{font-size:14px;color:var(--pd-text-secondary)}
.review-field :deep(.el-radio-group){flex-wrap:wrap;row-gap:6px}
</style>
