import type { PianoRawEvent } from './session.ts'
const mean=(values:number[])=>values.length?values.reduce((a,b)=>a+b,0)/values.length:null
const ratio=(n:number,d:number)=>d?n/d:null
/** Extra measurements derived from timestamps; no pressure or physical finger inference. */
export function extendedMetrics(events:PianoRawEvent[]):Record<string,number|null> {
  const rows=events.filter(e=>!e.is_prompt&&!e.is_wrong_key)
  const out:Record<string,number|null>={}
  for(let segment=0;segment<4;segment++) {
    const group=rows.filter(e=>e.tempo_segment===segment)
    out[`tempo_segment_${segment}_accuracy`]=ratio(group.filter(e=>e.is_correct).length,group.length)
    out[`tempo_segment_${segment}_mae_ms`]=mean(group.filter(e=>e.is_correct&&e.actual_time_ms!==null&&e.target_time_ms!==null).map(e=>Math.abs(e.actual_time_ms!-e.target_time_ms!)))
  }
  const holds=rows.filter(e=>e.target_hold_ms!=null)
  const released=holds.filter(e=>e.key_down_time_ms!==null&&e.key_up_time_ms!==null)
  out.hold_duration_mae_ms=mean(released.map(e=>Math.abs(e.key_up_time_ms!-e.key_down_time_ms!-e.target_hold_ms!)))
  out.hold_release_completion_rate=ratio(released.length,holds.length)
  const pairs=new Map<number,PianoRawEvent[]>()
  for(const e of rows) if(e.pair_id!=null) pairs.set(e.pair_id,[...(pairs.get(e.pair_id)??[]),e])
  const errors:number[]=[]
  for(const pair of pairs.values()) {
    const l=pair.find(e=>e.pair_role==='PRIMARY'), r=pair.find(e=>e.pair_role==='SECONDARY')
    if(l?.actual_time_ms!=null&&r?.actual_time_ms!=null) errors.push(Math.abs(r.actual_time_ms-l.actual_time_ms-(l.target_offset_ms??0)))
  }
  out.inter_hand_phase_mae_ms=mean(errors)
  for(const [side,role] of [['left','PRIMARY'],['right','SECONDARY']]) {
    const hand=rows.filter(e=>e.pair_id!=null&&e.pair_role===role)
    out[`offset_${side}_miss_rate`]=ratio(hand.filter(e=>e.is_missed).length,hand.length)
  }
  const reverse=rows.filter(e=>e.recipe_id==='REVERSE_SEQUENCE')
  out.reverse_position_accuracy=ratio(reverse.filter(e=>e.is_correct).length,reverse.length)
  const groups=[...new Set(reverse.map(e=>e.memory_group))].map(id=>reverse.filter(e=>e.memory_group===id))
  out.reverse_completion_rate=ratio(groups.filter(g=>g.length===g[0].sequence_length&&g.every(e=>e.is_correct)).length,groups.length)
  const go=rows.filter(e=>e.cue_type==='GO'), no=rows.filter(e=>e.cue_type==='NO_GO')
  out.go_commission_count=no.length?no.filter(e=>e.actual_time_ms!==null).length:null
  out.go_omission_count=go.length?go.filter(e=>e.is_missed).length:null
  out.go_response_latency_ms=mean(go.filter(e=>e.is_correct&&e.actual_time_ms!==null&&e.cue_onset_time_ms!==null).map(e=>e.actual_time_ms!-e.cue_onset_time_ms!))
  return out
}
