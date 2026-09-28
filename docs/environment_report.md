# Phase 0 环境审计报告

> 项目：帕金森病智能辅助识别、运动状态量化与数字康复训练平台（PD-Rehab-Web）
> 阶段：Phase 0 —— 环境与指标审计
> 生成方式：全部数据来自本机与服务器的真实命令输出，未做任何推测性填写。
> 自动采集脚本：`scripts/check_models.py`，原始 JSON：`data/demo/phase0_probe.json`
> 医疗声明：本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。

---

## 0. 结论速览

| 检查项 | 结论 | 是否阻塞 Phase 1 |
| --- | --- | --- |
| 工作区 | `D:\CodingData\Competition\PD\PD-Rehab-Web` | 否 |
| Conda 环境 `pd` | 存在，Python 3.11.16 | 否 |
| `pd` 环境已装包 | **仅 pip / setuptools / wheel / packaging（空环境）** | 否（Phase 1 安装） |
| NVIDIA GPU | RTX 5070 Laptop GPU，8151 MiB，compute capability **12.0** | 否 |
| NVIDIA 驱动 | 610.47（CUDA UMD 13.3） | 否 |
| PyTorch | **未安装** | 否（Phase 1 安装，见 §3.4） |
| 本机 CUDA Toolkit | v12.8.93（`nvcc` 可用） | 否 |
| MediaPipe / OpenCV / FastAPI 等 | **全部未安装** | 否（Phase 1 安装） |
| Node / npm | v22.19.0 / 10.9.3 | 否 |
| Git | 2.50.1.windows.1，已配置 user.name/email | 否 |
| GitHub CLI | 2.91.0，已登录 `WuChangqing1`（scopes: gist, read:org, repo, workflow） | 否 |
| Finger Tapping 外部仓库 | 存在，HEAD `170299a`，working tree clean | 否 |
| 外部仓库是否有预训练严重度模型 | **没有** → `severity_score` / `severity_label` 必须为 NULL | 否 |
| 老师微表情模型 | **未提供** → `MODEL_NOT_CONFIGURED` | **部分阻塞 Phase 3（不阻塞 4/5/6）** |
| fengz 服务器 | Ubuntu 22.04.5，4 vCPU / 3.6 GiB RAM / 40 GB，**无 GPU** | 否（但影响部署方案，见 §8） |

---

## 1. 工作区与项目目录

| 项 | 值 |
| --- | --- |
| 当前工作区（Session workspace） | `D:\CodingData\Competition\PD` |
| 新建项目根目录 | `D:\CodingData\Competition\PD\PD-Rehab-Web` |
| 原规格文档（只读，未改动） | `D:\CodingData\Competition\PD\PD_Rehab_Web_Development_Spec.md` |
| V2 规格文档（只读，未改动） | `D:\CodingData\Competition\PD\PD_Rehab_Web_Development_Spec_V2_Metrics.md` |
| PPT（只读，未改动） | `D:\CodingData\Competition\PD\帕金森应用.pptx`（12 页，25 张媒体） |
| 演示视频（只读，未改动） | `D:\CodingData\Competition\PD\项目演示视频\`（2 个 mp4，共约 1.02 GB） |

> 规格文档中曾建议目录为 `D:\CodingData\Github\PD-Rehab-Web`；本轮任务书明确指定为
> `D:\CodingData\Competition\PD\PD-Rehab-Web`。以**任务书为准**，该差异已记录在 `docs/spec_conflicts.md`。

---

## 2. Python / Conda

### 2.1 环境列表（`conda env list`，base = `D:\App\Business\Coding\Python\Miniconda`）

```
base                   D:\App\Business\Coding\Python\Miniconda
AIPPT                  D:\App\Business\Coding\Python\Miniconda\envs\AIPPT
AIqinban               D:\App\Business\Coding\Python\Miniconda\envs\AIqinban
AIqinban-tf            D:\App\Business\Coding\Python\Miniconda\envs\AIqinban-tf
LLM-API-Platform       D:\App\Business\Coding\Python\Miniconda\envs\LLM-API-Platform
MultiAgent             D:\App\Business\Coding\Python\Miniconda\envs\MultiAgent
SchoolStage            D:\App\Business\Coding\Python\Miniconda\envs\SchoolStage
cosyvoice              D:\App\Business\Coding\Python\Miniconda\envs\cosyvoice
dachuangxiangmu        D:\App\Business\Coding\Python\Miniconda\envs\dachuangxiangmu
fullfg                 D:\App\Business\Coding\Python\Miniconda\envs\fullfg
generative_agents      D:\App\Business\Coding\Python\Miniconda\envs\generative_agents
heartmula              D:\App\Business\Coding\Python\Miniconda\envs\heartmula
huawei                 D:\App\Business\Coding\Python\Miniconda\envs\huawei
isaacsim               D:\App\Business\Coding\Python\Miniconda\envs\isaacsim
markitdown             D:\App\Business\Coding\Python\Miniconda\envs\markitdown
mnn_convert            D:\App\Business\Coding\Python\Miniconda\envs\mnn_convert
mytutor                D:\App\Business\Coding\Python\Miniconda\envs\mytutor
pd                     D:\App\Business\Coding\Python\Miniconda\envs\pd      <-- 本项目使用
pd_marker              D:\App\Business\Coding\Python\Miniconda\envs\pd_marker
separation             D:\App\Business\Coding\Python\Miniconda\envs\separation
smoking                D:\App\Business\Coding\Python\Miniconda\envs\smoking
spider                 D:\App\Business\Coding\Python\Miniconda\envs\spider
spider-python          D:\App\Business\Coding\Python\Miniconda\envs\spider-python
```

Conda 版本：`conda 25.5.1`。

### 2.2 本项目使用的解释器

| 项 | 值 |
| --- | --- |
| Conda 环境名 | `pd` |
| Python 版本 | **3.11.16** |
| Python 绝对路径 | `D:\App\Business\Coding\Python\Miniconda\envs\pd\python.exe` |
| `sys.prefix` | `D:\App\Business\Coding\Python\Miniconda\envs\pd` |
| 构建信息 | `3.11.16 \| packaged by conda-forge \| (main, Sep 2 2026, 23:31:17) [MSC v.1944 64 bit (AMD64)]` |
| `.condarc` | 使用 USTC 镜像源（anaconda/cloud/conda-forge、pkgs/free、pkgs/main），`auto_activate: false` |

### 2.3 重要：默认 `python` 不是 `pd`

未激活环境时，`where python` 的首选项是 **系统 Python 3.13.12**：

```
D:\App\Business\Coding\Python\Python313\python.exe       <-- 系统 3.13.12（默认）
D:\App\Business\Coding\Python\Miniconda\python.exe       <-- conda base
C:\Users\All_in\AppData\Local\Microsoft\WindowsApps\python.exe
```

因为 `.condarc` 设置了 `auto_activate: false`，**每次新开 shell 都必须显式激活**，否则会误用 3.13 解释器：

```powershell
conda activate pd
python --version          # 必须输出 Python 3.11.16
```

开发期间所有命令统一使用绝对路径形式，避免解释器错配：

```powershell
& "D:\App\Business\Coding\Python\Miniconda\envs\pd\python.exe" -m pip install ...
```

### 2.4 `pd` 环境已安装包（完整 `pip list`）

```
Package    Version
---------- -------
packaging  26.3
pip        26.2.1
setuptools 84.0.0
wheel      0.48.0
```

> **结论：`pd` 环境目前是一个干净的、只带 pip 工具链的环境，尚未安装任何后端依赖。**
> 这符合规格中"Phase 0 只做审计"的定位，但意味着 **Phase 1 必须完成依赖安装**（见 §3.4 与 §9）。
> 未创建任何新的 conda 环境（未创建 `pd2` / `pd_new` / `venv`）。

---

## 3. GPU / CUDA / PyTorch

### 3.1 `nvidia-smi` 真实输出（本机，2026-09-28）

```
NVIDIA-SMI 610.47                 KMD Version: 610.47     CUDA UMD Version: 13.3
+-----------------------------------------------------------------------------+
| GPU  Name                     Driver-Model | Memory-Usage        | GPU-Util |
|=============================================================================|
|   0  NVIDIA GeForce RTX 5070 ...   WDDM   | 2584MiB / 8151MiB   |     12%  |
+-----------------------------------------------------------------------------+
```

| 项 | 值 |
| --- | --- |
| GPU 型号 | `NVIDIA GeForce RTX 5070 Laptop GPU` |
| 显存总量 | 8151 MiB（约 8 GB） |
| 驱动版本 | 610.47（KMD 610.47） |
| 驱动侧 CUDA UMD | **13.3** |
| **Compute Capability** | **12.0**（Blackwell / sm_120） |
| 本机 CUDA Toolkit (`nvcc`) | `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8\bin\nvcc.exe`，release 12.8, V12.8.93 |

### 3.2 PyTorch 现状

```
torch installed : False
import error    : ModuleNotFoundError: No module named 'torch'
```

- **PyTorch 未安装**。
- 老师模型的 `requirements` **尚未提供**，因此无法以其为准锁定版本。
- 规格要求验收 `torch.cuda.is_available() == True`，该项**本轮无法验证，标记为 PENDING**（依赖安装后才能验证）。

### 3.3 关键硬件约束：sm_120 必须匹配正确 wheel

RTX 5070 Laptop 属于 Blackwell 架构，compute capability **12.0（sm_120）**。
PyTorch 官方 CUDA 支持矩阵（`pytorch/pytorch` RELEASE.md，2.14）：

| CUDA | Windows 构建支持的架构 | 备注 |
| --- | --- | --- |
| 12.6.3 | Maxwell 5.0, Pascal 6.0, Volta 7.0, Turing 7.5, Ampere 8.0/8.6, Hopper 9.0 | **不含 Blackwell** |
| 13.0.3 | Turing 7.5, Ampere 8.0/8.6, Hopper 9.0, **Blackwell 10.0, 12.0+PTX** | 覆盖 sm_120 |
| 13.2.1 | 同上 | 覆盖 sm_120 |

来源：[pytorch/pytorch RELEASE.md](https://raw.githubusercontent.com/pytorch/pytorch/main/RELEASE.md)、[PyTorch Get Started](https://pytorch.org/get-started/locally/)

**推论（重要，避免 Phase 1 踩坑）：**

1. **绝不能安装 cu126 wheel**。cu126 构建不含 sm_120 kernel，装上后典型症状是
   `torch.cuda.is_available()` 返回 `True`，但第一个 CUDA kernel 就报
   `CUDA error: no kernel image is available for execution on the device`。
   （同类问题参考 [diffusers#12489](https://github.com/huggingface/diffusers/issues/12489)、[env-doctor#54](https://github.com/mitulgarg/env-doctor/issues/54)）
2. **必须选 cu128 或更高**。RTX 50 系需要 CUDA 12.8+ 构建。
3. 驱动 CUDA UMD 13.3 **向下兼容** CUDA 12.8 / 13.0 运行时，无需安装 "cu133"（官方也不存在该 wheel）。
   **本项目明确不寻找、不安装任何 cu133 包。**

### 3.4 Phase 1 建议的 PyTorch 安装目标（Phase 0 不执行安装）

本轮已核对 PyTorch 官方 wheel 索引（`https://download.pytorch.org/whl/<cuda>/torch/`，`cp311` + `win_amd64`）：

| wheel 索引 | 可用的最新版（cp311 / win_amd64） | 是否含 sm_120 |
| --- | --- | --- |
| `cu130` | 2.14.0 / 2.13.0 / 2.12.1 / 2.12.0 / 2.11.0 / 2.10.0 / 2.9.1 / 2.9.0 | 是（官方矩阵明确列出 Blackwell 12.0） |
| `cu128` | 2.11.0 / 2.10.0 / 2.9.1 / 2.9.0 / 2.8.0 / 2.7.1 / 2.7.0 | 是（RTX 50 系首次支持的稳定线） |
| `cu126` | 2.14.0 … 2.10.0 | **否 —— 禁止使用** |

**推荐（待老师模型 requirements 到手后复核）：**

```powershell
# 首选：CUDA 13.0 运行时，官方矩阵显式覆盖 Blackwell sm_120
conda activate pd
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130

# 备选：CUDA 12.8 运行时（若老师模型对 12.x 有硬约束）
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

安装后**必须**执行规格指定的验收命令：

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

并追加一次真实 kernel 冒烟测试（用于排除"可用但无 kernel"的假阳性）：

```powershell
python -c "import torch; a=torch.randn(64,64,device='cuda'); print((a@a).sum().item()); print('KERNEL_OK')"
```

**兼容性风险声明：** 老师模型 requirements 未知，届时若其要求 CUDA 12.6 及以下的 torch，
在本机 sm_120 上将**无法使用 GPU**。届时的处置顺序为：
① 优先请老师确认可用的更高 CUDA 版本；② 其次让老师模型跑 CPU（本系统业务无关）；
③ **不允许**为迁就旧 wheel 而安装不含 sm_120 kernel 的版本并谎报 `cuda.is_available()==True` 可用。

---

## 4. Node / npm / 其它工具链

| 工具 | 版本 | 路径 |
| --- | --- | --- |
| Node.js | **v22.19.0** | `node`（满足 Vite 5/6 要求的 Node ≥ 18） |
| npm | **10.9.3** | `npm` |
| Git | **2.50.1.windows.1** | `git` |
| GitHub CLI | **2.91.0** (2026-04-22) | `gh` |
| Conda | 25.5.1 | `D:\App\Business\Coding\Python\Miniconda\Scripts\conda.exe` |
| 本机 CUDA Toolkit | 12.8.93 | `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8` |

Git 全局身份：

```
user.name  = 阿尔法星人
user.email = 14774641+alpha-aliens@user.noreply.gitee.com      (gitee noreply 地址，非 GitHub)
```

> 注意：`user.email` 目前是 **gitee** 的 noreply 地址。推送到 GitHub 时提交会与该邮箱绑定，
> 但 GitHub 无法把它关联到 `WuChangqing1` 账号。若要提交计入 GitHub 贡献图，建议改为：
> `git config --global user.email "14774641+WuChangqing1@users.noreply.github.com"`
> 本轮**未擅自修改**全局 Git 配置。

### 4.1 GitHub CLI 认证状态

```
github.com
  ✓ Logged in to github.com account WuChangqing1 (keyring)
  - Active account: true
  - Git operations protocol: https
  - Token: gho_************************************
  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
```

**已登录，且具备 `repo` scope → 可以直接创建 Public Repository。**

---

## 5. Finger Tapping 外部仓库审计（只读）

仓库：`D:\CodingData\Github\VideoBased-PD-Biomarkers`
远程：`git@github.com:TaherehZarratEhsan/VideoBased-PD-Biomarkers.git`
HEAD：`170299a257d05a96f2edf127ad86354e35f017cd`
`git status --porcelain`：**空（working tree clean）**
**本轮未写入、未修改、未提交该仓库的任何内容。**

### 5.1 文件清单（全量）

| 大小 | 相对路径 |
| --- | --- |
| 127 B | `.gitignore` |
| 526 B | `environment.yml` |
| 6998 B | `README.md` |
| 132 B | `.vscode/settings.json` |
| 30,370,755 B | `assets/FT.gif` |
| 30,755,904 B | `assets/LA.gif` |
| 1,703,466 B | `src/demo/finger_tapping_test.mp4` |
| 11,895 B | `src/demo/ft_video_analysis.py` |
| **7,819,105 B** | **`src/demo/hand_landmarker.task`** |
| 18,886 B | `src/demo/la_video_analysis.py` |
| 1,855,460 B | `src/demo/leg_agility_test.mp4` |
| 9,202 B | `src/feature extraction/feature_extraction.py` |
| 18,617 B | `src/preprocessing/keypoint_extraction.py` |
| 30,893 B | `src/training/optimization_training.py` |

论文：Zarrat Ehsan et al., *Interpretable and Granular Video-Based Quantification of Motor Characteristics from the Finger Tapping Test in Parkinson's Disease*, **npj Parkinson's Disease**, 2026. DOI [10.1038/s41531-026-01307-w](https://doi.org/10.1038/s41531-026-01307-w)。License: Apache-2.0。

### 5.2 真实 Input / Output

**Input（两种入口）**

1. Demo 端到端入口 `src/demo/ft_video_analysis.py`：
   - CLI：`--video_path <mp4>`、`--hand2track {Left,Right}`
   - 用 OpenCV 读视频，逐帧送 MediaPipe **HandLandmarker（Tasks API，VIDEO 模式，`num_hands=2`）**
   - 依据 `handedness[0].category_name == hand_to_track` 过滤目标手
   - 输出：`src/demo/results/<video 父目录名>_<视频文件名>` 的标注视频 + `features.csv`

2. 批量科研入口 `src/preprocessing/keypoint_extraction.py`：
   - Input：`data/raw/segmented_ft_vid2score.csv`，列 `video_path`、`score`、`id`
   - **手别从文件名推断**：`'Right' if '2R' in video_path else 'Left' if '2L' in video_path else None`
   - 输出：`data/raw/video_keypoints.pkl`，字典键为
     `{'video_path', 'distances', 'keypoints', 'label', 'id', 'fps'}`
   - `distance` 开关：`True`=距离信号，`False`=角度信号（默认 False）

**Output（特征）** —— `feature_extraction.feature_ext_analysis._extract_features()` 返回
`features` 字典（12 个键），列名前缀 `['ids','video_path','label','medication_state','visit','hand']`：

```
avg_amplitude
avg_percycle_max_speed
avg_percycle_avg_speed
avg_cycle_duration
amp_slope
cycle_slope
speed_slope
cov_cycle_duration
cov_amp
cov_percycle_max_speed
cov_percycle_avg_speed
num_interruptions
```

`ft_video_analysis.py` 只取 `feature_names[6:]`（即上面 12 个）写入 `features.csv`。

### 5.3 真实信号处理管线（逐条对应规格审计清单）

| 审计项 | 真实实现（`feature_extraction.py` / `keypoint_extraction.py`） |
| --- | --- |
| MediaPipe 用法 | `mp.tasks.vision.HandLandmarker`，`BaseOptions(model_asset_buffer=...)`，`num_hands=2`，`VisionRunningMode.VIDEO`，`detect_for_video(mp_image, frame_timestamp_ms)`；时间戳 = `CAP_PROP_POS_MSEC` |
| 关键点 | 21 个手部关键点，保存原始归一化 `(x, y, z)` |
| 手别判定 | 用 MediaPipe `handedness[0].category_name` 字符串比对；注意 MediaPipe 的手别是按**镜像/前置摄像头**约定给的，与真实解剖手别相反，**这是一个需要产品层确认的假设** |
| Distance Signal | 归一化后 `INDEX_FINGER_TIP` 与 `THUMB_TIP` 的 3D 欧氏距离 |
| Angle Signal | `angle_signal()`：向量 wrist→thumb_tip 与 wrist→index_tip 的夹角（度），用像素坐标 |
| Normalization | **PALM_REFERENCE**：以 `WRIST` 为原点平移，除以 `wrist → INDEX_FINGER_MCP` 的 3D 欧氏距离（退化时钳到 `1e-5`） |
| Filter | Butterworth 低通，`order=4`，`ft` cutoff = **9.0 Hz**，`la` cutoff = 5.0 Hz；`nyq = 0.5*fs`；**`fs` 硬编码为 30.0**，与真实视频 fps 解耦 |
| 滤波实现 | `scipy.signal.filtfilt`（零相位，双向），因此对 `peaks` 的帧索引**不引入相位偏移** |
| Peaks | `find_peaks(d, distance=5, height=mean(d)/2, prominence=mean(d)/2)`（ft） |
| Troughs | `find_peaks(-d, distance=5, height=-mean(d), prominence=mean(d)/2)`（ft） |
| Cycle 分割 | `cycle_durations = np.diff(peaks) / fps`（相邻 peak 间隔） |
| Amplitude | 对每个 peak，取 `troughs[troughs < peak][-1]`（左侧最近 trough），`amp = abs(d[peak] - d[last_trough])`；`avg_amplitude = mean(amplitudes)`（**未做 CV 安全处理**） |
| Speed | `speed_signal = np.diff(d) / (1/fps)`（一阶差分 / 采样间隔）；按 cycle 切片 `speed_signal[peaks[i]:peaks[i+1]]`，逐周期取 `np.mean(np.abs(window))` 与 `np.percentile(np.abs(window), 95)` |
| Cycle Duration | `median` 与 `mean` 都算；`avg_cycle_duration = mean_cycle_duration` |
| CV | `cov_x = std_x / mean_x`，对 `cycle_durations`、`amplitudes`、`per_cycle_speed_*` 各算一个 |
| Slope | `sklearn.linear_model.LinearRegression`，自变量为 `np.arange(len(values)).reshape(-1,1)`（**cycle index，不是时间**），取 `coef_[0]` |
| Interruptions | `threshold = 1.5 * median_cycle_duration`；`num_interruptions = sum(interval > threshold for interval in cycle_durations)` |
| `tapping_frequency` | **不存在**。仓库里没有任何频率字段。需要新项目实现，或由 `1/avg_cycle_duration` 派生（必须显式记录为 NEW_DERIVED） |
| 左右手 | 仓库**不产出**左右差异字段。左右手是两个独立视频、两次独立运行；`left_right_difference` 必须由新项目在结果层计算 |
| QC（检测率） | `keypoint_extraction.preprocess_and_display_video()` 内有 `if detected_frames / total_frames >= 0.5`，否则打印跳过并 `return None`。**Demo 脚本 `ft_video_analysis.py` 没有这个检查**，且 `detected_frames` 被统计但从未使用 |
| QC（帧数） | 仅在 `load_data()` 中：`if video_length >= 4*fps` 才提取特征 |
| checkpoint | **无**。全仓库唯一的模型资产是 `src/demo/hand_landmarker.task`（7,819,105 B，sha256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`），即 MediaPipe 官方 HandLandmarker，属于**感知模型不是严重度模型** |
| 预训练模型 | **无任何** `.pt/.pth/.ckpt/.onnx/.engine/.pkl/.joblib` 权重 |
| Severity Inference | **不存在**。仓库没有"保存模型 → 加载模型 → 预测新样本"的链路 |

### 5.4 `optimization_training.py` 深入审计（科研实验脚本，非产品代码）

- **目标变量**：来自 `vid2score.csv` 的 `score` 列 = **MDS-UPDRS 0–4 序数评分（5 类）**，
  **不是 PD/Non-PD 二分类**。跑两种口径：`multi`（直接 5 分类）与 `ordinal`（4 个累积二分类阈值 1..4 后 argmax）。
- **分类器**（三个，全部每次都跑，无默认）：`Random Forest`、`Logistic Regression`、`LightGBM`。
- **指标**：`accuracy`、`precision(macro)`、`f1(macro)`、`balanced_accuracy`、
  `acceptable_accuracy = mean(|y_pred - y_test| <= 1)`、`AUC(ovr)`（ordinal 分支恒为 NaN）。
- **是否保存模型：不保存。** 全局搜索 `pickle.dump` / `joblib` / `save_model` / `to_json` / `.save(` 在 `src/` 内
  **只命中关键点字典**（`keypoint_extraction.py:410`）。仅输出：
  - `data/processed/dynamic_save.csv`（追加写入指标）
  - `data/processed/{model}_performance_metrics.png`（3 张 300dpi 图）
- **是否有推理入口：没有。** 无 `load_model` / `inference` / `predict_new`；`load_and_plot_results()` 只读指标 CSV。
- **是否用 GPU/torch：否。** 纯 CPU 的 scikit-learn + lightgbm + optuna，`n_jobs=1`，`trials=100`。
- **硬编码科研假设**（**产品化时全部不复用**）：患者级 `LeaveOneOut`、`if fold>=171:` 静默跳过前 170 折、
  `eval()` 解析 `id2vid.csv` 单元格、`//chansey.umcn.nl → /data` 内网路径重写、`iloc[0, 3:]` 取特征、
  5 类硬编码、`visit`/`hand`/`medication_state` 列在训练器里**完全未被使用**。

### 5.5 复用判定

| 文件 | 判定 | 理由 |
| --- | --- | --- |
| `src/preprocessing/keypoint_extraction.py` | **部分复用（复制要点到新项目）** | 归一化公式、距离/角度定义、`detected_frames/total_frames >= 0.5` 的 QC 阈值是**本项目的算法真值来源**。但原文件耦合了 `cv2.imshow`、绘图、pickle 批处理、`data/raw` 目录假设，且 `cap.release()` 写在 `return` 之后（永不执行，句柄泄漏）→ **不复用其控制流，只固化其算法语义** |
| `src/feature extraction/feature_extraction.py` | **复用算法语义，重写实现** | 12 个特征的公式是真值来源。但存在必须修正的缺陷：① `cov_percycle_max_speed = std_amp/mean_percycle_max_speed` **分子用了 `std_amp`，是 bug**（应为 `std_per_cycle_speed_maxima`）；② `filtfilt` 的 `fs` 硬编码 30.0，与真实 fps 不一致；③ 空序列时 `np.mean([])`→NaN 且 CV 会除零；④ 目录名含空格（`feature extraction`）无法正常 import；⑤ 特征列名前缀写着 `medication_state/visit/hand` 但调用处只取后 12 列，训练器却按 `iloc[0,3:]` 取 → 生产者 6 列 vs 消费者 3 列**不一致** |
| `src/training/optimization_training.py` | **不复用** | 论文实验脚本：需要 PEP 私有数据库、LOO-by-patient、硬编码折偏移、无模型持久化、无推理链路。与本项目"单视频 → 即时指标"的产品形态不匹配 |
| `src/demo/ft_video_analysis.py` | **不复用，仅作 API 参考** | 交互式 demo（`cv2.imshow`/`waitKey`），且存在缺陷：`preprocess_and_display_video()` 在 `_extract_features()` 之前从未给 `self.fps` 之外的 config 补默认值逻辑、检测率阈值缺失、`cap.release()` 位置错误 |
| `src/demo/la_video_analysis.py` | **不复用** | Leg Agility（腿部），本项目第一版不做 |
| `src/demo/hand_landmarker.task` | **可复用（需复制并在 `NOTICE` 注明来源）** | MediaPipe 官方 HandLandmarker float16；Apache-2.0。新项目应复制到 `models/mediapipe/` 并记录 sha256 |

> **强制规则**：规格文档中的指标定义**不能凌驾于真实算法代码**。
> 凡外部仓库已有实现的，一律以仓库代码为准；仓库没有的（`tapping_frequency`、左右差异、
> `valid_frame_ratio`、`avg_landmark_confidence`、`severity_*`）标记 **`NEEDS_IMPLEMENTATION`**。
> **本轮没有修改算法使其"看起来符合文档"。**

---

## 6. 老师微表情 / AI 模型状态

| 项 | 值 |
| --- | --- |
| 模型源码目录 | **未提供** |
| Checkpoint / 权重 | **未提供** |
| 入口函数 | **未知** |
| 标签字典 | **未知**（已知历史系统展示过：伤心 / 其他 / 厌恶 / 开心 / 恐惧 / 惊讶 / 愤怒，**但这只是历史截图，不是代码事实**） |
| 输入规范（时长/FPS/分辨率/预处理） | **未知** |
| 输出字段（是否含 `pd_probability` / `tag_distribution`） | **未知** |

可探测位置全部未命中：

```
[  -  ] (env MICRO_EXPRESSION_MODEL_DIR 为空)
[  -  ] D:\CodingData\Competition\PD\PD-Rehab-Web\models\micro_expression
[  -  ] D:\CodingData\Github\micro-expression
[  -  ] D:\CodingData\Github\micro_expression
[  -  ] D:\CodingData\Github\MicroExpression
[  -  ] D:\CodingData\Github\PD-MicroExpression
```

全盘按名称模式（micro.?expr / expression / face / emotion / parkinson / 微表情 等）扫描
`D:\CodingData` 深度 3 层，**未发现任何候选模型目录**。

```
STATUS: MODEL_NOT_CONFIGURED
```

按规格要求，Phase 3 在本状态下只交付：Adapter 接口 + API + DB Schema + 前端状态 + `MODEL_NOT_CONFIGURED` 显式状态，
**禁止伪造标签、概率、截图百分比；禁止自行训练替代模型；禁止后台静默返回 Mock。**
详见 `docs/model_integration.md`。

---

## 7. Git / GitHub

| 项 | 值 |
| --- | --- |
| `git --version` | 2.50.1.windows.1 |
| `gh --version` | 2.91.0 (2026-04-22) |
| `gh auth status` | ✅ Logged in as **WuChangqing1**，protocol https，scopes: `gist, read:org, repo, workflow` |
| 本地仓库 | `D:\CodingData\Competition\PD\PD-Rehab-Web`（`git init`，分支 `main`） |
| GitHub Public Repo | 见本文件末尾 §10「本轮实际产出」与最终回复 |

GitHub 认证可用，因此本轮**已实际创建 Public Repository 并完成首次推送**（结果见 §10）。

---

## 8. fengz 服务器只读审计

连接方式：`ssh fengz`（BatchMode 连接成功）。**全程只读，未修改 Nginx、未停止任何服务、未写入任何文件。**

### 8.1 系统

| 项 | 值 |
| --- | --- |
| 主机名 | `VM-0-11-ubuntu` |
| OS | **Ubuntu 22.04.5 LTS (Jammy Jellyfish)** |
| Kernel | `Linux 5.15.0-171-generic #181-Ubuntu SMP Fri Feb 6 22:44:50 UTC 2026 x86_64` |
| 虚拟化 | KVM / full（腾讯云 CVM） |
| 登录用户 | `ubuntu` (uid=1000)，组：`sudo, adm, dialout, cdrom, floppy, audio, dip, video, plugdev, lxd, netdev` |
| 免密 sudo | **YES**（`sudo -n true` 成功） |
| 内网 IP | `10.0.0.11` |
| 公网 IP | **`110.42.236.65`** |

### 8.2 CPU / 内存 / 磁盘

| 项 | 值 |
| --- | --- |
| CPU | Intel(R) Xeon(R) Platinum 8255C @ 2.50GHz |
| 核心 | 4 vCPU（1 socket × 4 core × 1 thread） |
| 内存 | **总计 3.6 GiB**，已用 618 MiB，可用 2.7 GiB |
| **Swap** | **0 B（未配置 swap）** |
| 磁盘 | `/dev/vda2` 40 GB，已用 7.9 GB，**可用 30 GB（21%）** |
| inode | 使用率 6%（充足） |

> ⚠️ **内存是最大硬约束**：3.6 GiB 且无 swap。MediaPipe + OpenCV + FastAPI + Python 3.11 常驻约 800 MiB–1.5 GiB；
> 一旦叠加视频解码峰值极易 OOM。**服务器方案必须按"无 GPU + 3.6 GiB RAM"设计**（见 `docs/server_deployment_plan.md`）。

### 8.3 GPU

```
nvidia-smi NOT INSTALLED
lspci | grep -i vga → 00:02.0 VGA compatible controller: Cirrus Logic GD 5446
```

**服务器没有 GPU**（Cirrus Logic GD 5446 是 QEMU/KVM 虚拟显示控制器，非计算卡）。

**直接后果：**

1. 微表情 / AI 模型在服务器上只能 **CPU 推理**（或不在服务器上跑）。
2. Finger Tapping 的 MediaPipe Hand Landmarker 在服务器上只能 **CPU 推理**；MediaPipe CPU 版可用，
   但 4 vCPU + 3.6 GiB 下 10–20 秒视频的逐帧处理会比较慢，且并发必须限制为 1。
3. 规格中 "GPU 推理单并发（`Semaphore(1)`）" 在服务器上退化为 **CPU 推理单并发 + 请求排队**，
   并需要显式设置 `torch.set_num_threads()` 限制，避免 4 核被打满导致 Nginx 抖动。
4. **demo 最佳实践：本地 Windows（有 RTX 5070）跑重推理，服务器只跑轻量展示**；或服务器上仅开放
   上传 MP4 的异步 Job 流程，前端轮询 `GET /api/jobs/{job_id}`。

### 8.4 软件版本

| 工具 | 版本 | 说明 |
| --- | --- | --- |
| Python | **3.10.12** (`/usr/bin/python3`) | 系统自带；`python`（无 3）不存在 |
| python3.11 | 未安装（apt candidate 仅 `3.11.0~rc1`，是 RC 版） | **不建议**用 apt 装 3.11 |
| pip3 | 22.0.2（系统 dist-packages） |  |
| conda | **未安装** |  |
| venv | 可用（`import venv` OK） | 推荐用 venv / uv |
| Node.js | **v12.22.9** (`/usr/bin/node`) | **过旧**：Vite 5/6 需要 Node ≥ 18 |
| npm | **未安装** | 需先安装 Node |
| pnpm / yarn | 均未安装 |  |
| Nginx | **nginx/1.18.0 (Ubuntu)**，systemd `active` + `enabled` | 已稳定运行 1 周 3 天 |
| certbot | **1.21.0** |  |

> **服务器当前无法构建前端**（Node 12 + 无 npm）。**建议方案：本地 `npm run build` 产出 `dist/`，
> 用 `rsync/scp` 上传静态产物到服务器，服务器完全不需要 Node。** 这条路径最省内存也最稳。

### 8.5 Nginx 现状（关键：不要动已有配置）

已有 server 块（`nginx -T` 摘要）：

| 监听 | server_name | 站点根 / 反代 | 归属 |
| --- | --- | --- | --- |
| `80` | `110.42.236.65` | `root /var/www/fitness` + `include snippets/smoking-monitor-locations.conf` + `include snippets/exercises-locations.conf` | fitness / exercises |
| `80`, `443 ssl` | `ccqspace.site www.ccqspace.site` | `location / → proxy_pass 127.0.0.1:8000`；`/home/ → /var/www/homepage`；`/market/ → /var/www/market_frontend` | mysite.conf |
| `18082` | `_` | `root /var/www/smoking-monitor/dist`，`/api/ → 127.0.0.1:18081` | smoking-monitor.conf |
| `18083` | `_` | `root /var/www/smoking-monitoring-system/dist`，`/api/ → 127.0.0.1:18084` | smoking-monitoring-system.conf |

- **80 端口已被 `server_name 110.42.236.65`（fitness）与 `ccqspace.site` 占用**，
  且 fitness 通过 `include` 挂载了 `smoking-monitor-locations.conf` / `exercises-locations.conf`。
  → **绝不能再往 80 加第三个 server 块**（会 server_name 冲突 / 抢路由）。
- TLS 证书：`/etc/letsencrypt/live/ccqspace.site/`（RSA，域名 `ccqspace.site` + `www.ccqspace.site`，
  有效期至 **2026-12-10**，剩 72 天）。
  → **没有任何证书覆盖 `110.42.236.65`（纯 IP）**。

### 8.6 端口占用（`ss -lntp`，sudo 视角）

| 端口 | 绑定 | 进程 | 归属 |
| --- | --- | --- | --- |
| 22 | 0.0.0.0 / [::] | `sshd` | SSH |
| 53 | 127.0.0.53 | `systemd-resolve` | 本地 DNS |
| 80 | 0.0.0.0 | `nginx` | fitness + mysite |
| 443 | 0.0.0.0 | `nginx` | ccqspace.site TLS |
| **8000** | 127.0.0.1 | `python` (pid 1649531) | `exercises.service` |
| **18080** | 127.0.0.1 | `python` (pid 3979478) | `llm-api-platform.service` |
| **18081** | 127.0.0.1 | `uvicorn` (pid 1800107) | `smoking-monitor-api` |
| **18082** | 0.0.0.0 / [::] | `nginx` | smoking-monitor 前端 |
| **18083** | 0.0.0.0 / [::] | `nginx` | smoking-monitoring-system 前端 |
| **18084** | 127.0.0.1 | `uvicorn` (pid 1838442) | `smoking-monitoring-system-api` |

全端口扫描结论：

```
已占用（8000-20000 区间）：8000 18080 18081 18082 18083 18084
5173 空闲；3306 空闲；5432 空闲；6379 空闲；8080 空闲；8443 空闲
推荐给本项目的新端口（已验证 FREE）：18085 / 18086 / 18090 / 18091
```

已运行的其它服务（systemd，running）：`exercises`、`llm-api-platform`、`smoking-monitor-api`、
`smoking-monitoring-system-api`、`nginx`、`ssh`、`snapd`、`unattended-upgrades` 等。

### 8.7 已有站点目录

```
/opt/exercises            (ubuntu:ubuntu)   <- exercises.service, venv at /opt/exercises/.venv
/opt/llm-api-platform     (ubuntu:ubuntu)
/var/www/fitness
/var/www/homepage
/var/www/smoking-monitor
/var/www/smoking-monitoring-system
/home/ubuntu/apps
```

`/opt` 权限为 `root:root`，但用户 `ubuntu` 有免密 sudo，**可以**创建 `/opt/pd-rehab/`。

### 8.8 网络与安全组

- `ufw` 未安装；`iptables -S` 需要 root（云安全组在平台层控制）。
- 从既有配置文件注释可确认：**18082 / 18083 已在云安全组放行**。
  → 新增端口（如 18085）**需要用户在腾讯云安全组手动放行**，否则外网不可达。**这是一个已知的前置动作项。**

### 8.9 HTTPS 与摄像头（重要产品约束）

规格要求三种浏览器本地摄像头功能（微表情录制、Finger Tapping、Pose）。
但 `getUserMedia` 依赖 **Secure Context**：

| 访问方式 | 是否 Secure Context | 摄像头可用？ |
| --- | --- | --- |
| `http://127.0.0.1:5173`（本地开发） | 是 | ✅ |
| `http://localhost:5173` | 是 | ✅ |
| `https://ccqspace.site/...` | 是 | ✅（需该域名解析到本服务器且 Nginx 反代） |
| **`http://110.42.236.65:18085`** | **否** | ❌ 浏览器拒绝摄像头 |

**因此**：
- 服务器 Demo 若走 `http://<IP>:18085`，**只能使用"本地 MP4 文件上传"路径**，不能录制。
  规格已明确此优先级："如果暂时没有 HTTPS：优先保证本地 MP4 文件上传完整可用。"
- 若要服务器端支持录制，必须使用**已有证书覆盖的域名**（`ccqspace.site`）新增路径/子域，
  或申请新证书。**本轮不修改 Nginx，只在部署方案中给出计划。**
- **严禁**用 `--unsafely-treat-insecure-origin-as-secure` 之类方式绕过浏览器安全策略。

---

## 9. 变更清单（Phase 0 只读约束遵守情况）

| 约束 | 状态 |
| --- | --- |
| 未删除 / 覆盖 / 移动 `PD_Rehab_Web_Development_Spec.md` | ✅ |
| 未删除 / 覆盖 / 移动 `PD_Rehab_Web_Development_Spec_V2_Metrics.md` | ✅ |
| 未删除 / 覆盖 / 移动 `帕金森应用.pptx` | ✅ |
| 未删除 / 覆盖 / 移动 `项目演示视频\` | ✅ |
| 未修改 `D:\CodingData\Github\VideoBased-PD-Biomarkers`（`git status` clean） | ✅ |
| 未创建额外 conda 环境（无 pd2 / pd_new / venv） | ✅ |
| 未安装任何 Python 包 | ✅ |
| 未安装/未尝试 `cu133` 类不存在的 PyTorch | ✅ |
| 服务器全程只读，未改 Nginx，未停服务 | ✅ |
| 未伪造任何模型输出 / 临床评分 / Pose 分数 | ✅ |
| 未开始 Phase 1 业务开发 | ✅ |

工作区根目录新增的临时审计脚本：`_phase0_server_audit.sh`、`_phase0_server_audit2.sh`
（服务器只读审计用的远端脚本源文件，非项目源码，后续可删除）。

---

## 10. Blockers 汇总

| # | Blocker | 影响 | 是否需要用户动作 |
| --- | --- | --- | --- |
| B1 | **老师微表情模型未提供**（无目录、无 checkpoint、无入口、无标签字典、无 requirements） | Phase 3 无法真实接入；当前只能交付 `MODEL_NOT_CONFIGURED` | ✅ 需要（提供模型目录） |
| B2 | **`pd` 环境为空**，全部后端依赖未安装（含 PyTorch） | Phase 1 第一步必须安装；`torch.cuda.is_available()` 目前无法验证 | 否（Phase 1 执行） |
| B3 | **服务器无 GPU + 3.6 GiB RAM + 无 swap** | 服务器无法承载真实微表情/Pose 模型；需按 CPU-only 轻量方案设计 | 需知悉并决策（见部署方案） |
| B4 | **服务器 Node 12 + 无 npm** | 服务器不能构建前端 → 改为本地 build + 上传 `dist/` | 否（方案已定） |
| B5 | **纯 IP 访问不是 Secure Context** | 服务器 Demo 上摄像头录制不可用，只能上传 MP4 | 需知悉 |
| B6 | **新端口需在腾讯云安全组放行**（如 18085） | 不放行则外网访问不通 | ✅ 需要（用户在控制台放行） |
| B7 | 老师模型 requirements 未知 → 无法最终锁定 PyTorch 版本 | 若其要求 CUDA ≤ 12.6，本机 sm_120 无法用 GPU | ⚠️ 待 B1 解决后复核 |
| B8 | 外部仓库**无严重度分类模型**、`tapping_frequency` 不存在 | `severity_score`/`severity_label` 保持 NULL；`tapping_frequency` 需新实现并版本化 | 否（已记录到 metric_definitions.md） |
| B9 | Git 全局 `user.email` 是 gitee noreply 地址 | GitHub 提交无法关联 `WuChangqing1` 账号（不影响推送） | ⚠️ 建议修改，未擅自改 |

---

## 11. Phase 1 前置条件

Phase 1 可以立即开始，唯一需要预先准备的是：

1. `conda activate pd` 并安装依赖（`backend/requirements.txt` + PyTorch cu130/cu128 wheel）。
2. 老师模型目录（仅影响 Phase 3，不阻塞 Phase 1/2/4/5/6）。
3. 云安全组放行（仅影响最终部署，不阻塞开发）。

---

> 本报告全部结论均可由 `scripts/check_models.py` 与 `docs/server_deployment_plan.md` 中的命令复现。
> 本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。
