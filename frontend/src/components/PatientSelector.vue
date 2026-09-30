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
        placeholder="搜索姓名 / 患者编号 / 电话"
        clearable
        @keyup.enter="search"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <div v-if="recent.length && !hasQuery" class="recent">
        <span class="pd-muted" style="font-size: 12px">最近使用</span>
        <el-button
          v-for="item in recent"
          :key="item.id"
          size="small"
          round
          @click="choose(item.id)"
        >
          {{ item.name }} · {{ item.hospital_number }}
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="rows"
        size="small"
        empty-text="没有匹配的患者"
        style="margin-top: 12px"
        @row-click="(row: PatientListItem) => choose(row.id)"
      >
        <el-table-column label="姓名" min-width="110">
          <template #default="{ row }">
            <strong>{{ row.name }}</strong>
          </template>
        </el-table-column>
        <el-table-column prop="hospital_number" label="患者编号" width="110" />
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

:deep(.el-table__row) {
  cursor: pointer;
}
</style>
