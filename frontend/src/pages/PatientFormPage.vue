<script setup lang="ts">
/**
 * Patient create / edit form. Doubles as /patients/new and /patients/:id/edit.
 *
 * `id_card` is intentionally not part of the form: the platform does not store
 * identity-card numbers at all.
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowLeft, Check } from '@element-plus/icons-vue'

import { patientApi } from '@/api'
import { notifyError } from '@/api/client'
import type { Patient } from '@/types'

const route = useRoute()
const router = useRouter()

const patientId = computed(() => {
  const value = route.params.id
  return typeof value === 'string' && value ? value : null
})
const isEdit = computed(() => Boolean(patientId.value))

const formRef = ref<FormInstance>()
const loading = ref(false)
const saving = ref(false)
const loadError = ref<string | null>(null)

const form = reactive<Record<string, unknown>>({
  hospital_number: '',
  name: '',
  sex: 'UNKNOWN',
  birthday: null,
  phone: '',
  address: '',
  emergency_contact: '',
  emergency_phone: '',
  dominant_hand: 'UNKNOWN',
  affected_side: 'UNKNOWN',
  diagnosis_date: null,
  disease_duration_years: null,
  current_stage: '',
  current_medications: '',
  medication_state: 'UNKNOWN',
  medical_history: '',
  comorbidities: '',
  allergies: '',
  surgery_history: '',
  rehab_history: '',
  doctor_notes: '',
})

const rules: FormRules = {
  hospital_number: [{ required: true, message: '请输入患者编号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
}

async function loadPatient() {
  if (!patientId.value) return
  loading.value = true
  loadError.value = null
  try {
    const patient = await patientApi.get(patientId.value)
    for (const key of Object.keys(form)) {
      const value = (patient as unknown as Record<string, unknown>)[key]
      form[key] = value === undefined ? null : value
    }
  } catch (error) {
    loadError.value = notifyError(error, '无法加载患者信息。').message
  } finally {
    loading.value = false
  }
}

/** Send only fields the user can edit, dropping empties so PATCH stays minimal. */
function buildPayload(): Partial<Patient> {
  const payload: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(form)) {
    if (value === '' ) {
      payload[key] = null
    } else {
      payload[key] = value
    }
  }
  return payload as Partial<Patient>
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const payload = buildPayload()
    if (isEdit.value && patientId.value) {
      await patientApi.update(patientId.value, payload)
      ElMessage.success('已保存')
      router.push({ name: 'patient-detail', params: { id: patientId.value } })
    } else {
      const created = await patientApi.create(payload)
      ElMessage.success('已创建患者')
      router.push({ name: 'patient-detail', params: { id: created.id } })
    }
  } catch (error) {
    notifyError(error, '保存失败。')
  } finally {
    saving.value = false
  }
}

onMounted(loadPatient)
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">{{ isEdit ? '编辑患者' : '新增患者' }}</h1>
        <p class="pd-page-subtitle">
          请使用虚拟或脱敏资料。系统不存储身份证号，所有上传文件均使用 UUID 命名。
        </p>
      </div>
      <el-button :icon="ArrowLeft" @click="router.back()">返回</el-button>
    </div>

    <el-alert v-if="loadError" type="error" :closable="false" show-icon :title="loadError" style="margin-bottom: 16px" />

    <el-form ref="formRef" :model="form" :rules="rules" label-width="130px" :disabled="!!loadError">
      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">基本信息</span></div>
        <div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item label="患者编号" prop="hospital_number">
            <el-input v-model="form.hospital_number as string" placeholder="如 P0001" />
          </el-form-item>
          <el-form-item label="姓名" prop="name">
            <el-input v-model="form.name as string" placeholder="虚拟姓名" />
          </el-form-item>
          <el-form-item label="性别">
            <el-select v-model="form.sex as string" style="width: 100%">
              <el-option label="男" value="MALE" />
              <el-option label="女" value="FEMALE" />
              <el-option label="其他" value="OTHER" />
              <el-option label="未知" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item label="出生日期">
            <el-date-picker
              v-model="form.birthday as string"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="联系电话">
            <el-input v-model="form.phone as string" />
          </el-form-item>
          <el-form-item label="联系地址">
            <el-input v-model="form.address as string" />
          </el-form-item>
          <el-form-item label="紧急联系人">
            <el-input v-model="form.emergency_contact as string" />
          </el-form-item>
          <el-form-item label="紧急联系电话">
            <el-input v-model="form.emergency_phone as string" />
          </el-form-item>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">帕金森相关信息</span></div>
        <div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item label="惯用手">
            <el-select v-model="form.dominant_hand as string" style="width: 100%">
              <el-option label="左手" value="LEFT" />
              <el-option label="右手" value="RIGHT" />
              <el-option label="双手" value="AMBIDEXTROUS" />
              <el-option label="未知" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item label="主要受累侧">
            <el-select v-model="form.affected_side as string" style="width: 100%">
              <el-option label="左侧" value="LEFT" />
              <el-option label="右侧" value="RIGHT" />
              <el-option label="双侧" value="BILATERAL" />
              <el-option label="未知" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item label="临床诊断日期">
            <el-date-picker
              v-model="form.diagnosis_date as string"
              type="date"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="病程（年）">
            <el-input-number v-model="form.disease_duration_years as number" :min="0" :max="100" :precision="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="当前分期">
            <el-input v-model="form.current_stage as string" placeholder="如 H-Y 2 期（医生填写）" />
          </el-form-item>
          <el-form-item label="用药状态">
            <el-select v-model="form.medication_state as string" style="width: 100%">
              <el-option label="开期（ON）" value="ON" />
              <el-option label="关期（OFF）" value="OFF" />
              <el-option label="未知" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item label="当前用药">
            <el-input v-model="form.current_medications as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="末次用药时间">
            <el-date-picker
              v-model="form.last_medication_time as string"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              style="width: 100%"
            />
          </el-form-item>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">其他医疗信息</span></div>
        <div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item label="既往病史">
            <el-input v-model="form.medical_history as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="合并症">
            <el-input v-model="form.comorbidities as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="过敏史">
            <el-input v-model="form.allergies as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="手术史">
            <el-input v-model="form.surgery_history as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="康复史">
            <el-input v-model="form.rehab_history as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="医生备注">
            <el-input v-model="form.doctor_notes as string" type="textarea" :rows="2" />
          </el-form-item>
        </div>
      </div>

      <div class="form-actions">
        <el-button :icon="ArrowLeft" @click="router.back()">取消</el-button>
        <el-button type="primary" :icon="Check" :loading="saving" @click="submit">
          {{ isEdit ? '保存修改' : '创建患者' }}
        </el-button>
      </div>
    </el-form>

  </div>
</template>

<style scoped>
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}
</style>
