/**
 * MediaRecorder format negotiation.
 *
 * A browser records with MediaRecorder: Chrome and Firefox produce webm, Safari
 * produces mp4. The backend accepts both, but the uploaded filename must carry
 * the extension of the container that is actually inside it -- naming a webm
 * "recording.mp4" would pass the extension check while lying about the format.
 *
 * Kept as pure functions rather than a composable: there is one caller, and the
 * camera/MediaRecorder lifecycle around it is used from exactly one place.
 */

export interface RecordingFormat {
  mimeType: string
  extension: string
}

/** Candidate formats, best first. */
export const RECORDING_FORMATS: readonly RecordingFormat[] = [
  { mimeType: 'video/mp4;codecs=h264', extension: 'mp4' },
  { mimeType: 'video/mp4', extension: 'mp4' },
  { mimeType: 'video/webm;codecs=vp9', extension: 'webm' },
  { mimeType: 'video/webm;codecs=vp8', extension: 'webm' },
  { mimeType: 'video/webm', extension: 'webm' },
]

export const DEFAULT_RECORDING_NAME = 'recording.webm'

/**
 * The best format this browser declares support for.
 *
 * An empty `mimeType` means "let the browser choose"; webm is the safe extension
 * default because that is what an unspecified MediaRecorder produces everywhere
 * except Safari, which ignores the option and still reports its own type back.
 */
export function pickRecordingFormat(): RecordingFormat {
  if (typeof MediaRecorder === 'undefined') {
    return { mimeType: '', extension: 'webm' }
  }
  for (const format of RECORDING_FORMATS) {
    if (MediaRecorder.isTypeSupported(format.mimeType)) return format
  }
  return { mimeType: '', extension: 'webm' }
}

/**
 * Filename for a recording, using the container the recorder actually produced.
 *
 * `actualType` is `MediaRecorder.mimeType`, which is authoritative: a browser may
 * ignore the requested type and record something else.
 */
export function recordingFilename(actualType: string | null | undefined): string {
  const type = (actualType ?? '').toLowerCase()
  if (type.includes('mp4')) return 'recording.mp4'
  return DEFAULT_RECORDING_NAME
}
