<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import { t } from '@/i18n'
import { brandLogoUrl } from '@/branding'
import { createRegistrationApi } from '@/registration/publicApi'
import { RegistrationController } from '@/registration/controller'

const registration = reactive(new RegistrationController(createRegistrationApi(import.meta.env.BASE_URL || '/')))
const tick = ref(0)
const retrySeconds = computed(() => { void tick.value; return registration.retrySeconds })
const canSend = computed(() => { void tick.value; return registration.canSend })
const copyMessage = ref('')
let timer: ReturnType<typeof setInterval> | undefined
let mounted = true
onMounted(() => { void registration.load(); timer = setInterval(() => tick.value++, 500) })
onBeforeUnmount(() => { mounted = false; clearInterval(timer); registration.dispose() })
function updatePhone(event: Event) { registration.setPhone((event.target as HTMLInputElement).value) }
function submit(event: Event) {
  // Native submit has one path for click and Enter; composition Enter is ignored.
  if (event instanceof KeyboardEvent && event.isComposing) return
  void registration.submit()
}
async function copyRecovery() {
  const code = registration.result?.recoveryCode
  if (!code) return
  try { await navigator.clipboard.writeText(code); if (mounted) copyMessage.value = '已复制，请妥善保存。' }
  catch { if (mounted) copyMessage.value = '复制失败，请手动选择并保存恢复码。' }
}
</script>

<template>
  <main class="registration-page">
    <section class="registration-card" aria-labelledby="registration-title">
      <div class="registration-language"><LanguageSwitcher /></div>
      <header>
        <img class="registration-mark" :src="brandLogoUrl" alt="" />
        <h1 id="registration-title">{{ t('手机号注册') }}</h1>
        <p>{{ t('注册患者账号后，请在 App 中使用手机号登录。工作人员仍使用原账号登录。') }}</p>
      </header>

      <template v-if="registration.result">
        <div role="status" class="registration-success">
          <h2>{{ t(registration.newAccount ? '注册成功' : '此手机号已有账号') }}</h2>
          <p>{{ t(registration.newAccount ? '患者账号已创建，请保存以下信息。' : '已确认原账号，无需重复注册。请在 App 中使用手机号登录。') }}</p>
          <p>{{ t('用户名') }} <strong class="registration-secret">{{ registration.result.username }}</strong></p>
        </div>
        <div v-if="registration.result.recoveryCode" class="recovery-panel">
          <h2>{{ t('一次性恢复码') }}</h2>
          <p>{{ t('仅在本次注册时显示，可用于恢复账号。请保存到安全位置，不要分享给他人。') }}</p>
          <code class="registration-secret">{{ registration.result.recoveryCode }}</code>
          <div class="registration-actions">
            <button type="button" @click="copyRecovery">{{ t('复制恢复码') }}</button>
            <button type="button" @click="registration.clearRecovery(); copyMessage = ''">{{ t('已保存，清除恢复码') }}</button>
          </div>
          <p role="status">{{ t(copyMessage) }}</p>
        </div>
        <p v-if="registration.cleanupRunning" role="status">{{ t('正在清理临时会话…') }}</p>
        <div v-else-if="registration.cleanupPending" role="alert" class="registration-error">
          <p>{{ t('账号验证已完成，但临时会话清理失败。请联网后重试清理。') }}</p>
          <button type="button" @click="registration.retryCleanup()">{{ t('重试清理') }}</button>
        </div>
      </template>

      <form v-else @submit.prevent="submit" @keydown.enter="($event.isComposing || $event.keyCode === 229) && $event.preventDefault()">
        <label for="registration-phone">{{ t('手机号（中国大陆）') }}</label>
        <input id="registration-phone" :value="registration.phone" @input="updatePhone" type="tel" inputmode="tel" autocomplete="tel" maxlength="14" :disabled="registration.submitting" placeholder="13800138000" required />
        <label for="registration-code">{{ t('短信验证码') }}</label>
        <div class="verification-row">
          <input id="registration-code" v-model="registration.code" type="text" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" :disabled="registration.submitting" :placeholder="t('6 位验证码')" required />
          <button type="button" :disabled="!canSend" @click="registration.send()">
            {{ registration.sending ? t('正在发送…') : retrySeconds ? `${retrySeconds} ${t('秒后重试')}` : t('获取验证码') }}
          </button>
        </div>
        <p class="registration-hint">{{ t('验证码 5 分钟内有效；修改手机号后需重新获取。') }}</p>
        <label class="consent-row">
          <input v-model="registration.consent" type="checkbox" :disabled="registration.submitting" />
          <span>{{ t('我同意创建或验证患者账号，并同步保存本人的训练记录与康复档案。') }}</span>
        </label>
        <p v-if="registration.error" role="alert" class="registration-error">{{ t(registration.error) }}</p>
        <button v-if="!registration.enabled && !registration.loading" type="button" @click="registration.load()">{{ t('重新检查短信服务') }}</button>
        <button type="submit" class="registration-submit" :disabled="!registration.canSubmit">{{ t(registration.submitting ? '正在验证…' : '验证并注册') }}</button>
      </form>
      <RouterLink class="registration-back" :to="{ name: 'login' }">{{ t('返回工作人员登录') }}</RouterLink>
    </section>
  </main>
</template>

<style scoped>
.registration-page{min-height:100dvh;padding:var(--pd-page-pad-x);display:flex;justify-content:center;align-items:center;background:var(--pd-bg)}
.registration-card{width:100%;max-width:520px;min-width:0;padding:32px;background:var(--pd-surface);border:1px solid var(--pd-border);border-radius:var(--pd-radius-card);box-shadow:var(--pd-shadow-lg);overflow-wrap:anywhere}
.registration-language{display:flex;justify-content:flex-end}.registration-mark{width:46px;height:46px;object-fit:contain}header{text-align:center;margin-bottom:24px}h1{font-size:1.5rem;line-height:1.4}h2{font-size:1.15rem;line-height:1.5}p{line-height:1.6;margin:12px 0}label{display:block;margin:16px 0 8px;line-height:1.5}input:not([type=checkbox]){min-width:0;width:100%;min-height:48px;border:1px solid var(--pd-border);border-radius:8px;padding:10px 12px;font:inherit;color:inherit;background:var(--pd-surface);box-sizing:border-box}button{min-height:48px;padding:10px 14px;border:1px solid var(--pd-border);border-radius:8px;background:var(--pd-surface);color:inherit;font:inherit;white-space:normal;overflow-wrap:anywhere;line-height:1.5;cursor:pointer}button:disabled{opacity:.55;cursor:not-allowed}button:focus-visible,input:focus-visible,a:focus-visible{outline:3px solid var(--pd-primary);outline-offset:3px}.verification-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;align-items:stretch}.consent-row{display:flex;align-items:flex-start;gap:10px}.consent-row input{flex:none;width:22px;height:22px;margin:2px 0;accent-color:var(--pd-primary)}.registration-hint{font-size:.9rem}.registration-submit{margin-top:16px;width:100%;background:var(--pd-primary);color:white}.registration-back{display:block;text-align:center;margin-top:24px;line-height:1.5;color:var(--pd-primary)}.registration-error{color:var(--pd-danger,#a52222)}.registration-secret{display:block;overflow-wrap:anywhere;user-select:all;line-height:1.6}.recovery-panel{padding:16px;border:1px solid var(--pd-border);border-radius:8px}.registration-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.registration-actions button{flex:1 1 140px}
@media(max-width:479px){.registration-card{padding:22px 18px}.verification-row{grid-template-columns:minmax(0,1fr)} }
</style>
