<script setup lang="ts">
const balletCover = `${import.meta.env.BASE_URL}images/ballet-studio-cover-20261017.webp`
withDefaults(defineProps<{ kind: 'piano' | 'ballet'; compact?: boolean }>(), { compact: false })
</script>
<template>
  <div class="training-art" :class="[`is-${kind}`, { 'is-compact': compact }]" aria-hidden="true">
    <svg v-if="kind === 'piano'" viewBox="0 0 560 240" fill="none">
      <circle cx="415" cy="72" r="108" fill="#d5e4f6" /><circle cx="111" cy="226" r="124" fill="#e1ebf8" /><path d="M44 71H181M55 87H188M64 103H163M399 163H512M391 179H493" stroke="#adc4e3" stroke-width="2" />
      <g transform="translate(133 51) rotate(-9 145 80)"><rect x="-8" y="-8" width="300" height="166" rx="18" fill="#234b79" /><rect width="284" height="150" rx="10" fill="#fefefe" /><path v-for="x in [40,81,122,163,204,245]" :key="x" :d="`M${x} 0V149`" stroke="#c8d6e8" stroke-width="2" /><rect v-for="x in [28,69,151,192,233]" :key="x" :x="x" width="25" height="86" rx="4" fill="#23405f" /><path d="M122 145H162" stroke="#5489cd" stroke-width="8" /></g>
      <g stroke="#547fb2" stroke-width="3"><path d="M450 58v38m0-38 22-5v37" /><ellipse cx="443" cy="97" rx="7" ry="5" fill="#547fb2" /><ellipse cx="465" cy="91" rx="7" ry="5" fill="#547fb2" /></g><circle cx="91" cy="144" r="5" fill="#6591c5" />
    </svg>
    <img v-else class="ballet-cover" :src="balletCover" alt="" loading="lazy" decoding="async" />
  </div>
</template>
<style scoped>
.training-art { position: relative; background: #edf3fb; overflow: hidden; aspect-ratio: 7 / 3; }
.training-art.is-ballet { background: #eaf5f2; }
.training-art svg { width: 100%; height: 100%; display: block; }
.ballet-cover { width: 100%; height: 100%; display: block; object-fit: cover; object-position: center; }
.is-compact { border-radius: 12px; }
</style>
