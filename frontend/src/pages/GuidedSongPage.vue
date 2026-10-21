<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import TrainingStartGate from '@/components/TrainingStartGate.vue'
import GuidedSongStage from '@/piano/guided-song/GuidedSongStage.vue'
import { useGuidedSong } from '@/piano/guided-song/useGuidedSong'
import { DIFFICULTY_BPM, KEYBOARD_LETTERS } from '@/piano/guided-song/song'
import { displayPatientName, formatDateTime } from '@/utils/format'
const route=useRoute()
const song=useGuidedSong()
const {state,patient,hand,difficulty,consent,simulationDemo,active,launching,busy,error,hint,announcement,target,pressed,wrong,session,audioUrl,audioElement,paused,history,saved,pendingCancellation,isPlay,isDemo,segment,progress}=song
const isDevelopment=import.meta.env.DEV
const keyPrompt=computed(()=>target.value===null?'准备跟随发光琴键':`${wrong.value!==null?'按键不符，请重试。':''}按 ${KEYBOARD_LETTERS[target.value]} 键，或点击发光琴键`)
const labels:Record<string,string>={BEGINNER:'初级',INTERMEDIATE:'中级',ADVANCED:'高级'}
const camera=computed(()=>({IDLE:'摄像头未启用',STOPPED:'摄像头已关闭',CONSENT_REQUIRED:'摄像头未授权',CONNECTING:'正在连接面部分析',MODEL_NOT_CONFIGURED:'面部分析未配置，仍可正常弹奏',UNAVAILABLE:'面部分析不可用，仍可正常弹奏',STREAMING:'面部视频采集中',SIMULATED:'模拟测试，非真实情绪结果'}[song.live.status.value]??'面部分析不可用'))
const metricRows=[['first_attempt_accuracy','首次尝试准确率','ratio'],['total_attempt_accuracy','总体尝试准确率','ratio'],['completion_rate','完成率','ratio'],['wrong_press_count','错误按键','count'],['skip_count','跳过音符','count'],['mean_response_latency_ms','平均正确响应时延','ms']]
function metric(key:string,kind:string){const value=session.value?.metrics?.[key];if(value===null||value===undefined)return '—';return kind==='ratio'?`${(value*100).toFixed(1)}%`:kind==='ms'?`${Math.round(value)} ms`:String(value)}
onMounted(()=>{void song.loadContext()})
</script>
<template>
 <div v-if="active" class="song-immersive" :data-state="state">
  <header class="song-toolbar">
   <button type="button" class="song-quiet" @click="song.end">结束训练</button>
   <div class="song-title"><strong>两只老虎</strong><span>{{ patient?displayPatientName(patient.name):'' }} · {{ hand==='LEFT'?'左手':'右手' }}任务 · 第 {{ segment }} / 2 段</span></div>
   <span class="song-tempo">{{ labels[segment===1?session!.segment_1_difficulty:session!.segment_2_difficulty] }} · {{ segment===1?session!.segment_1_bpm:session!.segment_2_bpm }} BPM</span>
   <span class="song-count">{{ progress }} / 32</span>
  </header>
  <div class="song-status" aria-live="polite"><strong>{{ paused?'训练已暂停':isDemo?'跟随示范试弹 · 不计成绩':isPlay?'轮到您弹奏':hint }}</strong><span>{{ paused?hint:(isPlay||isDemo)?keyPrompt:hint }}</span></div>

  <GuidedSongStage :target="paused?null:target" :pressed="pressed" :error="wrong" :disabled="(!isPlay&&!isDemo)||paused" @down="song.down" @up="song.up"/>
  <Transition name="song-message"><div v-if="announcement" class="song-announcement">{{ announcement }}</div></Transition>
  <footer class="song-controls">
   <span class="song-camera">{{ camera }}</span>
   <button v-if="isPlay||isDemo" type="button" class="song-quiet" @click="song.togglePause">{{ paused?'继续训练':'暂停' }}</button>
   <button v-if="isPlay" type="button" class="song-quiet" :disabled="paused" @click="song.skip">跳过当前音符</button>
   <button v-if="error&&!busy" type="button" class="song-primary" @click="song.retry">重试保存并继续</button>
  </footer>
  <p v-if="error||song.gate.state.error" role="alert" class="song-error">{{ error||song.gate.state.error }}</p>
 </div>
 <section v-else class="song-page">
  <router-link class="song-back" :to="{path:'/training/piano',query:route.query}">← 钢琴节奏训练</router-link>
  <header class="song-page-heading"><div><h1>曲目跟弹</h1></div></header>
  <p v-if="error||song.gate.state.error" role="alert" class="song-error">{{ error||song.gate.state.error }}</p>
  <button v-if="pendingCancellation" class="song-primary" :disabled="busy" @click="song.retry">{{ busy?'正在同步取消…':'重试同步取消状态' }}</button>
  <section v-if="saved&&session" class="song-result pd-card" aria-label="曲目训练结果">
   <header><div><h2>本次演奏结果</h2><p>{{ labels[session.initial_difficulty] }}开始 · {{ session.selected_hand==='LEFT'?'左手':'右手' }}任务</p></div><span class="song-badge">{{ session.status==='COMPLETED'?'已完成':'已结束' }}</span></header>
   <p v-if="session.metadata?.input_source==='SYNTHETIC_SELFTEST'||session.emotion_source==='SIMULATED'" class="song-notice">此记录含测试或模拟来源，不作为真实临床测量。</p>
   <div class="song-metrics"><article v-for="row in metricRows" :key="row[0]"><span>{{ row[1] }}</span><strong>{{ metric(row[0]!,row[2]!) }}</strong></article></div>

   <div class="song-playback"><h3>回听您的演奏</h3>
    <audio v-if="audioUrl" ref="audioElement" :src="audioUrl" controls preload="metadata" @ended="song.playbackEnded"/>
    <div class="song-actions"><button v-if="audioUrl" class="song-primary" @click="audioElement?.play()">播放本次演奏</button><a v-if="audioUrl" :href="audioUrl" download="曲目跟弹_本次演奏.wav" class="song-quiet">下载演奏</a><button class="song-quiet" :disabled="busy" @click="song.retry">{{ busy?'正在处理…':audioUrl?'重新生成并保存音频':'生成演奏音频' }}</button></div>
   </div>
   <details><summary>逐音记录与难度调整</summary><p>第一段 {{ session.segment_1_bpm }} BPM → 第二段 {{ session.segment_2_bpm }} BPM</p><p>{{ session.difficulty_adjustment?.adjustment_reason??'维持当前难度' }}</p><div class="song-table"><table><thead><tr><th>音符</th><th>尝试次数</th><th>错误次数</th><th>正确响应时延</th><th>按住时长</th><th>状态</th></tr></thead><tbody><tr v-for="note in session.notes" :key="String(note.note_index)"><td>{{ Number(note.note_index)+1 }}</td><td>{{ note.attempt_count }}</td><td>{{ note.wrong_attempt_count }}</td><td>{{ note.response_latency_ms??'—' }}</td><td>{{ note.hold_duration_ms??'—' }}</td><td>{{ note.was_skipped?'跳过':note.correct_press_time_ms!=null?'完成':'未完成' }}</td></tr></tbody></table></div></details>
  </section>
  <div class="song-setup-grid">
   <section class="song-config pd-card">
    <h2>训练设置</h2><fieldset><legend>训练手别</legend><div class="song-options"><button v-for="value in (['LEFT','RIGHT'] as const)" :key="value" :aria-pressed="hand===value" :disabled="song.gate.busy.value||launching" @click="hand=value">{{ value==='LEFT'?'左手':'右手' }}</button></div></fieldset>
    <fieldset><legend>训练难度</legend><div class="song-options"><button v-for="(bpm,key) in DIFFICULTY_BPM" :key="key" :aria-pressed="difficulty===key" :disabled="song.gate.busy.value||launching" @click="difficulty=key"><strong>{{ labels[key] }}</strong><span>{{ bpm }} BPM · {{ key==='BEGINNER'?'慢速':key==='INTERMEDIATE'?'稍慢速':'正常速度' }}</span></button></div></fieldset>
    <fieldset><legend>选择曲目</legend><button class="song-track" aria-pressed="true"><span class="song-track-icon">♫</span><span><strong>两只老虎</strong></span><span>已选择</span></button></fieldset>
    <label class="song-consent"><input v-model="consent" type="checkbox"/>我已向患者说明并取得同意：在模型可用时采集前置摄像头视频，用于本次训练的面部分析。</label><p class="song-muted">不采集麦克风声音，不永久保存原始面部视频。拒绝授权或摄像头不可用仍可训练。当前真实模型尚未配置。</p>
    <label v-if="isDevelopment" class="song-consent song-notice"><input v-model="simulationDemo" type="checkbox"/>开发模拟演示：使用固定模拟情绪样本验证段间提速。需服务器启用开关，此记录为自测，不属于真实患者测量。</label>
    <div class="song-start-row"><button class="song-primary" :disabled="song.gate.busy.value||launching||busy||pendingCancellation" @click="song.begin">{{ launching?'正在建立训练…':'开始训练' }}</button><button v-if="launching" class="song-quiet" @click="song.cancelStart">取消启动</button><span>{{ patient?`本次患者：${displayPatientName(patient.name)}`:'开始时选择患者' }}</span></div>
   </section>
   <aside class="song-preview pd-card"><span class="song-eyebrow">跟随发光的琴键</span><h2>先跟随试弹，再正式练习</h2><div class="song-preview-stage"><GuidedSongStage :target="2" :pressed="new Set()" :error="null" disabled/></div><ol><li>示范时按琴键上的字母跟随试弹，不计成绩。</li><li>示范结束后正式跟弹；按错可重试，按对才进入下一音。</li><li>完成后练习后半段，最后回听自己的演奏。</li></ol><p class="song-muted">可暂停、跳过音符或结束。</p><p class="song-muted">电脑使用 A S D F G H J 弹奏；触屏直接点击发光琴键。</p></aside>
  </div>
  <section class="song-history pd-card"><header><h2>曲目训练历史</h2><button class="song-quiet" @click="song.loadHistory">刷新记录</button></header><p v-if="!history.length" class="song-muted">暂无曲目记录</p><button v-for="row in history" :key="row.id" class="song-history-row" :disabled="busy||pendingCancellation" @click="song.viewHistory(row)"><span>两只老虎 · {{ row.selected_hand==='LEFT'?'左手':'右手' }}任务</span><span>{{ formatDateTime(row.created_at) }}</span><span>{{ row.status==='COMPLETED'?'已完成':row.status==='ACTIVE'?'未完成':'已结束' }} · 查看结果 →</span></button></section>
 </section>
 <TrainingStartGate :state="song.gate.state" exercise="两只老虎 · 曲目跟弹" @select="song.gate.selectPatient" @cancel="song.cancelStart" @change="song.changePatient"/>
</template>
<style scoped>
.song-page{max-width:1360px;margin:0 auto;padding:28px 32px;box-sizing:border-box;width:100%;color:#263d58}.song-back{color:#456d9e;text-decoration:none;font-size:14px}.song-page-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin:22px 0 28px}.song-page-heading h1{font-size:32px;margin:8px 0}.song-page-heading p,.song-muted{color:#65788e;line-height:1.7}.song-eyebrow{font-size:13px;letter-spacing:.08em;color:#457b99}.song-badge{border:1px solid #dae6ee;background:#f4f9fc;border-radius:30px;padding:9px 16px;color:#527286;font-size:13px;white-space:nowrap}.song-setup-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:24px}.song-config,.song-preview,.song-history,.song-result{padding:28px}.song-config h2,.song-preview h2,.song-history h2,.song-result h2{margin:0 0 20px;font-size:21px}.song-config fieldset{border:0;margin:0 0 24px;padding:0;min-width:0}.song-config legend{font-weight:600;margin-bottom:12px}.song-options{display:flex;gap:12px}.song-options button{flex:1;display:flex;flex-direction:column;gap:8px;align-items:center;justify-content:center;min-height:74px;border:1px solid #cfdae6;border-radius:12px;background:#fff;font:inherit;color:#3c526c;cursor:pointer}.song-options button[aria-pressed=true]{background:#edf5ff;border:2px solid #608cc1;color:#24588f}.song-options span{font-size:12px}.song-muted{font-size:13px;margin:12px 0}.song-track{width:100%;display:flex;align-items:center;gap:16px;text-align:left;padding:16px;background:#f2f8f8;border:1px solid #b8d8d0;border-radius:12px;color:#284a49}.song-track>span:nth-child(2){flex:1}.song-track strong,.song-track small{display:block}.song-track small{margin-top:7px;color:#607e7c}.song-track-icon{font-size:32px}.song-consent{display:flex;align-items:flex-start;gap:10px;font-size:13px;line-height:1.8}.song-consent input{margin-top:5px;min-width:18px;height:18px;accent-color:#428b80}.song-start-row{display:flex;align-items:center;flex-wrap:wrap;gap:16px;margin-top:26px}.song-start-row>span{font-size:13px;color:#60748c}.song-primary,.song-quiet{display:inline-flex;justify-content:center;align-items:center;min-height:44px;padding:10px 18px;border-radius:10px;font:inherit;font-size:14px;text-decoration:none;cursor:pointer}.song-primary{background:#386cad;color:white;border:1px solid #386cad}.song-quiet{background:#ffffffd9;border:1px solid #ccd9e6;color:#355574}.song-primary:disabled,.song-quiet:disabled{opacity:.55;cursor:default}.song-start-row .song-primary{min-width:180px;min-height:50px}.song-preview-stage{position:relative;height:220px;display:flex;margin:24px 0}.song-preview ol{padding-left:22px;line-height:2.2;font-size:15px}.song-history{margin-top:24px}.song-history header,.song-result header{display:flex;justify-content:space-between;align-items:center;gap:16px}.song-history-row{width:100%;display:flex;justify-content:space-between;gap:16px;padding:18px 0;border:0;border-top:1px solid #e2e9ef;background:none;text-align:left;color:#3a536c;cursor:pointer}.song-immersive{position:fixed;inset:0;z-index:1000;background:linear-gradient(135deg,#eef4fb,#f5f9f8);display:flex;flex-direction:column;padding:14px 18px max(14px,env(safe-area-inset-bottom));gap:12px;height:100dvh;box-sizing:border-box}.song-toolbar{display:flex;align-items:center;gap:18px;min-height:52px}.song-title{display:flex;flex-direction:column;gap:5px;flex:1}.song-title strong{font-size:20px}.song-title span{font-size:12px;color:#567086}.song-tempo{font-size:13px;color:#52718d}.song-count{color:#416d9d;min-width:56px;text-align:right}.song-status{display:flex;align-items:center;justify-content:center;gap:18px;min-height:38px}.song-status strong{font-size:20px;color:#2f648c}.song-status span{font-size:14px;color:#60788f}.song-controls{display:flex;align-items:center;gap:12px}.song-camera{font-size:12px;color:#6d8191;flex:1}.song-error{background:#fff0eb;border:1px solid #efcfc4;border-radius:10px;padding:12px;color:#954a3a;font-size:14px;line-height:1.7;margin:0}.song-rotate{display:none}.song-result{margin-bottom:24px}.song-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:22px 0}.song-metrics article{background:#f2f7fb;padding:18px;border-radius:12px;display:flex;flex-direction:column;gap:12px}.song-metrics span{color:#62788d;font-size:13px}.song-metrics strong{font-size:26px;color:#345e89}.song-playback{border-top:1px solid #e1e9ef;padding:18px 0}.song-playback p{font-size:13px;color:#63768b}.song-playback audio{width:100%;margin:12px 0}.song-actions{display:flex;gap:12px;flex-wrap:wrap}.song-table{overflow:auto}.song-table table{border-collapse:collapse;width:100%;min-width:570px;font-size:13px}.song-table th,.song-table td{padding:10px;border-bottom:1px solid #dbe4ed;text-align:left}.song-result summary{cursor:pointer;min-height:44px;line-height:44px}.song-notice{padding:12px;background:#fff5dc;color:#806829;border-radius:8px}
@media(max-width:1050px){.song-setup-grid{grid-template-columns:1fr}.song-preview{display:none}.song-page-heading h1{font-size:26px}}
@media(max-width:600px){.song-page{padding:18px 14px}.song-config,.song-history,.song-result{padding:18px}.song-page-heading .song-badge{display:none}.song-options{gap:7px}.song-options span{font-size:11px}.song-options button{min-height:80px}.song-metrics{grid-template-columns:repeat(2,1fr)}.song-history-row{flex-direction:column;gap:8px}.song-immersive{padding:10px;gap:8px}.song-toolbar{gap:10px;flex-wrap:wrap}.song-title strong{font-size:17px}.song-status{flex-direction:column;gap:3px}.song-status span{font-size:12px}.song-controls{flex-wrap:wrap}.song-camera{flex-basis:100%}.song-tempo{font-size:12px}.song-rotate{display:block;font-size:12px;color:#617990;text-align:center;margin:0}}
@media(max-height:500px) and (orientation:landscape){.song-immersive{padding:6px 12px;gap:5px}.song-toolbar{min-height:36px}.song-toolbar .song-quiet{min-height:34px;padding:6px 12px}.song-status{min-height:26px}.song-status strong{font-size:16px}.song-controls .song-quiet{min-height:36px;padding:6px 14px}.song-title strong{font-size:16px}.song-title span{font-size:11px}.song-immersive :deep(.guided-song-stage){min-height:120px}.song-rotate{display:none}}
</style>

<style scoped>
.song-announcement{position:absolute;left:50%;top:30%;transform:translateX(-50%);max-width:80%;padding:18px 26px;border:1px solid #d2e1ed;background:#f8fcffed;border-radius:16px;box-shadow:0 8px 26px #27496912;color:#35638b;font-size:22px;font-weight:600;text-align:center;pointer-events:none;z-index:3}
.song-message-enter-active,.song-message-leave-active{transition:opacity .4s}.song-message-enter-from,.song-message-leave-to{opacity:0}
@media(max-height:500px){.song-announcement{font-size:17px;padding:12px 18px}}
@media(prefers-reduced-motion:reduce){.song-message-enter-active,.song-message-leave-active{transition:none}}
</style>

<style scoped>.song-options span,.song-consent,.song-preview ol,.song-start-row>span{font-size:14px}</style>
