<script setup lang="ts">
/**
 * Follow-up and reports: one place for looking back at a patient's data.
 *
 * History, trends and the report were three separate pages reached from three
 * different places, each showing a development notice. They are the same task --
 * "show me what has happened" -- so they are one entry with three views.
 *
 * None of the three panels is implemented yet. Rather than render a roadmap, the
 * page says so plainly and points at where the data currently lives.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PatientSelector from '@/components/PatientSelector.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import { assessmentApi, pianoApi, poseApi } from '@/api'
import { notifyError } from '@/api/client'
import { usePatientContextStore } from '@/stores/patientContext'
import type { AssessmentSession, Patient, PianoSession, PoseSession } from '@/types'
import { formatDateTime, formatPercent } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patient = ref<Patient | null>(null)
const tab = ref<'timeline' | 'trends' | 'report'>('timeline')
const sessions = ref<AssessmentSession[]>([])
const piano = ref<PianoSession[]>([])
const pose = ref<PoseSession[]>([])
const loading = ref(false)

const patientId = computed(() => patient.value?.id ?? null)

async function load() {
  if (!patientId.value) return
  loading.value = true
  try {
    sessions.value = (await assessmentApi.listSessions(patientId.value, 1, 50)).items
    piano.value = (await pianoApi.history(patientId.value, 20)).items
    pose.value = (await poseApi.history(patientId.value, 20)).items
  } catch (error) {
    notifyError(error, '无法加载随访数据。')
  } finally {
    loading.value = false
  }
}

async function usePatient(id: string) {
  patient.value = await store.resolve(id)
  if (patient.value) {
    router.replace({ query: { ...route.query, patientId: id } })
    await load()
  }
}

onMounted(async () => {
  const fromQuery = route.query.patientId
  const fromTab = route.query.tab
  if (fromTab === 'trends' || fromTab === 'report') tab.value = fromTab
  if (typeof fromQuery === 'string' && fromQuery) await usePatient(fromQuery)
})
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">随访与报告</h1>
        <p class="pd-page-subtitle">
          查看患者既往的评估与训练记录。先选择患者。
        </p>
      </div>
    </div>

    <SelectedPatientBar v-if="patient" :patient="patient" @change="patient = null" />

    <PatientSelector
      v-if="!patient"
      title="选择患者"
      description="搜索姓名或患者编号，选择后查看其随访数据。"
      @select="(p) => usePatient(p.id)"
    />

    <template v-else>
      <el-tabs v-model="tab" class="pd-card tabs-card">
        <el-tab-pane label="时间轴" name="timeline">
          <div class="pd-card-body">
            <p class="pd-secondary" style="margin-top: 0">
              按时间顺序查看评估与训练记录。完整的时间轴视图正在开发中，
              以下为已保存记录的原始清单。
            </p>

            <h4>评估记录</h4>
            <el-table :data="sessions" size="small" empty-text="暂无评估记录">
              <el-table-column label="开始时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  {{ row.status === 'COMPLETED' ? '已完成' : '进行中' }}
                </template>
              </el-table-column>
            </el-table>

            <h4>钢琴训练</h4>
            <el-table :data="piano" size="small" empty-text="暂无钢琴训练记录">
              <el-table-column label="开始时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
              </el-table-column>
              <el-table-column label="准确率" width="100">
                <template #default="{ row }">
                  {{ row.accuracy === null ? '暂无数据' : formatPercent(row.accuracy) }}
                </template>
              </el-table-column>
            </el-table>

            <h4>动作训练</h4>
            <el-table :data="pose" size="small" empty-text="暂无动作训练记录">
              <el-table-column label="开始时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
              </el-table-column>
              <el-table-column label="完成次数" width="100">
                <template #default="{ row }">{{ row.repetition_count ?? '暂无数据' }}</template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="趋势分析" name="trends">
          <div class="pd-card-body">
            <el-empty description="趋势图暂未开放" />
            <p class="pd-muted" style="font-size: 13px">
              趋势图需要足够的历史数据点，并且每个数据点都要带算法版本才能比较。
              当前请先使用「时间轴」查看逐次记录。
            </p>
          </div>
        </el-tab-pane>

        <el-tab-pane label="综合报告" name="report">
          <div class="pd-card-body">
            <el-empty description="综合报告暂未开放" />
            <p class="pd-muted" style="font-size: 13px">
              报告会把面部分析、手指敲击、钢琴与动作训练的结果汇总到一页。
              本系统不输出「帕金森总分」，只列出各项客观指标。
            </p>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<style scoped>
.tabs-card {
  padding: 0 18px 18px;
}

h4 {
  margin: 18px 0 8px;
  font-size: 14px;
}
</style>
