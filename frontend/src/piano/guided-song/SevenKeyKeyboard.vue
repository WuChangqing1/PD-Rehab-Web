<script setup lang="ts">
import { onBeforeUnmount } from 'vue'
import { KEYBOARD_LETTERS } from './song'
const props=defineProps<{target:number|null; pressed:Set<number>; error:number|null; disabled?:boolean;hand?:'LEFT'|'RIGHT'}>()
const emit=defineEmits<{down:[index:number,id:string];up:[id:string]}>()
const names=['C','D','E','F','G','A','B']
const pointers=new Map<number,string>()
function down(index:number,e:PointerEvent){
 if(props.disabled||pointers.has(e.pointerId))return
 e.preventDefault();const id=`pointer-${e.pointerId}`;pointers.set(e.pointerId,id)
 ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);emit('down',index,id)
}
function up(e:PointerEvent){const id=pointers.get(e.pointerId);if(!id)return;pointers.delete(e.pointerId);emit('up',id)}
onBeforeUnmount(()=>{for(const id of pointers.values())emit('up',id);pointers.clear()})
</script>
<template>
 <div class="seven-keyboard" role="group" :aria-label="$t('七键钢琴')">
  <button v-for="(name,index) in names" :key="name" type="button" class="seven-key" :data-key="index" :data-hand="hand" :data-key-code="KEYBOARD_LETTERS[index]"
   :aria-label="$t(`第 ${$t(index+1)} 键，${$t(name)}，键盘 ${$t(KEYBOARD_LETTERS[index])}`)" :aria-pressed="pressed.has(index)" :disabled="disabled"
   :class="{'is-target':target===index,'is-pressed':pressed.has(index),'is-error':error===index,'hand-left':hand==='LEFT','hand-right':hand==='RIGHT'}"
   @pointerdown="down(index,$event)" @pointerup="up" @pointercancel="up" @lostpointercapture="up"
   @keydown.enter.prevent="!$event.repeat&&emit('down',index,`accessible-${index}`)" @keyup.enter="emit('up',`accessible-${index}`)"
   @keydown.space.prevent="!$event.repeat&&emit('down',index,`accessible-${index}`)" @keyup.space.prevent="emit('up',`accessible-${index}`)">
   <span v-if="hand" class="key-hand">{{ $t(hand==='LEFT'?'左手':'右手') }}</span>
   <span class="key-letter" aria-hidden="true">{{ $t(KEYBOARD_LETTERS[index]) }}</span>
  </button>
 </div>
</template>
<style scoped>
.seven-keyboard{position:absolute;inset:0;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:0}
.seven-key{appearance:none;min-width:0;border:0;border-right:1px solid #cbd6e6;border-bottom:8px solid #d3dce8;border-radius:0 0 16px 16px;background:linear-gradient(#fff 0%,#fff 80%,#f1f5fa);touch-action:none;cursor:pointer;transition:background .14s,box-shadow .14s;position:relative}
.seven-key:last-child{border-right:0}.seven-key.is-target{background:linear-gradient(#eef7ff,#d9ecff);box-shadow:inset 0 0 35px #80b8fa70;border-bottom-color:#6fa7e5}
.seven-key.is-pressed{background:linear-gradient(#edfcf5,#a7e5d1);border-bottom-color:#4fbaa0}
.seven-key.is-error{background:linear-gradient(#fff6f3,#f4c8c1);border-bottom-color:#cc867a}
.seven-key:focus-visible{outline:4px solid #305f9e;outline-offset:-6px;z-index:1}
.key-letter{position:absolute;bottom:clamp(16px,5vh,44px);left:0;right:0;font:600 clamp(22px,3.2vw,40px)/1.2 system-ui,sans-serif;color:#425e7b;pointer-events:none}
.seven-key.is-target .key-letter{color:#205b99}.seven-key.is-pressed .key-letter{color:#176650}.seven-key:disabled{opacity:1;cursor:default}
@media(prefers-reduced-motion:reduce){.seven-key{transition:none}}
.seven-key.hand-left { --hand-color:#1D4ED8;--hand-soft:#EFF6FF; }
.seven-key.hand-right { --hand-color:#C2410C;--hand-soft:#FFF7ED; }
.seven-key.is-target { background:var(--hand-soft,#EFF6FF);border-bottom-color:var(--hand-color,#1D4ED8);box-shadow:inset 0 0 0 4px var(--hand-color,#1D4ED8); }
.seven-key.is-target .key-letter { color:var(--hand-color,#1D4ED8); }
.key-hand { position:absolute;bottom:clamp(66px,12vh,106px);left:0;right:0;text-align:center;font-size:clamp(12px,2vw,20px);font-weight:700;color:var(--hand-color,#425e7b); }
</style>
