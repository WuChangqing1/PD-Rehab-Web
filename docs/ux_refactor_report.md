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
| 操作模式 | 路由 `meta.focusMode` → `MainLayout` 不渲染侧栏，只留页面本身 |
| 基础测试命名 | 数据层仍叫 Calibration；UI 文案已是"基础能力测试"（训练入口页） |

**未完成**（见 §14）：Round 选择器仍在页面中、难度参数（BPM / 判定窗口 / 序列长度）
仍可编辑、结果区未做 Progressive Disclosure。

---

## 7. Pose 修改

| 项 | 修改 |
| --- | --- |
| 患者来源 | 改为 `?patientId=`，无患者时先选择 |
| 操作模式 | `focusMode` 生效，隐藏侧栏 |
| 重复入口 | 训练入口页的「最近动作训练记录」已删除（历史归随访与报告） |
| 录制 | 改为共享 `VideoCapturePanel`（摄像头 + 文件上传 + 预览 + 重拍） |

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
| **A** 评估中心 → 搜索 → 选择患者 → 手指敲击 | ✅ 实测：侧栏 5 项；选择患者后信息条显示`吴国庆（虚拟）/ DEMO-0010 / 男·73岁 / 左侧 / ON`；三张方式卡片出现 |
| **B** 康复训练 → 选择患者 → 钢琴 | ⚠️ 部分：患者选择与跳转可用；Round 选择器与难度参数仍在（§14） |
| **C** 康复训练 → 选择患者 → 动作训练 | ✅ 患者选择、录制、分析可用（Step Flow 未做） |
| **D** 随访与报告 → 选择患者 → 时间轴 | ✅ 患者选择与时间轴清单可用；趋势与报告面板显示"暂未开放" |
| 旧链接兼容 | ✅ `/patients/<id>/training/piano` → `/training/piano?patientId=<id>`，患者操作模式隐藏侧栏 |
| 患者列表 | ✅ 新增「状态」列；行内操作只剩 详情/编辑/删除；无「评估」按钮 |
| 免责声明 | ✅ 登录后全局只出现 1 次 |
| 侧栏稳定性 | ✅ 进入患者相关页面后仍为 5 项，不动态增加 |

---

## 14. 尚未实现功能（**不以 Placeholder 假装完成**）

| 项 | 现状 |
| --- | --- |
| **§13 综合评估 Stepper（el-steps 七步）** | 未实现。当前是"创建会话 → 跳到第一个模块"，没有步骤条与"上一步/下一步" |
| **§20 Finger Tapping 结果分层** | 未实现。页面结构未改，仍是单层展示 |
| **§22–27 钢琴患者模式** | 部分：focusMode 隐藏侧栏已完成；**Round 选择器、BPM/判定窗口/序列长度编辑器仍在**，"基础能力测试"命名与自动流程未改 |
| **§28 Pose 六步 Step Flow** | 未实现，仍是单页 |
| **§29 Pose 结果分层** | 未实现 |
| **§31 随访与报告的趋势 / 报告面板** | 未实现，显示"暂未开放"（如实说明，非 roadmap） |
| **§32 功能测试（9-HPT）** | 未实现 |
| **§36 患者表单 Progressive Disclosure** | 未实现，字段仍一次展开 |
| **§38 错误码到人话的映射层** | 仅部分完成（面部分析的 `MODEL_NOT_CONFIGURED`）；Finger Tapping 的 QC 错误码未映射 |
| **§44 共享组件** | 已完成 5 个；`AssessmentStepper.vue` / `AdvancedMetrics.vue` 未创建（无使用方） |

---

## 15. Git

| 项 | 值 |
| --- | --- |
| Branch | `main` |
| Commit | 见提交后输出 |
| `git status` | 见提交后输出 |
