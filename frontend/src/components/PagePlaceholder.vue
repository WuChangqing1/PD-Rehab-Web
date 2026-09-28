<script setup lang="ts">
/**
 * Placeholder for a page whose feature belongs to a later phase.
 *
 * It states plainly that nothing is implemented yet and lists what is planned.
 * It never displays example metrics, scores or charts: showing plausible sample
 * numbers would make an unimplemented feature look finished.
 */
import { ElAlert, ElTag } from 'element-plus'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'

withDefaults(
  defineProps<{
    title: string
    phase: string
    description: string
    planned?: string[]
    requirements?: string[]
  }>(),
  { planned: () => [], requirements: () => [] },
)
</script>

<template>
  <div class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">{{ title }}</h1>
        <p class="pd-page-subtitle">{{ description }}</p>
      </div>
      <ElTag type="info" size="large">{{ phase }} 待实现</ElTag>
    </div>

    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">当前状态</span>
      </div>
      <div class="pd-card-body">
        <ElAlert type="info" :closable="false" show-icon>
          <template #title>该功能尚未实现</template>
          <template #default>
            <p style="margin: 0">
              本页面为路由占位，用于确认页面结构与导航可用。为避免误导，系统
              <strong>不会</strong> 在此显示任何示例数据、模拟指标或占位分数。
            </p>
          </template>
        </ElAlert>

        <div v-if="planned.length" class="pd-block">
          <h3>计划实现内容</h3>
          <ul class="pd-list">
            <li v-for="item in planned" :key="item">{{ item }}</li>
          </ul>
        </div>

        <div v-if="requirements.length" class="pd-block">
          <h3>前置条件</h3>
          <ul class="pd-list">
            <li v-for="item in requirements" :key="item">{{ item }}</li>
          </ul>
        </div>
      </div>
    </div>

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
.pd-block {
  margin-top: 20px;
}

.pd-block h3 {
  margin-bottom: 8px;
}

.pd-list {
  margin: 0;
  padding-left: 20px;
  color: var(--pd-text-secondary);
}

.pd-list li {
  margin-bottom: 4px;
}
</style>
