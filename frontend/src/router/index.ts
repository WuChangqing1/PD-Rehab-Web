/**
 * Router.
 *
 * Route paths are fixed by spec V2 section 52. Pages whose feature belongs to a
 * later phase are real routes rendering a "not implemented yet" placeholder --
 * they never show invented data.
 */

import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/pages/DashboardPage.vue'),
        meta: { title: '工作台' },
      },
      {
        path: 'patients',
        name: 'patients',
        component: () => import('@/pages/PatientsPage.vue'),
        meta: { title: '患者管理' },
      },
      {
        path: 'patients/new',
        name: 'patient-new',
        component: () => import('@/pages/PatientFormPage.vue'),
        meta: { title: '新增患者' },
      },
      {
        path: 'patients/:id',
        name: 'patient-detail',
        component: () => import('@/pages/PatientDetailPage.vue'),
        meta: { title: '患者详情' },
      },
      {
        path: 'patients/:id/edit',
        name: 'patient-edit',
        component: () => import('@/pages/PatientFormPage.vue'),
        meta: { title: '编辑患者' },
      },
      {
        path: 'patients/:id/assessment',
        name: 'assessment',
        component: () => import('@/pages/AssessmentPage.vue'),
        meta: { title: '综合评估' },
      },
      {
        path: 'patients/:id/assessment/micro-expression',
        name: 'assessment-micro-expression',
        component: () => import('@/pages/MicroExpressionPage.vue'),
        meta: { title: '微表情分析' },
      },
      {
        path: 'patients/:id/assessment/finger-tapping',
        name: 'assessment-finger-tapping',
        component: () => import('@/pages/FingerTappingPage.vue'),
        meta: { title: 'Finger Tapping' },
      },
      {
        path: 'patients/:id/training',
        name: 'training',
        component: () => import('@/pages/TrainingPage.vue'),
        meta: { title: '康复训练' },
      },
      {
        path: 'patients/:id/training/piano',
        name: 'training-piano',
        component: () => import('@/pages/PianoTrainingPage.vue'),
        meta: { title: '钢琴训练' },
      },
      {
        path: 'patients/:id/training/movement',
        name: 'training-movement',
        component: () => import('@/pages/MovementTrainingPage.vue'),
        meta: { title: '动作训练' },
      },
      {
        path: 'patients/:id/history',
        name: 'history',
        component: () => import('@/pages/HistoryPage.vue'),
        meta: { title: '历史记录' },
      },
      {
        path: 'patients/:id/trends',
        name: 'trends',
        component: () => import('@/pages/TrendsPage.vue'),
        meta: { title: '长期趋势' },
      },
      {
        path: 'patients/:id/functional-assessment',
        name: 'functional-assessment',
        component: () => import('@/pages/FunctionalAssessmentPage.vue'),
        meta: { title: '功能评估' },
      },
      {
        path: 'patients/:id/report',
        name: 'report',
        component: () => import('@/pages/ReportPage.vue'),
        meta: { title: '报告' },
      },
      {
        path: 'system/model-status',
        name: 'model-status',
        component: () => import('@/pages/ModelStatusPage.vue'),
        meta: { title: '模型状态' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: { public: true, title: '页面不存在' },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (!auth.initialised) {
    await auth.restore()
  }

  if (to.meta.public) {
    // Already signed in? Skip the login page.
    if (to.name === 'login' && auth.isAuthenticated) {
      return { name: 'dashboard' }
    }
    return true
  }

  if (!auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) ?? ''
  document.title = title ? `${title} · PD-Rehab-Web` : 'PD-Rehab-Web'
})

export default router
