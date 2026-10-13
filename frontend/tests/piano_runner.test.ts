import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import * as session from '../src/piano/session.ts'
import * as recipes from '../src/piano/recipes.ts'
import * as metrics from '../src/piano/metrics.ts'
import * as extendedMetrics from '../src/piano/extendedMetrics.ts'
import * as samples from '../src/piano/samples.ts'

const require = createRequire(import.meta.url)
const vue = require('vue')
const ts = require('typescript')

/** Real runner and reactive Vue state; only browser/audio boundaries are isolated. */
function runnerFixture() {
  let now = 0
  let nextFrame = 0
  let stops = 0
  const frames = new Map<number, () => void>()
  const unmount: Array<() => void> = []
  const sounding = new Set<number>()
  const engine = {
    unlock: async () => {}, load: async () => {},
    status: () => ({ ready: true, failed: [], contextState: 'running' }),
    play: (midi: number) => sounding.add(midi), click: () => {},
    stopAll: () => { stops++; sounding.clear() },
  }
  const modules: Record<string, unknown> = {
    vue: { ...vue, onBeforeUnmount: (fn: () => void) => unmount.push(fn) },
    '@/piano/engine': { getPianoEngine: () => engine, INPUT_LATENCY_NOTE: 'test audio boundary' },
    '@/piano/session': session, '@/piano/recipes': recipes,
    '@/piano/metrics': metrics, './extendedMetrics': extendedMetrics,
    '@/piano/samples': samples,
  }
  const source = readFileSync(new URL('../src/piano/useRunner.ts', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const exports: any = {}
  new Function('require', 'exports', 'performance', 'requestAnimationFrame', 'cancelAnimationFrame', code)(
    (id: string) => {
      assert.ok(id in modules, `runner dependency ${id} must use its real module or an explicit browser boundary`)
      return modules[id]
    }, exports, { now: () => now },
    (callback: () => void) => { frames.set(++nextFrame, callback); return nextFrame },
    (id: number) => frames.delete(id),
  )
  const runner = exports.usePianoRunner()
  const difficulty = { ...session.DEFAULT_DIFFICULTY, session_duration_sec: 20 }
  const options = { mode: 'SINGLE_KEY_RHYTHM', difficulty, seed: 17, weakHand: null, countInMs: 0 }
  return {
    runner, options, difficulty, sounding, frames,
    stops: () => stops,
    at: (ms: number) => { now = ms },
    step: (ms: number) => {
      now = ms
      const pending = [...frames.values()]
      frames.clear()
      for (const callback of pending) callback()
    },
    dispose: () => { for (const cleanup of unmount) cleanup() },
  }
}

test('runner progress invalidates its cached value as successive cues resolve', async () => {
  const f = runnerFixture()
  f.runner.start(f.options)
  const observed: number[] = []
  const stop = vue.watchEffect(() => observed.push(f.runner.progress.value))
  try {
    assert.equal(f.runner.progress.value, 0, 'read before resolution to exercise the computed cache')
    const cues = f.runner.cues.value
    assert.ok(cues.length > 2)
    for (let index = 0; index < 2; index++) {
      f.step(cues[index].targetMs + f.difficulty.judgement_window_ms / 2 + 1)
      await vue.nextTick()
      assert.equal(f.runner.progress.value, (index + 1) / cues.length)
      assert.equal(observed.at(-1), (index + 1) / cues.length, 'a reactive progress consumer must update')
    }
    assert.deepEqual(observed, [0, 1 / cues.length, 2 / cues.length])
  } finally { stop(); f.dispose() }
})

test('release after blur belongs to the later physical press of the same key', () => {
  const f = runnerFixture()
  f.runner.start(f.options)
  f.at(700)
  f.runner.press('KeyJ')
  f.runner.releaseAll()
  assert.equal(f.runner.pressedKeys.value.size, 0)
  f.at(1500)
  f.runner.press('KeyJ')
  f.at(1580)
  f.runner.release('KeyJ')
  const presses = f.runner.presses.value
  assert.equal(presses.length, 2)
  assert.equal(presses[0].downTimeMs, 700)
  assert.equal(presses[0].upTimeMs, null, 'blur is not a physical release')
  assert.equal(presses[0].relativeUpMs, null)
  assert.equal(presses[1].upTimeMs, 1580)
  assert.equal(presses[1].relativeUpMs - presses[1].relativeDownMs, 80)
  assert.equal(f.runner.pressedKeys.value.size, 0)
  f.dispose()
})

for (const action of ['cancel', 'finish', 'unmount'] as const) {
  test(`${action} clears held keys and stops audio without inventing a keyup`, () => {
    const f = runnerFixture()
    f.runner.start(f.options)
    f.step(700)
    f.runner.press('KeyJ')
    assert.equal(f.runner.pressedKeys.value.size, 1)
    assert.ok(f.sounding.size > 0)
    f.at(1200)
    if (action === 'unmount') f.dispose()
    else f.runner[action]()
    assert.equal(f.runner.state.value, action === 'finish' ? 'FINISHED' : 'IDLE')
    assert.equal(f.runner.pressedKeys.value.size, 0)
    assert.equal(f.frames.size, 0, 'no scheduled animation survives cleanup')
    assert.equal(f.sounding.size, 0)
    assert.ok(f.stops() > 0)
    assert.equal(f.runner.presses.value[0].upTimeMs, null)
    assert.equal(f.runner.presses.value[0].relativeUpMs, null)
    assert.ok(f.runner.events.value.every((event: session.PianoRawEvent) => event.key_up_time_ms === null && event.hold_duration_ms === null))
    // A browser keyup delivered after cleanup must not fill the old null release.
    f.at(1300)
    f.runner.release('KeyJ')
    assert.equal(f.runner.presses.value[0].upTimeMs, null)
    assert.equal(f.runner.presses.value[0].relativeUpMs, null)
    if (action !== 'unmount') f.dispose()
  })
}

test('a cancelled round can start again and the same held key is a new press', () => {
  const f = runnerFixture()
  f.runner.start(f.options)
  f.at(700)
  f.runner.press('KeyJ')
  f.runner.cancel()
  f.at(1000)
  f.runner.start(f.options)
  f.at(1500)
  f.runner.press('KeyJ')
  f.at(1580)
  f.runner.release('KeyJ')
  assert.equal(f.runner.presses.value.length, 1)
  assert.equal(f.runner.presses.value[0].relativeDownMs, 500)
  assert.equal(f.runner.presses.value[0].relativeUpMs, 580)
  assert.equal(f.runner.pressedKeys.value.size, 0)
  f.dispose()
})

test('pointer cancellation clears only its held key and never fabricates a release', () => {
  const f = runnerFixture()
  f.runner.start(f.options)
  f.at(700)
  f.runner.press('KeyJ')
  f.at(720)
  f.runner.press('KeyM')
  f.at(750)
  f.runner.cancelPress('KeyJ')
  assert.deepEqual([...f.runner.pressedKeys.value], [samples.BINDING_BY_CODE.KeyM.midi])
  assert.equal(f.runner.presses.value[0].upTimeMs, null)
  assert.equal(f.runner.presses.value[0].relativeUpMs, null)
  f.at(800)
  f.runner.release('KeyJ')
  assert.equal(f.runner.presses.value[0].upTimeMs, null, 'late pointerup after cancellation is not a release measurement')
  f.at(820)
  f.runner.release('KeyM')
  assert.equal(f.runner.presses.value[1].upTimeMs, 820, 'the other held key still has its real release')
  f.at(1500)
  f.runner.press('KeyJ')
  f.at(1580)
  f.runner.release('KeyJ')
  const presses = f.runner.presses.value
  assert.equal(presses.length, 3, 'pointercancel removes the old repeat guard')
  assert.equal(presses[0].upTimeMs, null)
  assert.equal(presses[2].upTimeMs, 1580)
  assert.equal(presses[2].relativeUpMs - presses[2].relativeDownMs, 80)
  assert.equal(f.runner.pressedKeys.value.size, 0)
  f.dispose()
})
