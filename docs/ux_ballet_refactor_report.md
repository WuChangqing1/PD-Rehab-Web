# UX + Ballet Refactor Report

日期：2026-10-01
范围：`PD-Rehab-Web` 现有代码的产品结构、导航、交互、用户文案、芭蕾训练体系
配套文档：`docs/ux_ballet_refactor_plan.md`（审计与计划）、`docs/ballet_training_rationale.md`（动作依据）

---

## 1. 修改前的问题

按 `docs/ux_ballet_refactor_plan.md` 的方法审计（遍历 `frontend/src` 全部 `.vue`/`.ts`，
剥离注释后逐行匹配 70 个敏感词；再核对后端会经接口进入前端的字符串），实际发现：

**1.1 研发 / Demo / 科研文案直接出现在医生界面**
- `MedicalDisclaimer` 在每个登录页底部显示「本系统用于科研、辅助评估及康复训练展示，
  不能替代专业医生诊断和标准临床量表。」
- 工作台有 `DEMO DATA：当前处于 Mock 模式` / `DEMO_MOCK_MODE=true` 警告
- 工作台把内部模型键直接当功能名显示：`MediaPipe Hand Landmarker`、`MediaPipe Pose`、
  `微表情 / AI 模型`
- 患者列表与详情显示 `张三（虚拟）`，患者编号显示 `DEMO-0001`
- 随访页用整块 alert 向医生解释「已排除多少条非真人记录」「跨算法版本」
- 动作训练页把 `MOUNTAIN_ARMS_UP`、`CALIBRATION`、`FINGER_TAPPING_ONLY` 等枚举当标签显示

**1.2 患者任务没有专用界面**
`PatientTaskLayout.vue` 存在但**从未被任何页面引用**（它是我上一轮创建的，当时报告误记为
"已套用"）。患者做任务时看到的是完整的后台：侧栏、面包屑、患者管理、系统设置、
以及面向医生的技术卡片。

**1.3 动作模块是瑜伽，不是芭蕾**
五个动作全部是通用瑜伽体式（山式双臂上举、双臂侧平举、左右侧屈、坐姿躯干旋转、
坐姿交替抬臂）。没有节拍、没有口令、没有伴奏、没有坐姿/站姿区分——与老师给出的
「外部节奏 + 清晰口令 + 分解动作 + 慢速 + 音乐提示」完全不符。

**1.4 死页面与重复入口**
`TrainingPage.vue`（被 `TrainingHubPage` 取代）、`HistoryPage.vue`、`TrendsPage.vue`、
`ReportPage.vue` 四个文件**零引用**仍在仓库里。

**1.5 一次真实故障（记录在案）**
本轮开始时 `MainLayout` 的焦点模式实现把 `<router-view>` 放在 `v-if/v-else` 的两个分支里。
进入患者模式会销毁并重建被路由的页面组件，页面状态重置、卸载钩子又把标志清掉，
**界面会闪一下然后弹回后台**。实测点击「开始训练」复现。已改为 chrome 分别 v-if、
`<router-view>` 在树中位置不变。

---

## 2. 最终导航

侧栏（所有页面统一，恒为 6 项，不随路由增减）：

| # | 名称 | 路径 | 可见性 |
| --- | --- | --- | --- |
| 1 | 工作台 | `/dashboard` | 全部登录用户 |
| 2 | 患者档案 | `/patients` | 全部 |
| 3 | 评估中心 | `/assessment` | 全部 |
| 4 | 康复训练 | `/training` | 全部 |
| 5 | 随访与报告 | `/follow-up` | 全部 |
| 6 | 系统设置 | `/system/model-status` | 仅 ADMIN |

**功能测试不在侧栏。** 路由保留，直接访问显示「该功能暂未开放」（不含 Phase 等信息）。

---

## 3. 删除的重复入口

| 功能 | 修改前 | 现在 |
| --- | --- | --- |
| 面部表现分析 | 评估中心卡片 + 患者详情历史表按钮 | 评估中心（唯一） |
| 手指敲击 | 评估中心卡片 + 患者详情历史表按钮 | 评估中心（唯一） |
| 钢琴 | 康复训练卡片 | 康复训练（唯一） |
| 芭蕾/动作 | 康复训练卡片 | 康复训练（唯一） |
| 历史 / 趋势 / 报告 | 侧栏 3 项 + 患者详情 Tabs | 随访与报告（3 个 Tab） |
| 模型状态 | 侧栏对所有人可见 | 系统设置（仅 ADMIN） |
| 功能测试 | 侧栏/患者详情可达 | 无正式入口 |
| 工作台 | 曾承担「第二套菜单」 | 只做概览 |

工作台现在只有：今日统计、功能可用性、最近患者、最近评估、最近训练。
患者详情只有：基本资料、医疗资料、最近活动摘要、编辑入口。

---

## 4. 删除的研发 / Demo 文案

| 页面 | 删除的内容 |
| --- | --- |
| 全部（登录页与所有内页） | `MedicalDisclaimer` 组件及其文案，组件已删除 |
| 工作台 | `DEMO DATA / Mock 模式` 原文改为「系统当前处于演示数据模式，请联系系统管理员」；`MediaPipe *` 改为功能名（面部表现分析 / 手指敲击 / 芭蕾动作训练） |
| 患者档案 / 详情 / 选择器 | `（虚拟）` 后缀、`DEMO-` 前缀 |
| 新增患者 | 副标题「请使用虚拟或脱敏资料」→「请使用脱敏资料」；placeholder `虚拟姓名` → `患者姓名` |
| 评估中心 | 「面部分析」→「面部表现分析」；副标题去掉 `Finger Tapping` |
| 手指敲击页 | 标题去掉 `（Finger Tapping）` |
| 钢琴页 | 标题「虚拟钢琴 / 节奏训练」→「钢琴节奏训练」；键盘标题去掉「虚拟」；去掉「算法版本：…」整句；自检警告改写为不暴露内部枚举名 |
| 芭蕾页 | 标题去掉 `（Pose）`；副标题去掉 `MediaPipe Pose 逐帧提取 33 个关键点`；结果区去掉「算法版本」 |
| 随访与报告 | 趋势页删除「趋势图只画真人的测量值」「已排除 N 条非真人记录」「跨算法版本」三块说明；时间轴与报告页删除「来源」列与页脚排除统计 |
| 芭蕾历史表 | 删除「来源」列（真人录制 / 脚本自检录制 / 演示种子数据标签） |
| 系统设置（ADMIN） | **保留**全部技术信息：GPU、PyTorch、CUDA、模型状态、MediaPipe、Mock 模式等 |

**清洗逻辑没有被删除。** 非真人记录仍由 `src/followup/trends.ts` 在数据层排除，
只是不再向医生解释。缺失值仍显示「暂无数据」而不是 0。

---

## 5. 患者模式

`src/stores/taskMode.ts` 由页面在任务真正开始时置位，`MainLayout` 据此隐藏侧栏与顶栏
（chrome 分别 `v-if`，`<router-view>` 位置不变）。`PatientTaskLayout.vue` 提供：
顶部固定「返回 <目的地>」（44px，实测 40px 渲染高度）、患者姓名与编号、任务名、进度。
路由切换时 `afterEach` 兜底复位。

四个任务的进入方式（均由医生按「开始」触发，选患者阶段仍在后台）：

| 任务 | 入口动作 | 患者端看到 |
| --- | --- | --- |
| 面部表现分析 | 评估中心 → 面部表现分析 → 选患者 → 开始检查 | 摄像头、一句提示、一个「开始分析」，完成后「检查已完成，请稍候，医生会查看结果」 |
| 手指敲击 | 评估中心 → 手指敲击评估 → 选患者 → 开始检查 | 先测左手，录完自动进入右手，进度「第 N / 2 只手」 |
| 钢琴 | 康复训练 → 钢琴节奏训练 → 选患者与模式 → 开始 | 键盘、节拍提示、第 N / 3 轮 |
| 芭蕾 | 康复训练 → 芭蕾动作训练 → 选患者/方式/动作 → 开始训练 | 口令卡、节拍、摄像头、完成并分析 |

**浏览器实测**：芭蕾与手指敲击均确认进入（侧栏 0 项、`main` padding 0、返回按钮 40px）
并可从「返回」退出回到后台（侧栏恢复 6 项）。
**未验证**：面部表现的焦点模式——其模型未配置，「开始检查」按钮按设计保持禁用。

---

## 6. 评估中心

三张卡片，只有产品语言：

1. **综合评估** — 面部表现 + 左右手手指敲击
2. **面部表现分析** — 记录面部运动与表情变化
3. **手指敲击评估** — 手指动作速度、幅度与稳定性

卡片中没有 MediaPipe / PyTorch / Feature / Model / AI Algorithm。
模型不可用时页面只说「面部表现分析当前暂不可用」，技术原因在系统设置。

---

## 7. 钢琴训练

- **基础能力测试**（数据层仍叫 Calibration，UI 不再出现该词）：首次进入先做一次约 45 秒，
  用来测量患者自己的节奏。
- **自动三轮**：`第 N / 3 轮` 只读显示，难度由系统根据上一轮表现调整。患者无法手工跳轮。
- **四个基础模式**：单键节奏、左右手交替、按键序列、跟随节拍。
- **可选记忆节奏**：`MEMORY_RHYTHM`，系统先示范一小段（每个音都作为一个 `isPrompt` 提示
  音被点亮并播放），再由患者凭记忆弹出。难度按 4 → 5 → … 递增。
  - 它在 `TRAINING_MODES` 里（医生可选），但**不在** `CORE_TRAINING_MODES` 里，
    因此自动三轮流程永远不会排到它——否则「可选」就是假的。
  - 提示音在前后端**双向**排除出所有正确率分母（`is_prompt`）。把患者被要求「看」的音
    算成漏击，报告的是模式的产物而不是患者的表现。
  - 它是训练功能，不是认知诊断，不产生任何认知评分。
- **高级参数**（BPM / 判定窗口 / 序列长度）在「高级设置（医生）」折叠区，默认关闭。

---

## 8. 芭蕾训练

**五个动作**（`BALLET_*`），替代原瑜伽五式：

| 键 | 中文 | 关注 | 默认 BPM | 支持方式 |
| --- | --- | --- | --- | --- |
| `BALLET_PORT_DE_BRAS` | 芭蕾手臂组合 | 手臂活动范围、左右协调、流畅性、节奏 | 60 | 坐姿 + 站姿 |
| `BALLET_FIRST_POSITION` | 第一位姿态保持 | 躯干直立、对称、稳定、保持时间 | 60 | 站姿 + 坐姿 |
| `BALLET_TENDU` | 伸腿点地 | 腿部伸展、重心转移、活动范围、左右差异 | 60 | 站姿 + 坐姿 |
| `BALLET_DEMI_PLIE` | 半蹲 | 膝髋屈曲、对称、稳定、节奏 | 50 | 仅站姿（扶椅） |
| `BALLET_WEIGHT_SHIFT` | 节奏性重心转移 | 重心转移、全身协调、对称、节奏稳定性 | 60 | 坐姿 + 站姿 |

**坐姿 / 站姿**：医生在进入前选择，存 `pose_sessions.execution_mode`
（`SEATED` / `STANDING_SUPPORTED`）。选择后**只显示该方式支持的动作**
（坐姿下 Demi-Plié 不出现）。请求不支持的方式会被后端拒绝而不是静默降级——
坐姿录的 plié 不是 plié。历史行与退役的瑜伽键为 `UNKNOWN`，不猜。

**节拍与钢琴伴奏**：`BalletRhythmPanel` + `ballet/rhythm.ts` / `ballet/rhythmEngine.ts`。
- 纯 Web Audio 合成，**没有任何音频文件**，无版权风险。
- 节拍不是 `setInterval`：每个拍点按 AudioContext 时钟提前调度，UI 只补充调度队列；
  视觉计数读同一批拍点，看到的和听到的不会漂移。
- 4/4 小节，第一拍重音；伴奏是 C–Am–F–G 四小节循环，每拍一个音。
- 口令按「拍」映射到步骤：`双臂缓慢抬起`(4) → `向外打开`(4) → `缓慢回落`(4) → 保持(4)，
  大字显示当前步骤与步骤内第几拍。规则有 14 个单元测试锁定。

**Pose 指标**：新增 `knee_series`（hip-knee-ankle）与 `hip_abduction_series`
（shoulder-hip-knee）两个纯函数，供 Tendu / Demi-Plié 使用；**未修改任何已有指标定义**，
故 `POSE_METRICS_ALGORITHM_VERSION` 不变。展示分公式仍未定义，相关字段恒为空。

**动作示意**：内联 SVG 线稿（`PoseFigure.vue`），站姿动作画出椅子。
未使用任何版权不明的芭蕾图片。

**未做的**：没有向医生展示任何「芭蕾为什么有效」的文献或研究背景——那是汇报材料，
不是操作界面。

---

## 9. 随访报告

一个主入口 `/follow-up`，选患者后三个 Tab：**历史记录 / 趋势变化 / 综合报告**。

- 历史记录：评估、手指敲击、钢琴、芭蕾四张清单，名称与模式全部走中文字典
  （`SESSION_TYPE_LABELS`、`MODE_LABELS`、`exerciseName()`），退役动作键也能显示。
- 趋势变化：钢琴 / 芭蕾 / 手指敲击共 12 个指标折线。不同算法版本分成多条线不连成一条，
  单点画成点不画成线。
- 综合报告：各模块「最近一次 / 上一次 / 可用点数」。**不输出综合评分、严重程度分级、
  病情变化百分比**——没有经过验证的公式，因此留空而不是估算。

---

## 10. 功能测试

- 正式入口已隐藏：侧栏、工作台、患者详情、任何菜单都没有。
- 路由 `/functional-assessment` 仍在，直接访问显示「该功能暂未开放」并给出返回工作台，
  无 Phase 等研发信息。
- **后端未动**：`functional_assessments` 表、迁移、`FUNCTIONAL_TEST` 枚举、
  `FUNCTIONAL_TEST_LABELS` 全部保留。本轮 pytest 285 项全绿，含功能测试相关断言。

---

## 11. Demo Data

- **数据全部保留**：10 位患者、59 条芭蕾/动作会话、钢琴与评估历史一条未删。
- **普通 UI 已删除「虚拟 / Demo」标识**：姓名后缀、`DEMO-` 编号前缀、来源标签、
  演示免责说明。`displayPatientName()` / `displayHospitalNumber()` 只影响显示。
- **内部 provenance 完整保留**：`input_source`（`HUMAN_KEYBOARD` / `SYNTHETIC_SELFTEST` /
  `SEED_DEMO` / `UNLABELLED`）、`execution_mode`、审计日志、数据库里的原始姓名与编号
  一律未改。
- 搜索不受影响：后端按存储值做子串匹配，输入界面上看到的 `0010` 仍能命中 `DEMO-0010`。
- **一处数据修正**：种子写入的 `doctor_notes` 原文是「本行为演示用的虚拟患者记录，非真实病例。」
  这是数据不是界面文案，但它显示在「医生备注」下，读起来像对该患者的评述。
  种子脚本改为写普通临床备注，本地 10 行已同步更新。来源信息仍由姓名后缀、
  逐行 `input_source` 与审计日志承载。

---

## 12. 创建 / 修改 / 删除文件

**新增**
```
docs/ux_ballet_refactor_plan.md
docs/ux_ballet_refactor_report.md
docs/ballet_training_rationale.md
frontend/src/stores/taskMode.ts
frontend/src/ballet/rhythm.ts
frontend/src/ballet/rhythmEngine.ts
frontend/src/ballet/BalletRhythmPanel.vue
frontend/tests/rhythm.test.ts
frontend/tests/memory_rhythm.test.ts
backend/alembic/versions/e8f1a3c5b7d9_phase8_ballet_execution_mode.py
```

**修改（前端）**
```
layouts/MainLayout.vue              router/index.ts
components/PatientTaskLayout.vue    components/PatientSelector.vue
components/SelectedPatientBar.vue   components/PagePlaceholder.vue
components/PoseHistoryTable.vue     utils/format.ts
utils/source.ts                     types/index.ts
pose/exercises.ts                   pose/PoseFigure.vue
piano/session.ts                    piano/samples.ts
api/index.ts
pages/DashboardPage.vue             pages/PatientsPage.vue
pages/PatientDetailPage.vue         pages/PatientFormPage.vue
pages/AssessmentHubPage.vue         pages/MicroExpressionPage.vue
pages/FingerTappingPage.vue         pages/TrainingHubPage.vue
pages/PianoTrainingPage.vue         pages/MovementTrainingPage.vue
pages/FollowUpPage.vue              pages/LoginPage.vue
package.json                        tests/difficulty.test.ts（键名迁移）
```

**修改（后端）**
```
app/ml/pose/exercises.py            app/ml/pose/metrics.py
app/ml/pose/analyzer.py             app/db/models/training.py
app/db/models/assessment.py         app/schemas/pose.py
app/schemas/piano.py                app/schemas/assessment.py
app/services/pose_service.py        app/services/assessment_service.py
app/api/assessment_sessions.py      app/utils/piano_metrics.py
tests/test_pose_api.py              tests/test_pose_metrics.py
tests/test_system_and_models.py
scripts/seed_demo.py
```

**删除（均先全局搜索确认零引用）**
```
frontend/src/components/MedicalDisclaimer.vue
frontend/src/pages/TrainingPage.vue
frontend/src/pages/HistoryPage.vue
frontend/src/pages/TrendsPage.vue
frontend/src/pages/ReportPage.vue
```

---

## 13. Tests

| 命令 | 结果 |
| --- | --- |
| `pytest`（backend） | **285 passed / 0 failed / 0 errors** |
| `npm run build`（vue-tsc -b && vite build） | **✅ 通过** |
| `npm run test:rules`（node --test） | **74 passed / 0 failed**（原 25） |
| `npm test` | 不存在此脚本；前端可跑的规则测试即 `test:rules` |

新增测试覆盖：节拍与口令映射（14）、记忆节奏与提示音排除（12）、趋势过滤与版本分组（22）。

---

## 14. Manual Browser Check

逐页实测（本地 dev，患者 吴国庆）：

| 页面 | 结果 |
| --- | --- |
| Login | ✅ 无免责声明，凭据提示保留 |
| Dashboard | ✅ 侧栏 6 项；无 虚拟 / Demo / Mock / MediaPipe；功能名替代模型键 |
| Patients | ✅ 姓名无「（虚拟）」，编号无 `DEMO-`；无重复评估入口 |
| Patient Detail | ✅ 无第二套导航；钢琴模式与退役动作名均为中文 |
| Assessment Center | ✅ 三张卡片，只有产品语言 |
| Face | ⚠️ 模型未配置，页面提示「面部表现分析当前暂不可用」，开始按钮按设计禁用 |
| Finger Tapping | ✅ 进入焦点模式（侧栏 0、返回 40px、进度「第 1 / 2 只手」），可返回 |
| Training Center | ✅ 两张卡片按钮对齐 |
| Piano | ✅ 5 张模式卡（记忆节奏标「可选」）；第 1 / 3 轮只读 |
| Ballet | ✅ 5 个芭蕾动作按方式过滤（坐姿下 4 个）；进入焦点模式；口令随节拍推进（实测「第 1 步 / 双臂缓慢抬起 / 3 / 4」）；可返回 |
| Follow-up | ✅ 三个 Tab；趋势与报告无研发说明；历史里无枚举值 |

敏感词全站复扫（11 个页面 × 32 个禁用词）：**除系统设置（ADMIN 技术页，按设计保留）
外全部为 0 命中。**

---

## 15. Remaining Issues

1. **面部表现的焦点模式未实测**——老师提供的模型未接入，`MODEL_NOT_CONFIGURED`，
   开始按钮按设计禁用。焦点模式代码路径与手指敲击相同，但没有跑通过。
2. **芭蕾与动作的「通过门限」结果区未用真实样本验证**——本地库中「通过门限且有视频文件」
   的会话数为 0。拒绝分支已实测。
3. **趋势图仍无真实数据可画**——演示库全部是种子与自检数据，按规则被排除，
   趋势页显示空状态。需要演示前用真人做 2 次以上真实测量才能看到曲线。
4. **综合评估尚未做成 Stepper**——当前流程是「创建会话 → 进入第一个模块」，
   没有七步进度条与上一步/下一步。本轮未改动。
5. **9-HPT 等标准化功能测试未实现**——入口已按本轮要求隐藏，后端与数据保留。
6. **`POSE_METRICS_ALGORITHM_VERSION` 未升版**——本轮只新增了膝/髋角度函数，
   未改动任何既有指标公式，因此没有理由升版；但 Tendu 与 Demi-Plié 的
   `EXERCISE_DEFINITION_VERSION` 已从 `pose-exercises-v0.1.0-draft` 升为
   `ballet-exercises-v1.0.0`。
7. **芭蕾动作的临床参数（BPM、组数、保持时长）是起始默认值**，出处见
   `docs/ballet_training_rationale.md`；它们是可配置的训练设置，不是处方，也没有
   声称任何疗效。

---

## 16. Git

| 项 | 值 |
| --- | --- |
| Branch | `main` |
| 本批提交 | `23c71e8` 芭蕾动作体系 + 患者模式起步 → `ec93ddc` 用户界面研发文案清理 → `5dcdd98` 节拍与记忆节奏 + 四任务焦点模式 → `82551ba` 焦点模式挂载修复 + 标识清理 |
| 本轮之前的提交 | `2eccd16` 训练卡片对齐、`5f60f9e` 随访趋势与报告 |
| `git status` | 干净（工作树无未提交改动） |
| 已推送 | `origin main` |
| 已部署 | `https://ccqspace.site/pd-rehab/` |
