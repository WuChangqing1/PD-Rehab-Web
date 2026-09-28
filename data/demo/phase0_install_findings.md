# Phase 0 依赖安装校验发现（install findings）

> 项目：PD-Rehab-Web
> 生成阶段：Phase 0（**本轮未实际安装任何依赖**，以下均为元数据级校验结论）
> 关联文档：`docs/environment_report.md` §3.4、`backend/requirements.txt`

本文件记录 Phase 0 在确定 `backend/requirements.txt` 版本时**实际发现的问题**，
以便 Phase 1 安装时不再踩坑。所有结论都有可复现的校验方法。

---

## 1. PyTorch 版本与 sm_120（**最高优先级**）

| 项 | 结论 |
| --- | --- |
| 本机 GPU | NVIDIA GeForce RTX 5070 Laptop GPU |
| Compute capability | **12.0（Blackwell / sm_120）** |
| 驱动 | 610.47，CUDA UMD 13.3 |
| 本机 CUDA Toolkit | 12.8.93（`nvcc`，`C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8`） |

**官方支持矩阵（`pytorch/pytorch` RELEASE.md，2.14）Windows 构建：**

| CUDA | 支持的架构 | 含 sm_120？ |
| --- | --- | --- |
| 12.6.3 | Maxwell 5.0 … Hopper 9.0 | ❌ **否** |
| 13.0.3 | Turing 7.5 … **Blackwell 10.0, 12.0+PTX** | ✅ 是 |
| 13.2.1 | 同上 | ✅ 是 |

**已在官方 wheel 索引核实（`cp311` + `win_amd64`）：**

| 索引 | 可用最新版 |
| --- | --- |
| `cu130` | `2.14.0+cu130`（另有 2.9.0 起各版本） |
| `cu128` | `2.11.0+cu128` |
| `cu126` | `2.14.0+cu126` ← **存在但不能用** |

**决定：**

```powershell
# 首选
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130
# 备选（若老师模型对 12.x 有硬约束）
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

**禁止**安装 `cu126`（`is_available()` 可能返回 `True`，但第一个 kernel 就报
`no kernel image is available for execution on the device`）。
**禁止**寻找 `cu133`（官方不存在；驱动 UMD 13.3 向下兼容 12.8/13.0 运行时）。

**必须做的真实 kernel 冒烟测试**（排除假阳性）：

```powershell
python -c "import torch; print(torch.__version__, torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
python -c "import torch; a=torch.randn(256,256,device='cuda'); print(float((a@a).sum())); print('KERNEL_OK')"
```

---

## 2. OpenCV 家族冲突（**已通过校验发现并规避**）

### 现象

`mediapipe==1.0.1` 的依赖中包含 **`opencv-contrib-python`**。
如果 `requirements.txt` 同时写 `opencv-python`，两个发行版会向 site-packages
写入**同一批 `cv2/` 文件**。

### 实测数据（通过读取 wheel 的 ZIP 中央目录，仅下载各 wheel 尾部字节）

| wheel | 大小 | 顶层目录 | 文件数 |
| --- | --- | --- | --- |
| `opencv_python-5.0.0.93-cp37-abi3-win_amd64.whl` | 44,000,345 B | `cv2/`, `opencv_python-5.0.0.93.dist-info/` | 46 |
| `opencv_contrib_python-5.0.0.93-cp37-abi3-win_amd64.whl` | 53,822,579 B | `cv2/`, `opencv_contrib_python-5.0.0.93.dist-info/` | 110 |

**共同（会被互相覆盖）的文件路径：40 个**，按扩展名分布：

| 扩展名 | 数量 | 代表 |
| --- | --- | --- |
| `.pyi` | 23 | `cv2/__init__.pyi`、`cv2/aruco/__init__.pyi` … |
| `.py` | 12 | `cv2/__init__.py`、`cv2/config.py`、`cv2/misc/version.py` … |
| `.txt` | 2 | `cv2/LICENSE.txt`、`cv2/LICENSE-3RD-PARTY.txt` |
| `.typed` | 1 | `cv2/py.typed` |
| **`.pyd`** | **1** | **`cv2/cv2.pyd`（OpenCV 核心二进制扩展）** |
| `.dll` | 1 | （OpenCV 运行时 DLL） |

**两个 wheel 的 `top_level.txt` 都声明 `cv2`** → pip 无法通过顶层包名检测冲突，
因此**不会自动报错**，只会在先装的那个包上打印类似
`WARNING: ... Attempting uninstall` / 或被后装的静默覆盖。

### 后果

- `cv2/cv2.pyd` 被覆盖 → **`import cv2` 行为不确定**（取决于安装顺序与 pip 版本）。
- 两个发行版的 `dist-info` 同时存在 → `pip list` / `pip check` 显示不一致。
- 典型故障：`AttributeError: module 'cv2' has no attribute 'VideoCapture'`，
  或 `ImportError: DLL load failed`。

### 决定

**只安装 `opencv-contrib-python`**（`opencv-contrib-python` 是 `opencv-python` 的**超集**，
包含全部核心模块；MediaPipe 只使用其中的子集功能）。

```text
backend/requirements.txt:
    opencv-contrib-python==5.0.0.93     ✅
    # opencv-python  ← 不写，避免 cv2/ 目录被两个发行版争抢
```

### 复现校验方法

```powershell
# 在 pd 环境中确认只有一个 opencv 发行版
python -m pip list | Select-String -Pattern "opencv"
# 期望输出只有一行：opencv-contrib-python  5.0.0.93

# 确认 cv2 可用且核心接口存在
python -c "import cv2; print(cv2.__version__); print(hasattr(cv2,'VideoCapture'), hasattr(cv2,'CAP_PROP_FPS'))"
```

---

## 3. Python 3.11 造成的版本上限（已按 3.11 取版本）

`pd` 环境锁定 **Python 3.11.16**，以下包的最新版**不支持 3.11**，因此在
`requirements.txt` 中取了 3.11 可用的最新版：

| 包 | 最新版 | 最新版 requires_python | **本项目 pin（支持 3.11 的最新版）** |
| --- | --- | --- | --- |
| numpy | 2.5.3 | `>=3.12` | **2.4.6** |
| scipy | 1.18.1 | `>=3.12` | **1.17.1** |

其余依赖的最新版均声明支持 3.11，因此 pin 为最新稳定版。

**校验方式（可复现）：** 见 `scripts/_resolve_pins.py`（Phase 0 工具，按 PyPI 元数据
筛选"存在 cp311 / abi3 / py3-none-any wheel 且 `requires_python` 允许 3.11"的最新稳定版）。
结果快照：`data/demo/phase0_pins.json`。

> 注：`scripts/_*.py` 与 `scripts/_*.sh` 是**一次性 Phase 0 校验脚本**，
> 已按 `.gitignore` 的 `scripts/_*` 规则**不入库**，仅保留在本地供复现。

---

## 4. 依赖图整体校验（`pip install --dry-run`）

Phase 0 执行了**只解析不安装**的完整依赖图校验：

```powershell
python -m pip install --dry-run --ignore-installed --only-binary=:all: -r backend/requirements.txt
```

**结果：`exit code 0`，无版本冲突，无解析失败。** 解析出的关键版本：

```
fastapi-0.141.1  uvicorn-0.54.0  starlette-1.7.0  pydantic-2.13.5  pydantic_core-2.46.5
SQLAlchemy-2.1.1  alembic-1.20.0  PyMySQL-1.2.3  Mako-1.4.3
numpy-2.4.6  scipy-1.17.1  pandas-3.0.6  scikit-learn-1.9.1  joblib-1.6.0
mediapipe-1.0.1  opencv-contrib-python-5.0.0.93  pillow-12.3.0
matplotlib-3.11.2  contourpy-1.3.3  fonttools-4.66.0  kiwisolver-1.5.1
python-jose-3.5.0  ecdsa-0.19.2  rsa-4.9.1  cryptography-50.0.1
passlib-1.7.4  bcrypt-5.0.0  email-validator-2.3.0
python-multipart-0.0.32  aiofiles-25.1.0  httptools-0.8.0  watchfiles-1.3.0  websockets-17.1
pytest-9.1.1  pytest-asyncio-1.4.0  httpx-0.28.1
```

> 注：上面这次 dry-run 是在**修正 OpenCV 冲突之前**执行的，因此列表里同时出现了
> `opencv-python-5.0.0.93` 与 `opencv-contrib-python-5.0.0.93`。
> 修正后只保留 `opencv-contrib-python`。**Phase 1 安装后必须按 §2「复现校验方法」复查。**

---

## 5. MediaPipe 版本选择说明

| 项 | 值 |
| --- | --- |
| 外部仓库 `environment.yml` pin | `mediapipe==0.10.14` |
| 本项目 pin | `mediapipe==1.0.1` |

**理由与风险：**

- 外部仓库的 `environment.yml` 针对 **Python 3.12**，本项目固定 **Python 3.11**，
  不能直接照搬其版本组合。
- 外部仓库代码使用的是 **MediaPipe Tasks API**（`mp.tasks.vision.HandLandmarker`、
  `BaseOptions(model_asset_buffer=...)`、`VisionRunningMode.VIDEO`、`detect_for_video`），
  该 API 在 0.10.x 已稳定存在，1.0.x 为其延续。
- **Phase 4 必须先做一次 API 兼容冒烟测试**：用仓库自带的
  `src/demo/hand_landmarker.task` + `finger_tapping_test.mp4` 跑通
  `HandLandmarker.create_from_options(...).detect_for_video(...)`。
- **若 1.0.1 与仓库代码不兼容**，回退方案（按优先级）：
  1. `mediapipe==0.10.21`（Python 3.11 可用）
  2. `mediapipe==0.10.14`（与外部仓库完全一致）
  回退必须记录在 `docs/metric_definitions.md` §8 算法版本表 与 `NOTICE`。

> ⚠️ 若回退到 0.10.x，需重新核对 `opencv` 依赖是否仍为 `opencv-contrib-python`，
> 并重跑 §2 的冲突校验。

---

## 6. Phase 1 安装检查清单

```powershell
conda activate pd
python --version                     # 必须是 3.11.16
python -m pip install --upgrade pip

# 1) 后端依赖（不含 torch）
python -m pip install -r backend/requirements.txt

# 2) PyTorch（必须单独，按 GPU 架构选 wheel）
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130

# 3) 校验 A：opencv 只应有一个发行版
python -m pip list | Select-String opencv
#    期望：只有 opencv-contrib-python

# 4) 校验 B：cv2 可导入且接口完整
python -c "import cv2; print(cv2.__version__); print(hasattr(cv2,'VideoCapture'), hasattr(cv2,'CAP_PROP_FPS'))"

# 5) 校验 C：mediapipe Tasks API 可用
python -c "import mediapipe as mp; print(mp.__version__); print(hasattr(mp,'tasks'))"

# 6) 校验 D：torch CUDA 真实可用（含 kernel 冒烟）
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
python -c "import torch; a=torch.randn(256,256,device='cuda'); print(float((a@a).sum())); print('KERNEL_OK')"

# 7) 校验 E：依赖一致性
python -m pip check

# 8) 环境自检脚本
python scripts/check_models.py
```

**任何一步失败都必须先修复再进入 Phase 1 的业务开发**（规格 §76 第 4 条）。

---

## 7. 待老师模型 requirements 到位后的复核项

| # | 复核项 | 影响 |
| --- | --- | --- |
| 1 | torch 版本与 CUDA 组合 | 若要求 CUDA ≤ 12.6 → **本机 sm_120 无法用 GPU**，需上报决策 |
| 2 | numpy / scipy 版本区间 | 可能与 §3 的 pin 冲突 |
| 3 | opencv 发行版 | 若要求 `opencv-python` 而非 contrib → **必须重新解决 §2 冲突**（方案：移除 mediapipe 的 contrib 依赖或改用同一发行版） |
| 4 | Python 版本 | 若要求 3.12+ → 现有 `pd`（3.11.16）不满足，需与用户确认 |
| 5 | 额外依赖（如 timm / decord / av / facexlib） | 可能引入新的二进制冲突 |

---

> 本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。
