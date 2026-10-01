<script setup lang="ts">
/**
 * The count the patient follows: metronome, cue line and beat indicators.
 *
 * This is the part of the ballet module that makes it a guided task rather than
 * a video upload. It shows one instruction at a time, large, with the beat
 * number counting up beside it, and it plays a synthesised click and a simple
 * accompaniment so the patient has an external time reference.
 *
 * The visual count is driven by the same scheduled beats as the audio, not by
 * its own timer, so what is seen and what is heard stay together.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { VideoPause, VideoPlay } from '@element-plus/icons-vue'

import {
  TEMPO_CHOICES,
  beatInBar,
  cuePositionAt,
  repetitionBeats,
  type CueLike,
} from '@/ballet/rhythm'
import { RhythmEngine } from '@/ballet/rhythmEngine'

const props = withDefaults(
  defineProps<{
    cues: CueLike[]
    holdBeats: number
    bpm: number
    /** Repeated: how many times the patient performs the phrase. */
    repetitions: number
    /** Show the tempo controls. The doctor sees them; the patient does not. */
    showTempo?: boolean
    /** Start counting as soon as the panel is shown. */
    autoStart?: boolean
  }>(),
  { showTempo: false, autoStart: false },
)

const emit = defineEmits<{
  (e: 'repetition', index: number): void
  (e: 'finished'): void
}>()

const engine = new RhythmEngine()
const running = ref(false)
const beat = ref<number | null>(null)
const bpm = ref(props.bpm)
const accompany = ref(true)
const audioError = ref<string | null>(null)

const beatsPerRep = computed(() => repetitionBeats(props.cues, props.holdBeats))

const position = computed(() => {
  if (beat.value === null) {
    return cuePositionAt(props.cues, props.holdBeats, 0)
  }
  return cuePositionAt(props.cues, props.holdBeats, beat.value % beatsPerRep.value)
})

const repetitionIndex = computed(() =>
  beat.value === null ? 0 : Math.floor(beat.value / beatsPerRep.value),
)

const barBeat = computed(() => (beat.value === null ? 0 : beatInBar(beat.value) + 1))

const barDots = computed(() => {
  const count = beatsPerRep.value
  const current = beat.value === null ? -1 : beat.value % count
  return Array.from({ length: count }, (_, i) => ({
    index: i,
    active: i === current,
    step: cuePositionAt(props.cues, props.holdBeats, i).text,
  }))
})

function onBeat(event: { index: number }) {
  const previous = repetitionIndex.value
  beat.value = event.index
  const now = Math.floor(event.index / beatsPerRep.value)
  if (now !== previous && now > 0) {
    if (now >= props.repetitions) {
      engine.stop()
      running.value = false
      emit('finished')
      return
    }
    emit('repetition', now)
  }
}

async function start() {
  audioError.value = null
  try {
    await engine.unlock()
  } catch (error) {
    audioError.value = error instanceof Error ? error.message : '无法播放节拍声。'
    return
  }
  engine.start({ bpm: bpm.value, accompany: accompany.value, onBeat })
  running.value = true
}

function stop() {
  engine.stop()
  running.value = false
}

function toggle() {
  if (running.value) stop()
  else void start()
}

watch(bpm, (value) => engine.setTempo(value))
watch(accompany, () => {
  // Restarting is the only way to change the accompaniment mid-count; it keeps
  // the count honest rather than muting one voice under a running schedule.
  if (running.value) {
    stop()
    void start()
  }
})

onMounted(() => {
  if (props.autoStart) void start()
})

onBeforeUnmount(() => engine.dispose())
</script>

<template>
  <div class="rhythm">
    <el-alert
      v-if="audioError"
      type="warning"
      show-icon
      :closable="false"
      :title="audioError"
      style="margin-bottom: 12px"
    />

    <div class="cue-card" :class="{ 'is-holding': position.holding }">
      <span class="cue-step">
        {{ position.holding ? '保持' : `第 ${position.index + 1} 步` }}
      </span>
      <strong class="cue-text">{{ position.text }}</strong>
      <span class="cue-count">{{ position.stepBeat }} / {{ position.stepBeats }}</span>
    </div>

    <div class="beat-row">
      <span
        v-for="dot in barDots"
        :key="dot.index"
        class="beat-dot"
        :class="{ 'is-active': dot.active, 'is-accent': dot.index === 0 }"
        :title="dot.step"
      />
    </div>

    <div class="rhythm-bar">
      <el-button
        :type="running ? 'danger' : 'primary'"
        size="large"
        :icon="running ? VideoPause : VideoPlay"
        @click="toggle"
      >
        {{ running ? '暂停' : '开始' }}
      </el-button>

      <span class="rhythm-stat">
        第 {{ Math.min(repetitionIndex + 1, repetitions) }} / {{ repetitions }} 遍
      </span>
      <span class="rhythm-stat">第 {{ barBeat }} 拍</span>
      <span class="rhythm-stat">{{ bpm }} BPM</span>
    </div>

    <div v-if="showTempo" class="tempo-row">
      <span class="pd-muted" style="font-size: 13px">节拍速度</span>
      <el-radio-group v-model="bpm" size="small">
        <el-radio-button v-for="choice in TEMPO_CHOICES" :key="choice" :value="choice">
          {{ choice }}
        </el-radio-button>
      </el-radio-group>
      <el-checkbox v-model="accompany" size="small">钢琴伴奏</el-checkbox>
    </div>
  </div>
</template>

<style scoped>
.rhythm {
  width: 100%;
}

.cue-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 16px;
  border: 1px solid var(--pd-border);
  border-radius: 12px;
  background: var(--pd-surface);
  text-align: center;
}

.cue-card.is-holding {
  border-color: #bcd7ef;
  background: #f4f8fc;
}

.cue-step {
  font-size: 14px;
  color: var(--pd-text-secondary);
}

.cue-text {
  font-size: 30px;
  line-height: 1.25;
  font-weight: 600;
}

.cue-count {
  font-size: 16px;
  color: var(--pd-text-secondary);
}

.beat-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin: 14px 0;
}

.beat-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #dfe5ec;
}

.beat-dot.is-accent {
  box-shadow: inset 0 0 0 2px #b9c4d1;
}

.beat-dot.is-active {
  background: var(--pd-primary);
  transform: scale(1.25);
}

.rhythm-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.rhythm-stat {
  font-size: 16px;
  color: var(--pd-text-secondary);
}

.tempo-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--pd-border);
}
</style>
