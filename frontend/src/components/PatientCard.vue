<script setup lang="ts">
/**
 * One patient, as a card.
 *
 * Shown instead of the table row below 768px. A patient list on a phone cannot
 * be a twelve-column table: either it is squeezed until nothing is readable or
 * it scrolls sideways, and neither is usable one-handed in a ward. The card
 * carries the six facts the list is actually read for, and the two actions that
 * are actually taken from it.
 *
 * It renders the SAME row object the table renders -- there is no second query
 * and no second data shape, only a second presentation.
 */
import { Edit, View } from '@element-plus/icons-vue'

import type { PatientListItem } from '@/types'
import {
  AFFECTED_SIDE_LABELS,
  MEDICATION_LABELS,
  SEX_LABELS,
  displayHospitalNumber,
  displayPatientName,
  medicationTagType,
} from '@/utils/format'

const props = defineProps<{ patient: PatientListItem }>()

const emit = defineEmits<{
  (e: 'open'): void
  (e: 'edit'): void
}>()

function ageLabel(age: number | null | undefined): string {
  return age === null || age === undefined ? '年龄暂无' : `${age}岁`
}

function sexLabel(sex: string): string {
  return SEX_LABELS[sex] ?? sex
}

function sideLabel(side: string): string {
  return AFFECTED_SIDE_LABELS[side] ?? side
}

function medicationLabel(state: string): string {
  return MEDICATION_LABELS[state] ?? state
}

// Kept as a function so the template can call it without importing the map.
function tagType(state: string) {
  return medicationTagType(state)
}

defineExpose({ props })
</script>

<template>
  <article class="patient-card" :class="{ 'is-deleted': patient.is_deleted }">
    <header class="patient-card-head">
      <strong class="patient-card-name">{{ displayPatientName(patient.name) }}</strong>
      <span class="patient-card-number">{{ displayHospitalNumber(patient.hospital_number) }}</span>
    </header>

    <dl class="patient-card-facts">
      <div>
        <dt>性别 / 年龄</dt>
        <dd>{{ sexLabel(patient.sex) }} · {{ ageLabel(patient.age) }}</dd>
      </div>
      <div>
        <dt>主要受累侧</dt>
        <dd>{{ sideLabel(patient.affected_side) }}</dd>
      </div>
      <div>
        <dt>用药状态</dt>
        <dd>
          <el-tag :type="tagType(patient.medication_state)" size="small">
            {{ medicationLabel(patient.medication_state) }}
          </el-tag>
        </dd>
      </div>
      <div v-if="patient.is_deleted">
        <dt>状态</dt>
        <dd><el-tag type="info" size="small">已删除</el-tag></dd>
      </div>
    </dl>

    <footer class="patient-card-actions">
      <el-button :icon="View" @click="emit('open')">查看资料</el-button>
      <el-button :icon="Edit" @click="emit('edit')">编辑</el-button>
    </footer>
  </article>
</template>

<style scoped>
.patient-card {
  padding: 14px;
  background: var(--pd-surface);
  border: 1px solid var(--pd-border);
  border-radius: var(--pd-radius);
}

.patient-card + .patient-card {
  margin-top: 10px;
}

.patient-card.is-deleted {
  opacity: 0.7;
}

.patient-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--pd-border);
}

.patient-card-name {
  font-size: 17px;
}

.patient-card-number {
  font-size: 13px;
  color: var(--pd-text-muted);
  font-variant-numeric: tabular-nums;
}

.patient-card-facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
  margin: 12px 0;
}

.patient-card-facts > div {
  min-width: 0;
}

.patient-card-facts dt {
  font-size: 12px;
  color: var(--pd-text-muted);
}

.patient-card-facts dd {
  margin: 2px 0 0;
  font-size: 15px;
}

.patient-card-actions {
  display: flex;
  gap: 10px;
}

.patient-card-actions .el-button {
  flex: 1;
  min-height: var(--pd-touch);
  margin-left: 0;
}
</style>
