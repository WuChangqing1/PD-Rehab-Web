<script setup lang="ts">
import { reactive,onBeforeUnmount } from 'vue'
import { t } from '@/i18n'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import { StaffRegistrationController,createStaffRegistrationApi } from '@/staff/controller'
const registration=reactive(new StaffRegistrationController(createStaffRegistrationApi(import.meta.env.BASE_URL)))
onBeforeUnmount(()=>registration.dispose())
</script>
<template>
 <main class="staff-register">
  <section class="pd-card staff-register-card">
   <LanguageSwitcher />
   <h1>{{ t('医护注册申请') }}</h1>
   <template v-if="registration.result">
    <div role="status"><h2>{{ t('申请已提交，等待管理员审核') }}</h2><p>{{ t('审核通过后可使用申请时的用户名和密码登录。') }}</p></div>
   </template>
   <template v-else>
    <p>{{ t('请选择医生或护士身份，提交后由管理员审核。') }}</p>
    <form @submit.prevent="registration.submit()">
     <label>{{ t('用户名') }}<input v-model="registration.form.username" required minlength="3" maxlength="32" pattern="[A-Za-z0-9_]{3,32}" aria-describedby="staff-username-help" autocomplete="username" :disabled="registration.submitting" /></label><small id="staff-username-help">{{ t('用户名须为3至32位字母、数字或下划线。') }}</small>
     <label>{{ t('密码') }}<input v-model="registration.form.password" required type="password" minlength="8" maxlength="64" aria-describedby="staff-password-help" autocomplete="new-password" :disabled="registration.submitting" /></label><small id="staff-password-help">{{ t('密码须为8至64位。') }}</small>
     <label>{{ t('姓名') }}<input v-model="registration.form.display_name" required maxlength="128" autocomplete="name" :disabled="registration.submitting" /></label>
     <label>{{ t('联系电话') }}<input v-model="registration.form.phone" required type="tel" pattern="\+?[0-9 \-]{6,32}" maxlength="33" autocomplete="tel" :disabled="registration.submitting" /></label>
     <label>{{ t('申请身份') }}<select v-model="registration.form.requested_role" :disabled="registration.submitting"><option value="DOCTOR">{{ t('医生') }}</option><option value="NURSE">{{ t('护士') }}</option></select></label>
     <p v-if="registration.error" role="alert">{{ t(registration.error) }}</p>
     <button type="submit" class="staff-primary" :disabled="registration.submitting">{{ t(registration.submitting?'正在提交…':'提交申请') }}</button>
    </form>
   </template>
   <RouterLink to="/login">{{ t('返回医护登录') }}</RouterLink>
   <RouterLink to="/register/phone">{{ t('患者手机号注册') }}</RouterLink>
  </section>
 </main>
</template>
<style scoped>
.staff-register{min-height:100dvh;display:grid;place-items:center;padding:24px 16px}.staff-register-card{width:min(100%,480px);padding:clamp(16px,5vw,32px);box-sizing:border-box;overflow-wrap:anywhere}.staff-register-card h1{font-size:1.5rem;line-height:1.4}.staff-register-card form,.staff-register-card label{display:grid;gap:8px}.staff-register-card form{gap:18px;margin-block:24px}.staff-register-card input,.staff-register-card select,.staff-register-card button{font:inherit;min-height:48px;width:100%;box-sizing:border-box;border:1px solid var(--pd-border);border-radius:8px;padding:10px 12px;background:white;color:var(--pd-text)}.staff-register-card .staff-primary{background:var(--pd-primary);color:white;cursor:pointer}.staff-register-card a{display:block;margin-top:20px;line-height:1.5;color:var(--pd-primary)}.staff-register-card :focus-visible{outline:2px solid var(--pd-primary);outline-offset:3px}
</style>
