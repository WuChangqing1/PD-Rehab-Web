export interface VoiceState {status:'idle'|'requesting'|'recording'|'ready'|'error';blob:Blob|null;error:string}
export interface VoiceDependencies {media:()=>Promise<MediaStream>;recorder:(stream:MediaStream)=>MediaRecorder}
export class VoiceRecorder {
 state:VoiceState={status:'idle',blob:null,error:''}
 private generation=0
 private stream:MediaStream|null=null
 private recording:MediaRecorder|null=null
 private timer:ReturnType<typeof setTimeout>|null=null
 private deps:VoiceDependencies
 private changed:(state:VoiceState)=>void
 constructor(deps:VoiceDependencies,changed:(state:VoiceState)=>void=()=>{}){this.deps=deps;this.changed=changed}
 private emit(){this.changed({...this.state})}
 private release(){if(this.timer)clearTimeout(this.timer);this.timer=null;this.stream?.getTracks().forEach(t=>t.stop());this.stream=null}
 async start(){
  this.cancel();const generation=++this.generation
  this.state={status:'requesting',blob:null,error:''};this.emit()
  try {
   const stream=await this.deps.media()
   if(generation!==this.generation){stream.getTracks().forEach(t=>t.stop());return}
   this.stream=stream;const recorder=this.deps.recorder(stream);this.recording=recorder
   const chunks:Blob[]=[];let size=0
   recorder.ondataavailable=e=>{if(generation===this.generation&&e.data.size){chunks.push(e.data);size+=e.data.size;if(size>5*1024*1024)this.stop()}}
   recorder.onstop=()=>{if(generation!==this.generation)return;this.release();this.recording=null;const blob=new Blob(chunks,{type:recorder.mimeType||'audio/webm'});this.state=blob.size?{status:'ready',blob,error:''}:{status:'error',blob:null,error:'未录到声音，请重新录制。'};this.emit()}
   recorder.onerror=()=>{if(generation!==this.generation)return;this.cancel();this.state.error='录音失败，请重新录制。';this.state.status='error';this.emit()}
   recorder.start(1000);this.state.status='recording';this.emit();this.timer=setTimeout(()=>this.stop(),60_000)
  }catch(error){
   if(generation!==this.generation)return
   this.release();this.recording=null
   const name=(error as {name?:string})?.name
   this.state={status:'error',blob:null,error:name==='NotAllowedError'?'麦克风未授权，请允许访问后重试。':name==='NotFoundError'?'未找到麦克风，请检查设备。':'无法开始录音，请检查浏览器和麦克风。'};this.emit()
  }
 }
 stop(){if(this.recording?.state==='recording'){this.recording.stop();this.release()}}
 cancel(){
  ++this.generation;const recorder=this.recording;this.recording=null
  if(recorder){recorder.ondataavailable=null;recorder.onstop=null;recorder.onerror=null;try{if(recorder.state!=='inactive')recorder.stop()}catch{/* already stopped */}}
  this.release();this.state={status:'idle',blob:null,error:''};this.emit()
 }
}
