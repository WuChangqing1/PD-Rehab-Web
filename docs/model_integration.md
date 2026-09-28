# 模型接入设计文档（model_integration.md）

> 项目：PD-Rehab-Web
> 版本：**Phase 4 更新版（v0.4.0）** —— Finger Tapping 已实现；微表情模型仍未提供
> 医疗声明：本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。

---

## 0. 总原则

```
真实模型优先
不伪造任何模型输出
模型全部通过 Adapter 隔离
前端不得直接调用 Python 模型
模型只加载一次并复用
GPU 推理单并发
模型不可用时返回明确错误，绝不静默降级为 Mock
```

**红线（违反即视为缺陷）：**

1. ❌ 伪造模型结果
2. ❌ 随机生成标签或概率
3. ❌ 写死截图中的百分比
4. ❌ 根据需求猜模型结构
5. ❌ 自行训练一个替代模型冒充老师模型
6. ❌ 模型没有的字段填占位值（必须是 `null` 或不存在）

---

## 1. 微表情 / PD 辅助识别模型 Adapter

### 1.1 目录与文件

```
backend/app/ml/micro_expression/
├─ adapter.py       # MicroExpressionAnalyzer：加载 / 推理 / 状态
├─ schemas.py       # Pydantic：ModelStatus / MicroExpressionResult / TagScore
└─ errors.py        # 模型层异常（ModelNotConfigured / ModelLoadFailed / InferenceFailed）
```

### 1.2 统一接口（规格 V1 §11.5 固定）

```python
class MicroExpressionAnalyzer:
    """老师微表情 / PD 辅助识别模型的统一适配层。

    业务代码（API / Service）只依赖本类，不直接 import 任何模型内部模块。
    换模型时前端与 API 无需改动。
    """

    MODEL_NAME: str = "micro_expression_model"
    MODEL_VERSION: str = "unknown"

    def load(self) -> None:
        """在 FastAPI startup 时调用一次。失败时记录状态，不抛异常中断启动。"""

    def analyze(self, video_path: str) -> dict:
        """对单个视频推理，返回标准化 dict。"""

    def status(self) -> "ModelStatus":
        """返回模型当前状态，供 /api/system/models 与前端使用。"""
```

### 1.3 状态机

```text
MODEL_NOT_CONFIGURED   # MICRO_EXPRESSION_MODEL_DIR 为空或目录不存在  <-- 当前状态
LOADING
READY
UNAVAILABLE            # 目录存在但缺少 checkpoint / 入口 / 依赖
LOAD_FAILED            # 加载抛异常
INFERENCE_FAILED       # 单次推理失败（不改变全局状态）
```

**当前真实状态：`MODEL_NOT_CONFIGURED`。**

依据（`docs/environment_report.md` §6）：模型目录、checkpoint、入口函数、标签字典、
requirements 全部未提供；`MICRO_EXPRESSION_MODEL_DIR` 为空；本机全盘按名称模式扫描
`D:\CodingData` 深度 3 层未发现任何候选目录。

### 1.4 环境变量与目录约定

`.env`（**不入 Git**）：

```env
# 老师微表情 / PD 模型目录。为空 -> MODEL_NOT_CONFIGURED
MICRO_EXPRESSION_MODEL_DIR=

# 老师模型推理入口（可选）。留空时由 adapter 自动探测常见入口名。
MICRO_EXPRESSION_ENTRY=

# 老师模型权重文件名（可选）。留空时由 adapter 自动探测 *.pt/*.pth/*.ckpt
MICRO_EXPRESSION_CHECKPOINT=

# 设备偏好；留空时自动选择
MICRO_EXPRESSION_DEVICE=
```

**未来模型推荐存放位置（不入 Git）：**

| 场景 | 路径 |
| --- | --- |
| 本地开发（Windows） | `D:\CodingData\Competition\PD\PD-Rehab-Web\models\micro_expression\` |
| 服务器部署 | `/opt/pd-rehab/models/micro_expression/` |

目录内期望结构（**待老师确认后固化**）：

```
models/micro_expression/
├─ README.md            # 模型来源、论文、输入规范、标签字典、许可
├─ requirements.txt     # 真实依赖（决定 PyTorch / CUDA 版本）
├─ labels.json          # {"0":"伤心","1":"其他","2":"厌恶", ...}
├─ <checkpoint>.pt
└─ <inference code>
```

> ⚠️ `.gitignore` 已排除 `models/`、`*.pt`、`*.pth`、`*.ckpt`、`*.onnx`、`*.engine`。
> **老师模型权重、私有 checkpoint 绝对不得进入 Public 仓库。**

### 1.5 接入前必须向老师确认的清单（V1 §56）

| # | 待确认项 | 当前 |
| --- | --- | --- |
| 1 | 模型源码目录 | ❌ 未提供 |
| 2 | Checkpoint 文件名与位置 | ❌ 未提供 |
| 3 | 入口函数 / 调用方式 | ❌ 未知 |
| 4 | `requirements.txt`（**决定 PyTorch/CUDA 版本，直接影响本机 sm_120 可用性**） | ❌ 未提供 |
| 5 | 标签字典（真实标签集合与顺序） | ❌ 未知 |
| 6 | 视频规范：时长 / FPS / 分辨率 / 编码 | ❌ 未知 |
| 7 | 预处理方式（人脸检测/对齐、裁剪、归一化、帧采样） | ❌ 未知 |
| 8 | 输出字段：是否含 `pd_probability`？是否含 `tag_distribution`？ | ❌ 未知 |
| 9 | 是否需要 GPU？显存需求？ | ❌ 未知 |
| 10 | 许可与使用范围声明 | ❌ 未提供 |

> ⚠️ **历史截图中的标签（伤心/其他/厌恶/开心/恐惧/惊讶/愤怒）与百分比只是历史界面记录，
> 不是代码事实。在拿到真实标签字典前，`labels.json` 不得由 Agent 自行编写。**

### 1.6 标准化输出 JSON（Adapter 出口契约）

Adapter **必须**把模型原始输出转换为以下统一结构后再交给 Service。
**模型没有的字段一律 `null`，不省略、不编造：**

```json
{
  "model_name": "micro_expression_model",
  "model_version": "unknown",
  "feature_schema_version": "1.0",

  "predicted_class": null,
  "pd_probability": null,

  "dominant_tag": null,
  "tag_distribution": null,

  "raw_output_json": {},
  "inference_time_ms": 0,
  "quality_json": {
    "video_duration_ms": null,
    "fps": null,
    "frame_count": null,
    "width": null,
    "height": null,
    "model_input_spec": "unknown"
  },
  "created_at": "2026-01-01T00:00:00Z"
}
```

**当模型为 `tag_distribution` 型时**（V2 §5.1）：

```json
{
  "dominant_tag": "厌恶",
  "tag_distribution": [
    {"name": "伤心", "score": 0.241},
    {"name": "其他", "score": 0.105},
    {"name": "厌恶", "score": 0.574}
  ],
  "predicted_class": null,
  "pd_probability": null
}
```

**当模型为二分类/概率型时**（V2 §5.2）：

```json
{
  "predicted_class": "PD",
  "pd_probability": 0.72,
  "dominant_tag": null,
  "tag_distribution": null
}
```

**两者都有时**：全部原样保存。

### 1.7 未配置时的错误契约

`POST /api/assessment-sessions/{session_id}/micro-expression` 在
`MODEL_NOT_CONFIGURED` 下必须返回 **HTTP 503**：

```json
{
  "error": {
    "code": "MODEL_NOT_CONFIGURED",
    "message": "微表情 / AI 模型尚未配置，无法进行分析。请联系管理员配置模型目录。",
    "detail": {
      "env_var": "MICRO_EXPRESSION_MODEL_DIR",
      "current_value": ""
    }
  }
}
```

其他错误码：

| 错误码 | HTTP | 触发 |
| --- | --- | --- |
| `MODEL_NOT_CONFIGURED` | 503 | 目录为空/不存在 |
| `MODEL_UNAVAILABLE` | 503 | 目录存在但缺 checkpoint / 入口 / 依赖 |
| `MODEL_LOAD_FAILED` | 503 | 加载抛异常（附堆栈摘要） |
| `INFERENCE_FAILED` | 500 | 单次推理异常（附摘要） |
| `VIDEO_UNREADABLE` | 400 | 视频不可读 |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | 非 mp4/mov/avi |
| `CUDA_OUT_OF_MEMORY` | 503 | 显存不足 |

### 1.8 展示约束（强制，V2 §5）

- 统一用 **"辅助识别概率"** / **"模型输出概率"**。
- **禁止**写"确诊概率"、"病情严重度"、"病情下降 X%"。
- 微表情 tag 占比**只是面部运动 / 表情表现维度**，**不得**解释为帕金森严重程度。
- 微表情 tag 占比**不得**用于调整钢琴训练难度。
- 二分类概率**默认也不直接映射为治疗强度**。
- 图表必须标注"模型输出变化"，**不是**"病情改善 X%"。

---

## 2. Finger Tapping Adapter

> **状态：Phase 4 已实现并实测。** 本节记录**实际落地**的文件与接口（与 Phase 1 的规划版本不同）。

### 2.1 目录与文件（Phase 4 实际结构）

```
backend/app/ml/finger_tapping/
├─ adapter.py     # 组件状态（READY/UNAVAILABLE）、特征键、analysis_config 快照
├─ signal.py      # 关键点索引常量、PALM_REFERENCE 归一化、孔径序列、Butterworth 滤波、速度信号
├─ features.py    # 峰谷检测、周期分割、12 项运动特征、中断计数
├─ quality.py     # 8 道 QC 门限、错误码、QualityReport
└─ pipeline.py    # analyze_video()：端到端编排 + 数据库输出契约（AnalysisOutcome）
```

> 说明：Phase 1 规划中的 `feature_extractor.py` / `schemas.py` / `errors.py` **未单独成文件**。
> 特征逻辑落在 `features.py`；schema 与错误契约由 `quality.QualityReport`、
> `pipeline.AnalysisOutcome` 以及既有 `app/core/errors.py` 承担，避免重复定义。

### 2.2 统一接口（规格 V1 §15 固定）

```python
def analyze_video(video_path: str, hand: str) -> AnalysisOutcome:
    """hand ∈ {"LEFT","RIGHT"}。返回 AnalysisOutcome，或抛 APIError（含 QC 错误码）。"""

def analyze_bytes(content: bytes, hand: str, *, suffix=".mp4") -> AnalysisOutcome:
    """临时文件包装，便于测试与内存上传。"""
```

`AnalysisOutcome` 字段：`hand`、`features`（12 项，直接对应 DB 列）、`quality`、
`analysis_config`、`raw_features`、`timeseries`、`severity_score`/`severity_label`
（**恒为 None**）、`analyzer_version`、`qc_version`、`feature_schema_version`、
`inference_time_ms`、`handedness_note`。

### 2.3 数据流（真实实现路径）

```
Video (mp4)
  → cv2.VideoCapture                      # 读取 fps / frame_count / 逐帧
  → MediaPipe HandLandmarker (Tasks API)  # num_hands=2, VisionRunningMode.VIDEO
  → 21 个手部关键点 (x, y, z)
  → handedness 过滤目标手
  → PALM_REFERENCE 归一化                 # 平移至 WRIST，除以 |INDEX_MCP - WRIST|
  → d(t) = ‖THUMB_TIP − INDEX_FINGER_TIP‖
  → Butterworth 低通 (order=4, cutoff=9Hz, filtfilt, fs=真实 fps)
  → find_peaks → peaks / troughs
  → Cycle 分割 (np.diff(peaks)/fps)
  → Feature Extraction (12 项)
  → QC 门限检查
  → 标准 JSON + quality_json
  → DB (finger_tapping_results) + raw_features_json + quality_json
  → ECharts 图表
```

> **来源声明**：算法语义（归一化、距离信号、滤波、峰谷、12 个特征公式、中断阈值）
> 全部来自外部仓库 `D:\CodingData\Github\VideoBased-PD-Biomarkers`
> （Apache-2.0，论文 DOI [10.1038/s41531-026-01307-w](https://doi.org/10.1038/s41531-026-01307-w)）。
> **原仓库保持只读、零修改。** 算法缺陷与差异已逐条记录在
> `docs/metric_definitions.md` §7（D1–D12）。

### 2.4 复用 / 不复用清单

| 外部仓库文件 | 判定 | 说明 |
| --- | --- | --- |
| `src/preprocessing/keypoint_extraction.py` | **仅复用算法语义**（PALM_REFERENCE 归一化公式、距离/角度定义、0.5 检测率阈值）。**代码无法直接复用**：见下方 ⚠️。**不复用控制流**（`cv2.imshow`、绘图、pickle 批处理、`cap.release()` 位置错误导致句柄泄漏、`data/raw` 目录假设） | 归一化与距离公式已按语义在 `signal.py` 重写；关键点索引改为常量 |
| `src/feature extraction/feature_extraction.py` | **复用 12 个特征公式**，但必须修正：① `cov_percycle_max_speed` 分子 bug；② `fs` 硬编码 30.0；③ 空序列 NaN/除零；④ 目录名含空格无法 import；⑤ 特征列名契约不一致 | **已重写为 `features.py`**，纯函数、无 IO、无绘图 |
| `src/training/optimization_training.py` | **不复用** | 论文实验脚本：需 PEP 私有数据库、LOO-by-patient、`if fold>=171` 硬编码跳过、`eval()` 解析配置、内网路径重写、**不保存模型、无推理入口**、纯 CPU sklearn/lightgbm/optuna |
| `src/demo/ft_video_analysis.py` | **不复用**，仅作 API 参考 | 交互式 demo（`cv2.imshow`/`waitKey`），无检测率 QC；且依赖 `mp.solutions` |
| `src/demo/la_video_analysis.py` | **不复用** | Leg Agility，第一版不做 |
| `src/demo/hand_landmarker.task` | **可复用** | MediaPipe 官方 HandLandmarker float16，7,819,105 B，sha256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`。复制到 `models/mediapipe/hand_landmarker.task`，Apache-2.0，已在 `NOTICE` 注明来源 |

#### ⚠️ 2.4.1 关键发现：`mp.solutions` 已被 mediapipe 1.0.1 移除

外部仓库通过 `mp.solutions.hands.HandLandmark` 引用关键点。**mediapipe 1.0.1 完全删除了
`mp.solutions`**，实测结果：

```
hasattr(mp, 'solutions')       -> False
import mediapipe.python.solutions -> ModuleNotFoundError
import mediapipe.solutions        -> ModuleNotFoundError
```

**后果：仓库的 `keypoint_extraction.py` 与 `ft_video_analysis.py` 在本环境无法运行。**

处置方式（**未修改原仓库**）：

1. 把关键点索引作为**常量固定在** `backend/app/ml/finger_tapping/signal.py`：

   | 常量 | 值 | 用途 |
   | --- | --- | --- |
   | `WRIST` | 0 | 归一化原点 |
   | `THUMB_TIP` | 4 | 孔径信号端点 |
   | `INDEX_FINGER_MCP` | 5 | 掌宽参考（归一化分母） |
   | `INDEX_FINGER_TIP` | 8 | 孔径信号端点 |

2. 用**真实推理**验证这些索引确实指向正确的解剖位置：在仓库自带 demo 视频上
   327/327 帧检出手部，孔径信号产生 25 个生理合理的敲击周期（2.60 Hz）。
   若索引错误，信号会退化、无法产生规律峰谷。

3. 本项目**不依赖** `mp.solutions`，因此不会因 mediapipe 版本变化而失效。

#### ⚠️ 2.4.2 关键发现：`visibility` / `presence` 恒为 `None`

Phase 0 曾推断 Tasks API 的 `NormalizedLandmark` 可能**没有** `visibility`/`presence`。
Phase 4 实测结论更精确：**属性存在，但值恒为 `None`**（327/327 帧）。

```
landmark.visibility : 全部为 None（无任何数值）
landmark.presence   : 全部为 None
handedness[0].score : 0.9218 ~ 0.9744，327 帧中 326 个不同取值  <- 真实可用
```

因此 `avg_landmark_confidence` 改为保存**手别分类置信度**，并在
`quality_json.landmark_confidence_meaning` 中明确写出其含义。
详见 `docs/metric_definitions.md` §1.3.11。

### 2.5 输出 JSON（Adapter 出口契约）

> 下面是**契约结构示例**（数值为示意）。真实数值请以实际分析结果为准；
> 真实 demo 视频的实测值见 `docs/metric_definitions.md` §7.1。

```json
{
  "hand": "RIGHT",
  "algorithm_version": "ft-features-v1.0.0",
  "feature_schema_version": "1.0",
  "qc_version": "ft-qc-v1.0.0",

  "tapping_frequency": 3.42,
  "avg_amplitude": 0.55,
  "avg_speed": 0.83,
  "avg_cycle_duration": 0.29,

  "amplitude_cv": 0.19,
  "speed_cv": 0.20,
  "cycle_cv": 0.22,

  "amplitude_slope": -0.010,
  "speed_slope": -0.020,
  "cycle_slope": 0.003,

  "interruptions": 2,
  "valid_frame_ratio": 0.91,
  "avg_landmark_confidence": null,

  "severity_score": null,
  "severity_label": null,

  "analysis_config_json": {
    "normalization_method": "PALM_REFERENCE",
    "filter_method": "BUTTERWORTH",
    "filter_order": 4,
    "filter_cutoff_hz": 9.0,
    "filter_fs_source": "video_fps",
    "peak_distance": 5,
    "peak_height_factor": 0.5,
    "peak_prominence_factor": 0.5,
    "interruption_threshold_factor": 1.5,
    "interruption_threshold_basis": "median_cycle_duration",
    "interruption_rule_version": "v1.0.0",
    "min_valid_frame_ratio": 0.5,
    "min_cycle_count": 2,
    "handedness_convention": "TBD"
  },

  "quality_json": {
    "fps": 30.0,
    "frame_count": 450,
    "duration_sec": 15.0,
    "valid_frame_ratio": 0.91,
    "detected_frames": 410,
    "total_frames": 450,
    "avg_landmark_confidence": null,
    "normalization_method": "PALM_REFERENCE",
    "filter_method": "BUTTERWORTH",
    "feature_schema_version": "1.0",
    "notes": []
  },

  "raw_features_json": {
    "avg_percycle_max_speed": 1.62,
    "median_cycle_duration": 0.29,
    "cycle_durations": [0.30, 0.28, 0.31],
    "amplitudes": [0.54, 0.58, 0.52],
    "peak_frame_indices": [12, 21, 30],
    "trough_frame_indices": [8, 17, 26],
    "tapping_frequency_cycle_based": 3.45
  }
}
```

> ⚠️ `severity_score` / `severity_label` **始终为 `null`** —— 外部仓库不存在预训练严重度模型
> （已全仓搜索确认），`optimization_training.py` 不保存模型且无推理入口。
> 规格 V2 §41 明文：只有存在真实模型时才能写入，否则必须为 NULL。
>
> ⚠️ `avg_landmark_confidence` **当前为 `null`** —— MediaPipe Tasks API 的 `NormalizedLandmark`
> 不提供 `visibility`/`presence`。Phase 4 需实测确认可用替代来源（如 `handedness[i][0].score`）。

### 2.6 QC 错误契约（V2 §12 + V1 §47）

```json
{
  "error": {
    "code": "HAND_NOT_DETECTED",
    "message": "未能在足够的视频帧中检测到目标手，请重新录制。"
  }
}
```

| 错误码 | 触发 |
| --- | --- |
| `VIDEO_UNREADABLE` | OpenCV 打不开文件 |
| `VIDEO_FPS_INVALID` | `fps <= 0` |
| `VIDEO_TOO_SHORT` | `frame_count < 4*fps` 或时长 < 硬门限 |
| `HAND_NOT_DETECTED` | `detected_frames == 0` |
| `LOW_VALID_FRAME_RATIO` | `valid_frame_ratio < 0.5` |
| `LANDMARK_DISCONTINUOUS` | 关键点连续性不满足（门限待 Phase 4 定稿） |
| `INSUFFICIENT_CYCLES` | 有效周期 < 2 |
| `CUDA_OUT_OF_MEMORY` | 显存不足 |

**质量不足时禁止硬算结果。**

---

## 3. Pose 分析

### 3.1 架构（V1 §23.1 固定）

```
前端浏览器摄像头
  → getUserMedia 采集
  → 前端实时绘制骨架（MediaPipe Pose，WASM/JS）
  → 上报关键点/角度帧数据（批量）
POST /api/movement/sessions/{session_id}/frames/batch
  → 后端统一 Pose Service 计算最终指标
POST /api/movement/sessions/{session_id}/complete
```

**分工原则**：前端负责**实时骨架可视化与交互反馈**；**最终指标一律由后端统一计算**，
避免前端版本差异导致指标不可比。

### 3.2 文件

```
backend/app/ml/pose/
├─ analyzer.py    # PoseAnalyzer：帧序列 → 原始角度指标
├─ exercises.py   # 5 个动作定义（exercise_definition + 版本号）
└─ metrics.py     # ROM / Symmetry / Stability / 完成度（公式必须在 exercises 中配置）
```

### 3.3 规则

- **先保存可解释原始指标**（`left_shoulder_max_angle_deg`、`trunk_angle_deg`、`hold_time_sec`、
  `repetition_count`、`movement_speed_deg_per_sec`、`angle_std_deg`、`valid_pose_frame_ratio` …），
  再计算 `range_of_motion` / `symmetry_score` / `stability_score`。
- **每一个 Score 必须有确定公式**，公式在 `exercise definition` 中配置并带
  `exercise_definition_version`。**禁止随机返回 0～100 分数。**
- 公式未固化前（`docs/metric_definitions.md` §3.4 中标 `TBD` 的项），
  **相关 Score 不得入库、不得展示**；原始指标可先行入库。

---

## 4. 模型加载生命周期

### 4.1 正确流程（V2 §50 强制）

```
FastAPI startup (lifespan)
  → 读取配置
  → 尝试加载 MicroExpressionAnalyzer.load()   # 失败不抛出，仅记录状态
  → 尝试加载 FingerTappingAnalyzer（MediaPipe HandLandmarker 常驻实例）
  → 尝试加载 PoseAnalyzer（如需要）
  → 记录 ModelRegistry 状态
→ 之后所有请求复用已加载实例
```

**禁止每个请求重新加载模型。** MediaPipe 的 `hand_landmarker.task` 也必须复用
（用 `BaseOptions(model_asset_buffer=...)` 一次性读入内存，常驻 `HandLandmarker` 实例）。

### 4.2 模型注册表

```python
@dataclass
class ModelStatus:
    name: str
    version: str
    status: Literal["MODEL_NOT_CONFIGURED", "LOADING", "READY",
                    "UNAVAILABLE", "LOAD_FAILED"]
    device: str | None          # "cuda:0" / "cpu"
    detail: str | None
    loaded_at: datetime | None
```

`GET /api/system/models` 返回全部状态。`/dashboard` 与 `/system/model-status` 页面直接消费该接口。

### 4.3 启动不阻塞原则

任何模型加载失败**都不得**导致 FastAPI 启动失败。
系统必须能在"模型全部不可用"的状态下正常启动，并在页面上诚实显示 `Unavailable`。

---

## 5. GPU / 推理并发管理

### 5.1 单并发（V2 §31、§49 强制）

```python
# backend/app/jobs/gpu_inference.py
class GPUInferenceManager:
    """保证 GPU 推理单并发，避免多请求同时占用显存导致 OOM。"""
    def __init__(self, concurrency: int = 1):
        self._sem = asyncio.Semaphore(concurrency)

    @asynccontextmanager
    async def acquire(self):
        async with self._sem:
            yield
```

- 并发度由 `GPU_INFERENCE_CONCURRENCY` 控制，**默认 1**。
- 长任务通过 Job 机制（`PENDING / RUNNING / SUCCESS / FAILED`）异步执行，
  使用 `FastAPI BackgroundTasks` 或 `ThreadPoolExecutor`；
  **第一版不引入 Redis / Celery / Kafka / 微服务 / Kubernetes**（V2 §49、§60）。
- 前端通过 `GET /api/jobs/{job_id}` 轮询。

### 5.2 显存保护（本机 8 GB 显存）

- 加载后调用 `torch.cuda.empty_cache()`（仅在必要时）。
- 推理用 `torch.inference_mode()`，禁止保留计算图。
- 捕获 `torch.cuda.OutOfMemoryError` → 返回 `CUDA_OUT_OF_MEMORY`（HTTP 503），
  **不得**静默重试到 CPU 并混入不同来源的结果。
- 服务器侧（无 GPU）退化方案见 `docs/server_deployment_plan.md`。

### 5.3 设备选择

```
USE_GPU=true 且 torch.cuda.is_available()  → cuda:0
否则                                        → cpu
```

设备必须写入结果的 `quality_json.device`，避免 CPU/GPU 结果被误当作同一来源比较。

---

## 6. 作业（Job）状态机

```
PENDING → RUNNING → SUCCESS
                 → FAILED
```

`GET /api/jobs/{job_id}` 返回：

```json
{
  "job_id": "uuid",
  "status": "SUCCESS",
  "job_type": "FINGER_TAPPING_ANALYSIS",
  "progress": 1.0,
  "result_ref": {"finger_tapping_result_id": "uuid"},
  "error": null,
  "created_at": "...",
  "started_at": "...",
  "finished_at": "..."
}
```

失败时 `error` 使用 §1.7 / §2.6 的统一错误结构。

---

## 7. Mock 策略（V2 §67、§32 强制）

| 项 | 规则 |
| --- | --- |
| 默认 | `DEMO_MOCK_MODE=false` |
| 允许 Mock 的条件 | **仅当** `DEMO_MOCK_MODE=true` |
| 真实模型不可用时 | **必须**显示真实不可用状态（`MODEL_NOT_CONFIGURED` / `Unavailable`） |
| **禁止** | 后台偷偷返回 Mock 冒充真实结果 |
| Mock 数据标记 | 响应中 `is_mock: true`；页面必须显著标注 **`DEMO DATA`**；不得与真实结果混淆 |
| 落库 | Mock 结果**不得**写入正常的 `micro_expression_results` / `finger_tapping_results` 流程，或必须带 `is_mock` 标记且趋势图默认排除 |

---

## 8. 微表情模型接入检查清单（拿到模型后的执行顺序）

1. 把模型目录放到 `models/micro_expression/`（本地）或 `/opt/pd-rehab/models/micro_expression/`（服务器）。
2. 阅读其 `README` / 源码，填实 `labels.json`（**只用真实标签，不猜**）。
3. 记录 `requirements.txt`，**复核 PyTorch / CUDA 版本与本机 sm_120（RTX 5070 Laptop）兼容性**。
   若其要求 CUDA ≤ 12.6，则本机 GPU 不可用 —— 立即上报，**不得**安装不含 sm_120 kernel 的 wheel 谎报可用。
4. 运行模型自带 demo，记录真实输入规范（时长 / FPS / 分辨率 / 预处理）与真实输出字段。
5. 在 `adapter.py` 中实现 `load()` / `analyze()`，**只做转译，不做加工**。
6. 更新 `MODEL_NAME` / `MODEL_VERSION` / `feature_schema_version`。
7. 用真实视频跑通 → 比对 `raw_output_json` 与页面展示是否一致。
8. 更新 `docs/metric_definitions.md` §5（把所有 `NOT_AVAILABLE` 改为真实状态）。
9. 补 `backend/tests/` 中的 micro-expression schema 测试。
10. Git commit（`feat:` + 注明模型版本）。

> 在第 10 步之前，页面必须一直显示 `MODEL_NOT_CONFIGURED`，**不得**用任何占位数据填充图表。

---

> 本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。
