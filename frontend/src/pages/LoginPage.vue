<script setup lang="ts">
import { t, locale } from '@/i18n'

import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
/**
 * Login page.
 *
 * Vocabulary check: this page never says 确诊 / 治愈 / 治疗成功. The system
 * performs auxiliary assessment and training recording only.
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { API_BASE, notifyError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

import { brandLogoUrl } from '@/branding'
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const androidRelease = ref<{ available: boolean; versionName?: string; sizeBytes?: number; apkUrl?: string; min_sdk?: number; sha256?: string } | null>(null)
const androidLoading = ref(true)
onMounted(async () => {
  try {
    const response = await fetch(`${API_BASE}/android/latest`, { credentials: 'omit', cache: 'no-store' })
    if (response.ok) androidRelease.value = await response.json()
  } catch { /* Download availability must not interrupt staff login. */ }
  finally { androidLoading.value = false }
})

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '' })

const rules = computed<FormRules>(() => ({
  username: [{ required: true, message: t('请输入用户名'), trigger: 'blur' }],
  password: [{ required: true, message: t('请输入密码'), trigger: 'blur' }],
}))
watch(locale, () => formRef.value?.clearValidate())

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  try {
    await auth.login(form.username, form.password)
    ElMessage.success(t('登录成功'))
    const redirect = route.query.redirect
    const target = typeof redirect === 'string' && redirect ? redirect : '/dashboard'
    router.push(target)
  } catch (error) {
    notifyError(error, '登录失败，请检查用户名和密码。')
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-language"><LanguageSwitcher /></div>
      <header class="login-header">
        <img class="login-mark" :src="brandLogoUrl" alt="" aria-hidden="true" />
        <h1>{{ $t("帕琴律动") }}</h1>

      </header>

      <el-form :validate-on-rule-change="false"
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="submit"
      >
        <el-form-item :label="$t('用户名')" prop="username">
          <el-input v-model="form.username" :placeholder="$t('请输入用户名')" autocomplete="username" />
        </el-form-item>
        <el-form-item :label="$t('密码')" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="$t('请输入密码')"
            show-password
            autocomplete="current-password"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button
          type="primary"
          class="login-submit"
          :loading="auth.loading"
          @click="submit"
        >
          {{ $t("登录") }}
        </el-button>
      </el-form>
      <RouterLink class="registration-link" to="/register/staff">{{ $t('医护注册申请') }}</RouterLink>
      <RouterLink class="registration-link" :to="{ name: 'phone-registration' }">{{ $t('患者手机号注册') }}</RouterLink>
      <section class="android-download" aria-label="琴伴 Android App" aria-live="polite">
        <p>琴伴 · Android</p>
        <a v-if="androidRelease?.available" class="android-download-link" :href="androidRelease.apkUrl">下载琴伴 Android App</a>
        <el-button v-else disabled class="login-submit">下载琴伴 Android App</el-button>
        <p v-if="androidRelease?.available" class="android-download-detail">
          稳定版 {{ androidRelease.versionName }} · {{ ((androidRelease.sizeBytes || 0) / 1024 / 1024).toFixed(1) }} MB · 最低 Android API {{ androidRelease.min_sdk }}
        </p>
        <p v-else class="android-download-detail">{{ androidLoading ? '正在查询正式版本…' : '正式安装包准备中，请稍后再试。' }}</p>
        <p v-if="androidRelease?.available" class="android-download-detail">下载后按 Android 系统提示安装；覆盖升级前请保留原 App 数据。</p>
        <details v-if="androidRelease?.available" class="android-download-detail"><summary>文件校验 SHA256</summary><code>{{ androidRelease.sha256 }}</code></details>
      </section>
    </div>
  </div>
</template>

<style scoped>
.android-download { margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--pd-border); }
.android-download p { margin: 8px 0; }
.android-download-link { display: block; padding: 12px; border: 1px solid var(--pd-primary); border-radius: 6px; color: var(--pd-primary); text-align: center; }
.android-download-detail { font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }

.registration-link { display:block; margin-top:24px; text-align:center; line-height:1.5; color:var(--pd-primary); }
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: var(--pd-page-pad-x);
  background: var(--pd-bg);
}

.login-card {
  width: 100%;
  max-width: 440px;
  padding: 32px;
  background: var(--pd-surface);
  border: 1px solid var(--pd-border);
  border-radius: var(--pd-radius-card);
  box-shadow: var(--pd-shadow-lg);
}

@media (max-width: 479px) {
  .login-card {
    padding: 22px 18px;
  }
}

.login-language{display:flex;justify-content:flex-end;margin:-12px -12px 4px;}

.login-header {
  margin-bottom: 24px;
  text-align: center;
}

.login-mark {
  position: relative;
  font-size: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  margin-bottom: 12px;
  border-radius: 10px;
  background: #4f704e;
  color: #fff;
  font-weight: 700;
}



.login-header h1 {
  font-size: 20px;
  line-height: 1.4;
}

.login-header p {
  margin: 8px 0 0;
  font-size: 14px;
}

.login-submit {
  width: 100%;
  margin-top: 4px;
  min-height: var(--pd-touch-large);
}

.login-hint code {
  padding: 1px 4px;
  border-radius: 3px;
  background: var(--pd-bg);
  font-size: 11px;
}
</style>
