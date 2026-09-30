<script setup lang="ts">
/**
 * Kept as a route so old links do not 404.
 *
 * Trends are one view of 随访与报告 now, so this redirects rather than standing
 * alone with a development notice.
 */
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

onMounted(() => {
  const query: Record<string, string> = { tab: 'trends' }
  const id = route.params.id
  if (typeof id === 'string' && id) query.patientId = id
  router.replace({ name: 'follow-up', query })
})
</script>

<template>
  <div class="pd-page" />
</template>
