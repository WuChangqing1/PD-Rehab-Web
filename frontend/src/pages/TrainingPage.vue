<script setup lang="ts">
/**
 * 康复训练 — route placeholder (Phase 5 / Phase 6).
 *
 * This page only confirms that routing and navigation work. It deliberately
 * renders no metrics, scores or charts: plausible sample numbers would make an
 * unimplemented feature look finished.
 */
import PagePlaceholder from '@/components/PagePlaceholder.vue'
</script>

<template>
  <PagePlaceholder
    title="康复训练"
    phase="Phase 5 / Phase 6"
    description="训练入口：精细运动（虚拟钢琴 / 节奏）与较大动作（Pose / 简单瑜伽）。"
    :planned="[
      '钢琴训练：Calibration + 四种训练模式（单键节奏、左右手交替、映射序列、跟随节拍）',
      '三轮自适应难度：由 Accuracy / Miss Rate / Response Latency / CV / 左右差异 驱动',
      '动作训练：山式双臂上举、双臂侧平举、左右侧屈伸展、坐姿躯干旋转、坐姿交替抬臂',
      '每次训练保存 Raw Event 与客观指标，而不只是游戏总分',
    ]"
    :requirements="[
      'Phase 5（钢琴）与 Phase 6（Pose）实现',
      '钢琴仅需浏览器 Web Audio API，不需要 MIDI 硬件',
      '动作训练需要浏览器摄像头（HTTPS 或 localhost）或已录制视频',
    ]"
  />
</template>
