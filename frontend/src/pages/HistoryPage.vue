<script setup lang="ts">
/**
 * 历史记录 — route placeholder (Phase 8).
 */
import PagePlaceholder from '@/components/PagePlaceholder.vue'
</script>

<template>
  <PagePlaceholder
    title="历史记录"
    phase="Phase 8"
    description="训练与功能测试的统一时间轴（7 天 / 30 天 / 全部）。"
    :planned="[
      '按时间对齐展示：Baseline 评估、Piano Session、Finger Tapping 复评、9-HPT 等功能测试',
      '每条记录显示 medication_state（ON / OFF / UNKNOWN）——开期与关期数据不可直接比较',
      '支持 7 天 / 30 天 / 全部 三种时间范围',
    ]"
    :requirements="[
      'Phase 8 实现',
      '需要先有真实的评估与训练数据；系统不会用示例记录填充时间轴',
    ]"
  />
</template>
