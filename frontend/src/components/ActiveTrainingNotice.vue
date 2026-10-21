<script setup lang="ts">
import {ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {ElMessageBox} from 'element-plus'
import {activeTraining,type PendingTraining} from '@/training/activeTraining'
import {notifyError} from '@/api/client'
const props=defineProps<{patientId:string|null}>()
const rows=ref<PendingTraining[]>([]),busy=ref(false)
let request=0
async function load(){const token=++request,id=props.patientId;rows.value=[];if(!id)return;try{const data=await activeTraining.list(id);if(token===request)rows.value=data}catch(e){if(token===request)notifyError(e,'无法读取进行中的训练。')}}
async function clear(row:PendingTraining){
 const id=props.patientId;if(!id||busy.value)return
 try{await ElMessageBox.confirm(`清除进行中的${row.label}？已采集数据会保留，但本次不会作为已完成结果。`,'清除本次训练',{confirmButtonText:'确认清除',cancelButtonText:'取消',type:'warning'})}catch{return}
 if(id!==props.patientId)return
 busy.value=true;try{await activeTraining.clear(id,row);await load()}catch(e){notifyError(e,'清除失败，请重试。')}finally{busy.value=false}
}
watch(()=>props.patientId,load,{immediate:true})
onMounted(()=>window.addEventListener('training-active-changed',load))
onBeforeUnmount(()=>{++request;window.removeEventListener('training-active-changed',load)})
</script>
<template>
 <section v-if="rows.length" class="pending-training pd-card" aria-label="进行中的训练">
  <h2>进行中的训练</h2>
  <div v-for="row in rows" :key="row.id"><span>{{row.label}}</span><el-button type="danger" plain :disabled="!row.can_clear" :loading="busy" @click="clear(row)">清除本次训练</el-button></div>
 </section>
</template>
<style scoped>
.pending-training{padding:20px;margin-bottom:20px}.pending-training h2{font-size:18px;margin:0 0 12px}.pending-training>div{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 0}
</style>
