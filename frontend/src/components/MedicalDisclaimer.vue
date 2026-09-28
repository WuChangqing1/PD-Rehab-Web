<script setup lang="ts">
/**
 * Fixed medical disclaimer, required on every page by spec V2 section 59.
 * The wording is part of the product's compliance posture: this system is a
 * research and training aid, not a diagnostic device.
 */
withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })
</script>

<template>
  <div class="pd-disclaimer" :class="{ 'is-compact': compact }">
    本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。
  </div>
</template>

<style scoped>
.pd-disclaimer.is-compact {
  margin-top: 12px;
  font-size: 12px;
  padding: 8px 12px;
}
</style>
