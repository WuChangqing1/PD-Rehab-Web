export interface DancePart {
  courseId: string
  partId: string
  url: string
  durationSeconds: number
}
interface DanceManifest {
  courses: { courseId: string; titleZh: string; titleEn: string; language: string; posterUrl: string; partIds: string[] }[]
  items: DancePart[]
}

/** The UI language changes labels, never the available videos or their language. */
export function resolveCourses(manifest: DanceManifest, locale: string) {
  return manifest.courses.map(course => ({
    id: course.courseId,
    title: locale === 'en' ? course.titleEn : course.titleZh,
    language: course.language,
    poster: course.posterUrl,
    parts: course.partIds.map(id => {
      const part = manifest.items.find(item => item.courseId === course.courseId && item.partId === id)
      if (!part) throw new Error(`Missing dance part: ${id}`)
      return part
    }),
  }))
}

/** Release the selected clip on replacement or leaving the viewer. */
export function releaseVideo(video: Pick<HTMLVideoElement, 'pause' | 'removeAttribute' | 'load'> | null) {
  if (!video) return
  video.pause()
  video.removeAttribute('src')
  video.load()
}
