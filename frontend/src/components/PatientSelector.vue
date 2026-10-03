<script setup lang="ts">
/**
 * Pick the patient a task is about, without going through a patient page first.
 *
 * Task-first means the function comes before the patient: a doctor opens
 * "评估中心", then says who it is for. Search covers name and hospital number,
 * and the row shows the facts that decide how to run the task (age, affected
 * side, medication state).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'

import { patientApi } from '@/api'
import { notifyError } from '@/api/client'
import type { Patient, PatientListItem } from '@/types'
import { usePatientContextStore } from '@/stores/patientContext'
import {
  AFFECTED_SIDE_LABELS,
  displayPatientName,
  displayHospitalNumber,
  MEDICATION_LABELS,
  SEX_LABELS,
  medicationTagType,
} from '@/utils/format'

const props = withDefaults(
  defineProps<{
    /** Title above the search box. */
    title?: string
    description?: string
  }>(),
  {
    title: '选择患者',
    description: '搜索姓名或患者编号，选择后即可开始。',
  },
)

const emit = defineEmits<{
  (e: 'select', patient: Patient): void
}>()

const store = usePatientContextStore()

const query = ref('')
const rows = ref<PatientListItem[]>([])
const loading = ref(false)
const recent = ref<Patient[]>([])

const hasQuery = computed(() => query.value.trim().length > 0)

async function search() {
  loading.value = true
  try {
    const data = await patientApi.list({
      q: query.value.trim() || undefined,
      page: 1,
      page_size: 20,
    })
    rows.value = data.items
  } catch (error) {
    notifyError(error, '无法加载患者列表。')
  } finally {
    loading.value = false
  }
}

async function choose(id: string) {
  const patient = await store.select(id)
  if (!patient) {
    notifyError(null, '无法读取该患者资料，请重新选择。')
    return
  }
  emit('select', patient)
}

async function loadRecent() {
  // The recent list is a shortcut, never an automatic choice.
  for (const id of store.recentIds) {
    await store.fetchPatient(id)
  }
  recent.value = store.recentPatients()
}

onMounted(async () => {
  await loadRecent()
  await search()
})

watch(query, () => {
  // Debounced enough for a demo and a hospital-sized list; Enter searches now.
  window.clearTimeout(timer)
  timer = window.setTimeout(search, 250)
})
let timer = 0
</script>

<template>
  <div class="pd-card">
    <div class="pd-card-header">
      <span class="pd-card-title">{{ title }}</span>
    </div>
    <div class="pd-card-body">
      <p class="pd-secondary" style="margin-top: 0">{{ description }}</p>

      <el-input
        v-model="query"
        size="large"
        class="selector-search"
        placeholder="搜索姓名 / 患者编号 / 电话"
        clearable
        @keyup.enter="search"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <div v-if="recent.length && !hasQuery" class="recent">
        <span class="pd-muted selector-recent-label">最近使用</span>
        <el-button
          v-for="item in recent"
          :key="item.id"
          class="recent-chip"
          round
          @click="choose(item.id)"
        >
          {{ displayPatientName(item.name) }} · {{ displayHospitalNumber(item.hospital_number) }}
        </el-button>
      </div>

      <!-- Desktop: the whole row is readable, so a table is the right control. -->
      <div v-loading="loading" class="desktop-only pd-table-scroll" style="margin-top: 12px">
        <el-table
          :data="rows"
          size="small"
          empty-text="没有匹配的患者"
          @row-click="(row: PatientListItem) => choose(row.id)"
        >
          <el-table-column label="姓名" min-width="110">
            <template #default="{ row }">
              <strong>{{ displayPatientName(row.name) }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="患者编号" width="110">
            <template #default="{ row }">{{ displayHospitalNumber(row.hospital_number) }}</template>
          </el-table-column>
          <el-table-column label="性别 / 年龄" width="110">
            <template #default="{ row }">
              {{ SEX_LABELS[row.sex] ?? row.sex }} /
              {{ row.age != null ? `${row.age}岁` : '年龄暂无' }}
            </template>
          </el-table-column>
          <el-table-column label="主要受累侧" width="110">
            <template #default="{ row }">
              {{ AFFECTED_SIDE_LABELS[row.affected_side] ?? row.affected_side }}
            </template>
          </el-table-column>
          <el-table-column label="用药状态" width="100">
            <template #default="{ row }">
              <el-tag :type="medicationTagType(row.medication_state)" size="small">
                {{ MEDICATION_LABELS[row.medication_state] ?? row.medication_state }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="right">
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                :disabled="row.is_deleted"
                @click.stop="choose(row.id)"
              >
                选择
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!--
        Mobile: one tap target per patient rather than a table squeezed into
        375px. The entire row is the button, which is what a thumb expects.
      -->
      <div v-loading="loading" class="mobile-only selector-cards">
        <p v-if="!rows.length" class="pd-empty">没有匹配的患者</p>
        <button
          v-for="row in rows"
          :key="row.id"
          type="button"
          class="selector-card"
          :disabled="row.is_deleted"
          @click="choose(row.id)"
        >
          <span class="selector-card-top">
            <strong>{{ displayPatientName(row.name) }}</strong>
            <span class="selector-card-number">
              {{ displayHospitalNumber(row.hospital_number) }}
            </span>
          </span>
          <span class="selector-card-meta">
            {{ SEX_LABELS[row.sex] ?? row.sex }} ·
            {{ row.age != null ? `${row.age}岁` : '年龄暂无' }} ·
            {{ AFFECTED_SIDE_LABELS[row.affected_side] ?? row.affected_side }}
          </span>
          <span class="selector-card-meta">
            <el-tag :type="medicationTagType(row.medication_state)" size="small">
              {{ MEDICATION_LABELS[row.medication_state] ?? row.medication_state }}
            </el-tag>
            <el-tag v-if="row.is_deleted" type="info" size="small">已删除</el-tag>
          </span>
        </button>
      </div>

      <p class="pd-muted" style="font-size: 12px; margin: 10px 0 0">
        找不到患者？请先到「患者档案」新增。已删除的患者不会出现在这里。
      </p>
    </div>
  </div>
</template>

<style scoped>
.recent {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.recent-chip {
  min-height: 34px;
}

:deep(.el-table__row) {
  cursor: pointer;
}

/* -------------------------------------------------------------- mobile list */

.selector-search :deep(.el-input__wrapper) {
  min-height: var(--pd-touch);
}

.selector-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.selector-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  min-height: var(--pd-touch-large);
  padding: 14px;
  background: var(--pd-surface);
  border: 1px solid var(--pd-border);
  border-radius: var(--pd-radius);
  text-align: left;
  cursor: pointer;
  /* A patient tapping a name twice must not zoom the page instead. */
  touch-action: manipulation;
}

.selector-card:active {
  background: var(--pd-primary-soft);
  border-color: var(--pd-primary);
}

.selector-card:disabled {
  opacity: 0.6;
}

.selector-card-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.selector-card-top strong {
  font-size: 17px;
}

.selector-card-number {
  font-size: 13px;
  color: var(--pd-text-muted);
  font-variant-numeric: tabular-nums;
}

.selector-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--pd-text-secondary);
}

@media (max-width: 767px) {
  .selector-recent-label {
    font-size: 13px;
  }

  .recent-chip {
    min-height: var(--pd-touch);
  }
}
</style>
