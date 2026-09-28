<script setup lang="ts">
/**
 * Main application shell: top header + left sidebar + workspace
 * (spec V2 section 53).
 *
 * Menu wording follows the required vocabulary: 辅助识别 / 评估 / 分析 /
 * 运动表现 / 训练反馈 / 长期趋势. Words like 确诊, 治愈 and 病情下降 X% are
 * deliberately absent.
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  DataAnalysis,
  Fold,
  Histogram,
  HomeFilled,
  Monitor,
  Operation,
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

/** When viewing a patient, the sidebar also offers that patient's sub-pages. */
const patientId = computed(() => {
  const value = route.params.id
  return typeof value === 'string' && value ? value : null
})

const patientName = computed(() => {
  const value = route.query.patientName
  return typeof value === 'string' ? value : null
})

const activeMenu = computed(() => route.path)

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
    <el-aside :width="collapsed ? '64px' : '224px'" class="pd-aside">
      <div class="pd-brand">
        <span class="pd-brand-mark">PD</span>
        <span v-if="!collapsed" class="pd-brand-text">
          <strong>数字康复平台</strong>
          <small>辅助评估与训练</small>
        </span>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="pd-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <template #title>工作台</template>
        </el-menu-item>

        <el-menu-item index="/patients">
          <el-icon><User /></el-icon>
          <template #title>患者管理</template>
        </el-menu-item>

        <template v-if="patientId">
          <el-menu-item-group :title="collapsed ? '' : `当前患者${patientName ? '：' + patientName : ''}`">
            <el-menu-item :index="`/patients/${patientId}`">
              <el-icon><Operation /></el-icon>
              <template #title>患者详情</template>
            </el-menu-item>
            <el-menu-item :index="`/patients/${patientId}/assessment`">
              <el-icon><Monitor /></el-icon>
              <template #title>综合评估</template>
            </el-menu-item>
            <el-menu-item :index="`/patients/${patientId}/training`">
              <el-icon><DataAnalysis /></el-icon>
              <template #title>康复训练</template>
            </el-menu-item>
            <el-menu-item :index="`/patients/${patientId}/functional-assessment`">
              <el-icon><Histogram /></el-icon>
              <template #title>功能评估</template>
            </el-menu-item>
            <el-menu-item :index="`/patients/${patientId}/history`">
              <el-icon><Setting /></el-icon>
              <template #title>历史记录</template>
            </el-menu-item>
            <el-menu-item :index="`/patients/${patientId}/trends`">
              <el-icon><TrendCharts /></el-icon>
              <template #title>长期趋势</template>
            </el-menu-item>
          </el-menu-item-group>
        </template>

        <el-menu-item index="/system/model-status">
          <el-icon><Setting /></el-icon>
          <template #title>模型状态</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="pd-header">
        <div class="pd-header-left">
          <el-button text :icon="Fold" @click="collapsed = !collapsed" />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>PD-Rehab-Web</el-breadcrumb-item>
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

.pd-menu {
  border-right: none;
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
