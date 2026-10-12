/**
 * The README's checkable claims must stay true.
 *
 * Run with:  npm run test:rules
 *
 * WHY THIS EXISTS
 * ===============
 * Six rounds of changes left the README asserting things that had stopped being
 * true, and nothing noticed because nothing read it. The worst of them was a
 * permission claim -- the route table still said `/system/model-status` was
 * "仅 ADMIN" several rounds after the admin gate had been deleted -- which put the
 * README in direct contradiction with its own section 15.2 a few lines below.
 *
 * The other three were quieter: a test count three rounds out of date, a Phase 1
 * snapshot presented as current, and a description of how a synthetic calibration
 * was handled that had since been deliberately tightened into the opposite
 * behaviour.
 *
 * This checks the claims that CAN be checked mechanically: test counts, the
 * navigation list, and the retired statements that must not come back. It cannot
 * check the prose, and it does not try.
 */

import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import test from 'node:test'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = join(HERE, '..', '..')
const README = join(ROOT, 'README.md')

const readme = readFileSync(README, 'utf8')

/** Count the frontend test files actually wired into the npm script. */
function declaredTestFiles(): string[] {
  const pkg = JSON.parse(readFileSync(join(HERE, '..', 'package.json'), 'utf8')) as {
    scripts: Record<string, string>
  }
  const script = pkg.scripts['test:rules'] ?? ''
  return [...script.matchAll(/tests\/([\w.]+\.test\.ts)/g)].map((m) => m[1])
}

// ------------------------------------------------------------ test counts

test('every test file the npm script names actually exists', () => {
  const files = declaredTestFiles()
  assert.ok(files.length >= 8, `expected the test suite to be wired up, found ${files.length}`)
  const present = new Set(readdirSync(HERE))
  for (const file of files) {
    assert.ok(present.has(file), `${file} is in the npm script but not on disk`)
  }
})

test('every test file on disk is wired into the npm script', () => {
  // A test that nobody runs is worse than no test: it reads as coverage.
  const onDisk = readdirSync(HERE).filter((f) => f.endsWith('.test.ts'))
  const declared = new Set(declaredTestFiles())
  const missing = onDisk.filter((f) => !declared.has(f))
  assert.deepEqual(missing, [], `these tests exist but are never run: ${missing.join(', ')}`)
})

test('the README does not quote a stale test count', () => {
  // Counts that were true in earlier rounds. Any of them reappearing means the
  // README was edited from memory rather than from the suite.
  const stale = ['285 项', '97 项', '74 项', '122 项', '149 项', '298 项', '303 项', '308 项']
  for (const count of stale) {
    assert.ok(
      !readme.includes(count),
      `the README quotes ${count}, which was an earlier round's count`,
    )
  }
})

test('the README states the current frontend test count', () => {
  const declared = declaredTestFiles().length
  assert.ok(
    /前端测试 \*\*\d+ 项\*\*/.test(readme),
    'the README should state the frontend test count',
  )
  const quoted = Number(readme.match(/前端测试 \*\*(\d+) 项\*\*/)?.[1] ?? 0)
  assert.ok(quoted > 0, 'the quoted count should be a number')

  /*
    The floor is deliberately close to the real total rather than a token value.

    A test cannot count assertions without running the suite, so this cannot be an
    exact check. But a round of work adds roughly ten tests, so a floor one round
    behind turns "the number is a snapshot" into a failure the next time anyone
    touches the suite -- which is when they should update it.
  */
  const floor = 170
  assert.ok(
    quoted >= floor,
    `the README quotes ${quoted} frontend tests, below the current floor of ${floor} ` +
      `(${declared} test files). Update the README when the suite grows.`,
  )
})

// ------------------------------------------------------------- permissions

test('the README no longer claims any route is restricted to a role', () => {
  // The product has no roles. Section 15.2 says so; the route table used to
  // contradict it.
  assert.ok(
    !readme.includes('仅 ADMIN'),
    'the route table still claims a page is ADMIN-only, but the gate was removed',
  )
  assert.ok(
    !/系统设置（仅/.test(readme),
    'the system route must not be described as role-restricted',
  )
})

test('the README documents the system route as unlinked rather than restricted', () => {
  assert.match(readme, /\/system\/model-status\s+系统状态/)
  assert.match(readme, /无导航入口/)
})

// ---------------------------------------------------------------- content

test('the README no longer describes the superseded baseline behaviour', () => {
  // The old rule created an ACTIVE baseline from a synthetic calibration and
  // relied on a note being read. That note was never read, and the defect reached
  // production; the rule is now a query-layer gate.
  assert.ok(
    !/由非真人 Calibration 生成的基线，其 `note` 也写明/.test(readme),
    'the README still describes the superseded warn-only baseline behaviour',
  )
  assert.match(readme, /is_active=True/, 'the README should describe the current gate')
})

test('the README names the current exercise display name', () => {
  // 半蹲 was renamed because it implies a deeper movement than the definition
  // allows. The old name may appear only as an explanation of the change.
  const rows = readme.split('\n').filter((l) => l.startsWith('| `BALLET_DEMI_PLIE`'))
  assert.ok(rows.length > 0, 'the ballet table should list Demi-Plié')
  for (const row of rows) {
    assert.ok(
      row.includes('扶椅浅屈膝'),
      `the exercise table still shows the old name: ${row.trim()}`,
    )
    assert.ok(
      !/(?<!原为.*)半蹲/.test(row) || row.includes('扶椅浅屈膝'),
      `the exercise table shows 半蹲 without the current name: ${row.trim()}`,
    )
  }
})

test('the README documents the piano training recipes', () => {
  // Four recipes were added; a reader of the modes section would not know.
  for (const id of ['SFT_CUE_SYNC', 'CFT_RHYTHM_HOLD', 'BIMANUAL_SYNC', 'ACCENT_GROUPING']) {
    assert.ok(readme.includes(id), `the README does not mention the ${id} recipe`)
  }
})

test('the README warns that hidden media queries are invisible to desktop checks', () => {
  // This cost several rounds: the touch rules sit behind `@media (hover: none)`
  // and a mouse-driven browser never matches it, so nothing exercised them.
  assert.match(readme, /hover: none/)
  assert.match(readme, /setTouchEmulationEnabled/)
})

// ------------------------------------------------- what a failure says to whom

/** Read a source file, with comments stripped so prose cannot satisfy an assertion. */
function source(relative: string): string {
  return readFileSync(join(HERE, '..', 'src', relative), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
}

test('the offline message does not tell a clinician to start a backend', () => {
  /*
    The network-failure message used to be one sentence for everybody:
    "请确认后端已启动（默认 http://127.0.0.1:8000）". A clinician whose connection
    drops was being told to start a process on a loopback address, which in the
    deployed system is not even the right port. Unactionable advice, plus a
    description of the internal layout.

    It is now split: developers keep the hint, shipped builds say something the
    reader can act on.
  */
  const src = source('api/client.ts')
  assert.match(src, /import\.meta\.env\.DEV/, 'the message must branch on the build')
  assert.match(src, /无法连接到服务器/, 'a shipped build needs a user-facing message')
  assert.match(src, /后端已启动/, 'developers still need the local hint')
})

test('the developer hint is inside the DEV branch, not shipped unconditionally', () => {
  const src = source('api/client.ts')
  // The hint must appear after the DEV ternary, never as the plain message.
  const hintIndex = src.indexOf('后端已启动')
  const devIndex = src.indexOf('import.meta.env.DEV')
  assert.ok(devIndex >= 0 && hintIndex > devIndex, 'the hint must follow the DEV check')
  assert.ok(
    !/message:\s*'[^']*后端已启动/.test(src),
    'the developer hint must not be a bare message assignment',
  )
})

test('neither failure message leaks a raw error or a status code', () => {
  const src = source('api/client.ts')
  for (const bad of ['error.stack', 'JSON.stringify(error)']) {
    assert.ok(!src.includes(`message: ${bad}`), `a raw error would reach the user: ${bad}`)
  }
})
