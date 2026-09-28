<script setup lang="ts">
/**
 * 动作 / 简单瑜伽训练 — route placeholder (Phase 6).
 */
import PagePlaceholder from '@/components/PagePlaceholder.vue'
</script>

<template>
  <PagePlaceholder
    title="动作 / 简单瑜伽训练"
    phase="Phase 6"
    description="使用浏览器摄像头与 MediaPipe Pose 完成五个简单、低风险动作。"
    :planned="[
      '前端实时绘制骨架；最终指标由后端 Pose Service 统一计算',
      '优先保存可解释原始指标：左右肩最大角度、左右角度差、躯干角度、保持时间、动作次数、动作速度、角度标准差、有效姿态帧比例',
      '再由规则引擎按固定公式计算 range_of_motion / symmetry / stability / completion',
      '五个动作：山式双臂上举、双臂侧平举、左右侧屈伸展、坐姿躯干旋转、坐姿交替抬臂',
    ]"
    :requirements="[
      'Phase 6 实现',
      '每个展示分的公式必须先定义并版本化；公式固化前分数不入库、不展示，更不会随机生成 82 / 90 之类的分数',
      '需要浏览器摄像头（HTTPS 或 localhost 安全上下文）',
    ]"
  />
</template>
