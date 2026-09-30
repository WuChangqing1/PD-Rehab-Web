<script setup lang="ts">
/**
 * Main application shell: top header + left sidebar + workspace.
 *
 * The sidebar is FIXED. It used to inject a per-patient menu (患者详情 / 综合评估 /
 * 康复训练 / …) whenever the route carried a patient id, so the navigation grew
 * and shrank as the doctor moved and there was no stable sense of place. The
 * patient is now chosen inside each function instead, and this list never
 * changes shape.
 *
 * The medical disclaimer lives here and only here: it renders once for every
 * signed-in page. Child pages no longer repeat it, and the login page keeps its
 * own compact copy because it sits outside this layout.
 */
import { computed, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  DataAnalysis,
  Fold,
  HomeFilled,
  Monitor,
  Setting,
  TrendCharts,
  User,
} from '@element-plus/icons-vue'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const collapsed = ref(false)

interface MenuEntry {
  key: string
  title: string
  icon: Component
  to: string
  adminOnly?: boolean
}

const entries = computed<MenuEntry[]>(() => {
  const all: MenuEntry[] = [
    { key: 'dashboard', title: '工作台', icon: HomeFilled, to: '/dashboard' },
    { key: 'patients', title: '患者档案', icon: User, to: '/patients' },
    { key: 'assessment', title: '评估中心', icon: Monitor, to: '/assessment' },
    { key: 'training', title: '康复训练', icon: DataAnalysis, to: '/training' },
    { key: 'follow-up', title: '随访与报告', icon: TrendCharts, to: '/follow-up' },
    { key: 'system', title: '系统设置', icon: Setting, to: '/system/model-status', adminOnly: true },
  ]
  return all.filter((entry) => !entry.adminOnly || auth.isAdmin)
})

/**
 * Which entry is highlighted.
 *
 * Matched on the route *name* where possible: the sub-pages of a hub share its
 * prefix, so `/assessment/finger-tapping` must light up 评估中心 and not nothing.
 */
const activeEntry = computed(() => {
  const path = route.path
  if (path.startsWith('/patients')) return 'patients'
  if (path.startsWith('/assessment')) return 'assessment'
  if (path.startsWith('/training')) return 'training'
  if (path.startsWith('/follow-up')) return 'follow-up'
  if (path.startsWith('/system')) return 'system'
  return 'dashboard'
})

const currentTitle = computed(() => (route.meta.title as string | undefined) ?? '')

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
    <el-aside :width="collapsed ? '64px' : '216px'" class="pd-aside">
      <div class="pd-brand">
        <span class="pd-brand-mark">PD</span>
        <span v-if="!collapsed" class="pd-brand-text">
          <strong>数字康复平台</strong>
          <small>辅助评估与训练</small>
        </span>
      </div>

      <nav class="pd-nav">
        <router-link
          v-for="entry in entries"
          :key="entry.key"
          :to="entry.to"
          class="pd-nav-item"
          :class="{ 'is-active': activeEntry === entry.key }"
          :title="collapsed ? entry.title : undefined"
        >
          <el-icon><component :is="entry.icon" /></el-icon>
          <span v-if="!collapsed" class="pd-nav-title">{{ entry.title }}</span>
        </router-link>
      </nav>
    </el-aside>

    <el-container>
      <el-header class="pd-header">
        <div class="pd-header-left">
          <el-button text :icon="Fold" @click="collapsed = !collapsed" />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>PD-Rehab-Web</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
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

.pd-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 8px 24px;
}

.pd-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 42px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid transparent;
  color: var(--pd-text-secondary);
  text-decoration: none;
  font-size: 14px;
  white-space: nowrap;
}

.pd-nav-item:hover {
  background: #f2f6fa;
  color: var(--pd-text);
}

/* The selected entry gets a real frame, not just a colour change. */
.pd-nav-item.is-active {
  background: #e8f1fb;
  color: var(--pd-primary);
  border-color: #bcd7ef;
  border-left: 3px solid var(--pd-primary);
  font-weight: 600;
}

.pd-nav-title {
  overflow: hidden;
  text-overflow: ellipsis;
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
