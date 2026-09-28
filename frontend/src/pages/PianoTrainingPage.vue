<script setup lang="ts">
/**
 * 虚拟钢琴 / 节奏训练 — route placeholder (Phase 5).
 */
import PagePlaceholder from '@/components/PagePlaceholder.vue'
</script>

<template>
  <PagePlaceholder
    title="虚拟钢琴 / 节奏训练"
    phase="Phase 5"
    description="第一版不依赖 MIDI：使用网页虚拟钢琴、电脑键盘、鼠标与触屏，通过 Web Audio API 发声。"
    :planned="[
      'Calibration（30～60 秒）：建立个人 baseline_accuracy / baseline_response_latency / CV',
      '模式 1 单键节奏；模式 2 左右手交替；模式 3 映射序列；模式 4 跟随节拍序列',
      '每个按键事件保存 Raw Event：cue_onset_time_ms / target_time_ms / actual_time_ms / response_latency_ms / timing_error_ms / key_down / key_up / hold_duration',
      '严格区分 Response Latency（刺激出现→首次有效响应）与 Timing Error（目标时间→实际按键时间）',
      'Round 1 → 指标分析 → 调整 → Round 2 → 分析 → 调整 → Round 3',
    ]"
    :requirements="[
      'Phase 5 实现',
      '难度只依赖个人 Calibration 与实际训练表现，不使用微表情标签占比或疾病概率',
      '普通键盘无法获得真实击键力度，因此第一版不产出 velocity 指标，也不伪造',
    ]"
  />
</template>
