# P0 · UX 问题清单（真实源码 + 线上站点 + 本地实测）

审计时间：2026-10-12
审计对象：`PD-Rehab-Web` @ `9343061`（工作树干净，本地 = `origin/main`）
线上：`https://ccqspace.site/pd-rehab/`（已用真实浏览器登录并逐页点击）
本地：backend `127.0.0.1:8010` + Vite `127.0.0.1:5173`（用于对照与复现）
截图：`docs/upgrade_screenshots/before/`（34 张，7 种屏宽）

---

## 0. 审计方法

1. `git status` / `git log` / `git ls-remote` 确认工作树与线上版本。
2. 真实浏览器（Playwright/Chromium）访问线上站点，登录后逐页点击，
   记录 Console、XHR、图片、视频、按钮与布局矩形。
3. 本地起同一份源码，复现线上现象，区分「代码缺陷」与「部署/环境问题」。
4. 静态审查升级包点名的文件，核对与文档描述是否一致。

---

## 1. 本轮新发现的真实缺陷（升级包未列出）

### U01 —— P0 · 芭蕾页在未选患者时打出跨应用 502

**这是本次审计最重要的发现，升级包中没有。**

线上实测，访问 `/pd-rehab/training/movement`（未带 `patientId`）时浏览器发出 4 个请求：

```
/pd-rehab/api/auth/me                     200
/pd-rehab/api/patients/                   307  ← 空 id
/pd-rehab/api/patients?page=1&page_size=20 200
https://ccqspace.site/api/patients        502  ← 逃出子路径
```

**根因链（已逐段实测确认）：**

1. `MovementTrainingPage.load()` 无条件执行
   `patient.value = await patientApi.get(patientId.value)`；
   未选患者时 `patientId.value` 是空字符串，于是请求 `/api/patients/`。
2. FastAPI 的 `redirect_slashes` 把带尾斜杠的路径 307 重定向到不带尾斜杠的路径。
3. 它**按自己看到的路径**构造 `Location`。nginx 用 `proxy_pass …/` 已经把 `/pd-rehab`
   前缀剥掉，所以后端看到的是 `/api/patients/`，于是
   `location: https://ccqspace.site/api/patients`——**前缀丢失**。
4. 站点根路径的 `location /api/` 属于**另一个项目的 server block**
   （`/etc/nginx/conf.d/mysite.conf` → `127.0.0.1:8080`），该服务未运行，返回 502。

服务器实证：

```
GET /pd-rehab/api/patients/  → 307  location: https://ccqspace.site/api/patients
GET /api/patients            → 502
grep location /api/ /etc/nginx/conf.d/*.conf
  mysite.conf:62                      ← 根路径，另一个项目
  pd-rehab.conf:71                    ← 我们的
  smoking-monitor.conf:77             ← 另一个项目
  smoking-monitoring-system.conf:66   ← 另一个项目
```

**影响**：控制台出现跨应用错误；同一页面的其它请求正常，所以数据仍能显示，
属于「不致命但真实、且会让运维误判成后端故障」的缺陷。

**已修复**（代码侧）：`MovementTrainingPage.load()` 现在在 `patientId` 为空时
不请求患者，也不请求历史；动作目录与阈值仍加载（它们不依赖患者）。

**未修复（需要你决策）**：nginx 侧仍会让任何带尾斜杠的子路径请求逃出 `/pd-rehab`。
彻底堵住有两种做法，都会动到线上配置，**等确认后再做**：
- (a) 后端关闭 `redirect_slashes`（或注册带尾斜杠的显式路由）；
- (b) 在 `pd-rehab.conf` 的 proxy 块里用 `proxy_redirect` 重写 `Location` 前缀。

同一缺陷模式我在全项目扫描过一遍：只有 `MovementTrainingPage` 一处；
`TrainingHubPage.loadBaseline()` 有 `if (!patientId.value) return` 守卫，
`PianoTrainingPage` 用 `watch(hasPatient, …)` 门控，其余页面都在选定患者之后才调用。

### U02 —— P1 · `/follow-up` 的 `hidden` 元数据与主导航自相矛盾（= 升级包 G05，已确认）

实测 `router.getRoutes()`：

```
/follow-up                  hidden: true    ← 但侧栏第五项就是它
/functional-assessment      hidden: true    ← 这个才是应该隐藏的
```

`hidden` 在别处没有任何消费者，所以当前不影响渲染，但它是一句**错误的声明**，
且升级包明确要求解除。**待修**：`/follow-up` 去掉 `hidden`，功能测试保留。

### U03 —— P1 · 芭蕾结果卡片对腿部动作显示肩角度（= 升级包 G04，已确认）

`MovementTrainingPage.vue:198` 的 `summaryCards` 是写死的四项：

```js
{ label: '抬起角度', value: `左 ${metricText('left_shoulder_max_angle_deg')} · 右 ${…}` }
{ label: '动作速度', value: metricText('movement_speed_deg_per_sec') }
```

而 Tendu / Demi-Plié 是**腿部**动作。后端其实已经按动作声明了驱动关节：

| 动作 | `drive_series` | 现卡片显示 |
| --- | --- | --- |
| `BALLET_PORT_DE_BRAS` | `DRIVE_SHOULDER` | 肩角度 ✅ |
| `BALLET_FIRST_POSITION` | `DRIVE_SHOULDER` | 肩角度 ✅ |
| `BALLET_TENDU` | `DRIVE_HIP` | **肩角度 ❌** |
| `BALLET_DEMI_PLIE` | `DRIVE_KNEE` | **肩角度 ❌** |
| `BALLET_WEIGHT_SHIFT` | `DRIVE_TRUNK_TILT` | **肩角度 ❌** |

后端已为腿部动作补充了 `left/right_knee_max_angle_deg`、`left/right_hip_abduction_deg`
（`_LEG_RAW_METRICS`，加法式，未改动既有定义）。**待修**：按 `drive_series` 生成卡片。

### U04 —— P2 · 芭蕾动作卡没有 CTA 按钮

实测 4 张动作卡矩形完全一致（top 503 / bottom 757 / h 254 / SVG 110），
说明等高没问题；但 `ctaTop` 全部为 `null`——**卡片内没有任何按钮**。
升级包 doc 03 要求「按钮『查看动作』」，且 doc 02 的等高规范以 CTA 行对齐为前提。
**待修**：补 CTA，并按 `margin-top:auto` 对齐。

---

## 2. 升级包列出、经核实确实存在的问题

| ID | 核实结果 | 证据 |
| --- | --- | --- |
| G01 微表情无权重 | ✅ 属实 | 全仓库无任何 `.pth/.pt/.onnx/.ckpt`；`adapter.py` 显式 `MODEL_NOT_CONFIGURED` |
| G02 无示范视频 | ✅ 属实 | 动作卡 `hasMedia: 0`、`svgFigures: 4`；`public/` 下无 ballet 媒体 |
| G03 训练非统一状态机 | ✅ 属实 | 现为「选动作 → 采集 → 分析」，无 PREVIEW/COUNTDOWN 分离 |
| G04 指标与动作失配 | ✅ 属实 | 见 U03 |
| G05 `hidden` 语义冲突 | ✅ 属实 | 见 U02 |
| G06 钢琴缺分级配方 | ✅ 属实 | `session.ts` 仅 5 个 mode，无 SFT/CFT/同步/重音 |
| G07 卡片对齐/响应式 | ⚠️ 部分已解决 | 训练中心 2 卡 `bottomSpread: 0`、`ctaSpread: 0`；芭蕾 4 卡矩形一致。剩余问题在 U04 与详情页 |
| G08 技术性文案 | ⚠️ 大部分已清理 | 上轮已清；本轮扫描确认普通页面无 Demo/科研/Phase/虚拟 |
| G09 provenance 混算 | ✅ 已有机制 | `input_source` + 趋势层过滤，未发现混算 |
| G10 视频制作链不存在 | ✅ 属实 | 无 manifest 消费者、无 ffmpeg 流程 |
| G11 子路径媒体 | ⚠️ 未知，待 P2 实测 | 尚无媒体文件可测 |
| G12 手机钢琴/摄像头冲突 | ⚠️ 部分 | 琴键已 pointerdown + 可滚动；示范视频与摄像头并存尚未实现 |

---

## 3. 线上站点实测结论（真实浏览器）

- **可达**：`https://ccqspace.site/pd-rehab/` 登录、工作台、患者档案、评估中心、
  康复训练、随访与报告全部正常打开，5 项主导航一致。
- **Console**：仅 U01 的 502，无其它错误。
- **布局**：11 页面 × 7 尺寸横向溢出均为 0（上一轮成果保持）。
- **截图**：`docs/upgrade_screenshots/before/` 34 张。
- **注意**：截图使用演示账号，患者为演示库记录；未修改任何真实数据。

---

## 4. 优先级

| 级别 | 项 | 阶段 |
| --- | --- | --- |
| P0 | U01 空 id 跨应用 502（代码侧已修，nginx 侧待决策） | P0 ✅ |
| P1 | U02 `hidden` 语义、U03 按动作的结果指标、U04 动作卡 CTA | P1 |
| P1 | G07 剩余对齐、G08 收尾 | P1 |
| P2 | G02/G03/G10/G11 芭蕾媒体闭环与状态机 | P2 |
| P3 | G06 钢琴四类新配方 | P3 |
| P4 | G01 微表情（阻塞，等老师资源） | P4 |
| P5 | 回归、性能、部署与回滚 | P5 |
