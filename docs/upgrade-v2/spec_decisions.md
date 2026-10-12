# 升级包冲突与决策记录

格式：冲突 → 依据 → 决策。优先级按用户确认：
**当前用户确认的需求 > 升级总 Prompt > 专项设计文档 > 原版开发规格**；
真实算法公式与既有数据库约束以实际代码与已核实定义为准。

---

## D01 · 患者指标卡片：按动作选取，而不是通用模板

- **冲突**：`docs/02` §结果设计要求「动作的关节指标要按定义选，不能 Port de Bras、Tendu
  都显示『抬肩角度』」；现网 `MovementTrainingPage.vue` 对所有动作写死肩角度。
- **依据**：后端 `exercises.py` 已按动作声明 `drive_series`
  （`DRIVE_SHOULDER` / `DRIVE_HIP` / `DRIVE_KNEE` / `DRIVE_TRUNK_TILT`），
  且 `_LEG_RAW_METRICS` 已为腿部动作补齐膝/髋指标（加法式，未改既有定义）。
- **决策**：前端**从动作定义派生**结果卡片，不写死。以 `drive_series` 决定主指标，
  左右差异/速度/保持时长作为次要指标。不新增任何算法公式，不生成展示分。

## D02 · `/follow-up` 的 `hidden` 标记

- **冲突**：`router/index.ts` 给 `/follow-up` 标了 `hidden: true`，
  但 `MainLayout.vue` 把「随访与报告」放在主导航第五项。
- **依据**：`docs/02` §唯一主信息架构 —— 随访与报告是正式入口；
  `docs/01` G05 要求解除；功能测试才应隐藏。
- **决策**：`/follow-up` 去掉 `hidden`；`/functional-assessment` 保留
  `hidden: true`。`hidden` 目前无渲染消费者，此改动只让声明与事实一致，
  并加测试锁定。

## D03 · 芭蕾示范视频：无合格素材的动作不放视频

- **冲突**：`docs/03` 要求每个「动作 × 模式」有循环示范视频；
  实际 9 个组合中 7 个无候选，已下载的 1 个也未经动作审核。
- **依据**：`docs/04` §没有视频时正确回退 ——「不使用错误视频顶替」，
  「不得把静态 SVG 伪装成已经实现的真人视频」。
- **决策**：分三种状态明确区分并在 UI 上如实标注：
  `有已审核视频` / `有候选但未审核` / `暂无视频示范`。
  最后一种不放视频、不放别人的视频，只显示明确标注为示意的静态分解图。
  禁止用站姿视频冒充坐姿版。

## D04 · 坐姿 Tenndu 的命名

- **冲突**：`docs/01` 指出 `BALLET_TENDU` 同时支持坐姿与站姿，但坐姿变体
  不等同标准 ballet tendu。
- **依据**：`docs/03` 动作矩阵 ——「坐姿：伸膝—脚尖触地—回收，命名『坐姿伸腿改编版』」。
- **决策**：坐姿变体在界面上显示为「坐姿伸腿改编版」，
  不沿用站姿英文名 `Tendu` 作为主标题。

## D05 · Piano 新配方不新建第二套引擎

- **冲突**：`docs/05` 要求新增 SFT / CFT / 双手同步 / 重音分组四类训练；
  但 `docs/02` 与总 Prompt 都禁止「为相同能力复制三套页」。
- **依据**：`docs/05` §新的信息架构 —— 配方是**模板**，
  「所有训练均进入同一个 `PianoTrainingPage`/`PatientTaskLayout`，
  复用既有 `PianoKeyboard`, `useRunner`, `pianoApi` 和事件结构」。
- **决策**：新增的是**配方层**（recipe），复用既有 mode 与事件结构；
  `CFT` 与 `BIMANUAL_SYNC` 需要新增 cue 策略与事件归并，但不新建页面、不新建引擎。
  记忆节奏（`MEMORY_RHYTHM`）保持可选，不新增「记忆节奏 2」。

## D06 · CFT 撤除提示后的 `response_latency_ms`

- **冲突**：直觉上每个按键都应有反应延迟。
- **依据**：`docs/05` §原始事件 ——「CFT 在 cue 撤除后并无实际 `cue_onset`：
  对应反应延迟应为 `null`，不能以目标时间硬补；仍有目标拍位可算 timing error」。
- **决策**：撤提示阶段 `response_latency_ms = null`，
  只计算 `timing_error_ms`。这与既有 `metric_definitions.md` 的
  `response_latency_ms = first_valid_response − cue_onset` 定义一致，不构成公式改动。

## D07 · 双手同步不能复用单键指标

- **依据**：`docs/05` ——「不能随便用现有『一个 cue 一按键』计算作为双手同步分数」。
- **决策**：新增 `inter_hand_onset_diff_ms = |left_ms − right_ms|`，
  与既有单键指标并存、不互相替代。

## D08 · 展示分继续留空

- **冲突**：`docs/02` 想要直观的结果卡片。
- **依据**：`exercises.py` 中部分 `score formula` 为空；总 Prompt 禁止随机生成 0–100。
- **决策**：展示分（完成度 / ROM / 对称性 / 稳定性）**继续为 NULL**，
  只显示原始测量值，并在卡片脚注说明原因。不为了让页面好看而编造分数。

## D09 · nginx 子路径重定向逃逸

- **事实**：`/pd-rehab/api/patients/` 的 307 `Location` 丢掉了 `/pd-rehab` 前缀，
  落到根路径后被**另一个项目**的 nginx block 接走并返回 502（见 U01）。
- **决策**：代码侧已修（不再发出空 id 请求）。**nginx 侧不改动**，
  因为它属于线上共享配置且会影响其它服务；改法已记录在
  `UX_issue_inventory.md` U01，等用户确认后再动。

## D10 · 视频素材不进 Public 仓库

- **依据**：`docs/07` §部署安全；总 Prompt 禁止把私有资产推到 Public GitHub。
- **决策**：原始候选视频放 `private/source_videos/`（已 gitignore）。
  裁剪产物是否入库，取决于授权结论：`CC BY-SA` 允许再分发但需署名+同许可，
  因此**在处理产物上附鸣谢与许可信息**后再入库；未审核前不入库。
