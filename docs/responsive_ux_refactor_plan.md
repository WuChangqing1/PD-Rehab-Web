# 响应式与身份简化重构 · 审计与执行计划

版本：v1.0.0
日期：2026-10-03
范围：`PD-Rehab-Web` 的身份模型、导航、响应式布局、移动端交互、用户文案
**不在范围内**：Finger Tapping 特征公式、归一化、滤波、CV / Slope / Interruptions、
Response Latency、Timing Error、钢琴自适应引擎、Pose 原始指标、芭蕾 Pose 指标、
模型 Adapter、Raw Data Schema、算法版本追踪。

---

## 0. 审计方法

1. 遍历 `frontend/src` 全部 `.vue` / `.ts` / `.css`，按正则统计角色判断、固定像素宽度、
   `el-table` 用法、`@media` 数量、`:hover` 依赖、`el-dialog` / `el-drawer` 用法。
2. 检查 `VideoCapturePanel` 的移动端必需属性。
3. 检查 `PianoKeyboard` 的输入事件类型。
4. 按项目给出的禁用词表再次全文扫描普通用户界面文案。

---

## 1. 修改前的问题

### 1.1 身份与权限

| 位置 | 现状 |
| --- | --- |
| `stores/auth.ts` | 暴露 `roleLabel`（ADMIN →「管理员」/ 其他 →「医生」）与 `isAdmin` |
| `MainLayout.vue` | 菜单项带 `adminOnly: true`，`entries` 按 `auth.isAdmin` 过滤；顶栏显示 `displayName（roleLabel）` |
| `router/index.ts` | `meta.adminOnly` + 守卫 `if (to.meta.adminOnly && !auth.isAdmin) return dashboard` |
| `DashboardPage.vue` | 「查看详情」链接 `v-if="auth.isAdmin"` |
| `types/index.ts` | `role: 'ADMIN' \| 'DOCTOR'` |

结论：**产品层存在真实的角色分叉**，且顶栏把角色当身份徽章展示。

### 1.2 导航

侧栏当前 6 项，含**系统设置**（模型状态 / GPU / PyTorch / CUDA / MediaPipe）。
这是开发与运维信息，不是医护人员的业务功能。

### 1.3 响应式：**完全没有做**

审计结果：**整个 `frontend/src` 的 `@media` 规则数为 0。**

| # | 问题 | 证据 |
| --- | --- | --- |
| 1 | 没有任何断点 | `@media` 命中 0 处 |
| 2 | 侧栏恒为 216px 固定宽度，主区 `el-container` 无自适应 | `MainLayout.vue` |
| 3 | 手机顶栏塞 Logo + 系统全名 + 面包屑 + 用户名（角色）+ 退出 | `MainLayout.vue` header |
| 4 | 页面内边距固定 `padding: 20px 24px 32px` | `main.css .pd-page` |
| 5 | ~20 处 `el-table` 在 375px 视口必然横向溢出 | Dashboard / Patients / PatientDetail / FollowUp / FingerTapping / Movement / Piano / ModelStatus / PatientSelector |
| 6 | 功能卡网格 `repeat(auto-fill, minmax(320–360px, 1fr))`，窄屏溢出 | `TrainingHubPage`、`AssessmentHubPage`（220px）、`FollowUpPage`（360px） |
| 7 | 表单 `label-width="130px"` 单行挤压 | `PatientFormPage` |
| 8 | 结果区 `.pd-grid-2` 最小 280px，手机上仍是窄双列 | `main.css` |
| 9 | 无移动导航（无 Drawer / 无汉堡菜单） | 全项目无 `el-drawer` |
| 10 | 钢琴键尺寸为桌面设计，手机触摸目标偏小 | `PianoKeyboard.vue` |
| 11 | 芭蕾患者页为桌面双栏思路 | `MovementTrainingPage` + `BalletRhythmPanel` |

### 1.4 移动端交互

- `VideoCapturePanel`：`playsinline` **已设置**（好），但无前后摄像头切换，`getUserMedia`
  错误直接抛原始信息。
- `PianoKeyboard`：**已使用 `@pointerdown`**（好，触摸可用），但键位数量与尺寸未按手机优化，
  且没有横屏提示。
- `BalletRhythmPanel`：AudioContext 在用户点击「开始」时才 `unlock()`（已符合要求），
  但面板布局是桌面宽度设计。
- ECharts：`TrendChart` / `ApertureChart` 已监听 `window.resize`，但没有监听容器尺寸变化，
  手机旋转或抽屉开合后可能不重绘。
- Tooltip 依赖 hover 的地方（钢琴指标表、手指敲击指标表）在触屏上无法打开。

### 1.5 残留文案

| 位置 | 内容 |
| --- | --- |
| `LoginPage.vue` | 「演示账号由后端首次启动时创建，凭据取自 `.env` 的 `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD`」 |
| 顶栏 | 角色徽章「（管理员）」 |

---

## 2. 目标结构

### 2.1 身份

模块定位为大型医疗平台中的「帕金森评估与康复模块」，业务用户统一为
**已登录的医护工作人员**。

- **数据库**：`staff_users.role` 继续存在，不做迁移、不删列。
- **后端**：业务 API（患者 / 评估 / 钢琴 / 芭蕾 / 随访）只要求「已登录」；
  技术 API（`/api/system/*`）保留自身认证逻辑，不构建管理员 UI。
- **前端**：不再显示角色，不再有 `adminOnly`，所有登录用户看到同一套功能。

### 2.2 导航（五项，PC / 平板 / 手机一致）

1. 工作台
2. 患者档案
3. 评估中心
4. 康复训练
5. 随访报告

系统设置与功能测试**不出现在任何导航**。两者的 Route 保留（系统设置供开发/运维直接访问，
功能测试显示「该功能当前未开放」）。

### 2.3 断点（统一，不允许各页乱写）

| 名称 | 范围 | 页面内边距 |
| --- | --- | --- |
| Small mobile | `< 480px` | 12px |
| Mobile | `< 768px` | 12px |
| Tablet | `768px – 1199px` | 16px |
| Desktop | `>= 1200px` | 24px |

新增 `styles/responsive.css` 统一管理，提供
`.mobile-only` / `.desktop-only` / `.pd-stack` / `.pd-grid-2/3/4` 的移动覆盖。

---

## 3. 逐项执行清单

| # | 处理 | 动作 |
| --- | --- | --- |
| 1 | `auth.ts` 的 `roleLabel` / `isAdmin` | 从产品 UI 移除使用；store 不再导出角色文案 |
| 2 | `MainLayout` 菜单 `adminOnly` | 删除该字段与过滤 |
| 3 | `MainLayout` 顶栏角色徽章 | 只显示 `display_name` |
| 4 | `router` 的 `adminOnly` 守卫 | 删除；系统设置路由保留但不在菜单 |
| 5 | `DashboardPage` 的 `v-if="auth.isAdmin"` 链接 | 删除（系统设置不再是产品入口） |
| 6 | 侧栏「系统设置」 | 从 `entries` 删除 |
| 7 | `LoginPage` 的 `.env` / `BOOTSTRAP` 说明 | 删除 |
| 8 | 表头 | Desktop 用 sidebar + header；Tablet 侧栏默认折叠；Mobile 换成 MobileHeader + Drawer，去掉 Breadcrumb |
| 9 | `main.css` / `responsive.css` | 统一内边距与网格断点 |
| 10 | 患者列表 | `< 768px` 变患者卡片（姓名 / 编号 / 性别年龄 / 受累侧 / 用药状态 / 查看 / 编辑） |
| 11 | `PatientSelector` | 手机全宽、搜索框 100%、列表用卡片、触摸区 ≥44px |
| 12 | `PatientFormPage` | 手机单列（label 在上）、医疗资料继续折叠 |
| 13 | 功能卡网格 | Desktop 2–3 列 / Tablet 2 列 / Mobile 1 列 |
| 14 | 结果表格 | 外层可横向滚动容器；关键指标在手机改为卡片；技术指标继续折叠 |
| 15 | 钢琴 | 手机大琴键 + 横屏提示（不强制）；键位改为 7–10 个 |
| 16 | 芭蕾 | 手机单列；横屏提示；节拍面板自适应 |
| 17 | ECharts | 监听容器尺寸（ResizeObserver）+ 旋转重绘；触摸可打开 tooltip |
| 18 | `VideoCapturePanel` | 前后摄像头切换；错误说人话；离开页面停轨道 |
| 19 | 清理 | 再次全文扫描禁用词 |

---

## 4. 风险

| 风险 | 缓解 |
| --- | --- |
| 删角色判断导致越权 | 只删除**产品层**分叉；后端 `CurrentUser` 依赖不变，仍要求登录 |
| 手机改动破坏 PC | 所有移动规则放在 `max-width` 查询内；先在 1440/1366 回归验 |
| 表格改卡片造成两套数据逻辑 | 只用同一个 `rows` 数组渲染两种视图，不分叉 API |
| 钢琴触摸误触 | `touch-action: manipulation` + `pointerdown` + 阻止双击缩放 |
| 移动端相机不可用 | 保留文件上传路径为主要兜底，错误文案不出现技术词 |
| 横屏旋转后图表错位 | ResizeObserver + `orientationchange` 双保险 |
