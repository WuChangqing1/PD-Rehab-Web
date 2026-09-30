<script setup lang="ts">
/**
 * "Not available" page.
 *
 * Shown when a route exists but its feature is not finished. It says so in one
 * sentence and offers the way back. It deliberately does NOT show a phase number,
 * a development roadmap or a list of planned work: those are notes for the team,
 * not something a doctor or a patient should meet.
 *
 * It still never displays example metrics, scores or charts -- plausible sample
 * numbers would make an unimplemented feature look finished.
 */
import { useRouter } from 'vue-router'
import { ElAlert } from 'element-plus'

defineProps<{
  title: string
  description: string
}>()

const router = useRouter()
</script>

<template>
  <div class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">{{ title }}</h1>
        <p class="pd-page-subtitle">{{ description }}</p>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-body">
        <ElAlert type="info" :closable="false" show-icon>
          <template #title>该功能暂未开放</template>
          <template #default>
            <p style="margin: 0 0 12px">
              这个模块还在开发中，暂时不能使用。为避免误导，系统不会在这里显示
              任何示例数据或占位分数。已有的评估与训练记录不受影响。
            </p>
            <el-button type="primary" @click="router.push({ name: 'dashboard' })">
              返回工作台
            </el-button>
          </template>
        </ElAlert>
      </div>
    </div>
  </div>
</template>
