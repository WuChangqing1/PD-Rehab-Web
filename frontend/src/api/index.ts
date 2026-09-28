/**
 * Typed API wrappers. Views call these instead of touching axios directly.
 */

import { http } from '@/api/client'
import type {
  AssessmentSession,
  AssessmentSessionDetail,
  AssessmentSessionType,
  DashboardResponse,
  FingerTappingSessionSummary,
  FunctionalAssessment,
  GpuStatus,
  Job,
  LoginResponse,
  MedicationState,
  MicroExpressionResult,
  ModelsResponse,
  Page,
  Patient,
  PatientListItem,
  StaffUser,
  SystemInfo,
} from '@/types'

// ---------------------------------------------------------------------- auth
export const authApi = {
  async login(username: string, password: string): Promise<LoginResponse> {
    const { data } = await http.post<LoginResponse>('/auth/login', { username, password })
    return data
  },
  async logout(): Promise<void> {
    await http.post('/auth/logout')
  },
  async me(): Promise<StaffUser> {
    const { data } = await http.get<StaffUser>('/auth/me')
    return data
  },
}

// ------------------------------------------------------------------ patients
export interface PatientQuery {
  q?: string
  medication_state?: MedicationState
  affected_side?: string
  include_deleted?: boolean
  page?: number
  page_size?: number
}

export const patientApi = {
  async list(query: PatientQuery = {}): Promise<Page<PatientListItem>> {
    const { data } = await http.get<Page<PatientListItem>>('/patients', { params: query })
    return data
  },
  async get(id: string): Promise<Patient> {
    const { data } = await http.get<Patient>(`/patients/${id}`)
    return data
  },
  async create(payload: Partial<Patient>): Promise<Patient> {
    const { data } = await http.post<Patient>('/patients', payload)
    return data
  },
  async update(id: string, payload: Partial<Patient>): Promise<Patient> {
    const { data } = await http.patch<Patient>(`/patients/${id}`, payload)
    return data
  },
  async remove(id: string): Promise<Patient> {
    const { data } = await http.delete<Patient>(`/patients/${id}`)
    return data
  },
  async restore(id: string): Promise<Patient> {
    const { data } = await http.post<Patient>(`/patients/${id}/restore`)
    return data
  },
}

// -------------------------------------------------------- assessment sessions
export const assessmentApi = {
  async createSession(
    patientId: string,
    payload: { session_type: AssessmentSessionType; medication_state?: MedicationState; notes?: string },
  ): Promise<AssessmentSession> {
    const { data } = await http.post<AssessmentSession>(
      `/patients/${patientId}/assessment-sessions`,
      payload,
    )
    return data
  },
  async listSessions(patientId: string, page = 1, pageSize = 20): Promise<Page<AssessmentSession>> {
    const { data } = await http.get<Page<AssessmentSession>>(
      `/patients/${patientId}/assessment-sessions`,
      { params: { page, page_size: pageSize } },
    )
    return data
  },
  async getSession(sessionId: string): Promise<AssessmentSessionDetail> {
    const { data } = await http.get<AssessmentSessionDetail>(`/assessment-sessions/${sessionId}`)
    return data
  },
  async completeSession(sessionId: string, notes?: string): Promise<AssessmentSession> {
    const { data } = await http.post<AssessmentSession>(
      `/assessment-sessions/${sessionId}/complete`,
      { notes: notes ?? null },
    )
    return data
  },
  async listMicroExpression(sessionId: string): Promise<MicroExpressionResult[]> {
    const { data } = await http.get<MicroExpressionResult[]>(
      `/assessment-sessions/${sessionId}/micro-expression`,
    )
    return data
  },
  async uploadMicroExpression(
    sessionId: string,
    file: File,
    medicationState: MedicationState = 'UNKNOWN',
  ): Promise<MicroExpressionResult> {
    const form = new FormData()
    form.append('video', file)
    form.append('medication_state', medicationState)
    const { data } = await http.post<MicroExpressionResult>(
      `/assessment-sessions/${sessionId}/micro-expression`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return data
  },
  async getFingerTapping(sessionId: string): Promise<FingerTappingSessionSummary> {
    const { data } = await http.get<FingerTappingSessionSummary>(
      `/assessment-sessions/${sessionId}/finger-tapping`,
    )
    return data
  },
  async uploadFingerTapping(
    sessionId: string,
    file: File,
    hand: 'LEFT' | 'RIGHT',
    medicationState: MedicationState = 'UNKNOWN',
  ): Promise<FingerTappingSessionSummary> {
    const form = new FormData()
    form.append('video', file)
    form.append('hand', hand)
    form.append('medication_state', medicationState)
    const { data } = await http.post<FingerTappingSessionSummary>(
      `/assessment-sessions/${sessionId}/finger-tapping`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return data
  },
  async listFunctional(patientId: string): Promise<Page<FunctionalAssessment>> {
    const { data } = await http.get<Page<FunctionalAssessment>>(
      `/patients/${patientId}/functional-assessments`,
    )
    return data
  },
}

// -------------------------------------------------------------------- system
export const systemApi = {
  async health(): Promise<{ status: string; app: string; env: string; time: string }> {
    const { data } = await http.get('/system/health')
    return data
  },
  async models(): Promise<ModelsResponse> {
    const { data } = await http.get<ModelsResponse>('/system/models')
    return data
  },
  async gpu(): Promise<GpuStatus> {
    const { data } = await http.get<GpuStatus>('/system/gpu')
    return data
  },
  async info(): Promise<SystemInfo> {
    const { data } = await http.get<SystemInfo>('/system/info')
    return data
  },
  async dashboard(): Promise<DashboardResponse> {
    const { data } = await http.get<DashboardResponse>('/system/dashboard')
    return data
  },
}

// ---------------------------------------------------------------------- jobs
export const jobApi = {
  async get(jobId: string): Promise<Job> {
    const { data } = await http.get<Job>(`/jobs/${jobId}`)
    return data
  },
  async list(): Promise<Job[]> {
    const { data } = await http.get<Job[]>('/jobs')
    return data
  },
}
