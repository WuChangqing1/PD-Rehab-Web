<script setup lang="ts">
import { keyCenterX, staffY } from './geometry'
defineProps<{target:number|null;pressed:Set<number>}>()
const noteUrl=`${import.meta.env.BASE_URL}assets/music/quarter-note.svg`
</script>
<template>
 <svg class="wave-overlay" viewBox="0 0 700 100" preserveAspectRatio="none" aria-hidden="true">
  <path v-for="line in 5" :key="line" :d="`M 0 ${32+line*8} C 110 ${10+line*8} 160 ${70+line*8} 280 ${38+line*8} S 450 ${10+line*8} 700 ${38+line*8}`" />
 </svg>
 <div class="note-markers" aria-hidden="true">
  <span v-for="index in 7" :key="index" class="note-marker" :data-note="index-1"
   :class="{'is-active':target===index-1,'is-pressed':pressed.has(index-1)}"
   :style="{left:`${keyCenterX(index-1,100)}%`,top:`${staffY(index-1)}%`}"><img :src="noteUrl" alt="" /></span>
 </div>
</template>
<style scoped>
.wave-overlay{position:absolute;inset:12% 0 15%;width:100%;height:73%;pointer-events:none;opacity:.45}
.wave-overlay path{fill:none;stroke:#6c85a5;stroke-width:.55;vector-effect:non-scaling-stroke}
.note-markers{position:absolute;inset:0;pointer-events:none}.note-marker{position:absolute;transform:translate(-50%,-50%);width:clamp(24px,4.5vw,62px);height:clamp(44px,8vw,110px);opacity:.65;display:grid;place-items:center}.note-marker img{height:100%;width:100%;object-fit:contain}
.note-marker.is-active{opacity:1;filter:drop-shadow(0 3px 9px #4e93d960);animation:note-bounce 1s ease-in-out infinite}.note-marker.is-pressed{opacity:1;filter:drop-shadow(0 3px 10px #36a789)}
@keyframes note-bounce{50%{transform:translate(-50%,calc(-50% - 10px))}}
@media(prefers-reduced-motion:reduce){.note-marker.is-active{animation:none;outline:3px solid #4f89ca;border-radius:12px}}
</style>
