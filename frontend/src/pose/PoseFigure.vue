<script setup lang="ts">
/**
 * Schematic figures for the five movement exercises.
 *
 * Drawn as inline SVG on purpose. The reference fitness site this page takes its
 * card layout from serves photographs from /media/... which currently 404, and
 * a broken image is worse than an honest diagram. These are stick figures, not
 * photographs of a person: they show the movement, they render everywhere, and
 * they cannot be mistaken for a real demonstration.
 */
const props = defineProps<{ exercise: string }>()

const STROKE = '#2f5d8a'
const ACCENT = '#1b6fb8'
const MUTED = '#c3ced9'

/** Head + trunk, shared by every figure. */
const TORSO = { head: [50, 18, 9], spine: 'M50 27 L50 62' }
</script>

<template>
  <svg class="figure" viewBox="0 0 100 100" role="img" :aria-label="`${props.exercise} 示意图`">
    <!-- ---------------------------------------------- arms up overhead -->
    <template v-if="exercise === 'MOUNTAIN_ARMS_UP'">
      <circle :cx="TORSO.head[0]" :cy="TORSO.head[1]" :r="TORSO.head[2]" :fill="MUTED" />
      <path :d="TORSO.spine" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 62 L38 90 M50 62 L62 90" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 36 L34 22 L36 6 M50 36 L66 22 L64 6" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
      <path d="M28 6 L44 6 M56 6 L72 6" :stroke="ACCENT" stroke-width="2" stroke-dasharray="3 3" fill="none" />
    </template>

    <!-- ---------------------------------------------- arms out sideways -->
    <template v-else-if="exercise === 'ARMS_LATERAL_RAISE'">
      <circle :cx="TORSO.head[0]" :cy="TORSO.head[1]" :r="TORSO.head[2]" :fill="MUTED" />
      <path :d="TORSO.spine" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 62 L38 90 M50 62 L62 90" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 36 L18 36 M50 36 L82 36" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M12 36 L88 36" :stroke="ACCENT" stroke-width="2" stroke-dasharray="3 3" fill="none" />
    </template>

    <!-- ---------------------------------------------- side bend -->
    <template v-else-if="exercise === 'SIDE_BEND_STRETCH'">
      <circle cx="34" cy="22" r="9" :fill="MUTED" />
      <path d="M34 31 L42 64" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M42 64 L38 92 M42 64 L52 92" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M36 38 L18 30 L20 14 M36 38 L54 44 L58 30" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
      <path d="M50 6 L50 96" :stroke="ACCENT" stroke-width="2" stroke-dasharray="3 3" fill="none" />
    </template>

    <!-- ---------------------------------------------- seated trunk rotation -->
    <template v-else-if="exercise === 'SEATED_TRUNK_ROTATION'">
      <circle :cx="TORSO.head[0]" :cy="TORSO.head[1]" :r="TORSO.head[2]" :fill="MUTED" />
      <path :d="TORSO.spine" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 62 L30 66 L30 90 M50 62 L70 66 L70 90" :stroke="STROKE" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
      <path d="M50 38 L38 44 L46 50 M50 38 L62 44 L54 50" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
      <path d="M50 62 L50 44" :stroke="MUTED" stroke-width="2" stroke-dasharray="2 2" fill="none" />
    </template>

    <!-- ---------------------------------------------- seated alternating arm raise -->
    <template v-else>
      <circle :cx="TORSO.head[0]" :cy="TORSO.head[1]" :r="TORSO.head[2]" :fill="MUTED" />
      <path :d="TORSO.spine" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 62 L32 66 L32 90 M50 62 L68 66 L68 90" :stroke="STROKE" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
      <path d="M50 36 L66 26 L74 10" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
      <path d="M50 36 L36 50 L30 62" :stroke="MUTED" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
      <path d="M78 8 L78 4" :stroke="ACCENT" stroke-width="2" fill="none" />
    </template>
  </svg>
</template>

<style scoped>
.figure {
  width: 100%;
  height: 100%;
  max-height: 120px;
  display: block;
}
</style>
