<script setup lang="ts">
import { useId } from 'vue'
const onset = defineModel<number>('onset', {required:true})
const apex = defineModel<number | null>('apex', {required:true})
defineProps<{disabled?:boolean}>()
const id = useId()
</script>
<template>
 <fieldset class="microflow-keyframes" :disabled="disabled">
  <legend>{{ $t("视频关键帧") }}</legend>
  <div class="keyframe-fields">
   <label :for="`${id}-onset`">{{ $t("起始帧") }}<input :id="`${id}-onset`" v-model.number="onset" type="number" min="1" max="1799" step="1" required/></label>
   <label :for="`${id}-apex`">{{ $t("峰值帧") }}<input :id="`${id}-apex`" :value="apex??''" type="number" min="2" max="1800" step="1" required @input="apex=($event.target as HTMLInputElement).value?Number(($event.target as HTMLInputElement).value):null"/></label>
  </div>
  <p>{{ $t("帧序号从 1 开始，峰值帧须晚于起始帧。由操作者确认关键帧，模型不会自动定位峰值。") }}</p>
 </fieldset>
</template>
<style scoped>
.microflow-keyframes{border:1px solid #d8e3ec;border-radius:12px;padding:14px 16px;margin:16px 0;color:#35516c;min-width:0}.microflow-keyframes legend{font-weight:600;padding:0 6px}.keyframe-fields{display:grid;grid-template-columns:1fr 1fr;gap:14px}.keyframe-fields label{display:flex;flex-direction:column;gap:7px;font-size:14px}.keyframe-fields input{width:100%;box-sizing:border-box;padding:10px 12px;min-height:44px;border:1px solid #c5d4e2;border-radius:8px;font:inherit;color:#304d69;background:#fff}.keyframe-fields input:focus-visible{outline:3px solid #88b1dd;outline-offset:1px}.microflow-keyframes p{font-size:13px;line-height:1.7;margin:12px 0 0;color:#647b8f}.microflow-keyframes:disabled{opacity:.65}
</style>
