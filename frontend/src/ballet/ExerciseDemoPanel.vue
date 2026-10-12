<script setup lang="ts">
/**
 * The demonstration panel for the selected ballet exercise.
 *
 * TWO SOURCES, NEVER CONFUSED
 * ===========================
 * This panel only ever shows the DEMONSTRATION. The patient's own camera feed
 * belongs to the capture panel and each is labelled, because a patient who
 * mistakes a recording of someone else for a live view of themselves will try to
 * copy a body that is not theirs.
 *
 * WHAT IT SHOWS IS DECIDED ELSEWHERE
 * ==================================
 * `resolveDemo` in `ballet/demoAssets.ts` decides whether an approved clip
 * exists. Today none does -- the one candidate that downloaded was watched and
 * rejected -- so this renders the reviewed movement diagram with an honest label
 * rather than a stand-in video. When a clip does pass both gates, the video
 * branch below starts working with no change here.
 *
 * The video, when there is one, is muted and looping: the rhythm and the piano
 * accompaniment come from the audio engine on a single clock, and a second audio
 * track would drift against it and give the patient two tempos.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { FullScreen, VideoPause, VideoPlay } from '@element-plus/icons-vue'

import PoseFigure from '@/pose/PoseFigure.vue'
import { FALLBACK_LABELS, resolveDemo, reviewNotes, type DemoResolution } from '@/ballet/demoAssets'

const props = defineProps<{
  exerciseKey: string | null
  executionMode: string
  exerciseName: string
  description?: string
  /** Shown when a clip was rejected, so staff can see why. */
  showReviewDetail?: boolean
}>()

const videoEl = ref<HTMLVideoElement | null>(null)
const playing = ref(false)
const failed = ref(false)

const resolution = computed<DemoResolution>(() =>
  props.exerciseKey
    ? resolveDemo(props.exerciseKey, props.executionMode)
    : { kind: 'DIAGRAM', reason: 'NOT_SELECTED', note: '请先选择一个动作。' },
)

/**
 * The diagram branch, resolved to plain values.
 *
 * The template cannot narrow a union through `v-else` here, because the else
 * branch is reached both by "no approved clip" and by "the clip failed to load".
 * Resolving it once keeps the template readable and the types honest: a failed
 * load falls back to the diagram and says so, rather than leaving a blank box.
 */
const diagram = computed(() => {
  if (resolution.value.kind === 'DIAGRAM') {
    return { reason: resolution.value.reason, note: resolution.value.note }
  }
  return { reason: 'FILES_MISSING' as const, note: '示范视频无法播放，已改为动作示意。' }
})

const reasons = computed(() =>
  props.exerciseKey ? reviewNotes(props.exerciseKey, props.executionMode) : [],
)

/**
 * Absolute URL for a bundled asset.
 *
 * Built from BASE_URL so the same build works at the site root and under
 * `/pd-rehab/`; a hardcoded `/assets/...` would 404 on the deployed sub-path.
 */
function assetUrl(path: string): string {
  const base = import.meta.env?.BASE_URL ?? '/'
  return `${base.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
}

async function togglePlay() {
  const el = videoEl.value
  if (!el) return
  if (el.paused) {
    try {
      await el.play()
      playing.value = true
    } catch {
      // Autoplay policy: the patient must press play themselves. Not an error.
      playing.value = false
    }
  } else {
    el.pause()
    playing.value = false
  }
}

async function enterFullscreen() {
  const el = videoEl.value
  if (!el) return
  try {
    await el.requestFullscreen()
  } catch {
    // Fullscreen can be refused (iOS Safari on iPhone). The demo still plays.
  }
}

// A new exercise must not leave the previous clip's state behind.
watch(
  () => [props.exerciseKey, props.executionMode],
  () => {
    playing.value = false
    failed.value = false
    videoEl.value?.pause()
  },
)

// Stop the clip and release the element when the panel goes away.
onBeforeUnmount(() => {
  videoEl.value?.pause()
  videoEl.value = null
})

defineExpose({ resolution })
</script>

<template>
  <div class="demo-panel">
    <div class="demo-stage">
      <!--
        The video branch only renders for an asset that cleared both gates. The
        `v-if` is on the resolution rather than on a file path, so a rejected or
        unreviewed clip cannot reach the element by accident.
      -->
      <template v-if="resolution.kind === 'VIDEO' && !failed">
        <video
          ref="videoEl"
          class="demo-media"
          :src="assetUrl(resolution.video)"
          :poster="resolution.poster ? assetUrl(resolution.poster) : undefined"
          muted
          loop
          playsinline
          preload="metadata"
          @error="failed = true"
          @play="playing = true"
          @pause="playing = false"
        />
        <div class="demo-controls">
          <el-button :icon="playing ? VideoPause : VideoPlay" @click="togglePlay">
            {{ playing ? '暂停' : '播放' }}
          </el-button>
          <el-button :icon="FullScreen" @click="enterFullscreen">全屏</el-button>
        </div>
        <p v-if="resolution.attribution" class="demo-attribution">
          示范素材：{{ resolution.attribution.author }} ·
          <a :href="resolution.attribution.sourcePage" target="_blank" rel="noopener noreferrer">
            {{ resolution.attribution.license }}
          </a>
        </p>
      </template>

      <!--
        The honest fallback: a reviewed movement diagram, labelled as a diagram.
        It is never presented as footage of a person performing the exercise.
      -->
      <template v-else>
        <div class="demo-diagram">
          <PoseFigure v-if="exerciseKey" :exercise="exerciseKey" />
          <p v-else class="pd-muted">请选择动作</p>
        </div>
        <p class="demo-fallback-label">
          <el-tag type="info" effect="plain" size="small">
            {{ FALLBACK_LABELS[diagram.reason] }}
          </el-tag>
          <span class="pd-muted demo-fallback-note">{{ diagram.note }}</span>
        </p>
      </template>
    </div>

    <div class="demo-meta">
      <h3 class="demo-title">{{ exerciseName || '请选择一个动作' }}</h3>
      <p v-if="description" class="pd-secondary demo-desc">{{ description }}</p>

      <!--
        Staff-facing only. A licence discussion in front of a patient doing
        demi-pliés helps nobody, but a doctor asking "is a video coming?" deserves
        the real answer.
      -->
      <el-collapse v-if="showReviewDetail && reasons.length" class="demo-review">
        <el-collapse-item title="为什么没有示范视频">
          <ul class="demo-review-list">
            <li v-for="reason in reasons" :key="reason">{{ reason }}</li>
          </ul>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<style scoped>
.demo-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--pd-gap);
  align-items: start;
}

.demo-stage {
  position: relative;
  background: #10151a;
  border-radius: var(--pd-radius-video);
  overflow: hidden;
}

/* Reserved 16:9 box so the panel does not jump when a clip loads. */
.demo-diagram,
.demo-media {
  width: 100%;
  aspect-ratio: 16 / 9;
  display: block;
}

.demo-diagram {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f2f6fb;
}

.demo-diagram :deep(svg) {
  height: 92%;
  width: auto;
  max-width: 92%;
}

.demo-controls {
  position: absolute;
  left: 10px;
  bottom: 10px;
  display: flex;
  gap: 8px;
}

.demo-fallback-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 10px 12px;
  background: var(--pd-surface);
  border-top: 1px solid var(--pd-border);
}

.demo-fallback-note {
  font-size: var(--pd-font-size-secondary);
  min-width: 0;
}

.demo-attribution {
  margin: 0;
  padding: 8px 12px;
  background: var(--pd-surface);
  font-size: 12px;
  color: var(--pd-text-muted);
}

.demo-meta {
  min-width: 0;
}

.demo-title {
  margin: 0;
  font-size: var(--pd-font-size-section);
}

.demo-desc {
  margin: 8px 0 0;
}

.demo-review {
  margin-top: 12px;
}

.demo-review-list {
  margin: 0;
  padding-left: 18px;
  color: var(--pd-text-secondary);
  font-size: var(--pd-font-size-secondary);
  line-height: 1.7;
}

@media (max-width: 767px) {
  .demo-panel {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
