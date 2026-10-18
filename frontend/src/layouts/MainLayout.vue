<script setup lang="ts">
/**
 * Application shell for signed-in staff.
 *
 * FIVE ENTRIES, IDENTICAL FOR EVERYONE
 * ====================================
 * There is exactly one navigation, and it does not vary by who signed in. The
 * module is the Parkinson's assessment and rehabilitation part of a larger
 * hospital platform; account types and permissions belong to that parent system,
 * not here. So the list is a constant: 工作台 / 患者档案 / 评估中心 / 康复训练 /
 * 随访与报告. Technical surfaces (model status, GPU, model paths) are not a
 * clinical function and have no entry at all -- the route remains reachable for
 * whoever operates the server.
 *
 * THREE LAYOUTS, ONE PAGE SET
 * ===========================
 * Desktop keeps the fixed sidebar. Tablet starts with it collapsed. Below 768px
 * the sidebar is gone entirely and navigation moves into a drawer behind a
 * hamburger, with a compact header: menu, page title, account. The pages
 * themselves are the same components in all three cases.
 *
 * When a patient task is running the page raises `taskMode` and this chrome
 * steps aside (see PatientTaskLayout).
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Expand,
  Fold,
  User,
} from '@element-plus/icons-vue'

import NavigationIcon from '@/components/NavigationIcon.vue'

import { useAuthStore } from '@/stores/auth'
import { useTaskModeStore } from '@/stores/taskMode'

const auth = useAuthStore()
const taskMode = useTaskModeStore()
const route = useRoute()
const router = useRouter()

const collapsed = ref(false)
/** Mobile drawer. Only ever opened from the hamburger. */
const drawerOpen = ref(false)

/**
 * Which layout is active.
 *
 * A media query listener rather than a resize handler: `matchMedia` fires only
 * when the answer actually changes, and the tablet breakpoint also decides
 * whether the sidebar starts collapsed.
 */
const isMobile = ref(false)
const isTablet = ref(false)
let mobileQuery: MediaQueryList | null = null
let tabletQuery: MediaQueryList | null = null

function syncLayout() {
  isMobile.value = mobileQuery?.matches ?? false
  isTablet.value = tabletQuery?.matches ?? false
  // The tablet default is folded; the user can still open it. On desktop the
  // sidebar is always expanded again, so a fold made on a tablet does not
  // follow the operator back to a large screen.
  if (!isMobile.value && !isTablet.value) collapsed.value = false
  if (isMobile.value) collapsed.value = false
  else if (isTablet.value) collapsed.value = true
}

onMounted(() => {
  mobileQuery = window.matchMedia('(max-width: 767px)')
  tabletQuery = window.matchMedia('(min-width: 768px) and (max-width: 1199px)')
  syncLayout()
  mobileQuery.addEventListener('change', syncLayout)
  tabletQuery.addEventListener('change', syncLayout)
})

onBeforeUnmount(() => {
  mobileQuery?.removeEventListener('change', syncLayout)
  tabletQuery?.removeEventListener('change', syncLayout)
})

interface MenuEntry {
  key: string
  title: string
  to: string
}

/** The product navigation. Not filtered by anything, on purpose. */
const entries: MenuEntry[] = [
  { key: 'dashboard', title: '工作台', to: '/dashboard' },
  { key: 'patients', title: '患者档案', to: '/patients' },
  { key: 'assessment', title: '评估中心', to: '/assessment' },
  { key: 'training', title: '康复训练', to: '/training' },
  { key: 'follow-up', title: '随访与报告', to: '/follow-up' },
]

/**
 * Which entry is highlighted.
 *
 * Matched on the path prefix so the sub-pages of a hub light up their hub:
 * `/assessment/finger-tapping` must show 评估中心 and not nothing.
 */
const activeEntry = computed(() => {
  const path = route.path
  if (path.startsWith('/patients')) return 'patients'
  if (path.startsWith('/assessment')) return 'assessment'
  if (path.startsWith('/training')) return 'training'
  if (path.startsWith('/follow-up')) return 'follow-up'
  return 'dashboard'
})

const currentTitle = computed(() => (route.meta.title as string | undefined) ?? '')

/** Close the drawer after navigating, otherwise it covers the page it opened. */
function go(to: string) {
  drawerOpen.value = false
  router.push(to)
}

async function handleLogout() {
  drawerOpen.value = false
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
  <!--
    One tree, two chromes.

    The sidebar and header are hidden individually rather than by swapping the
    whole shell. An earlier version put `<router-view>` in both branches of a
    v-if/v-else, which meant entering patient mode destroyed and recreated the
    routed page: its state reset, its unmount hook cleared the flag, and the
    screen bounced straight back to the workspace. Keeping the view in one place
    in the tree keeps the page mounted through the switch.
  -->
  <el-container class="pd-shell">
    <a href="#main-content" class="pd-skip-link">跳转到主要内容</a>
    <!-- Desktop and tablet only. Below 768px navigation lives in the drawer. -->
    <el-aside
      v-if="!taskMode.active && !isMobile"
      :width="collapsed ? 'var(--pd-aside-collapsed)' : 'var(--pd-aside-width)'"
      class="pd-aside"
    >
      <router-link class="pd-brand" :class="{ 'is-collapsed': collapsed }" :to="{ name: 'dashboard' }" aria-label="数字康复平台，返回工作台" title="返回工作台">
        <span class="pd-brand-mark" aria-hidden="true">p<span>d</span><i /></span>
        <span v-if="!collapsed" class="pd-brand-text">
          <strong>数字康复平台</strong>
        </span>
      </router-link>
      <nav class="pd-nav" aria-label="主要导航">
        <router-link
          v-for="entry in entries"
          :key="entry.key"
          :to="entry.to"
          class="pd-nav-item"
          :class="{ 'is-active': activeEntry === entry.key }"
          :aria-current="activeEntry === entry.key ? 'page' : undefined"
          :title="collapsed ? entry.title : undefined"
        >
          <NavigationIcon :name="entry.key" :active="activeEntry === entry.key"/>
          <span v-if="!collapsed" class="pd-nav-title">{{ entry.title }}</span>
        </router-link>
      </nav>
      <div class="pd-sidebar-footer">
        <el-tooltip :content="collapsed ? '展开导航栏' : '收起导航栏'" placement="right" :disabled="!collapsed">
          <span class="pd-sidebar-trigger"><el-button text class="pd-sidebar-toggle" :icon="collapsed ? Expand : Fold" :aria-label="collapsed ? '展开导航栏' : '收起导航栏'" :aria-expanded="!collapsed" @click="collapsed = !collapsed"><span v-if="!collapsed">收起导航栏</span></el-button></span>
        </el-tooltip>
      </div>
    </el-aside>

    <el-container>
      <!-- Mobile header: menu, page title, account. No breadcrumb, no role. -->
      <el-header v-if="!taskMode.active && isMobile" class="pd-header pd-header-mobile">
        <el-button
          text
          :icon="Expand"
          class="pd-hamburger"
          aria-label="打开导航菜单"
          @click="drawerOpen = true"
        />
        <span class="pd-header-title">{{ currentTitle }}</span>
        <el-button text class="pd-header-user" @click="handleLogout">
          {{ auth.displayName || '退出' }}
        </el-button>
      </el-header>

      <el-header v-if="!taskMode.active && !isMobile" class="pd-header">
        <div class="pd-header-left">
          <span class="pd-workspace-title">{{ currentTitle }}</span>
        </div>

        <div class="pd-header-right">
          <span class="pd-account-avatar" aria-hidden="true"><el-icon><User /></el-icon></span>
          <span v-if="auth.user" class="pd-header-name">{{ auth.displayName }}</span>
          <el-button text @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>

      <el-main id="main-content" class="pd-main" :class="{ 'is-task': taskMode.active }">
        <router-view />
      </el-main>
    </el-container>

    <!--
      Mobile navigation. The same five entries, in the same order, as the
      sidebar; a drawer rather than a second menu definition.
    -->
    <el-drawer
      v-if="!taskMode.active"
      v-model="drawerOpen"
      direction="ltr"
      size="80%"
      :with-header="true"
      class="pd-nav-drawer"
      title="导航"
    >
      <router-link v-if="!taskMode.active" class="pd-brand pd-drawer-brand" :to="{ name: 'dashboard' }" aria-label="数字康复平台，返回工作台" @click="drawerOpen = false">
        <span class="pd-brand-mark" aria-hidden="true">p<span>d</span><i /></span>
        <span class="pd-brand-text"><strong>数字康复平台</strong></span>
      </router-link>
      <nav class="pd-nav pd-nav-drawer-list" aria-label="主要导航">
        <button
          v-for="entry in entries"
          :key="entry.key"
          type="button"
          class="pd-nav-item"
          :class="{ 'is-active': activeEntry === entry.key }"
          @click="go(entry.to)"
        >
          <NavigationIcon :name="entry.key" :active="activeEntry === entry.key"/>
          <span class="pd-nav-title">{{ entry.title }}</span>
        </button>
      </nav>

      <div class="pd-drawer-foot pd-safe-bottom">
        <span class="pd-muted">{{ auth.displayName }}</span>
        <el-button text @click="handleLogout">退出登录</el-button>
      </div>
    </el-drawer>
  </el-container>
</template>

<style scoped>
.pd-shell {
  height: 100vh;
  height: 100dvh;
}

/* Patient mode: the page brings its own chrome, so the workspace adds none. */
.pd-main.is-task {
  padding: 0;
}

.pd-aside {
  display: flex;
  flex-direction: column;
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
  min-height: 96px;
  padding: 24px 20px;
  color: var(--pd-text);
  flex-shrink: 0;
  white-space: nowrap;
}

.pd-brand.is-collapsed { justify-content: center; padding-inline: 12px; }
.pd-brand:hover { background: #f7f9fc; }
.pd-brand:focus-visible { outline: 2px solid var(--pd-primary); outline-offset: -4px; border-radius: 12px; }
.pd-drawer-brand { min-height: 76px; padding: 8px 0 24px; margin-bottom: 12px; }
.pd-workspace-title { font-size: 15px; font-weight: 500; }

.pd-brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #213e60;
  color: #fff;
  font-weight: 700;
  font-size: 23px;
  flex: none;
}

.pd-brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.pd-brand-text strong {
  font-size: 15px;
}


.pd-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px 24px;
}

.pd-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--pd-text-secondary);
  text-decoration: none;
  font-size: 14px;
  white-space: nowrap;
  cursor: pointer;
  width: 100%;
  text-align: left;
}

.pd-aside:has(.pd-brand.is-collapsed) .pd-nav { padding-inline: 8px; }
.pd-aside:has(.pd-brand.is-collapsed) .pd-nav-item { justify-content: center; padding-inline: 0; }

.pd-sidebar-footer { margin-top:auto; padding:16px; border-top:1px solid var(--pd-border); flex-shrink:0; }
.pd-sidebar-toggle { width:100%; justify-content:flex-start; min-height:44px!important; }
.pd-sidebar-trigger { display:block; width:100%; }
.pd-aside:has(.pd-brand.is-collapsed) .pd-sidebar-footer { padding:12px 8px; }
.pd-aside:has(.pd-brand.is-collapsed) .pd-sidebar-toggle { justify-content:center; }
.pd-nav-item:focus-visible { outline:2px solid var(--pd-primary); outline-offset:2px; }
.pd-nav-item:hover {
  background: #f2f6fa;
  color: var(--pd-text);
}

/* The selected entry gets a real frame, not just a colour change. */
.pd-nav-item.is-active {
  background: var(--pd-primary-soft);
  color: var(--pd-primary-dark);
  border-color: #d5e2f6;
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
  height: var(--pd-header-height);
  padding: 0 var(--pd-page-pad-x);
  background: var(--pd-surface);
  border-bottom: 1px solid var(--pd-border);
}

.pd-header-left,
.pd-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pd-header-name {
  font-size: 14px;
  color: var(--pd-text-secondary);
}

/* ------------------------------------------------------------- mobile header */

.pd-header-mobile {
  display: grid;
  grid-template-columns: 44px 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 0 8px 0 4px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.pd-header-title {
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pd-hamburger {
  width: 44px;
  height: 44px;
  font-size: 20px;
}

.pd-header-user {
  max-width: 96px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* -------------------------------------------------------------- nav drawer */

.pd-nav-drawer-list {
  padding: 0;
  gap: 4px;
}

/* Drawer entries are touch targets, not 42px desktop rows. */
.pd-nav-drawer-list .pd-nav-item {
  min-height: var(--pd-touch);
  font-size: 16px;
}

.pd-drawer-foot {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid var(--pd-border);
}

.pd-main {
  padding: 0;
  background: var(--pd-bg);
  overflow-y: auto;
}
.pd-brand-mark { position: relative; letter-spacing: -2px; padding-bottom: 4px; }
.pd-brand-mark > span { color: #b5d8d4; }
.pd-brand-mark i { position: absolute; width: 5px; height: 5px; border-radius: 50%; background: #b5d8d4; top: 8px; right: 5px; }
.pd-nav-item .el-icon { font-size: 19px; }
.pd-account-avatar { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 50%; background: var(--pd-primary-soft); color: var(--pd-primary); }
.pd-skip-link { position: fixed; left: 16px; top: -80px; z-index: 3000; padding: 12px 16px; border-radius: 8px; background: white; }
.pd-skip-link:focus { top: 12px; }
</style>
