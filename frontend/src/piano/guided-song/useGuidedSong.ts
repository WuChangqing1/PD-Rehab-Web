import {resolvePendingTraining} from '@/training/activeTraining'
import { API_BASE, TOKEN_STORAGE_KEY } from '@/api/client'
import { computed, onBeforeUnmount, ref, shallowRef, triggerRef, watch } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import { useTrainingStartGate } from '@/composables/useTrainingStartGate'
import { useTaskModeStore } from '@/stores/taskMode'
import { usePatientContextStore } from '@/stores/patientContext'
import { PianoEngine } from '@/piano/engine'
import type { Patient } from '@/types'
import { GuidedSongMachine } from './machine'
import { TWO_TIGERS, SEVEN_KEYS, DIFFICULTY_BPM, KEYBOARD_LETTERS } from './song'
import { renderPerformanceAudio } from './audio'
import { songApi, type SongSession } from './api'
import { useLiveEmotion } from '@/emotion/useLiveEmotion'

export function useGuidedSong(){
 const route=useRoute(),task=useTaskModeStore(),patientStore=usePatientContextStore()
 const engine=new PianoEngine(),machine=shallowRef(new GuidedSongMachine())
 const patient=ref<Patient|null>(patientStore.currentPatient),hand=ref<'LEFT'|'RIGHT'>('RIGHT')
 const difficulty=ref<keyof typeof DIFFICULTY_BPM>('BEGINNER'),consent=ref(false),simulationDemo=ref(false)
 const live=useLiveEmotion(),active=ref(false),launching=ref(false),busy=ref(false),error=ref(''),hint=ref(''),announcement=ref('')
 const target=ref<number|null>(null),pressed=ref(new Set<number>()),wrong=ref<number|null>(null)
 const session=ref<SongSession|null>(null),audioUrl=ref(''),audioElement=ref<HTMLAudioElement|null>(null)
 const pendingCancellation=ref(false)
 const paused=ref(false),history=ref<SongSession[]>([]),saved=ref(false)
 let generation=0,startPerf=0,raf=0,saveTimer=0,feedbackTimer=0,announcementTimer=0,requestId='',demoSegment:1|2=1,demoElapsed=0,demoStart=0
 let demoTimeline:Array<{midi:number;offset:number;duration:number}>=[],demoDuration=0
 let saveQueue:Promise<unknown>=Promise.resolve(),lastSavedCount=0,pressCounter=0,suppressAdvance=false
 const sounding=new Map<string,{index:number;pressId:string;scored:boolean;note:ReturnType<PianoEngine['play']>}>()
 const now=()=>Math.round(performance.now()-startPerf)
 const publish=()=>triggerRef(machine)
 const isPlay=computed(()=>machine.value.state.endsWith('_PLAY'))
 const isDemo=computed(()=>machine.value.state.endsWith('_DEMO'))
 const segment=computed(()=>machine.value.state.includes('_2_')||['MERGING_AUDIO','PLAYBACK','COMPLETED'].includes(machine.value.state)?2:1)
 const state=computed(()=>machine.value.state)
 const progress=computed(()=>{const metrics=machine.value.metrics();return metrics.completed_notes+metrics.skip_count})
 function releaseAll(){suppressAdvance=true;try{for(const id of [...sounding.keys()])up(id)}finally{suppressAdvance=false};pressed.value=new Set();engine.stopAll()}
 function setAudio(blob:Blob){if(audioUrl.value)URL.revokeObjectURL(audioUrl.value);audioUrl.value=URL.createObjectURL(blob)}
 function announce(text:string){announcement.value=text;clearTimeout(announcementTimer);announcementTimer=window.setTimeout(()=>announcement.value='',1600)}
 function stopMedia(){cancelAnimationFrame(raf);clearInterval(saveTimer);releaseAll();live.stop();audioElement.value?.pause()}
 async function exitImmersion(){task.exit();try{screen.orientation?.unlock()}catch{};if(document.fullscreenElement)try{await document.exitFullscreen()}catch{}}
 async function requestImmersion(){try{await document.documentElement.requestFullscreen?.();const orientation=screen.orientation as ScreenOrientation & {lock?:(v:string)=>Promise<void>};await orientation.lock?.('landscape')}catch{/* Viewport fallback remains operable. */}}
 function syncTarget(){target.value=machine.value.currentNote?(SEVEN_KEYS as readonly number[]).indexOf(machine.value.currentNote.midi):null;publish()}
 async function loadContext(){const id=route.query.patientId;if(typeof id==='string'){const run=generation;const resolved=await patientStore.fetchPatient(id,true);if(run!==generation||active.value||gate.busy.value)return;patient.value=resolved};await loadHistory()}
 async function loadHistory(){const id=patient.value?.id??patientStore.currentPatientId;if(!id)return;try{history.value=await songApi.history(id)}catch{error.value='暂时无法读取曲目历史，请检查网络后重试。'}}
 const gate=useTrainingStartGate({
  bind:async(p,signal)=>{if(!signal.aborted)patient.value=p},
  prepare:async(_p,signal)=>{
   await resolvePendingTraining(_p.id,signal);if(signal.aborted)return
   machine.value.transition('PREPARING',0);publish();await engine.load()
   if(signal.aborted)return
   if(!SEVEN_KEYS.every(m=>engine.has(m)))throw new Error('钢琴音源未准备完成，请刷新后重试。')
   machine.value.transition('COUNTDOWN',0);publish()
  },start:()=>{void launch()}
 })
 watch(()=>gate.state.error,message=>{if(message&&!active.value){machine.value.fail(session.value?now():0);publish();live.stop();void exitImmersion()}})
 function begin(){
  if(gate.busy.value||launching.value||active.value||pendingCancellation.value)return
  error.value='';saved.value=false;session.value=null;startPerf=0;paused.value=false;target.value=null;pressed.value=new Set();wrong.value=null;audioElement.value?.pause();if(audioUrl.value)URL.revokeObjectURL(audioUrl.value);audioUrl.value='';machine.value=new GuidedSongMachine();requestId=crypto.randomUUID()
  // Unlock on the gesture itself, before patient/network work consumes activation.
  void engine.unlock().catch(()=>{error.value='请允许音频播放后重试。'})
  void requestImmersion();gate.requestStart()
 }
 function cancelStart(){generation++;gate.cancelStart();machine.value.cancel(session.value?now():0);publish();live.stop();void exitImmersion()}
 function changePatient(){generation++;machine.value=new GuidedSongMachine();gate.changePatient()}
 async function launch(){
  if(launching.value||!patient.value)return
  const run=++generation;launching.value=true;error.value=''
  try{
   startPerf=performance.now()
   const created=await songApi.create({patient_id:patient.value.id,client_request_id:requestId,song_id:TWO_TIGERS.song_id,song_version:'1',selected_hand:hand.value,initial_difficulty:difficulty.value,input_source:route.query.selftest==='1'||simulationDemo.value?'SYNTHETIC_SELFTEST':'HUMAN_KEYBOARD',is_simulation:simulationDemo.value,client_clock_origin_epoch_ms:Date.now()})
   if(run!==generation){session.value=created;pendingCancellation.value=true;try{await songApi.cancel(created.id);pendingCancellation.value=false}catch{error.value='取消状态尚未同步，请恢复网络后重试。'}return}
   session.value=created;active.value=true;task.enter();lastSavedCount=0
   live.consent.value=consent.value
   if(consent.value)void live.start(created.id,created.patient_id,simulationDemo.value)
   saveTimer=window.setInterval(()=>{if(machine.value.events.length!==lastSavedCount)void saveRaw().catch(()=>{})},2500)
   demo(1)
  }catch{error.value='无法建立训练会话，请检查网络后重试。';void exitImmersion()}
  finally{launching.value=false}
 }
 function demo(which:1|2){
  releaseAll();paused.value=false;demoSegment=which;demoElapsed=0
  const bpm=which===1?session.value!.segment_1_bpm:session.value!.segment_2_bpm
  let offset=0;demoTimeline=TWO_TIGERS.segments[which-1]!.notes.map(note=>{const duration=note.beats*60000/bpm;const item={midi:note.midi,offset,duration};offset+=duration;return item});demoDuration=offset
  machine.value.transition(which===1?'SEGMENT_1_DEMO':'SEGMENT_2_DEMO',now());publish()
  announce(which===1?'跟随示范试弹一次':'第一段已完成，跟随示范练习后半段')
  hint.value='跟随发光琴键试弹，不计成绩；示范结束后再正式跟弹。'
  scheduleDemo()
 }
 function scheduleDemo(){
  const ctx=engine.ensureContext();demoStart=ctx.currentTime-demoElapsed/1000+.8
  for(const note of demoTimeline){if(note.offset+note.duration<=demoElapsed)continue
   const when=demoStart+Math.max(note.offset,demoElapsed)/1000
   const sound=engine.play(note.midi,engine.audioTimeToPerformance(when))
   if(sound){const end=demoStart+(note.offset+note.duration)/1000;sound.gain.gain.cancelScheduledValues(sound.audioTime+.01);sound.gain.gain.setValueAtTime(.65,sound.audioTime+.01);sound.gain.gain.setTargetAtTime(.0001,end,.08)}
  }
  function frame(){
   if(!active.value||paused.value||!isDemo.value)return
   demoElapsed=Math.max(0,(ctx.currentTime-demoStart)*1000)
   const current=demoTimeline.find(n=>demoElapsed>=n.offset&&demoElapsed<n.offset+n.duration)
   target.value=current?(SEVEN_KEYS as readonly number[]).indexOf(current.midi):null
   if(demoElapsed>=demoDuration){releaseAll();machine.value.transition(demoSegment===1?'SEGMENT_1_PLAY':'SEGMENT_2_PLAY',now());hint.value='示范完毕，现在按提示正式弹奏';announce(hint.value);syncTarget();return}
   raf=requestAnimationFrame(frame)
  }
  raf=requestAnimationFrame(frame)
 }
 function down(index:number,id:string){
  if((!isPlay.value&&!isDemo.value)||paused.value||sounding.has(id)||pressed.value.has(index))return
  const midi=SEVEN_KEYS[index];if(midi===undefined)return
  const pressId=`${id}-${++pressCounter}`
  if(isDemo.value){sounding.set(id,{index,pressId,scored:false,note:engine.play(midi)});pressed.value=new Set([...pressed.value,index]);return}
  const result=machine.value.down(midi,pressId,now());if(!result.accepted)return
  sounding.set(id,{index,pressId,scored:true,note:engine.play(midi)});pressed.value=new Set([...pressed.value,index])
  wrong.value=result.correct?null:index;hint.value=result.correct?'按键正确':'按键不符，请跟随发光琴键再试一次'
  clearTimeout(feedbackTimer);feedbackTimer=window.setTimeout(()=>wrong.value=null,450)
  syncTarget()
 }
 function up(id:string){
  const held=sounding.get(id);if(!held)return
  sounding.delete(id);const keys=new Set(pressed.value);keys.delete(held.index);pressed.value=keys
  if(held.note){const t=engine.ensureContext().currentTime;held.note.gain.gain.cancelScheduledValues(t);held.note.gain.gain.setTargetAtTime(.0001,t,.08)}
  if(held.scored){machine.value.up(held.pressId,now());syncTarget();if(!suppressAdvance)advance()}
 }
 function skip(){if(!isPlay.value||paused.value)return;releaseAll();machine.value.skip(now());hint.value='已记录跳过';syncTarget();advance()}
 function togglePause(){
  if(!isPlay.value&&!isDemo.value)return
  if(!paused.value){releaseAll();cancelAnimationFrame(raf);if(!isPlay.value&&!isDemo.value){advance();return};if(isPlay.value)machine.value.pause(now());paused.value=true;hint.value='已暂停，准备好后继续'}
  else{paused.value=false;if(isPlay.value){machine.value.resume(now());hint.value='轮到您弹奏';syncTarget()}else scheduleDemo()}
  publish()
 }
 function advance(){
  if(machine.value.state==='SEGMENT_1_RESULT'&&!busy.value)void nextSegment()
  if(machine.value.state==='MERGING_AUDIO'&&!busy.value)void finish()
 }
 async function saveRaw(){
  const id=session.value?.id;if(!id)return
  const events=structuredClone(machine.value.events)
  const run=generation
  const next=saveQueue.catch(()=>{}).then(()=>songApi.events(id,events));saveQueue=next
  try{const result=await next;if(run===generation){lastSavedCount=events.length;session.value=result}return result}
  catch(e){if(run===generation)error.value='网络异常，按键记录仍在当前页面；请保持页面打开并重试保存。';throw e}
 }
 async function nextSegment(){
  if(busy.value)return;busy.value=true;const run=generation,id=session.value!.id
  try{await saveRaw();if(run!==generation)return;const result=await songApi.second(id);if(run!==generation)return;session.value=result;error.value='';demo(2)}
  catch{if(run===generation){hint.value='第一段已完成，请恢复网络后继续';error.value='暂时无法保存第一段，请点击重试。'}}finally{if(run===generation)busy.value=false}
 }
 async function renderAudio(){
  if(!session.value)return
  const run=generation,id=session.value.id,events=structuredClone(machine.value.events)
  const result=await renderPerformanceAudio(events,midi=>engine.getBuffer(midi))
  if(run!==generation)return
  setAudio(result.blob)
  try{const updated=await songApi.upload(id,result.blob);if(run===generation)session.value=updated}catch{if(run===generation)error.value='训练记录已保存，音频上传失败；可下载本次演奏或重试音频保存。'}
 }
 async function finish(){
  if(busy.value)return;busy.value=true;const run=generation,id=session.value!.id
  const cameraStatus=live.status.value
  void songApi.emotion(id,consent.value,cameraStatus).catch(()=>{})
  live.stop();clearInterval(saveTimer);hint.value='正在保存训练记录…'
  try{
   await saveRaw();if(run!==generation)return;const result=await songApi.complete(id);if(run!==generation)return
   session.value=result;saved.value=true;error.value='';hint.value='音频合成中…'
   try{await renderAudio()}catch{error.value='训练记录已保存，演奏音频生成失败，可以重新生成。'}
   if(run!==generation)return
   machine.value.transition('PLAYBACK',now());publish();hint.value='完整训练已完成';active.value=false;await exitImmersion();await loadHistory()
   requestAnimationFrame(()=>{void audioElement.value?.play().catch(()=>{hint.value='点击“播放本次演奏”即可收听'})})
  }catch{if(run===generation)error.value='训练尚未保存，请保持页面打开并重试。'}finally{if(run===generation)busy.value=false}
 }
 async function retry(){if(pendingCancellation.value){await end();return};if(state.value==='SEGMENT_1_RESULT')await nextSegment();else if(state.value==='MERGING_AUDIO')await finish();else if(saved.value){busy.value=true;try{await engine.load();error.value='';await renderAudio()}catch{error.value='音频暂时无法生成，请稍后重试。'}finally{busy.value=false}}else await saveRaw().catch(()=>{})}
 async function end(){
  const id=session.value?.id;generation++;cancelStart();stopMedia();active.value=false;busy.value=true;error.value=''
  if(!saved.value&&id){
   pendingCancellation.value=true
   try{
    await saveQueue.catch(()=>{})
    const latest=await songApi.events(id,structuredClone(machine.value.events))
    session.value=latest
    if(latest.status==='COMPLETED')saved.value=true
    else session.value=await songApi.cancel(id)
    pendingCancellation.value=false
   }catch{
    // Completion may commit between the last snapshot and cancellation.
    try{const latest=await songApi.get(id);if(latest.status==='COMPLETED'){session.value=latest;saved.value=true;pendingCancellation.value=false}}catch{}
    if(pendingCancellation.value)error.value='已结束本地训练，但取消状态尚未同步；请恢复网络后重试保存。'
   }
  }
  await exitImmersion();await loadHistory();busy.value=false
 }
 async function viewHistory(row:SongSession){
  if(active.value||busy.value||pendingCancellation.value)return;generation++;busy.value=true;error.value=''
  try{session.value=await songApi.get(row.id);machine.value=new GuidedSongMachine();machine.value.events.push(...session.value.events);saved.value=true
   if(audioUrl.value)URL.revokeObjectURL(audioUrl.value);audioUrl.value=''
   if(session.value.audio_url)setAudio(await songApi.audio(row.id))
  }catch{error.value='无法读取训练详情，请稍后重试。'}finally{busy.value=false}
 }
 function onKeyDown(e:KeyboardEvent){if(!active.value||e.repeat||e.ctrlKey||e.metaKey||e.altKey)return;if((e.target as HTMLElement)?.closest('input,select,textarea'))return;const index=KEYBOARD_LETTERS.findIndex(letter=>`Key${letter}`===e.code);if(index>=0){e.preventDefault();down(index,`key-${e.code}`)}}
 function onKeyUp(e:KeyboardEvent){up(`key-${e.code}`)}
 function playbackEnded(){if(machine.value.state==='PLAYBACK'){machine.value.transition('COMPLETED',now());publish()}hint.value='播放完成，可再次收听'}
 function onHidden(){if(document.hidden&&active.value&&!paused.value)togglePause()}
 function onPageHide(){
  if(!active.value)return
  generation++;machine.value.cancel(now());stopMedia();active.value=false;task.exit()
  const id=session.value?.id;if(!id)return
  const body=JSON.stringify({events:machine.value.events})
  void fetch(`${API_BASE}/guided-song/sessions/${id}/cancel`,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${localStorage.getItem(TOKEN_STORAGE_KEY)||''}`},body:body.length<48000?body:undefined,keepalive:true}).catch(()=>{})
 }
 function onBlur(){if(active.value&&!paused.value)togglePause()}
 window.addEventListener('pagehide',onPageHide);window.addEventListener('keydown',onKeyDown);window.addEventListener('keyup',onKeyUp);window.addEventListener('blur',onBlur);document.addEventListener('visibilitychange',onHidden)
 onBeforeRouteLeave(async()=>{if(active.value||launching.value){if(!window.confirm('离开将结束本次训练。确定离开？'))return false;await end()}else cancelStart()})
 onBeforeUnmount(()=>{generation++;stopMedia();gate.cancelStart();void exitImmersion();void engine.close();clearTimeout(feedbackTimer);clearTimeout(announcementTimer);if(audioUrl.value)URL.revokeObjectURL(audioUrl.value);window.removeEventListener('pagehide',onPageHide);window.removeEventListener('keydown',onKeyDown);window.removeEventListener('keyup',onKeyUp);window.removeEventListener('blur',onBlur);document.removeEventListener('visibilitychange',onHidden)})
 return{machine,state,patient,hand,difficulty,consent,simulationDemo,live,active,launching,busy,error,hint,announcement,target,pressed,wrong,session,audioUrl,audioElement,paused,history,saved,pendingCancellation,gate,isPlay,isDemo,segment,progress,begin,cancelStart,changePatient,down,up,skip,togglePause,retry,end,loadContext,loadHistory,viewHistory,playbackEnded}
}
