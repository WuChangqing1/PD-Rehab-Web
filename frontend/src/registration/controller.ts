import type { RegistrationApi, RegistrationResult } from './publicApi.ts'

export class RegistrationController {
  phone = ''; code = ''; consent = false; enabled = false; loading = true
  sending = false; submitting = false; error = ''; challengeId = ''; expiresAt = 0; retryAt = 0
  result: RegistrationResult | null = null
  cleanupPending = false
  cleanupRunning = false
  newAccount = false
  private alive = true
  private revision = 0
  private api: RegistrationApi
  private now: () => number
  constructor(api: RegistrationApi, now: () => number = Date.now) { this.api = api; this.now = now }
  get retrySeconds() { return Math.max(0, Math.ceil((this.retryAt - this.now()) / 1000)) }
  get validPhone() { return /^(?:\+86)?1[3-9]\d{9}$/.test(this.phone.trim()) }
  get canSend() { return !this.loading && this.enabled && this.validPhone && this.consent && !this.sending && !this.submitting && this.retrySeconds === 0 && !this.result }
  get canSubmit() { return this.enabled && this.consent && !!this.challengeId && /^\d{6}$/.test(this.code) && !this.sending && !this.submitting && !this.result }
  setPhone(value: string) {
    if (value === this.phone) return
    this.phone = value; this.revision++; this.challengeId = ''; this.code = ''; this.expiresAt = 0; this.error = ''
  }
  async load() {
    try { const config = await this.api.providers(); if (this.alive) { this.enabled = config.sms_enabled; this.error = config.sms_enabled ? '' : '短信注册暂不可用，请稍后重试或联系技术支持。' } }
    catch (error) { if (this.alive) this.error = (error as Error).message }
    finally { if (this.alive) this.loading = false }
  }
  async send() {
    if (!this.canSend) return
    this.sending = true; this.error = ''; this.retryAt = this.now() + 60000; const revision = this.revision
    this.challengeId = ''; this.code = ''; this.expiresAt = 0
    try {
      const result = await this.api.challenge(this.phone.trim())
      if (!this.alive) return
      this.retryAt = this.now() + Math.max(60, result.retry_after) * 1000
      if (revision !== this.revision) return
      this.challengeId = result.challenge_id; this.expiresAt = this.now() + result.expires_in * 1000; this.code = ''
    } catch (error) {
      if (this.alive) { this.error = (error as Error).message; const retry = Number((error as {retryAfter?:number}).retryAfter); if (retry > 0) this.retryAt = this.now() + retry * 1000 }
    } finally { if (this.alive) this.sending = false }
  }
  async submit() {
    if (!this.canSubmit) return
    if (this.now() >= this.expiresAt) { this.error = '验证码已失效，请重新获取。'; this.challengeId = ''; this.code = ''; return }
    this.submitting = true; this.error = ''
    try {
      const result = await this.api.verify(this.challengeId, this.code)
      if (!this.alive) { void this.api.cleanup(); return }
      this.newAccount = !!result.recoveryCode; this.result = result; this.cleanupPending = true; this.phone = ''; this.code = ''; this.challengeId = ''
      void this.retryCleanup()
    } catch (error) {
      if (this.alive) { this.error = (error as Error).message; const retry = Number((error as {retryAfter?:number}).retryAfter); if (retry > 0) this.retryAt = this.now() + retry * 1000 }
    } finally { if (this.alive) this.submitting = false }
  }
  async retryCleanup() {
    if (this.cleanupRunning) return
    this.cleanupRunning = true
    const clean = await this.api.cleanup()
    if (this.alive) { this.cleanupPending = !clean; this.cleanupRunning = false }
  }
  clearRecovery() { if (this.result) delete this.result.recoveryCode }
  dispose() { this.alive = false; this.phone = ''; this.code = ''; this.result = null; void this.api.cleanup() }
}
