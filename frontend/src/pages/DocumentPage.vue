<script setup lang="ts">
import {ref,watch,nextTick,onUnmounted} from 'vue'
import {useRoute} from 'vue-router'
import {http,toApiError} from '@/api/client'
import {renderDocument,type HostedDocument} from '@/documents/render'
const route=useRoute(),title=ref('资料阅读'),html=ref(''),error=ref(''),loading=ref(false),pdf=ref('')
let request=0
let assetUrls:string[]=[]
function release(){if(pdf.value)URL.revokeObjectURL(pdf.value);pdf.value='';assetUrls.forEach(x=>URL.revokeObjectURL(x));assetUrls=[]}
watch(()=>route.params.documentId,async value=>{
 const seq=++request;release();html.value='';error.value='';loading.value=true
 try{
  const id=encodeURIComponent(String(value))
  const {data}=await http.get(`/documents/${id}`)
  if(seq!==request)return
  title.value=data.title
  if(data.format==='pdf'){
   const response=await http.get(`/documents/${id}/file`,{responseType:'blob'})
   if(seq!==request)return
   pdf.value=URL.createObjectURL(response.data)
  }else{
   const {data:list}=await http.get<{documents:HostedDocument[]}>('/documents')
   if(seq!==request)return
   const assets:Record<string,string>={}
   await Promise.all((data.assets??[]).map(async (path:string)=>{
    const response=await http.get(`/documents/${id}/assets/${path}`,{responseType:'blob'})
    if(seq!==request)return
    const url=URL.createObjectURL(response.data);assetUrls.push(url);assets[path]=url
   }))
   if(seq!==request)return
   html.value=renderDocument(data.content,data,import.meta.env.BASE_URL,list.documents,assets)
   await nextTick()
   if(route.hash)document.getElementById(decodeURIComponent(route.hash.slice(1)))?.scrollIntoView()
  }
 }catch(e){if(seq===request)error.value=toApiError(e).message}
 finally{if(seq===request)loading.value=false}
},{immediate:true})
onUnmounted(()=>{request++;release()})
</script>
<template><main class="document-page"><a :href="`${$router.options.history.base}/`">返回帕琴律动</a><h1>{{title}}</h1><p v-if="loading">正在加载</p><el-alert v-if="error" :title="error" type="error" :closable="false"/><template v-if="pdf"><a :href="pdf" :download="title+'.pdf'">下载 PDF</a><iframe :src="pdf" title="PDF 文档"/></template><article v-else class="document-body" v-html="html"/></main></template>
<style scoped>
.document-page{max-width:1100px;margin:auto;padding:28px;background:white;min-height:100vh}.document-body{font-size:18px;line-height:1.8;overflow-wrap:anywhere}.document-body :deep(img){max-width:100%;height:auto;display:block;margin:18px auto}.document-body :deep(table){border-collapse:collapse;display:block;overflow:auto;max-width:100%}.document-body :deep(td),.document-body :deep(th){border:1px solid #aeb8b5;padding:10px}.document-body :deep(pre){white-space:pre-wrap;padding:16px;background:#f3f6f4}.document-body :deep(a){text-decoration:underline}.document-page iframe{width:100%;height:80vh;border:1px solid #bbb}@media(max-width:600px){.document-page{padding:18px}}
</style>
