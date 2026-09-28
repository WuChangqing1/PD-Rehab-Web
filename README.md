# PD-Rehab-Web

**帕金森病智能辅助识别、运动状态量化与数字康复训练平台**

> **医疗声明**
> 本系统用于科研、辅助评估及康复训练展示，**不能替代专业医生诊断和标准临床量表**。
> 系统不产出医学诊断结论，不产出治疗建议，不产出"病情改善 X%"之类表述。

---

## 0. 在线 Demo（队友可直接访问）

| 入口 | 地址 | 摄像头 |
| --- | --- | --- |
| **推荐（HTTPS，可用摄像头）** | **https://ccqspace.site/pd-rehab/** | ✅ 可用 |
| 备用（纯 IP，HTTP） | http://110.42.236.65:18085/ | ❌ 不是安全上下文，浏览器禁用摄像头；只能上传视频文件 |

**登录账号：`admin` / `VZdTraIYAZnPGA`**

> 服务器上已生成 10 名**虚拟**演示患者（编号统一 `DEMO-` 前缀）以及评估、9-HPT、钢琴、动作训练记录，可直接浏览。
>
> **当前真实状态（不是占位，是如实显示）：**
> - 微表情 / AI 模型：**未配置**（老师模型尚未提供）→ 上传会返回 `503 MODEL_NOT_CONFIGURED`，不会伪造结果
> - Finger Tapping 分析：**不可用**（流水线属 Phase 4）→ 上传会返回 `501 NOT_IMPLEMENTED`
> - MediaPipe Hand Landmarker：**就绪**
> - MediaPipe Pose：**不可用**（指标属 Phase 6）
> - `DEMO_MOCK_MODE=false`，系统**不会**用模拟数据冒充真实结果
>
> 部署细节见 [`docs/server_deployment_plan.md`](docs/server_deployment_plan.md)。

---

## 1. 项目简介

面向医院 / 科研 / 比赛 Demo 的 Web 系统。核心不是"AI 检测一次 → 给结果 → 结束"，
而是形成长期闭环：

```text
医生登录
→ 选择患者
→ 综合评估（微表情 / AI 视频分析 + Finger Tapping 运动量化）
→ 建立个人 Baseline
→ 虚拟钢琴 / 节奏训练（Calibration + 3 轮自适应）
→ 简单动作 / 瑜伽训练（MediaPipe Pose）
→ 保存 Raw Data 与客观指标
→ 功能测试（9-HPT）
→ 历史趋势
→ 周期性复评
→ 调整训练
```

**产品原则：** 真实模型优先 · 可解释指标优先 · 原始数据优先 · 个人 Baseline 优先 ·
长期趋势优先 · 模块解耦 · 算法版本可追踪 · 医疗表述严谨 · Demo 主流程稳定 · 不过度工程化。

---

## 2. 系统截图

> 截图来自本地已运行的系统（虚拟演示数据，`scripts/seed_demo.py` 生成）。
> 界面刻意不使用大面积渐变与彩色色块，仅以医疗蓝作强调色。

### 工作台

![工作台](docs/images/dashboard.png)

顶部显示真实统计；**模型状态区如实显示「未配置 / 不可用 / 就绪」**。

### 登录

![登录](docs/images/login.png)

### 患者管理

![患者列表](docs/images/patients.png)

### 患者详情（六个 Tab）

![患者详情](docs/images/patient-detail.png)

### 综合评估

![综合评估](docs/images/assessment.png)

### 微表情 / AI 视频分析（模型未配置时的真实状态）

![微表情](docs/images/micro-expression.png)

### Finger Tapping（左右手分别分析 + 左右差异）

![Finger Tapping](docs/images/finger-tapping.png)

### 模型状态页

![模型状态](docs/images/model-status.png)

### 未实现功能的页面（占位，不显示任何示例数据）

![占位页](docs/images/trends-placeholder.png)


---

## 3. 当前开发进度

| Phase | 内容 | 状态 |
| --- | --- | --- |
| **0** | **环境与指标审计** | ✅ **已完成** |
| **1** | **项目骨架（FastAPI + Vue3 + SQLite + Alembic + Login + Layout）** | ✅ **已完成** |
| 2 | 患者管理（CRUD / 软删除 / 药物状态） | ✅ **已提前完成**（随 Phase 1 交付并通过测试） |
| 3 | 真实 AI / 微表情模型接入 | ⏸️ **阻塞**（老师模型未提供） |
| 4 | Finger Tapping（OpenCV + MediaPipe + 特征提取） | ⏳ 未开始 |
| 5 | 钢琴训练（Calibration + 4 模式 + 3 轮自适应） | ⏳ 未开始 |
| 6 | Pose 动作训练（5 动作） | ⏳ 未开始 |
| 7 | 功能测试（9-HPT） | ⏳ 未开始 |
| 8 | 趋势与报告 | ⏳ 未开始 |
| 9 | Demo 打磨与服务器部署 | 🔄 **已部署可访问**（打磨待续） |

### 线上部署状态（Phase 1 完成后已上线）

| 项 | 值 |
| --- | --- |
| 前端入口 A | `https://ccqspace.site/pd-rehab/`（HTTPS，Secure Context，**摄像头可用**） |
| 前端入口 B | `http://110.42.236.65:18085/`（HTTP/IP，摄像头不可用，仅文件上传） |
| 后端 | systemd `pd-rehab-backend`，仅监听 `127.0.0.1:18086`，单 worker，`MemoryMax=1500M` |
| Python | 3.11.16（用 `uv` 安装到 `/opt/pd-rehab/venv`；**系统 python3.10 未被改动**） |
| Node | v22.23.3 + npm 10.9.9（本阶段由 12.22.9 升级） |
| 代码位置 | `/opt/pd-rehab/app/PD-Rehab-Web` |
| 数据 / 模型 | `/opt/pd-rehab/data`、`/opt/pd-rehab/models`（**在代码树之外，重新部署不会清除**） |
| Nginx | 新增 `conf.d/pd-rehab.conf` 与 `snippets/pd-rehab-locations.conf`；仅在已有 443 块内追加一行 `include`（原文件已备份到 `/root/`） |
| 既有站点 | 5 个服务全部未受影响（已逐项验证端口与状态） |

> ⚠️ **服务器无法访问 GitHub**（`git clone` 报 SSL timeout）。部署通过 `git bundle` 经 SSH 传输，
> 完整步骤见 [`docs/server_deployment_plan.md`](docs/server_deployment_plan.md) §8.1。

### Phase 1 已交付内容

**后端**（`backend/`，pytest 94 项全部通过）

- FastAPI 应用 `app/main.py`：lifespan 启动时**一次性**加载模型、初始化数据库、创建首个管理员
- 统一错误结构 `{error:{code,message,detail}}`，含 `MODEL_NOT_CONFIGURED` 等稳定错误码
- JWT 认证（bcrypt 直接调用，规避 passlib 与 bcrypt 4.1+ 的兼容问题）
- **13 张表**的 SQLAlchemy 2.0 ORM 模型 + Alembic 首个迁移
- 按 V2 §48 实现的 API：Auth / Patients / Assessment Sessions / Micro Expression / Finger Tapping / System / Jobs（共 18 个路径）
- 模型 Adapter 骨架：`micro_expression`（返回 `MODEL_NOT_CONFIGURED`）、`finger_tapping`（Phase 4 占位，抛 `NOT_IMPLEMENTED`）、`pose`（五个动作定义，展示分公式留空）
- `GPUInferenceManager`：并发度 1，GPU 与 CPU 行为一致
- Job 机制：`PENDING / RUNNING / SUCCESS / FAILED`，无 Redis / Celery
- 指标原语 `app/utils/metrics.py`：CV、slope、左右差异、中断计数，**NaN / Inf 永不外泄**

**前端**（`frontend/`，`npm run build` 无 TypeScript 错误）

- Vue 3 + TypeScript + Vite + Vue Router + Pinia + Axios + Element Plus + ECharts
- Header + Sidebar + 主工作区布局；白 / 浅灰底，医疗蓝少量强调
- **全部 17 条路由**均已实现；未实现的功能渲染明确占位页，**不显示任何示例数据**
- 摄像头能力探测（`isSecureContext` + `getUserMedia`），不安全上下文下禁用并说明原因
- 每个页面固定医疗声明；不存在「确诊 / 治愈 / 治疗成功」等表述

**脚本**（`scripts/`）

- `bootstrap.ps1` 一键初始化（依赖 / .env / 迁移 / 测试）
- `run_backend.ps1`、`run_frontend.ps1`
- `seed_demo.py` 生成 10 名**虚拟**患者（编号统一 `DEMO-` 前缀）
- `check_models.py` 只读环境 / 模型 / 外部仓库探测器

Phase 0 产出文档：

- [`docs/environment_report.md`](docs/environment_report.md) —— 环境 / GPU / 外部仓库 / 服务器审计
- [`docs/metric_definitions.md`](docs/metric_definitions.md) —— **指标定义主文档**
- [`docs/model_integration.md`](docs/model_integration.md) —— Adapter 接口与模型接入设计
- [`docs/server_deployment_plan.md`](docs/server_deployment_plan.md) —— 服务器只读审计与部署方案
- [`docs/spec_conflicts.md`](docs/spec_conflicts.md) —— 两份规格的冲突与合并裁定

---

## 4. 技术栈

### Backend

```text
Python 3.11
FastAPI
PyTorch
MediaPipe
OpenCV
NumPy / SciPy / Pandas / scikit-learn
SQLAlchemy + Alembic
SQLite（开发） / MySQL（可切换）
```

### Frontend

```text
Vue 3 + TypeScript
Vite
Vue Router
Pinia
Axios
Element Plus
ECharts
Web Audio API
MediaDevices / getUserMedia
```

### 第一版明确不引入

```text
Redis · Celery · Kafka · 微服务 · Kubernetes · 强力 MIDI 硬件依赖
```

---

## 5. 目录结构

```text
PD-Rehab-Web/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/                 # auth, patients, assessment_sessions, assessments,
│  │  │                       # training, functional_assessments, reports, jobs, system
│  │  ├─ core/                # config, security, logging
│  │  ├─ db/                  # session, base, models/
│  │  ├─ schemas/
│  │  ├─ services/            # patient/assessment/piano/pose/trend/report service
│  │  ├─ ml/
│  │  │  ├─ micro_expression/ # adapter.py, schemas.py, errors.py
│  │  │  ├─ finger_tapping/   # adapter, feature_extractor, quality, signal, schemas
│  │  │  └─ pose/             # analyzer, exercises, metrics
│  │  ├─ jobs/                # manager.py, gpu_inference.py
│  │  └─ utils/
│  ├─ alembic/
│  ├─ tests/
│  └─ requirements.txt
├─ frontend/
│  ├─ src/                    # api, components, layouts, pages, router, stores, styles, utils
│  └─ package.json
├─ data/
│  ├─ uploads/   (Git 忽略)
│  ├─ outputs/   (Git 忽略)
│  ├─ reports/   (Git 忽略)
│  └─ demo/      # 可入库的 Demo 数据 / 审计产物
├─ models/       (Git 忽略；私有模型放这里)
├─ docs/         # 5 份 Phase 0 文档 + 后续 api_decisions.md
├─ scripts/      # bootstrap / run_backend / run_frontend / check_models / seed_demo
├─ deploy/       # nginx / systemd 部署配置（已在实际服务器使用）
├─ .env.example
├─ .gitignore
├─ NOTICE        # 第三方代码与模型来源声明
└─ README.md
```

---

## 6. 环境准备

### 6.1 Conda 环境

**已存在的环境，无需重新创建：**

```powershell
conda activate pd
python --version     # 必须输出 Python 3.11.16
```

| 项 | 值 |
| --- | --- |
| 环境名 | `pd` |
| Python | **3.11.16** |
| 路径 | `D:\App\Business\Coding\Python\Miniconda\envs\pd\python.exe` |

> ⚠️ `.condarc` 设置了 `auto_activate: false`，且系统默认 `python` 是 **3.13.12**。
> 每次新开 shell 都必须显式 `conda activate pd`，否则会误用错误解释器。

### 6.2 Backend 依赖

```powershell
conda activate pd
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

### 6.3 PyTorch（**必须单独安装**）

PyTorch **不在** `requirements.txt` 中，因为 wheel 的 CUDA 版本必须与 GPU 架构匹配。

本机 GPU 是 **RTX 5070 Laptop（Blackwell，compute capability 12.0 / sm_120）**：

```powershell
# 首选：CUDA 13.0 运行时（PyTorch 官方矩阵显式覆盖 Blackwell sm_120）
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130

# 备选：CUDA 12.8 运行时
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

> ⛔ **禁止安装 cu126 或更低版本**：这些构建**不含 sm_120 kernel**。
> 典型症状是 `torch.cuda.is_available()` 返回 `True`，但第一个 CUDA kernel 就报
> `no kernel image is available for execution on the device`。
>
> ⛔ **禁止寻找 / 安装 "cu133"**：官方不存在该 wheel。驱动显示 `CUDA UMD 13.3` 只代表
> 驱动能力上限，**向下兼容** cu128 / cu130 运行时。

验收：

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"

# 真实 kernel 冒烟测试（排除"可用但无 kernel"的假阳性）
python -c "import torch; a=torch.randn(64,64,device='cuda'); print((a@a).sum().item()); print('KERNEL_OK')"
```

### 6.4 Node / 前端依赖

```powershell
node --version    # 需 >= 18（本机 v22.19.0 ✅）
npm --version     # 本机 10.9.3 ✅

cd frontend
npm install
```

---

## 7. 老师微表情模型配置

### 7.1 当前状态：`MODEL_NOT_CONFIGURED`

模型源码目录、checkpoint、入口函数、标签字典、`requirements` **均未提供**。
系统在此状态下：

- ✅ 正常启动
- ✅ 页面明确显示「微表情 / AI 模型：**Unavailable**」
- ✅ 调用分析接口返回 **HTTP 503 `MODEL_NOT_CONFIGURED`**
- ❌ **绝不伪造标签、概率或截图百分比**
- ❌ **绝不自行训练替代模型**
- ❌ **绝不后台静默返回 Mock**

### 7.2 配置方式

在 `.env` 中设置（**拿到模型后**）：

```env
MICRO_EXPRESSION_MODEL_DIR=./models/micro_expression
MICRO_EXPRESSION_ENTRY=
MICRO_EXPRESSION_CHECKPOINT=
MICRO_EXPRESSION_DEVICE=
```

模型目录约定（**不入 Git**）：

```
models/micro_expression/
├─ README.md          # 来源、论文、输入规范、标签字典、许可
├─ requirements.txt   # 真实依赖（决定 torch/CUDA 版本）
├─ labels.json        # 真实标签字典
├─ <checkpoint>.pt
└─ <inference code>
```

完整接入清单见 [`docs/model_integration.md`](docs/model_integration.md) §8。

---

## 8. Finger Tapping 外部仓库配置

外部算法仓库（**只读，不修改**）：

```text
D:\CodingData\Github\VideoBased-PD-Biomarkers
```

```env
FINGER_TAPPING_REPO_DIR=D:/CodingData/Github/VideoBased-PD-Biomarkers
HAND_LANDMARKER_PATH=./models/mediapipe/hand_landmarker.task
```

MediaPipe HandLandmarker 模型文件（Apache-2.0）可从外部仓库复制：

```powershell
New-Item -ItemType Directory -Force -Path models\mediapipe | Out-Null
Copy-Item "D:\CodingData\Github\VideoBased-PD-Biomarkers\src\demo\hand_landmarker.task" models\mediapipe\
# sha256 应为 fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1
```

来源与复用判定见 [`NOTICE`](NOTICE) 与 [`docs/model_integration.md`](docs/model_integration.md) §2.4。

> ⚠️ **重要**：该外部仓库**没有**预训练严重度分类模型，且
> `optimization_training.py` **不保存模型、无推理入口**。
> 因此 `severity_score` / `severity_label` **恒为 `NULL`**。

---

## 9. 环境变量

```powershell
Copy-Item .env.example .env
```

**必须至少修改：**

| 变量 | 说明 |
| --- | --- |
| `JWT_SECRET` | 改成随机值：`python -c "import secrets; print(secrets.token_hex(32))"` |
| `BOOTSTRAP_ADMIN_PASSWORD` | 首次启动创建的 admin 密码 |
| `DATABASE_URL` | 开发默认 `sqlite:///./data/pd.db` |
| `USE_GPU` | 有可用 CUDA 时 `true`，否则 `false` |
| `DEMO_MOCK_MODE` | **保持 `false`**。只有显式设为 `true` 才允许 Mock，且页面会标记 `DEMO DATA` |

完整变量说明见 [`.env.example`](.env.example)。

> 🔒 `.env` 已在 `.gitignore` 中，**绝对不得提交**。

---

## 10. 数据库初始化

```powershell
conda activate pd
cd backend
alembic upgrade head          # 应用迁移
alembic revision --autogenerate -m "init"   # 生成新迁移（改模型后）
```

开发库：SQLite `data/pd.db`（Git 忽略）。

**切换 MySQL**（无需改代码）：

```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/pd_rehab?charset=utf8mb4
```

---

## 11. 如何启动 Backend

```powershell
conda activate pd
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API 根：`http://127.0.0.1:8000/api`
- Swagger：`http://127.0.0.1:8000/docs`

> ⚠️ `--reload` **仅用于开发**。生产 / 服务器必须用 systemd（见
> [`docs/server_deployment_plan.md`](docs/server_deployment_plan.md) §5），
> 规格明确禁止长期运行 `uvicorn --reload`。

## 12. 如何启动 Frontend

```powershell
cd frontend
npm run dev
```

浏览器打开：`http://localhost:5173`

> 💡 `localhost` / `127.0.0.1` 属于 **Secure Context**，摄像头录制功能可用。
> 若通过 `http://<局域网IP>:5173` 访问，浏览器会禁用 `getUserMedia`。

---

## 13. 如何运行测试

### Backend

```powershell
conda activate pd
cd backend
pytest -v
```

覆盖范围（V2 §63 + 任务书第三十三条）：

```text
patient CRUD
assessment session
micro-expression schema
finger-tapping feature schema
finger-tapping QC
CV 计算
left-right difference
piano raw event
piano metrics
difficulty engine
pose metrics
functional assessment CRUD
trend aggregation
```

### Frontend

```powershell
cd frontend
npm run build     # 必须无 TypeScript build error
```

### 环境自检

```powershell
conda activate pd
python scripts/check_models.py                       # 环境 / 模型 / 外部仓库状态
python scripts/check_models.py --video path\to.mp4   # 附带视频元数据探测
```

---

## 14. Demo 账号

> 首次启动时由后端自动创建（依据 `.env` 的 `BOOTSTRAP_ADMIN_*`）。

| 角色 | 用户名 | 密码 | 说明 |
| --- | --- | --- | --- |
| ADMIN | `admin` | 由 `BOOTSTRAP_ADMIN_PASSWORD` 决定 | 首次登录后请立即修改 |

虚拟患者数据由 `scripts/seed_demo.py` 生成（**Phase 2 交付**）：

```powershell
conda activate pd
python scripts/seed_demo.py
```

生成约 **10 名虚拟 / 脱敏患者**，覆盖不同年龄、左右受累侧、`ON` / `OFF` / `UNKNOWN` 药物状态。

> 🚫 **绝不使用真实患者资料。** 不写死真实身份证号；上传文件名一律使用 UUID。

---

## 15. 页面路由

```text
/login
/dashboard
/patients
/patients/new
/patients/:id
/patients/:id/edit
/patients/:id/assessment
/patients/:id/assessment/micro-expression
/patients/:id/assessment/finger-tapping
/patients/:id/training
/patients/:id/training/piano
/patients/:id/training/movement
/patients/:id/history
/patients/:id/trends
/patients/:id/functional-assessment
/patients/:id/report
/system/model-status
```

---

## 16. 已知限制

### 16.1 模型相关

| # | 限制 | 说明 |
| --- | --- | --- |
| L1 | **微表情 / AI 模型未接入** | 老师模型目录 / checkpoint / 入口 / 标签字典 / requirements 均未提供。当前 `MODEL_NOT_CONFIGURED`，接口返回 503 |
| L2 | **无严重度分级** | 外部仓库不存在预训练严重度分类模型。`severity_score` / `severity_label` **恒为 NULL**。第一版只输出真实运动学指标 |
| L3 | **`avg_landmark_confidence` 恒为 NULL** | MediaPipe **Tasks API** 的 `NormalizedLandmark` 不提供 `visibility`/`presence`。规格示例值 `0.88` 不可真实获得，**不填占位值** |
| L4 | **`tapping_frequency` 为新增派生指标** | 外部仓库无该字段。新项目按 `(peaks-1)/span` 与 `1/avg_cycle_duration` 两种口径并行计算，Phase 4 用真实视频固化 |

### 16.2 手别与手指

| # | 限制 | 说明 |
| --- | --- | --- |
| L5 | **MediaPipe 手别约定待验证** | `handedness` 按镜像（前置摄像头）约定输出，可能与解剖手别相反。外部仓库未纠正，本系统在 Phase 4 用真实视频验证 |
| L6 | **钢琴"手指"是任务映射，不是真实手指识别** | 普通键盘只能知道"要求按哪个映射键"，**无法确认患者实际用了哪根生理手指**。`weak_finger_error_rate` 等指标必须标注该限制 |

### 16.3 指标边界

| # | 限制 | 说明 |
| --- | --- | --- |
| L7 | **`timing_error_cv` 可能不稳定** | `timing_error` 均值可能接近 0（提前与滞后互相抵消），CV 会爆炸。系统在 `\|mean\| < 1e-9` 时返回 `null` |
| L8 | **`*_slope` 自变量是 cycle index 而非时间** | 单位是"每周期变化量"，不是"每秒变化量"。前端已注明 |
| L9 | **斜率不代表病情变化** | 只描述"单次任务内部是否出现持续变化趋势"，**禁止**解释为病情加重 / 改善 |
| L10 | **左右差异不得用于判断疾病侧别** | 只作为运动表现差异展示 |
| L11 | **微表情标签占比不得当作严重程度** | 也不得用于调整钢琴训练难度 |
| L12 | **Pose 展示分需要先定义公式** | 公式未固化前（`metric_definitions.md` §3.4 标 `TBD` 的项），Score **不入库、不展示**；只有原始角度指标可用 |

### 16.4 功能范围

| # | 限制 | 说明 |
| --- | --- | --- |
| L13 | **第一版不接 MIDI** | 因此**没有力度 / velocity 指标**，且**不伪造**力度数据 |
| L14 | **BBT / MDS-UPDRS / PDQ-39 仅保留数据结构** | 第一版 UI 只实现 9-HPT。**系统不自动生成 MDS-UPDRS 等临床评分** |
| L15 | **不做**：MRI、自动医学诊断、药物推荐、自动治疗决策、聊天机器人、远程视频问诊、移动 App | — |

### 16.5 部署相关

| # | 限制 | 说明 |
| --- | --- | --- |
| L16 | **服务器无 GPU** | `ssh fengz` 服务器为 Ubuntu 22.04 / 4 vCPU / **3.6 GiB RAM（无 swap）** / 无 GPU。推理只能 CPU + 单并发 |
| L17 | **服务器纯 IP 访问无法使用摄像头** | `http://110.42.236.65:18085` 不是 Secure Context，`getUserMedia` 不可用 → **服务器 Demo 走「本地 MP4 上传」路径** |
| L18 | **服务器已升级 Node 22** | 原为 Node 12 且无 npm，Phase 1 已升级到 **Node 22.23.3 + npm 10.9.9**，服务器可直接构建前端（已实测）。⚠️ 但服务器**无法访问 GitHub**，部署需经 SSH 传输（见部署文档 §8.1） |
| L19 | **新端口需安全组放行** | 计划使用 **18085**（前端）/ **18086**（后端，仅回环），需在腾讯云控制台放行 18085 |

详见 [`docs/server_deployment_plan.md`](docs/server_deployment_plan.md) 与
[`docs/spec_conflicts.md`](docs/spec_conflicts.md) §5。

---

## 17. 数据安全红线

**Public 仓库中绝对禁止出现：**

```text
真实患者视频 / 身份信息 / 身份证号
医院私有数据
老师模型权重 / 私有 checkpoint
.env / JWT Secret
SQLite DB / MySQL dump
data/uploads · data/outputs · data/reports
*.pt  *.pth  *.ckpt  *.onnx  *.engine
```

**上传文件必须使用 UUID 文件名**，例如 `a3f1c8e2-....mp4`，
**不得**使用 `张三_帕金森.mp4` 这类名称。

存储路径约定：

```text
data/uploads/{patient_uuid}/{YYYY-MM-DD}/{uuid}.mp4
data/outputs/{assessment_uuid}/           # annotated.mp4 / preview.jpg / metrics.json / timeseries.npz
```

---

## 18. 授权与第三方来源

- 本项目自有代码：见 [`LICENSE`](LICENSE)（待定）
- 第三方代码 / 模型来源与许可：见 [`NOTICE`](NOTICE)
- Finger Tapping 算法来源：Zarrat Ehsan et al., *Interpretable and Granular Video-Based
  Quantification of Motor Characteristics from the Finger Tapping Test in Parkinson's Disease*,
  **npj Parkinson's Disease**, 2026. DOI [10.1038/s41531-026-01307-w](https://doi.org/10.1038/s41531-026-01307-w)
  （Apache-2.0）

---

> 本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。
>
> 训练页面固定提示：**请在医生或工作人员指导下完成。如出现疼痛、头晕或明显不适，请立即停止。**
