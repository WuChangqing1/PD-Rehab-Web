# 规格冲突与合并记录（spec_conflicts.md）

> 项目：PD-Rehab-Web
> 版本：Phase 0
> 依据：任务书第二条「两个 Markdown 的合并规则」
>
> **合并规则（本文档的执行准则）**
> 1. **互补内容全部保留。**
> 2. **重复内容优先采用 V2 中更详细、更严格的定义。**
> 3. **直接冲突不静默选择**：记录到本文件，**默认优先 V2**；
>    若冲突明显影响核心产品逻辑，在最终报告中明确告知用户。
> 4. **需求文档的指标定义不能凌驾于真实算法代码。** 与
>    `VideoBased-PD-Biomarkers` 真实实现不一致的，以真实代码为依据，并记录差异
>    （→ 见 `docs/metric_definitions.md` §7 的 D1–D12）。
> 5. **不悄悄删除任一文档的要求。**

---

## 0. 两份文档总览

| 项 | V1 `PD_Rehab_Web_Development_Spec.md` | V2 `PD_Rehab_Web_Development_Spec_V2_Metrics.md` |
| --- | --- | --- |
| 行数 | 2805 | 2874 |
| 定位（本任务书） | **工程实现、环境配置、Adapter、项目目录、启动方式、患者使用流程、前后端开发、Demo 落地** | **指标体系、数据结构、科研严谨性、算法指标定义、质量控制、数据库字段、长期趋势、功能验证** |
| 章节数 | 61 | 80 |
| 独有重点 | 微表情模型接入细节、Pose 动作逐一说明、Conda/pip 命令、前端初始化命令、资料依据（DRUM-AI / Leap Motion / HoVRS / NeuroRecover / PaWei）、MVP 边界、`training_plans` 表 | 指标分层 L1–L4、P0/P1/P2 优先级、Finger Tapping 指标定义逐条、CV/slope/interruptions 规范、钢琴 Raw Event 全字段、Response Latency vs Timing Error 严格区分、Calibration 指标清单、自适应规则引擎、9-HPT/BBT/MDS-UPDRS/PDQ-39 分层、Baseline 增强、assessment_sessions 父子结构、audit_logs、Jobs、metric_definitions.md 强制要求、`.env.example` 增强 |
| 共同内容 | 项目闭环、技术栈、Finger Tapping 仓库规则、老师模型规则、UI 风格、页面路由、大部分 API、Piano 4 模式、Pose 5 动作、医疗文案、Phase 划分 | 同左（更详细） |

---

## 1. 重复内容清单（V2 更详细/更严格 → 采用 V2）

| # | 主题 | V1 | V2 | 采用 |
| --- | --- | --- | --- | --- |
| R1 | 项目闭环 | §2 | §1 | **V2**（V2 增加"更新 Baseline / 调整训练"回路） |
| R2 | 技术栈 | §1.3 | §3 | 一致，两者合并（V2 增加 `GPU_INFERENCE_CONCURRENCY`） |
| R3 | Finger Tapping 仓库规则 | §1.4 | §4.1 | **V2**（V2 增加"Phase 0 必须先确认特征定义/归一化/滤波/峰谷/预训练模型"） |
| R4 | 老师模型不确定项 | §1.5 | §4.2 | **V2**（V2 列出更完整的不确定项清单：FPS/输入尺寸/预处理/是否输出二分类概率） |
| R5 | 输出兼容两类模型 | 隐含（只有 tag 分布） | §5.1/§5.2/§5.3 显式 | **V2**（V2 显式支持 `pd_probability` 型 + 使用表述约束） |
| R6 | 不做帕金森总分 | §16、§39 | §6、§8 | **V2**（V2 提出 L1–L4 分层） |
| R7 | Finger Tapping 分析流程 | §14（mermaid） | §10（文字） | **V2**（V2 增加"尺度归一化 → 质量控制"两步） |
| R8 | 质量控制门限 | §48（3 项） | §12（5 项 + quality_json） | **V2**（更严格） |
| R9 | 文件存储路径 | §33 | §51 | **V2**（V2 增加 `timeseries.npz`、显式点名 `UUID.mp4`） |
| R10 | 模型加载策略 | §38 | §50 | **V2**（V2 显式要求 MediaPipe 也复用） |
| R11 | 长任务 Job | §32 | §49 | **V2**（V2 显式 `GPUInferenceManager + Semaphore(1)`） |
| R12 | 页面路由 | §4 | §52 | **V2**（V2 增加 `/patients/:id/functional-assessment`） |
| R13 | UI 要求 | §5 | §53 | **V2**（V2 增加"字号略大""患者模式减少菜单"） |
| R14 | Dashboard | §6 | §54 | 一致，合并（V1 增加"不要在首页显示确诊人数"） |
| R15 | 患者详情 Tab | §9（5 个 Tab） | §55（6 个 Tab） | **V2**（V2 增加「功能评估」Tab） |
| R16 | 患者字段 | §8 + §29.2 | §37 | **V2**（V2 增加 `is_deleted`；V1 独有字段见 §2-工程） |
| R17 | Baseline | §17 | §33 | **V2**（V2 增加 `piano_calibration`、`quality_metadata`、`algorithm_version`） |
| R18 | 钢琴 4 模式 | §19 | §15 | **V2**（V2 增加"模式 3 = 按键映射任务，非真实手指识别"的明确限定） |
| R19 | Piano Raw Event 字段 | §20 | §17 | **V2**（V2 增加 `event_index`/`cue_onset_time_ms`/`response_latency_ms`/key up/hold） |
| R20 | 钢琴 Calibration | §22.2 | §20 | **V2**（V2 列出 8 个 `baseline_*` 指标名） |
| R21 | 自适应规则 | §22.4 | §23 | **V2**（V2 增加 `Timing MAE` 条件、`note_density`、降级措辞更完整） |
| R22 | 左右手自适应 | §22.5 | §24 | **V2**（V2 增加"每轮最多调整 10%～15%"的幅度限制） |
| R23 | Pose 动作 | §24（5 个，逐一说明） | §27（5 个，仅列表） | **两者合并**：动作列表用 V2，每个动作的检测关节/指标用 V1（V2 未展开） |
| R24 | Pose 展示指标 | §25 | §29 | **V2**（V2 强制"每个公式必须在 exercise definition 中配置"） |
| R25 | Pose 安全规则 | §26 | §59 | **V2**（V2 增加统一医疗安全文案） |
| R26 | 医疗边界 | §55 | §53、§59 | **V2**（V2 措辞更完整，含训练页提示） |
| R27 | 开发 Phase | §44（8 个 Phase） | §64–§73（10 个 Phase） | **V2**（见 §4-C1，与任务书一致） |
| R28 | 测试要求 | §46 | §63 | **V2**（V2 增加 finger-tapping QC / CV / left-right difference / functional CRUD / trend aggregation） |
| R29 | `.env.example` | §34 | §77 | **V2**（V2 增加 `GPU_INFERENCE_CONCURRENCY`） |
| R30 | Agent 工作规则 | §45（12 条） | §76（17 条） | **两者合并**（见 §2-工程 E4） |

---

## 2. 各自独有内容（**全部保留，不删除**）

### 2.1 V2 独有（必须实现）

| # | 内容 | 章节 |
| --- | --- | --- |
| V2-1 | 指标分层 L1 Raw / L2 Online / L3 Session / L4 Clinical | §6 |
| V2-2 | P0 / P1 / P2 指标优先级清单 | §7.1 |
| V2-3 | "为什么选择这些指标"的依据说明 | §8 |
| V2-4 | Finger Tapping 输入规范（10–20 秒、3 秒倒计时、页面提示文案） | §9.1 |
| V2-5 | Finger Tapping 指标逐条定义（frequency/amplitude/speed/cycle/CV/slope/interruptions） | §11 |
| V2-6 | **interruptions 阈值不得随意固定**，必须配置化并存入 `analysis_config_json` | §11.7 |
| V2-7 | `quality_json` 具体字段示例 | §12 |
| V2-8 | 左右手比较的 8 个成对指标 + `absolute_difference` 优先 + "不得判断疾病侧别" | §13 |
| V2-9 | **Response Latency 与 Timing Error 的严格区分** | §16 |
| V2-10 | `mean_absolute_timing_error` 定义 | §16.3 |
| V2-11 | 弱指指标的"任务映射"限定说明 | §19 |
| V2-12 | 长期难度进阶配置（4–8 周、第 4/8 周复评） | §25 |
| V2-13 | MIDI 第一版不接入的 4 条理由 + 后续字段清单 | §26 |
| V2-14 | Pose 原始指标优先（11 个原始字段名） | §28 |
| V2-15 | range_of_motion / symmetry / stability / movement_speed 的定义方向 | §30 |
| V2-16 | 功能测试分层：9-HPT(MVP) / BBT(推荐) / 手指协同 / MDS-UPDRS / PDQ-39 | §31 |
| V2-17 | **综合评估父子结构 `assessment_sessions`** | §34 |
| V2-18 | 完整数据库字段定义（staff_users…audit_logs） | §36–§47 |
| V2-19 | `severity_score` / `severity_label` 只能来自真实模型，否则 NULL | §41 |
| V2-20 | 完整 API 清单（含 Assessment Session / Functional Assessment / System / Jobs） | §48 |
| V2-21 | `metric_definitions.md` 强制要求与条目格式 | §62 |
| V2-22 | `functional_assessments` 表与 `test_type` 枚举 | §46 |
| V2-23 | 训练与功能测试统一时间轴（7 天 / 30 天 / 全部） | §57 |
| V2-24 | 长期比较必须显示 `medication_state` | §57 |
| V2-25 | 一句话产品定义（"评估—训练—记录—复评—趋势"长期闭环） | §79 |

### 2.2 V1 独有（必须保留）

| # | 内容 | 章节 |
| --- | --- | --- |
| V1-1 | 旧系统参考的 5 个具体方面（布局 / 患者列表与新增页 / 上传后左右双栏 / 弹窗详情+饼图 / 医院后台风格） | §1.1 |
| V1-2 | 产品闭环 mermaid 流程图 | §2 |
| V1-3 | 用户角色设计：医生/管理员 + 患者模式（患者不强制单独账号，医生"进入患者模式"） | §3 |
| V1-4 | 患者列表表格字段建议（10 列）与行操作 | §7.1 |
| V1-5 | 患者基本信息字段（含 `age`、`id_card`、`emergency_contact`、`emergency_phone`） | §8.1 |
| V1-6 | 微表情模块：支持 mp4/mov/avi；前端支持"本地上传 + 摄像头录制" | §11.2 |
| V1-7 | 微表情展示结构：左侧原视频 / 右侧分析结果视频或关键帧；结果卡 5 项；"不需要保留旧 MRI 按钮" | §11.4 |
| V1-8 | Finger Tapping Adapter 文件清单（含 `feature_extractor.py`、`schemas.py`） | §15 |
| V1-9 | 视频评估结果页双维度并列展示（微表情维度 + Finger Tapping 维度） | §16 |
| V1-10 | 资料依据与产品参考（DRUM-AI / Leap Motion Serious Games / HoVRS / NeuroRecover / PaWei） | §41 |
| V1-11 | MVP 边界清单 | §42 |
| V1-12 | Pose 动作逐一说明（每个动作的检测目标与指标） | §24 |
| V1-13 | 动作难度调整方向（保持时间/次数/范围目标/节奏/左右交替复杂度 + 具体阈值示例） | §27 |
| V1-14 | **`training_plans` 表定义**（V2 未给出该表字段，但 §43 引用 `training_plan_id`） | §29.7 |
| V1-15 | 综合报告的分维度展示结构（面部表现/精细运动/钢琴/动作训练） | §39 |
| V1-16 | 历史比较的 4 个必备字段（date/value/session_type/medication_state） | §40 |
| V1-17 | 后端/前端项目结构（含 `services/` 分层、`scripts/` 5 个脚本） | §30 |
| V1-18 | Conda 环境创建与 pip 安装命令、前端初始化命令、启动命令 | §35–§37 |
| V1-19 | `scripts/seed_demo.py`（10 个虚拟患者，覆盖年龄/左右受累/ON-OFF-UNKNOWN） | §49 |
| V1-20 | **README 必须包含的 13 项内容清单** | §50 |
| V1-21 | 模型异常处理的 6 类场景 | §47 |
| V1-22 | "当前仍需后续补充的信息"（老师模型 6 项） | §56 |
| V1-23 | 产品创新点的 5 条呈现方式 | §54 |
| V1-24 | 首次启动目标（PowerShell 双窗口 + localhost:5173） | §52 |
| V1-25 | Phase 0 验收标准（8 项） | §58 |

---

## 3. 直接冲突（**不静默选择 → 全部记录，默认优先 V2**）

### C1 — 开发目录（**需要用户知悉**）

| | 内容 |
| --- | --- |
| V1 §51 / V2 §78 | 开发目录 `D:\CodingData\Github\PD-Rehab-Web` |
| 任务书第三节 / 第三十五条 | 开发目录 `D:\CodingData\Competition\PD\PD-Rehab-Web` |
| **最终采用** | **任务书**：`D:\CodingData\Competition\PD\PD-Rehab-Web` |
| 理由 | 任务书是本轮的**直接指令**，且工作区为 `D:\CodingData\Competition\PD`；两份规格文档中的路径属旧约定 |
| 影响 | 无功能影响。仅 README / 脚本文档中的路径需按新目录书写 |

### C2 — 数据模型：`assessments` vs `assessment_sessions`（**核心结构冲突**）

| | 内容 |
| --- | --- |
| V1 §29.4 | 表名 `assessments`，字段 `assessment_type`、`status`、`created_by`、`started_at`、`completed_at`、`notes` |
| V1 §31 | 综合评估 API：`POST /api/patients/{id}/assessments/comprehensive`、`GET /api/patients/{id}/assessments`、`GET /api/patients/{id}/latest-assessment` |
| V2 §34 / §38 / §48 | 表名 **`assessment_sessions`**，字段 `session_type`（枚举）、`status`、`created_by`、`started_at`、`completed_at`、`notes`、`created_at`；API 为 `/api/patients/{id}/assessment-sessions`、`/api/assessment-sessions/{sid}`、`/api/assessment-sessions/{sid}/complete` |
| **最终采用** | **V2**。表名 `assessment_sessions`，类型字段 `session_type`，枚举 `COMPREHENSIVE / MICRO_EXPRESSION_ONLY / FINGER_TAPPING_ONLY / FUNCTIONAL_TEST`。所有子结果（微表情、左手 FT、右手 FT、功能测试）通过 `assessment_session_id` 外键挂载到同一次综合评估 |
| 理由 | V2 明确以"避免不同时间数据被错误当作同一次评估"为设计目标（V2 §34），且 V2 的 API/DB/前端路由自洽 |
| **额外裁定（V1 独有要求不得丢失）** | V1 §10 要求"两个模块不强制一定一次完成，完成任何一个都可以保存单项结果" → **已保留**：由 `session_type` 的 `MICRO_EXPRESSION_ONLY` / `FINGER_TAPPING_ONLY` 支持 |
| 影响 | 需在 `docs/api_decisions.md` 记录为 API 决策，并在 Phase 1 Alembic 迁移中体现 |

### C3 — 微表情 API 路径

| | 内容 |
| --- | --- |
| V1 §31 | `POST /api/patients/{patient_id}/assessments/micro-expression` |
| V2 §48 | `POST /api/assessment-sessions/{session_id}/micro-expression` |
| **最终采用** | **V2**（任务书第三十条："不要自行随意改变 V2 已规定 URI"） |

### C4 — Finger Tapping API 路径

| | 内容 |
| --- | --- |
| V1 §31 | `POST /api/patients/{patient_id}/assessments/finger-tapping` |
| V2 §48 | `POST /api/assessment-sessions/{session_id}/finger-tapping` + `GET` 同路径 |
| **最终采用** | **V2**（V2 额外提供 GET 查询，是 V1 缺失的能力） |

### C5 — Movement 帧上传 API

| | 内容 |
| --- | --- |
| V1 §31 | `POST /api/movement/sessions/{session_id}/analyze` |
| V2 §48 | `POST /api/movement/sessions/{session_id}/frames/batch` |
| **最终采用** | **V2**。但 **V1 §23.1 的架构原则保留**："前端实时绘制骨架，最终指标由统一的 Pose Service 计算" —— 即 `frames/batch` 上传关键点/角度帧，`complete` 时由后端计算最终指标 |

### C6 — 钢琴指标命名：RT 家族 vs Latency 家族（**影响长期趋势与 API 契约**）

| | 内容 |
| --- | --- |
| V1 §21 / §29.8 | `mean_reaction_time_ms`、`median_reaction_time_ms`、`reaction_time_cv`、`left_mean_rt`、`right_mean_rt`、`left_right_rt_difference`、`timing_mae_ms` |
| V2 §18 / §43 | `mean_response_latency_ms`、`median_response_latency_ms`、`response_latency_cv`、`left_mean_latency`、`right_mean_latency`、`left_right_latency_difference`、`timing_mae_ms` |
| **最终采用** | **V2 全量命名**。DB 列名与 API JSON 字段一律用 `*_response_latency_*` / `*_latency*` |
| 理由 | ① V2 更严格地定义了 `response_latency` 与 `timing_error` 的语义区分（V2 §16），命名必须与语义一致；② 任务书第十三条明确要求区分 Response Latency 与 Timing Error；③ V1 的 "Reaction Time" 措辞在 V2 中被有意替换 |
| 影响 | 术语统一，**无功能损失**。`timing_mae_ms`（两版一致）保留 |

### C7 — 钢琴 Session 字段完整度

| | 内容 |
| --- | --- |
| V1 §29.8 | `bpm`、`judgement_window_ms`、`sequence_length`、`hand_mode`、`session_duration_sec`（**无** `weak_side_ratio`、`finger_complexity`、`early/late_press_rate`、`sequence/session_completion_rate`、`left_accuracy`/`right_accuracy`、`median_timing_error_ms`） |
| V2 §43 | 上述全部 **+** `weak_side_ratio`、`finger_complexity`、`early_press_rate`、`late_press_rate`、`left_accuracy`、`right_accuracy`、`weak_finger_error_rate`、`sequence_completion_rate`、`session_completion_rate`、`median_timing_error_ms`、`left_right_latency_difference` |
| **最终采用** | **V2**（超集） |

### C8 — Piano Event 字段完整度

| | 内容 |
| --- | --- |
| V1 §29.9 | `target_time_ms`、`actual_time_ms`、`timing_error_ms`、`key_code`、`note`、`hand`、`finger_hint`、`is_correct`、`is_missed` |
| V2 §44 | 上述 **+** `cue_onset_time_ms`、`response_latency_ms`、`key_down_time_ms`、`key_up_time_ms`、`hold_duration_ms` |
| **最终采用** | **V2**（超集）。`cue_onset_time_ms` 是计算 `response_latency_ms` 的必要输入 |

### C9 — `severity_score` / `severity_label`

| | 内容 |
| --- | --- |
| V1 §12.2 | "如果仓库中确实存在可直接使用的训练完成模型 / checkpoint，再额外返回 severity_score / severity_label" |
| V2 §41 | "只有外部仓库存在真实模型时才能写入。否则必须为 NULL。" |
| **最终采用** | **V2**。**且经 Phase 0 实际审计，外部仓库确无预训练严重度模型**（`optimization_training.py` 不保存模型、无推理入口），故这两个字段**必须为 NULL** |
| 影响 | 无功能损失；**如实反映真实能力**，符合"不虚构"原则 |

### C10 — `avg_landmark_confidence`（**证据冲突**）

| | 内容 |
| --- | --- |
| V1 §48 | 质量控制只要求 3 项（可读 / 帧数 / FPS / 检测比例），**不提** landmark confidence |
| V2 §12 | "建议保存 `avg_landmark_confidence`"（示例 JSON 中给出 `0.88`） |
| **最终采用** | **V2 的字段保留，但值当前必须为 `NULL`** |
| 理由 | 外部仓库使用 **MediaPipe Tasks API**，其 `NormalizedLandmark` **不提供 `visibility`/`presence`** 字段（那是旧版 `mp.solutions.hands` 的语义）。**V2 示例中的 `0.88` 是示意值，不是可获得的真实值**；直接填 `0.88` 会构成伪造 |
| 待办 | Phase 4 实测确认是否有真实来源（候选：`detection_result.handedness[i][0].score`）。确认前保持 `NULL` |
| 影响 | **需要用户知悉**：这是 V2 示例值与真实 API 能力之间的冲突，本系统选择"宁可 NULL，不伪造" |

### C11 — `cycle_duration_cv` vs `cycle_cv`

| | 内容 |
| --- | --- |
| V2 §7.1 | 指标清单写 `cycle_duration_cv` |
| V2 §41 | 数据库字段写 `cycle_cv` |
| **最终采用** | **DB 列名 `cycle_cv`**（"数据库设计以 V2 §41 为主要依据"），**API JSON 同时提供 `cycle_duration_cv` 别名** |
| 影响 | 轻微；记入 `docs/api_decisions.md` |

### C12 — `avg_speed` vs 仓库双字段

| | 内容 |
| --- | --- |
| V1 §12.2 / V2 §41 | 单一字段 `avg_speed` |
| 真实仓库 | `avg_percycle_avg_speed` **与** `avg_percycle_max_speed` 两个字段 |
| **最终采用** | `avg_speed := avg_percycle_avg_speed`（与"平均速度"语义一致）；`avg_percycle_max_speed` 存入 `raw_features_json` 不丢失 |
| 影响 | 轻微；记入 `docs/api_decisions.md` |

### C13 — 患者年龄字段

| | 内容 |
| --- | --- |
| V1 §8.1 | 字段列表含 `age`（和 `id_card`、`emergency_contact`、`emergency_phone`） |
| V2 §37 | 字段列表**无** `age`、`id_card`、`emergency_contact`、`emergency_phone`；有 `birthday` |
| **最终采用** | **`age` 不入库**，由 `birthday` 实时计算派生（避免年龄陈旧）。**V1 要求的 `age` 展示能力保留**（患者列表与详情页显示计算出的年龄） |
| `id_card` | **不实现**。V2 §58 与任务书第二十一条均强调数据安全；`id_card` 是可选的 Demo 字段且"不建议使用真实数据" → 直接不建该字段，杜绝风险 |
| `emergency_contact` / `emergency_phone` | **保留**（V1 独有且属合理医疗信息，V2 未禁止）→ 作为 V1 增量字段实现 |

### C14 — 患者列表字段

| | 内容 |
| --- | --- |
| V1 §7.1 | 10 列表格：患者编号 / 姓名 / 性别 / 年龄 / 主要受累侧 / 惯用手 / 病程 / 当前用药状态 / 最后评估时间 / 最后训练时间 |
| V2 | 未定义列表字段 |
| **最终采用** | **V1**（V2 未涉及，属互补） |

### C15 — 患者详情 Tab 数量

| | 内容 |
| --- | --- |
| V1 §9 | 5 个 Tab：基本资料 / 最近评估 / 康复训练 / 长期趋势 / 报告 |
| V2 §55 | 6 个 Tab：基本资料 / 最近评估 / 康复训练 / **功能评估** / 长期趋势 / 报告 |
| **最终采用** | **V2**（超集，与 V2 §32「外部验证页面」一致） |

### C16 — 开发 Phase 划分（**需要用户知悉**）

| | 内容 |
| --- | --- |
| V1 §44 | 8 个 Phase：0 环境 / 1 骨架 / 2 患者 / 3 微表情 / 4 FingerTapping / 5 钢琴 / 6 Pose / 7 趋势 / 8 报告与 Demo |
| V2 §64–§73 | 10 个 Phase：0 环境与指标审计 / 1 骨架 / 2 患者 / 3 真实AI微表情 / 4 FingerTapping / 5 Piano / 6 Pose / **7 功能测试** / **8 趋势和报告** / **9 Demo 打磨** |
| 任务书第三十四条 | 与 **V2** 完全一致（Phase 0–9，名称逐字相同） |
| **最终采用** | **V2**（与任务书一致） |
| V1 内容保留 | V1 的 "Phase 8：报告与 Demo" 被拆入 V2 的 Phase 8（趋势和报告）与 Phase 9（Demo 打磨），**内容无丢失** |

### C17 — Pose 展示分是否直接输出

| | 内容 |
| --- | --- |
| V1 §25 | 直接给出 `completion_score: 82`、`range_of_motion: 74`、`symmetry_score: 88`、`stability_score: 79` 的 JSON |
| V2 §28 / §29 / §30 | **先保存原始指标**，再由规则引擎计算展示分；"每个 score 必须有确定公式，公式必须在 exercise definition 中配置，**不允许 Agent 随意返回 0～100 的随机分数**" |
| **最终采用** | **V2**。且更进一步：在公式固化前（`metric_definitions.md` §3.4 中标 `TBD` 的项），**Score 不入库、不展示**；原始指标先行入库 |
| 影响 | **需要用户知悉**：V1 §25 中的 `82/74/88/79` **是示意值，不是可实现的默认输出**。实现这些分数需要先定义公式（Phase 6） |

### C18 — 微表情输出结构

| | 内容 |
| --- | --- |
| V1 §11.3 | 输出含 `assessment_id`、`patient_id`、`model_name`、`model_version`、`dominant_tag`、`tags[]`、`video_duration_ms`、`created_at` |
| V2 §40 | DB 字段：`predicted_class NULL`、`pd_probability NULL`、`dominant_tag NULL`、`tag_distribution_json NULL`、`raw_output_json`、`inference_time_ms`、`quality_json`、`feature_schema_version` |
| **最终采用** | **V2 为 DB 结构**；**V1 的 `video_duration_ms` 保留**（归入 `quality_json`）；V1 的 `tags[]` ↔ V2 的 `tag_distribution_json`（同一语义，采用 V2 命名） |
| 两者一致处 | "不能在 API 层硬编码标签数量，标签列表以真实模型为准"（V1 §11.3）→ **V2 未反对，保留** |

### C19 — 综合报告结构

| | 内容 |
| --- | --- |
| V1 §39 | 四段式分维度展示（面部表现 / 精细运动 / 钢琴训练 / 动作训练） |
| V2 §56 / §72 | 按模块列趋势指标；明确"模型输出变化"而非"病情改善 X%" |
| **最终采用** | **两者合并**：报告结构用 V1 §39 的分维度布局，措辞与趋势口径用 V2 §56 的约束 |
| 共同底线 | **禁止"帕金森总分 78"**（V1 §39 与 V2 §6 一致） |

### C20 — 训练计划表

| | 内容 |
| --- | --- |
| V1 §29.7 | 定义 `training_plans` 表（`id/patient_id/name/status/start_date/end_date/created_by/config_json/created_at`） |
| V2 §43 | `piano_sessions.training_plan_id` 引用该表，但 **V2 未给出 `training_plans` 的表定义** |
| 任务书第二十条 | 要求实现 `training_plans` |
| **最终采用** | **V1 §29.7 的定义**（V2 未定义 → 无冲突，属 V1 独有的必要补充） |

### C21 — 集成测试覆盖范围

| | 内容 |
| --- | --- |
| V1 §46 | 6 项测试 |
| V2 §63 | 13 项测试 |
| 任务书第三十三条 | 与 V2 一致（14 项，含 `functional assessment CRUD` 与 `trend aggregation`） |
| **最终采用** | **V2 + 任务书**（超集） |

### C22 — Q3：患者年龄与"id_card"

见 C13。**`id_card` 明确不实现**（安全优先）。

### C23 — 表清单

| | 内容 |
| --- | --- |
| V1 §29 | 12 张表：`staff_users`、`patients`、`media_files`、`assessments`、`micro_expression_results`、`finger_tapping_results`、`training_plans`、`piano_sessions`、`piano_events`、`pose_sessions`、`baselines`、`audit_logs` |
| V2 §36–§47 | 12 张表：`staff_users`、`patients`、`assessment_sessions`、`media_files`、`micro_expression_results`、`finger_tapping_results`、`baselines`、`piano_sessions`、`piano_events`、`pose_sessions`、**`functional_assessments`**、`audit_logs`（**无 `training_plans`**） |
| 任务书第二十条 | 13 张表：V2 的 12 张 **+ `training_plans`** |
| **最终采用** | **任务书 = V2 ∪ V1 = 13 张表**：<br>`staff_users`、`patients`、`assessment_sessions`、`media_files`、`micro_expression_results`、`finger_tapping_results`、`baselines`、**`training_plans`**、`piano_sessions`、`piano_events`、`pose_sessions`、`functional_assessments`、`audit_logs` |
| 说明 | `assessments` → 重命名为 `assessment_sessions`（见 C2）。**两者是同一实体，不是两张表，不重复实现** |

### C24 — 数据来源（真人 / 脚本 / 演示种子）**两份规格都没有定义**

| | 内容 |
| --- | --- |
| V1 | 只在 `DEMO_MOCK_MODE` 处提到"演示模式"，未定义任何逐行来源字段 |
| V2 | 要求"原始数据优先""不得伪造"，但同样没有给出来源标记字段 |
| 任务书 | 禁止随机标签、随机概率、硬编码截图百分比、静默 Mock |
| **实际风险** | Phase 5 的脚本自检把合成按键事件写进了库，**该行与真人测量完全无法区分**；`seed_demo.py` 生成的 84 条钢琴历史同样带着看似合理的随机指标 |
| **最终采用** | 新增 `piano_sessions.input_source`（非空 + 索引 + 封闭集合）：`HUMAN_KEYBOARD` / `SYNTHETIC_SELFTEST` / `SEED_DEMO`。**默认 `HUMAN_KEYBOARD`，非法值 422**。非真人来源的 Calibration 生成的 Baseline 必须写明"不是真人测量值" |
| 说明 | 这是**新增字段而非规格冲突**，因此不改变任何指标公式，也不递增算法版本号。定义见 `docs/metric_definitions.md` §2.3.4，迁移 `b1c7f0a2d4e5` |
| 待办 | Phase 6（Pose）与 Phase 7（9-HPT）落地时需要各自的同类标记 |

---

## 4. 冲突对核心产品逻辑的影响评估

| 冲突 | 是否影响核心产品逻辑 | 说明 |
| --- | --- | --- |
| C1 目录 | ❌ 否 | 纯路径约定 |
| **C2 数据模型** | ✅ **是** | 决定了整个评估数据如何组织。已按 V2 的父子结构实现，并保留 V1 的"单项可独立完成"能力 |
| C3/C4/C5 API 路径 | ⚠️ 轻度 | 影响前后端契约，已统一采用 V2 |
| **C6 指标命名** | ⚠️ **是（需知悉）** | `RT` → `Response Latency` 是**语义澄清**而非改名。若前端/报告误用 "Reaction Time" 会与 `timing_error` 混淆，**这是 V2 有意修正的重点** |
| C9 severity | ⚠️ 是 | 直接决定"不能输出严重度分数"，如实反映能力 |
| **C10 landmark confidence** | ⚠️ **是（需知悉）** | V2 示例值 `0.88` **在真实 API 下不可得**。选择保持 NULL |
| **C16 Phase 划分** | ⚠️ **是（需知悉）** | Phase 7 从"趋势"变为"功能测试"，趋势与报告合并到 Phase 8。**与任务书一致** |
| **C17 Pose 分数** | ⚠️ **是（需知悉）** | V1 的 82/74/88/79 是示意值，**不可直接实现**。需要 Phase 6 先定义公式 |
| C23 表清单 | ⚠️ 轻度 | 采用并集（13 张表），无信息丢失 |
| **C24 数据来源标记** | ⚠️ **是（需知悉）** | 规格未定义来源字段，实测已出现"脚本合成的按键被当成患者测量值"这一类风险。新增 `input_source` 并在 UI 与基线备注中显式声明 |

---

## 5. 需要用户明确知悉的 5 项（**重点**）

> 以下 5 项冲突会影响核心产品逻辑或对"系统能做什么"的预期，**请在审核 Phase 0 时确认**。

### ⚠️ K1 — 真实能力限制：没有严重度分数

外部仓库 `VideoBased-PD-Biomarkers` **不存在**预训练严重度分类模型
（全仓搜索 `*.pt/*.pth/*.ckpt/*.onnx/*.engine/*.pkl/*.joblib` 无命中；
`optimization_training.py` 不保存模型、无推理入口）。
因此 `severity_score` / `severity_label` **将始终为 NULL**，第一版只输出真实运动学指标。
**这不是实现缺失，而是如实反映上游能力。** 若要严重度分级，需另行训练模型（需数据与权重）。

### ⚠️ K2 — `avg_landmark_confidence` 无法从现有 API 真实获得

V2 §12 的示例值 `0.88` 与 MediaPipe Tasks API 的实际字段能力矛盾。
本系统选择**保持 NULL 而不填占位值**。Phase 4 会尝试从
`detection_result.handedness[i][0].score` 找到真实替代来源；若找不到，该字段长期为 NULL。

### ⚠️ K3 — 钢琴难度不依赖微表情标签 / PD 概率

`帕金森应用.pptx` 第 10 页提出"以患病概率设置基础难度（如 0.7 → 0.7 的基础难度）"，
**V2 §5.3 / §20 / §22 与任务书第十五条明确否定该做法**。
**最终采用 V2**：难度只依赖个人 Calibration + 实际训练表现。
这属于**产品设计的有意变更**（原始想法被规格否决），而非文档冲突，特此记录。

### ⚠️ K4 — Pose 展示分需要先定义公式，不能直接给 82/88/79

V1 §25 的 `completion_score: 82` 等数值是**示意值**。
V2 §29 强制"每个 score 必须有确定公式，公式必须在 exercise definition 中配置"。
因此 **Phase 6 必须先完成公式定义并版本化，Score 才能入库/展示**；
在此之前只有原始角度指标可用。`metric_definitions.md` §3.4 已把这些公式标为 `TBD`。

### ⚠️ K5 — 服务器无法承担真实 GPU 推理，且纯 IP 下摄像头不可用

1. **服务器无 GPU**（`lspci` 只有 Cirrus Logic GD 5446），且内存仅 **3.6 GiB 且无 swap**。
   → 微表情模型与 MediaPipe 只能 CPU 推理，必须单并发 + 严格内存限制。
2. **服务器用 `http://110.42.236.65:18085` 访问时不是 Secure Context**
   → 浏览器 `getUserMedia` 不可用，**摄像头录制功能在服务器上无法工作**。
   规格已规定此时"优先保证本地 MP4 文件上传完整可用"，本方案遵循该优先级。
   若必须支持服务器端录制，需使用已有证书域名 `ccqspace.site`（会涉及修改已有 Nginx 文件，**需您批准**）。
3. **新端口 18085 需在腾讯云安全组放行**，否则外网不可达。

---

## 6. 合并后的最终技术裁定汇总（Phase 1 起生效）

| 领域 | 裁定 |
| --- | --- |
| 项目根目录 | `D:\CodingData\Competition\PD\PD-Rehab-Web` |
| 主规格 | V2 为指标体系/数据结构/API/科研严谨性主规格；V1 为工程实现与流程补充规格 |
| 数据库 | **13 张表**（V2 的 12 张 + V1 的 `training_plans`）；`assessments` → `assessment_sessions` |
| API 前缀 | `/api`，路径一律以 V2 §48 为准 |
| 钢琴术语 | 一律用 `response_latency`（**不用** `reaction_time` / `rt`） |
| 严重度 | `severity_score` / `severity_label` 恒为 NULL |
| landmark confidence | 恒为 NULL（待 Phase 4 实测确认替代来源） |
| 微表情模型 | 当前 `MODEL_NOT_CONFIGURED`，禁止任何 Mock/伪造 |
| 难度引擎 | 只依赖 Calibration + 实时表现；**不依赖**微表情标签或 PD 概率 |
| Pose 分数 | 公式未固化前不入库、不展示；只入库原始指标 |
| 开发 Phase | V2 / 任务书的 Phase 0–9 |
| 测试 | V2 §63 + 任务书第三十三条（14 项后端 + `npm run build`） |
| 医疗文案 | 统一用 V2 §53/§59 措辞 |

---

> 本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。
