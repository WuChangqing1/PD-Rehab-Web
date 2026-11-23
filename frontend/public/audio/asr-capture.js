// Stateful box-filter resampling; fractional samples carry across worklet blocks.
export class PcmEncoder {
 constructor(rate, emit, maxSamples=960000, onLimit=()=>{}) {
  if(rate<16000)throw new Error('Unsupported sample rate')
  this.ratio=rate/16000;this.emit=emit;this.sum=0;this.weight=0;this.frame=[];this.samples=0;this.maxSamples=maxSamples;this.onLimit=onLimit
 }
 push(samples) {
  for(const value of samples){
   if(this.samples>=this.maxSamples)return
   let left=1
   while(left>1e-9){
    const take=Math.min(left,this.ratio-this.weight)
    this.sum+=value*take;this.weight+=take;left-=take
    if(this.weight>=this.ratio-1e-9){
     const v=Math.max(-1,Math.min(1,this.sum/this.ratio))
     this.frame.push(Math.trunc(v*(v<0?32768:32767)));this.sum=0;this.weight=0
     this.samples++
     if(this.frame.length===1600)this.flush()
     if(this.samples===this.maxSamples){this.flush();this.onLimit();return}
    }
   }
  }
 }
 flush(){
  if(!this.frame.length)return
  const data=new ArrayBuffer(this.frame.length*2), view=new DataView(data)
  this.frame.forEach((v,i)=>view.setInt16(i*2,v,true));this.frame=[];this.emit(data)
 }
}
if(typeof registerProcessor==='function'){
 class Capture extends AudioWorkletProcessor {
  constructor(){super();this.enabled=true;this.encoder=new PcmEncoder(sampleRate,b=>this.port.postMessage(b,[b]),960000,()=>{this.enabled=false;this.port.postMessage('limit')});this.port.onmessage=e=>{if(e.data==='flush'){this.enabled=false;this.encoder.flush();this.port.postMessage('flushed')}}}
  process(inputs){if(this.enabled&&inputs[0]?.[0])this.encoder.push(inputs[0][0]);return true}
 }
 registerProcessor('asr-capture',Capture)
}
