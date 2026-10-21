<script setup lang="ts">
import {computed,nextTick,ref,watch} from 'vue'
import {monthCells,shiftMonth,todayKey,type DaySummary} from '@/followup/calendar'
const props=defineProps<{month:string;selected:string;days:Record<string,DaySummary>;loading?:boolean}>()
const emit=defineEmits<{month:[value:string];select:[value:string]}>()
const cells=computed(()=>monthCells(props.month))
const root=ref<HTMLElement|null>(null)
let pendingFocus=false
function keydown(event:KeyboardEvent,date:string){
  const delta:Record<string,number>={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7}
  if(delta[event.key]===undefined)return
  event.preventDefault()
  pendingFocus=true
  const next=new Date(date+'T00:00:00Z');next.setUTCDate(next.getUTCDate()+delta[event.key]!)
  const key=next.toISOString().slice(0,10)
  if(key.slice(0,7)!==props.month)emit('month',key.slice(0,7))
  emit('select',key)
}
watch(()=>[props.selected,props.month,props.loading],async()=>{
  if(!pendingFocus||props.loading)return
  await nextTick()
  root.value?.querySelector<HTMLButtonElement>(`button[data-date="${props.selected}"]`)?.focus()
  pendingFocus=false
})
function dayLabel(date:string){
  const day=props.days[date]
  return `${date}，${day?.completedTraining??0} 项已完成训练，${day?.assessments??0} 项评估`
}
</script>
<template>
  <section ref="root" class="activity-calendar pd-card" aria-label="训练日历" :aria-busy="loading">
    <div class="calendar-header"><el-button aria-label="上个月" :disabled="loading" @click="emit('month',shiftMonth(month,-1))">‹</el-button><h2>{{month.replace('-','年')}}月</h2><el-button aria-label="下个月" :disabled="loading" @click="emit('month',shiftMonth(month,1))">›</el-button><el-button :disabled="loading" @click="emit('month',todayKey().slice(0,7));emit('select',todayKey())">今天</el-button></div>
    <div class="calendar-week"><span v-for="day in ['一','二','三','四','五','六','日']" :key="day">{{day}}</span></div>
    <div class="calendar-days"><template v-for="(date,index) in cells" :key="date??index"><button v-if="date" type="button" :data-date="date" :aria-label="dayLabel(date)" :aria-pressed="selected===date" :class="{selected:selected===date,today:date===todayKey(),trained:(days[date]?.completedTraining??0)>0}" :disabled="loading" @click="emit('select',date)" @keydown="keydown($event,date)"><span class="calendar-date">{{Number(date.slice(-2))}}</span><span class="calendar-markers"><i v-if="days[date]?.completedTraining" class="training-dot"/><i v-if="days[date]?.assessments" class="assessment-dot"/></span></button><span v-else class="calendar-pad"/></template></div>
    <div class="calendar-legend"><span><i class="training-dot"/>已训练</span><span><i class="assessment-dot"/>有评估</span></div>
  </section>
</template>
<style scoped>
.activity-calendar{padding:20px;min-width:0}.calendar-header{display:flex;align-items:center;gap:10px;margin-bottom:18px}.calendar-header h2{font-size:18px;flex:1;margin:0;text-align:center}.calendar-header .el-button{margin:0}.calendar-week,.calendar-days{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px}.calendar-week span{text-align:center;padding:8px;color:var(--pd-text-secondary);font-size:13px}.calendar-days button{min-width:0;min-height:78px;border:1px solid transparent;background:transparent;border-radius:10px;color:var(--pd-text);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;cursor:pointer}.calendar-days button:hover{background:#f0f4fb}.calendar-days button:focus-visible{outline:2px solid var(--pd-primary);outline-offset:2px}.calendar-days button.trained{background:#eef7f3}.calendar-days button.today{border-color:var(--pd-primary);box-shadow:0 0 0 1px var(--pd-primary) inset}.calendar-days button.today .calendar-date{font-weight:800}.calendar-days button.selected{border-color:var(--pd-primary);background:var(--pd-primary-soft)}.calendar-markers{display:flex;gap:4px;height:7px}.calendar-count{font-size:10px;line-height:1}.calendar-legend{display:flex;align-items:center;flex-wrap:wrap;gap:16px;margin-top:18px;color:var(--pd-text-secondary);font-size:12px}.calendar-legend span{display:flex;align-items:center;gap:5px}i{display:inline-block;width:7px;height:7px;border-radius:50%}.training-dot{background:#288563}.assessment-dot{background:#5974c2}.unfinished-dot{background:#cb9436}@media(max-width:600px){.activity-calendar{padding:12px}.calendar-week,.calendar-days{gap:3px}.calendar-days button{min-height:64px;gap:5px}.calendar-header{gap:6px}.calendar-header h2{font-size:16px}.calendar-legend{gap:10px}}
</style>

<style scoped>
.calendar-days { grid-template-rows:repeat(6,78px); }
.calendar-week span,.calendar-legend { font-size:14px; }
@media(max-width:600px) { .calendar-days{grid-template-rows:repeat(6,64px)} }
</style>
