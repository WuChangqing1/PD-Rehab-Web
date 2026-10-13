<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import PoseFigure from '@/pose/PoseFigure.vue'
import { illustrationPath } from './illustrations'
const props = withDefaults(defineProps<{ exercise: string; mode?: string; compact?: boolean }>(), { mode: 'STANDING_SUPPORTED', compact: false })
const failed = ref(false)
const path = computed(() => illustrationPath(props.exercise, props.mode))
const src = computed(() => `${import.meta.env.BASE_URL}${path.value ?? ''}`)
watch(src, () => { failed.value = false })
</script>
<template>
  <figure class="ballet-illustration" :class="{ compact }">
    <img v-if="path && !failed" :key="src" :src="src" :alt="`${mode === 'SEATED' ? '坐姿' : '站姿'}动作示意（AI 生成）`" @error="failed = true" />
    <PoseFigure v-else :exercise="exercise" />
    <figcaption v-if="!compact">{{ failed ? '图片暂时无法加载，显示动作简图' : 'AI 生成动作示意 · 请结合动作步骤与指导使用' }}</figcaption>
  </figure>
</template>
<style scoped>
.ballet-illustration { position: relative; margin: 0; width: 100%; height: 100%; min-height: 0; background: #f4f3ef; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden; }
img { display: block; width: 100%; min-height: 0; max-height: 460px; object-fit: contain; flex: 1; }
figcaption { flex: none; width: 100%; padding: 9px 12px; text-align: center; font-size: 12px; line-height: 1.5; color: #52666d; background: #f6f8f9; }
.compact img { width: 100%; height: 100%; object-fit: cover; }
svg { width: 100%; max-height: 320px; }
</style>
