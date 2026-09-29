<script setup lang="ts">
/**
 * Main application shell: top header + left sidebar + workspace
 * (spec V2 section 53).
 *
 * The sidebar is data-driven rather than hand-written markup: every section
 * declares its own sub-pages, which gives the selected entry a visible frame and
 * opens its sub-modules underneath, so a page is reachable in one click instead
 * of being found by typing its URL (which is how the piano and pose pages were
 * missed twice).
 *
 * Menu wording follows the required vocabulary: 辅助识别 / 评估 / 分析 /
 * 运动表现 / 训练反馈 / 长期趋势. Words like 确诊, 治愈 and 病情下降 X% are
 * deliberately absent.
 */
import { computed, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  DataAnalysis,
  Document,
  EditPen,
  Fold,
  Histogram,
  HomeFilled,
  InfoFilled,
  Monitor,
  Operation,
  Setting,
  TrendCharts,
  User,
  VideoCamera,
} from '@element-plus/icons-vue'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { patientApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const collapsed = ref(false)

/** When viewing a patient, the sidebar also offers that patient's sub-pages. */
const patientId = computed(() => {
  const value = route.params.id
  return typeof value === 'string' && value ? value : null
})

/**
 * Name of the patient in the current route.
 *
 * Pages linked from the patient list pass it as a query parameter; a direct URL
 * or a refresh does not, so the name is fetched once and cached per id rather
 * than leaving the header saying "已选择".
 */
const patientNames = ref<Record<string, string>>({})

const patientName = computed(() => {
  const fromQuery = route.query.patientName
  if (typeof fromQuery === 'string' && fromQuery) return fromQuery
  const id = patientId.value
  return id ? (patientNames.value[id] ?? null) : null
})

watch(
  patientId,
  async (id) => {
    if (!id || patientNames.value[id]) return
    try {
      const patient = await patientApi.get(id)
      patientNames.value = { ...patientNames.value, [id]: patient.name }
    } catch {
      // A missing or deleted patient is the page's problem to report, not the
      // sidebar's; leave the chip unnamed rather than showing an error here.
    }
  },
  { immediate: true },
)

interface MenuChild {
  title: string
  to: string
  icon?: Component
  /** Shown as a tag next to the title when the page is a placeholder. */
  pending?: boolean
}

interface MenuSection {
  key: string
  title: string
  icon: Component
  /** Set when the section itself is a page; otherwise it is only a container. */
  to?: string
  children?: MenuChild[]
}

const sections = computed<MenuSection[]>(() => {
  const id = patientId.value
  const patientSections: MenuSection[] = id
    ? [
        {
          key: 'patient',
          title: '患者详情',
          icon: Operation,
          to: `/patients/${id}`,
          children: [
            { title: '基本信息', to: `/patients/${id}`, icon: InfoFilled },
            { title: '编辑资料', to: `/patients/${id}/edit`, icon: EditPen },
          ],
        },
        {
          key: 'assessment',
          title: '综合评估',
          icon: Monitor,
          to: `/patients/${id}/assessment`,
          children: [
            { title: '评估会话', to: `/patients/${id}/assessment`, icon: Document },
            {
              title: '微表情 / AI 分析',
              to: `/patients/${id}/assessment/micro-expression`,
              icon: VideoCamera,
            },
            {
              title: 'Finger Tapping',
              to: `/patients/${id}/assessment/finger-tapping`,
              icon: DataAnalysis,
            },
          ],
        },
        {
          key: 'training',
          title: '康复训练',
          icon: DataAnalysis,
          to: `/patients/${id}/training`,
          children: [
            { title: '训练入口', to: `/patients/${id}/training`, icon: Document },
            { title: '虚拟钢琴 / 节奏', to: `/patients/${id}/training/piano`, icon: Histogram },
            { title: '动作训练（Pose）', to: `/patients/${id}/training/movement`, icon: VideoCamera },
          ],
        },
        {
          key: 'functional',
          title: '功能评估',
          icon: Histogram,
          to: `/patients/${id}/functional-assessment`,
          children: [
            {
              title: '9-HPT 钉板测试',
              to: `/patients/${id}/functional-assessment`,
              icon: Histogram,
              pending: true,
            },
          ],
        },
        { key: 'history', title: '历史记录', icon: Document, to: `/patients/${id}/history` },
        { key: 'trends', title: '长期趋势', icon: TrendCharts, to: `/patients/${id}/trends` },
      ]
    : []

  return [
    { key: 'dashboard', title: '工作台', icon: HomeFilled, to: '/dashboard' },
    {
      key: 'patients',
      title: '患者管理',
      icon: User,
      to: '/patients',
      children: [
        { title: '患者列表', to: '/patients', icon: Document },
        { title: '新增患者', to: '/patients/new', icon: EditPen },
      ],
    },
    ...patientSections,
    { key: 'model-status', title: '模型状态', icon: Setting, to: '/system/model-status' },
  ]
})

/**
 * The child entry that matches the current route.
 *
 * Matched on the longest prefix so `/patients/x/training/piano` selects the
 * piano entry and not the training overview.
 */
const activePath = computed(() => route.path)

const openSections = computed(() =>
  sections.value
    .filter((section) => section.children?.some((child) => child.to === activePath.value))
    .map((section) => section.key),
)

/**
 * Force the menu to re-render when the open section changes.
 *
 * `default-openeds` is only read when the menu mounts, so without this the
 * sub-modules of a newly selected section would stay collapsed.
 */
const menuKey = computed(() => `${openSections.value.join('|')}::${collapsed.value}`)

/** The section title shown above the breadcrumb of the current page. */
const currentSection = computed(
  () =>
    sections.value.find(
      (section) =>
        section.to === activePath.value ||
        section.children?.some((child) => child.to === activePath.value),
    ) ?? null,
)

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确认退出登录？', '提示', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  await auth.logout()
  ElMessage.success('已退出登录')
  router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="pd-shell">
    <el-aside :width="collapsed ? '64px' : '238px'" class="pd-aside">
      <div class="pd-brand">
        <span class="pd-brand-mark">PD</span>
        <span v-if="!collapsed" class="pd-brand-text">
          <strong>数字康复平台</strong>
          <small>辅助评估与训练</small>
        </span>
      </div>

      <div v-if="patientId && !collapsed" class="pd-patient-chip">
        <span class="pd-patient-label">当前患者</span>
        <span class="pd-patient-name">{{ patientName ?? '已选择' }}</span>
      </div>

      <el-menu
        :key="menuKey"
        :default-active="activePath"
        :default-openeds="openSections"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="pd-menu"
      >
        <template v-for="section in sections" :key="section.key">
          <!-- Sections with sub-modules expand and show them underneath -->
          <el-sub-menu v-if="section.children?.length" :index="section.key">
            <template #title>
              <el-icon><component :is="section.icon" /></el-icon>
              <span class="pd-menu-title">{{ section.title }}</span>
            </template>

            <!-- The section's own page comes first, so it stays reachable -->
            <el-menu-item
              v-for="child in section.children"
              :key="child.to"
              :index="child.to"
            >
              <el-icon><component :is="child.icon ?? Document" /></el-icon>
              <template #title>
                <span class="pd-menu-title">{{ child.title }}</span>
                <el-tag v-if="child.pending" size="small" type="info" class="pd-menu-tag">
                  待实现
                </el-tag>
              </template>
            </el-menu-item>
          </el-sub-menu>

          <el-menu-item v-else :index="section.to">
            <el-icon><component :is="section.icon" /></el-icon>
            <template #title>{{ section.title }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="pd-header">
        <div class="pd-header-left">
          <el-button text :icon="Fold" @click="collapsed = !collapsed" />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>PD-Rehab-Web</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentSection && currentSection.title !== route.meta.title">
              {{ currentSection.title }}
            </el-breadcrumb-item>
            <el-breadcrumb-item>{{ route.meta.title ?? '' }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="pd-header-right">
          <el-tag v-if="auth.user" type="info" effect="plain">
            {{ auth.displayName }}（{{ auth.roleLabel }}）
          </el-tag>
          <el-button text @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>

      <el-main class="pd-main">
        <router-view />
        <MedicalDisclaimer />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.pd-shell {
  height: 100vh;
}

.pd-aside {
  background: var(--pd-surface);
  border-right: 1px solid var(--pd-border);
  transition: width 0.2s ease;
  overflow-x: hidden;
  overflow-y: auto;
}

.pd-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 60px;
  padding: 0 16px;
  border-bottom: 1px solid var(--pd-border);
  white-space: nowrap;
}

.pd-brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: var(--pd-primary);
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  flex: none;
}

.pd-brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.pd-brand-text strong {
  font-size: 14px;
}

.pd-brand-text small {
  color: var(--pd-text-muted);
  font-size: 11px;
}

.pd-patient-chip {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin: 10px 12px 4px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f2f6fa;
  border: 1px solid var(--pd-border);
  white-space: nowrap;
  overflow: hidden;
}

.pd-patient-label {
  font-size: 11px;
  color: var(--pd-text-muted);
}

.pd-patient-name {
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pd-menu {
  border-right: none;
  padding: 6px 8px 24px;
}

.pd-menu-title {
  font-size: 13px;
}

.pd-menu-tag {
  margin-left: 6px;
  transform: scale(0.85);
  transform-origin: left center;
}

/* ---------------------------------------------------------------- selection
   The selected entry gets an actual frame, not just a colour change: a light
   fill, a border and a left accent bar, so it is obvious which module is open.
   Sub-modules of the current section are tinted a little lighter than their
   parent so the hierarchy stays readable. */
.pd-menu :deep(.el-menu-item) {
  height: 38px;
  line-height: 38px;
  margin: 3px 0;
  border-radius: 8px;
  border: 1px solid transparent;
  color: var(--pd-text-secondary);
}

.pd-menu :deep(.el-menu-item:hover) {
  background: #f2f6fa;
  color: var(--pd-text);
}

.pd-menu :deep(.el-menu-item.is-active) {
  background: #e8f1fb;
  color: var(--pd-primary);
  border-color: #bcd7ef;
  border-left: 3px solid var(--pd-primary);
  font-weight: 600;
}

.pd-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: var(--pd-primary);
  font-weight: 600;
}

.pd-menu :deep(.el-sub-menu__title) {
  height: 38px;
  line-height: 38px;
  margin: 3px 0;
  border-radius: 8px;
  border: 1px solid transparent;
  color: var(--pd-text-secondary);
}

.pd-menu :deep(.el-sub-menu__title:hover) {
  background: #f2f6fa;
  color: var(--pd-text);
}

/* The section whose sub-modules are open reads as "current module". */
.pd-menu :deep(.el-sub-menu.is-opened > .el-sub-menu__title) {
  background: #f4f8fc;
  border-color: var(--pd-border);
  color: var(--pd-text);
}

/* Sub-modules sit inset under their section. */
.pd-menu :deep(.el-menu--inline) {
  padding-left: 0;
}

.pd-menu :deep(.el-menu--inline .el-menu-item) {
  height: 34px;
  line-height: 34px;
  min-width: 0;
  padding-left: 38px !important;
  font-size: 13px;
}

.pd-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 20px;
  background: var(--pd-surface);
  border-bottom: 1px solid var(--pd-border);
}

.pd-header-left,
.pd-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pd-main {
  padding: 0;
  background: var(--pd-bg);
  overflow-y: auto;
}
</style>
