<script setup lang="ts">
/**
 * Progressive disclosure for measurements.
 *
 * A patient-facing summary shows a handful of plain-language numbers; the full
 * metric set, quality report, algorithm version and raw series stay available
 * one click away. Nothing is deleted -- research data keeps its home -- it just
 * stops being the first thing a patient sees.
 */
import { computed, useSlots } from 'vue'

export interface SummaryCard {
  /** Plain-language label, e.g. "敲击频率". */
  label: string
  /** Pre-formatted value, e.g. "2.60 Hz" or "暂无数据". */
  value: string
  /** One short line of context, optional. */
  note?: string
  /** Emphasised cards are the ones a patient should look at first. */
  emphasis?: boolean
}

const props = withDefaults(
  defineProps<{
    cards: SummaryCard[]
    /** Heading for the collapsed section. */
    advancedLabel?: string
    /** Hint under the summary explaining what these numbers are. */
    footnote?: string
  }>(),
  { advancedLabel: '查看详细指标', footnote: '' },
)

const hasAdvanced = computed(() => Boolean(useSlots().default))
</script>

<template>
  <div class="summary">
    <div class="summary-grid">
      <div
        v-for="card in cards"
        :key="card.label"
        class="summary-card"
        :class="{ 'is-emphasis': card.emphasis }"
      >
        <span class="summary-label">{{ card.label }}</span>
        <strong class="summary-value">{{ card.value }}</strong>
        <span v-if="card.note" class="summary-note">{{ card.note }}</span>
      </div>
    </div>

    <p v-if="footnote" class="pd-muted" style="font-size: 13px; margin: 10px 0 0">
      {{ footnote }}
    </p>

    <el-collapse v-if="hasAdvanced" style="margin-top: 12px">
      <el-collapse-item :title="advancedLabel" name="advanced">
        <slot />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
  border: 1px solid var(--pd-border);
  border-radius: 10px;
  background: var(--pd-surface);
}

.summary-card.is-emphasis {
  border-color: #bcd7ef;
  background: #f4f8fc;
}

.summary-label {
  font-size: 13px;
  color: var(--pd-text-secondary);
}

.summary-value {
  font-size: 22px;
  font-weight: 600;
}

.summary-note {
  font-size: 12px;
  color: var(--pd-text-secondary);
}
</style>
