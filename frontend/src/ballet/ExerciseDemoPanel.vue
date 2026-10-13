<script setup lang="ts">
/** Approved live-action videos retain the existing review gate.
 * Otherwise show a labelled, mode-specific AI static illustration. */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { FullScreen, VideoPause, VideoPlay } from '@element-plus/icons-vue'

import BalletIllustration from '@/ballet/BalletIllustration.vue'
import { resolveDemo, reviewNotes, type DemoResolution } from '@/ballet/demoAssets'

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
          <BalletIllustration v-if="exerciseKey" :exercise="exerciseKey" :mode="executionMode" />
          <p v-else class="pd-muted">请选择动作</p>
        </div>

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
  grid-template-columns: minmax(0, 1fr);
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
  flex-wrap: wrap;
  margin: 0;
  padding: 10px 12px;
  background: var(--pd-surface);
  border-top: 1px solid var(--pd-border);
}

.demo-fallback-note {
  font-size: 12px;
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
