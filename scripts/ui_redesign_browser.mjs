// Local browser QA uses isolated request fixtures; no request reaches a patient database.
import { chromium } from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import { mkdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'
const phase = process.argv[2] ?? 'after'
const quick = process.argv.includes('--flows')
const base = `http://127.0.0.1:${phase === 'before' ? 5174 : 5173}`
const out = new URL(`../docs/ui-screenshots/${phase}/`, import.meta.url)
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const patient = { id: 'qa-patient', hospital_number: 'QA-001', name: '测试患者', age: 65, sex: 'FEMALE', affected_side: 'LEFT', medication_state: 'ON', dominant_hand: 'RIGHT', is_deleted: false }
const secondPatient = { ...patient, id: 'qa-second', hospital_number: 'QA-002', name: '另一测试患者' }
const controls = { failStart: false, deleted: false, noBaseline: false, delayStart: 0 }
let holdInitialPatient = false
let releasePatient
let baselineDelay = 0
let holdHistory = false
let historyReleases = []
let raceHistory = false
const writes = []
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
await context.addInitScript(() => localStorage.setItem('pd-rehab-token', 'isolated-ui-test'))
let exercises = []
try { exercises = JSON.parse(await readFile(new URL('../docs/ui-screenshots/exercises.json', import.meta.url), 'utf8')) } catch {}
await context.route('**/api/**', async route => {
  const path = new URL(route.request().url()).pathname
  if (!path.startsWith('/api/')) return route.continue()
  if (holdInitialPatient && path.endsWith('/patients/qa-patient')) {
    holdInitialPatient = false
    await new Promise(resolve => { releasePatient = resolve })
  }
  if (path.endsWith('/piano/baseline') && baselineDelay) await new Promise(resolve => setTimeout(resolve, baselineDelay))
  if (holdHistory && route.request().method() === 'GET' && path.includes('/qa-patient/pose/sessions')) await new Promise(resolve => historyReleases.push(resolve))
  if (route.request().method() === 'POST') {
    writes.push({ path, body: route.request().postDataJSON() })
    if (controls.delayStart) await new Promise(resolve => setTimeout(resolve, controls.delayStart))
    if (controls.failStart) return route.fulfill({ status: 503, json: { detail: 'Isolated failure case' } })
    return route.fulfill({ json: { id: `isolated-session-${writes.length}`, input_source: 'SYNTHETIC_SELFTEST' } })
  }
  let data = { items: [], total: 0, page: 1, page_size: 20 }
  if (path.endsWith('/auth/me')) data = { id: 'qa', display_name: '测试医护', username: 'qa' }
  else if (path.endsWith('/system/dashboard')) data = { counts: { total_patients: 0, today_assessments: 0, today_trainings: 0 }, model_status: { models: [], ready: 0, total: 0 }, recent_patients: [], recent_assessments: [] }
  else if (path.endsWith('/pose/exercises')) data = exercises
  else if (path.endsWith('/pose/thresholds')) data = {}
  else if (path.endsWith('/piano/baseline')) {
    if (controls.noBaseline) return route.fulfill({ status: 404, json: { detail: 'No baseline' } })
    data = { baseline_accuracy: 0.8, baseline_response_latency: 280, baseline_response_latency_cv: 0.2, baseline_timing_mae: 100, baseline_left_accuracy: 0.8, baseline_right_accuracy: 0.8, baseline_left_latency: 280, baseline_right_latency: 280, baseline_spontaneous_bpm: path.includes('qa-second') ? 90 : 60, created_at: '2026-10-13T00:00:00Z' }
  }
  else if (path.endsWith('/patients/qa-patient')) data = { ...patient, is_deleted: controls.deleted }
  else if (path.endsWith('/patients/qa-second')) data = secondPatient
  else if (path.endsWith('/patients')) data = { ...data, items: [patient, secondPatient], total: 2 }
  else if (raceHistory && path.endsWith('/pose/sessions')) data = { ...data, items: [{ id:'race-session', exercise_type:'BALLET_PORT_DE_BRAS', repetition_count: path.includes('qa-second') ? 22 : 11, hold_time_sec: null, valid_pose_frame_ratio: null, started_at:'2026-10-13T00:00:00Z', completed_at:null }] }
  else if (path.endsWith('/finger-tapping-results')) data = []
  await route.fulfill({ json: data })
})
const page = await context.newPage()
const errors = []
page.on('pageerror', error => { errors.push(error.message); console.error('PAGE ERROR:', error.message) })
const shot = async (name) => {
  // Element Plus exposes the dialog before its entry animation becomes opaque.
  await page.waitForTimeout(350)
  return page.screenshot({ path: fileURLToPath(new URL(name, out)) })
}
async function open(path) {
  await page.goto(`${base}${path}`)
  await page.locator('.pd-page, .pd-main > .pd-card').first().waitFor()
  await page.waitForTimeout(250)
}
if (process.argv.includes('--captures')) {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 })
    await open('/training/piano')
    await page.getByRole('button', { name: '开始训练', exact: true }).click()
    await page.getByRole('dialog', { name: '选择本次训练患者' }).waitFor()
    await shot(`patient-picker-${width}.png`)
    const picker = page.getByRole('dialog', { name: '选择本次训练患者' })
    if (width === 1440) await picker.getByRole('button', { name: '选择', exact: true }).first().click()
    else await picker.locator('.selector-cards button').first().click()
    await page.locator('.training-countdown__number').waitFor()
    await shot(`countdown-${width}.png`)
    await page.getByRole('button', { name: '取消启动' }).click()
  }
  assert.deepEqual(errors, [])
  await browser.close()
  console.log('Refreshed four dialog screenshots after entry animations; validation results preserved.')
  process.exit(0)
}
for (const [name, path] of Object.entries(quick ? {} : { training: '/training', piano: '/training/piano', ballet: '/training/movement', dashboard: '/dashboard', assessment: '/assessment', patients: '/patients', followup: '/follow-up' })) {
  await open(path)
  await shot(`${name}-1440.png`)
}
if (phase === 'after') {
  const checks = []
  for (const [width, height] of (quick ? [] : [[1440,900],[1366,768],[1024,768],[768,1024],[430,932],[390,844],[375,812],[320,812]])) {
    await page.setViewportSize({ width, height })
    for (const [name, path] of Object.entries({ training:'/training', piano:'/training/piano', ballet:'/training/movement', dashboard:'/dashboard', assessment:'/assessment', patients:'/patients', followup:'/follow-up?patientId=qa-patient', detail:'/patients/qa-patient' })) {
      await open(path)
      const overflow = await page.evaluate(() => ({ viewport: innerWidth, doc: document.documentElement.scrollWidth, main: document.querySelector('.pd-main').scrollWidth, mainWidth: document.querySelector('.pd-main').clientWidth }))
      assert.ok(overflow.doc <= width + 1 && overflow.main <= overflow.mainWidth + 1, `${name} overflows at ${width}: ${JSON.stringify(overflow)}`)
      if (name === 'training' && width >= 768) {
        const boxes = await page.locator('.training-card .pd-primary-link').evaluateAll(elements => elements.map(element => element.getBoundingClientRect().top))
        assert.ok(Math.abs(boxes[0] - boxes[1]) <= 2, `training CTAs are not aligned: ${boxes}`)
      }
      if (width === 390 || width === 375 || (name === 'ballet' && width === 1366)) await shot(`${name}-${width}.png`)
    }
    checks.push(`${width}x${height}: 8 pages without horizontal overflow`)
  }
  await page.setViewportSize({ width: 1440, height: 900 })
  await open('/training/piano')
  await page.getByRole('button', { name: /双手同时敲击/ }).click()
  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await page.getByRole('dialog', { name: '选择本次训练患者' }).waitFor()
  await shot('patient-picker-1440.png')
  await page.getByRole('dialog').getByRole('button', { name: '选择', exact: true }).first().click()
  await page.locator('.training-countdown__number').waitFor({ timeout: 10000 }).catch(async error => { console.error(await page.locator('body').innerText()); await shot('failure.png'); throw error })
  assert.match(await page.locator('.training-countdown__content').innerText(), /测试患者[\s\S]*QA-001/)
  assert.match(await page.locator('.training-countdown__content').innerText(), /双手同时敲击/)
  await shot('countdown-1440.png')
  await page.getByRole('button', { name: '取消启动' }).click()
  await page.waitForTimeout(3300)
  assert.equal(await page.locator('.pd-main.is-task').count(), 0)
  checks.push('Piano: configure without patient, picker preserves recipe, identity shown, cancellation prevents start')

  let count = writes.length
  await page.getByRole('button', { name: '开始训练', exact: true }).click({ clickCount: 2 })
  await page.locator('.training-countdown__number').waitFor()
  await page.waitForTimeout(3200)
  assert.equal(writes.length, count + 1)
  assert.equal(await page.locator('.pd-main.is-task').count(), 1)
  assert.equal(await page.getByRole('dialog', { name: '选择本次训练患者' }).count(), 0)
  await page.getByRole('button', { name: '结束本轮', exact: true }).click()
  await page.getByRole('button', { name: '保存本轮结果', exact: true }).waitFor()
  checks.push('Piano: existing patient skips picker, double click creates one session, countdown enters task, finish exposes save')

  await open('/training/piano?patientId=qa-patient')
  await page.getByRole('button', { name: '更换患者' }).click()
  await page.getByRole('dialog').getByRole('button', { name: '选择', exact: true }).last().click()
  await page.waitForURL('**patientId=qa-second')
  assert.match(await page.locator('.patient-bar').innerText(), /QA-002/)
  await page.getByText('高级设置（医生）', { exact: true }).click()
  const bpm = await page.locator('.el-form-item').filter({ hasText: 'BPM' }).getByRole('spinbutton').inputValue()
  assert.equal(bpm, '90')
  controls.failStart = true
  count = writes.length
  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await page.locator('.pd-start-error').waitFor()
  assert.equal(await page.locator('.pd-main.is-task').count(), 0)
  assert.equal(writes.length, count + 1)
  assert.match(writes.at(-1).path, /qa-second/)
  controls.failStart = false
  checks.push('Piano: switching patient loads their baseline (90 BPM), server failure stays in configuration')

  controls.deleted = true
  await open('/training/piano?patientId=qa-patient')
  count = writes.length
  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await page.locator('.pd-start-error').waitFor()
  assert.equal(writes.length, count)
  controls.deleted = false
  checks.push('Deleted patient cannot create a session')

  controls.noBaseline = true
  await open('/training/piano?patientId=qa-patient')
  await page.getByRole('button', { name: /双手同时敲击/ }).click()
  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await page.locator('.training-countdown__number').waitFor()
  assert.match(writes.at(-1).path, /calibration$/)
  await page.getByRole('button', { name: '取消启动' }).click()
  assert.match(await page.locator('.practice-preview h2').innerText(), /双手同时敲击/)
  controls.noBaseline = false
  checks.push('No baseline runs calibration first; cancelling restores chosen recipe')

  await open('/training/movement?patientId=qa-patient')
  await page.getByText('站姿（扶椅）', { exact: true }).click()
  assert.equal(await page.locator('.exercise-choice').count(), 5)
  await page.locator('.exercise-choice').last().click()
  const exercise = await page.locator('.exercise-choice.is-selected strong').innerText()
  count = writes.length
  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await page.locator('.training-countdown__number').waitFor()
  assert.match(await page.locator('.training-countdown__content').innerText(), new RegExp(exercise))
  await page.waitForTimeout(3200)
  assert.equal(await page.locator('.pd-main.is-task').count(), 1)
  assert.equal(writes.length, count + 1)
  await page.getByText('录制动作', { exact: true }).waitFor()
  checks.push('Ballet: all five standing actions, selected action preserved, shared countdown, capture only in task')

  await open('/training/movement')
  controls.failStart = true
  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await page.getByRole('dialog', { name: '选择本次训练患者' }).waitFor()
  await page.getByRole('dialog').getByRole('button', { name: '选择', exact: true }).first().click()
  await page.locator('.pd-start-error').waitFor()
  assert.equal(await page.locator('.pd-main.is-task').count(), 0)
  controls.failStart = false
  checks.push('Ballet: no patient opens picker; server failure never enters task')

  await page.setViewportSize({ width: 390, height: 844 })
  await open('/training/piano')
  await page.evaluate(() => {
    window.qaEvents = []
    for (const type of ['pointerdown','pointerup','click']) document.addEventListener(type, event => window.qaEvents.push({type, target:event.target.outerHTML.slice(0,200), x:event.clientX,y:event.clientY, button:document.querySelector('.practice-start')?.getBoundingClientRect().toJSON()}), true)
  })
  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await page.getByRole('dialog', { name: '选择本次训练患者' }).waitFor({ timeout: 5000 }).catch(async error => { console.error(await page.evaluate(() => window.qaEvents)); console.error(page.url(), await page.locator('body').innerText()); await shot('failure-mobile.png'); throw error })
  await shot('patient-picker-390.png')
  await page.getByRole('dialog').locator('.selector-cards button').first().click()
  await page.locator('.training-countdown__number').waitFor()
  await shot('countdown-390.png')
  await page.keyboard.press('Escape')
  await page.waitForTimeout(3200)
  assert.equal(await page.locator('.pd-main.is-task').count(), 0)
  checks.push('Mobile: picker and countdown fit, Escape cancels startup')

  await page.setViewportSize({ width: 1440, height: 900 })
  holdInitialPatient = true
  baselineDelay = 1000
  await open('/training/piano?patientId=qa-patient')
  const baselineRequest = page.waitForRequest(request => new URL(request.url()).pathname.endsWith('/piano/baseline'))
  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await baselineRequest
  releasePatient()
  await page.locator('.training-countdown__number').waitFor()
  assert.doesNotMatch(writes.at(-1).path, /calibration$/)
  await page.getByRole('button', { name: '取消启动' }).click()
  baselineDelay = 0
  checks.push('Delayed initial patient response cannot clear an existing baseline or force calibration')

  raceHistory = true
  holdHistory = true
  await open('/training/movement?patientId=qa-patient')
  await page.getByRole('button', { name: '更换患者', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: '选择', exact: true }).nth(1).click()
  await page.waitForURL('**patientId=qa-second')
  assert.match(await page.locator('.movement-history tbody').innerText(), /22/)
  holdHistory = false
  for (const release of historyReleases) release()
  historyReleases = []
  await page.waitForTimeout(250)
  assert.match(await page.locator('.movement-history tbody').innerText(), /22/)
  assert.doesNotMatch(await page.locator('.movement-history tbody').innerText(), /11/)
  raceHistory = false
  checks.push('Delayed history from patient A cannot replace patient B records')

  await open('/training/piano?patientId=qa-patient')
  controls.delayStart = 700
  const preparingRequest = page.waitForRequest(request => request.method() === 'POST')
  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await preparingRequest
  await page.getByRole('button', { name: '取消启动' }).click()
  await page.waitForTimeout(900)
  assert.equal(await page.locator('.training-countdown__number').count(), 0)
  assert.equal(await page.locator('.pd-main.is-task').count(), 0)
  controls.delayStart = 0
  checks.push('Cancelling preparation ignores a late session response')

  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await page.locator('.training-countdown__number').waitFor()
  await page.getByRole('dialog', { name: '准备训练' }).getByRole('button', { name: '更换患者', exact: true }).click()
  await page.getByRole('dialog', { name: '选择本次训练患者' }).waitFor()
  await page.getByRole('dialog', { name: '选择本次训练患者' }).getByRole('button', { name: '选择', exact: true }).last().click()
  await page.locator('.training-countdown__number').waitFor()
  assert.match(await page.locator('.training-countdown__content').innerText(), /QA-002/)
  await page.getByRole('button', { name: '取消启动' }).click()
  checks.push('Changing patient during countdown starts a fresh countdown for the new identity')

  await page.getByRole('button', { name: '开始训练', exact: true }).click()
  await page.locator('.training-countdown__number').waitFor()
  await page.evaluate(() => document.querySelector('.pd-back').click())
  await page.waitForURL('**/training?patientId=qa-second')
  await page.waitForTimeout(3200)
  assert.equal(await page.locator('.pd-main.is-task').count(), 0)
  assert.equal(await page.locator('.training-countdown__number').count(), 0)
  checks.push('Leaving the page during countdown cannot activate patient task mode later')
  assert.deepEqual(errors, [])
  const { writeFile } = await import('node:fs/promises')
  await writeFile(new URL('../docs/ui-browser-results.json', import.meta.url), JSON.stringify({ isolation: 'All API requests fulfilled with fixtures; no patient database writes', checks, writes: writes.length, pageErrors: errors }, null, 2))
  console.log(checks.join('\n'))
}
await browser.close()
console.log(`Saved ${phase} screenshots with isolated API fixtures.`)
