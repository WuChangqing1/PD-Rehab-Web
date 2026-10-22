<script setup lang="ts">
/**
 * Pick the patient a task is about, without going through a patient page first.
 *
 * Task-first means the function comes before the patient: a doctor opens
 * "评估中心", then says who it is for. Search covers name and hospital number,
 * and the row shows the facts that decide how to run the task (age, affected
 * side, medication state).
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'

import { patientApi } from '@/api'
import OptionalValue from '@/components/OptionalValue.vue'
import { notifyError } from '@/api/client'
import type { Patient, PatientListItem } from '@/types'
import { usePatientContextStore } from '@/stores/patientContext'
import {
  AFFECTED_SIDE_LABELS,
  displayPatientName,
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
const choosing = ref(false)
let disposed = false
let searchVersion = 0

const hasQuery = computed(() => query.value.trim().length > 0)

async function search() {
  const version = ++searchVersion
  loading.value = true
  try {
    const data = await patientApi.list({
      q: query.value.trim() || undefined,
      page: 1,
      page_size: 20,
    })
    if (!disposed && version === searchVersion) rows.value = data.items
  } catch (error) {
    notifyError(error, '无法加载患者列表。')
  } finally {
    if (version === searchVersion) loading.value = false
  }
}

async function choose(id: string) {
  if (choosing.value) return
  choosing.value = true
  const patient = await store.fetchPatient(id, true)
  choosing.value = false
  if (disposed) return
  if (!patient) {
    notifyError(null, '无法读取该患者资料，请重新选择。')
    return
  }
  store.accept(patient)
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
onBeforeUnmount(() => { disposed = true; window.clearTimeout(timer) })
</script>

<template>
  <div v-loading="choosing" class="pd-card patient-selector">
    <div class="pd-card-header">
      <span class="pd-card-title">{{ $t(title) }}</span>
    </div>
    <div class="pd-card-body">


      <el-input
        v-model="query"
        :aria-label="$t('搜索患者姓名或编号')"
        size="large"
        class="selector-search"
        :placeholder="$t('搜索姓名 / 患者编号 / 电话')"
        clearable
        @keyup.enter="search"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <div v-if="recent.length && !hasQuery" class="recent">
        <span class="selector-recent-label">{{ $t("最近选择的患者") }}</span>
        <div class="recent-list" tabindex="0" :aria-label="$t('最近选择的患者')">
          <el-button v-for="item in recent.slice(0,5)" :key="item.id" class="recent-chip" round @click="choose(item.id)">{{displayPatientName(item.name)}}</el-button>
        </div>
      </div>

      <!-- Desktop: the whole row is readable, so a table is the right control. -->
      <div v-loading="loading" class="selector-results">
        <el-table
          :data="rows"
          height="100%"
          class="selector-table"
          :empty-text="$t('没有匹配的患者')"
          @row-click="(row: PatientListItem) => choose(row.id)"
        >
          <el-table-column :label="$t('姓名')" min-width="110">
            <template #default="{ row }">
              <strong>{{ displayPatientName(row.name) }}</strong>
            </template>
          </el-table-column>
          <el-table-column :label="$t('性别')" width="70"><template #default="{row}">{{ $t(SEX_LABELS[row.sex]??row.sex) }}</template></el-table-column>
          <el-table-column :label="$t('年龄')" width="70"><template #default="{row}"><OptionalValue :value="row.age"/></template></el-table-column>
          <el-table-column :label="$t('主要受累侧')" width="110">
            <template #default="{ row }">
              <OptionalValue localize :value="row.affected_side==='UNKNOWN'?null:AFFECTED_SIDE_LABELS[row.affected_side]"/>
            </template>
          </el-table-column>
          <el-table-column :label="$t('用药状态')" width="126">
            <template #default="{ row }">
              <el-tag :type="medicationTagType(row.medication_state)" size="small">
                {{ $t(MEDICATION_LABELS[row.medication_state] ?? row.medication_state) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="$t('操作')" width="90" align="right">
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                :disabled="row.is_deleted"
                @click.stop="choose(row.id)"
              >
                {{ $t("选择") }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

    </div>
  </div>
</template>

<style scoped>
.patient-selector { min-width:0; }
.patient-selector .pd-card-body { min-width:0; }
.recent { display:flex;flex-direction:column;gap:10px;margin-top:16px;min-width:0; }
.selector-recent-label { font-size:14px;color:var(--pd-text-secondary); }
.recent-list { display:flex;gap:8px;overflow-x:auto;min-width:0;width:100%;padding:3px 0; }
.recent-chip { flex-shrink:0;min-height:36px;margin:0; }
.selector-results { margin-top:16px;min-width:0;height:420px; }
.selector-search :deep(.el-input__wrapper) { min-height:40px; }
:deep(.el-table__row) { cursor:pointer; }
:deep(.el-table .cell) { white-space:nowrap; }
:deep(.el-scrollbar__bar.is-horizontal) { height:6px; }
:deep(.el-scrollbar__bar.is-vertical) { display:none; }
@media(max-height:700px) { :deep(.el-table__body-wrapper .el-scrollbar__wrap) { max-height:35dvh!important; } }
</style>
