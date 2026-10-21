<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { assessmentApi, patientApi } from '@/api'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import ApertureChart from '@/components/ApertureChart.vue'
import type { AssessmentSessionDetail, FingerTappingResult, FingerTappingSessionSummary, FingerTappingTimeseries, Patient } from '@/types'
import { formatDateTime, formatNumber, SESSION_TYPE_LABELS, SESSION_STATUS_LABELS, FUNCTIONAL_TEST_LABELS } from '@/utils/format'

const route = useRoute()
const session = ref<AssessmentSessionDetail|null>(null), patient = ref<Patient|null>(null)
const summary = ref<FingerTappingSessionSummary|null>(null)
const series = ref<Partial<Record<'LEFT'|'RIGHT',FingerTappingTimeseries>>>({})
const seriesErrors = ref<Partial<Record<'LEFT'|'RIGHT',string>>>({})
const loading = ref(false), error = ref(''), analysisError = ref('')
let generation = 0
const metrics: Array<{key:keyof FingerTappingResult,label:string,unit?:string}> = [
  {key:'tapping_frequency',label:'敲击频率',unit:' Hz'}, {key:'avg_amplitude',label:'平均幅度（归一化距离）'},
  {key:'avg_speed',label:'平均速度（归一化距离/秒）'}, {key:'avg_cycle_duration',label:'平均周期',unit:' s'},
  {key:'amplitude_cv',label:'幅度变异系数'}, {key:'speed_cv',label:'速度变异系数'}, {key:'cycle_cv',label:'周期变异系数'},
  {key:'amplitude_slope',label:'幅度变化斜率'}, {key:'speed_slope',label:'速度变化斜率'}, {key:'cycle_slope',label:'周期变化斜率'},
  {key:'interruptions',label:'中断次数'}, {key:'valid_frame_ratio',label:'有效帧比例'}, {key:'avg_landmark_confidence',label:'平均手别置信度'},
]
function metric(hand:'left'|'right',key:keyof FingerTappingResult,unit='') {
  const value=summary.value?.[hand]?.[key]
  return formatNumber(typeof value==='number'?value:null,key==='interruptions'?0:3,unit)
}
function label(key:string) {return metrics.find(m=>m.key===key)?.label??key}
const json = (value:unknown) => JSON.stringify(value,null,2)
async function load() {
  const current=++generation
  loading.value=true;error.value='';analysisError.value='';session.value=null;patient.value=null;summary.value=null;series.value={};seriesErrors.value={}
  try {
    const record=await assessmentApi.getSession(String(route.params.sessionId))
    if(route.query.patientId && route.query.patientId!==record.patient_id) throw new Error('患者与评估记录不一致，无法显示结果。')
    const person=await patientApi.get(record.patient_id)
    if(current!==generation)return
    session.value=record;patient.value=person
    if(record.finger_tapping_results.length){
      try {const data=await assessmentApi.getFingerTapping(record.id);if(current!==generation)return;summary.value=data}
      catch {if(current===generation)analysisError.value='无法读取手指敲击汇总，请重试。原始已保存结果仍可在下方查看。'}
      await Promise.all((['LEFT','RIGHT'] as const).map(async hand=>{
        if(!record.finger_tapping_results.some(r=>r.hand===hand))return
        try {const data=await assessmentApi.getFingerTappingTimeseries(record.id,hand);if(current===generation)series.value[hand]=data}
        catch {if(current===generation)seriesErrors.value[hand]='本次曲线未保存或暂时无法读取。'}
      }))
    }
  } catch(e){if(current===generation)error.value=e instanceof Error?e.message:'无法读取评估结果。'}
  finally{if(current===generation)loading.value=false}
}
watch(()=>[route.params.sessionId,route.query.patientId],load,{immediate:true})
</script>

<template>
  <div class="pd-page" v-loading="loading">
    <router-link class="pd-back" :to="session?{name:'patient-detail',params:{id:session.patient_id}}:{name:'assessment'}">← {{session?'返回患者资料':'返回评估中心'}}</router-link>
    <div class="pd-page-header"><div><h1 class="pd-page-title">本次评估结果</h1></div><el-button @click="load" :disabled="loading">刷新结果</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="session && patient">
      <SelectedPatientBar :patient="patient" :allow-change="false" />
      <section class="pd-card result-section">
        <h2>{{SESSION_TYPE_LABELS[session.session_type]??session.session_type}} <el-tag>{{SESSION_STATUS_LABELS[session.status]}}</el-tag></h2>
        <p>开始时间：{{formatDateTime(session.started_at)}} · 完成时间：{{formatDateTime(session.completed_at)}}</p>
        <p v-if="session.notes" class="saved-notes">评估备注：{{session.notes}}</p>
        <el-alert v-if="session.status!=='COMPLETED'" title="本次评估尚未完成，以下仅显示已经保存的结果。" type="info" :closable="false" />
      </section>
      <section class="pd-card result-section">
        <h2>手指敲击分析</h2>
        <el-alert v-if="analysisError" :title="analysisError" type="warning" :closable="false" />
        <div v-if="!session.finger_tapping_results.length" class="pd-empty">本次未保存手指敲击结果。</div>
        <template v-else>

          <el-table :data="metrics" size="small"><el-table-column prop="label" label="指标" min-width="220"/><el-table-column label="左手" min-width="130"><template #default="{row}">{{metric('left',row.key,row.unit)}}</template></el-table-column><el-table-column label="右手" min-width="130"><template #default="{row}">{{metric('right',row.key,row.unit)}}</template></el-table-column></el-table>
          <div class="result-charts"><div v-for="hand in (['LEFT','RIGHT'] as const)" :key="hand"><h3>{{hand==='LEFT'?'左手':'右手'}}开合时间序列</h3><ApertureChart v-if="series[hand]" :frames="series[hand]!.series.frame_index" :values="series[hand]!.series.aperture_filtered" :peak-frames="series[hand]!.peak_frames"/><div v-else class="pd-empty">{{seriesErrors[hand]??'本次未保存该手结果。'}}</div></div></div>
          <h3>左右手差异</h3><el-table :data="summary?.comparisons??[]" size="small"><el-table-column label="指标" min-width="220"><template #default="{row}">{{label(row.metric)}}</template></el-table-column><el-table-column label="左手 − 右手" min-width="140"><template #default="{row}">{{formatNumber(row.absolute_difference,3)}}</template></el-table-column><el-table-column label="不对称比值" min-width="140"><template #default="{row}">{{formatNumber(row.asymmetry_ratio,3)}}</template></el-table-column></el-table>
          <el-collapse class="raw-results"><el-collapse-item v-for="result in session.finger_tapping_results" :key="result.id" :name="result.id" :title="`${result.hand==='LEFT'?'左手':'右手'} · ${formatDateTime(result.created_at)} · 查看全部保存数据`"><p>算法版本：{{result.analyzer_version??'暂无数据'}} · 数据来源：{{result.input_source}}</p><pre>{{json(result)}}</pre></el-collapse-item></el-collapse>
        </template>
      </section>
      <section class="pd-card result-section"><h2>面部表现分析</h2><div v-if="!session.micro_expression_results.length" class="pd-empty">本次未保存面部分析结果。模型不可用或未完成采集时，不生成分析数值。</div>
        <article v-for="result in session.micro_expression_results" :key="result.id" class="face-result"><h3>{{formatDateTime(result.created_at)}}</h3><p>模型：{{result.model_name??'暂无数据'}} {{result.model_version??''}} · 分析耗时：{{formatNumber(result.inference_time_ms,0,' ms')}}</p><p>预测类别：{{result.predicted_class??'暂无数据'}} · 主要标签：{{result.dominant_tag??'暂无数据'}}</p><el-table v-if="result.tag_distribution?.length" :data="result.tag_distribution" size="small"><el-table-column prop="name" label="标签"/><el-table-column label="模型得分"><template #default="{row}">{{formatNumber(row.score,4)}}</template></el-table-column></el-table><el-collapse><el-collapse-item title="查看模型原始输出与质量数据" :name="result.id"><pre>{{json(result)}}</pre></el-collapse-item></el-collapse></article>
      </section>
      <section v-if="session.functional_assessments.length" class="pd-card result-section"><h2>功能测试记录</h2><el-table :data="session.functional_assessments"><el-table-column label="测试" min-width="220"><template #default="{row}">{{FUNCTIONAL_TEST_LABELS[row.test_type]??row.test_type}}</template></el-table-column><el-table-column label="测量值" min-width="140"><template #default="{row}">{{formatNumber(row.value_primary,2,` ${row.unit}`)}}</template></el-table-column><el-table-column prop="notes" label="备注" min-width="180"/></el-table></section>
    </template>
  </div>
</template>

<style scoped>
.result-section{padding:24px;margin-top:20px;min-width:0}.result-section h2{margin:0 0 16px;font-size:20px}.result-section h3{font-size:16px;margin:24px 0 12px}.result-section p{line-height:1.7;color:var(--pd-text-secondary)}.saved-notes{white-space:pre-wrap;overflow-wrap:anywhere}.result-charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.raw-results{margin-top:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:420px;overflow:auto;background:#f6f8fb;padding:16px;border-radius:8px;font-size:12px}.face-result+.face-result{border-top:1px solid var(--pd-border);margin-top:24px}
@media(max-width:900px){.result-charts{grid-template-columns:1fr}.result-section{padding:16px}}
</style>
