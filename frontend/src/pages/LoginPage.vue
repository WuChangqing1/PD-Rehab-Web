<script setup lang="ts">
/**
 * Login page.
 *
 * Vocabulary check: this page never says 确诊 / 治愈 / 治疗成功. The system
 * performs auxiliary assessment and training recording only.
 */
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { notifyError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
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
      <header class="login-header">
        <div class="login-mark">PD</div>
        <h1>帕金森评估与康复</h1>
        <p class="pd-secondary">请使用工作人员账号登录</p>
      </header>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="submit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
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
          登录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
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
  border-radius: 12px;
  box-shadow: var(--pd-shadow-lg);
}

@media (max-width: 479px) {
  .login-card {
    padding: 22px 18px;
  }
}

.login-header {
  margin-bottom: 24px;
  text-align: center;
}

.login-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  margin-bottom: 12px;
  border-radius: 10px;
  background: var(--pd-primary);
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
