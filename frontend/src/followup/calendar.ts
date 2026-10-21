import type { FollowUpData } from './types.ts'
import { practiceLabel } from '../piano/catalogue.ts'
import { exerciseName } from '../pose/exercises.ts'
import { SESSION_TYPE_LABELS, SESSION_STATUS_LABELS } from '../utils/format.ts'

export const DAY_OFFSET_MINUTES=480
export function timestamp(value:string|null|undefined):Date|null {
  if(!value)return null
  const date=new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)?value:value+'Z')
  return Number.isFinite(date.getTime())?date:null
}
export function dayKey(value:string|null|undefined, offset=DAY_OFFSET_MINUTES):string|null {
  const date=timestamp(value)
  return date?new Date(date.getTime()+offset*60000).toISOString().slice(0,10):null
}
export function todayKey():string { return dayKey(new Date().toISOString())! }
export function monthCells(month:string):Array<string|null>{
  if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(month))return []
  const [year,part]=month.split('-').map(Number)
  const first=new Date(Date.UTC(year!,part!-1,1))
  const count=new Date(Date.UTC(year!,part!,0)).getUTCDate()
  const cells:Array<string|null>=Array((first.getUTCDay()+6)%7).fill(null)
  for(let i=1;i<=count;i++)cells.push(`${month}-${String(i).padStart(2,'0')}`)
  while(cells.length<42)cells.push(null)
  return cells
}
export function shiftMonth(month:string,delta:number):string{
  const date=new Date(month+'-01T00:00:00Z');date.setUTCMonth(date.getUTCMonth()+delta)
  return date.toISOString().slice(0,7)
}
export function monthRange(month:string):[string,string]{
  const dates=monthCells(month).filter((x):x is string=>!!x)
  return [dates[0]!,dates.at(-1)!]
}
export interface Activity {
  id:string; kind:'assessment'|'piano'|'pose'|'guided'; at:string; day:string; label:string; status:string
  completed:boolean; source:string|null; raw:unknown
}
export function buildActivities(data:Pick<FollowUpData,'assessments'|'piano'|'pose'|'guided'>&{exercise_names?:Record<string,string>}):Activity[]{
  const rows:Activity[]=[]
  function add(kind:Activity['kind'],record:{id:string},at:string|null,label:string,status:string,completed:boolean,source:string|null){
    const day=dayKey(at);if(!at||!day)return
    rows.push({id:record.id,kind,at,day,label,status,completed,source,raw:record})
  }
  for(const r of data.assessments)add('assessment',r,r.started_at,SESSION_TYPE_LABELS[r.session_type]??r.session_type,SESSION_STATUS_LABELS[r.status]??r.status,r.status==='COMPLETED',null)
  for(const r of data.piano){
    const interrupted=r.difficulty_before_json?.completion_status==='INTERRUPTED'
    add('piano',r,r.started_at,practiceLabel(r.mode,r.recipe_id),interrupted?'已中断':r.completed_at?'已完成':'未完成',!!r.completed_at&&!interrupted,r.input_source)
  }
  for(const r of data.pose)add('pose',r,r.started_at,exerciseName(r.exercise_type,data.exercise_names?.[r.exercise_type]),r.completed_at?'已完成':'未完成',!!r.completed_at,r.input_source)
  for(const r of data.guided)add('guided',r,r.started_at,'曲目跟弹',r.status==='COMPLETED'?'已完成':r.status==='CANCELLED'?'已取消':'未完成',r.status==='COMPLETED',r.source)
  return rows.sort((a,b)=>timestamp(b.at)!.getTime()-timestamp(a.at)!.getTime())
}
export interface DaySummary {assessments:number; training:number; completedTraining:number; unfinished:number}
export function summarizeDays(rows:readonly Activity[]):Record<string,DaySummary>{
  const days:Record<string,DaySummary>={}
  for(const row of rows){
    const day=days[row.day]??={assessments:0,training:0,completedTraining:0,unfinished:0}
    if(row.kind==='assessment')day.assessments++
    else{day.training++;if(row.completed)day.completedTraining++}
    if(!row.completed)day.unfinished++
  }
  return days
}
