import { mulberry32, type Cue, type DifficultyConfig } from './session.ts'
import { BINDING_BY_MIDI } from './samples.ts'

/** Additive protocols; legacy cue generators and their stored identifiers stay intact. */
export function extendedCues(id: string, cues: Cue[], config: DifficultyConfig, seed=20260929): Cue[] {
  if(!cues.length) return []
  const beat = 60000 / Math.max(20, config.bpm)
  const end = config.session_duration_sec * 1000
  const left = Object.values(BINDING_BY_MIDI).find(b => b.hand === 'LEFT' && b.fingerHint === 'INDEX')!
  const right = Object.values(BINDING_BY_MIDI).find(b => b.hand === 'RIGHT' && b.fingerHint === 'INDEX')!
  let result: Cue[] = []
  if (id === 'TEMPO_RAMP') {
    let target = 700
    const rates = [1, 1.05, 1.1, 1]
    const ceiling = Math.min(160, config.tempo_ceiling_bpm ?? 160)
    while(target+config.judgement_window_ms/2 < end) {
      const segment = Math.min(3, Math.floor(target * 4 / end))
      result.push({...cues[0],targetMs:target,cueOnsetMs:Math.max(0,target-700),tempoSegment:segment})
      target += 60000 / Math.min(ceiling,config.bpm*Math.max(.25,config.note_density)*rates[segment])
    }
  } else if (id === 'HOLD_RELEASE') {
    const interval = Math.max(beat, 750 + config.judgement_window_ms + 200)
    result = cues.map((c,i) => ({ ...c, binding: right, targetMs: 700+i*interval,
      cueOnsetMs: i*interval, targetHoldMs: i%2 ? 750 : 250 }))
      .filter(c=>c.targetMs+c.targetHoldMs+config.judgement_window_ms/2 < end)
  } else if (id === 'BIMANUAL_OFFSET') {
    for(let i=0; 700+i*beat*2+beat/2+config.judgement_window_ms/2<end;i++) {
      for(const secondary of [false,true]) {
        const target = 700+i*beat*2+(secondary?beat/2:0)
        result.push({ ...cues[0], binding: secondary?right:left, targetMs: target,
          cueOnsetMs: Math.max(0,target-700), pairId:i, targetOffsetMs:Math.round(beat/2),
          pairRole: secondary?'SECONDARY':'PRIMARY' })
      }
    }
  } else if (id === 'REVERSE_SEQUENCE') {
    const random=mulberry32(seed)
    const pool=Object.values(BINDING_BY_MIDI).filter(b=>config.finger_complexity>=3||b.fingerHint==='INDEX'||config.finger_complexity===2&&b.fingerHint==='MIDDLE')
    const length=Math.max(2,Math.min(8,config.sequence_length,pool.length))
    let cursor=700, group=0
    while(cursor+(length*2+2)*beat<end) {
      const offset=Math.floor(random()*pool.length)
      const notes=Array.from({length},(_,i)=>pool[(offset+i)%pool.length])
      for(const prompt of [true,false]) {
        const sequence=prompt?notes:[...notes].reverse()
        sequence.forEach((binding,i)=>{
          result.push({...cues[0],binding,targetMs:cursor,cueOnsetMs:Math.max(0,cursor-700),isPrompt:prompt,memoryGroup:group,sequencePosition:i+1,sequenceLength:length})
          cursor+=beat
        })
        if(prompt) cursor+=2*beat
      }
      group++
    }
  } else if (id === 'GO_NO_GO') {
    result=cues.map((c,i)=>({...c,binding:right,cueOnsetMs:c.targetMs,responseWindowMs:Math.min(1000,beat*.8),cueType:i%3===2?'NO_GO' as const:'GO' as const}))
  }
  return result.map((c,i)=>({...c,eventIndex:i,recipeId:id}))
}
