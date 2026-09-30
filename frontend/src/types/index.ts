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
  /** Soft-deleted rows appear only when the list is asked to include them. */
  is_deleted: boolean
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

/**
 * The aperture series an analysis was computed from, served unchanged so it can
 * be re-plotted or re-thresholded without re-running inference.
 */
export interface FingerTappingTimeseries {
  session_id: string
  hand: Hand
  result_id: string
  analyzer_version: string | null
  peak_frames: number[]
  series: {
    frame_index: number[]
    timestamp_ms: number[]
    aperture_raw: number[]
    aperture_filtered: number[]
  }
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

// -------------------------------------------------------------------- piano
export type PianoMode =
  | 'CALIBRATION'
  | 'SINGLE_KEY_RHYTHM'
  | 'ALTERNATING_HANDS'
  | 'MAPPED_SEQUENCE'
  | 'FOLLOW_THE_BEAT'

/** One raw key event as stored by the server. */
export interface PianoEventRecord {
  id: string | null
  session_id: string | null
  event_index: number
  cue_onset_time_ms: number | null
  target_time_ms: number | null
  actual_time_ms: number | null
  response_latency_ms: number | null
  timing_error_ms: number | null
  key_code: string | null
  note: string | null
  hand: Hand | null
  finger_hint: string | null
  key_down_time_ms: number | null
  key_up_time_ms: number | null
  hold_duration_ms: number | null
  is_correct: boolean | null
  is_missed: boolean | null
  is_wrong_key: boolean
  cue_index: number | null
  sequence_position: number | null
  sequence_length: number | null
  created_at: string | null
}

/**
 * Where a session's key events came from.
 *
 * Only `HUMAN_KEYBOARD` is a measurement. The other two exist so a scripted
 * self-test or a seeded demo row can never be read as a patient result.
 */
export type PianoInputSource = 'HUMAN_KEYBOARD' | 'SYNTHETIC_SELFTEST' | 'SEED_DEMO'

// Display labels live in `@/utils/source`, which keeps one map per module: the
// human case means "played on a keyboard" for the piano and "recorded on a
// camera" for movement training, and a single shared map labelled camera
// recordings as keyboard input.

export interface PianoSession {
  id: string
  patient_id: string
  training_plan_id: string | null
  mode: PianoMode
  round_number: number
  input_source: PianoInputSource

  bpm: number
  judgement_window_ms: number
  sequence_length: number
  note_density: number
  hand_mode: string
  weak_side_ratio: number
  finger_complexity: number
  session_duration_sec: number

  accuracy: number | null
  miss_rate: number | null
  mean_response_latency_ms: number | null
  median_response_latency_ms: number | null
  response_latency_cv: number | null
  mean_timing_error_ms: number | null
  median_timing_error_ms: number | null
  timing_mae_ms: number | null
  timing_error_cv: number | null
  early_press_rate: number | null
  late_press_rate: number | null
  left_mean_latency: number | null
  right_mean_latency: number | null
  left_right_latency_difference: number | null
  left_accuracy: number | null
  right_accuracy: number | null
  weak_finger_error_rate: number | null
  sequence_completion_rate: number | null
  session_completion_rate: number | null

  difficulty_before_json: Record<string, unknown> | null
  difficulty_after_json: Record<string, unknown> | null
  adaptation_reason_json: Record<string, unknown> | null
  difficulty_engine_version: string | null
  metrics_version: string | null

  started_at: string | null
  completed_at: string | null
}

export interface PianoSessionDetail extends PianoSession {
  events: PianoEventRecord[]
  planned_cues: number | null
}

/** The eight calibration values from spec V2 section 20. */
export interface PianoCalibrationBaseline {
  id: string
  patient_id: string
  baseline_accuracy: number | null
  baseline_response_latency: number | null
  baseline_response_latency_cv: number | null
  baseline_timing_mae: number | null
  baseline_left_accuracy: number | null
  baseline_right_accuracy: number | null
  baseline_left_latency: number | null
  baseline_right_latency: number | null
  created_at: string
  algorithm_version: string | null
  is_active: boolean
  snapshot: Record<string, unknown> | null
}

// --------------------------------------------------------------------- pose
export interface PoseExerciseDefinition {
  key: string
  name_zh: string
  description: string
  joints: string[]
  raw_metrics: string[]
  hold_time_sec: number | null
  target_repetitions: number | null
  contraindications: string[]
  /** False until every display-score formula is defined and versioned. */
  scores_available: boolean
  score_formulas: {
    completion: string | null
    rom: string | null
    symmetry: string | null
    stability: string | null
  }
}

export interface PoseQualityReport {
  fps: number | null
  width: number
  height: number
  frame_count: number
  valid_frame_count: number
  valid_pose_frame_ratio: number | null
  duration_sec: number | null
  mean_visibility_core_joints: number | null
  mean_visibility_trunk_joints: number | null
  visibility_measured: boolean
  gate_failures: string[]
  analysis_config: Record<string, unknown>
}

export interface PoseSession {
  id: string
  patient_id: string
  exercise_type: string
  input_source: PianoInputSource
  difficulty_json: Record<string, unknown> | null

  /** Always null while the formulas are undefined. */
  completion_score: number | null
  range_of_motion: number | null
  symmetry_score: number | null
  stability_score: number | null

  hold_time_sec: number | null
  repetition_count: number | null
  movement_speed: number | null
  valid_pose_frame_ratio: number | null

  raw_metrics_json: Record<string, unknown> | null
  quality_json: PoseQualityReport | null
  algorithm_version: string | null
  exercise_definition_version: string | null
  media_file_id: string | null

  started_at: string | null
  completed_at: string | null
}

export interface PoseAnalysisResponse {
  session: PoseSession
  accepted: boolean
  gate_failures: string[]
  warnings: string[]
  quality: PoseQualityReport
  message: string
}

export interface PoseThresholds {
  min_valid_frame_ratio: number
  min_duration_sec: number
  min_landmark_visibility: number
  min_movement_range_deg: number
  algorithm_version: string
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
