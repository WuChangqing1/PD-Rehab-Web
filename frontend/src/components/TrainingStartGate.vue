<script setup lang="ts">
import PatientSelector from '@/components/PatientSelector.vue'
import type { Patient } from '@/types'
import { displayHospitalNumber, displayPatientName } from '@/utils/format'
defineProps<{ state: { phase: string; remaining: number; patient: Patient | null; error: string }; exercise: string }>()
defineEmits<{ select: [patient: Patient]; cancel: []; change: [] }>()
</script>

<template>
  <el-dialog
    :model-value="state.phase === 'picking'"
    title="选择本次训练患者"
    class="training-picker"
    width="680px"
    align-center
    destroy-on-close
    :before-close="() => $emit('cancel')"
  >
    <PatientSelector title="患者资料" description="选择后将保留当前练习设置，并自动继续准备训练。" @select="$emit('select', $event)" />
  </el-dialog>
  <el-dialog
    :model-value="state.phase === 'preparing' || state.phase === 'countdown'"
    class="training-countdown"
    title="准备训练"
    width="520px"
    align-center
    :show-close="false"
    :close-on-click-modal="false"
    :before-close="() => $emit('cancel')"
  >
    <div class="training-countdown__content" role="status" aria-live="polite">
      <span class="pd-eyebrow">准备训练</span>
      <h2>{{ exercise }}</h2>
      <p v-if="state.patient" class="training-identity">
        <strong>{{ displayPatientName(state.patient.name) }}</strong>
        <span>患者编号 {{ displayHospitalNumber(state.patient.hospital_number) }}</span>
      </p>
      <p v-else class="pd-secondary">正在核实患者资料…</p>
      <div v-if="state.phase === 'countdown'" :key="`countdown-${state.remaining}`" class="training-countdown__number">{{ state.remaining }}</div>
      <div v-else class="training-preparing"><span class="training-preparing__dot" />正在准备，请稍候…</div>
      <p class="pd-secondary">{{ state.phase === 'countdown' ? '放松双肩，跟随节奏。' : '准备完成后将自动开始 3 秒倒计时。' }}</p>
      <div class="training-countdown__actions">
        <el-button size="large" @click="$emit('cancel')">取消启动</el-button>
        <el-button size="large" @click="$emit('change')">更换患者</el-button>
      </div>
    </div>
  </el-dialog>
</template>
