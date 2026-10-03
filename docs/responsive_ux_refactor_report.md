# Responsive UX Refactor Report

日期：2026-10-03
范围：身份模型、导航、响应式布局、移动端交互、用户文案
配套文档：`docs/responsive_ux_refactor_plan.md`（审计与计划）

---

## 1. Role Simplification

**原结构。** 产品层存在真实的角色分叉，共 13 处：

| 位置 | 原行为 |
| --- | --- |
| `stores/auth.ts` | 导出 `roleLabel`（ADMIN →「管理员」，其余 →「医生」）与 `isAdmin` |
| `layouts/MainLayout.vue` | 菜单项 `adminOnly: true`，`entries` 按 `auth.isAdmin` 过滤；顶栏显示 `displayName（roleLabel）` |
| `router/index.ts` | `meta.adminOnly` + 守卫 `if (to.meta.adminOnly && !auth.isAdmin) return dashboard` |
| `pages/DashboardPage.vue` | 「查看详情」链接 `v-if="auth.isAdmin"` |
| `types/index.ts` | `role: 'ADMIN' \| 'DOCTOR'` |

**如何取消。** 去掉的是**产品层**分叉，不是认证：

- `auth.ts` 不再派生 `roleLabel` / `isAdmin`；`StaffUser` 类型里的 `role` 字段保留（服务端仍返回）。
- `MainLayout` 的 `entries` 从计算属性变成常量数组，没有任何过滤。
- 路由守卫删掉 `adminOnly` 判断，只保留「未登录 → 登录页」。
- 顶栏只显示 `display_name`，不再显示角色。
- `DashboardPage` 删掉那唯一的角色分支。

**数据库是否保留 role。** **保留。** `staff_users.role` 列、枚举、迁移一律未动。
为一个 UX 目标删列是高风险低收益的改动，而且账号生命周期未来由父系统负责。
本轮只保证：**这个字段不影响任何普通业务功能与页面**。

**当前业务用户定义：** 「已登录的医护工作人员」。所有已登录用户拥有完全一致的五个
功能入口与页面权限。患者不建立登录账号。

---

## 2. Final Navigation

固定五项，PC / 平板 / 手机完全一致：

| # | 名称 | 路径 |
| --- | --- | --- |
| 1 | 工作台 | `/dashboard` |
| 2 | 患者档案 | `/patients` |
| 3 | 评估中心 | `/assessment` |
| 4 | 康复训练 | `/training` |
| 5 | 随访与报告 | `/follow-up` |

**不再出现在任何导航：** 系统设置、功能测试、用户管理、管理员、模型管理。
两者的 Route 都保留，直接访问时：`/system/model-status` 显示技术状态页（供运维直接访问，
无导航入口），`/functional-assessment` 显示「该功能暂未开放」。

---

## 3. Desktop

保持原有结构：固定侧栏（216px，可折叠到 64px）+ 顶栏 + 内容区。
面包屑只在桌面显示。页面内边距 24px。功能卡 2–4 列。表格保持表格。
**桌面端本轮未被破坏**：1440×900 与 1366×768 实测无横向溢出、无移动端控件泄漏。

---

## 4. Tablet

- 断点 768–1199px；页面内边距 16px。
- 侧栏默认**折叠**（用户仍可展开）；回到桌面宽度时自动恢复展开，
  平板上的折叠状态不会跟着操作者回到大屏。
- 功能卡按可用宽度 2 列。
- 侧栏在 1024px 下宽度降为 180px，把空间让给内容。

---

## 5. Mobile

**Header。** `< 768px` 不再显示 Logo + 系统全名 + 面包屑 + 用户名 + 角色 + 退出。
改为 `☰ | 页面标题 | 用户名`（用户名点击即退出确认）。面包屑在移动端完全不渲染。

**Drawer。** 汉堡按钮打开 `el-drawer`（宽 80%），内含同样五项 + 退出登录。
条目高度 44px。点击任意条目后**自动关闭**（实测：点击「患者档案」→ URL 变为
`/patients`，抽屉关闭）。Drawer 与侧栏读同一个 `entries` 数组，不会各自漂移。

**Cards。** 功能卡与指标卡在 `< 768px` 变为单列。所有 `auto-fill` 网格的最小轨道
从固定 `minmax(160–360px, 1fr)` 改为 `minmax(min(Npx, 100%), 1fr)`——固定最小值
比手机宽度还大，这正是横向溢出的直接原因。

**Forms。** `label-width="130px"` 在手机上改为 `label-position="top"`。
130px 标签列 + 输入框在 375px 里放不下，挤压后输入框窄到无法输入。

**Dialogs。** 项目模板中**没有** `el-dialog` / `el-drawer`（审计确认 0 处），
唯一的模态是 `ElMessageBox.confirm`，Element Plus 自带响应式。新增的导航 Drawer 宽 80%。

**Tables。** 保留桌面表格；小表格（两列）包在 `.pd-table-scroll` 内自行横向滚动，
不推动整页。多列的患者列表在手机上改为卡片（见 §6）。

**Charts。** `TrendChart` 与 `ApertureChart` 除 `window.resize` 外新增
`ResizeObserver` 监听**容器**尺寸，并监听 `orientationchange`。
旋转屏幕、打开 Drawer、切换 Tab 都会改变宽度但不触发 window resize，
之前图表会保持初次绘制时的宽度。

---

## 6. Patient List Mobile

`< 768px`：表格替换为 `PatientCard` 列表。每张卡：

```
┌──────────────────────────────┐
│ 吴国庆                  0010 │
│ 性别 / 年龄   男 · 73岁       │
│ 主要受累侧    左侧            │
│ 用药状态      开期（ON）      │
│ [ 查看资料 ]   [ 编辑 ]       │
└──────────────────────────────┘
```

- 卡片高 104px，操作按钮 44px。
- **同一份 `rows` 数组**渲染两种视图：没有第二次请求、没有第二种数据结构，
  因此两者不可能不一致。
- 手机分页器去掉总条数与每页条数选择器（`total, sizes, prev, pager, next`
  → `prev, pager, next`），后者在 375px 下约为视口两倍宽。
- 实测：手机 10 张卡 / 0 个可见表格；桌面 10 行 / 1 个可见表格。

---

## 7. Assessment Mobile

**评估中心。** 三张卡纵向单列，每张只有大标题、一行说明和大按钮。

**面部表现分析。** 模型未配置时按钮按设计禁用，页面只说「面部表现分析当前暂不可用」。
相机预览在竖屏手机上从 16:9 改为 3:4，不再浪费大半个屏幕；录制按钮全宽堆叠。

**手指敲击。** 患者模式下先左手后右手自动推进，进度显示「第 N / 2 只手」。
手机实测：进入患者模式后侧栏 0 项、返回按钮 40px、摄像头按钮 48px、无横向溢出。

**综合评估。** 本轮未改动其七步 Stepper 计划（仍为「创建会话 → 进入第一个模块」）。
本轮只保证它在手机上不溢出。

---

## 8. Piano Mobile

**Touch。** 琴键使用 `@pointerdown`（不是 `click`）——`click` 要等手指抬起才触发，
对运动迟缓的患者这是可感知的延迟。新增 `@pointercancel`：触摸被系统打断
（通知、手势判定为滑动）时释放琴键，否则音符会一直保持按下。

**Keys。** 14 个白键在 375px 上每个约 25px，低于所有触摸目标规范。
**没有删减键位**——琴键范围是全量生成的提示流所需要的，删键会让部分提示无法弹奏。
改为：键盘变成可横向滚动的条带，白键最小 46px；**当前应弹的键会自动滚入视野**
（`scrollIntoView` + `nearest`），所以条带虽长但不需要找。

实测（390×844）：14 个白键，每个 46×176px，`scrollWidth 644 > clientWidth 308` 可滚动，
`pointerdown` 后 `is-pressed` 键数 = 1。

**Orientation。** 竖屏时显示「横屏使用可以获得更大的琴键区域。」+「知道了」。
**不阻止任何操作**——支架夹住手机无法旋转的患者必须仍能完成任务。

**Rounds。** 桌面与手机一致：`第 N / 3 轮` 只读，系统自动推进，患者无法手工跳轮。

**Memory Rhythm。** 同一套大琴键，提示段高亮、复现段隐藏。手机尤其适合这个模式，
因为触摸比键盘更接近「点一下」的直觉。

---

## 9. Ballet Mobile

**Camera。** 与面部/手指共用 `VideoCapturePanel`。竖屏 3:4 预览，按钮全宽堆叠。
新增「切换前后摄像头」，**仅当设备确实有第二个摄像头时出现**（`enumerateDevices`
计数），免得给出一个点了没反应的按钮。

**Orientation。** 进入患者模式后提示「把手机放稳，横屏可以获得更大的画面区域。」，
同样不阻止。

**Metronome / Piano。** 节拍仍由 AudioContext 时钟提前调度，UI 只补充队列。
手机浏览器要求用户手势才能出声，逻辑是：患者点「开始」→ `unlock()` 恢复
AudioContext → 才 `start()` 调度。顺序由测试锁定（`unlock` 必须早于 `start`）。
离开页面时 `engine.dispose()` 停止振荡器并关闭 context。

**Seated / Standing。** 坐姿竖屏横屏都可用；站姿扶椅建议横屏（提示里已说明）。
选择方式仍由医生决定，存 `execution_mode`。

---

## 10. Patient Task Mode

**工作人员界面。** 侧栏 + 顶栏 + 内容区。用于选功能、选患者、看结果、看趋势。

**患者界面。** 页面在任务真正开始时置位 `taskMode`，`MainLayout` 分别 `v-if`
侧栏与顶栏（`<router-view>` 保持在树的同一位置——早期版本把它放在 `v-if/v-else`
两个分支里，进入患者模式会销毁重建页面组件，界面闪一下弹回后台）。

患者模式顶部固定：**返回**（44px，实测 40px 渲染高度）、患者姓名 · 编号、任务名、
进度。实测芭蕾（390×844）：侧栏 0 项、口令字号 30px、无横向溢出；
点返回后回到 `/training` 并恢复汉堡导航。

---

## 11. Removed User-facing Content

| 类别 | 删除内容 | 位置 |
| --- | --- | --- |
| **Admin / 角色** | 「管理员」「医生」角色徽章、`adminOnly` 菜单与守卫、`roleLabel`/`isAdmin` | 顶栏、侧栏、路由、store |
| **Demo / Mock** | 工作台「系统当前处于演示数据模式」整块警告；钢琴页「仅用于演示与流程验证」改为「仅用于流程验证」 | Dashboard、Piano |
| **Research** | 「本系统用于科研、辅助评估及康复训练展示」（上轮已删，本轮扫描确认无残留） | — |
| **Phase** | 无残留（扫描确认） | — |
| **Virtual** | 登录页与患者表单中的「虚拟」字样（上轮已处理，本轮扫描确认无残留） | — |
| **开发信息** | 登录页的「演示账号由后端首次启动时创建，凭据取自 `.env` 的 `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD`」整段；登录页标题从「帕金森病智能辅助识别与数字康复训练平台 / 面向医院与科研场景…」改为「帕金森评估与康复 / 请使用工作人员账号登录」 | LoginPage |
| **技术状态** | 从导航移除；页面本身保留（供运维直接访问），仍含 GPU / PyTorch / 模型路径等 | 侧栏 |

自动化复扫（`tests/ui_contract.test.ts`）对 16 个界面文件 × 12 个禁用词做模板级扫描，
并**正是它发现了上面三处残留**。

---

## 12. Hidden Features

| 功能 | 侧栏 | 工作台 | 患者详情 | 功能卡 | 直接访问 Route |
| --- | --- | --- | --- | --- | --- |
| 功能测试（9-HPT / BBT / MDS-UPDRS / PDQ-39） | ✗ | ✗ | ✗ | ✗ | 显示「该功能暂未开放」 |
| 系统设置 / 模型状态 | ✗ | ✗ | ✗ | ✗ | 显示技术状态页 |

**后端与数据未破坏**：`functional_assessments` 表、迁移、`FUNCTIONAL_TEST` 枚举、
`FUNCTIONAL_TEST_LABELS`、`/api/system/health`、`/api/system/models`、`/api/system/gpu`
全部保留。pytest 285 项含相关断言全绿。

---

## 13. Modified Files

**新增**
```
docs/responsive_ux_refactor_plan.md
docs/responsive_ux_refactor_report.md
frontend/src/styles/responsive.css
frontend/src/components/PatientCard.vue
frontend/src/components/OrientationHint.vue
frontend/tests/ui_contract.test.ts
```

**修改（前端）**
```
main.ts                          vite.config.ts（代理端口可配置）
layouts/MainLayout.vue           router/index.ts
stores/auth.ts                   components/PatientSelector.vue
components/VideoCapturePanel.vue components/MetricSummaryCards.vue
piano/PianoKeyboard.vue          components/TrendChart.vue
components/ApertureChart.vue     pages/LoginPage.vue
pages/DashboardPage.vue          pages/PatientsPage.vue
pages/PatientFormPage.vue        pages/AssessmentHubPage.vue
pages/TrainingHubPage.vue        pages/PianoTrainingPage.vue
pages/MovementTrainingPage.vue   pages/FollowUpPage.vue
package.json（test 别名）
```

**后端**：本轮**未修改任何后端文件**（核心算法与数据逻辑保持原样）。

---

## 14. Tests

| 命令 | 结果 |
| --- | --- |
| `pytest`（backend） | **285 passed / 0 failed / 0 errors** |
| `npm run build` | ✅ 通过（vue-tsc + vite） |
| `npm run test:rules` | **97 passed / 0 failed**（上一轮 74） |
| `npm test` | 新增别名 → `test:rules`（前端没有其他测试运行器） |

新增 23 项 source-contract 测试，覆盖任务书要求的：已登录用户权限一致、
ADMIN/DOCTOR 不影响普通 Route、侧栏无系统设置、侧栏无功能测试、登录页无角色、
页头无角色、功能卡手机单列、患者手机卡片、选择器手机卡片、钢琴触摸事件、
摄像头 `playsinline`、芭蕾音频由用户手势启动、断点统一、桌面流程不被破坏。

> 说明：这些是**源码断言**而非 DOM 测试。项目没有 jsdom / testing-library，
> 为这组检查引入它们比整个现有测试套件还重。它们能防住「有人把 `adminOnly` 加回来」
> 这类回归；不能验证行为——行为由 §15 的浏览器实测覆盖。

---

## 15. Responsive Manual Tests

13 个页面 × 7 个尺寸，实测 `document.documentElement.scrollWidth - window.innerWidth`：

| 页面 | 1440×900 | 1366×768 | 1024×768 | 768×1024 | 430×932 | 390×844 | 375×812 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Patients | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| PatientDetail | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| PatientForm | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AssessmentCenter | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Face | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Finger | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| TrainingCenter | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Piano | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Ballet | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| FollowUp | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Trends | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Report | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

单位为像素，**全部为 0：没有任何页面在任何尺寸下横向溢出。**

布局切换断言同时通过：`< 768px` 无桌面侧栏且有汉堡按钮；`>= 768px` 无汉堡按钮。

**交互实测（390×844）**

| 项目 | 结果 |
| --- | --- |
| 移动导航打开 | ✓ 5 项，条目高 44px |
| 移动导航关闭 | ✓ 点击条目后跳转且抽屉关闭 |
| 患者列表 | ✓ 10 张卡 / 0 可见表格；桌面 10 行 / 1 可见表格 |
| 患者选择器 | ✓ 10 张卡 / 0 可见表格；搜索框 352px（全宽）；卡片高 104px |
| 钢琴琴键 | ✓ 46×176px，可滚动，pointerdown 触发按键 |
| 钢琴横屏提示 | ✓ 竖屏出现，可关闭 |
| 芭蕾患者模式 | ✓ 侧栏 0、返回 40px、口令 30px、横屏提示、无溢出 |
| 手指敲击患者模式 | ✓ 侧栏 0、摄像头按钮 48px、无溢出 |
| 返回路径 | ✓ 退出后回到 `/training`，汉堡导航恢复 |
| 患者详情 / 表单 | ✓ 手机无溢出；表单标签改为顶部对齐 |

---

## 16. Remaining Issues

1. **面部表现分析的患者模式仍未实测。** 老师提供的模型未接入
   （`MODEL_NOT_CONFIGURED`），「开始检查」按钮按设计禁用，因此其焦点模式与手机
   相机流程没有跑通过。代码路径与手指敲击相同，但**没有实测证据**。
2. **触摸琴键的自动滚动未在真实提示流中验证。** 单键点击已实测；
   「提示音切换时琴键自动滚入视野」只在代码层面确认。
3. **平板侧栏默认折叠状态未在真实平板上验证。** 断点行为在浏览器模拟尺寸下验证，
   未在实体 iPad / Android 平板上跑过。
4. **iOS Safari 的 `playsinline` 未在真机验证。** 属性已设置并断言，
   但只在桌面 Chromium 与模拟视口下测试过。
5. **综合评估的 Stepper 仍未实现**（上一轮遗留）。手机上目前不溢出，
   但七步流程本身还没有。
6. **功能测试与 9-HPT 未实现**，入口已按本轮要求保持隐藏。
7. **趋势图仍无真实数据可画。** 演示库全部是种子/自检数据，按既有规则被排除，
   趋势页显示空状态；需要演示前用真人做两次以上真实测量。
8. **本轮发现的环境问题**：本机 8000 端口被另一个项目的进程占用，导致开发代理
   静默转发到别的应用、页面空数据而不报错。已把代理目标改为可用
   `VITE_DEV_BACKEND` 覆盖，并在 `vite.config.ts` 注释说明。**部署环境不受影响**
   （服务器上后端由 systemd 固定在 127.0.0.1:18086）。

---

## 17. Git

| 项 | 值 |
| --- | --- |
| Branch | `main` |
| `refactor: unify staff permissions and add the responsive foundation` | `d9390dd` |
| `feat: make the phone layouts usable rather than merely narrow` | `8adff6a` |
| `test: lock the permission, navigation and responsive decisions` | `3d62a1e` |
| `git status` | 干净 |
| 已推送 | `origin main` |
| 已部署 | `https://ccqspace.site/pd-rehab/` |
