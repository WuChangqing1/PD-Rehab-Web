<script setup lang="ts">
/**
 * Aperture time series chart for Finger Tapping.
 *
 * Plots the real thumb-index aperture signal (filtered) that the features were
 * computed from, with detected peaks marked. Nothing is synthesised: when no
 * series is available the component says so instead of drawing an empty axis.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  frames: number[]
  values: number[]
  peakFrames?: number[]
  title?: string
  height?: number
}>()

const container = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const hasData = computed(() => props.frames.length > 0 && props.values.length > 0)

function buildOption(): echarts.EChartsOption {
  const peakSet = new Set(props.peakFrames ?? [])
  const peaks = props.frames
    .map((frame, index) => (peakSet.has(frame) ? [frame, props.values[index]] : null))
    .filter((p): p is number[] => p !== null)

  return {
    animation: false,
    grid: { left: 52, right: 20, top: 28, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v) => (typeof v === 'number' ? v.toFixed(4) : String(v)),
    },
    xAxis: {
      type: 'value',
      name: '帧',
      nameLocation: 'middle',
      nameGap: 24,
      axisLine: { lineStyle: { color: '#c9ced6' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '归一化距离',
      nameTextStyle: { padding: [0, 0, 6, 0] },
      axisLine: { lineStyle: { color: '#c9ced6' } },
      splitLine: { lineStyle: { color: '#eef1f5' } },
    },
    series: [
      {
        name: '拇指-食指距离（滤波后）',
        type: 'line',
        showSymbol: false,
        lineStyle: { width: 1.6, color: '#2b6cb0' },
        data: props.frames.map((frame, index) => [frame, props.values[index]]),
      },
      {
        name: '检测到的峰值',
        type: 'scatter',
        symbolSize: 7,
        itemStyle: { color: '#c0504d' },
        data: peaks,
      },
    ],
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

/*
  Resize on the container as well as the window: rotating a phone, opening a
  drawer or revealing a collapsed section changes the width without a window
  resize, and the chart would otherwise keep its original size.
*/
let observer: ResizeObserver | null = null

function observeContainer() {
  if (!container.value || typeof ResizeObserver === 'undefined') return
  observer?.disconnect()
  observer = new ResizeObserver(() => onResize())
  observer.observe(container.value)
}

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
  window.addEventListener('orientationchange', onResize)
  observeContainer()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('orientationchange', onResize)
  observer?.disconnect()
  observer = null
  chart?.dispose()
  chart = null
})

watch(
  () => [props.frames, props.values, props.peakFrames, container.value],
  async () => {
    await nextTick()
    render()
    observeContainer()
  },
  { deep: true },
)
</script>

<template>
  <div class="chart-wrapper">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div
      v-if="hasData"
      ref="container"
      class="chart"
      :style="{ height: `${height ?? 260}px` }"
    />
    <div v-else class="pd-empty">
      暂无时间序列数据。
      <div style="font-size: 12px">分析未产生结果时不会绘制空图表。</div>
    </div>
  </div>
</template>

<style scoped>
.chart-wrapper {
  width: 100%;
}

.chart-title {
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--pd-text-secondary);
}

.chart {
  width: 100%;
}
</style>
