export type LiveEmotionStatus = 'IDLE' | 'CONSENT_REQUIRED' | 'CONNECTING' | 'MODEL_NOT_CONFIGURED' | 'STREAMING' | 'UNAVAILABLE' | 'STOPPED' | 'SIMULATED'
export interface EmotionResult {
  source: string
  quality: string
  probabilities: number[]
  result_timestamp_ms: number
  session_id?: string
  patient_id?: string
  stream_id?: string
  seq?: number
  capture_timestamp_ms?: number | null
  model_name?: string
  model_version?: string
  inference_latency_ms?: number | null
}
export const EMOTION_LABELS = ['sadness','other','disgust','happiness','fear','surprise','anger'] as const
export function validDistribution(values: unknown): values is number[] {
  return Array.isArray(values) && values.length === 7 && values.every(v => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1) && Math.abs(values.reduce((a,b) => a+b,0)-1) <= .001
}
/** Preview only; server independently decides and stores the authoritative policy. */
export function nextSimulationBpm(bpm:number, boundary:boolean, simulation:boolean, result:EmotionResult|null, now=Date.now()):number {
  if (!boundary || !simulation || !result || result.source !== 'SIMULATED' || result.quality !== 'GOOD' || !validDistribution(result.probabilities) || !Number.isFinite(result.result_timestamp_ms) || now-result.result_timestamp_ms < 0 || now-result.result_timestamp_ms > 30000) return bpm
  return result.probabilities[1]!+result.probabilities[3]! > .5 ? Math.min(120,bpm < 80 ? 80 : bpm < 100 ? 100 : bpm+10) : bpm
}
