import assert from 'node:assert/strict'
import test from 'node:test'
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const vue = require('vue')
const ts = require('typescript')

// Run the real setup code with network, media and router boundaries controlled.
// The page's refs, guards and save functions remain the production implementation.
function movementFixture(overrides: Record<string, unknown> = {}) {
  const route = vue.reactive({ query: {}, params: {} })
  const beforeLeave: Array<() => Promise<unknown> | unknown> = []
  const unmount: Array<() => void> = []
  const writes: Array<{ patient: string; config: unknown }> = []
  const analyses: string[] = []
  const messages: string[] = []
  const errors: string[] = []
  const confirmations: string[] = []
  let allowLeave = true
  const store = { currentPatient: null, resolve: async () => null }
  let gate: any
  const api = {
    startSession: async (patient: string, config: unknown) => {
      writes.push({ patient, config })
      return { id: `session-${writes.length}` }
    },
    analyze: async (id: string) => { analyses.push(id); return { session: { id } } },
    exercises: async () => [], thresholds: async () => ({}), history: async () => ({ items: [] }),
    ...overrides,
  }
  const modules: Record<string, unknown> = {
    vue: { ...vue, watch: (source: unknown, fn: unknown, options: object) => vue.watch(source, fn, { ...options, immediate: false }), onBeforeUnmount: (fn: () => void) => unmount.push(fn), onMounted: () => {} },
    'vue-router': { useRoute: () => route, useRouter: () => ({ push: async () => {} }), onBeforeRouteUpdate: () => {}, onBeforeRouteLeave: (fn: () => unknown) => beforeLeave.push(fn) },
    'element-plus': { ElMessage: { warning: (s: string) => messages.push(s), success: (s: string) => messages.push(s) }, ElMessageBox: { confirm: async (s: string) => { confirmations.push(s); if (!allowLeave) throw new Error('cancelled') } } },
    '@/composables/useTrainingStartGate': { useTrainingStartGate: (options: unknown) => { gate = options; return { state: {}, busy: vue.ref(false), requestStart: () => {}, cancelStart: () => {} } } },
    '@/stores/patientContext': { usePatientContextStore: () => store },
    '@/stores/taskMode': { useTaskModeStore: () => ({ enter: () => {}, exit: () => {} }) },
    '@/ballet/rhythmEngine': { RhythmEngine: class { unlock = async () => true; stop() {}; dispose() {} } },
    '@/api': { poseApi: api }, '@/api/client': { notifyError: (_error: unknown, message: string) => errors.push(message) },
    '@/utils/recording': { DEFAULT_RECORDING_NAME: 'recording.webm' },
  }
  const source = readFileSync(new URL('../src/pages/MovementTrainingPage.vue', import.meta.url), 'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)![1]!
  const expose = '\nexport const exposed = { patient, exercises, selectedKey, executionMode, started, sessionId, result, rejection, analyzing, recordedBlob, startTask, analyze, ensureSession, reset };'
  const code = ts.transpileModule(source.replace(/import\.meta/g, '({ env: {} })') + expose, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const exports: any = {}
  new Function('require', 'exports', code)((id: string) => modules[id] ?? {}, exports)
  const page = exports.exposed
  const first = { id: 'patient-a', name: 'A', is_deleted: false }
  page.patient.value = first
  page.exercises.value = [{ key: 'BALLET_TENDU', supported_modes: ['SEATED', 'STANDING_SUPPORTED'] }]
  page.selectedKey.value = 'BALLET_TENDU'
  return { page, gate, first, route, writes, analyses, messages, errors, confirmations, beforeLeave, unmount, denyLeave: () => { allowLeave = false } }
}

async function beginMovement(f: ReturnType<typeof movementFixture>) {
  f.page.startTask()
  await f.gate.prepare(f.first, new AbortController().signal)
  f.gate.start()
  f.page.recordedBlob.value = new Blob(['actual-video'], { type: 'video/webm' })
}

const moduleUrl = new URL('../src/training/startController.ts', import.meta.url)
async function controller() {
  assert.ok(existsSync(moduleUrl), 'training start needs a cancellable shared controller')
  return (await import(moduleUrl.href)).TrainingStartController
}

async function gateFixture(initial: { routeId?: string; currentId?: string } = {}, get?: (id: string) => Promise<unknown>) {
  const Controller = await controller()
  const route = vue.reactive({ query: initial.routeId ? { patientId: initial.routeId } : {} })
  const requests: string[] = []
  const bindings: string[] = []
  const starts: string[] = []
  const accepted: string[] = []
  let bound = ''
  const store = { currentPatientId: initial.currentId ?? null, accept: (patient: any) => { accepted.push(patient.id); store.currentPatientId = patient.id } }
  const modules: Record<string, unknown> = {
    vue: { ...vue, onBeforeUnmount: () => {} },
    'vue-router': { useRoute: () => route, useRouter: () => ({ replace: async ({ query }: any) => { route.query = query } }), onBeforeRouteLeave: () => {} },
    '@/api': { patientApi: { get: async (id: string) => { requests.push(id); return get ? get(id) : { id, is_deleted: false } } } },
    '@/stores/patientContext': { usePatientContextStore: () => store },
    '@/training/startController': { TrainingStartController: class extends Controller { constructor(publish: (state: unknown) => void) { super(publish, async () => {}) } } },
  }
  const source = readFileSync(new URL('../src/composables/useTrainingStartGate.ts', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const exports: any = {}
  new Function('require', 'exports', code)((id: string) => modules[id] ?? {}, exports)
  const gate = exports.useTrainingStartGate({ bind: async (patient: any) => { bound = patient.id; bindings.push(bound) }, prepare: async () => {}, start: () => starts.push(bound) })
  return { gate, route, requests, bindings, starts, accepted }
}

const settle = () => new Promise<void>((resolve) => setImmediate(resolve))

test('the rendered start gate changes preparing into a visible number at 3, 2 and 1', async () => {
  const source = readFileSync(new URL('../src/components/TrainingStartGate.vue', import.meta.url), 'utf8')
  const template = source.match(/<template>([\s\S]*?)<\/template>/)![1]!
  const { code } = require('@vue/compiler-dom').compile(template, { mode: 'function', prefixIdentifiers: true })
  const render = new Function('Vue', code)(vue)
  type Node = { type: string; props: Record<string, unknown>; text: string; children: Node[]; parent?: Node }
  const node = (type: string, text = ''): Node => ({ type, text, props: {}, children: [] })
  const renderer = vue.createRenderer({
    createElement: (tag: string) => node(tag), createText: (text: string) => node('#text', text), createComment: (text: string) => node('#comment', text),
    setText: (el: Node, text: string) => { el.text = text },
    setElementText: (el: Node, text: string) => { el.text = text; el.children = [] },
    patchProp: (el: Node, key: string, _old: unknown, value: unknown) => { el.props[key] = value },
    insert: (el: Node, parent: Node, anchor?: Node) => {
      if (el.parent) el.parent.children.splice(el.parent.children.indexOf(el), 1)
      el.parent = parent
      const index = anchor ? parent.children.indexOf(anchor) : -1
      parent.children.splice(index < 0 ? parent.children.length : index, 0, el)
    },
    remove: (el: Node) => { el.parent?.children.splice(el.parent.children.indexOf(el), 1) },
    parentNode: (el: Node) => el.parent,
    nextSibling: (el: Node) => el.parent?.children[el.parent.children.indexOf(el) + 1],
  })
  const state = vue.reactive({ phase: 'preparing', remaining: 0, patient: null, error: '' })
  const Gate = { props: ['state', 'exercise'], setup: () => ({ displayPatientName: (name: string) => name, displayHospitalNumber: (id: string) => id }), render }
  const app = renderer.createApp(Gate, { state, exercise: '测试练习' })
  app.component('ElDialog', { props: ['modelValue'], setup: (props: any, { slots }: any) => () => vue.h('dialog', { visible: props.modelValue }, slots.default?.()) })
  app.component('ElButton', { setup: (_props: any, { slots }: any) => () => vue.h('button', slots.default?.()) })
  app.component('PatientSelector', { render: () => vue.h('aside') })
  const root = node('root')
  const all = (el: Node): Node[] => [el, ...el.children.flatMap(all)]
  app.mount(root)
  try {
    assert.equal(all(root).filter((el) => el.props.class === 'training-preparing').length, 1)
    for (const remaining of [3, 2, 1]) {
      Object.assign(state, { phase: 'countdown', remaining })
      await vue.nextTick()
      const number = all(root).find((el) => el.props.class === 'training-countdown__number')
      assert.ok(number, `countdown ${remaining} must replace the preparing node and its class`)
      assert.equal(number.text, String(remaining))
      assert.equal(all(root).filter((el) => el.props.class === 'training-preparing').length, 0)
    }
    state.phase = 'idle'
    await vue.nextTick()
    assert.ok(all(root).filter((el) => el.type === 'dialog').every((el) => el.props.visible === false))
  } finally { app.unmount() }
})

test('training catalogue and configuration remain visible without a patient', () => {
  for (const name of ['TrainingHubPage', 'PianoTrainingPage', 'MovementTrainingPage']) {
    const source = readFileSync(new URL(`../src/pages/${name}.vue`, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /<PatientSelector\s+v-if="!(?:hasPatient|patient)"/, `${name} must allow browsing`)
  }
})

test('prepare finishes before countdown and starts exactly after 3, 2, 1', async () => {
  const Controller = await controller()
  const events: string[] = []
  const gate = new Controller((state: { phase: string; remaining: number }) => {
    if (state.phase === 'countdown') events.push(String(state.remaining))
  }, async (ms: number) => { assert.equal(ms, 1000) })
  await gate.run(async () => { events.push('prepared') }, () => { events.push('started') })
  assert.deepEqual(events, ['prepared', '3', '2', '1', 'started'])
})

test('double clicks never prepare a second session', async () => {
  const Controller = await controller()
  let finish!: () => void
  let prepared = 0
  const gate = new Controller(() => {}, async () => {})
  const first = gate.run(async () => { prepared++; await new Promise<void>((r) => { finish = r }) }, () => {})
  await gate.run(async () => { prepared++ }, () => {})
  finish()
  await first
  assert.equal(prepared, 1)
})

test('cancel during preparation ignores the late response', async () => {
  const Controller = await controller()
  let finish!: () => void
  let started = false
  const gate = new Controller(() => {}, async () => {})
  const pending = gate.run(() => new Promise<void>((r) => { finish = r }), () => { started = true })
  gate.cancel()
  finish()
  await pending
  assert.equal(started, false)
})

test('cancel during countdown does not start the task', async () => {
  const Controller = await controller()
  let started = false
  const gate = new Controller(() => {}, async () => { gate.cancel() })
  await gate.run(async () => {}, () => { started = true })
  assert.equal(started, false)
})

test('cancellation at each displayed countdown number prevents the start', async () => {
  const Controller = await controller()
  for (const number of [3, 2, 1]) {
    let started = false
    let current = 0
    const gate = new Controller((state: { remaining: number }) => { current = state.remaining }, async () => { if (current === number) gate.cancel() })
    await gate.run(async () => {}, () => { started = true })
    assert.equal(started, false, `cancel at ${number} must never start`)
  }
})

test('training start asks for a patient only after start and resumes the selected patient', async () => {
  const f = await gateFixture()
  assert.equal(f.gate.state.phase, 'idle')
  assert.deepEqual(f.requests, [])
  f.gate.requestStart()
  assert.equal(f.gate.state.phase, 'picking')
  await f.gate.selectPatient({ id: 'chosen', is_deleted: false })
  await settle()
  assert.deepEqual(f.starts, ['chosen'])
  assert.equal(f.route.query.patientId, 'chosen')
})

test('an explicit route patient takes priority over the shared patient context', async () => {
  const f = await gateFixture({ routeId: 'route-patient', currentId: 'other' })
  f.gate.requestStart()
  await settle()
  assert.deepEqual(f.requests, ['route-patient'])
  assert.deepEqual(f.starts, ['route-patient'])
})

test('changing patient while browsing verifies fresh details and updates shared context', async () => {
  const f = await gateFixture({ currentId: 'old' })
  f.gate.changePatient()
  await f.gate.selectPatient({ id: 'new', is_deleted: false })
  assert.deepEqual(f.requests, ['new'])
  assert.deepEqual(f.accepted, ['new'])
  assert.deepEqual(f.starts, [])
})

test('deleted patient returned by fresh verification cannot be selected or started', async () => {
  const f = await gateFixture({}, async (id) => ({ id, is_deleted: true }))
  f.gate.changePatient()
  await f.gate.selectPatient({ id: 'deleted', is_deleted: false })
  assert.deepEqual(f.bindings, [])
  assert.deepEqual(f.accepted, [])
  assert.deepEqual(f.starts, [])
  assert.ok(f.gate.state.error.includes('删除'))
})

test('a late patient lookup cannot replace the patient selected after cancellation', async () => {
  let release!: (value: unknown) => void
  const f = await gateFixture({ currentId: 'old' }, (id) => id === 'old' ? new Promise((resolve) => { release = resolve }) : Promise.resolve({ id, is_deleted: false }))
  f.gate.requestStart()
  f.gate.changePatient()
  await f.gate.selectPatient({ id: 'new', is_deleted: false })
  await settle()
  release({ id: 'old', is_deleted: false })
  await settle()
  assert.deepEqual(f.starts, ['new'])
  assert.deepEqual(f.accepted, ['new'])
  assert.equal(f.route.query.patientId, 'new')
  assert.equal(f.gate.state.phase, 'idle')
})

test('failed preparation returns to idle and allows retry', async () => {
  const Controller = await controller()
  let started = 0
  const gate = new Controller(() => {}, async () => {})
  await assert.rejects(gate.run(async () => { throw new Error('server unavailable') }, () => { started++ }))
  await gate.run(async () => {}, () => { started++ })
  assert.equal(started, 1)
})

test('movement preparation and cancellation never create a server session', async () => {
  const f = movementFixture()
  f.page.startTask()
  await f.gate.prepare(f.first, new AbortController().signal)
  assert.deepEqual(f.writes, [], 'preparation only unlocks audio and fixes the configuration')
  for (const dispose of f.unmount) dispose()
  assert.deepEqual(f.writes, [], 'leaving an unrecorded task must not persist anything')
})

test('movement analysis binds to the patient and configuration accepted at start', async () => {
  const f = movementFixture()
  await beginMovement(f)
  f.page.patient.value = { id: 'patient-b', is_deleted: false }
  f.page.selectedKey.value = 'BALLET_SIDE_BEND'
  f.route.query.selftest = '1'
  await f.page.analyze()
  assert.deepEqual(f.writes, [{ patient: 'patient-a', config: { exercise_type: 'BALLET_TENDU', execution_mode: 'SEATED', input_source: 'HUMAN_KEYBOARD' } }])
})

test('movement analysis retry reuses its session and double save is ignored', async () => {
  let attempts = 0
  const f = movementFixture({ analyze: async () => { if (++attempts === 1) throw new Error('temporary failure'); return { session: { id: 'session-1' } } } })
  await beginMovement(f)
  await Promise.all([f.page.analyze(), f.page.analyze()])
  assert.equal(f.writes.length, 1)
  assert.equal(attempts, 1)
  assert.equal(f.page.result.value, null)
  await f.page.analyze()
  await f.page.analyze()
  assert.equal(f.writes.length, 1)
  assert.equal(attempts, 2, 'a saved clip cannot be saved again')
})

test('movement ignores a session response arriving after page disposal', async () => {
  let finish!: (value: { id: string }) => void
  let uploads = 0
  let delay = false
  const f = movementFixture({ startSession: () => delay ? new Promise((resolve) => { finish = resolve }) : Promise.resolve({ id: 'session-1' }), analyze: async () => { uploads++; return { session: {} } } })
  await beginMovement(f)
  f.page.sessionId.value = null
  delay = true
  const saving = f.page.analyze()
  for (const dispose of f.unmount) dispose()
  finish({ id: 'late-session' })
  await saving
  assert.equal(uploads, 0, 'unmounted task must never begin a late upload')
  assert.equal(f.page.sessionId.value, null)
  assert.equal(f.page.result.value, null)
  assert.equal(f.messages.includes('分析完成，指标已保存'), false)
})

test('movement quality refusal stays retryable and does not claim completion', async () => {
  const f = movementFixture({ analyze: async () => { throw { response: { status: 422, data: { error: { detail: { gate_failures: ['VIDEO_TOO_SHORT'] } } } } } } })
  await beginMovement(f)
  await f.page.analyze()
  assert.equal(f.page.result.value, null)
  assert.deepEqual(f.page.rejection.value.gate_failures, ['VIDEO_TOO_SHORT'])
  f.page.reset()
  f.page.recordedBlob.value = new Blob(['retake'])
  await f.page.analyze()
  assert.equal(f.writes.length, 1, 'quality retry retains the started session id')
})

test('movement route leave keeps an interrupted recording when confirmation is cancelled', async () => {
  const f = movementFixture()
  await beginMovement(f)
  f.denyLeave()
  assert.ok(f.beforeLeave.length > 0, 'the active task needs a route leave guard')
  assert.equal(await f.beforeLeave.at(-1)!(), false)
  assert.equal(f.page.started.value, true)
  assert.ok(f.page.recordedBlob.value)
  assert.equal(f.writes.length, 0)
})

test('movement history refresh failure does not report a saved analysis as failed', async () => {
  const f = movementFixture({ history: async () => { throw new Error('history offline') } })
  await beginMovement(f)
  await f.page.analyze()
  assert.equal(f.page.result.value.session.id, 'session-1')
  assert.ok(!f.errors.includes('动作分析失败。'))
  assert.ok(f.errors.some((message) => message.includes('历史')))
})

test('movement creation failure preserves the clip and configuration for retry', async () => {
  let attempts = 0
  const patients: string[] = []
  const f = movementFixture({ startSession: async (patient: string) => {
    patients.push(patient)
    if (++attempts === 1) throw new Error('server unavailable')
    return { id: 'recovered-session' }
  } })
  await beginMovement(f)
  const clip = f.page.recordedBlob.value
  await f.page.analyze()
  assert.equal(f.page.analyzing.value, false)
  assert.equal(f.page.recordedBlob.value, clip)
  assert.equal(f.page.sessionId.value, null)
  assert.equal(f.page.started.value, true)
  f.page.patient.value = { id: 'other', is_deleted: false }
  await f.page.analyze()
  assert.deepEqual(patients, ['patient-a', 'patient-a'])
  assert.deepEqual(f.analyses, ['recovered-session'])
})

test('movement blocks route leave until a pending save has settled', async () => {
  let finish!: (value: unknown) => void
  const f = movementFixture({ analyze: () => new Promise((resolve) => { finish = resolve }) })
  await beginMovement(f)
  const pending = f.page.analyze()
  await settle()
  assert.equal(await f.beforeLeave.at(-1)!(), false)
  assert.deepEqual(f.confirmations, [], 'a pending save cannot be discarded through a second dialog')
  finish({ session: { id: 'session-1' } })
  await pending
  assert.equal(await f.beforeLeave.at(-1)!(), true)
})
