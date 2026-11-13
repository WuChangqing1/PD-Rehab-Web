<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { locale, t } from '@/i18n'
import manifest from '@/dance/resources-v2.json'
import { releaseVideo, resolveCourses } from '@/dance/courses'

const courses = computed(() => resolveCourses(manifest, locale.value))
const courseId = ref('')
const partId = ref('')
const course = computed(() => courses.value.find(item => item.id === courseId.value))
const part = computed(() => course.value?.parts.find(item => item.partId === partId.value))
const partNumber = computed(() => (course.value?.parts.findIndex(item => item.partId === partId.value) ?? -1) + 1)
const video = ref<HTMLVideoElement | null>(null)
const playerSection = ref<HTMLElement | null>(null)
const loading = ref(false)
const failed = ref(false)
const revision = ref(0)

function clearPlayer() { releaseVideo(video.value) }
async function selectPart(id: string, selectedPart: string) {
  clearPlayer()
  courseId.value = id
  partId.value = selectedPart
  failed.value = false
  loading.value = true
  revision.value++
  await nextTick()
  playerSection.value?.focus({ preventScroll: true })
  playerSection.value?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'nearest' })
}
function pauseInBackground() { if (document.hidden) video.value?.pause() }
function mediaError() { failed.value = true; loading.value = false }
function partLabel(number: number) { return locale.value === 'en' ? `Part ${number}` : `第 ${number} 段` }
function duration(seconds: number) {
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}
onMounted(() => document.addEventListener('visibilitychange', pauseInBackground))
onBeforeRouteLeave(clearPlayer)
onBeforeUnmount(() => { clearPlayer(); document.removeEventListener('visibilitychange', pauseInBackground) })
</script>

<template>
  <div class="pd-page dance-library" data-testid="dance-library">
    <router-link class="pd-back" :to="{ name: 'training' }">← {{ t('返回康复训练') }}</router-link>
    <div class="pd-page-header"><h1 class="pd-page-title">{{ t('舞蹈视频课程') }}</h1></div>
    <p class="library-note">{{ t('本页仅播放视频，不保存训练记录。') }}</p>

    <div class="course-grid">
      <article v-for="item in courses" :key="item.id" class="course-card" :data-course-id="item.id">
        <img :src="item.poster" alt="" loading="lazy" width="640" height="360" />
        <div class="course-body">
          <span class="course-language">{{ item.language === 'zh' ? t('中文视频') : t('英文视频') }} · {{ item.parts.length }} {{ t('个分段') }}</span>
          <h2>{{ item.title }}</h2>
          <button class="pd-primary-link" type="button" :aria-pressed="courseId === item.id" @click="selectPart(item.id, item.parts[0]!.partId)">{{ t('观看课程') }} <span aria-hidden="true">→</span></button>
        </div>
      </article>
    </div>

    <section v-if="course && part" ref="playerSection" class="course-player pd-card" tabindex="-1" :aria-label="course.title" data-testid="dance-player">
      <div class="player-heading"><h2>{{ course.title }}</h2><span>{{ partLabel(partNumber) }} / {{ course.parts.length }}</span></div>
      <video :key="`${partId}-${revision}`" ref="video" :src="part.url" :poster="course.poster" controls playsinline preload="metadata" :aria-label="`${course.title} · ${partLabel(partNumber)}`" @loadstart="loading = true" @loadeddata="loading = false" @canplay="loading = false" @playing="loading = false" @waiting="loading = true" @error="mediaError" />
      <div class="player-status" role="status" aria-live="polite">
        <template v-if="failed">{{ t('视频加载失败，请检查网络后重试。若仍无法播放，请尝试其他浏览器或设备。') }} <button type="button" class="retry-button" @click="selectPart(course.id, part.partId)">{{ t('重试') }}</button></template>
        <template v-else-if="loading">{{ t('正在加载视频…') }}</template>
        <template v-else>{{ t('使用播放器控制播放、音量与全屏。切换分段后请点击播放。') }}</template>
      </div>
      <nav class="part-list" :aria-label="t('课程分段')">
        <button v-for="(lesson, index) in course.parts" :key="lesson.partId" type="button" :data-part-id="lesson.partId" :aria-current="partId === lesson.partId ? 'true' : undefined" @click="selectPart(course.id, lesson.partId)">
          <span>{{ partLabel(index + 1) }}</span><span class="part-duration">{{ duration(lesson.durationSeconds) }}</span>
        </button>
      </nav>
    </section>
  </div>
</template>

<style scoped>
.library-note { margin: 0 0 24px; color: var(--pd-text-secondary); line-height: 1.7; max-width: 85ch; }
.course-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }
.course-card { display: flex; flex-direction: column; overflow: hidden; min-width: 0; border: 1px solid var(--pd-border); border-radius: var(--pd-radius-card); background: var(--pd-surface); box-shadow: var(--pd-shadow); }
.course-card img { display: block; width: 100%; height: auto; aspect-ratio: 16/9; object-fit: cover; background: #e8eeee; }
.course-body { display: flex; flex-direction: column; flex: 1; padding: 20px; }
.course-language { color: var(--pd-text-secondary); font-size: 14px; }
.course-body h2 { font-size: 22px; margin: 12px 0 20px; line-height: 1.4; overflow-wrap: anywhere; }
.course-body button { margin-top: auto; width: 100%; justify-content: space-between; cursor: pointer; font: inherit; min-height: 48px; }
.course-body button[aria-pressed="true"] { outline: 3px solid var(--pd-text-secondary); outline-offset: 3px; }
.course-player { margin-top: 28px; padding: 24px; }
.player-heading { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.player-heading h2 { margin: 0; font-size: 24px; }
.course-player video { display: block; width: 100%; max-height: 65vh; aspect-ratio: 16/9; background: #111; border-radius: 8px; }
.player-status { padding: 14px 0; color: var(--pd-text-secondary); line-height: 1.7; min-height: 50px; }
.retry-button { font: inherit; min-height: 44px; padding: 6px 16px; cursor: pointer; }
.part-list { display: flex; flex-wrap: wrap; gap: 12px; }
.part-list button { display: flex; justify-content: space-between; align-items: center; gap: 20px; min-height: 52px; min-width: 132px; padding: 10px 16px; border: 1px solid var(--pd-border); border-radius: 8px; background: var(--pd-surface); color: var(--pd-text); font: inherit; cursor: pointer; }
.part-list button[aria-current="true"] { background: #e3f2ef; color: #174f44; border: 2px solid #287461; font-weight: 700; }
.part-duration { font-size: 14px; font-variant-numeric: tabular-nums; }
button:focus-visible { outline: 3px solid #287461; outline-offset: 3px; }
@media (max-width: 1050px) { .course-grid { gap: 14px; } .course-body { padding: 16px; } }
@media (max-width: 767px) { .course-grid { grid-template-columns: 1fr; } .course-player { padding: 16px; } .course-body h2 { margin-bottom: 16px; } .part-list button { flex: 1 1 120px; } }
@media (prefers-reduced-motion: reduce) { .dance-library { scroll-behavior: auto; } }
</style>
