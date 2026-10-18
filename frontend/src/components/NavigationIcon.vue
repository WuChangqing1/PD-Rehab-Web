<script setup lang="ts">
defineProps<{name:string;active:boolean}>()
const outlines:Record<string,string>={
 dashboard:'M3 10 12 3l9 7v11h-6v-7H9v7H3Z',
 patients:'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 21v-2a8 5 0 0 1 16 0v2Z',
 assessment:'M4 3h16v13H4ZM8 21h8M12 16v5',
 training:'M3 4h18v14H3ZM8 22l2-4m6 4-2-4',
 'follow-up':'M3 3h18v18H3Z',
}
</script>
<template><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path :d="outlines[name]" :fill="active?'currentColor':'none'"/><path v-if="name==='training'" d="M7 13v-3m5 3V7m5 6V9" :stroke="active?'var(--pd-surface)':'currentColor'"/><path v-if="name==='follow-up'" d="m6 16 4-5 4 2 4-6" :stroke="active?'var(--pd-surface)':'currentColor'" fill="none"/></svg></template>
