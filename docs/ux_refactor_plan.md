# UX / 信息架构重构计划

> 版本：v1.0.0 · 2026-09-29
> 范围：`frontend/src` 全部页面与导航、`backend` 的患者列表 / 评估会话约束。
> **不涉及**：Finger Tapping、Piano、Pose 的任何公式、指标定义、模型 Adapter、原始数据存储。

---

## 0. 一句话目标

当前系统是**以数据库关系为中心**的：`patient → assessment_session → module`。
重构后是**以医生任务为中心**的：**先选功能 → 再选患者 → 开始**。

---

## 1. 现状盘点（修改前）

### 1.1 现有入口清单

| 入口 | 位置 | 患者从何而来 |
| --- | --- | --- |
| 工作台 | Sidebar `/dashboard` | — |
| 患者管理 | Sidebar `/patients` | — |
| 患者详情 | Sidebar（**动态注入**）`/patients/:id` | URL param |
| 综合评估 | Sidebar（动态）+ 患者详情顶部按钮 + 患者列表"评估"按钮 | URL param |
| 康复训练 | Sidebar（动态）`/patients/:id/training` | URL param |
| 功能评估 | Sidebar（动态）+ 患者详情 Tab | URL param |
| 历史记录 | Sidebar（动态） | URL param |
| 长期趋势 | Sidebar（动态）+ 患者详情 Tab | URL param |
| 微表情 | 患者详情历史表按钮 + 评估页内部按钮 | `?sessionId` |
| Finger Tapping | 患者详情历史表按钮 + 评估页内部按钮 | `?sessionId` |
| 钢琴训练 | 训练入口页卡片 | URL param |
| 动作训练 | 训练入口页卡片 | URL param |
| 报告 | 患者详情 Tab | URL param |
| 模型状态 | Sidebar `/system/model-status` | — |

### 1.2 重复入口（同一功能出现在 ≥2 处）

| 功能 | 出现位置 | 数量 |
| --- | --- | --- |
| 综合评估 | Sidebar「当前患者」组 / 患者详情顶部「开始综合评估」/ 患者详情「最近评估」Tab 内按钮 / 患者列表行内「评估」 | **4** |
| 微表情 | 患者详情「最近评估」行内按钮 / 综合评估页「评估模块入口」 | 2 |
| Finger Tapping | 同上 | 2 |
| 康复训练 | Sidebar / 患者详情顶部「开始训练」/ 患者详情「康复训练」Tab 内按钮 | **3** |
| 功能评估 | Sidebar / 患者详情「功能评估」Tab 内按钮 | 2 |
| 长期趋势 | Sidebar / 患者详情「长期趋势」Tab 内按钮 | 2 |
| 报告 | 患者详情「报告」Tab | 1 |

### 1.3 死入口 / 断头路

| 问题 | 证据 |
| --- | --- |
| 微表情页直接访问时提示"未指定评估会话，请从综合评估页进入" | `MicroExpressionPage.vue:181` |
| 患者详情历史表「微表情 / Finger Tapping」按钮**不传 `row.session.id`** | `PatientDetailPage.vue:152-157`（`go()` 只带 patient id），点击后 `sessionId` 缺失，必然走到上面的死路 |
| 微表情「浏览器摄像头录制」按钮**没有任何 click 处理**，只写"将在 Phase 3 接入" | `MicroExpressionPage.vue:153-168` |
| Finger Tapping 页面文案写"录制 10–20 秒 / 3 秒倒计时"，实际只有文件上传 | `FingerTappingPage.vue` |
| 软删除患者**无法恢复**：后端 `POST /patients/{id}/restore` 与前端 `patientApi.restore()` 都存在，但列表没有 `is_deleted` 列与恢复按钮 | `PatientsPage.vue`（`PatientListItem` 也缺字段） |

### 1.4 用户路径（修改前）

```text
要评估 → 患者管理 → 找患者 → 患者详情 → 找到「最近评估」Tab
       → 新建综合评估 → 回到评估页 → 创建 Session → 选模块 → 做 → 标记完成
要训练 → 患者管理 → 找患者 → 患者详情 → 开始训练 → 训练入口 → 选模块
```

每一步都要记住"我在哪个患者里"。侧栏还会随患者页面**变长**，医生失去位置感。

### 1.5 开发者信息泄露到用户页面

| 出现位置 | 内容 |
| --- | --- |
| 微表情页 | `MODEL_NOT_CONFIGURED`、`docs/model_integration.md`、"老师团队的模型" |
| 患者详情 3 个 Tab | "Phase 5 / Phase 6 接入"、"Phase 7 接入"、"Phase 8 接入" |
| 功能评估 / 历史 / 趋势 / 报告 页 | `PagePlaceholder` 整页显示 `Phase 7` / `Phase 8` 与开发计划清单 |
| Finger Tapping 页 | 严重度模型缺失的大段黄色警告、algorithm version、feature schema 说明 |
| 动作训练页 | "服务端 MediaPipe 逐帧提取 33 个关键点"、"公式未定义"、质量阈值表 |
| 训练入口页 | Pose 质量阈值表、算法版本、两套 History 表、规则引擎版本号 |
| 模型状态页 | 本身即技术页，但挂在主 Sidebar 对所有角色可见 |

---

## 2. 目标信息架构

### 2.1 固定主导航（**不再随路由变化**）

```text
工作台
患者档案
评估中心
康复训练
随访与报告
系统设置          ← 仅 ADMIN 可见
```

- 侧栏**完全静态**：删除 `patientSections` 动态注入。
- 「功能测试」当前只有 placeholder → **不进入主导航**（§32 规则）。
- 「随访与报告」内部为 Tabs（时间轴 / 趋势 / 报告），三个子页当前均为 placeholder →
  主导航**暂不显示**，Route 保留，直接访问给出"该功能暂未开放"。

### 2.2 新 Route

| 主入口 | 内部流程 Route（**不进 Sidebar**） |
| --- | --- |
| `/assessment` | `/assessment/micro-expression`、`/assessment/finger-tapping` |
| `/training` | `/training/piano`、`/training/movement` |
| `/functional-assessment` | — |
| `/follow-up` | — |
| `/system/model-status`（ADMIN） | — |

患者上下文用 **query** 携带：`?patientId=<uuid>`（必要时再加 `&sessionId=<uuid>`），
页面可刷新、可分享。

### 2.3 患者选择

所有功能中心统一使用：

1. `PatientSelector.vue` —— 搜索（姓名 / 编号 / 电话）、显示姓名·编号·年龄·受累侧·用药状态。
2. `SelectedPatientBar.vue` —— 固定显示"当前患者：姓名 / 编号 / 性别·年龄 / 受累侧 / 用药状态
   + 更换患者"。**不允许患者身份只存在于 URL 里**。
3. `stores/patientContext.ts` —— 记录最近使用患者，**仅作为默认建议**。

### 2.4 患者操作模式（Focus Mode）

医生选定「功能 + 患者」并开始后进入：

- 隐藏 Sidebar 与后台导航；
- 顶部只有：`← 退出`、当前患者、当前任务；
- 正文 ≥16px、主按钮 ≥44px（训练核心按钮 ≥48px）。

---

## 3. 逐项处理清单

| # | 处理 | 动作 |
| --- | --- | --- |
| 1 | 侧栏动态注入 | **删除**，改为静态六大项 |
| 2 | 患者列表「评估」按钮 | **删除**（评估唯一入口是评估中心） |
| 3 | 患者详情顶部「开始综合评估 / 开始训练」 | **删除** |
| 4 | 患者详情 Tabs：康复训练 / 功能评估 / 长期趋势 / 报告 | **删除**（跳转型 Tab） |
| 5 | 患者详情历史表两个模块按钮 | **删除**，改为单个「查看详情」并携带真实 `sessionId` |
| 6 | 评估类型里的 `FUNCTIONAL_TEST` | **从评估中心移除**，功能测试独立成模块 |
| 7 | 训练入口页的质量阈值表 / 算法版本 / 两张 History 表 | **删除**（阈值 → 系统；历史 → 随访） |
| 8 | 微表情页摄像头死按钮 | **实现**真正的录制（与 Finger/Pose 共用 `VideoCapturePanel`） |
| 9 | Finger Tapping 录像文案与能力不一致 | **实现**录制后统一由 `VideoCapturePanel` 承担 |
| 10 | 各页重复的 `<MedicalDisclaimer />` | 保留 `MainLayout` 一处全局；子页删除 |
| 11 | `PagePlaceholder` 的 Phase 文案 | 改为"该功能暂未开放" |
| 12 | 模型状态 | 移入「系统设置」，仅 ADMIN |
| 13 | 软删除恢复 | 补 `is_deleted` 字段 + 状态标签 + 恢复按钮 |

---

## 4. 必须保留的内部 Route

以下 Route **不删**（兼容旧书签 / Demo 链接），只做 Redirect：

```text
/patients/:id/assessment                → /assessment?patientId=:id
/patients/:id/assessment/micro-expression → /assessment/micro-expression?patientId=:id
/patients/:id/assessment/finger-tapping   → /assessment/finger-tapping?patientId=:id
/patients/:id/training                  → /training?patientId=:id
/patients/:id/training/piano            → /training/piano?patientId=:id
/patients/:id/training/movement         → /training/movement?patientId=:id
/patients/:id/trends                    → /follow-up?patientId=:id&tab=trends
/patients/:id/history                   → /follow-up?patientId=:id&tab=timeline
/patients/:id/report                    → /follow-up?patientId=:id&tab=report
/patients/:id/functional-assessment     → /functional-assessment?patientId=:id
/patients/:id                           → 保留（患者资料不是功能入口）
```

旧 Route 带 `sessionId` 时转换为 query 参数继续传递。

---

## 5. 后端允许的修改（**不动 ML**）

| # | 修改 | 原因 |
| --- | --- | --- |
| B1 | `PatientListItem.is_deleted` + `_to_list_item()` 返回 | 恢复流程缺失 |
| B2 | `_assert_session_accepts()` 增加 **session_type 约束** | `MICRO_EXPRESSION_ONLY` 目前可以接 Finger Tapping |
| B3 | 综合评估**完成条件校验** | 当前可无条件标记完成 |
| B4 | 未完成会话列表接口（按患者 + 状态） | 评估中心需要让医生显式选择"继续 / 放弃" |
| B5 | 会话与患者一致性校验所需字段（`GET /assessment-sessions/{id}` 已有） | 防 URL 患者 A + Session 患者 B |

明确**不做**：ML 特征公式、指标定义、Adapter 接口、原始数据表结构、算法版本号。

---

## 6. 验证

```bash
cd backend && python -m pytest
cd frontend && npm run build && npm run test:rules
```

外加 4 个手工场景（见 `docs/ux_refactor_report.md` §13）。
