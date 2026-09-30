<script setup lang="ts">
/**
 * A single metric over time.
 *
 * The chart draws one line per algorithm version. Two points produced by
 * different versions are not necessarily the same measurement, so joining them
 * into one unbroken line would assert a continuity the data does not have.
 * Splitting the series makes the change visible instead of hiding it.
 *
 * A single point is drawn as a symbol rather than a line: one measurement is not
 * a trend, and a line through one point looks like a flat one.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

import type { TrendPoint, TrendUnit } from '@/followup/trends'
import { buildTrendOption, formatTrendValue } from '@/followup/trendOption'

const props = defineProps<{
  points: TrendPoint[]
  /** Axis and tooltip label, e.g. "准确率". */
  label: string
  unit: TrendUnit
  height?: number
}>()

const container = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const hasData = computed(() => props.points.length > 0)

function formatValue(value: number): string {
  return formatTrendValue(value, props.unit)
}

function buildOption(): echarts.EChartsOption {
  const grouped = buildTrendOption(props.points)
  const showLegend = grouped.multiVersion
  const series: echarts.EChartsOption['series'] = grouped.series.map((item) => ({
    // The version is in the series name because that is what the reader needs
    // in order to know whether the points are comparable.
    name: item.name,
    type: 'line',
    showSymbol: true,
    symbolSize: 7,
    lineStyle: { width: 1.8 },
    // A single point must stay a point: a line through one measurement looks
    // like a flat trend that was never measured.
    connectNulls: false,
    data: item.data,
  }))

  return {
    animation: false,
    grid: { left: 58, right: 24, top: showLegend ? 44 : 20, bottom: 44 },
    legend: showLegend ? { top: 0, type: 'scroll' } : undefined,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => (typeof value === 'number' ? formatValue(value) : String(value)),
    },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: '#c9ced6' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: props.label,
      nameTextStyle: { padding: [0, 0, 6, 0] },
      axisLine: { lineStyle: { color: '#c9ced6' } },
      splitLine: { lineStyle: { color: '#eef1f5' } },
      axisLabel: {
        formatter: (value: number) => formatValue(value),
      },
    },
    series,
  }
}

function render() {
  if (!container.value || !hasData.value) return
  if (!chart) {
    chart = echarts.init(container.value)
  }
  chart.setOption(buildOption(), true)
  chart.resize()
}

function onResize() {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})

watch(() => props.points, render, { deep: true })
</script>

<template>
  <div class="trend-chart">
    <div
      v-if="hasData"
      ref="container"
      class="chart"
      :style="{ height: `${height ?? 240}px` }"
    />
    <div v-else class="pd-empty">暂无可绘制的数据点。</div>
  </div>
</template>

<style scoped>
.trend-chart {
  width: 100%;
}

.chart {
  width: 100%;
}
</style>
