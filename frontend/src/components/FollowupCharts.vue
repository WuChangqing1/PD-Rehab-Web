<script setup lang="ts">
import TrendChart from '@/components/TrendChart.vue'
import type {MetricSpec} from '@/followup/analysis'
import type {TrendSeries} from '@/followup/trends'
import {objectiveSummary} from '@/followup/analysis'
import {formatTrendValue,formatTrendDelta} from '@/followup/trendOption'
defineProps<{items:Array<{spec:MetricSpec;built:TrendSeries}>}>()
function change(item:{spec:MetricSpec;built:TrendSeries}){
  const delta=objectiveSummary(item.built).delta
  return delta===null?'暂无可比前次':`${delta>0?'+':''}${formatTrendDelta(delta,item.spec.unit)}`
}
</script>
<template>
  <div class="followup-charts"><article v-for="item in items" :key="item.spec.key" class="pd-card trend-card">
    <header><h3>{{ $t(item.spec.label) }}</h3><el-tag size="small" type="info">{{ $t(`${$t(item.built.points.length)} 次`) }}</el-tag></header>
    <div class="metric-latest"><strong>{{ $t(item.built.points.length?formatTrendValue(item.built.points.at(-1)!.value,item.spec.unit):'暂无数据') }}</strong><span>{{ $t(change(item)) }}</span></div>
    <TrendChart :points="item.built.points" :label="$t(item.spec.label)" :unit="item.spec.unit" :height="210"/>
    <footer v-if="item.built.mixedVersions">{{ $t("不同算法版本分别绘制") }}</footer>
    <footer v-else-if="item.built.points.length===1">{{ $t("仅 1 次记录，暂不判断变化") }}</footer>
  </article></div>
</template>
<style scoped>
.followup-charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.trend-card{min-width:0;padding:20px}.followup-charts>.trend-card+.trend-card{margin-top:0}header{display:flex;align-items:center;justify-content:space-between;gap:12px}h3{font-size:15px;margin:0;line-height:1.5}.metric-latest{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;margin:18px 0}.metric-latest strong{font-size:25px;font-variant-numeric:tabular-nums}.metric-latest span,footer{font-size:14px;color:var(--pd-text-secondary)}footer{margin-top:8px}@media(max-width:1000px){.followup-charts{grid-template-columns:1fr}}@media(max-width:600px){.trend-card{padding:14px}}
</style>
