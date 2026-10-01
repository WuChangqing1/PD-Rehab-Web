<script setup lang="ts">
/**
 * The bar that says whose data this is.
 *
 * Fixed at the top of every page that produces or shows patient data. Patient
 * identity must never be reachable only through the URL: that is how a doctor
 * ends up recording the wrong hand.
 *
 * Switching patient mid-task is confirmed first, because the alternative is
 * silently discarding collected data or, worse, attributing it to someone else.
 */
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Refresh, User } from '@element-plus/icons-vue'

import type { Patient } from '@/types'
import {
  AFFECTED_SIDE_LABELS,
  MEDICATION_LABELS,
  SEX_LABELS,
  medicationTagType,
  displayPatientName,
  displayHospitalNumber,
} from '@/utils/format'

const props = withDefaults(
  defineProps<{
    patient: Patient | null
    /** True while unsaved results exist; switching patient then needs a confirm. */
    hasUnsavedWork?: boolean
    /** What is being done, shown so a long session stays identifiable. */
    taskLabel?: string
  }>(),
  { hasUnsavedWork: false, taskLabel: '' },
)

const emit = defineEmits<{
  (e: 'change'): void
}>()

const summary = computed(() => {
  const p = props.patient
  if (!p) return ''
  const parts = [SEX_LABELS[p.sex] ?? p.sex]
  parts.push(p.age != null ? `${p.age}岁` : '年龄暂无')
  parts.push(`受累侧 ${AFFECTED_SIDE_LABELS[p.affected_side] ?? p.affected_side}`)
  return parts.join(' · ')
})

async function requestChange() {
  if (props.hasUnsavedWork) {
    try {
      await ElMessageBox.confirm(
        '当前任务的采集结果尚未保存，更换患者会丢失这些数据。确认更换？',
        '更换患者',
        { confirmButtonText: '放弃并更换', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  }
  emit('change')
}
</script>

<template>
  <div class="patient-bar" :class="{ 'is-empty': !patient }">
    <el-icon class="patient-bar-icon"><User /></el-icon>

    <template v-if="patient">
      <div class="patient-bar-main">
        <span class="pd-muted">当前患者</span>
        <strong class="patient-bar-name">{{ displayPatientName(patient.name) }}</strong>
        <span class="patient-bar-code">{{ displayHospitalNumber(patient.hospital_number) }}</span>
      </div>
      <div class="patient-bar-meta">
        <span>{{ summary }}</span>
        <el-tag :type="medicationTagType(patient.medication_state)" size="small">
          {{ MEDICATION_LABELS[patient.medication_state] ?? patient.medication_state }}
        </el-tag>
      </div>
    </template>

    <div v-else class="patient-bar-main">
      <span class="pd-muted">尚未选择患者</span>
    </div>

    <div class="patient-bar-right">
      <span v-if="taskLabel" class="pd-muted patient-bar-task">{{ taskLabel }}</span>
      <el-button :icon="Refresh" size="small" @click="requestChange">
        {{ patient ? '更换患者' : '选择患者' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.patient-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  margin-bottom: 16px;
  border: 1px solid var(--pd-border);
  border-left: 4px solid var(--pd-primary);
  border-radius: 8px;
  background: var(--pd-surface);
}

.patient-bar.is-empty {
  border-left-color: var(--el-color-warning);
}

.patient-bar-icon {
  font-size: 18px;
  color: var(--pd-primary);
}

.patient-bar-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.patient-bar-name {
  font-size: 16px;
}

.patient-bar-code {
  font-family: 'Cascadia Mono', Consolas, monospace;
  font-size: 13px;
  color: var(--pd-text-secondary);
}

.patient-bar-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--pd-text-secondary);
}

.patient-bar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.patient-bar-task {
  font-size: 12px;
}
</style>
