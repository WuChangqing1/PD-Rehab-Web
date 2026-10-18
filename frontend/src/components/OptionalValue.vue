<script setup lang="ts">
import {displayOptionalValue} from '@/utils/format'
defineProps<{value:unknown}>()
</script>
<template><span :class="{'pd-missing':displayOptionalValue(value)==='—'}">{{displayOptionalValue(value)}}</span></template>
