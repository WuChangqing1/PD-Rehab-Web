/**
 * Router.
 *
 * Function first: the main entries are 评估中心 / 康复训练 / 随访与报告, and the
 * patient is chosen inside them (`?patientId=`). The old patient-centric paths
 * still work through redirects, so saved bookmarks and demo links do not break.
 *
 * Sub-pages of a hub (/assessment/finger-tapping, /training/piano) are real
 * routes but never appear in the sidebar: each function has exactly one visible
 * entry (see docs/ux_refactor_plan.md section 5).
 */

import { createRouter, createWebHistory } from 'vue-router'
import type { RouteLocationGeneric, RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useTaskModeStore } from '@/stores/taskMode'

/**
 * Carry the patient context across a redirect.
 *
 * Redirect targets receive the raw route location, whose query values may be
 * null or arrays; only single string values are forwarded.
 */
function withPatient(to: RouteLocationGeneric): Record<string, string> {
  const query: Record<string, string> = {}
  const id = to.params.id
  if (typeof id === 'string' && id) query.patientId = id
  for (const key of ['sessionId', 'tab', 'patientName'] as const) {
    const value = to.query[key]
    if (typeof value === 'string' && value) query[key] = value
  }
  return query
}

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

      // ------------------------------------------------------------ patients
      {
        path: 'patients',
        name: 'patients',
        component: () => import('@/pages/PatientsPage.vue'),
        meta: { title: '患者档案' },
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
        meta: { title: '患者资料' },
      },
      {
        path: 'patients/:id/edit',
        name: 'patient-edit',
        component: () => import('@/pages/PatientFormPage.vue'),
        meta: { title: '编辑患者' },
      },

      // ---------------------------------------------------------- assessment
      {
        path: 'assessment',
        name: 'assessment',
        component: () => import('@/pages/AssessmentHubPage.vue'),
        meta: { title: '评估中心' },
      },
      {
        path: 'assessment/micro-expression',
        name: 'assessment-micro-expression',
        component: () => import('@/pages/MicroExpressionPage.vue'),
        meta: { title: '面部表现分析', patientTask: true },
      },
      {
        path: 'assessment/finger-tapping',
        name: 'assessment-finger-tapping',
        component: () => import('@/pages/FingerTappingPage.vue'),
        meta: { title: '手指敲击评估', patientTask: true },
      },

      // ------------------------------------------------------------ training
      {
        path: 'training',
        name: 'training',
        component: () => import('@/pages/TrainingHubPage.vue'),
        meta: { title: '康复训练' },
      },
      {
        path: 'training/piano',
        name: 'training-piano',
        component: () => import('@/pages/PianoTrainingPage.vue'),
        meta: { title: '钢琴节奏训练' },
      },
      {
        path: 'training/movement',
        name: 'training-movement',
        component: () => import('@/pages/MovementTrainingPage.vue'),
        meta: { title: '动作训练' },
      },

      // ------------------------------------------- not yet available to users
      // Kept as routes for development; hidden from the sidebar until real.
      {
        path: 'functional-assessment',
        name: 'functional-assessment',
        component: () => import('@/pages/FunctionalAssessmentPage.vue'),
        meta: { title: '功能测试', hidden: true },
      },
      {
        path: 'follow-up',
        name: 'follow-up',
        component: () => import('@/pages/FollowUpPage.vue'),
        meta: { title: '随访与报告', hidden: true },
      },

      // ------------------------------------------------- system (no menu entry)
      // Kept reachable for whoever operates the server: it reports model
      // availability, GPU details and paths. It is not a clinical function, so
      // it is not in the navigation and carries no role gate -- whoever is
      // signed in can look, exactly as they can at any other page.
      {
        path: 'system/model-status',
        name: 'model-status',
        component: () => import('@/pages/ModelStatusPage.vue'),
        meta: { title: '系统状态' },
      },

      // ------------------------------------------------- legacy path redirects
      // The old patient-centric URLs must not 404: they are in bookmarks and in
      // the demo script. Each keeps the patient and session it carried.
      {
        path: 'patients/:id/assessment',
        redirect: (to) => ({ name: 'assessment', query: withPatient(to) }),
      },
      {
        path: 'patients/:id/assessment/micro-expression',
        redirect: (to) => ({ name: 'assessment-micro-expression', query: withPatient(to) }),
      },
      {
        path: 'patients/:id/assessment/finger-tapping',
        redirect: (to) => ({ name: 'assessment-finger-tapping', query: withPatient(to) }),
      },
      {
        path: 'patients/:id/training',
        redirect: (to) => ({ name: 'training', query: withPatient(to) }),
      },
      {
        path: 'patients/:id/training/piano',
        redirect: (to) => ({ name: 'training-piano', query: withPatient(to) }),
      },
      {
        path: 'patients/:id/training/movement',
        redirect: (to) => ({ name: 'training-movement', query: withPatient(to) }),
      },
      {
        path: 'patients/:id/history',
        redirect: (to) => ({
          name: 'follow-up',
          query: { ...withPatient(to), tab: 'timeline' },
        }),
      },
      {
        path: 'patients/:id/trends',
        redirect: (to) => ({
          name: 'follow-up',
          query: { ...withPatient(to), tab: 'trends' },
        }),
      },
      {
        path: 'patients/:id/report',
        redirect: (to) => ({
          name: 'follow-up',
          query: { ...withPatient(to), tab: 'report' },
        }),
      },
      {
        path: 'patients/:id/functional-assessment',
        redirect: (to) => ({ name: 'functional-assessment', query: withPatient(to) }),
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
  // Honour the Vite base so the same build works at '/' or under '/pd-rehab/'.
  history: createWebHistory(import.meta.env.BASE_URL),
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

  // No role gate. Every signed-in staff member has the same product surfaces;
  // see the auth store for why the server keeps the column but the interface
  // does not use it.
  return true
})

router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) ?? ''
  document.title = title ? `${title} · PD-Rehab-Web` : 'PD-Rehab-Web'

  // Safety net: a page that enters patient mode is expected to clear it on
  // unmount, but a navigation can bypass that. Clearing on every route change
  // means the workspace chrome can never stay hidden on a page that did not ask
  // for it -- which is how an earlier version left the patient with no way out.
  useTaskModeStore().reset()
})

export default router
