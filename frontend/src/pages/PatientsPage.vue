<script setup lang="ts">
/**
 * Patient list: search, filters, pagination, row actions.
 *
 * Deletion is a soft delete; the backend keeps the medical history and the
 * confirmation text says so explicitly.
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { patientApi } from '@/api'
import { notifyError } from '@/api/client'
import type { PatientListItem } from '@/types'
import {
  AFFECTED_SIDE_LABELS,
  DOMINANT_HAND_LABELS,
  MEDICATION_LABELS,
  SEX_LABELS,
  formatDateTime,
  medicationTagType,
} from '@/utils/format'

const router = useRouter()

const loading = ref(false)
const rows = ref<PatientListItem[]>([])
const total = ref(0)

const query = reactive({
  q: '',
  medication_state: '' as '' | 'ON' | 'OFF' | 'UNKNOWN',
  affected_side: '' as '' | 'LEFT' | 'RIGHT' | 'BILATERAL' | 'UNKNOWN',
  include_deleted: false,
  page: 1,
  page_size: 20,
})

async function load() {
  loading.value = true
  try {
    const data = await patientApi.list({
      q: query.q || undefined,
      medication_state: query.medication_state || undefined,
      affected_side: query.affected_side || undefined,
      include_deleted: query.include_deleted || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    notifyError(error, '无法加载患者列表。')
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  load()
}

function reset() {
  query.q = ''
  query.medication_state = ''
  query.affected_side = ''
  query.include_deleted = false
  query.page = 1
  load()
}

async function remove(row: PatientListItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除患者「${row.name}」？该操作为软删除，历史医疗记录会保留，可在列表中勾选“包含已删除”后恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await patientApi.remove(row.id)
    ElMessage.success('已删除（软删除）')
    load()
  } catch (error) {
    notifyError(error, '删除失败。')
  }
}

function open(row: PatientListItem) {
  router.push({ name: 'patient-detail', params: { id: row.id } })
}

function edit(row: PatientListItem) {
  router.push({ name: 'patient-edit', params: { id: row.id } })
}

function startAssessment(row: PatientListItem) {
  router.push({ name: 'assessment', params: { id: row.id } })
}

onMounted(load)
</script>

<template>
  <div class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">患者管理</h1>
        <p class="pd-page-subtitle">患者档案、受累侧与用药状态。删除为软删除，历史记录不会丢失。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="router.push({ name: 'patient-new' })">
        新增患者
      </el-button>
    </div>

    <div class="pd-card">
      <div class="pd-card-body filter-bar">
        <el-input
          v-model="query.q"
          placeholder="搜索姓名 / 患者编号 / 电话"
          clearable
          style="width: 240px"
          @keyup.enter="search"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <el-select v-model="query.medication_state" placeholder="药物状态" clearable style="width: 150px">
          <el-option label="开期（ON）" value="ON" />
          <el-option label="关期（OFF）" value="OFF" />
          <el-option label="未知" value="UNKNOWN" />
        </el-select>

        <el-select v-model="query.affected_side" placeholder="主要受累侧" clearable style="width: 150px">
          <el-option label="左侧" value="LEFT" />
          <el-option label="右侧" value="RIGHT" />
          <el-option label="双侧" value="BILATERAL" />
          <el-option label="未知" value="UNKNOWN" />
        </el-select>

        <el-checkbox v-model="query.include_deleted">包含已删除</el-checkbox>

        <el-button type="primary" :icon="Search" @click="search">查询</el-button>
        <el-button :icon="Refresh" @click="reset">重置</el-button>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-body">
        <el-table v-loading="loading" :data="rows" stripe empty-text="暂无患者记录">
          <el-table-column prop="hospital_number" label="患者编号" width="110" />
          <el-table-column prop="name" label="姓名" min-width="120" />
          <el-table-column label="性别" width="70">
            <template #default="{ row }">{{ SEX_LABELS[row.sex] ?? row.sex }}</template>
          </el-table-column>
          <el-table-column label="年龄" width="70">
            <template #default="{ row }">{{ row.age ?? '暂无数据' }}</template>
          </el-table-column>
          <el-table-column label="主要受累侧" width="110">
            <template #default="{ row }">
              {{ AFFECTED_SIDE_LABELS[row.affected_side] ?? row.affected_side }}
            </template>
          </el-table-column>
          <el-table-column label="惯用手" width="90">
            <template #default="{ row }">
              {{ DOMINANT_HAND_LABELS[row.dominant_hand] ?? row.dominant_hand }}
            </template>
          </el-table-column>
          <el-table-column label="病程(年)" width="90">
            <template #default="{ row }">
              {{ row.disease_duration_years ?? '暂无数据' }}
            </template>
          </el-table-column>
          <el-table-column label="用药状态" width="110">
            <template #default="{ row }">
              <el-tag :type="medicationTagType(row.medication_state)" size="small">
                {{ MEDICATION_LABELS[row.medication_state] ?? row.medication_state }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最后评估" width="150">
            <template #default="{ row }">{{ formatDateTime(row.last_assessment_at) }}</template>
          </el-table-column>
          <el-table-column label="最后训练" width="150">
            <template #default="{ row }">{{ formatDateTime(row.last_training_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="open(row)">详情</el-button>
              <el-button link type="primary" @click="startAssessment(row)">评估</el-button>
              <el-button link type="primary" @click="edit(row)">编辑</el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          style="margin-top: 16px; justify-content: flex-end"
          @current-change="load"
          @size-change="search"
        />
      </div>
    </div>

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
</style>
