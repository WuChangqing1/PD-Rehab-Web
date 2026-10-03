<script setup lang="ts">
/**
 * On-screen piano keyboard.
 *
 * Layout follows the reference project's white/black arrangement, but the key
 * bindings are corrected: upstream mapped every octave onto the same ten key
 * codes, so one key sounded five notes at once. Here each binding has exactly
 * one note, and the two rows are split between the two hands.
 *
 * The keyboard is playable at any time, including before a round starts, so the
 * patient can find the keys and hear them first. Presses are only *recorded*
 * while a round is running -- that decision lives in the runner, not here.
 *
 * Buttons are used rather than divs so the keyboard is reachable by tab and
 * Enter, and pointer events cover mouse and touch alike.
 */
import { computed, nextTick, ref, watch } from 'vue'

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

/**
 * Release a key whose pointer the browser took away.
 *
 * Without `pointercancel` a key can stay stuck down when the system interrupts
 * the touch -- a notification, a scroll gesture starting, the browser deciding
 * the gesture was a swipe. The note would then sustain and the pressed
 * indicator would lie about what the patient is holding.
 */
function onCancel(binding: KeyBinding) {
  onUp(binding)
}

function handLabel(binding: KeyBinding): string {
  return binding.hand === 'LEFT' ? '左' : '右'
}

/*
  Keep the key the patient is being asked for on screen.

  The mobile keyboard is wider than the viewport, so without this the target can
  sit off-screen and the task becomes a hunt. `scrollIntoView` with `nearest`
  only moves when the key is actually outside the visible strip, and the inline
  behaviour keeps it from scrolling the page itself.
*/
const scrollEl = ref<HTMLDivElement | null>(null)

function targetEl(): HTMLElement | null {
  return scrollEl.value?.querySelector('.piano-key.is-target') ?? null
}

watch(
  () => props.targetMidi,
  async (midi) => {
    if (midi === null || midi === undefined) return
    await nextTick()
    targetEl()?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })
  },
)
</script>

<template>
  <div class="piano" :class="{ 'is-disabled': disabled }">
    <div class="legend">
      <span class="legend-item">
        <i class="swatch left" />左手 · 下排 <b>Z S X D C V G B H N J M</b> = C3–B3
      </span>
      <span class="legend-item">
        <i class="swatch right" />右手 · 上排 <b>Q 2 W 3 E R 5 T 6 Y 7 U</b> = C4–B4
      </span>
      <span class="legend-item muted">每键只对应一个音；高亮描边 = 当前应弹</span>
    </div>

    <div class="piano-shell">
      <div ref="scrollEl" class="piano-scroll">
      <div class="piano-row">
        <!-- black keys are absolutely positioned over the white row -->
        <div
          v-for="binding in blackKeys"
          :key="binding.code"
          class="piano-key black"
          :class="keyClass(binding)"
          :style="{ left: `${blackLeftPercent(binding)}%`, width: `${whiteWidthPercent * 0.6}%` }"
          role="button"
          :aria-label="`${binding.note} 键 ${binding.label} ${handLabel(binding)}手`"
          :tabindex="disabled ? -1 : 0"
          @pointerdown="onDown(binding, $event)"
          @pointerup="onUp(binding)"
          @pointerleave="onUp(binding)"
          @pointercancel="onCancel(binding)"
          @keydown.enter.prevent="onDown(binding, $event as unknown as PointerEvent)"
          @keydown.space.prevent="onDown(binding, $event as unknown as PointerEvent)"
          @keyup.enter="onUp(binding)"
          @keyup.space="onUp(binding)"
        >
          <span class="hint">{{ binding.label }}</span>
          <span class="note">{{ binding.note }}</span>
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
          @pointercancel="onCancel(binding)"
          @keydown.enter.prevent="onDown(binding, $event as unknown as PointerEvent)"
          @keydown.space.prevent="onDown(binding, $event as unknown as PointerEvent)"
          @keyup.enter="onUp(binding)"
          @keyup.space="onUp(binding)"
        >
          <span class="hint">{{ binding.label }}</span>
          <span class="note">{{ binding.note }}</span>
          <span class="hand">{{ handLabel(binding) }}</span>
        </div>
      </div>
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

/* ------------------------------------------------ legend ------------------------------------------------ */
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 20px;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--pd-text-secondary);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend-item b {
  font-family: 'Cascadia Mono', Consolas, monospace;
  color: var(--pd-text);
}

.legend-item.muted {
  color: var(--pd-text-secondary);
  opacity: 0.8;
}

.swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}

.swatch.left {
  background: #4c7fb8;
}

.swatch.right {
  background: #b8874c;
}

/* ------------------------------------------------ shell ------------------------------------------------ */
.piano-shell {
  padding: 14px 14px 16px;
  border-radius: 10px;
  background: linear-gradient(180deg, #23282f 0%, #161a1f 100%);
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 8%), 0 6px 18px rgb(16 20 24 / 22%);
}

.piano-scroll {
  overflow: hidden;
}

.piano-row {
  position: relative;
  display: flex;
  height: 224px;
  border-radius: 4px;
  overflow: hidden;
  background: #0c0f12;
}

/*
  MOBILE KEYS
  ===========
  Fourteen white keys across a 375px screen is 25px each: below every touch
  target guideline, and a patient with tremor cannot hit one. Rather than drop
  keys -- which would make some cues unplayable, and the cue stream is generated
  from the full range -- the keyboard becomes a horizontally scrollable strip
  with a real key width, and the key the patient is being asked for is scrolled
  into view automatically. So the strip is long but the target is never hunted.
*/
@media (max-width: 767px) {
  .piano-shell {
    padding: 10px 10px 12px;
  }

  .piano-scroll {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    /* The patient is swiping the keyboard, not the page. */
    touch-action: pan-x;
  }

  .piano-row {
    height: 176px;
    min-width: max-content;
    overflow: visible;
  }

  .piano-key.white {
    min-width: 46px;
  }

  .piano-key.white .hint {
    font-size: 18px;
  }
}

.piano-key {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  cursor: pointer;
  transition: background 0.05s linear, transform 0.05s linear;
  -webkit-tap-highlight-color: transparent;
}

/* ------------------------------------------------ white keys ------------------------------------------------ */
.piano-key.white {
  position: relative;
  gap: 1px;
  padding-bottom: 12px;
  color: #1f2733;
  background: linear-gradient(180deg, #ffffff 0%, #f7f9fb 72%, #e6ebf1 100%);
  border-right: 1px solid #c9d1da;
  border-radius: 0 0 5px 5px;
  box-shadow: inset 0 -6px 10px -8px rgb(20 30 40 / 45%);
}

.piano-key.white:last-child {
  border-right: none;
}

.piano-key.white .hint {
  font-size: 21px;
  font-weight: 700;
  line-height: 1.1;
  font-family: 'Cascadia Mono', Consolas, monospace;
  color: #1b2530;
}

.piano-key.white .note {
  font-size: 11px;
  color: #6b7885;
}

.piano-key.white .hand {
  font-size: 10px;
  color: #9aa5b1;
}

/* ------------------------------------------------ black keys ------------------------------------------------ */
.piano-key.black {
  position: absolute;
  top: 0;
  height: 62%;
  z-index: 2;
  gap: 0;
  padding-bottom: 9px;
  color: #eef2f6;
  background: linear-gradient(180deg, #4b535c 0%, #262c33 42%, #12161a 100%);
  border-radius: 0 0 4px 4px;
  box-shadow: 0 3px 6px rgb(0 0 0 / 55%), inset 0 -3px 5px -2px rgb(0 0 0 / 70%);
}

.piano-key.black .hint {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.1;
  font-family: 'Cascadia Mono', Consolas, monospace;
}

.piano-key.black .note {
  font-size: 9px;
  color: #aab4bf;
}

/* ------------------------------------------------ states ------------------------------------------------ */
.piano-key.is-pressed.white {
  background: linear-gradient(180deg, #dce9f8 0%, #c6dcf3 100%);
  transform: translateY(1px);
}

.piano-key.is-pressed.black {
  background: linear-gradient(180deg, #2f7cc0 0%, #1b5f9c 100%);
  transform: translateY(1px);
}

/* the key the patient should press now */
.piano-key.is-target {
  outline: 3px solid var(--pd-primary);
  outline-offset: -3px;
}

.piano-key.is-target.white {
  background: linear-gradient(180deg, #e7f1fd 0%, #cfe2f7 100%);
}

.piano-key.is-target.black {
  background: linear-gradient(180deg, #3b8ed0 0%, #1b6fb8 100%);
}

/* cue is visible but not yet due */
.piano-key.is-upcoming {
  outline: 2px dashed #9fb8d4;
  outline-offset: -2px;
}

/* pressed when it should not have been */
.piano-key.is-error.white {
  background: linear-gradient(180deg, #fbe3e1 0%, #f3cdc9 100%);
}

.piano-key.is-error.black {
  background: linear-gradient(180deg, #c9564f 0%, #a33c37 100%);
}
</style>
