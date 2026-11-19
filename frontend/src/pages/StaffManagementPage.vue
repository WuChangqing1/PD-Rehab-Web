<script setup lang="ts">
import { reactive,onMounted,onBeforeUnmount,ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { StaffManagementController,type StaffApplication,type ManagedStaff } from '@/staff/controller'
import { staffManagementApi } from '@/staff/api'
const auth=useAuthStore()
const router=useRouter()
const management=reactive(new StaffManagementController(staffManagementApi))
const reviewTarget=ref<StaffApplication|null>(null),reviewRole=ref<'DOCTOR'|'NURSE'>('DOCTOR'),reason=ref(''),decision=ref<'APPROVE'|'REJECT'>('APPROVE')
const roleTarget=ref<ManagedStaff|null>(null),newRole=ref<'DOCTOR'|'NURSE'>('DOCTOR')
const roleLabel=(role:string)=>t(role==='ADMIN'?'管理员':role==='NURSE'?'护士':'医生')
const statusLabel=(status:string)=>t(status==='APPROVED'?'已通过':status==='REJECTED'?'已拒绝':'待审核')
function openReview(application:StaffApplication,value:'APPROVE'|'REJECT'){reviewTarget.value=application;reviewRole.value=application.requested_role;decision.value=value;reason.value=''}
async function submitReview(){if(!reviewTarget.value)return;await management.review(reviewTarget.value.id,decision.value,reviewRole.value,reason.value);if(!management.error)reviewTarget.value=null}
function openRole(user:ManagedStaff){roleTarget.value=user;newRole.value=user.role==='NURSE'?'NURSE':'DOCTOR'}
async function refreshIdentity(){const restored=await auth.restore();if(!restored)await router.replace('/login');else if(!auth.permissions.admin)await router.replace('/dashboard')}
async function saveRole(){if(!roleTarget.value)return;if(await management.update(roleTarget.value.id,{role:newRole.value})){roleTarget.value=null;await refreshIdentity()}}
async function toggleActive(user:ManagedStaff){try{await ElMessageBox.confirm(t(user.is_active?'确认停用此医护账户？':'确认启用此医护账户？'),t('医护管理'),{confirmButtonText:t('确认'),cancelButtonText:t('取消'),type:'warning'})}catch{return};if(await management.update(user.id,{is_active:!user.is_active}))await refreshIdentity()}
onMounted(()=>{if(auth.permissions.admin)void management.load()})
onBeforeUnmount(()=>management.dispose())
</script>
<template>
 <div class="pd-page staff-management">
  <h1 class="pd-page-title">{{ t('医护管理') }}</h1>
  <p>{{ t('审核医护申请，管理当前共享工作区的医护账户。') }}</p>
  <el-alert v-if="management.error" type="error" :closable="false" :title="t(management.error)" role="alert" />
  <template v-if="auth.permissions.admin">
   <section class="pd-card staff-section" :aria-label="t('注册申请')">
    <div class="staff-heading"><h2>{{ t('注册申请') }}</h2><el-button :loading="management.loading" :disabled="management.busy" @click="management.load()">{{ t('刷新') }}</el-button></div>
    <label class="staff-filter">{{ t('申请状态') }}<select v-model="management.status" :disabled="management.busy" @change="management.load()"><option value="PENDING">{{ t('待审核') }}</option><option value="APPROVED">{{ t('已通过') }}</option><option value="REJECTED">{{ t('已拒绝') }}</option></select></label>
    <p v-if="management.loading" role="status">{{ t('正在加载…') }}</p>
    <p v-else-if="!management.applications.length">{{ t('暂无注册申请') }}</p>
    <article v-for="application in management.applications" :key="application.id" class="staff-row">
     <div><h3>{{ application.display_name }}</h3><p>{{ t('用户名') }}: {{ application.username }}</p><p>{{ t('联系电话') }}: {{ application.phone }}</p><p>{{ t('申请身份') }}: {{ roleLabel(application.requested_role) }} · {{ statusLabel(application.status) }}</p><p v-if="application.reason">{{ t('审核说明') }}: {{ application.reason }}</p></div>
     <div v-if="application.status==='PENDING'" class="staff-actions"><el-button :disabled="management.busy" type="primary" @click="openReview(application,'APPROVE')">{{ t('通过申请') }}</el-button><el-button :disabled="management.busy" type="danger" plain @click="openReview(application,'REJECT')">{{ t('拒绝申请') }}</el-button></div>
    </article>
   </section>
   <section class="pd-card staff-section" :aria-label="t('医护账户')"><h2>{{ t('医护账户') }}</h2>
    <article v-for="user in management.staff" :key="user.id" class="staff-row"><div><h3>{{ user.display_name }}</h3><p>{{ t('用户名') }}: {{ user.username }}</p><p>{{ roleLabel(user.role) }} · {{ t(user.is_active?'已启用':'已停用') }}</p></div><div class="staff-actions"><el-button :disabled="management.busy" @click="openRole(user)">{{ t('更改身份') }}</el-button><el-button :disabled="management.busy" :type="user.is_active?'danger':'primary'" plain @click="toggleActive(user)">{{ t(user.is_active?'停用账户':'启用账户') }}</el-button></div></article>
   </section>
  </template>
  <el-dialog :model-value="!!reviewTarget" :title="t(decision==='APPROVE'?'通过申请':'拒绝申请')" width="min(92vw, 520px)" :close-on-click-modal="!management.busy" :show-close="!management.busy" @close="reviewTarget=null">
   <p>{{ reviewTarget?.display_name }}</p>
   <el-form label-position="top" :disabled="management.busy"><el-form-item v-if="decision==='APPROVE'" :label="t('批准身份')"><el-select v-model="reviewRole"><el-option value="DOCTOR" :label="t('医生')"/><el-option value="NURSE" :label="t('护士')"/></el-select></el-form-item><el-form-item :label="t('审核说明（选填）')"><el-input v-model="reason" type="textarea" maxlength="500" :rows="3"/></el-form-item></el-form>
   <p v-if="management.error" role="alert">{{ t(management.error) }}</p>
   <template #footer><div class="staff-actions"><el-button :disabled="management.busy" @click="reviewTarget=null">{{ t('取消') }}</el-button><el-button type="primary" :loading="management.busy" @click="submitReview">{{ t('确认') }}</el-button></div></template>
  </el-dialog>
  <el-dialog :model-value="!!roleTarget" :title="t('更改身份')" width="min(92vw, 520px)" :close-on-click-modal="!management.busy" :show-close="!management.busy" @close="roleTarget=null"><p>{{ roleTarget?.display_name }}</p><el-form label-position="top"><el-form-item :label="t('医护身份')"><el-select v-model="newRole" :disabled="management.busy"><el-option value="DOCTOR" :label="t('医生')"/><el-option value="NURSE" :label="t('护士')"/></el-select></el-form-item></el-form><p v-if="management.error" role="alert">{{ t(management.error) }}</p><template #footer><div class="staff-actions"><el-button :disabled="management.busy" @click="roleTarget=null">{{ t('取消') }}</el-button><el-button type="primary" :loading="management.busy" @click="saveRole">{{ t('确认') }}</el-button></div></template></el-dialog>
 </div>
</template>
<style scoped>
.staff-management{overflow-wrap:anywhere}.staff-section{padding:clamp(16px,3vw,24px);margin-top:24px}.staff-section h2{font-size:1.2rem;margin:0 0 16px}.staff-heading,.staff-row{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}.staff-heading{align-items:center}.staff-row{padding:20px 0;border-top:1px solid var(--pd-border)}.staff-row h3{font-size:1.05rem;margin:0}.staff-row p{margin:8px 0;line-height:1.5}.staff-actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.staff-actions :deep(.el-button){margin:0;min-height:44px;height:auto;white-space:normal;padding:12px 16px}.staff-filter{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px}.staff-filter select{font:inherit;min-height:44px;max-width:100%;padding:8px;border:1px solid var(--pd-border);border-radius:6px}.staff-management :deep(.el-form-item__label){height:auto;line-height:1.5}.staff-management :deep(.el-select){width:100%}
</style>
