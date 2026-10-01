# UX + 芭蕾康复重构 · 审计与执行计划

版本：v1.0.0
日期：2026-10-01
范围：`PD-Rehab-Web` 现有代码的产品结构、导航、交互、用户文案、动作体系
**不在范围内**：Finger Tapping 数学公式、CV / Slope 定义、钢琴 Timing Error / Response
Latency 定义、自适应规则核心、Pose 原始角度计算、老师模型 Adapter、算法版本号、Raw Data 存储。

---

## 0. 审计方法

1. 遍历 `frontend/src/**/*.vue` 与 `*.ts`，剥离注释后按 70 个敏感词逐行匹配，得到「普通用户
   可能在界面上看到的研发/Demo/科研文案」清单。
2. 遍历 `backend/app/**` 的 API 与 schema，确认哪些字符串会经由接口进入前端。
3. 逐个检查 `router/index.ts` 的路由与 `MainLayout.vue` 的侧栏，找出同一功能的多个入口。
4. 检查 `pages/` 下是否存在 router / components / api 均不再引用的旧页面。
5. 检查 Pose 动作定义、指标引擎与前端动作展示，评估「瑜伽 → 芭蕾」的改动面。

---

## 1. 当前用户会看到的不合理内容

### 1.1 全局

| 位置 | 当前文案 | 问题 |
| --- | --- | --- |
| `components/MedicalDisclaimer.vue` | 「本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。」 | 每个登录页面底部都出现。医生/患者界面的产品免责声明，按要求删除 |
| `MainLayout.vue` | 同上，渲染一次 | 组件删除后一并移除 |

### 1.2 工作台 `DashboardPage.vue`

| 行 | 内容 | 处理 |
| --- | --- | --- |
| 76-77 | `title="DEMO DATA：当前处于 Mock 模式"` / `description="DEMO_MOCK_MODE=true，页面数据可能包含演示用模拟结果…"` | Mock 开启时才显示，但**医生界面不应出现 DEMO/Mock 字样** → 移到系统设置 |
| 36-37 | `MediaPipe Hand Landmarker` / `MediaPipe Pose` 模型名 | 技术信息 → 移到系统设置；工作台只显示「可用 / 不可用」 |
| 入口卡片 | 工作台是否还有「开始评估 / 开始训练」等按钮 | 与评估中心、康复训练重复 → 删除，只留概览 |

### 1.3 系统设置 `ModelStatusPage.vue`（本就是 ADMIN 页，允许保留技术信息）

`PyTorch 已安装` / `Mock 模式` / `mediapipe_hand_landmarker` / `展示分公式未定义` 等保留在此页。
需要确认：该页**仅 ADMIN 可见**（当前路由守卫已按 `auth.isAdmin` 过滤侧栏 + 守卫拦截）。

### 1.4 患者相关

| 位置 | 当前 | 处理 |
| --- | --- | --- |
| 患者列表 / 详情 / 选择器 | 姓名带「（虚拟）」后缀（来自种子数据 `name` 字段本身） | UI 显示时剥离后缀；**数据库不动** |
| `PatientFormPage.vue:123` | 「请使用虚拟或脱敏资料。系统不存储身份证号…」 | 改写为不出现「虚拟」的说明 |
| `PatientFormPage.vue:139` | `placeholder="虚拟姓名"` | 改为「患者姓名」 |
| `PatientFormPage.vue:192` | `临床诊断日期` | 「临床」为医学术语但医生可读，保留 |

### 1.5 评估中心

| 位置 | 当前 | 处理 |
| --- | --- | --- |
| `AssessmentHubPage` | 卡片标题「综合评估 / 面部分析 / 手指敲击评估」 | 「面部分析」→「面部表现分析」（§16） |
| `MicroExpressionPage` | 标题「面部分析」 | →「面部表现分析」 |
| 模型不可用时 | 显示 `MODEL_NOT_CONFIGURED` 等 code | → 只说「面部分析当前暂不可用」 |

### 1.6 训练相关

| 位置 | 当前 | 处理 |
| --- | --- | --- |
| `TrainingHubPage` | 「动作 / 简单瑜伽训练」 | →「芭蕾动作训练」 |
| `MovementTrainingPage` | 标题「动作训练（Pose）」 | →「芭蕾动作训练」；去掉 Pose |
| `PianoTrainingPage` | 自检模式 alert「自检模式：本轮按键由脚本合成…`input_source=SYNTHETIC_SELFTEST`」 | 仅 `?selftest=1` 时出现，属开发入口；保留但降级为不暴露内部枚举名，或改为开发者提示 |
| `PianoTrainingPage` | 「算法版本」段落、`driver` 说明 | 折叠进高级设置（医生） |

### 1.7 随访报告

| 位置 | 当前 | 处理 |
| --- | --- | --- |
| `FollowUpPage` 趋势页 | 「趋势图只画真人的测量值 / 已排除 24 条非真人记录（钢琴 14…）」 | 数据清洗在后台做，医生只看结果 → 删除该 alert |
| `FollowUpPage` 趋势页 | 「跨算法版本」警告 | 同上，删除 |
| `FollowUpPage` 时间轴 | 「来源」列显示「非真人数据」标签 | 普通 UI 删除该列 |
| `FollowUpPage` 报告页 | 页脚「已排除非真人记录…来源未标注…」 | 删除 |

> **重要**：这些规则本身是正确的（防止把种子数据画成患者趋势），删除的只是**展示**。
> 过滤逻辑保留在 `src/followup/trends.ts` 中，前端仍在数据层排除非真人记录，只是不再向
> 医生解释这件事。若将来需要可追溯性，可在报告导出或管理员页恢复。

### 1.8 错误提示

`utils/errors.ts` 已把多数 code 映射成人话，需补齐：`MODEL_NOT_CONFIGURED` →
「面部分析当前暂不可用。」、`CAMERA_PERMISSION_DENIED` → 「无法使用摄像头，请允许浏览器访问
摄像头，或上传已有视频。」

### 1.9 占位页

`PagePlaceholder.vue`「该功能暂未开放 / 这个模块还在开发中」——只允许出现在**已隐藏入口**的
页面上（功能测试）。不属于正式导航可达页面。

---

## 2. 重复入口清单

| 功能 | 当前入口 | 目标 |
| --- | --- | --- |
| 新增患者 | 患者档案页按钮 | 患者档案（唯一） |
| 编辑患者 | 患者列表行内 + 患者详情页 | 保留两处但都属「患者档案」内部操作，不算跨模块重复 |
| 综合评估 | 评估中心卡片 | 评估中心 |
| 面部分析 | 评估中心卡片；患者详情历史表按钮 | 评估中心 |
| 手指敲击 | 评估中心卡片；患者详情历史表按钮 | 评估中心 |
| 钢琴 | 康复训练卡片 | 康复训练 |
| 动作/瑜伽 | 康复训练卡片 | 康复训练（改名芭蕾） |
| 历史 / 趋势 / 报告 | 侧栏「随访与报告」+ 患者详情 Tabs | 随访报告 |
| 模型状态 | 侧栏「系统设置」（ADMIN） | 系统设置 |
| 功能测试 | 路由 `functional-assessment` 可达 | 侧栏无入口；路由重定向到工作台 |

需逐页确认 Dashboard 与 PatientDetail 不再形成「第二套菜单」。

---

## 3. 死页面 / 无引用页面

待全局搜索确认后处理（不得盲删）：

| 文件 | 状态 | 处理 |
| --- | --- | --- |
| `pages/TrainingPage.vue` | `/training` 已改用 `TrainingHubPage` | 搜索引用后删除 |
| `pages/HistoryPage.vue` | 已改为重定向桩 | 保留桩或删除后改路由重定向 |
| `pages/TrendsPage.vue` | 同上 | 同上 |
| `pages/ReportPage.vue` | 同上 | 同上 |
| `pages/AssessmentPage.vue` | 已删除 | — |

---

## 4. 需要改名为芭蕾的动作模块

当前 5 个动作（`backend/app/ml/pose/exercises.py`）全部是瑜伽定位：

| 旧 key | 旧中文名 |
| --- | --- |
| `MOUNTAIN_ARMS_UP` | 山式双臂上举 |
| `ARMS_LATERAL_RAISE` | 双臂侧平举 |
| `SIDE_BEND_STRETCH` | 左右侧屈伸展 |
| `SEATED_TRUNK_ROTATION` | 坐姿躯干旋转 |
| `SEATED_ALTERNATING_ARM_RAISE` | 坐姿交替抬臂 |

目标 5 个芭蕾动作（§30）：

| 新 key | 中文名 | 主导关节 | 默认执行方式 |
| --- | --- | --- | --- |
| `BALLET_PORT_DE_BRAS` | 芭蕾手臂组合 | 肩 / 肘 | 坐姿 + 站姿 |
| `BALLET_FIRST_POSITION` | 第一位姿态保持 | 躯干 / 肩 | 站姿扶椅（允许坐姿简化） |
| `BALLET_TENDU` | 伸腿点地 | 髋 / 膝 / 踝 | 站姿扶椅（允许简化） |
| `BALLET_DEMI_PLIE` | 半蹲 | 膝 / 髋 | 站姿扶椅 |
| `BALLET_WEIGHT_SHIFT` | 节奏性重心转移 | 躯干 / 肩 | 坐姿 + 站姿 |

**旧历史数据**：现有 `pose_sessions.exercise_type` 有旧的 5 个 key。不得删除、不得报错。
处理：前端 `pose/exercises.ts` 保留旧 key 的显示映射，历史记录显示为「历史动作训练」+
旧中文名；新记录只写入新 key。

**指标引擎改动**：Tendu 与 Demi-Plié 需要膝角度，现有 `metrics.py` 只有肩/肘/躯干。
需要**新增**（不是修改）膝角度纯函数 `knee_series`（hip-knee-ankle）与腿部驱动序列，
`POSE_METRICS_ALGORITHM_VERSION` 不变（已有指标定义未变），`EXERCISE_DEFINITION_VERSION` 升版。

---

## 5. 患者模式（Focus Mode）

**背景冲突与处理**：上一轮用户明确要求「所有的页面都应该有侧边栏」，因此删除了
`meta.focusMode` 与 `MainLayout` 的隐藏分支。本轮要求「患者任务模式隐藏 Sidebar」。
两者可以同时满足：**隐藏侧栏的前提是患者任务页顶部有一个显眼、随时可点的「返回」**，
这正是上一轮真正缺失的东西（当时页面没有退出口）。

方案：
- `MainLayout` 恢复 `meta.patientTask` 分支；患者任务页在**任务已开始**后进入 Focus 模式。
- Focus 模式由新组件 `PatientTaskLayout.vue` 承担（仓库中当前**不存在**该文件，
  需新建；不是重复组件）。
- 顶部固定：`← 返回`（带确认）、当前患者姓名、当前任务名、进度。
- 未开始任务前（选择患者阶段）仍留在普通后台布局，避免医生刚进来就失去导航。

适用任务：面部表现分析、手指敲击、钢琴、芭蕾。

---

## 6. 执行顺序

1. 建 `PatientTaskLayout.vue`，接入 4 个患者任务
2. 导航与重复入口收敛（Dashboard / PatientDetail / 侧栏 / 功能测试隐藏）
3. 用户文案清理（全局 + 逐页）
4. 芭蕾动作体系替换（后端定义 + 指标 + 前端展示 + 旧数据映射）
5. 坐姿 / 站姿 `execution_mode`
6. 节拍器 + Web Audio 钢琴伴奏 + 中文口令节奏提示
7. 钢琴可选记忆节奏模式
8. 测试（pytest / npm run build / npm run test:rules）+ 浏览器人工验收
9. `docs/ux_ballet_refactor_report.md` + README 更新 + 分批 commit

---

## 7. 风险

| 风险 | 缓解 |
| --- | --- |
| 芭蕾腿部动作需要新指标 | 只**新增**纯函数，不改已有公式；新指标版本独立标注 |
| 旧瑜伽历史导致页面报错 | 前端旧 key 映射 + 后端 `get_exercise` 返回 None 时前端降级显示 |
| Focus 模式回归上一轮「退不出去」的问题 | `PatientTaskLayout` 顶部固定返回按钮，浏览器验收必须实测返回路径 |
| 删除免责声明被误解为放宽合规 | 免责声明移入报告导出与管理员页，普通界面不再展示（按本轮要求） |
| 全局字符串替换破坏内部逻辑 | 逐条人工判断，只改用户可见字符串，不改枚举值/字段名 |
