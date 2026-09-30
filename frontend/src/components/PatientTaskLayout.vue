<script setup lang="ts">
/**
 * Patient operating mode.
 *
 * Once a doctor has chosen the function and the patient, the patient is the one
 * using the screen. The workspace navigation, patient editing and admin surfaces
 * are noise at that moment, so this layout drops them and keeps only what the
 * person in front of the screen needs: who this is for, what they are doing, and
 * the way out.
 *
 * Larger type and taller controls than the clinical pages: this is a
 * rehabilitation task, often performed by someone with tremor or reduced vision.
 */
import { computed } from 'vue'
import { Back, User } from '@element-plus/icons-vue'

import type { Patient } from '@/types'

const props = withDefaults(
  defineProps<{
    patient: Patient | null
    /** What the patient is doing, e.g. "钢琴节奏训练". */
    task: string
    /** Optional one-line instruction shown under the task name. */
    instruction?: string
  }>(),
  { instruction: '' },
)

const emit = defineEmits<{
  (e: 'exit'): void
}>()

const identity = computed(() => {
  const p = props.patient
  if (!p) return ''
  return `${p.name} · ${p.hospital_number}`
})
</script>

<template>
  <div class="focus-shell">
    <header class="focus-header">
      <el-button :icon="Back" size="large" @click="emit('exit')">退出</el-button>

      <div class="focus-identity">
        <el-icon><User /></el-icon>
        <span class="focus-name">{{ identity || '未选择患者' }}</span>
      </div>

      <div class="focus-task">
        <strong>{{ task }}</strong>
        <span v-if="instruction" class="focus-instruction">{{ instruction }}</span>
      </div>
    </header>

    <main class="focus-main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.focus-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--pd-bg);
  /* Patient mode raises the base size: 12px must never carry something the
     patient has to read to complete the task. */
  font-size: 16px;
  line-height: 1.6;
}

.focus-header {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 20px;
  background: var(--pd-surface);
  border-bottom: 1px solid var(--pd-border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.focus-identity {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
}

.focus-task {
  display: flex;
  flex-direction: column;
  margin-left: auto;
  text-align: right;
}

.focus-task strong {
  font-size: 18px;
}

.focus-instruction {
  font-size: 14px;
  color: var(--pd-text-secondary);
}

.focus-main {
  flex: 1;
  width: 100%;
  max-width: 1080px;
  margin: 0 auto;
  padding: 20px;
}

/* Patient-facing controls are bigger than the clinical default. */
.focus-main :deep(.el-button) {
  min-height: 44px;
  font-size: 16px;
}

.focus-main :deep(.el-button--large),
.focus-main :deep(.pd-big-action) {
  min-height: 48px;
  font-size: 17px;
}

.focus-main :deep(.el-card__body),
.focus-main :deep(.pd-card-body) {
  font-size: 16px;
}
</style>
