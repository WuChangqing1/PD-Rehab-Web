# PD-Rehab-Web V2 深度升级 · 执行报告

日期：2026-10-12
分支：`main`　基线：`9343061`　当前：`bea7e4e`
线上：`https://ccqspace.site/pd-rehab/`（**尚未部署本轮改动**，理由见 §9）

> **第二轮补记。** 第一轮报告只验证了部分验收标准。第二轮逐条补验，
> **发现并修复了三个真实缺陷**，其中两个是我自己引入的：
>
> 1. **配方事件字段根本没有入库。** `PianoEventIn` 接受 `pair_role` 等字段、
>    前端也确实发送，但 service 一个都没写——本项目早有 `events_extra_json`
>    侧信道约定，我把字段加进 schema 却没加进那里。字段被接受、被校验、被丢弃，
>    **没有任何报错**，导致双手配方的同步指标读到丢失配对的事件后报 None。
>    新增的「schema 字段必须有归宿」测试立刻又抓到两个**早已在丢**的字段。
> 2. **`is_prompt` / `memory_group` 也一直在丢。** `is_prompt` 标记"这一行是示范、
>    不是提问"，`compute_metrics` 靠它把示范行排除出分母。丢掉它等于把系统自己
>    示范的音符算成患者没答上来，用根本没发生的失败抬高漏击率。
> 3. **双手配方的第二个键从来没有显示给患者。** `secondaryBinding` 只存在于数据层，
>    键盘只高亮一个键——界面要求按两个键却只给看一个，**功能不可玩**。
>    这正是任务书警告的「只增加功能名称或卡片」。
>
> 详见 `PROGRESS.md` 第二轮小节与 §8 的补验结果。

---

## 1. 真实源码审计

### 1.1 早就有、本轮没重做的能力

| 能力 | 代码依据 | 本轮处理 |
| --- | --- | --- |
| Vue3 单站 + `/pd-rehab/` 子路径 | `vite.config.ts`、`router/index.ts` | 保留 BASE 与旧路由重定向 |
| 固定五项主导航、手机 Drawer | `layouts/MainLayout.vue` | 未改结构，仅统一视觉 token |
| 统一角色体验、患者不登录 | `stores/auth.ts` | 未改 |
| 功能优先入口（评估/训练中心） | `AssessmentHubPage`、`TrainingHubPage` | 保留 |
| 患者选择 / Focus 模式 | `PatientSelector`、`PatientTaskLayout`、`taskMode` | 复用 |
| 摄像头共享组件 | `VideoCapturePanel.vue` | 复用 |
| Finger Tapping 视频分析 | `backend/app/ml/finger_tapping/*` | **公式未改** |
| 芭蕾五动作与坐/站模式 | `backend/app/ml/pose/exercises.py` | 仅改显示名与文案 |
| 节拍 / 伴奏引擎 | `BalletRhythmPanel.vue`、`rhythmEngine.ts` | 复用，未加第二套播放器 |
| 钢琴五个 mode | `piano/session.ts` | 保留，新增的是配方层 |
| 后端评估 / 钢琴 / Pose API | `backend/app/api` | 最小扩展 |
| 自动测试 | `backend/tests`、`frontend/tests` | 增量添加 |

### 1.2 本轮新发现（升级包未列出）

**U01 · P0 · 芭蕾页在未选患者时打出跨应用 502**

线上实测：访问 `/pd-rehab/training/movement`（不带 `patientId`）时，浏览器发出

```
/pd-rehab/api/patients/                   307  ← 空 id
https://ccqspace.site/api/patients        502  ← 逃出子路径
```

根因链（逐段实测确认）：`MovementTrainingPage.load()` 无条件执行
`patientApi.get(patientId.value)`，空 id 时请求 `/api/patients/`；FastAPI 的
`redirect_slashes` 按**剥离前缀后**的路径构造 `Location`，于是重定向到站点根路径；
根路径的 `location /api/` 属于**另一个项目的 nginx server block**
（`mysite.conf:62` → `127.0.0.1:8080`），该服务未运行，返回 502。

**已修**（代码侧）：空 id 不再请求患者与历史。全项目扫描确认只有这一处。
nginx 侧按你的决定**不动**。

**U02 · P1 · `/follow-up` 的 `hidden` 与主导航自相矛盾（= G05）**
实测 `router.getRoutes()`：`/follow-up` 标记 `hidden: true`，但它就是侧栏第五项。
**已修**：去掉该标记；`/functional-assessment` 保留。

**U03 · P1 · 芭蕾结果卡片对腿部动作显示肩角度（= G04）**
`summaryCards` 写死 `left_shoulder_max_angle_deg`。**已修**，见 §2。

**U04 · P2 · 芭蕾动作卡没有任何按钮**。**已修**。

**U05 · P2 · `BALLET_DEMI_PLIE` 显示名是「半蹲」**
「半蹲」暗示的深度超过动作定义允许的范围。**已改**为「扶椅浅屈膝」。

### 1.3 PPT 里是概念、不是权重

- FG-LGL（光流引导双注意力 / ViT-DA、9 个 AU 语义区、两级 Transformer）与
  AUG-GCN（滑窗累积光流、鼻尖运动补偿、AU 先验图卷积、BATEM onset/apex/offset）
  是**论文方法描述**。
- UF1 / UAR / F1 是**原论文实验结果**，不是本平台在 PD 数据上的准确率。
- 全仓库**不存在任何** `.pth/.pt/.onnx/.ckpt/.safetensors`；
  `micro_expression/adapter.py` 显式 `MODEL_NOT_CONFIGURED`。

---

## 2. 视觉改造

| 位置 | 改动 | 证据 |
| --- | --- | --- |
| 设计 token | 调色板、字号阶、圆角阶、内容宽 1360px 全部集中到 `main.css`，与 `docs/02` 对齐 | `styles/main.css` |
| 主导航 | 未改结构（上一轮已固定五项），统一到新 token | `after/p1-*` |
| 康复训练中心 | 两张一级卡保持 | `after/p1-training-hub-1440x900.png` |
| 芭蕾动作卡 | 由整块 `<button>` 改为 `.pd-action-card`：16:9 媒体区、保留 2 行标题区、3 行说明区、`margin-top:auto` 的 CTA 行，新增「查看动作」按钮 | `after/p2-demo-1440x900.png` |
| 卡片等高 | 同排 4 项：`bottomSpread 0`、`mediaBottomSpread 0`、`titleTopSpread 0`、`ctaTopSpread 0`（预算 2px） | 浏览器实测 |
| 动作示范区 | 新增 `ExerciseDemoPanel`：左介绍 / 右示范，示范与摄像头分区标注 | `after/p2-demo-*` |
| 钢琴配方 | 三组四张配方卡，单卡占满整行、双卡等高；原有五模式收进折叠区 | `after/p3-recipes-1440x900.png` |
| 患者 Focus | 未改结构（上一轮已完成），本轮回归验证通过 | 7 种尺寸无溢出 |
| 响应式 | 12 条路由 × 7 种尺寸，最大横向溢出 **0px** | 见 §8 |

**一处自己发现并修掉的视觉缺陷**：标题的 2 行预留被全局 `h3 { margin: 0 0 0.5em }`
叠加，导致单行标题下方出现空档。已把 margin 显式归零，使预留高度成为唯一来源。

---

## 3. 芭蕾素材验收表

**结论：9 个「动作 × 模式」组合，0 个有可用于患者的视频。** 详情见
`docs/upgrade-v2/asset_gap_report.md` 与 `frontend/src/ballet/demoAssets.json`。

| 动作 | 模式 | 源页 | 授权 | 下载 | 看片审核 | 入出点 | 输出 MP4 / 封面 | 动作审核 | 线上播放 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `BALLET_DEMI_PLIE` | STANDING_SUPPORTED | Wikimedia Commons | CC BY-SA 3.0 ✅ 已核 | ✅ 868 406 B | ✅ **已逐帧看** | 未确定 | ❌ 未产出 | ❌ **REJECTED** | ❌ 不放 |
| `BALLET_TENDU` | STANDING_SUPPORTED | Wikimedia Commons | CC BY-SA 3.0 ✅ 已核 | ❌ **429 限流** | ❌ 没看过 | — | ❌ | ❌ 待审核 | ❌ 不放 |
| `BALLET_PORT_DE_BRAS` | SEATED / STANDING | — | — | — | — | — | — | — | ❌ 无候选 |
| `BALLET_FIRST_POSITION` | SEATED / STANDING | — | — | — | — | — | — | — | ❌ 无候选 |
| `BALLET_TENDU` | SEATED | — | — | — | — | — | — | — | ❌ 无候选 |
| `BALLET_WEIGHT_SHIFT` | SEATED / STANDING | — | — | — | — | — | — | — | ❌ 无候选 |

### SRC-PLIE-01 为什么被拒（`REJECTED_FOR_CLINICAL_USE`）

下载后生成逐秒 contact sheet 并**实际观看**，六项安全要求中三项不满足：

1. **全片没有任何椅子**。本站该动作只支持 `STANDING_SUPPORTED`，用自由站立的示范会让
   患者看到与实际任务不符的做法。
2. **双脚明显外旋成标准芭蕾第一位**。动作定义不要求外旋，给患者的提示是「双脚自然站立」。
3. **屈膝幅度属于中深蹲**，超过本动作要求的小幅屈膝范围。
4. 全片 12.649 秒中约 5 秒是标题卡与署名卡，不是动作画面。
5. 示范者穿深色宽松长裤，遮住本动作要测量的膝关节位置。

> 升级包的候选表本身就写着「一般 Plié 不一定有扶椅；如不符合安全版要求不可上线」。
> **看片确认了这个警告是对的**，这也是 SOP 要求先看片再决定裁剪段的意义所在。

### 本轮实际交付的媒体能力

不是「五段视频」，而是**一条真实、可验证、不会放错东西的媒体链路**：

- `frontend/src/ballet/demoAssets.json`——带真实审核结论的注册表（含 3 条 review 记录）。
- `frontend/src/ballet/demoAssets.ts`——纯函数解析器：**只有授权已核 AND 人工看片通过
  才返回 VIDEO**，否则返回 DIAGRAM 并说明原因。
- `frontend/src/ballet/ExerciseDemoPanel.vue`——有合格素材时播放
  `<video muted loop playsinline preload="metadata" :poster>`；没有时显示**明确标注为示意**
  的静态分解图，绝不拿别的动作的视频顶替。
- 版权署名入口（`demo-attribution`）已就位，等素材上线时自动显示作者 + 许可链接。
- **11 项测试**锁定：注册表当前 0 条可发布；两条门槛必须同时满足；被拒素材永不解析为视频；
  没有看过的候选不算审核通过；带视频路径却没过审核的条目会让构建失败。

**未做的、也不会做的**：不拿站姿视频冒充坐姿版；不把静态 SVG 说成真人视频；
不为凑「五段视频」而使用错误动作。

---

## 4. 钢琴训练扩展

### 4.1 四类新配方（模板，不是第二套引擎）

| ID | 名称 | 底层 mode | cue 策略 | 患者实际做什么 |
| --- | --- | --- | --- | --- |
| `SFT_CUE_SYNC` | 听提示按键 | `SINGLE_KEY_RHYTHM` | `FULL_CUE` | 每个提示都有画面与声音 |
| `CFT_RHYTHM_HOLD` | 保持节奏 | `FOLLOW_THE_BEAT` | `DEMONSTRATE_THEN_REMOVE` | 跟 8 拍提示，之后提示消失继续打 |
| `BIMANUAL_SYNC` | 双手同时敲击 | `SINGLE_KEY_RHYTHM` | `DUAL_CUE` | 一个提示要求左右手各按一键 |
| `ACCENT_GROUPING` | 强弱节拍分组 | `FOLLOW_THE_BEAT` | `ACCENT_GROUP` | 每 4 拍一组，第 1 拍重按 |

### 4.2 真的不一样（浏览器实测的 cue 流，24 拍）

| 配方 | 总 cue | 可见 | 撤除提示 | 双键 | 强拍 |
| --- | --- | --- | --- | --- | --- |
| SFT | 24 | 24 | 0 | 0 | 0 |
| **CFT** | 24 | 9 | **15** | 0 | 0 |
| **BIMANUAL** | 24 | 24 | 0 | **24** | 0 |
| **ACCENT** | 24 | 24 | 0 | 0 | **6** |

### 4.3 指标

保留全部原有指标。新增（仅在对应配方出现，其余为 NULL）：

- **CFT**：`cued_phase_accuracy`、`free_phase_accuracy`、`free_phase_timing_mae_ms`、
  `free_phase_interval_cv`、`free_phase_cue_count`。
- **BIMANUAL**：`inter_hand_sync_mean_ms`、`inter_hand_sync_sd_ms`、`inter_hand_pair_count`。
- **ACCENT**：`accent_hit_rate`、`accent_cue_count`。

**三条容易写错、且在 UI 上看不出来的规则（已测试锁定）：**

1. **CFT 撤提示后没有 cue onset，因此 `response_latency_ms` 必须为 null**，
   不能拿目标拍位硬补。`timing_error_ms` 保留。实测平均反应延迟 721 ms
   只来自有提示阶段的两拍。
2. **双手配对缺一只手时没有同步值**。报 0 ms 等于宣称一次没发生的按键完美同步。
3. **强拍属于「拍」而不是「手」**。两只手弹同一个强拍仍是一拍。

> 写指标测试时又发现自己代码里的第三处问题：普通轮次会输出一个
> `cued_phase_accuracy`，它其实就等于整体准确率，却挂着一个暗示跑过 CFT 的标题。
> 现在只有**确实存在两个阶段**时才输出拆分。

### 4.4 后端记录

- 迁移 `f2a4b6c8d0e1`：`piano_sessions.recipe_id`（可空）。**89 条既有会话未受影响**，
  列保持 NULL。可空是刻意的——旧记录与普通模式都没有配方，补一个值就是错误描述。
- 事件字段 `recipe_id` / `inter_hand_onset_diff_ms` / `pair_role` / `beat_in_bar` /
  `is_accent` 存入事件 JSON。
- 配方指标存入会话的 `server_metrics` 审计块（无需新列），实测可读回。

### 4.5 测试结果

- `frontend/tests/recipes.test.ts`：**27 项**（含 CFT latency=null、双手缺失手、
  强拍按拍计数、配方不改变目标时间、可复现性）。
- `backend/tests/test_piano_recipe_metrics.py`：**13 项**。

---

## 5. 微表情模型

**状态：BLOCKED。** 详见 `docs/upgrade-v2/model_readiness_report.md`。

- 磁盘证据：全仓库无任何权重文件；`adapter.py` 仅 8 497 B，`_infer()` 显式拒绝推理。
- PPT 提供的是论文方法与**原论文**实验数值，不是 checkpoint、标签表、依赖或输入规范。
- 已具备：单例与 `status()`、`MODEL_NOT_CONFIGURED`/`FAILED`/`NO_EVENT_DETECTED`
  三态区分、`MicroExpressionResult` 契约（非真实产出字段一律 None）、
  `MICRO_EXPRESSION_MODEL_DIR` 配置、不可用时的产品化表现（禁用按钮 + 「当前暂不可用」，
  **不绘制虚拟饼图**）。
- 需要你提供：源码、权重 + SHA256、标签映射、依赖版本、输入规范、
  两模型关系（串联还是一体化）、真实错误模型、输出语义、授权范围、
  3 段可重复测试视频。
- **不会做**：不训练替代模型、不用 MediaPipe blendshape 冒充 FG-LGL、
  不把原论文数值当平台性能、不把权重放进 Public GitHub。

---

## 6. API / DB / 兼容

| 项 | 结果 |
| --- | --- |
| 迁移 | **两次**：`f2a4b6c8d0e1`（加列 + 索引）与 `g3b5c7d9e1f2`（**改数据**：把已有的非真人钢琴基线置为非活动）。均可回滚 |
| 旧历史 | 89 条 piano 会话、全部 pose/评估记录未改动；`recipe_id` 为 NULL；11 条基线**一行未删** |
| 算法版本 | `ballet-exercises-v1.1.0`（因显示名与提示词变化而升版；key/指标/驱动关节/节拍/目标次数均未变）；`piano-recipe-v1.0.0` |
| `source_provenance` | 保留；本轮验证产生的 4 条探针记录已删除，其中 1 条曾被错误标为 `HUMAN_KEYBOARD` |
| 权限 | 未改：所有已登录工作人员一致，无管理员模块 |
| 发布状态 | 未部署 |
| 未破坏的合同 | `GET /api/movement/exercises?execution_mode=`、`/api/system/*` 保留 |

---

## 7. 完整代码改动与 Commit

```
分支 main
9343061  基线
ea509c8  fix: stop the ballet page escaping the deployment sub-path
b866bd6  feat: make result metrics follow the exercise, and align the action cards
8ed4cca  feat: gate ballet demonstration media behind a real review, and rename Demi-Plié
41f2b0e  feat: add four piano training recipes with their own interaction and data
```

**新增文件**

```
docs/upgrade-v2/UX_issue_inventory.md
docs/upgrade-v2/model_readiness_report.md
docs/upgrade-v2/asset_gap_report.md
docs/upgrade-v2/spec_decisions.md          （D01–D10）
docs/upgrade-v2/PROGRESS.md
docs/upgrade-v2/upgrade_report.md          （本文件）
frontend/src/pose/resultProfile.ts
frontend/src/ballet/demoAssets.json
frontend/src/ballet/demoAssets.ts
frontend/src/ballet/ExerciseDemoPanel.vue
frontend/src/piano/recipes.ts
frontend/tests/result_profile.test.ts
frontend/tests/demo_assets.test.ts
frontend/tests/recipes.test.ts
backend/tests/test_piano_recipe_metrics.py
backend/alembic/versions/f2a4b6c8d0e1_phase9_piano_training_recipe.py
```

**修改文件**

```
frontend/src/styles/main.css                 设计 token、卡片原语
frontend/src/styles/responsive.css           断点（未改数值）
frontend/src/main.ts                         （未改，token 在 main.css）
frontend/vite.config.ts                      代理目标改为可配置
frontend/tsconfig.app.json                   resolveJsonModule
frontend/tsconfig.test.json                  resolveJsonModule
frontend/package.json                        新增测试文件
frontend/src/api/index.ts                    recipe_id 字段
frontend/src/router/index.ts                 解除 /follow-up 的 hidden
frontend/src/pages/MovementTrainingPage.vue  空 id 守卫、动作卡重构、示范区、按动作指标
frontend/src/pages/PianoTrainingPage.vue     配方选择、配方指标行、网格 auto-fit
frontend/src/piano/session.ts                Cue/事件新字段、撤提示与双手解析
frontend/src/piano/useRunner.ts              接受并应用配方
backend/app/ml/pose/exercises.py             Demi-Plié 显示名与文案、定义版本升版
backend/app/schemas/piano.py                 recipe_id、事件新字段
backend/app/services/piano_service.py        持久化 recipe_id
backend/app/utils/piano_metrics.py           配方指标
backend/app/db/models/training.py            recipe_id 列
frontend/tests/ui_contract.test.ts           文案扫描改进（标签名不算文案）
```

`git status`：干净。

---

## 8. 测试原始结果

> 下表在第十二轮**更新为当前值**。第一轮/第二轮的数字保留在括号里作为轨迹。

| 命令 | 结果 |
| --- | --- |
| `pytest`（backend） | **327 passed / 0 failed / 0 errors**（第一轮 298 → 第二轮 303 → 现在 327） |
| `npm run test:rules` | **178 passed / 0 failed**（第一轮 149 → 第二轮 158 → 现在 178） |
| `npm run build` | ✅ 通过，无 TS 错误（默认 base 与 `VITE_BASE=/pd-rehab/` 均已构建通过） |

**浏览器验收**：17 条路由 × 7 种尺寸（1440×900、1366×768、1024×768、768×1024、
430×932、390×844、375×812）= **119 个组合**

- 最大横向溢出 **0 px**
- 手机端不出现桌面侧栏；≥768px 不出现汉堡按钮
- 无可见请求错误
- 覆盖了旧 URL 重定向（`/patients/:id/history`）与 404 页

**第十二轮补测**（前三轮新增的验证，逐项见 §8 之后的「验收标准逐条核对」）：

| 检查 | 结果 |
| --- | --- |
| 触屏目标（CDP 触屏模拟，开关前后各测一次） | 8 个页面 **<44px 的数量 0**（修复前 17 个） |
| 运行时按钮审计（8 页 / 16 个非破坏性按钮） | **0 个无反应、0 个报错、0 个 4xx** |
| 生产构建产物在 `/pd-rehab/` 子路径下 | 7 路由，**0 个 404、0 个失败请求、0 个页面级 JS 错误** |
| 后端不可达时的降级 | 完整外壳、`—` 而非 `0`、明确提示；**提示文案按构建分流**（生产不出现 `127.0.0.1:8000`） |
| 迁移链与回滚 | `upgrade head` / `downgrade base` / 往返 / `downgrade e8f1a3c5b7d9` **全部实跑通过** |

**本轮修掉的浏览器控制台错误**：U01 的 502（跨应用）——线上实测确认后修复。

### 钢琴双手配方的端到端实测

**真实浏览器驱动**，不是单测：

| 项 | 实测值 |
| --- | --- |
| 保存事件 | 43 条 |
| `pair_role` | 5 PRIMARY + 5 SECONDARY |
| 同步值 | `6, 6, 6, 6, 4, 4` ms |
| `inter_hand_sync_mean_ms` | **5.33** |
| `inter_hand_sync_sd_ms` | 0.94 |
| `inter_hand_pair_count` | 5 |

5.33 正是三条 PRIMARY 值 (6, 6, 4) 的平均，内部自洽。

### 验收标准逐条核对

> 本节在第十二轮**重写过**。上一版写于第二轮，数字已经过时，而且
> 「没有无效入口」那一行引用的证据**支撑不了它的结论**（见该行说明）。
> 表格只写我真的测过的东西；测不到的列在下面「证据的边界」里。

| # | 验收要求 | 证据 | 判定 |
| --- | --- | --- | --- |
| 1 | 所有同一行的卡片对齐 | 1440px 下同排 4 张卡：底边 / 媒体底 / 标题顶 / 按钮顶**四项偏差均为 0px**（预算 2px） | 通过 |
| 2 | **页面和按钮没有无效入口** | **静态**：`navigation.test.ts`（字面路径与命名路由对路由表校验、导航项与高亮分支一一对应、7 条旧 URL 仍重定向）。**运行时**：8 个页面 / **16 个非破坏性按钮**逐个点击，**0 个无反应、0 个报错、0 个 4xx** | 通过 |
| 3 | 手机端能够正常操作 | 17 路由 × 7 尺寸 = **119 组合，最差横向溢出 0px**；触屏模拟下 8 个页面**触控目标 <44px 的数量为 0**（修复前 17 个） | 通过 |
| 4 | 芭蕾卡片有封面 | 每张卡都有动作分解示意封面，并**明确标注为「示意」**，不冒充真人示范 | 通过 |
| 5 | **视频示范与患者摄像头明确分离** | 患者任务页两区：**动作示范**（标签随解析结果在「视频 / 示意」间切换）与**录制动作 · 您的动作**；桌面 2 列、手机堆叠且示范在前。播放器分支用一次性 fixture 实测：`muted` / `loop` / `playsinline` / poster 齐备，播放推进、暂停切换、署名链接正确 | 通过 |
| 6 | 钢琴新增训练确实可交互并保存 | 双手配方在真实浏览器跑通并入库：43 个事件（5 PRIMARY + 5 SECONDARY），同步值 6/6/6/6/4/4，均值 5.33ms | 通过（见边界） |
| 7 | 所有已存在的评估功能不回退 | pytest **327 项全绿**；Finger Tapping / Pose / 钢琴既有公式与阈值**未改动** | 通过 |
| 8 | 后端测试通过 | **327 / 0 failures / 0 errors** | 通过 |
| 9 | 前端测试和生产构建通过 | 规则与契约测试 **178 / 0**；`vue-tsc -b && vite build` 无 TS 错误 | 通过 |
| 10 | 浏览器无阻塞性错误 | **生产构建产物**（`VITE_BASE=/pd-rehab/`）在子路径下实测 7 条路由：**0 个 404、0 个失败请求、0 个页面级 JS 错误**；正文长度与开发服务器逐一相同 | 通过 |
| 11 | 部署前具备回滚方案 | 迁移链**实跑**：空库 `upgrade head` → `downgrade base` → 再 `upgrade head` → `downgrade e8f1a3c5b7d9`，`recipe_id` 确实消失。备份必须 WAL 感知（见 §9.1） | 通过 |

**第 2 行为什么要写两段证据。** 上一版只引用了 `navigation.test.ts`。
第十二轮实测发现：**那套测试检查的是静态路由目标，不检查运行时按钮是否真的有用**。
它能让「导航里没有死链」成立，但「按钮没有无效入口」需要真的去点。
补做的运行时审计结果见上表；**过程中我的工具两次报出假缺陷**（JS 点击点到了手机端
隐藏副本），已记入 `verification_notes.md`。

### 证据的边界（以下我**没有**验证）

写清楚，免得表格被读成比实际更强：

- **没有真机测试。** 全部是桌面浏览器 + 视口/触屏模拟。真机上的滚动惯性、
  软键盘顶起、iOS Safari 的媒体策略**均未验证**。
- **真实移动设备上的视频播放未验证。** 本机 Playwright Chromium **不含 H.264
  专有编解码器**，对 MP4 一律假阴性；真实 Chrome 已证实可播，**手机浏览器未测**。
- **未用真实患者数据做过端到端。** 本地库没有真人钢琴记录（4 条全在服务器上）；
  双手配方的 5.33ms 是**脚本按提示节拍按出来的**，证明链路正确，
  **不是任何患者的同步能力**。
- **面部表现分析从未跑通。** 模型不存在，患者模式没被真实走过。
- **芭蕾「接受结果」分支没出现过。** 没有任何一段视频通过审核。
- **趋势图表在本地库上永远是空的** —— 本地没有真人数据（界面现在会说明原因）。

**截图**：`docs/upgrade_screenshots/`（`before/` 35 张、`after/` 22 张，真实浏览器）。

---

## 9. 上线状态与回滚

**线上未更新。** 现在线上跑的是 `ed0fefe`。

原因：

1. 本轮含**两次**数据库迁移：`f2a4b6c8d0e1`（加列 + 索引）与
   `g3b5c7d9e1f2`（**修改数据**：把已存在的非真人钢琴基线置为非活动）。
   两者都可回滚，但按你的要求，生产环境的数据变更需要先确认。
2. 你已确认「视频素材等确认」，而芭蕾示范的上线形态与其有关。
3. nginx 侧按你的决定不动，代码侧修复已足够。

**回滚方案**（部署前已具备，迁移链已实跑验证）：

> ⚠️ **这个方案原先写错了，而且错在备份这一步。**
> 原第 1 步是 `cp /opt/pd-rehab/data/pd.db …`。**生产库处于 WAL 模式**
> （主库 471 KB，`-wal` 文件 4.16 MB，是主库的 8.8 倍），
> 后端进程长期持有它且从未 checkpoint —— **只拷主文件会静默丢掉已提交的数据。**
> 实测：`cp` 出来的副本读到 **88 行 / 3 条真人记录**，而数据库自己报 **89 / 4**。
> 备份看起来完全正常，却少了一条真实患者测量。
> 详见 `docs/server_deployment_plan.md` §9.1。

```bash
# 1. 备份数据库（WAL 感知 —— 不要用 cp）
#    VACUUM INTO 生成一个自洽的单文件副本，包含 WAL 里尚未合并的数据。
ssh fengz '/opt/pd-rehab/venv/bin/python -c "import sqlite3,datetime,os; d=\"/opt/pd-rehab/data/pd.db.bak-\"+datetime.datetime.now().strftime(\"%F-%H%M\"); c=sqlite3.connect(\"/opt/pd-rehab/data/pd.db\"); c.execute(\"VACUUM INTO ?\", (d,)); print(\"backup:\", d, os.path.getsize(d), \"bytes\")"'
#    替代方案：停服务后把 pd.db 与 pd.db-wal **一起**拷走（只拷主文件会丢数据）。

# 2. 代码回滚
ssh fengz "cd /opt/pd-rehab/app/PD-Rehab-Web && git reset --hard ed0fefe"

# 3. 迁移回滚
#    注意：g3b5c7d9e1f2 的 downgrade 是**有意的空操作** —— 它做的是数据订正，
#    重新激活那些基线会把缺陷装回去。所以回退到 e8f1a3c5b7d9 是安全且廉价的。
ssh fengz "/opt/pd-rehab/venv/bin/python -m alembic downgrade e8f1a3c5b7d9"

# 4. 重启
ssh fengz "systemctl restart pd-rehab-backend"
```

> 第 1 步的 `python -c` 一行式**已在本机等价验证过**（对本地 `data/pd.db` 执行，
> 生成的副本行数与源库一致，且不含 `-wal` 依赖）。

**这条链已经实跑过**（一次性空库）：`upgrade head` → `downgrade base` →
再 `upgrade head` → `downgrade e8f1a3c5b7d9`，且 `piano_sessions.recipe_id` **确实消失**。

**部署前我会先做**：记录服务器当前状态、**用 WAL 感知方式**备份 DB 与上传文件、
检查磁盘与 6 个服务、确认迁移在服务器 SQLite 上可执行，然后向你确认。

---

## 10. 尚未解决的真实问题 / 需要你提供的文件

| # | 问题 | 需要谁 |
| --- | --- | --- |
| 1 | **微表情模型源码 + 权重 + 标签表 + 依赖 + 输入规范 + 授权** | 老师 |
| 2 | **5 个芭蕾动作的康复安全审核意见**（哪些可放、哪些要改范围） | 老师 / 康复指导者 |
| 3 | 若要自录标准化教学片：一次拍摄（同机位、同服装、有无扶椅各一版） | 项目组 |
| 4 | `CC BY-SA 3.0` 素材的署名文字是否接受放在「资源来源/鸣谢」入口 | 你 |
| 5 | `SRC-TENDU-01` 下载被 Wikimedia 429 限流；需换网络或换源 | 无需人工，稍后重试 |
| 6 | 综合评估的七步 Stepper 仍未实现（上轮遗留） | 后续 |
| 7 | 功能测试（9-HPT）仍未实现，入口按设计要求保持隐藏 | 后续 |
| 8 | 趋势图仍无真实数据可画：演示库全部是种子/自检数据，按既有规则被排除 | 演示前需真人测两次以上 |
| 9 | 芭蕾「accepted result」分支仍无真实通过数据可验证 | 需一次合格录制 |
| 10 | 面部表现分析的患者模式仍未实测（模型未接入，按钮按设计禁用） | 取决于 #1 |

---

## 附：本轮没有做的事（明确记录）

- ❌ 没有新增管理员模块、角色管理、MRI、微服务、Redis/Celery、后台自训练模型。
- ❌ 没有删除任何数据库原始记录；没有把旧 Yoga 历史改名成 Ballet。
- ❌ 没有为了让页面好看而随机生成 0–100 展示分（继续为 NULL）。
- ❌ 没有用站姿视频冒充坐姿示范；没有把静态示意图说成真人视频。
- ❌ 没有修改 Finger Tapping / 钢琴 / Pose 的任何既有指标公式。
- ❌ 没有改动线上 nginx 配置。
