/**
 * Contract tests for the interface itself.
 *
 * Run with:  npm run test:rules
 *
 * These read the source and assert the properties that were deliberately built
 * and would otherwise erode silently. Each one corresponds to a decision that
 * took a debugging round to get right, or to a rule the product owner stated:
 * a re-added role gate, a navigation entry that should not exist, a camera
 * element that lost `playsinline`, a piano key that went back to `click`.
 *
 * They are source assertions rather than DOM tests on purpose: the project has
 * no jsdom or testing-library and adding one for this would be a larger
 * dependency than the whole rule-test suite. What they cannot check is
 * behaviour; that is what the browser verification in the report covers.
 */

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import test from 'node:test'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = join(HERE, '..', 'src')

function read(relative: string): string {
  return readFileSync(join(SRC, relative), 'utf8')
}

/** Strip comments so a rule mentioned in a doc comment does not pass a check. */
function code(relative: string): string {
  return read(relative)
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1')
}

/**
 * Strip every kind of comment, including the HTML ones inside templates.
 *
 * A note explaining *why* a rule exists legitimately mentions the words the rule
 * is about ("Mock mode is an operator condition..."), and that must not be read
 * as the interface showing them.
 */
function withoutComments(relative: string): string {
  return read(relative)
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1')
}

/**
 * Only the text a user can actually read.
 *
 * Two sources: the template block, and the arguments of the calls that put text
 * on screen (`ElMessage`, `ElMessageBox`). Everything else in `<script>` is
 * plumbing -- `input_source === 'SYNTHETIC_SELFTEST'` selects an API payload and
 * is never rendered, so flagging it would be a false positive that teaches
 * people to ignore the test.
 */
function userFacingText(relative: string): string {
  const src = withoutComments(relative)

  const template = src.match(/<template>([\s\S]*)<\/template>/)?.[1] ?? ''

  const messages = [...src.matchAll(/El(?:Message|MessageBox)\.\w+\(([^)]*)\)/g)]
    .map((m) => m[1])
    .join('\n')

  return `${template}\n${messages}`
}

// --------------------------------------------------------------- permissions

test('the auth store exposes no product-level role', () => {
  const src = code('stores/auth.ts')
  assert.ok(!/roleLabel/.test(src), 'roleLabel must not exist: nothing differs by role')
  assert.ok(!/isAdmin/.test(src), 'isAdmin must not exist: there is no admin surface')
})

test('no route is gated on a role', () => {
  const src = code('router/index.ts')
  assert.ok(!/adminOnly/.test(src), 'routes must not carry adminOnly')
  assert.ok(!/isAdmin/.test(src), 'the guard must not consult a role')
})

test('the shell has no role gate and shows no role badge', () => {
  const src = code('layouts/MainLayout.vue')
  assert.ok(!/adminOnly/.test(src))
  assert.ok(!/isAdmin/.test(src))
  assert.ok(!/roleLabel/.test(src))
  // The header shows the display name only.
  assert.match(src, /auth\.displayName/)
})

test('the patient detail page never appeared in a role-gated branch', () => {
  const src = code('pages/PatientDetailPage.vue')
  assert.ok(!/isAdmin/.test(src))
})

// ---------------------------------------------------------------- navigation

test('the sidebar shows exactly the five product entries', () => {
  const src = read('layouts/MainLayout.vue')
  const block = src.slice(src.indexOf('const entries'), src.indexOf('const activeEntry'))
  const titles = [...block.matchAll(/title: '([^']+)'/g)].map((m) => m[1])
  assert.deepEqual(titles, ['工作台', '患者档案', '评估中心', '康复训练', '随访与报告'])
})

test('neither 系统设置 nor 功能测试 is reachable from the navigation', () => {
  const src = read('layouts/MainLayout.vue')
  const block = src.slice(src.indexOf('const entries'), src.indexOf('const activeEntry'))
  assert.ok(!block.includes('系统设置'), 'technical surfaces are not a clinical function')
  assert.ok(!block.includes('功能测试'))
  assert.ok(!block.includes('/system'), 'the system route must not be linked from the menu')
})

test('the mobile drawer offers the same entries as the sidebar', () => {
  const src = read('layouts/MainLayout.vue')
  assert.match(src, /pd-nav-drawer-list/)
  // One `entries` array feeds both, so they cannot drift apart.
  const vForCount = (src.match(/v-for="entry in entries"/g) ?? []).length
  assert.equal(vForCount, 2, 'sidebar and drawer both iterate the single entries array')
})

test('the functional-assessment route stays hidden and unlinked', () => {
  const src = code('router/index.ts')
  assert.match(src, /functional-assessment/)
  const layout = read('layouts/MainLayout.vue')
  assert.ok(!layout.includes('functional-assessment'))
})

// --------------------------------------------------------------------- mobile

test('all responsive breakpoints live in one stylesheet', () => {
  const src = read('styles/responsive.css')
  assert.match(src, /max-width: 1199px/)
  assert.match(src, /max-width: 767px/)
  assert.match(src, /max-width: 479px/)
  assert.match(src, /--pd-touch:/)
  // iOS zooms a focused input below 16px, which jumps the whole layout.
  assert.match(src, /font-size: 16px/)
})

test('pages do not define their own unrelated breakpoints', () => {
  // A page may tune itself, but only at the shared widths.
  const files = [
    'pages/PatientsPage.vue',
    'pages/PianoTrainingPage.vue',
    'pages/MovementTrainingPage.vue',
    'components/PatientSelector.vue',
    'components/VideoCapturePanel.vue',
  ]
  const allowed = new Set(['1199px', '767px', '479px'])
  for (const file of files) {
    const found = [...read(file).matchAll(/max-width:\s*(\d+px)/g)].map((m) => m[1])
    for (const width of found) {
      assert.ok(allowed.has(width), `${file} uses a non-standard breakpoint ${width}`)
    }
  }
})

test('feature-card grids can never exceed their container', () => {
  const files = [
    'pages/AssessmentHubPage.vue',
    'pages/FollowUpPage.vue',
    'pages/MovementTrainingPage.vue',
    'pages/PianoTrainingPage.vue',
    'pages/TrainingHubPage.vue',
    'components/MetricSummaryCards.vue',
  ]
  for (const file of files) {
    const src = read(file)
    const grids = [...src.matchAll(/grid-template-columns:\s*(.+);/g)].map((m) => m[1])
    for (const value of grids) {
      if (!value.includes('auto-fill')) continue
      assert.match(
        value,
        /minmax\(min\(/,
        `${file} has a fixed minimum track, which overflows a phone: ${value}`,
      )
    }
  }
})

test('the patient list renders cards on mobile and a table on desktop', () => {
  const src = read('pages/PatientsPage.vue')
  assert.match(src, /class="desktop-only pd-table-scroll"/)
  assert.match(src, /class="mobile-only"/)
  assert.match(src, /<PatientCard/)
  // Both views are fed by the one rows array.
  const rowsBindings = (src.match(/:data="rows"/g) ?? []).length
  assert.equal(rowsBindings, 1, 'the table reads rows once')
  assert.match(src, /v-for="row in rows"/)
})

test('the patient selector offers a card list as well as a table', () => {
  const src = read('components/PatientSelector.vue')
  assert.match(src, /class="mobile-only selector-cards"/)
  assert.match(src, /class="desktop-only pd-table-scroll"/)
})

test('the mobile pager drops the controls that do not fit', () => {
  const src = read('pages/PatientsPage.vue')
  assert.match(src, /paginationLayout/)
  assert.match(src, /'prev, pager, next'/)
})

// ---------------------------------------------------------------------- piano

test('piano keys respond to pointerdown, not click', () => {
  const src = read('piano/PianoKeyboard.vue')
  assert.match(src, /@pointerdown="onDown/)
  assert.ok(!/@click="onDown/.test(src), 'click waits for the tap to end')
  // A cancelled touch must release the key or a note sticks down.
  assert.match(src, /@pointercancel="onCancel/)
})

test('the piano keyboard is scrollable on a phone with real key widths', () => {
  const src = read('piano/PianoKeyboard.vue')
  assert.match(src, /\.piano-scroll/)
  assert.match(src, /min-width: 46px/)
  assert.match(src, /scrollIntoView/)
})

// --------------------------------------------------------------------- camera

test('the capture video is inline on iOS', () => {
  const src = read('components/VideoCapturePanel.vue')
  assert.match(src, /playsinline/, 'without it iOS takes the video fullscreen')
  assert.match(src, /muted/)
})

test('camera failures are described in plain language', () => {
  const src = read('components/VideoCapturePanel.vue')
  assert.match(src, /describeCameraError/)
  assert.match(src, /请允许浏览器访问摄像头/)
  // The DOMException name goes to the console, not to the patient.
  assert.match(src, /console\.warn/)
})

test('the camera switch only appears when a second camera exists', () => {
  const src = read('components/VideoCapturePanel.vue')
  assert.match(src, /canSwitchCamera/)
  assert.match(src, /v-if="canSwitchCamera/)
})

// --------------------------------------------------------------------- ballet

test('ballet audio is unlocked by a user gesture before it starts', () => {
  const src = read('ballet/BalletRhythmPanel.vue')
  const unlockAt = src.indexOf('engine.unlock()')
  const startAt = src.indexOf('engine.start(')
  assert.ok(unlockAt >= 0, 'the context must be resumed')
  assert.ok(startAt >= 0, 'the engine must be started')
  assert.ok(unlockAt < startAt, 'resume must happen before scheduling, inside the click handler')
})

test('the rhythm engine schedules against the audio clock, not setInterval', () => {
  const src = read('ballet/rhythmEngine.ts')
  assert.match(src, /context\.currentTime/)
  assert.match(src, /SCHEDULE_AHEAD_SEC/)
  // A UI timer exists, but only to top up the schedule.
  assert.ok(!/setInterval\([^)]*click/i.test(src))
})

// ------------------------------------------------------------------ copy scan

test('no developer or demo copy survives in the signed-in interface', () => {
  const forbidden = [
    '科研',
    'Demo',
    '演示',
    'Mock',
    'Phase',
    '虚拟',
    'BOOTSTRAP_ADMIN',
    '不能替代',
    '辅助参考',
    'MODEL_NOT_CONFIGURED',
    'SEED_DEMO',
    'SYNTHETIC_SELFTEST',
  ]
  // The technical status page is the deliberate exception: it exists for
  // whoever operates the server and is not in any navigation.
  const exempt = new Set([
    'pages/ModelStatusPage.vue',
    'utils/source.ts',
    'utils/errors.ts',
  ])
  const files = [
    'layouts/MainLayout.vue',
    'pages/LoginPage.vue',
    'pages/DashboardPage.vue',
    'pages/PatientsPage.vue',
    'pages/PatientDetailPage.vue',
    'pages/PatientFormPage.vue',
    'pages/AssessmentHubPage.vue',
    'pages/MicroExpressionPage.vue',
    'pages/FingerTappingPage.vue',
    'pages/TrainingHubPage.vue',
    'pages/PianoTrainingPage.vue',
    'pages/MovementTrainingPage.vue',
    'pages/FollowUpPage.vue',
    'components/PatientSelector.vue',
    'components/PatientCard.vue',
    'components/PatientTaskLayout.vue',
  ]
  for (const file of files) {
    if (exempt.has(file)) continue
    // Only rendered text: template content and literals, with comments removed
    // and internal-code comparisons excluded.
    const visible = userFacingText(file)
    for (const term of forbidden) {
      assert.ok(
        !visible.includes(term),
        `${file} still shows "${term}" to a user`,
      )
    }
  }
})

test('the login page keeps credentials out of the interface', () => {
  const src = read('pages/LoginPage.vue')
  assert.ok(!/\.env/.test(src))
  assert.ok(!/BOOTSTRAP/.test(src))
  assert.ok(!/演示账号/.test(src))
  assert.ok(!/管理员|医生账号/.test(src))
})
