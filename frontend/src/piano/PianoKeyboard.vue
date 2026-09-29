<script setup lang="ts">
/**
 * On-screen piano keyboard.
 *
 * Layout follows the reference project's white/black arrangement, but the key
 * bindings are corrected: upstream mapped every octave onto the same ten key
 * codes, so one key sounded five notes at once. Here each binding has exactly
 * one note, and the two rows are split between the two hands.
 *
 * Buttons are used rather than divs so the keyboard is reachable by tab and
 * Enter, and pointer events cover mouse and touch alike.
 */
import { computed } from 'vue'

import { KEY_BINDINGS, isAccidental, type KeyBinding } from '@/piano/samples'

const props = defineProps<{
  /** MIDI notes currently held down. */
  pressed: Set<number>
  /** MIDI note the patient should press now, if any. */
  targetMidi?: number | null
  /** Cue is visible but its window has not opened yet. */
  upcomingMidi?: number | null
  /** MIDI notes that were pressed at the wrong time. */
  errorMidi?: number | null
  disabled?: boolean
  /** Show the keyboard-letter hints on each key. */
  showHints?: boolean
}>()

const emit = defineEmits<{
  (e: 'press', code: string): void
  (e: 'release', code: string): void
}>()

const whiteKeys = computed(() => KEY_BINDINGS.filter((b) => !isAccidental(b.midi)))
const blackKeys = computed(() => KEY_BINDINGS.filter((b) => isAccidental(b.midi)))

/**
 * Black keys are positioned between the white keys. Index i counts how many
 * white keys precede this black key, so its left edge sits at i * whiteWidth
 * minus half a black key.
 */
const whiteWidthPercent = computed(() => 100 / whiteKeys.value.length)

function blackLeftPercent(binding: KeyBinding): number {
  const preceding = whiteKeys.value.filter((w) => w.midi < binding.midi).length
  return preceding * whiteWidthPercent.value
}

function keyClass(binding: KeyBinding): Record<string, boolean> {
  return {
    'is-white': !isAccidental(binding.midi),
    'is-black': isAccidental(binding.midi),
    'is-pressed': props.pressed.has(binding.midi),
    'is-target': props.targetMidi === binding.midi,
    'is-upcoming': props.upcomingMidi === binding.midi && props.targetMidi !== binding.midi,
    'is-error': props.errorMidi === binding.midi,
  }
}

function onDown(binding: KeyBinding, event: PointerEvent) {
  if (props.disabled) return
  event.preventDefault()
  emit('press', binding.code)
}

function onUp(binding: KeyBinding) {
  if (props.disabled) return
  emit('release', binding.code)
}

function handLabel(binding: KeyBinding): string {
  return binding.hand === 'LEFT' ? '左' : '右'
}
</script>

<template>
  <div class="piano" :class="{ 'is-disabled': disabled }">
    <div class="piano-row">
      <!-- black keys are absolutely positioned over the white row -->
      <div
        v-for="binding in blackKeys"
        :key="binding.code"
        class="piano-key black"
        :class="keyClass(binding)"
        :style="{ left: `${blackLeftPercent(binding)}%`, width: `${whiteWidthPercent * 0.62}%` }"
        role="button"
        :aria-label="`${binding.note} 键 ${binding.label} ${handLabel(binding)}手`"
        :tabindex="disabled ? -1 : 0"
        @pointerdown="onDown(binding, $event)"
        @pointerup="onUp(binding)"
        @pointerleave="onUp(binding)"
        @keydown.enter.prevent="onDown(binding, $event as unknown as PointerEvent)"
        @keydown.space.prevent="onDown(binding, $event as unknown as PointerEvent)"
        @keyup.enter="onUp(binding)"
        @keyup.space="onUp(binding)"
      >
        <span class="note">{{ binding.note }}</span>
        <span v-if="showHints !== false" class="hint">{{ binding.label }}</span>
      </div>

      <div
        v-for="binding in whiteKeys"
        :key="binding.code"
        class="piano-key white"
        :class="keyClass(binding)"
        :style="{ width: `${whiteWidthPercent}%` }"
        role="button"
        :aria-label="`${binding.note} 键 ${binding.label} ${handLabel(binding)}手`"
        :tabindex="disabled ? -1 : 0"
        @pointerdown="onDown(binding, $event)"
        @pointerup="onUp(binding)"
        @pointerleave="onUp(binding)"
        @keydown.enter.prevent="onDown(binding, $event as unknown as PointerEvent)"
        @keydown.space.prevent="onDown(binding, $event as unknown as PointerEvent)"
        @keyup.enter="onUp(binding)"
        @keyup.space="onUp(binding)"
      >
        <span class="note">{{ binding.note }}</span>
        <span v-if="showHints !== false" class="hint">{{ binding.label }}</span>
        <span class="hand">{{ handLabel(binding) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.piano {
  width: 100%;
  user-select: none;
  touch-action: manipulation;
}

.piano.is-disabled {
  opacity: 0.6;
  pointer-events: none;
}

.piano-row {
  position: relative;
  display: flex;
  height: 190px;
  border: 1px solid var(--pd-border);
  border-radius: 6px;
  overflow: hidden;
  background: var(--pd-surface);
}

.piano-key {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  cursor: pointer;
  transition: background 0.05s linear, transform 0.05s linear;
  font-size: 11px;
}

.piano-key.white {
  background: #fbfcfd;
  border-right: 1px solid #dfe4ea;
  color: var(--pd-text-secondary);
  padding-bottom: 10px;
}

.piano-key.white:last-child {
  border-right: none;
}

.piano-key.black {
  position: absolute;
  top: 0;
  height: 62%;
  z-index: 2;
  background: #2b3138;
  color: #e8ecf1;
  border-radius: 0 0 4px 4px;
  padding-bottom: 8px;
}

.piano-key.black.is-white {
  display: none;
}

/* pressed by the patient */
.piano-key.is-pressed.white {
  background: #cfe0f2;
}
.piano-key.is-pressed.black {
  background: #1b6fb8;
}

/* the key the patient should press now */
.piano-key.is-target {
  outline: 3px solid var(--pd-primary);
  outline-offset: -3px;
}
.piano-key.is-target.white {
  background: #dbe9f8;
}
.piano-key.is-target.black {
  background: #1b6fb8;
}

/* cue is visible but not yet due */
.piano-key.is-upcoming {
  outline: 2px dashed #9fb8d4;
  outline-offset: -2px;
}

/* pressed when it should not have been */
.piano-key.is-error {
  background: #f5d4d2;
}
.piano-key.is-error.black {
  background: #c0504d;
}

.note {
  font-size: 10px;
  opacity: 0.75;
}

.hint {
  font-weight: 700;
  font-size: 14px;
  font-family: 'Cascadia Mono', Consolas, monospace;
}

.hand {
  font-size: 10px;
  opacity: 0.6;
}

.piano-key.black .hand {
  display: none;
}
</style>
