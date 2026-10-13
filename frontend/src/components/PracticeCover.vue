<script setup lang="ts">
defineProps<{ family: string; index: number }>()
</script>
<template>
  <svg class="practice-cover" :class="`family-${family.toLowerCase()}`" viewBox="0 0 240 64" aria-hidden="true">
    <path d="M12 20H228M12 44H228" class="cover-grid" />
    <template v-if="family === 'BIMANUAL'">
      <circle v-for="i in 5" :key="i" :cx="20+i*34" cy="20" r="5" />
      <circle v-for="i in 5" :key="`r${i}`" :cx="20+i*34+(index%2?12:0)" cy="44" r="5" class="cover-secondary" />
    </template>
    <template v-else-if="family === 'SEQUENCE'">
      <rect v-for="i in 6" :key="i" :x="24+i*26" :y="16+(i%3)*6" :width="index%2?12:20" :height="32-(i%3)*6" rx="4" />
    </template>
    <template v-else>
      <path :d="index%2?'M24 32H45V18H53V46H61V32H96V18H104V46H112V32H147V18H155V46H163V32H212':'M24 32H42V18H50V46H58V32H89V18H97V46H105V32H130V18H138V46H146V32H165V18H173V46H181V32H212'" class="cover-wave" />
    </template>
  </svg>
</template>
<style scoped>
.practice-cover { width:100%;height:64px;background:#edf3fc;color:#547ab5;fill:currentColor;border-radius:10px; }
.family-bimanual { background:#edf7f5;color:#44817d; }
.family-sequence { background:#f1f1fa;color:#7775a4; }
.family-cognitive { background:#f8f4eb;color:#a08a52; }
.cover-grid { stroke:currentColor;opacity:.13; }
.cover-wave { stroke:currentColor;stroke-width:2.5;fill:none;stroke-linejoin:round; }
.cover-secondary { opacity:.5; }
</style>
