<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { assessmentApi, patientApi } from '@/api'
import { notifyError } from '@/api/client'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import type { AssessmentSessionDetail, Patient } from '@/types'
import { formatDateTime, SESSION_STATUS_LABELS } from '@/utils/format'

const route = useRoute(), router = useRouter()
const session = ref<AssessmentSessionDetail|null>(null), patient = ref<Patient|null>(null)
const readiness = ref<Awaited<ReturnType<typeof assessmentApi.readiness>>|null>(null)
const loading = ref(false), saving = ref(false), error = ref('')
let generation = 0
const steps = computed(() => readiness.value?.items ?? [])
const editable = computed(() => session.value?.status === 'IN_PROGRESS')
async function load() {
  const current = ++generation
  loading.value = true; session.value = null; patient.value = null; readiness.value = null; error.value = ''
  try {
    const record = await assessmentApi.getSession(String(route.params.sessionId))
    if (route.query.patientId && route.query.patientId !== record.patient_id) throw new Error('患者与评估记录不一致。')
    if (record.session_type !== 'COMPREHENSIVE') throw new Error('这不是综合评估记录。')
    const [person, state] = await Promise.all([patientApi.get(record.patient_id), assessmentApi.readiness(record.id)])
    if (current !== generation) return
    session.value = record; patient.value = person; readiness.value = state
  } catch (e) { if (current === generation) error.value = e instanceof Error ? e.message : '无法读取评估记录。' }
  finally { if (current === generation) loading.value = false }
}
function openStep(key: string) {
  if (!session.value || !editable.value || saving.value) return
  router.push({ name: key === 'micro_expression' ? 'assessment-micro-expression' : 'assessment-finger-tapping',
    query: { patientId: session.value.patient_id, sessionId: session.value.id,
      ...(key === 'finger_tapping_right' ? { hand: 'RIGHT' } : key === 'finger_tapping_left' ? { hand: 'LEFT' } : {}) } })
}
function results() {
  if (session.value) router.push({ name: 'assessment-results', params: { sessionId: session.value.id }, query: { patientId: session.value.patient_id } })
}
async function finish() {
  if (!session.value || !editable.value || !readiness.value?.can_complete || saving.value) return
  saving.value = true
  try { await assessmentApi.completeSession(session.value.id); results() }
  catch (e) { notifyError(e, '无法完成评估，请刷新检查各项结果。'); await load() }
  finally { saving.value = false }
}
watch(() => [route.params.sessionId, route.query.patientId], load, { immediate: true })
</script>

<template>
  <div class="pd-page" v-loading="loading">
    <router-link class="pd-back" :to="{name:'assessment',query:{patientId:session?.patient_id}}">{{ $t("← 返回评估中心") }}</router-link>
    <div class="pd-page-header"><div><h1 class="pd-page-title">{{ $t("综合评估") }}</h1></div></div>
    <el-alert v-if="error" :title="$t(error)" type="error" :closable="false" />
    <template v-if="session && patient">
      <SelectedPatientBar :patient="patient" :allow-change="false" />
      <div class="workflow-meta">{{ $t(formatDateTime(session.started_at)) }} · {{ $t(SESSION_STATUS_LABELS[session.status]) }}</div>
      <div class="workflow-grid">
        <section v-for="(step,index) in steps" :key="step.key" class="pd-card workflow-step">
          <span class="step-number">{{ $t(index+1) }}</span><h2>{{ $t(step.label) }}</h2>

          <el-button v-if="editable && (step.state==='PENDING' || (step.key==='micro_expression' && step.state==='SKIPPED_MODEL_UNAVAILABLE'))" type="primary" :disabled="saving" @click="openStep(step.key)">{{ $t(`开始${$t(step.label)}`) }}</el-button>
          <el-button v-else-if="step.state==='COMPLETED'" @click="results">{{ $t("查看已保存结果") }}</el-button>
        </section>
      </div>
      <div class="workflow-footer pd-card">
        <div><strong>{{ $t("本次评估汇总") }}</strong></div>
        <div class="workflow-actions"><el-button @click="results">{{ $t("查看本次结果") }}</el-button><el-button v-if="editable" type="primary" :disabled="!readiness?.can_complete" :loading="saving" @click="finish">{{ $t("完成综合评估") }}</el-button></div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.workflow-meta{margin:20px 0;color:var(--pd-text-secondary)}
.workflow-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.workflow-step{padding:24px;display:flex;flex-direction:column;align-items:flex-start;gap:16px}
.workflow-grid > .workflow-step + .workflow-step{margin-top:0}
.workflow-step h2{font-size:20px;margin:0}.workflow-step p{line-height:1.7;flex:1;margin:0;color:var(--pd-text-secondary)}
.step-number{background:#edf2ff;color:#4966bb;border-radius:50%;width:36px;height:36px;display:grid;place-items:center;font-weight:700}
.workflow-footer{margin-top:24px;padding:24px;display:flex;align-items:center;justify-content:space-between;gap:20px}.workflow-footer p{margin:8px 0 0;color:var(--pd-text-secondary)}.workflow-actions{display:flex;gap:12px;flex-wrap:wrap}.workflow-actions .el-button{margin:0;width:176px;height:48px;min-height:48px;padding:12px 20px;box-sizing:border-box}
@media(max-width:900px){.workflow-grid{grid-template-columns:1fr}.workflow-footer{align-items:flex-start;flex-direction:column}}
</style>
