<script setup lang="ts">
import ActiveTrainingNotice from '@/components/ActiveTrainingNotice.vue'
/**
 * Rehabilitation training centre.
 *
 * Two choices, two cards. The page used to also carry the pose quality
 * thresholds, three algorithm version numbers and two history tables, which made
 * "start training" the smallest thing on a screen about starting training.
 * Thresholds belong to 系统设置, history to 随访与报告.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import TrainingArtwork from '@/components/TrainingArtwork.vue'
import { ArrowRight } from '@element-plus/icons-vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import { pianoApi } from '@/api'
import { usePatientContextStore } from '@/stores/patientContext'
import type { Patient, PianoCalibrationBaseline } from '@/types'

const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patient = ref<Patient | null>(null)
const baseline = ref<PianoCalibrationBaseline | null>(null)

const patientId = computed(() => patient.value?.id ?? null)

async function loadBaseline() {
  if (!patientId.value) return
  try {
    baseline.value = await pianoApi.baseline(patientId.value)
  } catch {
    // No baseline yet is a normal state, not an error: the piano page runs the
    // baseline test first.
    baseline.value = null
  }
}

async function usePatient(id: string) {
  patient.value = await store.resolve(id)
  if (patient.value) {
    // Keep the patient in the URL so the page survives a refresh and can be shared.
    router.replace({ query: { ...route.query, patientId: id } })
    await loadBaseline()
  }
}

onMounted(async () => {
  const fromQuery = route.query.patientId
  if (typeof fromQuery === 'string' && fromQuery) await usePatient(fromQuery)
})

function clearPatient() {
  patient.value = null
  baseline.value = null
  void store.select(null)
  const query = { ...route.query }
  delete query.patientId
  void router.replace({ query })
}
</script>

<template>
  <div class="pd-page">
    <div class="pd-page-header"><h1 class="pd-page-title">{{ $t("康复训练") }}</h1></div>
    <SelectedPatientBar v-if="patient" :patient="patient" @change="clearPatient" />
    <ActiveTrainingNotice :patient-id="patient?.id??null"/>

    <div class="training-grid">
      <article class="training-card">
        <TrainingArtwork kind="piano" />
        <div class="training-card-body">
          <span class="pd-pill">{{ $t("精细运动") }}</span>
          <h2>{{ $t("钢琴节奏训练") }}</h2>
          <router-link class="pd-primary-link" :to="{ name: 'training-piano', query: patientId ? { patientId } : {} }">{{ $t("浏览钢琴练习") }}<el-icon><ArrowRight /></el-icon></router-link>
        </div>
      </article>

      <article class="training-card">
        <TrainingArtwork kind="ballet" />
        <div class="training-card-body">
          <span class="pd-pill is-teal">{{ $t("身体控制") }}</span>
          <h2>{{ $t("芭蕾动作训练") }}</h2>
          <router-link class="pd-primary-link is-teal" :to="{ name: 'training-movement', query: patientId ? { patientId } : {} }">{{ $t("浏览芭蕾练习") }}<el-icon><ArrowRight /></el-icon></router-link>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.training-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: stretch; gap: 20px; }
.training-card { display: flex; flex-direction: column; min-width: 0; overflow: hidden; background: var(--pd-surface); border: 1px solid var(--pd-border); border-radius: var(--pd-radius-card); box-shadow: var(--pd-shadow); }
.training-card :deep(.training-art) { flex-shrink: 0; width: 100%; aspect-ratio: 7 / 3; }
.training-card-body { display: flex; flex: 1; flex-direction: column; min-width: 0; padding: 24px 28px 28px; }
.training-card-body > .pd-pill { align-self: flex-start; }
.training-card-body h2 { margin: 14px 0 0; font-size: 24px; line-height: 1.4; }
.training-description { min-height: 3.2em; margin: 12px 0 0; color: var(--pd-text-secondary); font-size: 14px; line-height: 1.6; }
.training-facts { display: flex; flex-wrap: wrap; gap: 8px 18px; color: var(--pd-text-secondary); font-size: 13px; margin: 18px 0 12px; }
.training-meta { display: flex; align-items: flex-start; flex-direction: column; gap: 6px; min-height: 50px; margin-bottom: 20px; color: var(--pd-text-muted); font-size: 12px; }
.training-card .pd-primary-link { margin-top: auto; }
@media (max-width: 767px) {
  .training-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .training-card-body { padding: 20px; }
  .training-card-body h2 { font-size: 22px; }
  .training-description, .training-meta { min-height: 0; }
}
</style>
