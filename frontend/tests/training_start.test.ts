import assert from 'node:assert/strict'
import test from 'node:test'
import { existsSync, readFileSync } from 'node:fs'

const moduleUrl = new URL('../src/training/startController.ts', import.meta.url)
async function controller() {
  assert.ok(existsSync(moduleUrl), 'training start needs a cancellable shared controller')
  return (await import(moduleUrl.href)).TrainingStartController
}

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

test('failed preparation returns to idle and allows retry', async () => {
  const Controller = await controller()
  let started = 0
  const gate = new Controller(() => {}, async () => {})
  await assert.rejects(gate.run(async () => { throw new Error('server unavailable') }, () => { started++ }))
  await gate.run(async () => {}, () => { started++ })
  assert.equal(started, 1)
})
