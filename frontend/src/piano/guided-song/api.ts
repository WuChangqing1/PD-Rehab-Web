import { http } from '@/api/client'
import type { SongEvent } from './machine'
export interface SongSession {
 id:string; patient_id:string; status:string; selected_hand:string; song_id:string; song_version:string
 initial_difficulty:string; segment_1_difficulty:string; segment_2_difficulty:string; final_difficulty:string
 bpm:number; segment_1_bpm:number; segment_2_bpm:number
 metrics:Record<string,number|null>; notes:Array<Record<string,unknown>>; events:SongEvent[]
 audio_url:string|null; audio_duration_ms:number|null; audio_source:string|null
 difficulty_adjustment:Record<string,unknown>|null; metadata:Record<string,unknown>
 emotion_analysis_status:string; emotion_source:string|null; created_at:string
}
const base='/guided-song/sessions'
export const songApi={
 async create(body:Record<string,unknown>){return (await http.post<SongSession>(base,body)).data},
 async events(id:string,events:SongEvent[]){return(await http.post<SongSession>(`${base}/${id}/events`,{events})).data},
 async emotion(id:string,consent:boolean,status:string){return(await http.post<SongSession>(`${base}/${id}/emotion-status`,{consent,status})).data},
 async second(id:string){return(await http.post<SongSession>(`${base}/${id}/segment-2`,{})).data},
 async complete(id:string){return(await http.post<SongSession>(`${base}/${id}/complete`,{})).data},
 async cancel(id:string){return(await http.post<SongSession>(`${base}/${id}/cancel`)).data},
 async get(id:string){return(await http.get<SongSession>(`${base}/${id}`)).data},
 async history(patientId:string){return(await http.get<{items:SongSession[]}>(`/patients/${patientId}/guided-song/history`)).data.items},
 async upload(id:string,blob:Blob){const data=new FormData();data.append('file',blob,'performance.wav');data.append('render_version','1');return(await http.post<SongSession>(`${base}/${id}/audio`,data,{headers:{'Content-Type':'multipart/form-data'}})).data},
 async audio(id:string){return(await http.get<Blob>(`${base}/${id}/audio`,{responseType:'blob'})).data},
}
