<script setup lang="ts">
import { computed } from 'vue'
import MetricSummaryCards from '@/components/MetricSummaryCards.vue'
import type {MicroExpressionResult} from '@/types'
import {formatDateTime} from '@/utils/format'
const props=defineProps<{result:MicroExpressionResult}>()
const tagName=(value:string|null|undefined)=>({negative:'负向',positive:'正向',surprise:'惊讶'}[value??'']??value??'暂无数据')
const cards=computed(()=>[
 {label:'主导标签',value:tagName(props.result.dominant_tag),emphasis:true},
 {label:'预测类别',value:tagName(props.result.predicted_class)},
 {label:'分析时间',value:formatDateTime(props.result.created_at)},
])
</script>
<template>
 <section class="face-analysis-result" role="region" :aria-label="$t('分析结果')" aria-live="polite">
  <h2>{{ $t('分析结果') }}</h2>
  <MetricSummaryCards :cards="cards"/>
  <dl v-if="result.tag_distribution?.length" class="face-scores">
   <div v-for="tag in result.tag_distribution" :key="tag.name">
    <dt>{{ $t(tagName(tag.name)) }}</dt><dd>{{ (tag.score*100).toFixed(1) }}%</dd>
   </div>
  </dl>
  <p class="result-meaning">{{ $t('标签占比表示面部运动 / 表情表现维度，不代表疾病严重程度，也不用于调整训练难度。') }}</p>
 </section>
</template>
<style scoped>
.face-analysis-result{font-size:18px;line-height:1.6;text-align:left}
h2{font-size:24px;line-height:1.4;margin:0 0 20px}
.face-scores{margin:20px 0;display:grid;gap:12px}
.face-scores>div{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:12px 16px;border-radius:10px;background:var(--pd-surface)}
dt{font-size:18px}dd{font-size:24px;font-weight:600;margin:0}
.result-meaning{font-size:16px;color:var(--pd-text-secondary);margin:16px 0 0}
</style>
