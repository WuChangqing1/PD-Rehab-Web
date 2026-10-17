<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {followupApi,pianoApi} from '@/api'
import {notifyError} from '@/api/client'
import PatientSelector from '@/components/PatientSelector.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import ActivityCalendar from '@/components/ActivityCalendar.vue'
import FollowupCharts from '@/components/FollowupCharts.vue'
import {usePatientContextStore} from '@/stores/patientContext'
import type {Patient,PianoSession,PoseSession} from '@/types'
import type {FollowUpData} from '@/followup/types'
import {buildActivities,summarizeDays,todayKey,monthRange,timestamp,type Activity} from '@/followup/calendar'
import {pianoPracticeKey,pianoConfigKey,poseConfigKey,usablePiano,metricValue,pianoMetricSpecs,poseMetricSpecs,GUIDED_METRICS,TAPPING_METRICS,objectiveSummary,type MetricSpec} from '@/followup/analysis'
import {buildTrendSeries,type TrendRowInput} from '@/followup/trends'
import {formatTrendValue,formatTrendDelta} from '@/followup/trendOption'
import {practiceLabel} from '@/piano/catalogue'
import {exerciseName} from '@/pose/exercises'
import {formatDateTime,NO_DATA} from '@/utils/format'

const route=useRoute(),router=useRouter(),store=usePatientContextStore()
const patient=ref<Patient|null>(null),feed=ref<FollowUpData|null>(null),calendarFeed=ref<FollowUpData|null>(null)
const patientId=computed(()=>patient.value?.id??null)
const tab=ref<'calendar'|'trends'|'report'>('calendar'),category=ref<'piano'|'pose'|'guided'|'tapping'>('piano')
const days=ref(90),month=ref(todayKey().slice(0,7)),selectedDate=ref(todayKey())
const loading=ref(false),calendarLoading=ref(false),error=ref(''),calendarError=ref('')
const DEMO_SOURCE='SEED_DEMO' as const
const scope=ref<'HUMAN_KEYBOARD'|'SEED_DEMO'>('HUMAN_KEYBOARD')
const pianoPractice=ref(''),pianoConfig=ref(''),poseExercise=ref(''),poseConfig=ref(''),guidedConfig=ref('')
let patientRequest=0,rangeRequest=0,calendarRequest=0,detailRequest=0
const range=computed(()=>{const end=todayKey(),start=new Date(end+'T00:00:00Z');start.setUTCDate(start.getUTCDate()-days.value+1);return [start.toISOString().slice(0,10),end] as const})
const localDate=(at:string|null)=>formatDateTime(timestamp(at)?.toISOString()??null)
async function loadRange(){
 const id=patientId.value;if(!id)return
 const request=++rangeRequest;loading.value=true;error.value='';feed.value=null
 try{const data=await followupApi.read(id,...range.value);if(request!==rangeRequest||id!==patientId.value)return;feed.value=data}
 catch(e){if(request===rangeRequest&&id===patientId.value)error.value='无法读取所选日期范围的记录，请重试。'}
 finally{if(request===rangeRequest)loading.value=false}
}
async function loadCalendar(){
 const id=patientId.value;if(!id)return
 const request=++calendarRequest;calendarLoading.value=true;calendarError.value='';calendarFeed.value=null
 try{const data=await followupApi.read(id,...monthRange(month.value));if(request!==calendarRequest||id!==patientId.value)return;calendarFeed.value=data}
 catch(e){if(request===calendarRequest&&id===patientId.value)calendarError.value='无法读取本月记录，请重试。'}
 finally{if(request===calendarRequest)calendarLoading.value=false}
}
function reset(){
 rangeRequest++;calendarRequest++;detailRequest++
 feed.value=null;calendarFeed.value=null;detailOpen.value=false;pianoDetail.value=null;poseDetail.value=null;guidedDetail.value=null
 pianoPractice.value='';pianoConfig.value='';poseExercise.value='';poseConfig.value='';guidedConfig.value=''
 loading.value=false;calendarLoading.value=false;detailBusy.value=false;error.value='';calendarError.value=''
}
async function usePatient(id:string){
 const request=++patientRequest;reset();patient.value=null
 const resolved=await store.resolve(id);if(request!==patientRequest||!resolved)return
 patient.value=resolved;scope.value=resolved.hospital_number==='DEMO-FOLLOWUP-20261017'?'SEED_DEMO':'HUMAN_KEYBOARD'
 router.replace({query:{...route.query,patientId:id}})
 await Promise.all([loadRange(),loadCalendar()])
}
function clearPatient(){patientRequest++;reset();patient.value=null;void store.select(null)}
function changeMonth(value:string){month.value=value;if(selectedDate.value.slice(0,7)!==value)selectedDate.value=value+'-01'}
watch(month,loadCalendar);watch(days,loadRange)
const activities=computed(()=>calendarFeed.value?buildActivities(calendarFeed.value):[])
const calendarDays=computed(()=>summarizeDays(activities.value.filter(a=>a.kind==='assessment'||sourceMatch(a.source))))
const dayActivities=computed(()=>activities.value.filter(a=>a.day===selectedDate.value))
const periodActivities=computed(()=>feed.value?buildActivities(feed.value):[])
const completedTraining=computed(()=>periodActivities.value.filter(a=>a.kind!=='assessment'&&a.completed&&sourceMatch(a.source)).length)
const trainedDays=computed(()=>new Set(periodActivities.value.filter(a=>a.kind!=='assessment'&&a.completed&&sourceMatch(a.source)).map(a=>a.day)).size)
const sourceMatch=(source:string|null|undefined)=>source===scope.value
const pianoRows=computed(()=>(feed.value?.piano??[]).filter(r=>sourceMatch(r.input_source)&&usablePiano(r)))
const poseRows=computed(()=>(feed.value?.pose??[]).filter(r=>sourceMatch(r.input_source)&&!!r.completed_at))
const guidedRows=computed(()=>(feed.value?.guided??[]).filter(r=>sourceMatch(r.source)&&r.status==='COMPLETED'))
const tappingRows=computed(()=>(feed.value?.tapping??[]).filter(r=>sourceMatch(r.input_source)))
const practices=computed(()=>[...new Set(pianoRows.value.map(pianoPracticeKey))].map(key=>({key,label:practiceLabel(pianoRows.value.find(r=>pianoPracticeKey(r)===key)!.mode,key)})))
const exercises=computed(()=>[...new Set(poseRows.value.map(r=>r.exercise_type))].map(key=>({key,label:exerciseName(key,feed.value?.exercise_names?.[key])})))
const pianoConfigs=computed(()=>{
 const unique=new Map<string,PianoSession>();for(const r of pianoRows.value.filter(r=>pianoPracticeKey(r)===pianoPractice.value))unique.set(pianoConfigKey(r),r)
 return [...unique].map(([key,r])=>({key,label:`${r.bpm} BPM · 判定 ${r.judgement_window_ms} ms · ${r.hand_mode==='BOTH'?'双手':r.hand_mode==='ALTERNATING'?'交替':'单手'} · 序列 ${r.sequence_length} · 密度 ${r.note_density} · ${r.session_duration_sec} 秒 · 复杂度 ${r.finger_complexity} · 弱侧 ${r.weak_side_ratio} · 上限 ${r.difficulty_before_json?.tempo_ceiling_bpm??'未标注'} BPM · 弱手 ${r.difficulty_before_json?.weak_hand==='LEFT'?'左':r.difficulty_before_json?.weak_hand==='RIGHT'?'右':'未标注'} · ${r.difficulty_before_json?.recipe_algorithm_version??'配方版本未标注'}`}))
})
const poseConfigs=computed(()=>{
 const unique=new Map<string,PoseSession>();for(const r of poseRows.value.filter(r=>r.exercise_type===poseExercise.value))unique.set(poseConfigKey(r),r)
 return [...unique].map(([key,r])=>({key,label:`${r.execution_mode==='SEATED'?'坐姿':r.execution_mode==='STANDING_SUPPORTED'?'站姿扶椅':'姿态未标注'} · ${r.difficulty_json?.bpm??'未标注'} BPM · ${r.exercise_definition_version??'动作版本未标注'}`}))
})
const guidedKey=(r:FollowUpData['guided'][number])=>JSON.stringify([r.song_id,r.selected_hand,r.difficulty,r.segment_1_bpm,r.segment_2_bpm])
const guidedConfigs=computed(()=>[...new Set(guidedRows.value.map(guidedKey))].map(key=>{
 const [song,hand,difficulty,first,second]=JSON.parse(key);return {key,label:`${song==='two_tigers'?'两只老虎':song??'曲目未标注'} · ${hand==='LEFT'?'左手':'右手'} · ${{BEGINNER:'初级',INTERMEDIATE:'中级',ADVANCED:'高级'}[difficulty as string]??'难度未标注'} · ${first??'未标注'} → ${second??'未标注'} BPM`}
}))
watch(()=>[practices.value,loading.value] as const,([options,busy])=>{if(!busy&&!options.some(x=>x.key===pianoPractice.value))pianoPractice.value=options[0]?.key??''},{immediate:true})
watch(()=>[exercises.value,loading.value] as const,([options,busy])=>{if(!busy&&!options.some(x=>x.key===poseExercise.value))poseExercise.value=options[0]?.key??''},{immediate:true})
watch(()=>[pianoConfigs.value,loading.value] as const,([options,busy])=>{if(!busy&&!options.some(x=>x.key===pianoConfig.value))pianoConfig.value=options[0]?.key??''},{immediate:true})
watch(()=>[poseConfigs.value,loading.value] as const,([options,busy])=>{if(!busy&&!options.some(x=>x.key===poseConfig.value))poseConfig.value=options[0]?.key??''},{immediate:true})
watch(()=>[guidedConfigs.value,loading.value] as const,([options,busy])=>{if(!busy&&!options.some(x=>x.key===guidedConfig.value))guidedConfig.value=options[0]?.key??''},{immediate:true})
function row(at:string|null,value:number|null,source:string|null,version:string|null):TrendRowInput{return {at:timestamp(at)?.toISOString()??null,value,source,version}}
const charts=computed(()=>{
 const specs:Array<{spec:MetricSpec;rows:TrendRowInput[]}>=[]
 if(category.value==='piano'){
  const selected=pianoRows.value.filter(r=>pianoPracticeKey(r)===pianoPractice.value&&pianoConfigKey(r)===pianoConfig.value)
  for(const spec of pianoMetricSpecs(pianoPractice.value))specs.push({spec,rows:selected.map(r=>row(r.completed_at??r.started_at,metricValue(r,spec.key),r.input_source,r.metrics_version))})
 }else if(category.value==='pose'){
  const selected=poseRows.value.filter(r=>r.exercise_type===poseExercise.value&&poseConfigKey(r)===poseConfig.value)
  for(const spec of poseMetricSpecs(poseExercise.value))specs.push({spec,rows:selected.map(r=>row(r.completed_at??r.started_at,metricValue(r,spec.key),r.input_source,r.algorithm_version))})
 }else if(category.value==='guided'){
  const selected=guidedRows.value.filter(r=>guidedKey(r)===guidedConfig.value)
  for(const spec of GUIDED_METRICS)specs.push({spec,rows:selected.map(r=>row(r.completed_at??r.started_at,metricValue(r.metrics,spec.key),r.source,r.version))})
 }else{
  for(const metric of TAPPING_METRICS)for(const hand of ['LEFT','RIGHT']){const spec={...metric,key:`${hand}_${metric.key}`,label:`${hand==='LEFT'?'左手':'右手'}${metric.label}`};specs.push({spec,rows:tappingRows.value.filter(r=>r.hand===hand).map(r=>row(r.created_at,metricValue(r,metric.key),r.input_source,r.analyzer_version))})}
 }
 return specs.map(({spec,rows})=>({spec,built:buildTrendSeries(rows,{source:scope.value})}))
})
const report=computed(()=>charts.value.map(item=>({...item,...objectiveSummary(item.built)})))
const provenance=computed(()=>({excludedByModule:{piano:(feed.value?.piano??[]).filter(r=>!sourceMatch(r.input_source)).length,pose:(feed.value?.pose??[]).filter(r=>!sourceMatch(r.input_source)).length,tapping:(feed.value?.tapping??[]).filter(r=>!sourceMatch(r.input_source)).length},excludedRecords:[...(feed.value?.piano??[]),...(feed.value?.pose??[]),...(feed.value?.tapping??[])].filter(r=>!sourceMatch(r.input_source)).length}))
const detailOpen=ref(false),detailBusy=ref(false),pianoDetail=ref<Awaited<ReturnType<typeof pianoApi.getSession>>|null>(null),poseDetail=ref<PoseSession|null>(null),guidedDetail=ref<Record<string,unknown>|null>(null)
async function openActivity(activity:Activity){
 if(activity.kind==='assessment'){router.push({name:'assessment-results',params:{sessionId:activity.id},query:{patientId:patientId.value}});return}
 pianoDetail.value=null;poseDetail.value=null;guidedDetail.value=null
 if(activity.kind==='piano'){
  const request=++detailRequest,id=patientId.value;detailBusy.value=true
  try{const detail=await pianoApi.getSession(activity.id);if(request!==detailRequest||id!==patientId.value||detail.patient_id!==id)return;pianoDetail.value=detail;detailOpen.value=true}
  catch(e){if(request===detailRequest)notifyError(e,'无法读取训练结果。')}
  finally{if(request===detailRequest)detailBusy.value=false}
 }else{if(activity.kind==='pose')poseDetail.value=activity.raw as PoseSession;else guidedDetail.value=activity.raw as Record<string,unknown>;detailOpen.value=true}
}
const detailMetrics=computed(()=>pianoDetail.value?pianoMetricSpecs(pianoPracticeKey(pianoDetail.value)).map(spec=>({...spec,value:metricValue(pianoDetail.value,spec.key)})):poseDetail.value?poseMetricSpecs(poseDetail.value.exercise_type).map(spec=>({...spec,value:metricValue(poseDetail.value,spec.key)})):GUIDED_METRICS.map(spec=>({...spec,value:metricValue(guidedDetail.value?.metrics??{},spec.key)})))
const detailSource=computed(()=>pianoDetail.value?.input_source??poseDetail.value?.input_source??guidedDetail.value?.source)
const json=(value:unknown)=>JSON.stringify(value,null,2)
const moduleLabel={assessment:'评估',piano:'钢琴',pose:'芭蕾',guided:'曲目跟弹'}
onMounted(async()=>{if(route.query.tab==='trends'||route.query.tab==='report')tab.value=route.query.tab;if(typeof route.query.patientId==='string')await usePatient(route.query.patientId)})
</script>

<template>
 <div class="pd-page">
  <div class="pd-page-header"><h1 class="pd-page-title">随访与报告</h1></div>
  <SelectedPatientBar v-if="patient" :patient="patient" :task-label="feed?.is_showcase?'独立演示患者':''" @change="clearPatient"/>
  <PatientSelector v-if="!patient" title="选择患者" @select="p=>usePatient(p.id)"/>
  <template v-else>
   <div class="followup-toolbar"><el-select v-model="days" aria-label="统计日期范围" style="width:160px"><el-option v-for="n in [30,90,180,365]" :key="n" :value="n" :label="`近 ${n} 天`"/></el-select><el-radio-group v-model="scope" aria-label="数据来源"><el-radio-button value="HUMAN_KEYBOARD">实际记录</el-radio-button><el-radio-button v-if="feed?.is_showcase || feed?.piano.some(r=>r.input_source===DEMO_SOURCE) || feed?.pose.some(r=>r.input_source===DEMO_SOURCE)" :value="DEMO_SOURCE">示例记录</el-radio-button></el-radio-group><el-button :loading="loading" @click="loadRange();loadCalendar()">刷新</el-button></div>
   <el-alert v-if="scope===DEMO_SOURCE" title="演示数据" description="独立示例记录，不计入真实患者结论。" type="warning" :closable="false" class="scope-label"/>
   <el-alert v-if="error" :title="error" type="error" :closable="false"/>
   <div class="followup-overview"><div><span>统计范围</span><strong class="date-range">{{range[0]}} — {{range[1]}}</strong></div><div><span>训练天数</span><strong>{{trainedDays}}</strong></div><div><span>已完成训练</span><strong>{{completedTraining}}</strong></div><div><span>评估记录</span><strong>{{feed?.assessments.length??0}}</strong></div></div>
   <el-tabs v-model="tab" class="pd-card tabs-card">
    <el-tab-pane label="训练日历" name="calendar">
     <el-alert v-if="calendarError" :title="calendarError" type="error" :closable="false"><el-button link @click="loadCalendar">重试</el-button></el-alert>
     <div class="calendar-layout"><ActivityCalendar :month="month" :selected="selectedDate" :days="calendarDays" :loading="calendarLoading" @month="changeMonth" @select="value=>selectedDate=value"/>
      <section class="pd-card day-records" v-loading="calendarLoading"><h2>{{selectedDate}}</h2><p class="day-summary" v-if="!calendarError">{{calendarDays[selectedDate]?.completedTraining??0}} 项已完成训练 · {{calendarDays[selectedDate]?.assessments??0}} 项评估</p>
       <div v-if="calendarError" class="pd-empty">当日记录暂不可用</div><div v-else-if="!dayActivities.length && !calendarLoading" class="pd-empty">当天暂无记录</div>
       <article v-for="activity in dayActivities" :key="`${activity.kind}-${activity.id}`" class="day-record"><div><el-tag size="small" type="info">{{moduleLabel[activity.kind]}}</el-tag><strong>{{activity.label}}</strong><el-tag v-if="activity.source && activity.source!=='HUMAN_KEYBOARD'" size="small" type="warning">{{activity.source===DEMO_SOURCE?'演示':'来源非测量'}}</el-tag></div><p>{{localDate(activity.at)}} · {{activity.status}}</p><el-button link type="primary" :loading="detailBusy" @click="openActivity(activity)">查看结果</el-button></article>
      </section>
     </div>
    </el-tab-pane>
    <el-tab-pane label="趋势分析" name="trends"/>
    <el-tab-pane label="综合报告" name="report"/>
   </el-tabs>
   <section v-if="tab!=='calendar'" class="analysis-section" v-loading="loading">
    <div class="analysis-filters"><el-radio-group v-model="category" aria-label="分析项目"><el-radio-button value="piano">钢琴练习</el-radio-button><el-radio-button value="pose">芭蕾动作</el-radio-button><el-radio-button value="guided">曲目跟弹</el-radio-button><el-radio-button value="tapping">手指敲击</el-radio-button></el-radio-group>
     <template v-if="category==='piano'"><el-select v-model="pianoPractice" aria-label="钢琴练习" placeholder="暂无练习记录"><el-option v-for="p in practices" :key="p.key" :value="p.key" :label="p.label"/></el-select><el-select v-model="pianoConfig" aria-label="钢琴训练参数" class="config-select" placeholder="暂无可比训练参数"><el-option v-for="c in pianoConfigs" :key="c.key" :value="c.key" :label="c.label"/></el-select></template>
     <template v-if="category==='pose'"><el-select v-model="poseExercise" aria-label="芭蕾动作" placeholder="暂无动作记录"><el-option v-for="p in exercises" :key="p.key" :value="p.key" :label="p.label"/></el-select><el-select v-model="poseConfig" aria-label="动作训练参数" class="config-select" placeholder="暂无可比训练参数"><el-option v-for="c in poseConfigs" :key="c.key" :value="c.key" :label="c.label"/></el-select></template>
     <el-select v-if="category==='guided'" v-model="guidedConfig" aria-label="曲目训练参数" class="config-select" placeholder="暂无曲目记录"><el-option v-for="c in guidedConfigs" :key="c.key" :value="c.key" :label="c.label"/></el-select>
    </div>
    <p class="analysis-context">{{scope===DEMO_SOURCE?'示例记录':'实际记录'}} · 仅比较相同练习与参数 · 已完成轮次 · 算法版本分线</p>
    <template v-if="tab==='trends'"><el-alert v-if="provenance.excludedRecords > 0" type="info" :closable="false" :title="`其他来源记录：钢琴 ${provenance.excludedByModule.piano}，芭蕾 ${provenance.excludedByModule.pose}，手指 ${provenance.excludedByModule.tapping}`"/><FollowupCharts :items="charts"/></template>
    <template v-else><el-alert v-if="provenance.excludedRecords > 0" type="info" :closable="false" :title="`报告未纳入 ${provenance.excludedRecords} 条其他来源记录`"/><div class="pd-card report-card"><h2>客观指标汇总</h2><p>变化值为本次减前次；仅比较最近算法版本。数值变化不等同于临床改善；未校正用药、疲劳与采集条件。</p><el-table :data="report" size="small"><el-table-column prop="spec.label" label="指标" min-width="190"/><el-table-column label="最近值" min-width="120"><template #default="{row}">{{row.latest?formatTrendValue(row.latest.value,row.spec.unit):NO_DATA}}</template></el-table-column><el-table-column label="前次值" min-width="120"><template #default="{row}">{{row.previous?formatTrendValue(row.previous.value,row.spec.unit):NO_DATA}}</template></el-table-column><el-table-column label="变化值" min-width="120"><template #default="{row}">{{row.delta===null?NO_DATA:formatTrendDelta(row.delta,row.spec.unit)}}</template></el-table-column><el-table-column label="中位数" min-width="120"><template #default="{row}">{{row.median===null?NO_DATA:formatTrendValue(row.median,row.spec.unit)}}</template></el-table-column><el-table-column label="范围" min-width="190"><template #default="{row}">{{row.minimum===null?NO_DATA:`${formatTrendValue(row.minimum,row.spec.unit)} — ${formatTrendValue(row.maximum,row.spec.unit)}`}}</template></el-table-column><el-table-column prop="count" label="同版本次数" min-width="110"/></el-table><p v-if="report.some(r=>r.count<2)" class="pd-muted">部分指标不足 2 次可比记录，暂不判断趋势。</p><p v-if="report.some(r=>r.latest&&!r.version)" class="pd-muted">部分记录未标注算法版本，未计算跨次变化。</p></div></template>
   </section>
  </template>
  <el-dialog v-model="detailOpen" title="训练结果" width="min(800px,94vw)" destroy-on-close>
   <template v-if="pianoDetail||poseDetail||guidedDetail"><el-tag v-if="detailSource!=='HUMAN_KEYBOARD'" type="warning">{{detailSource===DEMO_SOURCE?'演示数据':'非测量记录'}}</el-tag><el-table :data="detailMetrics"><el-table-column prop="label" label="指标" min-width="200"/><el-table-column label="结果"><template #default="{row}">{{row.value===null?NO_DATA:formatTrendValue(row.value,row.unit)}}</template></el-table-column></el-table><el-collapse><el-collapse-item v-if="pianoDetail" title="原始按键记录" name="events"><el-table :data="pianoDetail.events" max-height="360"><el-table-column prop="event_index" label="#" width="55"/><el-table-column prop="target_time_ms" label="目标 ms"/><el-table-column prop="key_down_time_ms" label="按下 ms"/><el-table-column prop="key_up_time_ms" label="释放 ms"/><el-table-column prop="is_prompt" label="示范"/></el-table></el-collapse-item><el-collapse-item v-if="poseDetail" title="已保存动作分析数据" name="pose"><pre>{{json(poseDetail.raw_metrics_json)}}</pre></el-collapse-item><el-collapse-item v-if="guidedDetail" title="已保存曲目指标" name="guided"><pre>{{json(guidedDetail.metrics)}}</pre></el-collapse-item></el-collapse></template>
  </el-dialog>
 </div>
</template>
<style scoped>
.followup-toolbar,.analysis-filters{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px}.scope-label{margin-bottom:18px}.followup-overview{display:grid;grid-template-columns:2fr repeat(3,1fr);gap:20px;background:white;border:1px solid var(--pd-border);border-radius:16px;padding:22px;margin:20px 0}.followup-overview>div{display:flex;flex-direction:column;gap:10px;min-width:0}.followup-overview span{font-size:12px;color:var(--pd-text-secondary)}.followup-overview strong{font-size:26px;font-variant-numeric:tabular-nums}.followup-overview .date-range{font-size:15px;line-height:1.6}.tabs-card{padding:6px 20px 20px}.calendar-layout{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:20px}.calendar-layout>.pd-card+.pd-card{margin-top:0}.day-records{padding:20px;min-width:0;max-height:650px;overflow:auto}.day-records h2{font-size:19px;margin:0}.day-summary{color:var(--pd-text-secondary);font-size:13px;margin:12px 0 18px}.day-record{padding:16px 0;border-top:1px solid var(--pd-border)}.day-record>div{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.day-record strong{font-size:14px}.day-record p{color:var(--pd-text-secondary);font-size:12px;margin:10px 0}.analysis-section{margin-top:20px}.analysis-filters .el-select{width:230px}.analysis-filters .config-select{width:min(100%,540px)}.analysis-context{font-size:12px;color:var(--pd-text-secondary);margin:0 0 18px}.analysis-section>.el-alert{margin-bottom:16px}.report-card{padding:24px;min-width:0}.report-card h2{font-size:20px;margin:0}.report-card p{line-height:1.7;font-size:13px;color:var(--pd-text-secondary)}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto;font-size:12px;background:#f6f8fb;padding:16px}@media(max-width:1100px){.calendar-layout{grid-template-columns:1fr}.followup-overview{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.tabs-card{padding:4px 10px 12px}.followup-overview{gap:16px;padding:16px}.followup-overview strong{font-size:22px}.followup-overview .date-range{font-size:12px}.analysis-filters .el-radio-group{display:flex;flex-wrap:wrap}.analysis-filters .el-select,.analysis-filters .config-select{width:100%}.day-records{padding:16px}.report-card{padding:16px}}
</style>
