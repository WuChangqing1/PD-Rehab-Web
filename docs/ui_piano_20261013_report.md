# UI 与钢琴训练优化交付报告（2026-10-13）

本轮在现有项目增量修改，未重新搭建、未清空数据库、未访问 SSH 或生产服务、未推送远端。完整阅读用户提供的 README、总 Prompt、7 份专项文档和首页截图后实施。

基线 `fb4d9d049fc3e8006e59d4a5e67ad7aa5a45249a`；工作分支 `codex/ui-piano-20261013`。开始时只有用户设计包 `docs/codex-ui-piano-20261013/` 未跟踪，没有未提交源码；该包保持原样，不纳入本轮源码提交。

## 已完成的产品与视觉变化

- 删除左下假加号和整张无交互说明卡、装饰英语、营销横幅和首页重复快捷入口。
- Logo 与平台名称整个区域成为工作台链接，支持展开/折叠侧栏、手机抽屉和键盘访问。患者任务继续使用带放弃确认的退出入口。
- 首页保留真实患者、评估、训练统计、最近患者及最近评估，将模型数量准确标为“分析组件状态”。当前首页 API 没有最近训练列表，没有虚构该数据；训练历史在随访查看。
- 统一导航、蓝灰配色、字号、卡片、表单、空状态、按钮、弹窗和响应式间距。训练入口卡和练习目录采用固定封面高度、统一标题位置、底部操作对齐。
- 钢琴目录不再折叠原有模式：13 张练习卡统一分类、选择、预览和开始。SFT 与单键节奏合并为同卡的“单键提示方式”变体，保留历史 ID，避免用重复卡凑数量。
- 手机提供左右手大触屏按键；保留完整键盘试听与选择。双指可同时操作，pointer capture 避免移动手指提前释放，取消触摸不伪造物理 keyup。
- 进入任务后回到操作指令区，琴键定位只横向滚动键盘，不再把操作指令和结束按钮滚出屏幕；浏览器断言先复现失败，再验证修复。

## 练习清单与实际行为

基础能力测试独立保留，不用于凑以下 13 项数量。

| 练习 | 存储标识 | 独有 Cue / 交互 | 保存、查看的主要指标 |
| --- | --- | --- | --- |
| 单键节奏 | SINGLE_KEY_RHYTHM；同卡 SFT_CUE_SYNC 变体 | 每个目标提示同一个琴键；SFT 保留原提示配方 | 正确率、反应延迟、节拍误差 |
| 左右手交替 | ALTERNATING_HANDS | 左右手交替，保留弱侧配置 | 左右准确率、延迟差、漏击 |
| 按键序列 | MAPPED_SEQUENCE | 按顺序完成映射琴键 | 正确率、序列指标、任务映射错误率 |
| 跟随节拍 | FOLLOW_THE_BEAT | 跟随固定节拍按键 | 节拍误差、绝对误差、间隔稳定性 |
| 记忆节奏 | MEMORY_RHYTHM | 先逐音示范，再按记忆同序弹出 | 非示范响应的准确率、漏击与时序指标 |
| 保持节奏 | CFT_RHYTHM_HOLD | 前 8 拍有提示，随后撤去提示继续敲击 | 有/无提示准确率、无提示 MAE、间隔 CV |
| 双手同时敲击 | BIMANUAL_SYNC | 同一目标时间左右手各一键，真实记录两个响应 | 双手同步误差均值/标准差、左右准确率 |
| 强拍识别 | ACCENT_GROUPING | 每组第一拍视觉/播放提示更明显，按准每拍 | 强拍命中率、节拍误差、漏击；无压力指标 |
| 节奏变速（新增） | TEMPO_RAMP | 按本轮实际时间分四段变速，再回起始速度；全部目标与判定窗留在本轮内 | 每段准确率、MAE、漏击率、Cue 数 |
| 长短音控制（新增） | HOLD_RELEASE | 交替要求保持 250 / 750ms，再释放；等待释放窗口后解析 | 持续时间 MAE、释放完成率、原始 down/up |
| 双手错位节奏（新增） | BIMANUAL_OFFSET | 左手先按，右手晚半拍；每组后休息一拍 | 双手相位 MAE、左右漏击率 |
| 反向序列（新增） | REVERSE_SEQUENCE | 顺序示范，间隔两拍后逆序弹出 | 逆序位置准确率、完整组完成率 |
| 选择性反应（新增） | GO_NO_GO | “按下 ○”出现后响应；每三次一次“等待 ×”不按 | NO_GO 误按目标数、GO 漏按数、GO 反应延迟 |

五种新配方使用 `piano-recipe-v2.0.0`；旧模式和旧配方 ID/版本继续兼容。原有自适应规则阈值和主要公式保留，本轮修复了示范行错误进入前端统计、双手第二键误判及释放归属等数据处理问题。

## 新算法与指标的可核查定义

- **变速**：默认四段倍率 1 / 1.05 / 1.10 / 1，按实际时间划段生成。实际速度取基础配置与密度的乘积再受上限限制；`tempo_ceiling_bpm` 随本轮配置保存，40–160，优先沿用已有个人基线/训练目标上限。倍率是可检查的软件任务参数，不是新增的疗效结论。
- **分段统计**：非示范、非额外错键目标分组；accuracy = 正确目标数/该段目标数，MAE = 正确响应 `abs(actual-target)` 的均值。后端另保存 miss_rate、cue_count。
- **长短音**：持续时间由实际 `keyup-keydown` 重算，不信客户端 duration。MAE = `abs(实际持续时间-target_hold)` 均值；释放完成率 = 有有效 down/up 的目标数/全部长音目标数。漏击、失焦、取消或未释放不伪造释放时间，留在分母。
- **错位节奏**：以 pair_id 配对 PRIMARY 左手 / SECONDARY 右手；相位 MAE = `abs(右actual-左actual-target_offset)` 均值。缺一手时不生成相位数值，左右漏击分别统计。
- **逆序**：示范行保留 `is_prompt`，但排除准确率/完成率分母；每组必须完整包含 1..sequence_length 且全正确，才计入完成组。
- **选择性反应**：GO 的响应窗口从可见信号开始，反应延迟 = actual-onset；NO_GO 正确不按是正确抑制，不算漏击、不产生虚构时序或反应时。误按数按发生按键的 NO_GO 目标数统计，额外错键不重复计目标。
- **真实性**：普通键盘/触屏没有压力采集；强拍只涉及提示和时序。手/手指标注为任务映射，不冒称实际生理手指识别。缺失值保留 null。

新字段穿过前端 Cue、原始事件、Pydantic、JSON side channel、服务端重算、数据库详情和随访结果：`tempo_segment`、`target_hold_ms`、`pair_id`、`target_offset_ms`、`cue_type`，复用原有示范/序列位置字段。`raw_presses` 单独保存全部实际按下/释放，保留未归入目标的输入。新增指标存于 `difficulty_before_json.server_metrics`，没有清库或数据库迁移。

## 启动、患者与失败处理

- 无患者可浏览全部练习、试听、选择；只有开始时检查患者。
- 开始时重新读取患者，拒绝删除患者。选择患者后保留练习、绑定身份，显示 3→2→1；取消、准备失败、倒计时切人不会建立训练 Session。
- 钢琴 Session 延迟至有原始事件且明确点击保存时创建，固定启动患者、配置、来源和时间快照。`client_request_id` 幂等创建，重复请求配置不一致返回 409。
- 原始事件按 event_index 幂等上传。SQLite 使用事务写锁；其他数据库采用 locking read，防止同患者的并发重试重复建会话/事件。
- 丢失完成响应时 GET 已保存结果恢复。主动结束标记 INTERRUPTED，保留实测事件，不推进训练难度或伪造完整轮次。
- 音频恢复在点击手势内启动，并等待 resume 的真实结果；倒计时节点键冲突修复，数字 3、2、1 均正确显示。
- 失焦/触摸取消/结束/卸载清持键和音频；迟到 keyup 不写到旧 press；进度值现在随已解决 Cue 更新。
- 芭蕾同样将建会话延迟到实际非空录制分析，保存互斥、固定患者快照、重试复用 ID，离开确认和迟到响应保护保留。
- 随访详情合并顶层持久化指标与扩展指标，修正 MAE 缺失；详情有患者身份，切人关闭详情、废弃迟到请求。

## 测试与浏览器证据

最终实际运行结果（均 exit 0）：

| 命令 | 结果 |
| --- | --- |
| `cd frontend; npm run test` | **219 passed，0 failed** |
| `cd frontend; npm run build` | **Vue/TypeScript 检查与 Vite 构建通过** |
| `cd backend; python -m pytest -o addopts='' -q`（项目 pd 环境） | **386 passed，2 warnings，92.56s** |
| `node scripts/ui_piano_shell_browser.mjs` | 6 页 × 7 尺寸；无横向溢出、卡片对齐、品牌/导航实际点击通过；0 API 写入 |
| `node scripts/ui_piano_browser.mjs` | 7 尺寸目录对齐；13 卡；3/2/1 各取消；5 新练习实际键盘输入→真实 API→独立 SQLite→结果读取；0 pageerror |
| `node scripts/ui_piano_edge_browser.mjs` | 患者选择/切换、网络失败重试、历史详情、390/375 双指触屏、750ms 长音、放弃退出、保存响应丢失重试通过；0 pageerror |
| `node scripts/ui_piano_capture.mjs` | 七尺寸封面/标题/CTA 对齐断言、无溢出、训练指令可见断言通过，截图已保存 |

后端警告：已有 Starlette TestClient/httpx 弃用提示，以及极端数值 CV 回归中的 NumPy overflow warning；均不是失败。前后端没有未解决的测试失败。

新增回归先复现问题再修复，包括示范计分、变速超时/上限、反向序列位置、NO_GO、双手同步、按下释放匹配、进度、幂等配置和真实 SQLite 并发。完整路径脚本使用真实 FastAPI 路由/服务/指标和独立内存 SQLite；所有保存输入声明 `SYNTHETIC_SELFTEST`，只有两个明确虚拟患者，不连接现有开发/生产患者库。

五项合成流程实际保存结果（用于验证逻辑，不是临床测量）：

| 配方 | 原始事件数 | 服务端准确率 | 专项结果 |
| --- | ---: | ---: | --- |
| TEMPO_RAMP | 20 | 100% | 四段均存在，分段 MAE 已保存 |
| HOLD_RELEASE | 15 | 100% | 持续时间 MAE 0ms |
| BIMANUAL_OFFSET | 20 | 100% | 相位 MAE 0ms |
| REVERSE_SEQUENCE | 12（含示范） | 100% | 完整逆序组完成率 100% |
| GO_NO_GO | 20 | 100% | NO_GO 误按 0，GO 漏按 0 |

边界脚本第一次从 5 个会话开始、结束为 6；滚动修复后最终重跑从 6 开始、结束为 7。每次浏览、取消、切人、触屏放弃都没有增加会话，只增加 1 个明确保存的 INTERRUPTED 会话。上传重试后事件索引唯一，完成响应丢失后恢复成功，没有重复结果。

七种尺寸：1440×900、1366×768、1024×768、768×1024、430×932、390×844、375×812。目录同排封面高度、卡片高度和 CTA 底边误差不超过 2px；没有页面横向溢出。手机输入通过真实 Chromium touch/CDP 两指事件验收，**不是实体手机硬件验收**。

机器结果：

- [全站布局与导航结果](ui-screenshots/ui-piano-shell-20261013/results.json)
- [新增练习真实 API 结果](../artifacts/ui_piano_browser_results.json)
- [触屏与失败重试结果](../artifacts/ui_piano_edge_results.json)
- [最终对齐与截图检查](../artifacts/ui_piano_capture_results.json)

## 截图

首页前后均有 2048×1092 版本。原图来自用户设计包，后图来自本轮明确的虚拟测试库，数据条数不能用于临床前后比较。

- [优化前首页](../artifacts/screenshots/dashboard_before.png)
- [优化后首页（2048）](../artifacts/screenshots/dashboard_after_2048.png)
- [优化后首页（1440）](../artifacts/screenshots/dashboard_after.png)
- [训练入口](../artifacts/screenshots/training_after.png)
- [桌面练习目录](../artifacts/screenshots/piano_catalog_after.png)
- [训练中](../artifacts/screenshots/piano_run_after.png)
- [手机首页](../artifacts/screenshots/mobile_dashboard.png)
- [手机双指钢琴](../artifacts/screenshots/mobile_piano.png)
- [375 手机钢琴](../artifacts/screenshots/mobile_piano_375.png)
- [手机长音](../artifacts/screenshots/mobile_hold_after.png)
- [历史指标详情](../artifacts/screenshots/piano_history_after.png)
- [丢失响应恢复结果](../artifacts/screenshots/piano_retry_after.png)

各尺寸目录截图及五个新增练习结果截图在 `artifacts/screenshots/`；一般页面 22 张截图在 `docs/ui-screenshots/ui-piano-shell-20261013/`。已人工查看桌面首页、目录和手机钢琴截图。

## 修改文件清单

源码与测试按职责列出；截图路径见上节。

**布局与常规页面**

```text
frontend/src/layouts/MainLayout.vue
frontend/src/styles/main.css
frontend/src/components/TrainingArtwork.vue
frontend/src/pages/DashboardPage.vue
frontend/src/pages/TrainingHubPage.vue
frontend/src/pages/AssessmentHubPage.vue
frontend/src/pages/LoginPage.vue
frontend/src/pages/PatientsPage.vue
frontend/src/pages/PatientDetailPage.vue
frontend/src/pages/FollowUpPage.vue
frontend/src/pages/MicroExpressionPage.vue
frontend/src/utils/errors.ts
```

**钢琴、启动与接口**

```text
frontend/src/pages/PianoTrainingPage.vue
frontend/src/pages/MovementTrainingPage.vue
frontend/src/components/PracticeCover.vue
frontend/src/components/TrainingStartGate.vue
frontend/src/composables/useTrainingStartGate.ts
frontend/src/piano/PianoKeyboard.vue
frontend/src/piano/catalogue.ts
frontend/src/piano/engine.ts
frontend/src/piano/extendedMetrics.ts
frontend/src/piano/extendedRecipes.ts
frontend/src/piano/metricDefinitions.ts
frontend/src/piano/metrics.ts
frontend/src/piano/recipes.ts
frontend/src/piano/session.ts
frontend/src/piano/useRunner.ts
frontend/src/api/index.ts
frontend/src/types/index.ts
backend/app/api/piano.py
backend/app/schemas/piano.py
backend/app/services/piano_service.py
backend/app/utils/piano_metrics.py
```

**测试、验证脚本与文档**

```text
frontend/package.json
frontend/tests/recipes.test.ts
frontend/tests/piano_expansion.test.ts
frontend/tests/piano_runner.test.ts
frontend/tests/training_start.test.ts
backend/tests/test_piano_extended_recipes.py
backend/tests/test_piano_concurrent_retries.py
scripts/ui_piano_shell_browser.mjs
scripts/ui_piano_browser.mjs
scripts/ui_piano_edge_browser.mjs
scripts/ui_piano_capture.mjs
scripts/ui_piano_test_server.py
docs/ui_piano_20261013_audit.md
docs/ui_piano_shell_notes.md
docs/ui_piano_backend_notes.md
docs/ui_piano_start_notes.md
docs/ui_piano_20261013_report.md
```

## 提交与未覆盖边界

已分阶段本地提交：

1. `9c2af83` — 首页、导航、通用视觉与初轮布局验收。
2. `f20b27e` — 13 项目录、5 种新配方、事件/指标/存储/历史与回归。
3. `4763c1f` — 倒计时、患者核实、芭蕾延迟保存和退出保护。
4. `c079c57` — 修复琴键自动定位导致操作指令离开视口的问题。

截图、最终验收脚本与本报告另作交付提交；最终 hash 见 `git log` 与交付回复。没有 push、SSH 或生产部署。

当前没有阻塞这 13 项练习交付的测试失败。以下边界明确保留：

- 未做实体 iOS/Android、蓝牙/MIDI 或真人临床效果验证；自动化输入不能作为患者改善数据。
- 非 SQLite 的锁分支未连接真实 MySQL/PostgreSQL 做并发实测。
- 校准完成与建立 baseline 仍沿用原有两次提交；服务进程恰在两次提交之间退出，可能出现已完成会话但 baseline 尚未建立。中断校准不会替换有效 baseline。
- 芭蕾实际创建/分析仍为两次 API。创建成功响应丢失或上传时硬刷新可能遗留未完成行；普通重试复用 ID、保存中阻止路由离开，但本轮没有扩展其后端为原子分析事务。该边界不在准备或倒计时取消时发生。
- 首页最近训练列表需要新增服务端概览字段，当前继续使用真实训练次数与随访历史，没有用假数据补齐。

生产数据、已有模型算法、账号与权限均未重置。临时 QA 进程及诊断文件在交付前清理；用户原始设计资料保留。
