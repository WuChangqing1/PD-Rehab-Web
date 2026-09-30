# UX Refactor 完成报告

> 2026-09-30 · `refactor: simplify navigation and patient workflows`
> 计划见 [`docs/ux_refactor_plan.md`](ux_refactor_plan.md)

---

## 1. 修改前主要问题

| # | 问题 | 证据 |
| --- | --- | --- |
| 1 | **过度 patient-first**：所有功能路由都是 `/patients/:id/...`，必须先找患者再进功能 | 见下表 |
| 2 | **侧栏随路由变化**：进入患者页后动态注入 6 个菜单项，导航结构不稳定 | `MainLayout.vue` 旧 `patientSections` |
| 3 | **功能有 4 个入口**：综合评估同时出现在侧栏、患者详情顶部、患者详情 Tab、患者列表行内 | 旧 `PatientsPage.vue:195`、`PatientDetailPage.vue:78,124` |
| 4 | **死入口**：患者详情历史表的「微表情 / Finger Tapping」按钮**不传 sessionId** | 旧 `PatientDetailPage.vue:152-157` → 落到"请从综合评估页进入" |
| 5 | **死按钮**：微表情「浏览器摄像头录制」无 click 处理，只写"将在 Phase 3 接入" | 旧 `MicroExpressionPage.vue:153-168` |
| 6 | **软删除无法恢复**：后端 `restore` 与前端 `patientApi.restore()` 都存在，列表却没有 `is_deleted` 与恢复按钮 | `PatientListItem` 缺字段 |
| 7 | **开发者信息泄露**：Phase 3/7/8、`MODEL_NOT_CONFIGURED`、`docs/model_integration.md`、feature schema 出现在医生页面 | 微表情页、患者详情 Tab、四个 placeholder 页 |
| 8 | **评估可无条件标记完成**：`complete_session()` 不检查任何子结果 | 旧 `assessment_service.py:130` |
| 9 | **Session 类型不约束内容**：`MICRO_EXPRESSION_ONLY` 可以接 Finger Tapping | 旧 `_assert_session_accepts()` 只判状态 |
| 10 | **免责声明重复**：`MainLayout` 已渲染，10 个子页面又各渲染一次 | 同屏出现两遍 |
| 11 | **技术参数占据患者页面**：训练入口页有 Pose 质量阈值表、3 个算法版本号、2 张历史表 | 旧 `TrainingPage.vue` |

---

## 2. 新导航结构（**固定，不再随路由变化**）

```text
工作台          /dashboard
患者档案        /patients
评估中心        /assessment
康复训练        /training
系统设置        /system/model-status     ← 仅 ADMIN 可见
```

- 「功能测试」「随访与报告」**暂不进入主导航**：其面板仍是占位，菜单不得指向开发说明。
  Route 保留，直接访问给出"该功能暂未开放"。
- 删除全部 patient-specific 动态菜单（患者详情 / 编辑资料 / 评估会话 / 微表情 / Finger
  Tapping / 训练入口 / 钢琴 / Pose / History / Trends）。

---

## 3. Function-first Flow

四个功能中心统一为 **功能 → 选择患者 → 开始**，共用 `PatientSelector` +
`SelectedPatientBar`：

| 中心 | 选择患者方式 | 选中后 |
| --- | --- | --- |
| **评估中心** `/assessment` | `PatientSelector`（姓名/编号搜索 + 最近使用） | 显示患者信息条 → 3 张评估方式卡片；若有未完成会话，先提示"继续 / 放弃" |
| **康复训练** `/training` | 同上 | 2 张训练卡片 + 钢琴基础测试状态 |
| **面部分析 / 手指敲击** | 页面自带选择器（直接访问时） | 自动创建或复用 Session |
| **随访与报告** `/follow-up` | 同上 | 时间轴 / 趋势 / 报告三个 Tab（前两个面板为未开放说明） |
| **钢琴 / 动作训练** | 页面自带选择器（直接访问时） | 进入患者操作模式 |

患者上下文写入 `?patientId=<uuid>`，页面可刷新、可分享。最近使用患者**只作为选择器里的快捷方式**，从不自动套用。

---

## 4. 删除的重复入口

| 功能 | 删除的入口 | 保留的唯一入口 |
| --- | --- | --- |
| 综合评估 | 患者列表行内「评估」；患者详情顶部「开始综合评估」；患者详情 Tab 内按钮 | 评估中心 |
| 康复训练 | 患者详情顶部「开始训练」；患者详情「康复训练」Tab | 康复训练 |
| 面部分析 | 侧栏（动态）；患者详情历史表按钮 | 评估中心 → 面部分析 |
| 手指敲击 | 侧栏（动态）；患者详情历史表按钮 | 评估中心 → 手指敲击评估 |
| 功能测试 | 侧栏（动态）；患者详情 Tab | 功能测试模块（暂未开放） |
| 历史 / 趋势 / 报告 | 侧栏 3 项 + 患者详情 2 个 Tab | 随访与报告（暂未开放） |
| 模型状态 | 侧栏对所有人可见 | 系统设置（仅 ADMIN） |

另删除：患者详情 4 个跳转型 Tab（康复训练 / 功能评估 / 长期趋势 / 报告）、
训练入口页的质量阈值表 / 算法版本 / 2 张历史表、`AssessmentPage.vue`（由 `AssessmentHubPage` 取代）。

---

## 5. Assessment 修改

**Session 由系统自动管理**：

| 医生选择 | 系统行为 |
| --- | --- |
| 综合评估 | 创建 `COMPREHENSIVE`，进入第一个模块 |
| 面部分析 | 复用同类型未完成会话，否则创建 `MICRO_EXPRESSION_ONLY` |
| 手指敲击评估 | 同上，`FINGER_TAPPING_ONLY` |

页面**不再出现** `sessionId` / `COMPREHENSIVE` / `IN_PROGRESS` 等概念。

**未完成会话显式处理**：进入评估中心先查 `status=IN_PROGRESS`，有则列出并给
「继续上次评估 / 放弃并开始新的」，不静默 `find()` 一条。

**完成条件校验（后端）**：`completion_readiness()` 按会话类型与当前可用模块计算：

| 项目 | 状态取值 |
| --- | --- |
| 面部分析 | `COMPLETED` / `PENDING`（模型可用但未做）/ `SKIPPED_MODEL_UNAVAILABLE`（模型未配置） |
| 左手 / 右手手指敲击 | `COMPLETED` / `PENDING` |

存在 `PENDING` 时 `complete` 返回 **409** 并附清单；被跳过项写入会话备注
（`[SKIPPED_MODEL_UNAVAILABLE]`），**不假装完成**。

**Session 类型约束（后端）**：`_assert_session_accepts(session, module)` 新增类型校验，
`MICRO_EXPRESSION_ONLY` 接 Finger Tapping 现在返回 409。

**患者一致性校验（前端）**：带 `sessionId` 时先 `GET` 会话取得真实 `patient_id` 与 URL 的
`patientId` 比对，不一致拒绝继续并提示"当前评估记录与所选患者不一致"。

---

## 6. Piano 修改

| 项 | 修改 |
| --- | --- |
| 患者来源 | 从 `route.params.id` 改为 `?patientId=`（params 作为旧链接回退） |
| 直接访问 | 无患者时渲染 `PatientSelector`，不再用空 id 调 API |
| 操作模式 | **已撤销隐藏侧栏**：所有页面统一保留侧栏（见 §14.1） |
| 基础测试命名 | 数据层仍叫 Calibration；UI 文案已是"基础能力测试"（训练入口页） |
| 页面返回 | 页面顶部新增「← 返回康复训练」，带 `?patientId=` 回训练入口 |
| 音源预加载 | 仅在选定患者后开始解码，且并发上限 4（原为挂载即并发 40+） |

**未完成**（见 §14）：Round 选择器仍在页面中、难度参数（BPM / 判定窗口 / 序列长度）
仍可编辑、结果区未做 Progressive Disclosure。

---

## 7. Pose 修改

| 项 | 修改 |
| --- | --- |
| 患者来源 | 改为 `?patientId=`，无患者时先选择 |
| 操作模式 | **已撤销隐藏侧栏**：所有页面统一保留侧栏（见 §14.1） |
| 重复入口 | 训练入口页的「最近动作训练记录」已删除（历史归随访与报告） |
| 录制 | 改为共享 `VideoCapturePanel`（摄像头 + 文件上传 + 预览 + 重拍） |
| 页面返回 | 页面顶部新增「← 返回康复训练」，带 `?patientId=` 回训练入口 |

**未完成**：§28 要求的 6 步 Step Flow 未实现，当前仍是单页；结果区未分层。

---

## 8. Patient 修改

| 项 | 修改 |
| --- | --- |
| **软删除恢复** | `PatientListItem.is_deleted`（后端 `_to_list_item` 返回 + 前端类型）→ 列表新增「状态」列；已删除行只显示「恢复 / 详情」，恢复后重新加载 |
| 标题 | 「患者管理」→「患者档案」 |
| 重复入口 | 删除行内「评估」按钮 |
| 患者详情 | 重写为**资料页**：基本资料 / 医疗资料 / 最近活动摘要；删除顶部两个跳转按钮与 4 个 Tab |
| Session Bug | 历史评估表的两个模块按钮删除，改为单个「查看本次评估」并**携带真实 `session.id`** |

---

## 9. Developer Information 迁移

| 原位置 | 内容 | 去向 |
| --- | --- | --- |
| 微表情页 | `MODEL_NOT_CONFIGURED`、`docs/model_integration.md`、模型路径 | 系统设置 → 模型状态；页面只留"当前暂不可用，请联系系统管理员" |
| 患者详情 3 个 Tab | "Phase 5/6/7/8 接入" | 已删除 |
| 4 个 placeholder 页 | `Phase 7` / `Phase 8` + 开发计划清单 | `PagePlaceholder` 重写为"该功能暂未开放"，无 roadmap |
| 训练入口页 | Pose 质量阈值表、算法版本号 | 已删除（阈值属系统/高级信息） |
| 模型状态页 | 原本对所有人可见 | 移入系统设置，**仅 ADMIN**（路由守卫 + 侧栏过滤） |
| Dashboard | 模型状态卡片的「查看详情」链接 | 仅 ADMIN 显示 |

**保留**：医疗免责声明、训练安全提示（头晕/疼痛请停止）、
"展示分公式未定义因此为空"的如实说明 —— 这些是诚实性要求，不是开发信息。

---

## 10. Route Compatibility

| 旧 Route | 新 Route |
| --- | --- |
| `/patients/:id/assessment` | `/assessment?patientId=:id` |
| `/patients/:id/assessment/micro-expression` | `/assessment/micro-expression?patientId=:id` |
| `/patients/:id/assessment/finger-tapping` | `/assessment/finger-tapping?patientId=:id` |
| `/patients/:id/training` | `/training?patientId=:id` |
| `/patients/:id/training/piano` | `/training/piano?patientId=:id` |
| `/patients/:id/training/movement` | `/training/movement?patientId=:id` |
| `/patients/:id/history` | `/follow-up?patientId=:id&tab=timeline` |
| `/patients/:id/trends` | `/follow-up?patientId=:id&tab=trends` |
| `/patients/:id/report` | `/follow-up?patientId=:id&tab=report` |
| `/patients/:id/functional-assessment` | `/functional-assessment?patientId=:id` |

`sessionId` / `tab` 一并透传。实测：`/patients/<id>/training/piano`
→ `/training/piano?patientId=<id>` ✓

---

## 11. 创建 / 修改文件

**新增（11）**
```
frontend/src/stores/patientContext.ts
frontend/src/components/PatientSelector.vue
frontend/src/components/SelectedPatientBar.vue
frontend/src/components/VideoCapturePanel.vue
frontend/src/components/PatientTaskLayout.vue
frontend/src/components/MetricSummaryCards.vue
frontend/src/pages/AssessmentHubPage.vue
frontend/src/pages/TrainingHubPage.vue
frontend/src/pages/FollowUpPage.vue
docs/ux_refactor_plan.md
docs/ux_refactor_report.md
```

**修改（12）**
```
frontend/src/router/index.ts
frontend/src/layouts/MainLayout.vue
frontend/src/stores/auth.ts
frontend/src/types/index.ts
frontend/src/api/index.ts
frontend/src/components/PagePlaceholder.vue
frontend/src/pages/MicroExpressionPage.vue
frontend/src/pages/PatientsPage.vue
frontend/src/pages/PatientDetailPage.vue
frontend/src/pages/DashboardPage.vue
frontend/src/pages/PianoTrainingPage.vue
frontend/src/pages/MovementTrainingPage.vue
backend/app/api/patients.py
backend/app/api/assessment_sessions.py
backend/app/schemas/patient.py
backend/app/services/assessment_service.py
backend/tests/test_assessment_sessions.py
```

**删除（5）**
```
frontend/src/pages/AssessmentPage.vue        （由 AssessmentHubPage 取代）
frontend/src/pages/HistoryPage.vue           （改为重定向）
frontend/src/pages/TrendsPage.vue            （改为重定向）
frontend/src/pages/ReportPage.vue            （改为重定向）
frontend/src/pages/FunctionalAssessmentPage.vue （改为"暂未开放"）
```

**未改动**：所有 `ml/` 算法、`utils/metrics.py`、`utils/piano_metrics.py`、
`ml/pose/metrics.py`、算法版本号、原始数据表结构。

---

## 12. Tests

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 后端 | `python -m pytest` | **285 passed, 0 failed**（新增 6：会话类型约束 ×3、完成条件 ×2、未完成列表 ×1） |
| 前端构建 | `npm run build` | **通过**（`vue-tsc -b` 无错误） |
| 规则引擎 | `npm run test:rules` | **25 passed** |

---

## 13. Screens / Manual Flow

| 场景 | 结果 |
| --- | --- |
| **A** 评估中心 → 搜索 → 选择患者 → 手指敲击 | ✅ 实测：侧栏 6 项；选择患者后信息条显示`吴国庆（虚拟）/ DEMO-0010 / 男·73岁 / 左侧 / ON`；三张方式卡片出现 |
| **B** 康复训练 → 选择患者 → 钢琴 | ⚠️ 部分：患者选择与跳转可用；Round 选择器与难度参数仍在（§14） |
| **C** 康复训练 → 选择患者 → 动作训练 | ✅ 患者选择、录制、分析可用（Step Flow 未做）；上传路径本批修复（§14.3） |
| **D** 随访与报告 → 选择患者 → 时间轴 | ✅ 患者选择与时间轴清单可用；趋势与报告面板显示"暂未开放" |
| 旧链接兼容 | ✅ `/patients/<id>/training/piano` → `/training/piano?patientId=<id>` |
| 患者列表 | ✅ 新增「状态」列；行内操作只剩 详情/编辑/删除；无「评估」按钮 |
| 免责声明 | ✅ 登录后全局只出现 1 次 |
| 侧栏稳定性 | ✅ **所有页面**（含钢琴、动作训练）都渲染侧栏，且恒为 6 项，不动态增减 |
| 页面返回 | ✅ 钢琴 / 动作训练 / 面部分析 / 手指敲击 / 患者详情 顶部都有带目的地的「← 返回 X」 |
| 结果分层（线上实测） | ✅ `ccqspace.site/pd-rehab/assessment/finger-tapping?patientId=…`：侧栏 6 项、「← 返回评估中心」、5 张摘要卡、「查看全部运动学指标」折叠；无结果时全部显示「暂无数据」而不是 0 |
| 动作训练录制区（线上实测） | ✅ 侧栏 6 项、「← 返回康复训练」、`VideoCapturePanel` 就位（1 个 file input、**0 个遗留 `el-upload`**）、按钮为「打开摄像头 / 选择视频文件」 |

---

## 14. 尚未实现功能（**不以 Placeholder 假装完成**）

**本轮（第二批）已补做：**

| 项 | 现状 |
| --- | --- |
| **§23 钢琴基础能力测试** | ✅ 数据层仍叫 Calibration；UI 已改为「基础能力测试」，无基线时给出"约 45 秒、用来测量患者自己的节奏"的说明，有基线时直接进入训练 |
| **§24 钢琴 Round 不允许手工选择** | ✅ 单选按钮已删除，改为只读的「第 N / 3 轮 · 难度由系统根据上一轮表现自动调整」；保存后自动推进并提示下一轮 |
| **§25 钢琴难度参数隐藏** | ✅ BPM / 判定窗口 / 序列长度 / 时长移入「高级设置（医生）」折叠区，**默认关闭**，并提示手工修改会写入审计 |
| **§26 钢琴模式选择用卡片** | ✅ 4 张卡片（单键节奏 / 左右手交替 / 按键序列 / 跟随节拍），各带一句中文说明；不再出现 `SINGLE_KEY_RHYTHM` 等内部名 |
| **§19 Finger Tapping 患者优先** | ✅ 页面自带患者选择器、自动创建/复用 `FINGER_TAPPING_ONLY` 会话、顶部显示当前患者、会话与患者一致性校验；「请先在综合评估页创建会话」死路已删除 |
| **§39 统一摄像头组件** | ⚠️ **上一批只做了两处，报告写错了**。微表情 / 手指敲击确实用了 `VideoCapturePanel`；动作训练页仍保留自己那套摄像头 + `el-upload`，见 §14.3（本批已修） |
| **§38 错误提示分两层** | ✅ 新增 `utils/errors.ts`：把 `HAND_NOT_DETECTED` 等映射为"没有检测到完整手部，请让手部完全进入画面后重新录制"；原始 code 只进 console |
| **§20 Finger Tapping 结果分层** | ✅ 本批完成：默认 5 张摘要卡（左右手敲击频率 / 节奏稳定性 / 动作幅度 / 中断次数），11 行指标表折叠进「查看全部运动学指标」 |
| **§27 钢琴结果分层** | ✅ 本批完成：默认 4 张摘要卡（准确率 / 平均反应延迟 / 平均节拍误差 / 左右手延迟差），14 项 P0 指标与算法说明折叠进「查看全部训练指标」 |
| **§29 Pose 结果分层** | ✅ 代码完成：默认 4 张摘要卡（完成次数 / 抬起角度 / 动作速度 / 左右差异），10 项原始指标折叠。**未用"通过门限"的真实结果截图验证**（见 §14.3） |
| **§31 趋势 / 报告面板** | ✅ 本批完成，见 §14.4。「随访与报告」因此重新出现在侧栏（侧栏从 5 项变 6 项） |
| **训练卡片对齐** | ✅ 用户反馈后修复，见 §14.5 |

**仍未实现：**

| 项 | 现状 |
| --- | --- |
| **§13 综合评估 Stepper（el-steps 七步）** | 未实现。当前是"创建会话 → 跳到第一个模块"，没有步骤条与"上一步/下一步" |
| **§28 Pose 六步 Step Flow** | 未实现，仍是单页 |
| **§32 功能测试（9-HPT）** | 未实现 |
| **§36 患者表单 Progressive Disclosure** | 未实现，字段仍一次展开 |
| **§22 患者模式视觉规格** | **用户已否决"隐藏侧栏"这一条**：改为所有页面保留侧栏（§14.1）。仍要做的是把 ≥44px 按钮 / ≥16px 正文 的规格落到钢琴与动作训练页 |

### 14.1 用户反馈变更：撤销焦点模式（本批）

用户原话："现在进入钢琴和动作之后没有退出的按钮，我想的是所有的页面都应该有侧边栏"。

隐藏侧栏的原意是"患者在屏幕前需要的是任务而不是导航"，实测结果相反：页面没有任何退出口，
患者和医生都只能按浏览器后退键。结论是**撤销焦点模式**，改为：

| 项 | 变更 |
| --- | --- |
| `MainLayout.vue` | 删除 `v-if="route.meta.focusMode"` 分支，唯一布局就是"侧栏 + 顶栏 + 内容" |
| `router/index.ts` | 移除钢琴 / 动作训练路由上的 `meta.focusMode`（不再有这段配置） |
| `styles/main.css` | 新增 `.pd-back` 工具类（≥40px 点击区、hover/focus 可见、写清目的地） |
| 钢琴 / 动作训练 | 顶部加「← 返回康复训练」，携带 `?patientId=` |
| 面部分析 / 手指敲击 | 顶部加「← 返回评估中心」，携带 `?patientId=` |
| 患者详情 | 顶部加「← 返回患者档案」 |

`PatientTaskLayout.vue` 从未被任何页面引用（仓库中不存在该文件），因此无需删除。

### 14.2 顺带修掉的真实缺陷：钢琴音源预加载拥塞

验证侧栏时发现：`/training/piano` 打开后患者列表长时间空白。实测 `GET /api/patients`
在浏览器里耗时 **86173 ms**（直连后端 4 ms）。

原因不在后端：`PianoTrainingPage` 在 `onMounted` 无条件调用 `runner.warmUp()`，
而 `PianoEngine.load()` 用 `Promise.all` 一次性发起约 40 个 mp3 请求，占满浏览器每域
6 条连接，把同一页面的 API 请求排在队尾（控制台可见大量 `ERR_CONNECTION_RESET`）。

修复：

| 文件 | 变更 |
| --- | --- |
| `piano/engine.ts` | `SAMPLE_FETCH_CONCURRENCY = 4`，用 4 个 worker 轮流取队列，不再无条件 `Promise.all` |
| `pages/PianoTrainingPage.vue` | `warmUp()` 改为 `watch(hasPatient, …, { immediate: true })`：选定患者后才开始解码 |

修复后同一页面患者列表立即渲染（10 条）。

### 14.3 顺带修掉的第二个真实缺陷：动作训练的上传一直是坏的

上一批报告写了「§39 三处全部改用 `VideoCapturePanel`」，**动作训练页并没有改**。
它仍保留自己那套「打开摄像头 / 开始录制 / `el-upload`」代码，而 `el-upload` 的
`:on-change` 回调收到的是 Element Plus 的 `UploadFile` 对象，页面里的

```ts
function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement   // ← event.target 是 undefined
  const file = input.files?.[0]
```

把它当 DOM 事件用。实测点击「选择视频文件」后控制台抛
`TypeError: Cannot read properties of undefined (reading 'files')`，
`recordedBlob` 永远为 null，**「上传并分析」按钮永远禁用**——动作训练的上传入口是死的。

修复（§39 真正落地）：

| 文件 | 变更 |
| --- | --- |
| `pages/MovementTrainingPage.vue` | 删除自建摄像头 / 录制 / `el-upload` 代码块（约 78 行）与 `onFilePicked`，改用 `VideoCapturePanel` + `onClipChange`；`重来` 通过组件暴露的 `clear()` 一并清空预览 |
| 同上 | 删除随之失效的 `useCameraCapability` 引用、`Upload`/`VideoCamera`/`VideoPlay` 图标、`pickRecordingFormat`/`recordingFilename`、`cameraOn`/`recording`/`cameraError`/`recordedUrl`/`recordedSeconds`/`videoEl` 等死代码 |

验证（本地 dev，患者 吴国庆）：

| 步骤 | 结果 |
| --- | --- |
| 选择动作 → 选择视频文件 | ✅ 「上传并分析」由禁用变为可用，预览 `<video>` 正常渲染（修复前抛 TypeError） |
| 点击「上传并分析」 | ✅ 走通服务端分析，返回 `NO_MOVEMENT_DETECTED`，页面按「未通过质量控制」分支展示：门限名 + 实测「有效帧 45 / 45，时长 3.0 秒」+ 重录建议 |
| **未验证** | 通过门限后的**摘要卡分支**没有拿到真实通过样本：本地库中「通过门限且有视频文件」的会话数为 0。该分支与已实测的手指敲击结果区共用同一组件与同一写法，但**没有实际看到渲染结果，因此不算已验证** |

> 用于验证的是一条脚本合成视频，分析后本地库把它记成了 `input_source=HUMAN_KEYBOARD`。
> 这是错误的来源标记，已把该 `pose_session`、对应 `media_files` 行与磁盘文件一并删除
> （`pose_sessions` 59 行，与验证前一致）。

> §20 / §27 / §29 的"结果分层"是同一类工作（默认摘要 + 折叠详细），本批已一次性统一处理，
> 没有三处各写一遍。

### 14.4 §31 趋势 / 报告：只画真人的测量值

「随访与报告」此前三个面板全是占位，所以侧栏一直没有这一项。本批把趋势与报告做成真的，
侧栏随之变成 6 项。

**核心规则：训练表里同时躺着真人记录、`SYNTHETIC_SELFTEST`（`?selftest=1` 脚本自检）与
`SEED_DEMO`（演示种子）。把三者画进同一条线，会显示患者从未产生过的趋势，因此趋势图一律
排除非真人记录，并把排除条数写在页面上。**

| 新增/修改 | 说明 |
| --- | --- |
| `src/followup/trends.ts` | 纯函数：按「只要有时间戳、有数值、且来源是真人」筛点，按时间升序；同时统计被排除/缺值/缺时间的条数，并保留各点算法版本 |
| `src/followup/trendOption.ts` | 纯函数：按算法版本分组折线。**不同版本的点不会连成一条线**；单点不画成线 |
| `src/components/TrendChart.vue` | ECharts 折线；只有一个点时显示为点而非线 |
| `src/pages/FollowUpPage.vue` | 趋势页 12 个指标（钢琴 4 / 动作 4 / 手指敲击 4）；报告页列出各模块「最近一次 / 上一次 / 可用点数」 |
| `GET /patients/{id}/finger-tapping-results` | 新增后端端点，一次返回该患者全部手指敲击结果（原来只能按会话逐个查） |
| `frontend/tests/trends.test.ts`、`trend_option.test.ts` | 22 个新测试，锁住上述规则（`npm run test:rules` 现为 47 个） |

**报告页明确不做的事**：不输出综合评分、严重程度分级、病情变化百分比，也不把面部分析的
表情标签占比算进来（它表示面部运动表现维度，不代表疾病严重程度）。

#### 14.4.1 过程中发现并修掉的两个「数字不诚实」问题

**一、`finger_tapping_results` 没有来源列。** 我最初想当然地把它当成一定是真人录制，
但本地库里唯一一行来自 `backend/tests/fixtures/finger_tapping_sample.mp4`——**是测试夹具**。
把它当患者数据画上去就是编造趋势。

处理：新增迁移 `d7e2b4c8a1f3` 给该表加 `input_source`，**默认值取 `UNLABELLED` 而不是
`HUMAN_KEYBOARD`**，这样忘记声明来源的代码路径会「失败得安全」（被排除），而不是悄悄冒充
患者数据。**已存在的行一律留在 `UNLABELLED`**：它们的来源确实无法判定，猜真人或猜种子都是
编造。分析服务在真实上传路径上显式写入 `HUMAN_KEYBOARD`。

**二、我自己写的排除条数是错的。** 第一版把各图表的排除数相加，页面显示「已排除 74 条
非真人记录」——一条记录会喂给 4 个指标图，所以这个数字被放大了约 4 倍。**虚高的数字同样是
错误数字。** 改为按记录去重统计，现在显示「已排除 24 条（钢琴 14、动作训练 9、手指敲击 1）」。
缺值/缺时间仍按「（记录 × 指标）组合」计数，并在文案里写明是组合数。

#### 14.4.2 演示库的现实：趋势页目前是空的

本地与服务器演示库里的钢琴/动作记录全部是 `SEED_DEMO` 与 `SYNTHETIC_SELFTEST`，
所以排除之后**没有任何可画的点**，趋势页会显示空状态。这不是 bug，是规则生效的结果
（页面同时显示排除了多少条、以及为什么）。

**要让演示有曲线，需要在演示前用真人做几次真实测量**（例如真人按键完成 3 轮钢琴、
真人录 2 次手指敲击）。系统不提供也不应该有「生成假真人数据」的开关，`?selftest=1` 产出的
记录会被正确标记为 `SYNTHETIC_SELFTEST` 并排除在趋势之外。

**未验证**：本批没有真人测量数据，因此**折线图实际渲染出的曲线没有亲眼验证过**。
该分组的正确性由 `trend_option.test.ts` 直接测试（版本不合并、单点不连线），
但「画出来长什么样」没有截图证据。

### 14.5 用户反馈：训练卡片没有对齐

用户指出 `training?patientId=…` 上两张训练卡片没有对齐。实测确认：两张卡片本身等高等宽，
但按钮位置差了 48px（钢琴卡 405、动作卡 357）——卡片是 flex 纵向排列且按钮紧跟正文，
钢琴卡多一行说明就把按钮压下去了。

修复：按钮 `margin-top: auto` 钉在卡片底部；两张卡片都补一行等高的说明行；标签
`flex: none` 不再挤压标题。修复后两张卡片高 282，按钮均在 432–480，完全对齐
（有无基础能力测试两种状态都验证过）。

---

## 15. Git

| 项 | 值 |
| --- | --- |
| Branch | `main` |
| 本批提交 | `ab36649` 侧栏常驻 + 返回链接 → `4964457` 返回链接 40px → `9b96c00` 结果分层 + 动作训练上传修复 → `2eccd16` 训练卡片对齐 → 本批文档提交 |
| 已推送 | `origin main` |
| 已部署 | `https://ccqspace.site/pd-rehab/`，5 个既有站点/服务均未受影响 |

**仓库卫生**：`4964457` 误把 4 MB 的 `_deploy/pd-rehab.bundle` 提交并推送了。
已删除该文件并忽略 `_deploy/`，**它仍留在 git 历史里**；用户已确认不做历史改写。
