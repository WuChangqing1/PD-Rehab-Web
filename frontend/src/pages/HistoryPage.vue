<script setup lang="ts">
/**
 * Kept as a route so old links do not 404.
 *
 * History, trends and the report are now one entry -- 随访与报告 -- and this page
 * redirects there instead of standing alone with a development notice.
 */
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

onMounted(() => {
  const query: Record<string, string> = { tab: 'timeline' }
  const id = route.params.id
  if (typeof id === 'string' && id) query.patientId = id
  router.replace({ name: 'follow-up', query })
})
</script>

<template>
  <div class="pd-page" />
</template>
