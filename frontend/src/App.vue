<script setup lang="ts">
/**
 * Root component. The router renders either the login page or the main layout,
 * so this stays a thin shell.
 */
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import { locale, pageTitle } from '@/i18n'
const route = useRoute()
const componentLocale = computed(() => locale.value === 'en' ? en : zhCn)
watch([locale, () => route.meta.title], () => { document.title = pageTitle(route.meta.title) }, { immediate: true })
</script>

<template>
  <el-config-provider :locale="componentLocale"><router-view /></el-config-provider>
</template>
