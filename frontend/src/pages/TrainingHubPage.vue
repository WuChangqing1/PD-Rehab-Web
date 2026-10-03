<script setup lang="ts">
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

import PatientSelector from '@/components/PatientSelector.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import { pianoApi } from '@/api'
import { usePatientContextStore } from '@/stores/patientContext'
import type { Patient, PianoCalibrationBaseline } from '@/types'
import { formatDateTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patient = ref<Patient | null>(null)
const baseline = ref<PianoCalibrationBaseline | null>(null)

const patientId = computed(() => patient.value?.id ?? null)
const hasBaseline = computed(() => baseline.value !== null)

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

function open(name: 'training-piano' | 'training-movement') {
  router.push({ name, query: { patientId: patientId.value ?? '' } })
}

onMounted(async () => {
  const fromQuery = route.query.patientId
  if (typeof fromQuery === 'string' && fromQuery) await usePatient(fromQuery)
})
</script>

<template>
  <div class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">康复训练</h1>
        <p class="pd-page-subtitle">
          先选择患者，再选择训练方式。每次训练都会保存原始数据与客观指标。
        </p>
      </div>
    </div>

    <SelectedPatientBar v-if="patient" :patient="patient" @change="patient = null" />

    <PatientSelector
      v-if="!patient"
      title="选择患者"
      description="搜索姓名或患者编号，选择后即可开始训练。"
      @select="(p) => usePatient(p.id)"
    />

    <template v-else>
      <div class="training-grid">
        <div class="training-card">
          <div class="training-head">
            <strong>钢琴 / 节奏训练</strong>
            <el-tag
              :type="hasBaseline ? 'success' : 'warning'"
              size="small"
              class="training-tag"
            >
              基础能力测试{{ hasBaseline ? '已完成' : '未完成' }}
            </el-tag>
          </div>
          <p class="pd-secondary">
            精细运动与节拍同步训练。首次进入需要先做一次约 45 秒的基础能力测试，
            用来设置适合患者的训练节奏；之后按轮次自动调整难度。
          </p>
          <p class="training-meta">
            <template v-if="hasBaseline">上次基础能力测试：{{ formatDateTime(baseline?.created_at) }}</template>
            <template v-else>尚未完成基础能力测试（约 45 秒）。</template>
          </p>
          <el-button type="primary" class="pd-big-action" @click="open('training-piano')">
            进入钢琴训练
          </el-button>
        </div>

        <div class="training-card">
          <div class="training-head">
            <strong>芭蕾动作训练</strong>
            <el-tag type="info" size="small" class="training-tag">5 个动作</el-tag>
          </div>
          <p class="pd-secondary">
            坐姿或站姿扶椅完成五个芭蕾动作，带节拍与口令提示，
            用摄像头录制或上传视频后由系统分析活动范围、完成次数与稳定性。
          </p>
          <p class="training-meta">可以先跟一遍节拍再录，分析在服务端完成。</p>
          <el-button type="primary" class="pd-big-action" @click="open('training-movement')">
            进入芭蕾动作训练
          </el-button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.training-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(320px, 100%), 1fr));
  gap: 16px;
}

.training-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px;
  background: var(--pd-surface);
  border: 1px solid var(--pd-border);
  border-radius: 10px;
}

/*
  The cards stretch to a shared height, so the call to action has to be pinned
  to the bottom. Without this the button follows the text and the two cards end
  up with their buttons 48px apart whenever one description runs longer.
*/
.training-card .pd-big-action {
  margin-top: auto;
  align-self: stretch;
}

/* Reserve one line for the meta row so both cards keep the same rhythm. */
.training-meta {
  margin: 0;
  min-height: 18px;
  color: var(--pd-text-muted);
  font-size: 12px;
}

.training-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 27px;
  font-size: 17px;
}

.training-head strong {
  min-width: 0;
}

.training-tag {
  flex: none;
}
</style>
