import {ElMessageBox} from 'element-plus'
import {http} from '@/api/client'
export interface PendingTraining{id:string;kind:'piano'|'pose'|'guided';label:string;started_at:string;can_clear:boolean}
export const activeTraining={
 async list(id:string):Promise<PendingTraining[]>{return (await http.get(`/patients/${id}/training/active`)).data},
 async clear(id:string,row:PendingTraining){await http.delete(`/patients/${id}/training/active/${row.kind}/${row.id}`);if(typeof window!=='undefined')window.dispatchEvent(new Event('training-active-changed'))},
}
export async function resolvePendingTraining(id:string,signal:AbortSignal){
 const rows=await activeTraining.list(id)
 if(signal.aborted||!rows.length)return
 if(rows.some(row=>!row.can_clear))throw new Error('今天还有其他账号进行中的训练，请先由原账号结束或清除。')
 let accepted=false
 const onAbort=()=>ElMessageBox.close()
 signal.addEventListener('abort',onAbort,{once:true})
 try{await ElMessageBox.confirm(`今天还有 ${rows.length} 项进行中的训练：${rows.map(r=>r.label).join('、')}。请返回完成，或清除后再开始。清除不会删除已完成结果。`,'进行中的训练',{confirmButtonText:'清除并继续',cancelButtonText:'返回完成训练',closeOnClickModal:false});accepted=true}catch{/* Keep the existing training. */}finally{signal.removeEventListener('abort',onAbort)}
 if(signal.aborted)return
 if(!accepted)throw new Error('已保留进行中的训练，请完成或清除后再开始。')
 for(const row of rows){if(signal.aborted)return;await activeTraining.clear(id,row)}
}
