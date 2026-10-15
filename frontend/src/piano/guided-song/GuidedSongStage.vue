<script setup lang="ts">
import SevenKeyKeyboard from './SevenKeyKeyboard.vue'
import WaveStaffOverlay from './WaveStaffOverlay.vue'
defineProps<{target:number|null;pressed:Set<number>;error:number|null;disabled?:boolean}>()
defineEmits<{down:[index:number,id:string];up:[id:string]}>()
</script>
<template><div class="guided-song-stage"><SevenKeyKeyboard :target="target" :pressed="pressed" :error="error" :disabled="disabled" @down="(i,id)=>$emit('down',i,id)" @up="$emit('up',$event)"/><WaveStaffOverlay :target="target" :pressed="pressed"/></div></template>
<style scoped>.guided-song-stage{position:relative;flex:1;min-height:200px;width:100%;isolation:isolate;overflow:hidden;border-radius:18px;box-shadow:0 12px 36px #18325515;border:1px solid #c5d3e3;background:#fff}</style>
