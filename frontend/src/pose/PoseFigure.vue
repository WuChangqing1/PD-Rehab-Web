<script setup lang="ts">
/**
 * Schematic figures for the five ballet exercises.
 *
 * Drawn as inline SVG on purpose. The reference fitness site this card layout
 * takes after serves photographs from /media/... which currently 404, and a
 * broken image is worse than an honest diagram. These are stick figures, not
 * photographs: they show the line of the movement, they render everywhere, and
 * they cannot be mistaken for a real demonstration of a real person. No ballet
 * photograph is bundled, because none with clear licensing was available.
 *
 * A chair is drawn where the exercise assumes support, so the patient can see
 * that the support is part of the task rather than an optional extra.
 */
const props = defineProps<{ exercise: string }>()

const STROKE = '#2f5d8a'
const ACCENT = '#1b6fb8'
const MUTED = '#c3ced9'
const CHAIR = '#b9c4d1'

/** Head + trunk, shared by every standing figure. */
const TORSO = { head: [50, 18, 9], spine: 'M50 27 L50 62' }
</script>

<template>
  <svg class="figure" viewBox="0 0 100 100" role="img" :aria-label="`${props.exercise} 示意图`">
    <!-- ------------------------------------- Port de Bras: arms open and lift -->
    <template v-if="exercise === 'BALLET_PORT_DE_BRAS'">
      <circle :cx="TORSO.head[0]" :cy="TORSO.head[1]" :r="TORSO.head[2]" :fill="MUTED" />
      <path :d="TORSO.spine" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 62 L38 90 M50 62 L62 90" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <!-- The rounded ballet arm line: out, then up. -->
      <path d="M50 36 Q30 40 22 24 M50 36 Q70 40 78 24" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M14 12 Q50 0 86 12" :stroke="ACCENT" stroke-width="2" stroke-dasharray="3 3" fill="none" />
    </template>

    <!-- ------------------------------------- First position: rounded arms, feet together -->
    <template v-else-if="exercise === 'BALLET_FIRST_POSITION'">
      <circle :cx="TORSO.head[0]" :cy="TORSO.head[1]" :r="TORSO.head[2]" :fill="MUTED" />
      <path :d="TORSO.spine" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 62 L46 92 M50 62 L54 92" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <!-- Arms held in a circle in front of the body. -->
      <path d="M50 36 Q34 46 42 58 M50 36 Q66 46 58 58" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" fill="none" />
      <ellipse cx="50" cy="52" rx="12" ry="9" :stroke="ACCENT" stroke-width="2" stroke-dasharray="3 3" fill="none" />
      <path d="M40 92 L60 92" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
    </template>

    <!-- ------------------------------------- Tendu: one leg extends along the floor -->
    <template v-else-if="exercise === 'BALLET_TENDU'">
      <!-- Chair back, because this exercise assumes support. -->
      <path d="M14 40 L14 92 M14 44 L30 44" :stroke="CHAIR" stroke-width="3" stroke-linecap="round" fill="none" />
      <circle cx="56" cy="16" r="9" :fill="MUTED" />
      <path d="M56 25 L56 58" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <!-- Supporting leg straight down, working leg extended to the side. -->
      <path d="M56 58 L54 92" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M56 58 L84 86" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M56 58 L88 88" :stroke="ACCENT" stroke-width="2" stroke-dasharray="3 3" fill="none" />
      <!-- Arm resting on the chair. -->
      <path d="M56 32 L30 44" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M56 32 L74 48" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" fill="none" />
    </template>

    <!-- ------------------------------------- Demi-plié: both knees bend, torso upright -->
    <template v-else-if="exercise === 'BALLET_DEMI_PLIE'">
      <path d="M14 40 L14 92 M14 44 L30 44" :stroke="CHAIR" stroke-width="3" stroke-linecap="round" fill="none" />
      <circle cx="56" cy="20" r="9" :fill="MUTED" />
      <path d="M56 29 L56 58" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <!-- Knees travel outward as the body lowers: the whole point of the shape. -->
      <path d="M56 58 L40 72 L44 92" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
      <path d="M56 58 L72 72 L68 92" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
      <path d="M56 34 L30 46" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M56 34 L76 50" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M36 92 L74 92" :stroke="MUTED" stroke-width="2" stroke-dasharray="3 3" fill="none" />
    </template>

    <!-- ------------------------------------- Weight shift with Port de Bras -->
    <template v-else-if="exercise === 'BALLET_WEIGHT_SHIFT'">
      <circle cx="42" cy="20" r="9" :fill="MUTED" />
      <path d="M42 29 L46 62" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <!-- Weight on one leg, the other relaxed. -->
      <path d="M46 62 L40 92" :stroke="STROKE" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M46 62 L58 88" :stroke="MUTED" stroke-width="4" stroke-linecap="round" fill="none" />
      <!-- Arms open to the opposite side. -->
      <path d="M44 38 Q26 30 14 34 M44 38 Q62 42 76 34" :stroke="ACCENT" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 4 L50 96" :stroke="MUTED" stroke-width="2" stroke-dasharray="3 3" fill="none" />
      <path d="M14 34 L86 34" :stroke="ACCENT" stroke-width="2" stroke-dasharray="3 3" fill="none" />
    </template>

    <!-- ------------------------------------- retired exercises: neutral placeholder -->
    <template v-else>
      <circle :cx="TORSO.head[0]" :cy="TORSO.head[1]" :r="TORSO.head[2]" :fill="MUTED" />
      <path :d="TORSO.spine" :stroke="MUTED" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 62 L38 90 M50 62 L62 90" :stroke="MUTED" stroke-width="4" stroke-linecap="round" fill="none" />
      <path d="M50 36 L32 48 M50 36 L68 48" :stroke="MUTED" stroke-width="4" stroke-linecap="round" fill="none" />
      <text x="50" y="82" text-anchor="middle" font-size="10" fill="#8c98a5">早期动作</text>
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
