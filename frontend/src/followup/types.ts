import type { AssessmentSession, FingerTappingResult, PianoSession, PoseSession } from '../types/index.ts'

export interface GuidedTrainingSummary {
  id:string; patient_id:string; status:string; started_at:string; completed_at:string|null
  source:string; song_id:string|null; selected_hand:string|null; difficulty:string|null; bpm:number|null
  metrics:Record<string,number|boolean|null>; version:string|null
}
export interface FollowUpData {
  patient_id:string; start_date:string; end_date:string; offset_minutes:number; is_showcase:boolean
  assessments:AssessmentSession[]; tapping:FingerTappingResult[]; piano:PianoSession[]; pose:PoseSession[]
  guided:GuidedTrainingSummary[]
}
