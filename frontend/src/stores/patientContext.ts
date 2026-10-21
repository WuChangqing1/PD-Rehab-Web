/**
 * Which patient the current task is about.
 *
 * Every data-producing page needs one, and the value has to be visible on the
 * page rather than only in the URL: a doctor must never have to read the address
 * bar to know whose hand they are recording.
 *
 * The recently-used list is a convenience only. It seeds the picker and is never
 * applied silently -- selecting a patient is always an explicit action.
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { patientApi } from '@/api'
import type { Patient } from '@/types'

const RECENT_LIMIT = 5

export const usePatientContextStore = defineStore('patientContext', () => {
  /** Patients used recently, newest first. Ids only; details are fetched. */
  const recentIds = ref<string[]>([])
  const cache = ref<Record<string, Patient>>({})

  const currentPatientId = ref<string | null>(null)
  const currentPatient = computed(() =>
    currentPatientId.value ? (cache.value[currentPatientId.value] ?? null) : null,
  )

  async function fetchPatient(id: string, fresh = false): Promise<Patient | null> {
    if (!fresh && cache.value[id]) return cache.value[id]
    try {
      const patient = await patientApi.get(id)
      if (patient.is_deleted) { invalidate(id); return null }
      cache.value = { ...cache.value, [id]: patient }
      return patient
    } catch {
      // A missing or deleted patient is the page's problem to report; the store
      // just does not have it.
      invalidate(id)
      return null
    }
  }

  /** Point the context at a patient and remember it for the picker. */
  async function select(id: string | null): Promise<Patient | null> {
    if (!id) { currentPatientId.value = null; return null }
    const patient = await fetchPatient(id, true)
    if (!patient) { currentPatientId.value = null; return null }
    accept(patient)
    return patient
  }

  function accept(patient: Patient) {
    if (patient.is_deleted) return
    cache.value = { ...cache.value, [patient.id]: patient }
    currentPatientId.value = patient.id
    recentIds.value = [patient.id, ...recentIds.value.filter((r) => r !== patient.id)].slice(0, RECENT_LIMIT)
  }

  /** Resolve an id that came from the URL, without changing the recent order. */
  async function resolve(id: string | null): Promise<Patient | null> {
    currentPatientId.value = id
    const patient = id ? await fetchPatient(id, true) : null
    if (!patient && currentPatientId.value === id) currentPatientId.value = null
    return patient
  }

  function forget(id: string) {
    recentIds.value = recentIds.value.filter((r) => r !== id)
  }

  function recentPatients(): Patient[] {
    return recentIds.value.map((id) => cache.value[id]).filter((p): p is Patient => Boolean(p))
  }

  function invalidate(id: string) {
    const next = { ...cache.value }
    delete next[id]
    cache.value = next
  }

  return {
    currentPatientId,
    currentPatient,
    recentIds,
    select,
    accept,
    resolve,
    forget,
    invalidate,
    recentPatients,
    fetchPatient,
  }
})
