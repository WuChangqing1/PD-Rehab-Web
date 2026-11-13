export interface RegistrationResult { username: string; recoveryCode?: string }
export class RegistrationError extends Error {
  retryAfter: number
  constructor(message: string, retryAfter = 0) { super(message); this.retryAfter = retryAfter }
}

/** Separate from staff http: no storage, Bearer interceptor or automatic 401 logout. */
export function createRegistrationApi(base: string, request: typeof fetch = fetch) {
  const prefix = `${base.replace(/\/$/, '')}/api/mobile/auth`
  let pendingRefresh = ''
  let cleanupInFlight: Promise<boolean> | null = null
  async function call(path: string, body?: object, keepalive = false) {
    let response: Response
    try {
      response = await request(prefix + path, {
        method: body ? 'POST' : 'GET', credentials: 'omit', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(20000),
        ...(keepalive ? { keepalive: true } : {}),
      })
    } catch { throw new RegistrationError('无法连接到服务器，请检查网络后重试。') }
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      const retry = Number(response.headers.get('Retry-After'))
      const message = data?.error?.code === 'LOGIN_PROVIDER_UNAVAILABLE' ? '短信注册暂不可用，请稍后重试或联系技术支持。' : data?.error?.message || '请求失败，请稍后重试。'
      throw new RegistrationError(message, Number.isFinite(retry) ? Math.max(0, retry) : 0)
    }
    return data
  }
  function cleanup(): Promise<boolean> {
    if (cleanupInFlight) return cleanupInFlight
    if (!pendingRefresh) return Promise.resolve(true)
    cleanupInFlight = (async () => {
      try { await call('/logout', { refresh_token: pendingRefresh }, true); pendingRefresh = ''; return true }
      catch { return false }
      finally { cleanupInFlight = null }
    })()
    return cleanupInFlight
  }
  return {
    providers: async (): Promise<{ sms_enabled: boolean }> => call('/providers'),
    challenge: async (phone: string): Promise<{ challenge_id: string; expires_in: number; retry_after: number }> => call('/sms/challenge', { phone }),
    async verify(challenge: string, code: string): Promise<RegistrationResult> {
      const data = await call('/sms/login', { challenge_id: challenge, code, sync_consent_version: 'account-sync-v1' })
      pendingRefresh = data.refresh_token
      const result: RegistrationResult = { username: data.user.username, ...(data.recovery_code ? { recoveryCode: data.recovery_code } : {}) }
      return result
    },
    cleanup,
  }
}
export type RegistrationApi = ReturnType<typeof createRegistrationApi>
