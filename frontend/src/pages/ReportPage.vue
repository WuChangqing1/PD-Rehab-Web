<script setup lang="ts">
/**
 * 综合报告 — route placeholder (Phase 8).
 */
import PagePlaceholder from '@/components/PagePlaceholder.vue'
</script>

<template>
  <PagePlaceholder
    title="综合报告"
    phase="Phase 8"
    description="多维度报告：面部表现、精细运动、钢琴训练、动作训练。不输出「帕金森总分」。"
    :planned="[
      '面部表现：表情标签分布（真实模型输出）',
      '精细运动：左右手 Amplitude、Speed、CV、Interruptions 及左右差异',
      '钢琴训练：Accuracy、Response Latency、CV、左右差异、弱指错误率',
      '动作训练：Completion、ROM、Symmetry、Stability',
      '报告导出（打印友好版）',
    ]"
    :requirements="[
      'Phase 8 实现',
      '报告底部固定医疗声明，不得出现确诊 / 治愈 / 病情下降 X% 等表述',
      '弱指指标须注明「基于任务映射，不代表真实生理手指表现」',
    ]"
  />
</template>
