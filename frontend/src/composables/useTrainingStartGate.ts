import { computed, onBeforeUnmount, reactive } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { patientApi } from '@/api'
import { usePatientContextStore } from '@/stores/patientContext'
import type { Patient } from '@/types'
import { TrainingStartController } from '@/training/startController'

export function useTrainingStartGate(options: {
  bind: (patient: Patient, signal: AbortSignal) => Promise<void>
  prepare: (patient: Patient, signal: AbortSignal) => Promise<void>
  start: () => void
}) {
  const route = useRoute()
  const router = useRouter()
  const store = usePatientContextStore()
  const state = reactive({ phase: 'idle' as 'idle' | 'picking' | 'preparing' | 'countdown', remaining: 0, patient: null as Patient | null, error: '' })
  const busy = computed(() => state.phase !== 'idle')
  let resumeAfterPick = false
  let binding: AbortController | null = null
  let tone: AudioContext | null = null

  function unlockTone() {
    try {
      tone ??= new AudioContext()
      void tone.resume().catch(() => {})
    } catch { /* Visual countdown is available without audio. */ }
  }
  function tick() {
    if (!tone || tone.state !== 'running') return
    const oscillator = tone.createOscillator()
    const gain = tone.createGain()
    oscillator.connect(gain).connect(tone.destination)
    oscillator.frequency.value = 660
    gain.gain.setValueAtTime(0.035, tone.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, tone.currentTime + 0.12)
    oscillator.start()
    oscillator.stop(tone.currentTime + 0.13)
  }
  const controller = new TrainingStartController((next) => {
    Object.assign(state, next)
    if (next.phase === 'countdown') tick()
  })

  async function launch(id: string) {
    state.error = ''
    state.patient = null
    try {
      await controller.run(async (signal) => {
        // Bypass the cache every time: deleted patients and stale URLs cannot start.
        const patient = await patientApi.get(id)
        if (signal.aborted) return
        if (patient.is_deleted) throw new Error('该患者已删除，请更换患者后重试。')
        state.patient = patient
        store.accept(patient)
        await options.bind(patient, signal)
        if (signal.aborted) return
        await router.replace({ query: { ...route.query, patientId: id } })
        if (signal.aborted) return
        await options.prepare(patient, signal)
      }, options.start)
    } catch (error) {
      state.error = (error as { response?: unknown })?.response
        ? '无法核实患者资料，请更换患者或检查网络后重试。'
        : error instanceof Error ? error.message : '无法开始训练，请检查网络后重试。'
    }
  }
  function requestStart() {
    if (busy.value) return
    unlockTone()
    const id = typeof route.query.patientId === 'string' && route.query.patientId
      ? route.query.patientId : store.currentPatientId
    if (!id) {
      resumeAfterPick = true
      state.phase = 'picking'
      return
    }
    void launch(id)
  }
  function cancelStart() {
    binding?.abort()
    binding = null
    resumeAfterPick = false
    controller.cancel()
  }
  function changePatient() {
    const resume = busy.value
    cancelStart()
    resumeAfterPick = resume
    state.phase = 'picking'
  }
  async function selectPatient(patient: Patient) {
    if (state.phase !== 'picking' || binding) return
    unlockTone()
    if (resumeAfterPick) {
      state.phase = 'idle'
      void launch(patient.id)
    } else {
      const operation = new AbortController()
      binding = operation
      try {
        await options.bind(patient, operation.signal)
        if (operation.signal.aborted) return
        await router.replace({ query: { ...route.query, patientId: patient.id } })
        if (!operation.signal.aborted) cancelStart()
      } catch (error) {
        if (!operation.signal.aborted) {
          state.error = error instanceof Error ? error.message : '无法读取患者资料，请重试。'
          cancelStart()
        }
      } finally { if (binding === operation) binding = null }
    }
  }
  onBeforeRouteLeave(cancelStart)
  onBeforeUnmount(() => {
    cancelStart()
    void tone?.close().catch(() => {})
  })
  return { state, busy, requestStart, selectPatient, cancelStart, changePatient }
}
