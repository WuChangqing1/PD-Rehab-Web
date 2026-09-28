/**
 * Shared API and domain types.
 *
 * These mirror the backend Pydantic schemas. Model-output fields are optional
 * and nullable on purpose: the backend sends null when a real model has not
 * produced a value, and the UI must render that honestly rather than inventing
 * a placeholder.
 */

// ---------------------------------------------------------------- error shape
export interface ApiErrorBody {
  code: string
  message: string
  detail?: unknown
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody
}

// ---------------------------------------------------------------------- auth
export interface StaffUser {
  id: string
  username: string
  display_name: string
  role: 'ADMIN' | 'DOCTOR'
  is_active: boolean
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: StaffUser
}

// ------------------------------------------------------------------- patient
export type Sex = 'MALE' | 'FEMALE' | 'OTHER' | 'UNKNOWN'
export type MedicationState = 'ON' | 'OFF' | 'UNKNOWN'
export type DominantHand = 'LEFT' | 'RIGHT' | 'AMBIDEXTROUS' | 'UNKNOWN'
export type AffectedSide = 'LEFT' | 'RIGHT' | 'BILATERAL' | 'UNKNOWN'
export type Hand = 'LEFT' | 'RIGHT'

export interface Patient {
  id: string
  hospital_number: string
  name: string
  sex: Sex
  birthday: string | null
  age: number | null
  phone: string | null
  address: string | null
  emergency_contact: string | null
  emergency_phone: string | null
  dominant_hand: DominantHand
  affected_side: AffectedSide
  diagnosis_date: string | null
  disease_duration_years: number | null
  current_stage: string | null
  current_medications: string | null
  last_medication_time: string | null
  medication_state: MedicationState
  medical_history: string | null
  comorbidities: string | null
  allergies: string | null
  surgery_history: string | null
  rehab_history: string | null
  doctor_notes: string | null
  is_deleted: boolean
  created_at: string
  updated_at: string
}

export interface PatientListItem {
  id: string
  hospital_number: string
  name: string
  sex: Sex
  age: number | null
  affected_side: AffectedSide
  dominant_hand: DominantHand
  disease_duration_years: number | null
  medication_state: MedicationState
  last_assessment_at: string | null
  last_training_at: string | null
}

// ------------------------------------------------------------------ paging
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ------------------------------------------------------- assessment sessions
export type AssessmentSessionType =
  | 'COMPREHENSIVE'
  | 'MICRO_EXPRESSION_ONLY'
  | 'FINGER_TAPPING_ONLY'
  | 'FUNCTIONAL_TEST'

export type SessionStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'ABORTED'

export interface AssessmentSession {
  id: string
  patient_id: string
  session_type: AssessmentSessionType
  medication_state: MedicationState
  status: SessionStatus
  created_by: string | null
  started_at: string | null
  completed_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface TagScore {
  name: string
  score: number
}

/** Real model output only. Every field may legitimately be null. */
export interface MicroExpressionResult {
  id: string
  assessment_session_id: string
  media_file_id: string | null
  model_name: string | null
  model_version: string | null
  feature_schema_version: string
  predicted_class: string | null
  pd_probability: number | null
  dominant_tag: string | null
  tag_distribution: TagScore[] | null
  raw_output_json: Record<string, unknown> | null
  inference_time_ms: number | null
  quality_json: Record<string, unknown> | null
  created_at: string
}

export interface FingerTappingResult {
  id: string
  assessment_session_id: string
  media_file_id: string | null
  hand: Hand
  tapping_frequency: number | null
  avg_amplitude: number | null
  avg_speed: number | null
  avg_cycle_duration: number | null
  amplitude_cv: number | null
  speed_cv: number | null
  cycle_cv: number | null
  amplitude_slope: number | null
  speed_slope: number | null
  cycle_slope: number | null
  interruptions: number | null
  valid_frame_ratio: number | null
  avg_landmark_confidence: number | null
  severity_score: number | null
  severity_label: string | null
  analyzer_version: string | null
  feature_schema_version: string
  analysis_config_json: Record<string, unknown> | null
  quality_json: Record<string, unknown> | null
  raw_features_json: Record<string, unknown> | null
  created_at: string
}

export interface LeftRightComparison {
  metric: string
  left: number | null
  right: number | null
  absolute_difference: number | null
  asymmetry_ratio: number | null
}

export interface FingerTappingSessionSummary {
  session_id: string
  left: FingerTappingResult | null
  right: FingerTappingResult | null
  comparisons: LeftRightComparison[]
}

export interface FunctionalAssessment {
  id: string
  patient_id: string
  assessment_session_id: string | null
  test_type: string
  hand: Hand | null
  value_primary: number
  value_secondary: number | null
  unit: string
  medication_state: MedicationState
  notes: string | null
  performed_at: string
  created_by: string | null
  created_at: string
}

export interface AssessmentSessionDetail extends AssessmentSession {
  micro_expression_results: MicroExpressionResult[]
  finger_tapping_results: FingerTappingResult[]
  functional_assessments: FunctionalAssessment[]
}

// ------------------------------------------------------------------- system
export type ModelState =
  | 'MODEL_NOT_CONFIGURED'
  | 'LOADING'
  | 'READY'
  | 'UNAVAILABLE'
  | 'LOAD_FAILED'

export interface ModelStatus {
  name: string
  version: string
  state: ModelState
  device: string | null
  detail: string | null
  loaded_at: string | null
  is_ready: boolean
  extra: Record<string, unknown>
}

export interface ModelSummaryItem {
  name: string
  version: string
  state: ModelState
  device: string | null
  is_ready: boolean
}

export interface ModelsResponse {
  mock_mode: boolean
  summary: {
    total: number
    ready: number
    not_ready: number
    models: ModelSummaryItem[]
  }
  models: Record<string, ModelStatus>
  exercises: ExerciseDefinition[]
}

export interface ExerciseDefinition {
  key: string
  name_zh: string
  description: string
  joints: string[]
  raw_metrics: string[]
  completion_formula: string | null
  rom_formula: string | null
  symmetry_formula: string | null
  stability_formula: string | null
  hold_time_sec: number | null
  target_repetitions: number | null
  contraindications: string[]
  scores_available: boolean
}

export interface GpuStatus {
  use_gpu_requested: boolean
  gpu_inference_concurrency: number
  torch_installed: boolean
  cuda_available: boolean
  device: string | null
  device_name: string | null
  cuda_version: string | null
  driver_note: string | null
  torch_version?: string
  compute_capability?: string
  error?: string
}

export interface DashboardResponse {
  counts: {
    total_patients: number
    today_assessments: number
    today_trainings: number
  }
  recent_patients: Array<{
    id: string
    name: string
    hospital_number: string
    age: number | null
    affected_side: AffectedSide
    medication_state: MedicationState
  }>
  recent_assessments: Array<{
    id: string
    patient_id: string
    patient_name: string | null
    session_type: AssessmentSessionType
    status: SessionStatus
    medication_state: MedicationState
    created_at: string
  }>
  model_status: ModelsResponse['summary']
  mock_mode: boolean
}

export interface SystemInfo {
  app: string
  env: string
  project_root: string
  python_version: string
  platform: string
  database_url_scheme: string
  mock_mode: boolean
  counts: Record<string, number>
}

export interface Job {
  job_id: string
  job_type: string
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED'
  progress: number
  result_ref: Record<string, unknown> | null
  error: ApiErrorEnvelope | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}
