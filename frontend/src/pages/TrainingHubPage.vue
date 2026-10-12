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

import TrainingArtwork from '@/components/TrainingArtwork.vue'
import { ArrowRight, Check, Headset, Timer } from '@element-plus/icons-vue'
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
    <div class="pd-page-header">
      <div>
        <span class="pd-eyebrow">REHABILITATION</span>
        <h1 class="pd-page-title">让每一次练习，都有节奏</h1>
        <p class="pd-page-subtitle">
          选择适合的训练，从手指协调到身体控制，循序渐进。
        </p>
      </div>
      <span class="pd-context-tag"><el-icon><Check /></el-icon>先浏览练习，开始时选择患者</span>
    </div>

    <SelectedPatientBar v-if="patient" :patient="patient" @change="clearPatient" />

    <div class="training-section-heading"><h2>康复训练</h2><span>两种训练方式 · 按患者能力调整</span></div>
      <div class="training-grid">
        <div class="training-card">
          <TrainingArtwork kind="piano" />
          <div class="training-card-body">
          <div class="training-card-heading"><span class="pd-step-number">01</span><span class="pd-pill">精细运动</span></div>
          <div class="training-head">
            <strong>钢琴节奏训练</strong>
            <el-tag
              v-if="patient"
              :type="hasBaseline ? 'success' : 'warning'"
              size="small"
              class="training-tag"
            >
              基础能力测试{{ hasBaseline ? '已完成' : '未完成' }}
            </el-tag>
          </div>
          <p class="training-english">Piano rhythm training</p>
          <p class="pd-secondary">
            精细运动与节拍同步训练。首次进入需要先做一次约 45 秒的基础能力测试，
            用来设置适合患者的训练节奏；之后按轮次自动调整难度。
          </p>
          <p v-if="patient" class="training-meta">
            <template v-if="hasBaseline">上次基础能力测试：{{ formatDateTime(baseline?.created_at) }}</template>
            <template v-else>尚未完成基础能力测试（约 45 秒）。</template>
          </p>
          <div class="training-facts"><span><el-icon><Headset /></el-icon>可试听琴键</span><span><el-icon><Timer /></el-icon>三轮自适应训练</span></div>
          <router-link class="pd-primary-link" :to="{ name: 'training-piano', query: patientId ? { patientId } : {} }">进入钢琴训练<el-icon><ArrowRight /></el-icon></router-link>
          </div>
        </div>

        <div class="training-card">
          <TrainingArtwork kind="ballet" />
          <div class="training-card-body">
          <div class="training-card-heading"><span class="pd-step-number">02</span><span class="pd-pill is-teal">身体控制</span></div>
          <div class="training-head">
            <strong>芭蕾动作训练</strong>
          </div>
          <p class="training-english">Ballet movement training</p>
          <p class="pd-secondary">
            坐姿或站姿扶椅完成五个芭蕾动作，带节拍与口令提示，
            用摄像头录制或上传视频后由系统分析活动范围、完成次数与稳定性。
          </p>
          <div class="training-facts"><span>5 个分解动作</span><span>坐姿 / 站姿扶椅</span></div>
          <router-link class="pd-primary-link is-teal" :to="{ name: 'training-movement', query: patientId ? { patientId } : {} }">进入芭蕾训练<el-icon><ArrowRight /></el-icon></router-link>
          </div>
        </div>
      </div>
    <div class="training-guide"><div><span class="pd-eyebrow">简单三步</span><h2>准备好，再开始</h2><p>浏览与试听无需选择患者。</p></div><ol><li><span>1</span><div><strong>挑选练习</strong><p>了解内容，调整训练方式</p></div></li><li><span>2</span><div><strong>确认患者</strong><p>开始时核实姓名与编号</p></div></li><li><span>3</span><div><strong>跟随节奏</strong><p>3 秒倒计时后，专注训练</p></div></li></ol></div>
  </div>
</template>

<style scoped>
.training-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.training-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0;
  overflow: hidden;
  background: var(--pd-surface);
  border: 1px solid var(--pd-border);
  border-radius: var(--pd-radius-card);
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
.training-section-heading { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin: 32px 0 16px; }
.training-section-heading h2 { font-size: 17px; margin: 0; }
.training-section-heading > span { font-size: 13px; color: var(--pd-text-secondary); }
.training-card-body { display: flex; flex: 1; flex-direction: column; padding: 24px 28px 28px; }
.training-card-heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.training-head { font-size: 24px; flex-wrap: wrap; }
.training-english { color: var(--pd-text-secondary); font-size: 13px; margin: 4px 0 0; }
.training-card-body > .pd-secondary { font-size: 14px; min-height: 4.8em; margin: 16px 0 0; }
.training-facts { display: flex; gap: 24px; flex-wrap: wrap; color: var(--pd-text-secondary); font-size: 13px; margin: 20px 0; }
.training-facts span { display: inline-flex; align-items: center; gap: 6px; }
.training-card .pd-primary-link { margin-top: auto; }
.training-guide { display: flex; gap: 40px; align-items: center; padding: 28px; background: #ecf1f6; border-radius: var(--pd-radius-card); margin-top: 28px; }
.training-guide h2 { margin: 6px 0; font-size: 20px; }
.training-guide p { font-size: 13px; color: var(--pd-text-secondary); margin: 0; }
.training-guide ol { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 28px; list-style: none; margin: 0; padding: 0; flex: 1; }
.training-guide li { display: flex; gap: 12px; }
.training-guide li > span { display: grid; place-items: center; flex: none; width: 30px; height: 30px; background: white; border-radius: 50%; font-size: 13px; color: var(--pd-primary); }
.training-guide strong { font-size: 14px; }
.training-guide li p { margin-top: 4px; }
@media (max-width: 1199px) { .training-guide { flex-direction: column; align-items: stretch; gap: 20px; } }
@media (max-width: 767px) { .training-section-heading { align-items: flex-start; flex-direction: column; gap: 4px; margin-top: 24px; } .training-card-body { padding: 20px; } .training-card-body > .pd-secondary { min-height: 0; } .training-guide { padding: 20px; } .training-guide ol { grid-template-columns: 1fr; gap: 20px; } }
</style>
