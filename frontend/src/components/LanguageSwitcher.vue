<script setup lang="ts">
import { locale, setLocale, t } from '@/i18n'
</script>
<template>
  <el-button text class="language-switch" :aria-label="t(locale === 'en' ? '切换为中文' : '切换为英文')" @click="setLocale(locale === 'en' ? 'zh-CN' : 'en')">
    <span aria-hidden="true" class="language-icon">文/A</span><span>{{ locale === 'en' ? '中文' : 'English' }}</span>
  </el-button>
</template>
<style scoped>
.language-switch{min-height:44px;margin:0;padding:8px;flex:none;white-space:nowrap;font-size:13px;}
.language-icon{font-size:12px;margin-right:5px;color:var(--pd-text-secondary);}
</style>
