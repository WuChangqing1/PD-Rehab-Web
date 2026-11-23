<script setup lang="ts">
import {watch,ref} from 'vue'
import {useRouter} from 'vue-router'
import {useAuthStore} from '@/stores/auth'
import {reviewOffer,prepareReview,takeReview,clearTrainingReviews} from '@/training/review'
const router=useRouter(),auth=useAuthStore()
const asking=ref(false)
watch(()=>auth.user?.id,()=>clearTrainingReviews())
async function ask(){
 if(asking.value||!reviewOffer.value)return
 asking.value=true;const row=reviewOffer.value;prepareReview()
 try{const failure=await router.push({name:'expert'});if(failure){takeReview();reviewOffer.value=row}}
 catch{takeReview();reviewOffer.value=row}
 finally{asking.value=false}
}
</script>
<template>
 <el-dialog :model-value="!!reviewOffer" :title="$t('本次训练已完成')" width="min(460px, calc(100vw - 32px))" :close-on-click-modal="false" @update:model-value="(value:boolean)=>{if(!value)reviewOffer=null}">
  <p class="review-question">{{ $t('是否询问 AI 本次训练表现？') }}</p>
  <p class="review-scope">{{ $t('点击后将发送本次训练项目、手别、速度或难度、完成情况及已有指标，不包含姓名、电话、病历或录像。') }}</p>
  <template #footer><el-button @click="reviewOffer=null">{{ $t('暂不询问') }}</el-button><el-button type="primary" :loading="asking" :disabled="asking" @click="ask">{{ $t('询问 AI') }}</el-button></template>
 </el-dialog>
</template>
<style scoped>
.review-question{font-size:20px;line-height:1.6;margin:0 0 12px}.review-scope{font-size:16px;line-height:1.7;color:var(--pd-text-secondary)}
</style>
