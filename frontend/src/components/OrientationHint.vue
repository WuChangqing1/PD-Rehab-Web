<script setup lang="ts">
/**
 * A landscape suggestion, shown only when it would actually help.
 *
 * A phone held upright gives a wide movement a tall, narrow window: the piano
 * keyboard has to scroll and a standing ballet exercise can lose the feet. The
 * suggestion is worth making once, quietly.
 *
 * It is a SUGGESTION, not a gate. Nothing is blocked, hidden or disabled while
 * the phone is upright -- a patient who cannot rotate the device, or whose
 * support is clamped in place, must still be able to complete the task. The
 * banner is dismissible and stays dismissed for the session.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Iphone } from '@element-plus/icons-vue'

const props = withDefaults(
  defineProps<{
    /** What gets better in landscape. Kept short; it is read standing up. */
    message?: string
  }>(),
  { message: '横屏可以获得更大的操作区域。' },
)

const dismissed = ref(false)
const isPortrait = ref(false)

let portraitQuery: MediaQueryList | null = null

function sync() {
  isPortrait.value = portraitQuery?.matches ?? false
}

onMounted(() => {
  portraitQuery = window.matchMedia('(orientation: portrait) and (max-width: 1023px)')
  sync()
  portraitQuery.addEventListener('change', sync)
})

onBeforeUnmount(() => portraitQuery?.removeEventListener('change', sync))
</script>

<template>
  <div v-if="isPortrait && !dismissed" class="orientation-hint mobile-only">
    <el-icon class="orientation-icon"><Iphone /></el-icon>
    <span class="orientation-text">{{ props.message }}</span>
    <button type="button" class="orientation-close" aria-label="不再提示" @click="dismissed = true">
      知道了
    </button>
  </div>
</template>

<style scoped>
.orientation-hint {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 12px;
  border: 1px solid #bcd7ef;
  border-radius: var(--pd-radius);
  background: var(--pd-primary-soft);
  font-size: 14px;
}

.orientation-icon {
  flex: none;
  font-size: 20px;
  color: var(--pd-primary);
  /* The icon is rotated to read as "turn the phone". */
  transform: rotate(90deg);
}

.orientation-text {
  flex: 1;
  min-width: 0;
}

.orientation-close {
  flex: none;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid var(--pd-primary);
  border-radius: 6px;
  background: transparent;
  color: var(--pd-primary);
  font-size: 14px;
  cursor: pointer;
  touch-action: manipulation;
}
</style>
