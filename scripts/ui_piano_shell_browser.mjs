// Isolated local UI fixtures. No real patient data or database writes.
import { chromium } from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import assert from 'node:assert/strict'
import { mkdir, writeFile, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
const out = new URL('../docs/ui-screenshots/ui-piano-shell-20261013/', import.meta.url)
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
await context.addInitScript(() => localStorage.setItem('pd-rehab-token', 'isolated-shell-fixture'))
const patient = { id: 'qa-shell', name: '界面测试患者', hospital_number: 'QA-SHELL', age: 65, sex: 'FEMALE', affected_side: 'LEFT', medication_state: 'ON', dominant_hand: 'RIGHT', is_deleted: false }
const models = [{ name: 'finger_tapping', state: 'READY' }, { name: 'mediapipe_pose', state: 'READY' }, { name: 'micro_expression_model', state: 'UNAVAILABLE' }]
const dashboard = { counts: { total_patients: 24, today_assessments: 3, today_trainings: 7 }, recent_patients: [patient], recent_assessments: [{ id: 'qa-assessment', patient_id: patient.id, patient_name: patient.name, session_type: 'COMPREHENSIVE', medication_state: 'ON', status: 'COMPLETED', created_at: '2026-10-13T00:00:00Z' }], model_status: { models, ready: 2, total: 3 }, mock_mode: false }
let exercises = []
try { exercises = JSON.parse(await readFile(new URL('../docs/ui-screenshots/exercises.json', import.meta.url), 'utf8')) } catch {}
const writes = []
await context.route('**/api/**', async route => {
  const path = new URL(route.request().url()).pathname
  if (!path.startsWith('/api/')) return route.continue()
  if (route.request().method() !== 'GET') writes.push(path)
  let data = { items: [], total: 0, page: 1, page_size: 20 }
  if (path.endsWith('/auth/me')) data = { id: 'qa-staff', display_name: '测试工作人员', username: 'qa' }
  else if (path.endsWith('/system/dashboard')) data = dashboard
  else if (path.endsWith('/patients/qa-shell')) data = patient
  else if (path.endsWith('/patients')) data = { ...data, items: [patient], total: 1 }
  else if (path.endsWith('/pose/exercises')) data = exercises
  else if (path.endsWith('/pose/thresholds')) data = {}
  else if (path.endsWith('/finger-tapping-results')) data = []
  else if (path.endsWith('/piano/baseline')) return route.fulfill({ status: 404, json: { detail: 'No baseline' } })
  await route.fulfill({ json: data })
})
const page = await context.newPage()
const errors = []
page.on('pageerror', error => errors.push(error.message))
async function open(path) {
  await page.goto('http://127.0.0.1:5173' + path)
  await page.locator('.pd-page').waitFor().catch(async error => { console.error('URL:', page.url(), 'Errors:', errors, 'Body:', await page.locator('body').innerText()); throw error })
  await page.waitForTimeout(150)
}
await open('/training')
await page.keyboard.press('Tab')
await page.keyboard.press('Tab')
assert.equal(await page.locator('.pd-brand').evaluate(el => el === document.activeElement), true, 'Tab reaches brand link')
assert.equal(await page.locator('.pd-brand').evaluate(el => getComputedStyle(el).outlineStyle), 'solid', 'brand has visible keyboard focus')
await page.keyboard.press('Enter')
await page.waitForURL('**/dashboard')
assert.equal(await page.locator('.dashboard-stats .pd-stat').count(), 3)
assert.equal(await page.locator('.dashboard-stats .pd-stat-value').allTextContents().then(items => items.join(',')), '24,3,7')
assert.match(await page.locator('.dashboard-models').innerText(), /2 \/ 3 就绪/)
assert.match(await page.locator('.dashboard-models').innerText(), /面部表现分析[\s\S]*不可用/)
await page.getByRole('link', { name: '查看界面测试患者的档案' }).click()
await page.waitForURL('**/patients/qa-shell')
await page.getByRole('button', { name: '折叠或展开侧栏' }).click()
assert.equal(await page.locator('.pd-brand.is-collapsed').count(), 1)
await page.locator('.pd-brand').focus()
await page.keyboard.press('Enter')
await page.waitForURL('**/dashboard')
const checks = ['Keyboard Tab/Enter brand navigation, visible focus, collapsed brand navigation', 'Three API-backed KPI values; component state meaning; semantic patient detail link']
for (const [width, height] of [[1440,900],[1366,768],[1024,768],[768,1024],[430,932],[390,844],[375,812]]) {
  await page.setViewportSize({ width, height })
  for (const [name, path] of Object.entries({ dashboard: '/dashboard', training: '/training', assessment: '/assessment', patients: '/patients', followup: '/follow-up', ballet: '/training/movement' })) {
    await open(path)
    const bounds = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth, main: document.querySelector('.pd-main').scrollWidth, mainWidth: document.querySelector('.pd-main').clientWidth }))
    assert.ok(bounds.doc <= width + 1 && bounds.main <= bounds.mainWidth + 1, name + ' horizontal overflow at ' + width + ': ' + JSON.stringify(bounds))
    if (name === 'training' && width >= 768) {
      for (const selector of ['.training-art', '.training-card h2', '.training-card .pd-primary-link']) {
        const values = await page.locator(selector).evaluateAll(items => items.map(item => { const box = item.getBoundingClientRect(); return [box.top, box.height] }))
        assert.ok(Math.abs(values[0][0] - values[1][0]) <= 2, selector + ' top alignment: ' + JSON.stringify(values))
        assert.ok(Math.abs(values[0][1] - values[1][1]) <= 2, selector + ' equal height: ' + JSON.stringify(values))
      }
    }
    if (['dashboard', 'training'].includes(name) || width === 1440 || width === 390) {
      await page.screenshot({ path: fileURLToPath(new URL(name + '-' + width + 'x' + height + '.png', out)), fullPage: true })
    }
  }
  if (width < 768) {
    await page.getByRole('button', { name: '打开导航菜单' }).click()
    const drawerBrand = page.getByRole('link', { name: '数字康复平台，返回工作台' })
    await drawerBrand.click()
    await page.waitForURL('**/dashboard')
    await page.getByRole('dialog', { name: '导航' }).waitFor({ state: 'hidden' })
  }
  checks.push(width + 'x' + height + ': six pages without horizontal overflow; training covers, titles, CTAs aligned; mobile drawer brand works')
}
assert.deepEqual(errors, [])
assert.deepEqual(writes, [])
await writeFile(new URL('results.json', out), JSON.stringify({ fixture: 'isolated synthetic UI fixture, no database writes', checks, pageErrors: errors, apiWrites: writes }, null, 2))
await browser.close()
console.log(checks.join('\n'))
