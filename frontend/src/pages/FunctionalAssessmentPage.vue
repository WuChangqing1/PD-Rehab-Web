<script setup lang="ts">
/**
 * 功能评估 — route placeholder (Phase 7).
 */
import PagePlaceholder from '@/components/PagePlaceholder.vue'
</script>

<template>
  <PagePlaceholder
    title="功能评估"
    phase="Phase 7"
    description="周期性外部功能验证指标。第一版实现 9-HPT，其余测试保留数据结构。"
    :planned="[
      '9-HPT（九孔插棒测试）：记录左手完成时间、右手完成时间、测试日期、药物状态与备注，并加入长期趋势',
      'BBT（盒块测试）：60 秒内转移木块数（第一版保留结构，不做界面）',
      '手指协同运动测试：医生人工记录 0～4 分或定性描述（保留结构）',
      'MDS-UPDRS 与 PDQ-39：由医生 / 患者人工录入（保留结构）',
    ]"
    :requirements="[
      'Phase 7 实现',
      '系统不自动生成 MDS-UPDRS 等临床评分，全部由医生人工录入',
      '左手与右手时间分别成图，不合并为单一分数',
    ]"
  />
</template>
