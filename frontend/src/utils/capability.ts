/**
 * Browser capability detection.
 *
 * Camera capture requires a Secure Context. Over plain HTTP on anything other
 * than localhost, `navigator.mediaDevices` is undefined and getUserMedia
 * cannot be called at all. We detect this and tell the user to upload a file
 * instead. We never work around the browser's security policy.
 */

import { computed, ref } from 'vue'

export interface CameraCapability {
  secureContext: boolean
  hasMediaDevices: boolean
  hasGetUserMedia: boolean
  available: boolean
  reason: string | null
}

function detect(): CameraCapability {
  const secureContext = typeof window !== 'undefined' ? window.isSecureContext : false
  const mediaDevices =
    typeof navigator !== 'undefined' && typeof navigator.mediaDevices !== 'undefined'
  const getUserMedia = Boolean(mediaDevices && navigator.mediaDevices.getUserMedia)

  let reason: string | null = null
  if (!secureContext) {
    reason =
      '当前访问方式不是安全上下文（需要 HTTPS 或 localhost），浏览器会禁用摄像头。请改用本地视频文件上传。'
  } else if (!getUserMedia) {
    reason = '当前浏览器不支持摄像头采集（navigator.mediaDevices.getUserMedia 不可用）。请改用本地视频文件上传。'
  }

  return {
    secureContext,
    hasMediaDevices: mediaDevices,
    hasGetUserMedia: getUserMedia,
    available: secureContext && getUserMedia,
    reason,
  }
}

const capability = ref<CameraCapability>(detect())

export function useCameraCapability() {
  return {
    capability,
    cameraAvailable: computed(() => capability.value.available),
    reason: computed(() => capability.value.reason),
    refresh: () => {
      capability.value = detect()
    },
  }
}
