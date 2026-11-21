<script setup lang="ts">
import { Download } from '@element-plus/icons-vue'
defineProps<{ compact?: boolean }>()
const apkUrl = `${import.meta.env.BASE_URL}assets/app-releases/0.1.73-75/qinban-0.1.73-android-universal.apk`
</script>

<template>
  <a class="app-download" :class="{ 'is-compact': compact }" :href="apkUrl"
    download="qinban-0.1.73-android-universal.apk" :title="$t('App下载')">
    <el-icon aria-hidden="true"><Download /></el-icon>
    <span>{{ $t('App下载') }}</span>
  </a>
</template>

<style scoped>
.app-download { display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:44px; padding:10px 18px; border:1px solid #cbdcc9; border-radius:10px; background:#f1f6ef; color:#365b3d; font-size:15px; font-weight:600; line-height:1.4; text-decoration:none; transition:background .18s ease,box-shadow .18s ease,transform .18s ease; }
.app-download:hover { background:#e4efdf; box-shadow:0 3px 10px #365b3d18; transform:translateY(-1px); }
.app-download:active { background:#d8e8d1; transform:scale(.97); box-shadow:none; }
.app-download:focus-visible { outline:3px solid var(--pd-primary); outline-offset:3px; }
.app-download.is-compact { flex-direction:column; gap:4px; padding:8px 2px; font-size:12px; }
@media (prefers-reduced-motion:reduce) { .app-download { transition:none; } .app-download:hover,.app-download:active { transform:none; } }
</style>
