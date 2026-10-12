/**
 * Navigation integrity: every entry a user can press must lead somewhere real.
 *
 * Run with:  npm run test:rules
 *
 * WHY THIS EXISTS
 * ===============
 * The acceptance criteria for this round include "页面和按钮没有无效入口" -- no
 * dead entries. That is easy to break and hard to notice: a card whose `to` names
 * a route that was renamed goes nowhere, a `router.push` to a path that no longer
 * exists lands on the not-found page, and neither throws, so a click-through
 * review can miss it while a patient hits it.
 *
 * The routes are parsed from the router source rather than imported, because
 * importing it would pull in every lazily-loaded page component and the rule
 * tests run without a DOM.
 *
 * What this covers: destinations that do not resolve.
 * What it does NOT cover: a control that is wired to a handler which does
 * nothing. That cannot be judged from source, and is left to the browser
 * click-through in the report.
 */

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'
import test from 'node:test'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = join(HERE, '..', 'src')
const ROUTER = join(SRC, 'router', 'index.ts')

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) sourceFiles(full, out)
    else if (/\.(vue|ts)$/.test(entry)) out.push(full)
  }
  return out
}

const routerSource = readFileSync(ROUTER, 'utf8')

/** Route names declared in the router, including the redirect targets. */
function declaredNames(): Set<string> {
  const names = new Set<string>()
  for (const m of routerSource.matchAll(/^\s+name:\s*'([^']+)'/gm)) names.add(m[1])
  // Redirects are declared as `name: 'x'` inside an arrow body, which the
  // pattern above also matches, but assert it explicitly so a change in
  // formatting cannot quietly shrink the set.
  for (const m of routerSource.matchAll(/redirect:[\s\S]{0,120}?name:\s*'([^']+)'/g)) names.add(m[1])
  return names
}

/** Child route paths, which are relative to the '/' parent. */
function declaredPaths(): Set<string> {
  const paths = new Set<string>(['/', '/login'])
  for (const m of routerSource.matchAll(/^\s+path:\s*'([^']*)'/gm)) {
    const p = m[1]
    if (p === '' || p.startsWith('/')) {
      if (p) paths.add(p)
      continue
    }
    paths.add('/' + p)
  }
  return paths
}

/**
 * True when a concrete URL matches a declared path.
 *
 * The dynamic segments are compared structurally: `/patients/abc` matches
 * `/patients/:id`, and `/patients/abc/edit` matches `/patients/:id/edit`.
 */
function matchesPath(url: string, pattern: string): boolean {
  const clean = url.split('?')[0].replace(/\/+$/, '') || '/'
  if (clean === pattern) return true
  const a = clean.split('/').filter(Boolean)
  const b = pattern.split('/').filter(Boolean)
  if (a.length !== b.length) return false
  return b.every((seg, i) => seg.startsWith(':') || seg === a[i])
}

const NAMES = declaredNames()
const PATHS = declaredPaths()

// --------------------------------------------------------------- the table

test('the route table parses and holds the expected surface', () => {
  assert.ok(NAMES.size >= 14, `expected the route names to be found, got ${NAMES.size}`)
  assert.ok(PATHS.size >= 10, `expected the route paths to be found, got ${PATHS.size}`)
  for (const name of ['login', 'dashboard', 'patients', 'assessment', 'training', 'follow-up']) {
    assert.ok(NAMES.has(name), `route ${name} is missing`)
  }
})

test('/follow-up is a real route, and feature testing is the only hidden one', () => {
  assert.ok(PATHS.has('/follow-up'), 'the fifth navigation entry must be routable')
  // `hidden` is only meaningful for surfaces genuinely not offered.
  const hidden = [...routerSource.matchAll(/name:\s*'([^']+)',\s*\n\s*component:[\s\S]{0,160}?hidden:\s*true/g)]
    .map((m) => m[1])
  for (const name of hidden) {
    assert.equal(name, 'functional-assessment', `${name} should not be marked hidden`)
  }
})

// ------------------------------------------------- every navigation target

/** Literal `to="/x"` and `router.push('/x')` destinations across the app. */
function literalDestinations(): Array<{ target: string; where: string }> {
  const found: Array<{ target: string; where: string }> = []
  for (const file of sourceFiles(SRC)) {
    const rel = relative(SRC, file).replace(/\\/g, '/')
    readFileSync(file, 'utf8')
      .split('\n')
      .forEach((line, i) => {
        for (const m of line.matchAll(/to="(\/[^"{}]*)"/g)) {
          found.push({ target: m[1], where: `${rel}:${i + 1}` })
        }
        for (const m of line.matchAll(/(?:router\.(?:push|replace))\(\s*'(\/[^']*)'/g)) {
          found.push({ target: m[1], where: `${rel}:${i + 1}` })
        }
        for (const m of line.matchAll(/(?:^|[\s,{])to:\s*'(\/[^']*)'/g)) {
          found.push({ target: m[1], where: `${rel}:${i + 1}` })
        }
      })
  }
  return found
}

test('every literal navigation destination resolves to a declared route', () => {
  const destinations = literalDestinations()
  assert.ok(destinations.length >= 6, `expected to find navigation targets, got ${destinations.length}`)

  for (const { target, where } of destinations) {
    const ok = [...PATHS].some((pattern) => matchesPath(target, pattern))
    assert.ok(ok, `${where} navigates to ${target}, which no route matches`)
  }
})

test('every named destination resolves to a declared route name', () => {
  const referenced: Array<{ name: string; where: string }> = []
  for (const file of sourceFiles(SRC)) {
    const rel = relative(SRC, file).replace(/\\/g, '/')
    readFileSync(file, 'utf8')
      .split('\n')
      .forEach((line, i) => {
        for (const m of line.matchAll(/(?:router\.(?:push|replace))\(\s*\{\s*name:\s*'([^']+)'/g)) {
          referenced.push({ name: m[1], where: `${rel}:${i + 1}` })
        }
        for (const m of line.matchAll(/^\s+name:\s*'([a-z][a-z0-9-]*)',\s*$/g)) {
          // Only inside a `{ name: '...', params|query }` object literal.
          if (/name:|params:|query:/.test(line)) referenced.push({ name: m[1], where: `${rel}:${i + 1}` })
        }
      })
  }

  assert.ok(referenced.length > 0, 'expected named navigation targets')
  const missing = referenced.filter((r) => !NAMES.has(r.name))
  assert.deepEqual(
    missing.map((m) => `${m.where} -> ${m.name}`),
    [],
    'these navigate to a route name that does not exist',
  )
})

// ------------------------------------------------------- the sidebar itself

test('the sidebar entries all point at real routes', () => {
  const layout = readFileSync(join(SRC, 'layouts', 'MainLayout.vue'), 'utf8')
  const block = layout.slice(layout.indexOf('const entries'), layout.indexOf('const activeEntry'))
  const targets = [...block.matchAll(/to:\s*'([^']+)'/g)].map((m) => m[1])

  assert.equal(targets.length, 5, 'the navigation is five entries')
  for (const target of targets) {
    assert.ok(
      [...PATHS].some((pattern) => matchesPath(target, pattern)),
      `navigation entry ${target} has no route`,
    )
  }
})

test('the highlight matcher covers every navigation entry', () => {
  // If an entry's prefix is not handled, that entry never lights up.
  const layout = readFileSync(join(SRC, 'layouts', 'MainLayout.vue'), 'utf8')
  const block = layout.slice(layout.indexOf('const entries'), layout.indexOf('const activeEntry'))
  const targets = [...block.matchAll(/to:\s*'([^']+)'/g)].map((m) => m[1])
  const active = layout.slice(layout.indexOf('const activeEntry'), layout.indexOf('const currentTitle'))

  for (const target of targets) {
    if (target === '/dashboard') continue // the fallback branch handles it
    assert.ok(
      active.includes(`'${target}'`),
      `no active-entry branch mentions ${target}; that entry can never highlight`,
    )
  }
})

// ------------------------------------------------------------- legacy paths

test('the legacy redirects still cover the old patient-centric URLs', () => {
  // Bookmarks and the demo script use these; they must not 404.
  const legacy = [
    'patients/:id/assessment',
    'patients/:id/training',
    'patients/:id/training/piano',
    'patients/:id/training/movement',
    'patients/:id/history',
    'patients/:id/trends',
    'patients/:id/report',
  ]
  for (const path of legacy) {
    assert.ok(
      routerSource.includes(`path: '${path}'`),
      `legacy path ${path} was removed; old links would now 404`,
    )
  }
})

/**
 * The route table only.
 *
 * The navigation guard also contains the word `redirect` -- `query: { redirect:
 * to.fullPath }` -- and splitting the whole file on it produced a block with no
 * route target. Every route definition precedes the guard, so the table is
 * everything before it.
 */
const ROUTE_TABLE = routerSource.split('router.beforeEach')[0]

test('every redirect target resolves, by name or by path', () => {
  // Redirects are written two ways: inline `name: 'x'`, and a multi-line object
  // using `path: '/x'`. Both have to land somewhere real.
  const blocks = ROUTE_TABLE.split(/redirect:/).slice(1)
  assert.ok(blocks.length >= 8, `expected the legacy redirects, found ${blocks.length}`)

  for (const block of blocks) {
    const body = block.slice(0, 400)
    const byName = body.match(/name:\s*'([^']+)'/)?.[1]
    const byPath = body.match(/path:\s*'([^']+)'/)?.[1]

    assert.ok(
      byName || byPath,
      `a redirect target could not be read from: ${body.slice(0, 80).replace(/\s+/g, ' ')}`,
    )
    if (byName) {
      assert.ok(NAMES.has(byName), `a redirect targets unknown route name ${byName}`)
    }
    if (byPath) {
      assert.ok(
        [...PATHS].some((pattern) => matchesPath(byPath, pattern)),
        `a redirect targets unknown path ${byPath}`,
      )
    }
  }
})

test('no legacy redirect points at itself', () => {
  // A redirect whose source path equals its target would loop forever.
  const blocks = ROUTE_TABLE.split(/\{\s*\n\s*path:\s*'/).slice(1)
  for (const block of blocks) {
    if (!block.includes('redirect:')) continue
    const source = '/' + block.slice(0, block.indexOf("'"))
    const targetPath = block.match(/redirect:[\s\S]{0,200}?path:\s*'([^']+)'/)?.[1]
    const targetName = block.match(/redirect:[\s\S]{0,200}?name:\s*'([^']+)'/)?.[1]

    if (targetPath) {
      assert.notEqual(targetPath, source, `${source} redirects to itself`)
    }
    if (targetName) {
      const named = ROUTE_TABLE.match(
        new RegExp(`path:\\s*'([^']+)',\\s*\\n\\s*name:\\s*'${targetName}'`),
      )?.[1]
      if (named) assert.notEqual('/' + named, source, `${source} redirects to itself`)
    }
  }
})
