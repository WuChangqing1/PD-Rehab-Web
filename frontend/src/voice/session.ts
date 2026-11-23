export interface Capture {start(send:(data:ArrayBuffer)=>void,onLimit:()=>void):void;flush():Promise<void>;close():void}
export interface Channel {send(data:ArrayBuffer):void;finish():Promise<void>;close():void}
export interface SpeechState {phase:'idle'|'connecting'|'listening'|'finishing'|'error';text:string;error:string}
interface Dependencies {
 capture(signal:AbortSignal):Promise<Capture>
 channel(text:(text:string)=>void,fail:()=>void,signal:AbortSignal):Promise<Channel>
}
export class SpeechSession {
 private generation=0
 private capture:Capture|null=null
 private channel:Channel|null=null
 private abort:AbortController|null=null
 private timer:ReturnType<typeof setTimeout>|null=null
 private baseline=''
 state:SpeechState={phase:'idle',text:'',error:''}
 private deps:Dependencies
 private changed:(state:SpeechState)=>void
 constructor(deps:Dependencies,changed:(state:SpeechState)=>void){this.deps=deps;this.changed=changed}
 get busy(){return ['connecting','listening','finishing'].includes(this.state.phase)}
 private publish(phase:SpeechState['phase'],error=''){this.state={...this.state,phase,error};this.changed(this.state)}
 private release(){
  this.abort?.abort();this.abort=null
  if(this.timer)clearTimeout(this.timer);this.timer=null
  this.capture?.close();this.capture=null;this.channel?.close();this.channel=null
 }
 private fail(){this.generation++;this.release();this.publish('error','语音输入中断，请检查网络或麦克风后重试。')}
 async start(text:string){
  if(this.busy)return
  const id=++this.generation;this.baseline=text;this.state={phase:'connecting',text,error:''};this.changed(this.state)
  const abort=this.abort=new AbortController()
  try{
   const capture=await this.deps.capture(abort.signal)
   if(id!==this.generation){capture.close();return}this.capture=capture
   const channel=await this.deps.channel(part=>{
    if(id===this.generation){this.state={...this.state,text:(this.baseline+part).slice(0,3000)};this.changed(this.state)}
   },()=>{if(id===this.generation)this.fail()},abort.signal)
   if(id!==this.generation){channel.close();return}this.channel=channel
   capture.start(data=>{try{channel.send(data)}catch{if(id===this.generation)this.fail()}},()=>void this.stop())
   this.publish('listening');this.timer=setTimeout(()=>void this.stop(),60000)
  }catch{if(id===this.generation)this.fail()}
 }
 async stop(){
  if(this.state.phase!=='listening')return
  const id=this.generation;this.publish('finishing')
  if(this.timer)clearTimeout(this.timer);this.timer=null
  try{
   await this.capture?.flush();this.capture?.close();this.capture=null
   if(id!==this.generation)return
   await this.channel?.finish()
   if(id!==this.generation)return
   this.generation++;this.release();this.publish('idle')
  }catch{if(id===this.generation)this.fail()}
 }
 cancel(){
  if(!this.busy)return
  this.generation++;this.release();this.state={phase:'idle',text:this.baseline,error:''};this.changed(this.state)
 }
}
