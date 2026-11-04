<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { http, notifyError } from '@/api/client'
import TrainingFaceRecordings from './TrainingFaceRecordings.vue'

const props = defineProps<{patientId: string}>()
type External = {
  id: string; record_type: string; source_record_id: string; schema_version: string
  task_version: string | null; metric_version: string | null; received_at: string
  captured_at_ms: number | null; origin: string; payload_sha256: string
  title?: string; plan_start?: string; version_count?: number; version_order?: string
  snapshot_revision?: number | null
  progress?: {completed_units: number; target: number; target_type: 'count' | 'minutes'} | null
}
type Detail = External & {payload: Record<string, unknown>}
const rows = ref<External[]>([])
const view = ref<'activity' | 'plans'>('activity')
const day = ref(new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Shanghai'}).format(new Date()))
const history = ref<External | null>(null)
const busy = ref(false)
const error = ref('')
const nextOffset = ref<number | null>(null)
const detail = ref<Detail | null>(null)
const detailOpen = ref(false)
let epoch = 0
let detailRequest = 0
const kinds: Record<string,string> = {
  PIANO_SESSION:'软件钢琴练习', PIECE_PERFORMANCE:'软件曲目演奏',
  DANCE_SESSION:'软件舞蹈练习', TRAINING_PLAN:'软件训练计划',
  TRAINING_PLAN_EVENT:'软件计划执行记录', OTHER:'其他软件记录',
}
const fmt = new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai', dateStyle:'short', timeStyle:'medium'})
function timestamp(value: number | string | null) {
  if (value == null) return '未记录'
  const d = new Date(value)
  return Number.isFinite(d.valueOf()) ? fmt.format(d) : '未记录'
}
const amount = new Intl.NumberFormat('zh-CN', {maximumFractionDigits: 3})
function progressText(row: External) {
  const p = row.progress
  if (!p) return '进度未知'
  const completed = p.target_type === 'minutes' ? p.completed_units / 60000 : p.completed_units
  return amount.format(completed) + '/' + amount.format(p.target) + (p.target_type === 'minutes' ? ' 分钟' : ' 次')
}
async function fetchPage(offset: number) {
  const plans = view.value === 'plans'
  const {data} = await http.get<{items: External[]; next_offset: number | null}>(
    plans ? '/integration/v1/plans' : '/integration/v1/records',
    {params: {patient_id: props.patientId, offset, limit: 30,
      ...(plans ? {on_date: day.value, snapshot_id: history.value?.id} : {exclude_plan_snapshots: true})}},
  )
  return data
}
let refreshing = false
let timer: ReturnType<typeof setInterval> | undefined
const refreshFailed = ref(false)
async function refreshVisible() {
  // Keep open snapshots stable. Resume the live list when the viewer closes.
  if (document.hidden || !props.patientId || busy.value || refreshing || detailOpen.value || history.value) return
  const generation = epoch
  const visible = Math.max(30, rows.value.length)
  refreshing = true
  try {
    const updated = new Map<string, External>()
    let offset: number | null = 0
    for (let pages = 0; offset !== null && pages < Math.ceil(visible / 30); pages++) {
      const page = await fetchPage(offset)
      if (generation !== epoch || history.value || detailOpen.value || document.hidden) return
      for (const row of page.items) updated.set(row.id, row)
      offset = page.next_offset
    }
    rows.value = [...updated.values()]
    nextOffset.value = offset
    error.value = ''
    refreshFailed.value = false
  } catch {
    if (generation === epoch) refreshFailed.value = true
  } finally {
    refreshing = false
  }
}
onMounted(() => {
  timer = setInterval(() => void refreshVisible(), 15000)
  document.addEventListener('visibilitychange', refreshVisible)
})
onUnmounted(() => {
  epoch++
  if (timer !== undefined) clearInterval(timer)
  document.removeEventListener('visibilitychange', refreshVisible)
})
async function load(reset = false) {
  const request = ++epoch
  if (reset) { rows.value = []; nextOffset.value = null; refreshFailed.value = false }
  busy.value = true; error.value = ''
  try {
    const data = await fetchPage(reset ? 0 : nextOffset.value ?? 0)
    if (request !== epoch) return
    rows.value = reset ? data.items : [...rows.value, ...data.items]
    nextOffset.value = data.next_offset
  } catch {
    if (request === epoch) error.value = '软件端记录读取失败，请刷新重试。'
  } finally {
    if (request === epoch) busy.value = false
  }
}
function clearDetail() {
  detailRequest++
  detailOpen.value = false
  detail.value = null
}
async function showDetail(row: External) {
  const request = ++detailRequest
  const revision = epoch
  try {
    const {data} = await http.get<Detail>('/integration/v1/records/' + row.id, {
      params: {patient_id: props.patientId},
    })
    if (revision !== epoch || request !== detailRequest) return
    detail.value = {...row, ...data}
    detailOpen.value = true
  } catch (err) {
    if (revision === epoch && request === detailRequest) notifyError(err, '无法查看同步记录。')
  }
}
const rawRecord = computed(() => {
  const record = detail.value?.payload.record
  return record && typeof record === 'object' && !Array.isArray(record) ? record as Record<string, unknown> : {}
})
const task = computed(() => ['task_id', 'task_code', 'training_id', 'exercise_type']
  .map(key => rawRecord.value[key]).find(value => typeof value === 'string' && value))
const recordStatus = computed(() => {
  const status = rawRecord.value.status
  if (typeof status !== 'string') return ''
  return ({COMPLETED:'已完成', EXITED:'已退出', RECOVERED_INTERRUPTED:'中断后恢复'} as Record<string,string>)[status] ?? status
})
watch(() => props.patientId, () => { history.value = null; clearDetail(); void load(true) }, {immediate:true})
watch([view, day], () => { history.value = null; clearDetail(); void load(true) })
function changeHistory(row: External | null) {
  history.value = row; clearDetail(); void load(true)
}
</script>

<template>
  <section class="pd-card external-panel">
    <header class="external-panel__header">
      <h2>软件端同步记录</h2>
      <el-button :loading="busy" @click="load(true)">刷新</el-button>
    </header>
    <div class="external-panel__toolbar">
      <el-radio-group v-model="view" aria-label="软件端记录分类">
        <el-radio-button value="activity">训练记录</el-radio-button>
        <el-radio-button value="plans">训练计划</el-radio-button>
      </el-radio-group>
      <label v-if="view === 'plans'">进度日期 <input v-model="day" required type="date" @blur="!day && (day = new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Shanghai'}).format(new Date()))" /></label>
      <el-button v-if="history" @click="changeHistory(null)">返回计划列表</el-button>
    </div>
    <el-alert v-if="refreshFailed && !error" title="自动刷新失败，暂显示上次记录。" type="warning" :closable="false"/>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
    <div v-if="!rows.length && !busy && !error" class="pd-empty">暂无同步记录</div>
    <el-table v-else v-loading="busy" :data="rows" row-key="id" style="width:100%">
      <el-table-column :label="view === 'plans' ? '计划' : '来源项目'" min-width="155">
        <template #default="{row}">{{ row.title || kinds[row.record_type] || row.record_type }}</template>
      </el-table-column>
      <el-table-column v-if="view === 'plans'" label="计划开始日期" min-width="125"><template #default="{row}">{{ row.plan_start || '未记录' }}</template></el-table-column>
      <el-table-column v-else label="训练发生时间" min-width="165"><template #default="{row}">{{ timestamp(row.captured_at_ms) }}</template></el-table-column>
      <el-table-column v-if="view === 'plans'" label="当日进度" min-width="116"><template #default="{row}">{{ progressText(row) }}</template></el-table-column>
      <el-table-column label="同步时间（北京时间）" min-width="175"><template #default="{row}">{{ timestamp(row.received_at) }}</template></el-table-column>
      <el-table-column v-if="view === 'plans'" label="版本顺序" min-width="132">
        <template #default="{row}">{{ row.version_order === 'source_revision' ? '修订 ' + row.snapshot_revision : history ? '无修订号' : '最近收到' }}</template>
      </el-table-column>
      <el-table-column v-else label="任务 / 指标版本" min-width="170">
        <template #default="{row}">{{ row.task_version || '未记录' }} / {{ row.metric_version || '未记录' }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="132">
        <template #default="{row}">
          <el-button link type="primary" @click="showDetail(row)">详情</el-button>
          <el-button v-if="view === 'plans' && !history && row.version_count > 1" link type="primary" @click="changeHistory(row)">版本历史</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-button v-if="nextOffset !== null" :loading="busy" @click="load()">加载更多</el-button>
    <el-dialog v-model="detailOpen" title="软件端记录详情" width="min(92vw, 800px)">
      <dl v-if="detail" class="external-panel__summary">
        <dt>项目</dt><dd>{{ detail.title || kinds[detail.record_type] || detail.record_type }}</dd>
        <template v-if="detail.record_type === 'TRAINING_PLAN'">
          <dt>计划开始日期</dt><dd>{{ detail.plan_start || '未记录' }}</dd>
          <dt>{{ day }} 进度</dt><dd>{{ progressText(detail) }}</dd>
        </template>
        <template v-else><dt>训练发生时间</dt><dd>{{ timestamp(detail.captured_at_ms) }}</dd></template>
        <template v-if="task"><dt>任务</dt><dd>{{ task }}</dd></template>
        <template v-if="recordStatus"><dt>状态</dt><dd>{{ recordStatus }}</dd></template>
        <dt>同步时间</dt><dd>{{ timestamp(detail.received_at) }}</dd>
        <dt>任务 / 指标版本</dt><dd>{{ detail.task_version || '未记录' }} / {{ detail.metric_version || '未记录' }}</dd>
        <dt>来源 / 记录编号</dt><dd>{{ detail.origin }} · {{ detail.source_record_id }}</dd>
      </dl>
      <TrainingFaceRecordings v-if="detailOpen && detail && ['PIANO_SESSION', 'PIECE_PERFORMANCE', 'DANCE_SESSION'].includes(detail.record_type)" :key="detail.id" :record-id="detail.id"/>
      <details v-if="detail" :key="detail.id">
        <summary>查看原始 JSON</summary>
        <pre class="external-panel__json">{{ JSON.stringify(detail.payload, null, 2) }}</pre>
      </details>
    </el-dialog>
  </section>
</template>
<style scoped>
.external-panel{padding:24px;margin-top:18px;min-width:0}
.external-panel__header,.external-panel__toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-bottom:16px}
.external-panel__header{justify-content:space-between}
.external-panel h2{font-size:18px;margin:0}
.external-panel__toolbar input{font:inherit;color:inherit;padding:5px;border:1px solid var(--el-border-color);border-radius:5px}
.external-panel__summary{display:grid;grid-template-columns:minmax(90px,auto) minmax(0,1fr);gap:8px 14px;margin:0 0 16px}
.external-panel__summary dd{margin:0;overflow-wrap:anywhere}
.external-panel__json{max-height:55vh;white-space:pre-wrap;overflow:auto;background:#f5f7fa;border-radius:12px;padding:14px;font-size:12px;overflow-wrap:anywhere}
@media(max-width:600px){.external-panel{padding:12px}}
</style>
