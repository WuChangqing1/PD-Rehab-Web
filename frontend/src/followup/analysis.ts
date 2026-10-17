import type {PianoSession,PoseSession} from '../types/index.ts'
import {RECIPE_METRIC_ROWS} from '../piano/metricDefinitions.ts'
import type {TrendSeries,TrendUnit,TrendPoint} from './trends.ts'

export interface MetricSpec {key:string;label:string;unit:TrendUnit}
export function pianoPracticeKey(row:Pick<PianoSession,'recipe_id'|'mode'>):string{return row.recipe_id??row.mode}
export function pianoConfigKey(row:PianoSession):string{
 const audit=row.difficulty_before_json
 return JSON.stringify([row.bpm,row.judgement_window_ms,row.sequence_length,row.note_density,row.hand_mode,row.weak_side_ratio,row.finger_complexity,row.session_duration_sec,audit?.tempo_ceiling_bpm??null,audit?.weak_hand??null,audit?.recipe_algorithm_version??null])
}
export function poseConfigKey(row:PoseSession):string{
 return JSON.stringify([row.execution_mode,row.difficulty_json?.bpm??null,row.exercise_definition_version])
}
export function usablePiano(row:PianoSession):boolean{return !!row.completed_at&&row.difficulty_before_json?.completion_status!=='INTERRUPTED'}
export function metricValue(row:unknown,key:string):number|null{
 const record=row as Record<string,unknown>
 const direct=record[key]
 const audit=record.difficulty_before_json as Record<string,unknown>|null
 const server=audit?.server_metrics as Record<string,unknown>|null
 const raw=record.raw_metrics_json as Record<string,unknown>|null
 const value=server?.[key]??direct??raw?.[key]
 return typeof value==='number'&&Number.isFinite(value)?value:null
}
export function pianoMetricSpecs(practice:string):MetricSpec[]{
 const common:MetricSpec[]=[
  {key:'accuracy',label:'准确率',unit:'ratio'}, {key:'timing_mae_ms',label:'节拍绝对误差',unit:'ms'},
  {key:'mean_response_latency_ms',label:'平均反应延迟',unit:'ms'}, {key:'miss_rate',label:'漏击率',unit:'ratio'},
  {key:'response_latency_cv',label:'反应延迟变异系数',unit:'number'},
  {key:'median_response_latency_ms',label:'反应延迟中位数',unit:'ms'},
  {key:'early_press_rate',label:'提前按键率',unit:'ratio'}, {key:'late_press_rate',label:'延迟按键率',unit:'ratio'},
  {key:'session_completion_rate',label:'轮次完成率',unit:'ratio'},
 ]
 if(['ALTERNATING_HANDS','BIMANUAL_SYNC','BIMANUAL_OFFSET'].includes(practice))common.push(
  {key:'left_accuracy',label:'左手准确率',unit:'ratio'},{key:'right_accuracy',label:'右手准确率',unit:'ratio'},
  {key:'left_right_latency_difference',label:'左右反应延迟差',unit:'ms'})
 if(['MAPPED_SEQUENCE','MEMORY_RHYTHM','REVERSE_SEQUENCE'].includes(practice))common.push({key:'sequence_completion_rate',label:'序列完成率',unit:'ratio'})
 for(const m of RECIPE_METRIC_ROWS[practice]??[])common.push({key:m.key,label:m.label,unit:m.kind==='ratio'?'ratio':m.kind==='ms'?'ms':m.key.endsWith('_count')?'count':'number'})
 return common
}
export function poseMetricSpecs(exercise:string):MetricSpec[]{
 const metrics:MetricSpec[]=[{key:'repetition_count',label:'完成次数',unit:'count'},{key:'hold_time_sec',label:'保持时间',unit:'sec'},
  {key:'movement_speed',label:'动作速度（°/秒）',unit:'number'},{key:'valid_pose_frame_ratio',label:'有效姿态帧比例',unit:'ratio'},
  {key:'left_right_angle_difference_deg',label:'左右角度差',unit:'deg'},{key:'trunk_angle_deg',label:'躯干倾斜角',unit:'deg'},
  {key:'angle_std_deg',label:'角度波动',unit:'deg'}]
 if(exercise==='BALLET_FIRST_POSITION')return metrics.filter(m=>!['repetition_count','movement_speed'].includes(m.key))
 const joint=['BALLET_TENDU','BALLET_WEIGHT_SHIFT'].includes(exercise)?'hip':exercise==='BALLET_DEMI_PLIE'?'knee':'shoulder'
 for(const side of ['left','right'])metrics.push({key:joint==='hip'?`${side}_hip_abduction_deg`:`${side}_${joint}_max_angle_deg`,label:`${side==='left'?'左':'右'}侧${joint==='hip'?'髋外展':joint==='knee'?'膝关节':'肩关节'}最大角度`,unit:'deg'})
 return metrics
}
export const GUIDED_METRICS:MetricSpec[]=[
 {key:'first_attempt_accuracy',label:'首次按键准确率',unit:'ratio'},
 {key:'total_attempt_accuracy',label:'全部按键准确率',unit:'ratio'},
 {key:'mean_response_latency_ms',label:'平均反应延迟',unit:'ms'},
 {key:'skip_count',label:'跳过音符数',unit:'count'},
 {key:'wrong_press_count',label:'误按次数',unit:'count'}, {key:'completion_rate',label:'曲目完成率',unit:'ratio'},
]
export const TAPPING_METRICS:MetricSpec[]=[
 {key:'tapping_frequency',label:'敲击频率（Hz）',unit:'number'},{key:'avg_amplitude',label:'平均归一化幅度',unit:'number'},
 {key:'avg_speed',label:'平均归一化速度',unit:'number'},{key:'avg_cycle_duration',label:'平均周期',unit:'sec'},
 {key:'cycle_cv',label:'周期变异系数',unit:'number'},{key:'amplitude_cv',label:'幅度变异系数',unit:'number'},
 {key:'speed_cv',label:'速度变异系数',unit:'number'},{key:'amplitude_slope',label:'幅度变化斜率',unit:'number'},
 {key:'speed_slope',label:'速度变化斜率',unit:'number'},{key:'cycle_slope',label:'周期变化斜率',unit:'number'},
 {key:'interruptions',label:'中断次数',unit:'count'},{key:'valid_frame_ratio',label:'有效帧比例',unit:'ratio'},
 {key:'avg_landmark_confidence',label:'平均手别置信度',unit:'ratio'},
]
export interface ObjectiveSummary {latest:TrendPoint|null;previous:TrendPoint|null;delta:number|null;count:number;median:number|null;minimum:number|null;maximum:number|null;version:string|null}
export function objectiveSummary(series:TrendSeries):ObjectiveSummary{
 const latest=series.points.at(-1)??null
 const compatible=latest?.version?series.points.filter(p=>p.version===latest.version):latest?[latest]:[]
 const previous=compatible.at(-2)??null,values=compatible.map(p=>p.value).sort((a,b)=>a-b)
 const mid=Math.floor(values.length/2)
 return {latest,previous,delta:latest&&previous?latest.value-previous.value:null,count:values.length,
  median:values.length?(values.length%2?values[mid]!:(values[mid-1]!+values[mid]!)/2):null,
  minimum:values[0]??null,maximum:values.at(-1)??null,version:latest?.version??null}
}
