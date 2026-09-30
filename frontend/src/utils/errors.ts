/**
 * Turn a backend error into something a doctor or a patient can act on.
 *
 * The API's codes are stable identifiers and belong in the logs and in 系统设置,
 * not in a message shown to someone holding a tablet. A doctor needs to know what
 * to do next ("record again with the whole hand in frame"), not that the pipeline
 * returned HAND_NOT_DETECTED.
 *
 * The raw code is still available via `toApiError` for the console and for the
 * advanced view; this module only supplies the wording.
 */

export interface PlainError {
  /** One sentence a non-engineer can act on. */
  message: string
  /** Whether retrying the same recording could plausibly help. */
  retryable: boolean
}

const MESSAGES: Record<string, PlainError> = {
  // ---- recording quality: the operator can fix these by recording again
  HAND_NOT_DETECTED: {
    message: '没有检测到完整手部，请让手部完全进入画面后重新录制。',
    retryable: true,
  },
  LOW_VALID_FRAME_RATIO: {
    message: '画面中能看清手部的帧太少，请固定手机、避免遮挡后重新录制。',
    retryable: true,
  },
  LANDMARK_DISCONTINUOUS: {
    message: '手部在录制过程中多次移出画面，请重新录制并保持手在画面内。',
    retryable: true,
  },
  INSUFFICIENT_CYCLES: {
    message: '有效敲击次数不足，请录制 10–20 秒连续敲击后重试。',
    retryable: true,
  },
  VIDEO_TOO_SHORT: {
    message: '视频时间太短，请录满 10–20 秒后重试。',
    retryable: true,
  },
  VIDEO_UNREADABLE: {
    message: '无法读取该视频文件，请换一个文件或重新录制。',
    retryable: true,
  },
  VIDEO_FPS_INVALID: {
    message: '视频帧率异常，无法分析。请用手机重新录制。',
    retryable: true,
  },
  NO_POSE_DETECTED: {
    message: '没有检测到人体，请让整个人进入画面后重新录制。',
    retryable: true,
  },
  LOW_LANDMARK_VISIBILITY: {
    message: '关键点看不清楚，请让整个人进入画面、避免逆光后重新录制。',
    retryable: true,
  },
  NO_MOVEMENT_DETECTED: {
    message: '没有检测到动作，请完成几次完整的动作后重试。',
    retryable: true,
  },
  INSUFFICIENT_REPETITIONS: {
    message: '没有完成一次完整动作，请按说明做完几次后重试。',
    retryable: true,
  },

  // ---- upload mechanics
  UNSUPPORTED_MEDIA_TYPE: {
    message: '这个文件格式不支持，请使用 MP4、MOV 或 WebM 视频。',
    retryable: true,
  },
  FILE_TOO_LARGE: {
    message: '文件太大，请压缩或录制更短的视频后重试。',
    retryable: true,
  },

  // ---- configuration: retrying will not help
  MODEL_NOT_CONFIGURED: {
    message: '该分析功能当前暂不可用，请联系系统管理员。',
    retryable: false,
  },
  MODEL_UNAVAILABLE: {
    message: '该分析功能当前暂不可用，请联系系统管理员。',
    retryable: false,
  },
  MODEL_LOAD_FAILED: {
    message: '该分析功能启动失败，请联系系统管理员。',
    retryable: false,
  },
  INFERENCE_FAILED: {
    message: '分析过程中出错，请重试一次；若仍失败请联系系统管理员。',
    retryable: true,
  },

  // ---- record state
  CONFLICT: {
    message: '这条记录的状态不允许该操作，请刷新页面后重试。',
    retryable: false,
  },
  NOT_FOUND: {
    message: '找不到对应的记录，请重新选择患者或重新开始。',
    retryable: false,
  },
  VALIDATION_ERROR: {
    message: '提交的内容不符合要求，请检查后重试。',
    retryable: false,
  },
}

/**
 * Plain wording for an API error.
 *
 * Falls back to the server's own message when the code is unknown, and to a
 * generic line when there is nothing to show. It never surfaces the raw code.
 */
export function plainError(error: unknown, fallback = '操作失败，请重试。'): PlainError {
  const apiError = error as
    | { code?: string; message?: string; status?: number }
    | null
    | undefined

  const code = apiError?.code
  if (code && MESSAGES[code]) return MESSAGES[code]

  // Network-level failures have no code.
  if (!apiError?.status) {
    return { message: '无法连接服务器，请检查网络后重试。', retryable: true }
  }
  if (apiError.message) {
    // Server messages are already written for humans on this API.
    return { message: apiError.message, retryable: true }
  }
  return { message: fallback, retryable: true }
}

/** Convenience for a plain string, for `ElMessage` and inline text. */
export function plainErrorMessage(error: unknown, fallback?: string): string {
  return plainError(error, fallback).message
}
