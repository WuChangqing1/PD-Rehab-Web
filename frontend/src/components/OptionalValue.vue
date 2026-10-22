<script setup lang="ts">
import {displayOptionalValue} from '@/utils/format'
defineProps<{value:unknown;localize?:boolean}>()
</script>
<template><span :class="{'pd-missing':displayOptionalValue(value)==='—'}">{{ localize ? $t(displayOptionalValue(value)) : displayOptionalValue(value) }}</span></template>
