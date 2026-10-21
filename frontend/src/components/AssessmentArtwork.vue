<script setup lang="ts">
import {computed} from 'vue'
const props=defineProps<{kind:string}>()
const base=import.meta.env.BASE_URL
const cover=computed(()=>props.kind==='COMPREHENSIVE'?'comprehensive':props.kind==='FINGER_TAPPING_ONLY'?'finger':'face')
const descriptions={comprehensive:'医生与长者进行问诊',face:'面部与关键点定位图',finger:'拇指与食指对指动作'}
</script>
<template>
  <div class="assessment-art">
    <img :src="`${base}images/assessment-20261021/${cover}.webp`" :alt="descriptions[cover]" width="1200" height="515" decoding="async">
    <a :href="`${base}images/assessment-20261021/SOURCES.html`" target="_blank" rel="noopener" class="image-credit" aria-label="查看封面图片来源" @click.stop>ⓘ</a>
  </div>
</template>
<style scoped>
.assessment-art{position:relative;aspect-ratio:7/3;width:100%;background:#edf3f9;overflow:hidden}.assessment-art img{display:block;width:100%;height:100%;object-fit:cover}.image-credit{position:absolute;right:8px;bottom:8px;display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#ffffffeb;color:#315b80;font-size:18px;text-decoration:none}.image-credit:focus-visible{outline:3px solid #315b80;outline-offset:2px}
</style>
