<script setup lang="ts">
defineProps<{kind:string}>()
</script>
<template>
  <div class="assessment-art" aria-hidden="true">
    <svg viewBox="0 0 560 240" fill="none">
      <circle cx="440" cy="45" r="135" fill="#dce9f6"/><circle cx="100" cy="240" r="130" fill="#e6f1ed"/>
      <g v-if="kind!=='FINGER_TAPPING_ONLY'" :transform="kind==='COMPREHENSIVE'?'translate(-65 0)':''" stroke="#315b80" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M236 77c0-27 16-45 44-45s44 18 44 45v40c0 32-18 53-44 53s-44-21-44-53Z" fill="#fff"/>
        <path d="M257 96h3m40 0h3m-26 7-5 21h13m-24 18c12 7 25 7 37 0M221 205c6-23 24-35 59-35s53 12 59 35"/>
        <path d="M211 54h-14v26m152-26h14v26m-166 70v25h14m152-25v25h-14" stroke="#7ca3ba"/>
      </g>
      <g v-if="kind!=='MICRO_EXPRESSION_ONLY'" :transform="kind==='COMPREHENSIVE'?'translate(115 0)':''" stroke="#315b80" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
        <path d="m232 171-28-37c-9-13 7-26 18-14l15 17V65c0-17 22-17 22 0v40-66c0-17 23-17 23 0v66-55c0-17 23-17 23 0v58-38c0-17 23-17 23 0v79c0 31-15 57-49 57-21 0-36-13-47-35Z" fill="#fff"/>
        <path d="M231 218h96M350 107v38m-16-19h32" stroke="#74a397"/>
      </g>
    </svg>
  </div>
</template>
<style scoped>
.assessment-art{aspect-ratio:7/3;width:100%;background:#edf3f9;overflow:hidden}.assessment-art svg{display:block;width:100%;height:100%}
</style>
