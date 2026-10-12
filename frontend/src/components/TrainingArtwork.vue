<script setup lang="ts">
withDefaults(defineProps<{ kind: 'piano' | 'ballet'; compact?: boolean }>(), { compact: false })
</script>
<template>
  <div class="training-art" :class="[`is-${kind}`, { 'is-compact': compact }]" aria-hidden="true">
    <svg v-if="kind === 'piano'" viewBox="0 0 560 240" fill="none">
      <circle cx="415" cy="72" r="108" fill="#d5e4f6" /><circle cx="111" cy="226" r="124" fill="#e1ebf8" /><path d="M44 71H181M55 87H188M64 103H163M399 163H512M391 179H493" stroke="#adc4e3" stroke-width="2" />
      <g transform="translate(133 51) rotate(-9 145 80)"><rect x="-8" y="-8" width="300" height="166" rx="18" fill="#234b79" /><rect width="284" height="150" rx="10" fill="#fefefe" /><path v-for="x in [40,81,122,163,204,245]" :key="x" :d="`M${x} 0V149`" stroke="#c8d6e8" stroke-width="2" /><rect v-for="x in [28,69,151,192,233]" :key="x" :x="x" width="25" height="86" rx="4" fill="#23405f" /><path d="M122 145H162" stroke="#5489cd" stroke-width="8" /></g>
      <g stroke="#547fb2" stroke-width="3"><path d="M450 58v38m0-38 22-5v37" /><ellipse cx="443" cy="97" rx="7" ry="5" fill="#547fb2" /><ellipse cx="465" cy="91" rx="7" ry="5" fill="#547fb2" /></g><circle cx="91" cy="144" r="5" fill="#6591c5" />
    </svg>
    <svg v-else viewBox="0 0 560 240" fill="none">
      <circle cx="282" cy="112" r="104" fill="#d0e9e5" /><circle cx="282" cy="112" r="82" stroke="#b3d7d2" /><path d="M65 188H495M89 204H468" stroke="#b3d7d2" stroke-width="2" /><path d="M138 135c29-62 57-91 102-96m82 6c39 17 71 48 100 92" stroke="#8fbfb9" stroke-dasharray="4 8" stroke-width="2" /><circle cx="281" cy="46" r="13" fill="#276a67" /><path d="M276 66c-8 23-9 43-3 62l-16 26 28 6 19-18-9-17c5-19 4-38-5-59" fill="#36827c" /><path d="M274 75c-35-9-55-28-72-47m89 47c29-8 51-28 68-48" stroke="#276a67" stroke-width="9" stroke-linecap="round" /><path d="m276 150-16 52-21 9m48-58 41 35 51-7" stroke="#276a67" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" /><path d="M258 124c18 6 30 6 43 0l18 24c-27 11-52 11-75 0z" fill="#72aaa4" /><path d="M109 94h25m-12-12v25M430 75h18m-9-9v18" stroke="#84b6b0" stroke-width="2" />
    </svg>
    <span class="training-art__label">{{ kind === 'piano' ? 'RHYTHM & COORDINATION' : 'MOVEMENT & BALANCE' }}</span>
  </div>
</template>
<style scoped>
.training-art { position: relative; background: #edf3fb; overflow: hidden; aspect-ratio: 7 / 3; }
.training-art.is-ballet { background: #eaf5f2; }
.training-art svg { width: 100%; height: 100%; display: block; }
.training-art__label { position: absolute; top: 18px; left: 24px; color: #3c618b; font-size: 10px; font-weight: 600; letter-spacing: 1.7px; }
.is-ballet .training-art__label { color: #386b66; }
.is-compact { border-radius: 12px; }
@media (max-width: 767px) { .training-art__label { top: 12px; left: 16px; font-size: 9px; } }
</style>
