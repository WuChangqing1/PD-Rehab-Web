<script setup lang="ts">
import { ref, watch } from 'vue'
import { http, notifyError } from '@/api/client'

const props = defineProps<{patientId: string}>()
type External = {
  id: string; record_type: string; source_record_id: string; schema_version: string;
  task_version: string | null; metric_version: string | null; created_at: string;
  captured_at_ms: number | null; origin: string; payload_sha256: string;
}
const rows = ref<External[]>([])
const busy = ref(false)
const error = ref('')
const currentOffset = ref(0)
const more = ref(false)
const detail = ref<Record<string, unknown> | null>(null)
const detailOpen = ref(false)
let epoch = 0
const kinds: Record<string,string> = {
  PIANO_SESSION:'软件钢琴练习', PIECE_PERFORMANCE:'软件曲目演奏',
  DANCE_SESSION:'软件舞蹈练习', TRAINING_PLAN:'软件训练计划',
  TRAINING_PLAN_EVENT:'软件计划执行记录', OTHER:'其他软件记录',
}
function timestamp(ms: number | null): string {
  return ms == null ? '时间未记录' : new Date(ms).toLocaleString('zh-CN')
}
async function load(reset = false) {
  const request = ++epoch
  if (reset) { rows.value = []; currentOffset.value = 0 }
  busy.value = true; error.value = ''
  try {
    const { data } = await http.get<{items: External[]; next_offset: number | null}>('/integration/v1/records', {
      params: { patient_id: props.patientId, offset: currentOffset.value, limit: 30 },
    })
    if (request !== epoch) return
    rows.value = reset ? data.items : [...rows.value, ...data.items]
    more.value = data.next_offset !== null
    currentOffset.value = data.next_offset ?? 0
  } catch (err) {
    if (request === epoch) error.value = '软件端记录读取失败，请检查网络并重试。'
  } finally {
    if (request === epoch) busy.value = false
  }
}
async function showDetail(row: External) {
  const patient=props.patientId, revision=epoch
  try {
    // Avoid exposing another patient's source record in a shared results view.
    const {data} = await http.get<External & {payload: Record<string, unknown>}>(`/integration/v1/records/${row.id}`, {
      params: { patient_id: props.patientId },
    })
    if(patient!==props.patientId || revision!==epoch)return
    detail.value = data.payload
    detailOpen.value = true
  } catch (err) { notifyError(err, '无法查看同步的原始记录。') }
}
watch(() => props.patientId, () => {detail.value=null;detailOpen.value=false;void load(true)}, {immediate:true})
</script>
<template>
  <section class="pd-card external-panel">
    <header class="external-panel__header">
      <div><h2>软件端同步记录</h2><p>来源于 PianoForParkinson 软件，保留原始记录和指标版本。跨端算法指标未验证一致前不直接混合统计。</p></div>
      <el-button :loading="busy" @click="load(true)">刷新</el-button>
    </header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
    <div v-if="!rows.length && !busy" class="pd-empty">此患者尚无软件端同步记录</div>
    <el-table v-else v-loading="busy" :data="rows" style="width:100%">
      <el-table-column label="来源项目" min-width="154"><template #default="{row}">{{ kinds[row.record_type] ?? row.record_type }}</template></el-table-column>
      <el-table-column label="记录时间" min-width="175"><template #default="{row}">{{ timestamp(row.captured_at_ms) }}</template></el-table-column>
      <el-table-column label="任务版本" min-width="120"><template #default="{row}">{{ row.task_version ?? '—' }}</template></el-table-column>
      <el-table-column label="指标版本" min-width="120"><template #default="{row}">{{ row.metric_version ?? '—' }}</template></el-table-column>
      <el-table-column label="操作" width="100"><template #default="{row}"><el-button link type="primary" @click="showDetail(row)">查看原始记录</el-button></template></el-table-column>
    </el-table>
    <el-button v-if="more" :loading="busy" @click="load()">加载更多</el-button>
    <el-dialog v-model="detailOpen" title="软件原始训练记录" width="min(92vw, 800px)">
      <p>此数据保留软件原始字段；与 Web 指标的比较需经过统一算法版本和单位验证。</p>
      <pre class="external-panel__json">{{ JSON.stringify(detail, null, 2) }}</pre>
    </el-dialog>
  </section>
</template>
<style scoped>
.external-panel{padding:24px;margin-top:18px;min-width:0}
.external-panel__header{display:flex;gap:16px;align-items:center;justify-content:space-between;margin-bottom:18px}
.external-panel h2{font-size:18px;margin:0 0 6px}
.external-panel p{font-size:13px;color:var(--pd-text-secondary);margin:0;line-height:1.5}
.external-panel__json{max-height:55vh;white-space:pre-wrap;overflow:auto;background:#f5f7fa;border-radius:12px;padding:14px;font-size:12px;overflow-wrap:anywhere}
@media(max-width:600px){.external-panel{padding:12px}.external-panel__header{align-items:flex-start;flex-direction:column}}
</style>
