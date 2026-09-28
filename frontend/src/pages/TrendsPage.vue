<script setup lang="ts">
/**
 * 长期趋势 — route placeholder (Phase 8).
 *
 * Trend pages must show "model output change", never "condition improved by X%".
 */
import PagePlaceholder from '@/components/PagePlaceholder.vue'
</script>

<template>
  <PagePlaceholder
    title="长期趋势"
    phase="Phase 8"
    description="按模块展示随时间变化的客观指标。展示的是「模型输出变化」，不是「病情改善 X%」。"
    :planned="[
      'Finger Tapping：敲击频率、平均幅度、平均速度、周期时长、CV、中断次数、左右差异',
      '钢琴：Accuracy、Response Latency、Response Latency CV、Timing MAE、左右差异、弱指错误率',
      '动作训练：ROM、Symmetry、Stability、Movement Speed、Repetition Count',
      'AI / 微表情：真实模型实际输出的 tag 分布或模型概率趋势',
      '功能测试：9-HPT 左手时间 / 右手时间',
    ]"
    :requirements="[
      'Phase 8 实现',
      '每个数据点必须携带 algorithm_version，算法变更后可追溯',
      '缺失数据点留空并标注，不插值、不用 0 代替',
    ]"
  />
</template>
