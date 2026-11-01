<script setup lang="ts">
import { t } from '@/i18n'
import {captureAssessmentCleanup} from '@/navigation/assessmentLifecycle'

/**
 * Facial video analysis.
 *
 * Reached from 评估中心 with a patient, or directly with `?patientId=`. If no
 * session exists yet the page creates one itself: the old flow refused to work
 * without a session id and told the operator to go and create one elsewhere,
 * which is a dead end dressed up as guidance.
 *
 * Sessions remain in the database -- they are how results are grouped -- but they
 * are not something the operator has to think about.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'

import FaceAnalysisResult from '@/components/FaceAnalysisResult.vue'
import PatientSelector from '@/components/PatientSelector.vue'
import PatientTaskLayout from '@/components/PatientTaskLayout.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import VideoCapturePanel from '@/components/VideoCapturePanel.vue'
import MicroFlowKeyframes from '@/components/MicroFlowKeyframes.vue'
import FaceKeyframeSelection from '@/components/FaceKeyframeSelection.vue'
import type {SelectionMetadata} from '@/emotion/selection'
import { assessmentApi, systemApi } from '@/api'
import { notifyError, toApiError } from '@/api/client'
import { usePatientContextStore } from '@/stores/patientContext'
import { useTaskModeStore } from '@/stores/taskMode'
import type { MicroExpressionResult, Patient } from '@/types'
import {validKeyframes,type VideoFrameInfo} from '@/emotion/keyframes'
import {http} from '@/api/client'

let pageActive=true
const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patient = ref<Patient | null>(null)
const sessionId = ref<string | null>(null)
const comprehensive = ref(false)
const returnTarget = computed(() => comprehensive.value && sessionId.value
  ? { name: 'assessment-comprehensive', params: { sessionId: sessionId.value }, query: { patientId: patientId.value ?? undefined } }
  : { name: 'assessment', query: { patientId: patientId.value ?? undefined } })
const returnLabel = computed(() => comprehensive.value ? '返回综合评估' : '返回评估中心')

const modelReady = ref(false)
const microflowConnected = ref(false)
const causalnetConnected=ref(false)
const microflowIssue = ref(false)
const onsetFrame = ref(1)
const apexFrame = ref<number|null>(null)
const offsetFrame=ref<number|null>(null)
const videoInfo=ref<VideoFrameInfo|null>(null)
const inspecting=ref(false)
const selecting=ref(false)
const capturing=ref(false)
const automaticReady=ref(false)
const selectionReceipt=ref<SelectionMetadata>()
function updateSelection(value:{onset:number;apex:number|null;offset:number|null;info:VideoFrameInfo|null;ready:boolean;busy:boolean;metadata?:SelectionMetadata}){
 onsetFrame.value=value.onset;apexFrame.value=value.apex;offsetFrame.value=value.offset
 videoInfo.value=value.info;automaticReady.value=value.ready;selecting.value=value.busy;selectionReceipt.value=value.metadata
}
function captureChanged(active:boolean){
 capturing.value=active
 if(active)void setClip({blob:null,name:''})
}
let clipRevision=0
let patientRevision=0
const keyframesValid=computed(()=>(!causalnetConnected.value||automaticReady.value)&&!capturing.value&&!selecting.value&&validKeyframes(onsetFrame.value,apexFrame.value,offsetFrame.value,causalnetConnected.value,videoInfo.value?.frame_count??1800)&&(!causalnetConnected.value||videoInfo.value!==null)&&!inspecting.value)
const results = ref<MicroExpressionResult[]>([])
const loading = ref(false)
const uploading = ref(false)
const clip = ref<{ blob: Blob | null; name: string }>({ blob: null, name: '' })

/**
 * Whether the screen currently belongs to the patient.
 *
 * Set by the doctor pressing 开始检查, cleared by 返回. Choosing the patient is
 * still a doctor activity, so it happens in the normal shell.
 */
const started = ref(false)
const analyzed = ref(false)
const resultPanel=ref<HTMLElement|null>(null)
const taskMode = useTaskModeStore()

const taskProgress = computed(() => (analyzed.value ? '已完成' : '进行中'))

function startTask() {
  started.value = true
  taskMode.enter()
}

async function leaveTask() {
  if (hasClip.value && !analyzed.value) {
    try {
      await ElMessageBox.confirm(t('本次录制尚未分析，确定要离开吗？'), t('提示'), {
        confirmButtonText: t('离开'),
        cancelButtonText: t('继续检查'),
        type: 'warning',
      })
    } catch {
      return
    }
  }
  started.value = false
  taskMode.exit()
  router.push(returnTarget.value)
}

const patientId = computed(() => patient.value?.id ?? null)
const hasClip = computed(() => clip.value.blob !== null)
async function setClip(value:{blob:Blob|null;name:string}) {
  const revision=++clipRevision
  automaticReady.value=false;selectionReceipt.value=undefined;selecting.value=false
  clip.value=value;onsetFrame.value=1;apexFrame.value=null;offsetFrame.value=null;analyzed.value=false;videoInfo.value=null;inspecting.value=false
  if(!value.blob||!microflowConnected.value||causalnetConnected.value)return
  inspecting.value=true
  try{
    const form=new FormData();form.append('video',new File([value.blob],value.name||'recording.webm',{type:value.blob.type}))
    const response=await http.post<VideoFrameInfo>('/micro-expression/video-info',form,{headers:{'Content-Type':'multipart/form-data'}})
    if(revision===clipRevision)videoInfo.value=response.data
  }catch(error){if(revision===clipRevision)notifyError(error,'无法读取视频。')}
  finally{if(revision===clipRevision)inspecting.value=false}
}


async function loadModelStatus() {
  try {
    const models = await systemApi.models()
    const model = models.models.micro_expression_model
    modelReady.value = model?.is_ready === true
    causalnetConnected.value=model?.extra?.adapter==='causalnet'
    microflowConnected.value = model?.extra?.adapter === 'microflow_da'||causalnetConnected.value
    microflowIssue.value = !!model?.extra?.known_source_issue
  } catch {
    modelReady.value = false
  }
}

async function loadResults() {
  if (!sessionId.value) return
  const session=sessionId.value,patient=patientId.value,revision=patientRevision
  try {
    const rows=await assessmentApi.listMicroExpression(session)
    if(sessionId.value===session&&patientId.value===patient&&patientRevision===revision)results.value=rows
  } catch {
    if(sessionId.value===session&&patientId.value===patient&&patientRevision===revision)results.value=[]
  }
}

/** Find an open session of the right kind, or create one. */
async function ensureSession(): Promise<string | null> {
  const originPatient=patientId.value
  const discardCreated=captureAssessmentCleanup()
  if(!pageActive)return null
  if(sessionId.value){
    const current=await assessmentApi.getSession(sessionId.value)
    if(!pageActive||patientId.value!==originPatient)return null
    if(current.status==='IN_PROGRESS')return current.id
    if(current.session_type==='COMPREHENSIVE')return null
    sessionId.value=null
  }
  if(!patientId.value)return null
  const created = await assessmentApi.createSession(patientId.value, {
    session_type: 'MICRO_EXPRESSION_ONLY',
    medication_state: patient.value?.medication_state ?? 'UNKNOWN',
  })
  if(!pageActive||patientId.value!==originPatient){
    await discardCreated(created.id)
    return null
  }
  sessionId.value = created.id
  await router.replace({query:{...route.query,patientId:patientId.value,sessionId:created.id}})
  if(!pageActive){await discardCreated(created.id);return null}
  return created.id
}

async function usePatient(id: string) {
  if(uploading.value)return
  const revision=++patientRevision
  await setClip({blob:null,name:''})
  const resolved=await store.resolve(id)
  if(revision!==patientRevision)return
  patient.value = resolved
  router.replace({ query: { ...route.query, patientId: id } })
  sessionId.value = null
  comprehensive.value = false
  results.value = []
  const fromQuery = route.query.sessionId
  if (typeof fromQuery === 'string' && fromQuery) {
    sessionId.value = fromQuery
    if (await assertSessionMatchesPatient()) await loadResults()
  }
}

function changePatient(){
  if(uploading.value)return
  patientRevision++
  patient.value=null;sessionId.value=null;results.value=[]
  comprehensive.value=false
  router.replace({query:{...route.query,patientId:undefined,sessionId:undefined}})
  void setClip({blob:null,name:''})
}

/** Refuse to analyse when the URL's patient and the session's patient disagree. */
async function assertSessionMatchesPatient(): Promise<boolean> {
  if(!pageActive)return false
  if (!sessionId.value || !patientId.value) return true
  const id=sessionId.value,patient=patientId.value,revision=patientRevision
  try {
    const session = await assessmentApi.getSession(id)
    if(id!==sessionId.value||patient!==patientId.value||revision!==patientRevision)return false
    if (session.patient_id !== patient) {
      ElMessage.error(t('当前评估记录与所选患者不一致，请重新选择。'))
      sessionId.value = null
      return false
    }
    comprehensive.value = session.session_type === 'COMPREHENSIVE'
    return true
  } catch {
    if(id!==sessionId.value||patient!==patientId.value||revision!==patientRevision)return false
    ElMessage.error(t('无法读取该评估记录，请重新开始。'))
    sessionId.value = null
    return false
  }
}

async function analyze() {
  if(uploading.value)return
  if (!modelReady.value) { ElMessage.warning(t('模型权重尚未就绪，暂时无法分析。')); return }
  if (microflowConnected.value&&!keyframesValid.value) { ElMessage.warning(t(causalnetConnected.value?'请先选择有效的起始帧、峰值帧和结束帧。':'请先填写有效的起始帧和峰值帧。')); return }
  if (!clip.value.blob) {
    ElMessage.warning(t('请先录制或选择一个视频文件。'))
    return
  }
  uploading.value = true
  try {
    if (!(await assertSessionMatchesPatient())) return
    const id = await ensureSession()
    if (!id) return
    if (!(await assertSessionMatchesPatient())) return

    const file = new File([clip.value.blob], clip.value.name || 'recording.webm', {
      type: clip.value.blob.type,
    })
    const result = await assessmentApi.uploadMicroExpression(id, file, 'UNKNOWN',
      microflowConnected.value?{onset_frame:onsetFrame.value,apex_frame:apexFrame.value!,...(causalnetConnected.value?{offset_frame:offsetFrame.value!}:{})}:undefined,selectionReceipt.value)
    results.value = [result, ...results.value]
    analyzed.value = true
    await nextTick()
    resultPanel.value?.scrollIntoView({behavior:'smooth',block:'start'})
    ElMessage.success(t('分析完成'))
  } catch (error) {
    const apiError = toApiError(error)
    if (apiError.code === 'MODEL_NOT_CONFIGURED') {
      // Operator-facing wording; the technical reason lives in 系统设置.
      ElMessage.warning(t('面部表现分析当前暂不可用，请联系技术维护人员。'))
    } else {
      notifyError(error, '分析失败。')
    }
  } finally {
    uploading.value = false
  }
}

onMounted(async () => {
  await loadModelStatus()
  const fromQuery = route.query.patientId
  if (typeof fromQuery === 'string' && fromQuery) await usePatient(fromQuery)
})

// Leaving the page must restore the workspace chrome even if the doctor used
// the browser's back button instead of 返回.
onBeforeUnmount(() => {pageActive=false;clipRevision++;patientRevision++;taskMode.exit()})
</script>

<template>
  <!--
    Patient mode. The doctor starts the task; the patient then sees only the
    camera, one instruction and one button. `返回评估中心` in the header is the
    way out, and it asks before discarding an unanalysed recording.
  -->
  <PatientTaskLayout
    v-if="started && patient"
    :patient="patient"
    :task="$t('面部表现检查')"
    :instruction="$t('请正对镜头，让面部完整入镜')"
    :progress="$t(taskProgress)"
    :back-label="$t('返回评估中心')"
    @exit="leaveTask"
  >
    <div class="pd-card">
      <div class="pd-card-header"><span class="pd-card-title">{{ $t("录制面部视频") }}</span></div>
      <div class="pd-card-body">
        <VideoCapturePanel guided
          :show-file-preview="!microflowConnected"
          :disabled="uploading||selecting"
          @recording-change="captureChanged"
          :max-seconds="30"
          :instruction="$t('请让患者正对镜头，面部完整入镜，光线均匀。')"
          @change="setClip"
        />

        <FaceKeyframeSelection v-if="causalnetConnected && hasClip" :blob="clip.blob" :filename="clip.name" :disabled="!modelReady||uploading||capturing" @change="updateSelection"/>
        <MicroFlowKeyframes v-else-if="microflowConnected && !causalnetConnected && hasClip" v-model:onset="onsetFrame" v-model:apex="apexFrame" v-model:offset="offsetFrame" :require-offset="causalnetConnected" :blob="clip.blob" :info="videoInfo" :inspecting="inspecting" :disabled="!modelReady||uploading"/>

        <el-button
          v-if="!analyzed && hasClip"
          type="primary"
          size="large"
          class="pd-big-action"
          style="width: 100%; margin-top: 16px"
          :loading="uploading"
          :disabled="!modelReady||!hasClip||(microflowConnected&&!keyframesValid)"
          @click="analyze"
        >
          {{ $t("开始分析") }}
        </el-button>

        <div v-if="analyzed" ref="resultPanel" class="task-done">
          <p class="task-done-title">{{ $t("检查已完成") }}</p>
          <FaceAnalysisResult v-if="results[0]" :result="results[0]"/>
          <el-button size="large" style="width: 100%" @click="leaveTask">{{ $t(returnLabel) }}</el-button>
        </div>
      </div>
    </div>
  </PatientTaskLayout>

  <div v-else v-loading="loading" class="pd-page">
    <router-link class="pd-back" :to="returnTarget">
      <el-icon><ArrowLeft /></el-icon>{{ $t(returnLabel) }}
    </router-link>

    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">{{ $t("面部表现分析") }}</h1>

      </div>
    </div>

    <el-alert v-if="microflowConnected" class="microflow-status" type="info" show-icon :closable="false"
      :title="$t(modelReady?'面部模型已就绪':'面部分析暂不可用')"
      :description="$t(modelReady ? undefined : '等待模型权重与验证。')"/>

    <SelectedPatientBar v-if="patient" :patient="patient" @change="changePatient" />

    <PatientSelector
      v-if="!patient"
      :title="$t('选择患者')"
      :description="$t('搜索姓名或患者编号，选择后即可开始面部表现分析。')"
      @select="(p) => usePatient(p.id)"
    />

    <template v-else>
      <!-- What is unavailable is stated plainly; the technical reason is not here. -->
      <el-alert
        v-if="!modelReady&&!microflowConnected"
        type="info"
        show-icon
        :closable="false"
        :title="$t('面部表现分析当前暂不可用')"
        :description="$t('该功能需要模型支持，当前环境尚未配置。其他评估与训练不受影响。')"
        style="margin-bottom: 16px"
      />

      <div class="pd-card" style="margin-bottom: 16px">
        <div class="pd-card-body start-row">
          <div>
            <strong>{{ $t("使用简洁检查界面") }}</strong>

          </div>
          <el-button
            type="primary"
            size="large"
            :disabled="!modelReady"
            @click="startTask"
          >
            {{ $t("进入检查界面") }}
          </el-button>
        </div>
      </div>

      <div class="pd-grid pd-grid-2">
        <div class="pd-card">
          <div class="pd-card-header"><span class="pd-card-title">{{ $t("录制面部视频") }}</span></div>
          <div class="pd-card-body">
            <VideoCapturePanel guided
              :show-file-preview="!microflowConnected"
              :disabled="!modelReady||uploading||selecting"
              @recording-change="captureChanged"
              :max-seconds="30"
              :instruction="$t('请让患者正对镜头，面部完整入镜，光线均匀。')"
              @change="setClip"
            />

            <FaceKeyframeSelection v-if="causalnetConnected && hasClip" :blob="clip.blob" :filename="clip.name" :disabled="!modelReady||uploading||capturing" @change="updateSelection"/>
        <MicroFlowKeyframes v-else-if="microflowConnected && !causalnetConnected && hasClip" v-model:onset="onsetFrame" v-model:apex="apexFrame" v-model:offset="offsetFrame" :require-offset="causalnetConnected" :blob="clip.blob" :info="videoInfo" :inspecting="inspecting" :disabled="!modelReady||uploading"/>

            <el-button
              v-if="hasClip && !analyzed"
              type="primary"
              class="pd-big-action"
              style="width: 100%; margin-top: 12px"
              :loading="uploading"
              :disabled="!modelReady || !hasClip || (microflowConnected&&!keyframesValid)"
              @click="analyze"
            >
              {{ $t("开始分析") }}
            </el-button>
          </div>
        </div>

        <div ref="resultPanel" class="pd-card">
          <div class="pd-card-header"><span class="pd-card-title">{{ $t("分析结果") }}</span></div>
          <div class="pd-card-body">
            <div v-if="!results.length" class="pd-empty">
              {{ $t("尚无分析结果。完成一次分析后，这里会显示标签分布与概率。") }}
            </div>

            <template v-else>
              <FaceAnalysisResult v-if="results[0]" :result="results[0]"/>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.microflow-status{margin-bottom:20px}
.start-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.task-done {
  scroll-margin-top:150px;
  margin-top: 20px;
  text-align: center;
}

.task-done-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
}
</style>
