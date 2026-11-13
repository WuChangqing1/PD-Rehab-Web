import test from 'node:test'
import assert from 'node:assert/strict'
import manifest from '../src/dance/resources-v2.json' with { type: 'json' }

// These tests catch locale filtering, an incorrectly joined part, and media
// continuing to download/play after the viewer leaves or switches lessons.
const module = await import('../src/dance/courses.ts').catch(() => null)
test('course library preserves every course and declared part order in both locales', () => {
  assert.ok(module, 'dance course resolver is implemented')
  const manifest = {
    courses: [
      { courseId: 'a', titleZh: '甲', titleEn: 'A', language: 'zh', posterUrl: '/a.jpg', partIds: ['a-2', 'a-1'] },
      { courseId: 'b', titleZh: '乙', titleEn: 'B', language: 'en', posterUrl: '/b.jpg', partIds: ['b-1'] },
    ],
    items: [
      { courseId: 'a', partId: 'a-1', url: '/1.mp4', durationSeconds: 60 },
      { courseId: 'b', partId: 'b-1', url: '/b.mp4', durationSeconds: 90 },
      { courseId: 'a', partId: 'a-2', url: '/2.mp4', durationSeconds: 20 },
    ],
  }
  for (const locale of ['zh-CN', 'en']) {
    const courses = module.resolveCourses(manifest, locale)
    assert.deepEqual(courses.map((course: { id: string }) => course.id), ['a', 'b'])
    assert.deepEqual(courses[0].parts.map((part: { url: string }) => part.url), ['/2.mp4', '/1.mp4'])
    assert.equal(courses[0].title, locale === 'en' ? 'A' : '甲')
    assert.equal(courses[1].language, 'en')
  }
  assert.throws(() => module.resolveCourses({ ...manifest, items: manifest.items.slice(1) }, 'en'), /a-1/)
})

test('releasing a video pauses it and cancels its resource request', () => {
  assert.ok(module, 'dance video lifecycle is implemented')
  const calls: string[] = []
  module.releaseVideo({ pause: () => calls.push('pause'), removeAttribute: (name: string) => calls.push(`remove:${name}`), load: () => calls.push('load') })
  assert.deepEqual(calls, ['pause', 'remove:src', 'load'])
  assert.doesNotThrow(() => module.releaseVideo(null))
})

test('the bundled library resolves ten playable parts with preserved media versions', () => {
  assert.ok(module)
  for (const locale of ['zh-CN', 'en']) {
    const courses = module.resolveCourses(manifest, locale)
    assert.deepEqual(courses.map(course => [course.id, course.parts.length]), [
      ['hkpdf-balance-six', 3], ['brain-and-body', 4], ['move-and-shout', 3],
    ])
    assert.equal(new Set(courses.flatMap(course => course.parts.map(part => part.url))).size, 10)
    for (const course of courses) {
      for (const part of course.parts) {
        const url = new URL(part.url)
        assert.equal(url.origin, 'https://ccqspace.site')
        assert.match(url.pathname, course.id === 'hkpdf-balance-six' ? /^\/pd-rehab\/assets\/dance\/v1\/balance-six-part-[1-3]\.mp4$/ : /^\/pd-rehab\/assets\/dance\/v2\/(brain-and-body|move-and-shout)-part-[1-4]\.mp4$/)
        assert.ok(part.durationSeconds > 0)
      }
    }
  }
})
