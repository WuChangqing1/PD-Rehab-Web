# 指标定义文档（metric_definitions.md）

> 项目：PD-Rehab-Web —— 帕金森病智能辅助识别、运动状态量化与数字康复训练平台
> 版本：**Phase 5 更新版（v0.7.0）** —— Finger Tapping 与钢琴训练指标均已实现并实测；
> v0.6.0 新增 §2.3.4 数据来源标记 `input_source`，并把 §2.3.1.1 的实测证据来源订正为「脚本自检」；
> v0.7.0 新增 §2.2.1 键位映射与阶段目标的偏差记录，§2.5 把"每轮只改少量参数"写成硬上限
> （规则引擎 `piano-difficulty-v1.0.0` → **v1.1.0**）
> 医疗声明：本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。
> 本文档中所有指标的 **"医学诊断" 一栏默认均为 `NO`**。任何未确认的定义一律写 `TBD`，**不做猜测**。

---

## 0. 文档规则（强制）

1. **真实算法代码 > 需求文档。** 若规格文档的指标定义与
   `D:\CodingData\Github\VideoBased-PD-Biomarkers` 的真实实现不同，**以仓库代码为准**，并在
   §7「文档与真实实现的差异」中记录。**不允许为了"看起来符合文档"而修改算法。**
2. 仓库已实现的指标 → 来源标记 `EXTERNAL_REPO`，逐条附文件与行号。
3. 仓库未实现的指标 → 来源标记 **`NEEDS_IMPLEMENTATION`**，并在实现前补全本文档条目。
4. 每个指标必须记录：中文名称 / 英文 key / 输入 / 计算公式 / 单位 / 异常处理 /
   最小有效数据要求 / 来源模块 / 来源代码 / 算法版本 / 是否用于展示 / 长期趋势 / 难度调整 / 医学诊断。
5. 所有进入长期趋势的指标，**必须**同时存 `algorithm_version`（见 §8 版本登记表）。
6. `severity_score` / `severity_label` 在真实模型接入前**必须为 `NULL`**。
7. 本文档中 `TBD` 表示**尚未确认**，不是"待办事项"，禁止在实现时用猜测值替代。

### 状态标记说明

| 标记 | 含义 |
| --- | --- |
| `EXTERNAL_REPO` | 外部仓库已有真实实现，公式直接取自其代码 |
| `EXTERNAL_REPO_BUGFIX` | 外部仓库有实现但存在缺陷，新项目按**修正后**公式实现，差异已记录 |
| `NEW_DERIVED` | 由外部仓库已有指标派生（如频率由周期取倒数），需显式记录派生关系 |
| `NEW` | 外部仓库没有，新项目自行实现 |
| `NEEDS_IMPLEMENTATION` | 尚未实现，规格要求存在 |
| `NOT_AVAILABLE` | 真实模型未提供，当前不可产出 |

### 通用约定

- `d[t]`：**归一化后的拇指-食指距离时间序列**（见 §1.2），无量纲（除以掌宽）。
- `fps`：视频真实帧率（`cv2.CAP_PROP_FPS`）。**注意**：外部仓库滤波阶段硬编码 30.0，见 §7-D2。
- `peaks` / `troughs`：对 `d` 滤波后的极大/极小值帧索引。
- `CV` 统一公式：`CV = std(x) / mean(x)`。**当 `mean(x)` 接近 0 时必须安全处理，禁止 Inf / NaN**。
  实现约定：`|mean| < EPS(=1e-9)` → 返回 `None`（JSON `null`）并写入 `quality_json.notes`。
- 所有 `*_slope` 的自变量统一为 **cycle index**（`0,1,2,...`），**不是**真实时间。
  单位因此是"每周期变化量"，不是"每秒变化量"。这一点必须在前端展示时注明。

---

## 1. Finger Tapping

### 1.1 输入规范

| 项 | 值 | 来源 |
| --- | --- | --- |
| 输入 | `video`（multipart）+ `hand` ∈ {`LEFT`,`RIGHT`} + `medication_state` ∈ {`ON`,`OFF`,`UNKNOWN`} | V2 §9.1 |
| 建议时长 | 10～20 秒 | V2 §9.1 |
| 录制前倒计时 | 3 秒 | V2 §9.1 |
| 支持格式 | mp4 / mov / avi（Demo 优先 mp4） | V1 §11.2 |
| 单次分析只处理**一只手** | MediaPipe `handedness` 过滤 | 外部仓库 |

### 1.2 信号定义

| 项 | 定义 | 来源 |
| --- | --- | --- |
| 关键点 | MediaPipe HandLandmarker，21 个手部关键点，`num_hands=2`，`VisionRunningMode.VIDEO` | `keypoint_extraction.py:280-285` |
| 时间戳 | `int(cap.get(cv2.CAP_PROP_POS_MSEC))` | `keypoint_extraction.py:294` |
| 归一化（**PALM_REFERENCE**） | 以 `WRIST` 为原点平移，再除以 `‖INDEX_FINGER_MCP − WRIST‖`（3D 欧氏距离）；分母 < `1e-5` 时钳位到 `1e-5` | `keypoint_extraction.py:88-112` |
| 距离信号 | `d = ‖normalized(THUMB_TIP) − normalized(INDEX_FINGER_TIP)‖`（3D 欧氏距离） | `keypoint_extraction.py:319-324` |
| 角度信号（备选，未启用） | 像素坐标下向量 `WRIST→THUMB_TIP` 与 `WRIST→INDEX_FINGER_TIP` 的夹角（度） | `keypoint_extraction.py:46-82` |
| 滤波 | Butterworth 低通，`order=4`，`cutoff=9.0 Hz`（ft），`nyq=0.5*fs`，`fs` **硬编码 30.0**，`scipy.signal.filtfilt`（零相位） | `feature_extraction.py:32-43` |
| 手别判定 | `handedness[0].category_name == hand_to_track` | `keypoint_extraction.py:250,302` |

> ⚠️ **手别假设待确认**：MediaPipe 的 `handedness` 按**前置摄像头镜像**约定输出（与解剖手别相反）。
> 外部仓库直接字符串比对，未做镜像纠正。**产品层必须在 Phase 4 用真实视频验证**，
> 并把结论写入本节与 `analysis_config_json.handedness_convention`。当前状态：`TBD`。

---

### 1.3 P0 指标

#### 1.3.1 `tapping_frequency` 敲击频率

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 敲击频率 |
| 英文 key | `tapping_frequency` |
| 输入 | `peaks`（峰值帧索引数组）、`fps`、有效分析时长 |
| 计算公式 | `tapping_frequency = (len(peaks) - 1) / (peak_span_sec)`，其中 `peak_span_sec = (peaks[-1] - peaks[0]) / fps` |
| 单位 | **Hz（次/秒）** —— 数据库 `unit` 字段必须记录 |
| 异常处理 | `len(peaks) < 2` → `None`；`peak_span_sec <= 0` → `None`；结果写入 `quality_json.notes` |
| 最小有效数据要求 | ≥ 2 个 peak，且 span > 0 |
| 来源模块 | **`NEW_DERIVED`**（外部仓库只输出 `avg_cycle_duration`） |
| 来源代码 | 外部仓库**无此字段**（已全仓搜索确认）。新项目由 `1 / avg_cycle_duration` 与上式两种口径并行计算并交叉校验 |
| 算法版本 | `ft-features-v1.0.0` |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| 备注 | 规格 V2 §11.1 定义为"有效敲击周期数 / 有效分析时长"。该定义与
`(len(peaks)-1)/span` 在等间隔假设下等价，但边界（首尾半周期）处理不同。
**两值都存**：`tapping_frequency`（规格口径）与 `tapping_frequency_cycle_based`（周期倒数口径），
并在 `analysis_config_json` 记录口径。**在 Phase 4 用真实视频比对后固化其中之一。** |

#### 1.3.2 `avg_amplitude` 平均动作幅度

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 平均动作幅度 |
| 英文 key | `avg_amplitude` |
| 输入 | 归一化距离序列 `d`、`peaks`、`troughs` |
| 计算公式 | ① 先对齐：`while troughs[0] > peaks[0]: peaks = peaks[1:]`（丢弃首个 peak 之前的 trough）<br>② 对每个 `peak`，取其**左侧最近**的 `trough`：`last_trough = max{t ∈ troughs : t < peak}`<br>③ `amp_i = |d[peak_i] − d[last_trough_i]|`<br>④ `avg_amplitude = mean(amp_i)` |
| 单位 | 无量纲（掌宽归一化后的比值，1.0 = 一个掌宽） |
| 异常处理 | `amplitudes` 为空 → `None`（**禁止** `np.mean([])` 产生 NaN） |
| 最小有效数据要求 | ≥ 1 个有效 (peak, trough) 对；Phase 4 起建议 ≥ 3 才写库 |
| 来源模块 | `EXTERNAL_REPO` |
| 来源代码 | `src/feature extraction/feature_extraction.py:54-72` |
| 算法版本 | `ft-features-v1.0.0` |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| 备注 | 归一化方式已固定为 **PALM_REFERENCE**（`wrist→INDEX_FINGER_MCP`），必须存入 `quality_json.normalization_method`。规格 V2 §11.2 要求"opening peak 与 closing trough 之间的差"，仓库实现用的是**最近左侧 trough**，与规格文字一致，判定为**无冲突**。 |

#### 1.3.3 `avg_speed` 平均动作速度

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 平均动作速度 |
| 英文 key | 数据库 `finger_tapping_results` 字段为 `avg_speed`（V2 §41）。仓库原始字段名有两个，见下 |
| 输入 | 滤波后 `d`、`fps`、`peaks` |
| 计算公式 | ① `speed_signal = np.diff(d) / (1/fps)`（一阶前向差分 ÷ 采样间隔）<br>② 第 i 个周期窗口 `w_i = speed_signal[peaks_i : peaks_{i+1}]`<br>③ `avg_percycle_avg_speed = mean_i( mean(|w_i|) )`（**取绝对值**）<br>④ 另有 `avg_percycle_max_speed = mean_i( percentile(|w_i|, 95) )` |
| 单位 | 1/秒（掌宽/秒，即 normalized distance per second） |
| 异常处理 | 窗口为空则跳过；`per_cycle_speed_avg` 为空 → `None` |
| 最小有效数据要求 | ≥ 2 个 peak（才能切出 ≥ 1 个周期窗口） |
| 来源模块 | `EXTERNAL_REPO` |
| 来源代码 | `src/feature extraction/feature_extraction.py:47-49, 81-99` |
| 算法版本 | `ft-features-v1.0.0` |
| 用于展示 | ✅（默认展示 `avg_percycle_avg_speed`） |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| 备注 | ⚠️ **命名歧义需在 Phase 4 决策**：仓库同时输出 `avg_percycle_max_speed` 与 `avg_percycle_avg_speed`，
而 V2 §41 只有一个 `avg_speed`。**默认映射：`avg_speed := avg_percycle_avg_speed`**，
另一个存入 `raw_features_json.avg_percycle_max_speed` 并在 `docs/api_decisions.md` 记录。 |
| 采样间隔口径 | `1/fps`，`fps` 取视频真实帧率（**不使用**滤波阶段硬编码的 30.0） |
| 是否取绝对值 | **是**（仓库 `np.abs(window_speed)`） |
| 是否区分 opening / closing | **否**（仓库不区分）。规格 V2 §11.3 要求"必须明确"→ 本条目即为明确记录 |

#### 1.3.4 `avg_cycle_duration` 平均周期时长

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 平均敲击周期时长 |
| 英文 key | `avg_cycle_duration` |
| 输入 | `peaks`、`fps` |
| 计算公式 | `cycle_durations = np.diff(peaks) / fps`；`avg_cycle_duration = mean(cycle_durations)` |
| 单位 | **秒（s）** |
| 异常处理 | `len(peaks) < 2` → `None` |
| 最小有效数据要求 | ≥ 2 个 peak |
| 来源模块 | `EXTERNAL_REPO` |
| 来源代码 | `src/feature extraction/feature_extraction.py:108-111` |
| 算法版本 | `ft-features-v1.0.0` |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| 备注 | 仓库同时计算 `median_cycle_duration`，但**未写入特征字典**。新项目将其存入 `raw_features_json.median_cycle_duration`（零成本、对离群更稳健）。 |

#### 1.3.5 `amplitude_cv` 幅度变异系数

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 幅度变异系数 |
| 英文 key | 数据库字段名 `amplitude_cv`（V2 §41）；仓库原始字段名 `cov_amp` |
| 输入 | `amplitudes` |
| 计算公式 | `CV = std(amplitudes) / mean(amplitudes)`，`std` 为 **总体标准差（`ddof=0`，numpy 默认）** |
| 单位 | 无量纲（比值） |
| 异常处理 | `len(amplitudes) < 2` → `None`；`|mean| < 1e-9` → `None`；**禁止 Inf / NaN** |
| 最小有效数据要求 | ≥ 2 个有效周期幅度 |
| 来源模块 | `EXTERNAL_REPO` |
| 来源代码 | `src/feature extraction/feature_extraction.py:124-125` |
| 算法版本 | `ft-features-v1.0.0` |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |

#### 1.3.6 `speed_cv` 速度变异系数

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 速度变异系数 |
| 英文 key | `speed_cv`（V2 §41）；仓库有 **两个** 字段：`cov_percycle_avg_speed`、`cov_percycle_max_speed` |
| 输入 | `per_cycle_speed_avg[]` 或 `per_cycle_speed_maxima[]` |
| 计算公式 | **修正后（新项目实现）**：<br>`cov_percycle_avg_speed = std(per_cycle_speed_avg) / mean(per_cycle_speed_avg)`<br>`cov_percycle_max_speed = std(per_cycle_speed_maxima) / mean(per_cycle_speed_maxima)` |
| 单位 | 无量纲 |
| 异常处理 | 样本数 < 2 或 `|mean| < 1e-9` → `None` |
| 最小有效数据要求 | ≥ 2 个周期速度样本 |
| 来源模块 | **`EXTERNAL_REPO_BUGFIX`** |
| 来源代码 | `src/feature extraction/feature_extraction.py:127-131` |
| 算法版本 | `ft-features-v1.0.0` |
| 用于展示 | ✅（`speed_cv := cov_percycle_avg_speed`） |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| **已知上游缺陷** | 第 128 行：`cov_per_cycle_speed_maxima = std_amp / mean_percycle_max_speed` —— **分子误用 `std_amp`（幅度标准差）**，正确应为 `std_per_cycle_speed_maxima`。该 bug 使 `cov_percycle_max_speed` 语义错误，**已被上游仓库污染为"幅度标准差 / 平均最大速度"**。新项目按**修正后**公式实现，并把本差异写入 §7-D1。另外 `cov_percycle_avg_speed`（131 行）用的是 `std_per_cycle_speed_avg`，是**正确的**。 |

#### 1.3.7 `cycle_duration_cv` 周期时长变异系数

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 周期时长变异系数 |
| 英文 key | 数据库字段名 `cycle_cv`（V2 §41）；需求文档正文用 `cycle_duration_cv`（V2 §7.1）；仓库字段名 `cov_cycle_duration` |
| 输入 | `cycle_durations` |
| 计算公式 | `CV = std(cycle_durations) / mean(cycle_durations)` |
| 单位 | 无量纲 |
| 异常处理 | 样本数 < 2 → `None`；`|mean| < 1e-9` → `None` |
| 最小有效数据要求 | ≥ 2 个周期 |
| 来源模块 | `EXTERNAL_REPO` |
| 来源代码 | `src/feature extraction/feature_extraction.py:121-122` |
| 算法版本 | `ft-features-v1.0.0` |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| 备注 | ⚠️ **命名不一致（需在 Phase 4 统一）**：V2 §7.1 写作 `cycle_duration_cv`，V2 §41 数据库字段写作 `cycle_cv`。按"数据库字段以 V2 §41 为准"处理：DB 列名 `cycle_cv`，API JSON 同时提供 `cycle_duration_cv` 别名。记入 `docs/api_decisions.md`。 |

#### 1.3.8 `amplitude_slope` / `speed_slope` / `cycle_slope` 趋势斜率

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 幅度斜率 / 速度斜率 / 周期斜率 |
| 英文 key | DB 列名：`amplitude_slope`、`speed_slope`、`cycle_slope`（V2 §41）；仓库字段名：`amp_slope`、`speed_slope`、`cycle_slope` |
| 输入 | 逐周期序列 `amplitudes[]` / `per_cycle_speed_avg[]` / `cycle_durations[]` |
| 计算公式 | 普通最小二乘一元线性回归 `y = a + b·x`，`x = np.arange(len(y))`（**cycle index，非时间**），取斜率 `b`（`sklearn.linear_model.LinearRegression.coef_[0]`） |
| 单位 | 幅度斜率：无量纲/周期；速度斜率：(1/秒)/周期；周期斜率：秒/周期 |
| 异常处理 | 样本数 < 2 → `None`（线性回归至少需 2 点；回归无意义时返回 `None` 而非 0） |
| 最小有效数据要求 | ≥ 2 个点；**趋势解释建议 ≥ 5 个点**（少于 5 时同时在 `quality_json.notes` 标注 `slope_low_sample`） |
| 来源模块 | `EXTERNAL_REPO` |
| 来源代码 | `feature_extraction.py:75-79`（幅度）、`102-106`（速度）、`113-116`（周期） |
| 算法版本 | `ft-features-v1.0.0` |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| 备注 | 斜率**只**用于描述"单次任务内部是否出现持续变化趋势"。**禁止**解释为"病情加重/改善"（V2 §11.6 明文要求）。前端文案固定为"任务内变化趋势"。 |

#### 1.3.9 `interruptions` 中断次数

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 异常停顿（中断）次数 |
| 英文 key | `interruptions`（V2 §41）；仓库字段名 `num_interruptions` |
| 输入 | `cycle_durations` |
| 计算公式 | `threshold = 1.5 × median(cycle_durations)`；`interruptions = |{c ∈ cycle_durations : c > threshold}|` |
| 单位 | 次（整数） |
| 异常处理 | `cycle_durations` 为空 → `interruptions = 0`（且 `quality_json.notes += 'no_cycle'`）；`median = 0` → `None` + 标注 |
| 最小有效数据要求 | ≥ 1 个周期时长 |
| 来源模块 | `EXTERNAL_REPO` |
| 来源代码 | `src/feature extraction/feature_extraction.py:133-135` |
| 算法版本 | `ft-features-v1.0.0` |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| **配置化要求（V2 §11.7 强制）** | 阈值系数 `1.5` 与统计量 `median` **必须配置化**，不得散落在代码中。实现为 `analysis_config_json`：<br>`{"interruption_threshold_factor": 1.5, "interruption_threshold_basis": "median_cycle_duration", "interruption_rule_version": "v1.0.0"}`<br>**单次分析必须可复现**：`analysis_config_json` 与 `algorithm_version` 一并入库。 |
| 备注 | 规格 V2 §11.7 要求"首先检查外部算法仓库是否已有中断定义"→ **已确认存在**，故直接采用其定义（阈值 1.5×median），无需自行发明。 |

#### 1.3.10 `valid_frame_ratio` 有效帧比例

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 有效帧比例 |
| 英文 key | `valid_frame_ratio` |
| 输入 | `total_frames`、`detected_frames`（检测到**目标手**的帧数） |
| 计算公式 | `valid_frame_ratio = detected_frames / total_frames` |
| 单位 | 无量纲（0～1） |
| 异常处理 | `total_frames == 0` → 直接判 `VIDEO_UNREADABLE` 错误，不产出指标 |
| 最小有效数据要求 | 见 §1.4 QC 门限 |
| 来源模块 | **`NEW`**（外部仓库 `keypoint_extraction.py:347` 只做 `detected_frames/total_frames >= 0.5` 判断，**不保存该比例**；`ft_video_analysis.py` 统计了 `detected_frames` 但**从未使用**） |
| 来源代码 | 外部仓库 `keypoint_extraction.py:269-271, 315-316, 347`（统计逻辑）；新项目负责持久化 |
| 算法版本 | `ft-qc-v1.0.0` |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅（作为质量元数据） |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| DB 列 | `finger_tapping_results.valid_frame_ratio`（V2 §41） |

#### 1.3.11 `avg_landmark_confidence` 平均手别置信度

> **Phase 4 已实测确认。** 本节在 Phase 0 的结论（"visibility / presence 可能不存在"）基础上，
> 用真实推理给出了确定答案，并据此改变了字段语义。**字段名保持不变**（V2 §41 已固定 DB 列名），
> 但其含义必须在 UI、报告与 `quality_json` 中如实说明。

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 平均**手别判定**置信度（不是逐关键点可见度） |
| 英文 key | `avg_landmark_confidence`（DB 列名沿用 V2 §41，未改动） |
| 输入 | 每帧目标手 `handedness[0].score` |
| 计算公式 | `avg_landmark_confidence = mean(handedness_score_f)`，对**检测到目标手的帧**取均值；无检测帧则为 `None` |
| 单位 | 无量纲（0～1） |
| 异常处理 | 无任何检测帧 → `None`；非有限值 → `None`；结果同时写入 `quality_json.avg_landmark_confidence` |
| 最小有效数据要求 | ≥ 1 个检测到目标手的帧 |
| 来源模块 | **`NEW`**（媒体管道侧真实字段，非需求文档定义） |
| 来源代码 | `backend/app/ml/finger_tapping/pipeline.py::_decode`，`quality.py::evaluate_detection` |
| 算法版本 | `ft-qc-v1.0.0` |
| 用于展示 | ✅（**必须同时显示含义说明**） |
| 用于长期趋势 | ✅（作为质量元数据） |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| **Phase 4 实测结论（327 帧真实视频）** | ① `NormalizedLandmark.visibility` 与 `.presence` 属性**存在但恒为 `None`** —— 327/327 帧全部为 `None`，**不可用**。Phase 0 的"属性可能不存在"判断方向正确，实际是"存在但无值"。<br>② `handedness[0].score` **是真实且变化的**：范围 0.9218～0.9744，327 帧中有 **326 个不同取值**，可用作真实置信度。<br>③ 因此本字段保存**手别分类置信度**，并在 `quality_json.landmark_confidence_meaning` 中写明：<br>`"MediaPipe handedness classification score (left/right), not a per-landmark visibility score; the Tasks API returns null for visibility and presence."` |
| **禁止** | 不得把该值描述为"关键点可见度"或"关键点置信度"；不得用 `1.0`、`0.95` 之类占位值填充；无检测帧时必须为 `NULL` |
| 规格要求 | V2 §11"如可得到：landmark confidence 也保存"→ 现已可得到**真实**来源，故不再为 NULL，但含义已按事实修正 |

#### 1.3.12 `left_right_difference` 左右手差异

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 左右手差异 |
| 英文 key | `left_right_difference`（V2 §13） |
| 输入 | 同一次综合评估中 `hand=LEFT` 与 `hand=RIGHT` 的两条 `finger_tapping_results` |
| 计算公式 | **绝对差（V2 §13 优先）**：`left_right_difference(metric) = left_metric − right_metric`<br>可选附加：`asymmetry_ratio = (left − right) / ((left + right) / 2)` |
| 单位 | 与对应 `metric` 相同（差值单位） |
| 异常处理 | 任一侧缺失 → `None`（**禁止**用 0 代替缺失）；`(left+right)` ≈ 0 → `asymmetry_ratio = None` |
| 最小有效数据要求 | 左右手两次独立分析均通过 QC |
| 来源模块 | **`NEW`**（外部仓库**不产出**任何左右差异字段；左右手是两个独立视频、两次独立运行） |
| 来源代码 | — |
| 算法版本 | `ft-compare-v1.0.0` |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌ |
| 用于医学诊断 | **NO** |
| **需要的成对指标（V2 §13 最少要求）** | `left_avg_amplitude` / `right_avg_amplitude`、`left_avg_speed` / `right_avg_speed`、`left_tapping_frequency` / `right_tapping_frequency`、`left_cycle_cv` / `right_cycle_cv` |
| **禁止** | 不得用单个左右差异直接判断疾病侧别（V2 §13 明文）。前端文案：`左右手运动表现差异`，**不得**写"患侧/健侧"。 |
| 存放位置 | **Phase 4 已定稿**：计算于结果层（`assessment_session` 级聚合），**不写入单条 `finger_tapping_results` 行**。<br>实现位置：`api/assessment_sessions.py::_session_summary` → `services/assessment_service.py::compare_left_right`。<br>已实现 4 个成对指标：`avg_amplitude`、`avg_speed`、`tapping_frequency`、`cycle_cv`，各自给出 `left` / `right` / `absolute_difference` / `asymmetry_ratio`。<br>通过 `GET /api/assessment-sessions/{id}/finger-tapping` 的 `comparisons` 数组返回 |

---

### 1.4 Finger Tapping 质量控制（QC）

执行顺序与错误码（V2 §12 + V1 §48）：

| 顺序 | 检查项 | 门限 | 失败错误码 | 触发条件 |
| --- | --- | --- | --- | --- |
| 1 | 视频可读 | `cv2.VideoCapture.isOpened() == True` | `VIDEO_UNREADABLE` | 否 |
| 2 | FPS 有效 | `fps > 0` | `VIDEO_FPS_INVALID` | 否 |
| 3 | 帧数足够 | `frame_count >= 4 × fps`（源自仓库 `video_length >= 4*fps`） | `VIDEO_TOO_SHORT` | 否 |
| 4 | 最短时长 | `duration_sec >= 3.0`（`FT_MIN_DURATION_SEC`；Phase 4 实测 3 秒以下的视频无法产生 ≥ 2 个周期，故保持 3.0） | `VIDEO_TOO_SHORT` | 否 |
| 5 | 目标手检测比例 | `valid_frame_ratio >= 0.5`（源自仓库 `detected_frames/total_frames >= 0.5`） | `LOW_VALID_FRAME_RATIO` | 否 |
| 6 | 关键点连续性 | **Phase 4 定稿**：`longest_continuous_run / frame_count >= 0.25`（`MIN_CONTINUOUS_FRAME_RATIO`，上游未定义，本系统新增并配置化） | `LANDMARK_DISCONTINUOUS` | 否 |
| 7 | 检测到目标手 | `detected_frames == 0` | `HAND_NOT_DETECTED` | 否 |
| 8 | 有效周期数 | `len(cycle_durations) >= 2` | `INSUFFICIENT_CYCLES` | 否 |

> **门限 5 与 6 的关系（Phase 4 实测）**：每帧交替检测成功/失败的视频，其
> `valid_frame_ratio` 恰为 0.5，能通过门限 5，但时间序列是断裂的、无法可靠定峰。
> 门限 6 正是为拦截这种情况而设：门限 5 只统计"总共有多少帧检测到"，
> 门限 6 关心"是否连续"。两者都在 `analysis_config_json` 中记录。
>
> 门限 5、6 均在 `backend/tests/test_finger_tapping_pipeline.py` 中有对应测试。

**质量不足时必须返回明确错误，禁止硬算结果**（V2 §12）。
所有拒绝路径（含 `VIDEO_UNREADABLE`）都返回同一结构，并在 `detail.quality`
中附带**实测的质量报告**，便于操作者判断原因：

```json
{
  "error": {
    "code": "HAND_NOT_DETECTED",
    "message": "未能在任何视频帧中检测到目标手，请重新录制。",
    "detail": {
      "quality": {
        "fps": 30.0,
        "frame_count": 210,
        "detected_frames": 0,
        "valid_frame_ratio": 0.0,
        "error_code": "HAND_NOT_DETECTED"
      }
    }
  }
}
```

**`quality_json` 必须保存（V2 §12 建议 + 强制）**，Phase 4 实际写入字段：

```json
{
  "passed": true,
  "fps": 30.0,
  "frame_count": 210,
  "width": 456,
  "height": 446,
  "duration_sec": 7.0,
  "detected_frames": 210,
  "total_frames": 210,
  "valid_frame_ratio": 1.0,
  "longest_continuous_run": 210,
  "continuous_frame_ratio": 1.0,
  "analyzed_samples": 210,
  "cycle_count": 14,
  "avg_landmark_confidence": 0.9501,
  "landmark_confidence_meaning": "MediaPipe handedness classification score (left/right), not a per-landmark visibility score; the Tasks API returns null for visibility and presence.",
  "normalization_method": "PALM_REFERENCE",
  "filter_method": "BUTTERWORTH",
  "filter_order": 4,
  "filter_cutoff_hz": 9.0,
  "filter_fs_used_hz": 30.0,
  "feature_schema_version": "1.0",
  "error_code": null,
  "error_message": null,
  "notes": []
}
```

> `avg_landmark_confidence` 的含义见 §1.3.11 —— 它是**手别判定置信度**，
> 不是逐关键点可见度，页面与报告必须照此表述。

---

### 1.5 P1 指标（外部仓库审计结论）

| 规格要求的 P1 指标 | 外部仓库状态 | 标记 |
| --- | --- | --- |
| `opening_speed` | **不存在**（仓库不区分 opening / closing） | `NEEDS_IMPLEMENTATION` |
| `closing_speed` | **不存在**（同上） | `NEEDS_IMPLEMENTATION` |
| `interval_distribution` | **不存在**（仓库只存 `cycle_durations` 用于算 CV/slope，**序列本身未持久化**） | `NEEDS_IMPLEMENTATION` |
| `asymmetry_ratio` | **不存在**（仓库无左右比较） | `NEEDS_IMPLEMENTATION` |

---

### 1.6 明确不实现的字段

| 字段 | 状态 | 依据 |
| --- | --- | --- |
| `severity_score` | **必须为 `NULL`** | 外部仓库**无任何**预训练分类模型（已全仓搜索 `*.pt/*.pth/*.ckpt/*.onnx/*.engine/*.pkl/*.joblib` → 无命中）；`optimization_training.py` **不保存模型**、**无推理入口**。V2 §41 明文："只有外部仓库存在真实模型时才能写入，否则必须为 NULL" |
| `severity_label` | **必须为 `NULL`** | 同上 |

> ⚠️ 外部仓库的 `optimization_training.py` 训练的是 **MDS-UPDRS 0–4 序数 5 分类**（不是 PD/Non-PD 二分类），
> 且需要 PEP 私有数据库，**无法**在本项目复用为在线推理。若未来要用，必须：① 拿到数据与权重；
> ② 明确分类目标与标签语义；③ 走 Adapter 并标注模型版本与适用范围。

---

## 2. 虚拟钢琴（Piano）

> **状态：Phase 5 已实现并在浏览器中实测跑通。**
> 实现位置：`frontend/src/piano/`（引擎、出题、指标、规则引擎）+ `backend/app/utils/piano_metrics.py`（服务端权威指标）。
> 音源与键位来源见 `NOTICE` §3。

### 2.1 时间基准定义（**必须严格区分**，V2 §16）

| 概念 | 定义 | 公式 | 单位 |
| --- | --- | --- | --- |
| `cue_onset_time_ms` | **刺激真正出现 / 允许响应**的时间（相对 session 起点） | — | ms |
| `target_time_ms` | 目标节拍/判定点时间 | — | ms |
| `actual_time_ms` | 用户实际按键时间 | — | ms |
| **`response_latency_ms`** | **反应延迟**：刺激出现 → **首次有效按键** | `response_latency_ms = first_valid_response_time − cue_onset_time` | ms |
| **`timing_error_ms`** | **节拍误差**：目标时间 → 实际按键时间 | `timing_error_ms = actual_time_ms − target_time_ms` | ms |

> **两者绝不可混用。** 符号约定：`timing_error_ms < 0` = 提前；`> 0` = 滞后；`= 0` = 正好。
> 时间基准统一使用 **`performance.now()`**（单调时钟），不使用 `Date.now()`。

### 2.2 Piano Raw Event（V2 §17）

每个按键事件**必须**保存以下完整字段（Raw Event 比总分重要）：

| 字段 | 类型 | 单位 | 说明 |
| --- | --- | --- | --- |
| `event_index` | int | — | 事件序号 |
| `cue_onset_time_ms` | int | ms | 刺激出现时间 |
| `target_time_ms` | int | ms | 目标节拍时间 |
| `actual_time_ms` | int/`null` | ms | 实际按键时间（Miss 时为 `null`） |
| `response_latency_ms` | int/`null` | ms | 反应延迟 |
| `timing_error_ms` | int/`null` | ms | 节拍误差 |
| `key_code` | str | — | 键盘按键码 |
| `note` | str | — | 音符名（如 `C4`） |
| `hand` | `LEFT`/`RIGHT` | — | 任务映射手别 |
| `finger_hint` | `INDEX`/`MIDDLE`/`RING`/`LITTLE` | — | **任务映射**的手指提示 |
| `is_correct` | bool | — | 是否命中正确目标 |
| `is_missed` | bool | — | 是否漏击 |
| `key_down_time_ms` | int/`null` | ms | 按下时间 |
| `key_up_time_ms` | int/`null` | ms | 抬起时间 |
| `hold_duration_ms` | int/`null` | ms | `key_up − key_down` |

> ⚠️ **`finger_hint` 的语义限制（必须在页面与报告注明）**：第一版使用普通电脑键盘，
> 系统**只能知道"要求按哪个映射键"**，**无法确认患者实际使用了哪根生理手指**。
> 因此所有 `*_finger_*` 指标均为**任务映射指标**，不是医学意义上的手指识别。

#### 2.2.1 键位映射（**与阶段目标存在一处偏差，已记录，未静默处理**）

| | 内容 |
| --- | --- |
| 阶段目标原文 | "键位映射修正为左手 **C3-B3** / 右手 **C4-C6** 无重叠" |
| **实际实现** | 左手 **C3–B3**（12 键，下排 `Z S X D C V G B H N J M`）<br>右手 **C4–B4**（12 键，上排 `Q 2 W 3 E R 5 T 6 Y 7 U`） |
| 相同点 | **两侧无重叠**、每键**只对应一个音**，目标中"修正重叠"的意图**已达成** |
| 不同点 | 右手上界是 **B4** 而不是 C6 |
| 为什么不能做到 C6 | ① 该仓库 61 个 mp3 的**实测音高上限就是 B4**（MIDI 71），C5–C6 没有任何真实音源；<br>② 上排只有 12 个可用物理键，C4–C6 需要 **25 个**音，无法做到"一键一音且不重叠"；<br>③ 用 `playbackRate = 2.0` 把 C4–B4 升八度能凑出音高，但音色明显失真（"花栗鼠"音），<br>而本项目其余音源都是**实测真实采样**，混入合成音会破坏"音源真实"这一前提 |
| 结论 | 维持 **C3–B3 / C4–B4**。C3–B4 的 24 个音中 22 个有直接实测样本，**E3 / F3** 由相邻样本移调 1 个半音。 |
| 影响 | **不影响任何指标定义**（`hand` 与 `finger_hint` 都是任务映射，音高只影响听感与映射难度）。若后续必须覆盖 C5–C6，需要**另行提供高音区音源**，届时只需扩展 `frontend/src/piano/samples.ts` 的音符表与 `KEY_BINDINGS`。 |

> 实测依据：`data/demo/piano_samples_measured.json`（`note_index` 覆盖 MIDI 48–71，
> `coverage = {direct: 22, shifted: 2}`），由 `scripts/_piano_build_index.py` 用 ffmpeg + FFT 生成。

### 2.3 Piano Session 指标

#### 2.3.1 P0（第一版必须实现）

| 中文名称 | 英文 key | 计算公式 | 单位 | 异常处理 | 最小有效数据 | 来源 | 用于展示 | 长期趋势 | 难度调整 | 医学诊断 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 准确率 | `accuracy` | `correct_count / total_cues` | 无量纲 0–1 | `total_cues == 0` → `None` | ≥ 1 cue | `NEW` | ✅ | ✅ | ✅ | **NO** |
| 漏击率 | `miss_rate` | `missed_count / total_cues` | 无量纲 0–1 | `total_cues == 0` → `None` | ≥ 1 cue | `NEW` | ✅ | ✅ | ✅ | **NO** |
| 节拍误差均值 | `mean_timing_error_ms` | `mean(timing_error_ms)`（**带符号**，仅在 `is_missed=false` 的事件上） | ms | 有效事件数 = 0 → `None` | ≥ 1 有效事件 | `NEW` | ✅ | ✅ | ⚠️ 参考 | **NO** |
| 节拍误差中位数 | `median_timing_error_ms` | `median(timing_error_ms)` | ms | 同上 | ≥ 1 | `NEW` | ✅ | ✅ | ❌ | **NO** |
| 节拍误差变异 | `timing_error_cv` | `std(timing_error_ms) / mean(timing_error_ms)` | 无量纲 | 样本 < 2 或 `\|mean\| < 1e-9` → `None` | ≥ 2 | `NEW` | ✅ | ✅ | ❌ | **NO** |
| ⚠️ CV 语义警告 | — | `timing_error_ms` **均值可能接近 0**（提前与滞后互相抵消），导致 CV 爆炸 | — | **必须**在 `|mean| < EPS` 时返回 `None`，并在前端改展示 `timing_error_std_ms` | — | — | ✅ | ✅ | ❌ | **NO** |
| 反应延迟均值 | `mean_response_latency_ms` | `mean(response_latency_ms)` | ms | 有效事件 = 0 → `None` | ≥ 1 | `NEW` | ✅ | ✅ | ✅ | **NO** |
| 反应延迟变异 | `response_latency_cv` | `std(response_latency_ms) / mean(response_latency_ms)` | 无量纲 | 样本 < 2 或 `\|mean\| < 1e-9` → `None` | ≥ 2 | `NEW` | ✅ | ✅ | ✅（升级条件之一） | **NO** |
| 左手平均延迟 | `left_mean_latency` | `mean(response_latency_ms \| hand=LEFT)` | ms | 无左手事件 → `None` | ≥ 1 | `NEW` | ✅ | ✅ | ✅ | **NO** |
| 右手平均延迟 | `right_mean_latency` | `mean(response_latency_ms \| hand=RIGHT)` | ms | 无右手事件 → `None` | ≥ 1 | `NEW` | ✅ | ✅ | ✅ | **NO** |
| 左右延迟差 | `left_right_latency_difference` | `left_mean_latency − right_mean_latency` | ms | 任一侧缺失 → `None` | 两侧均 ≥ 1 | `NEW` | ✅ | ✅ | ✅ | **NO** |
| 左手准确率 | `left_accuracy` | `correct_left / total_left` | 无量纲 | `total_left == 0` → `None` | ≥ 1 | `NEW` | ✅ | ✅ | ✅ | **NO** |
| 右手准确率 | `right_accuracy` | `correct_right / total_right` | 无量纲 | `total_right == 0` → `None` | ≥ 1 | `NEW` | ✅ | ✅ | ✅ | **NO** |
| 弱指错误率 | `weak_finger_error_rate` | `errors(finger_hint ∈ {RING, LITTLE}) / total(finger_hint ∈ {RING, LITTLE})` | 无量纲 0–1 | 分母为 0 → `None` | ≥ 1 个弱指任务 | `NEW`（V2 §19 定义） | ✅（**必须附限制说明**） | ✅ | ✅ | **NO** |
| 会话完成率 | `session_completion_rate` | `completed_cues / planned_cues` | 无量纲 0–1 | `planned_cues == 0` → `None` | ≥ 1 | `NEW` | ✅ | ✅ | ❌ | **NO** |

> **`weak_finger_error_rate` 展示限制（强制）**：页面与报告必须标注
> "基于任务映射的弱指错误率，不代表真实生理手指表现"（V2 §19）。
> **Phase 5 已固化口径**：错误 = `is_correct == false`（含点错键与漏击）；
> 分母 = `finger_hint ∈ {RING, LITTLE}` 的目标数。
> 实现见 `frontend/src/piano/metrics.ts` 与 `backend/app/utils/piano_metrics.py`。

#### 2.3.1.1 `timing_error_cv` 的可用性限制（**Phase 5 实测发现，重要**）

**不能无条件报告 `timing_error_cv`。**

节拍误差是**带符号**的（提前为负、滞后为正）。对表现正常的患者，提前与滞后会**互相抵消**，
使**均值接近 0**，而标准差并不小，于是 `std / mean` 会得到一个巨大且无意义的比值。

**Phase 5 触发该缺陷时的实测数据**：

```
mean_timing_error_ms = 1.4 ms
timing_error_std_ms  ≈ 82 ms
→ 若直接相除，CV = 58.7   ← 无意义
```

> ⚠️ **来源说明（务必如实转述）**：这组数字来自 Phase 5 的**脚本自检**会话
> （页面以 `?selftest=1` 打开、由合成键盘事件驱动，库中标记为
> `input_source = SYNTHETIC_SELFTEST`），**不是真人 Calibration**。
> 正因为按键落点相对节拍点是随机的，提前与滞后大量互相抵消，才把
> `mean ≈ 0 而 std 不小` 这一形状暴露了出来——这是**数学形状**的证据，
> 与数据来源无关，因此该限制对真人数据同样成立。真人数据只是**尚未采集**。

**采用的规则**（前后端一致实现）：

```text
当 |mean| < 0.25 × std  →  timing_error_cv = None，并写入 timing_error_cv_note
                        →  改看 timing_error_std_ms（节拍误差标准差）
否则                    →  正常报告 CV
```

- `0.25` 是配置常量，记录在代码与本节，可随科研方案调整并递增版本。
- 同一限制**不适用于 `response_latency_cv`**：反应延迟恒为正，均值不会接近 0，CV 始终可解释。
- 回归测试：`backend/tests/test_piano_regressions.py`。

#### 2.3.2 P1（P0 稳定后实现）

| 英文 key | 计算公式 | 单位 | 状态 |
| --- | --- | --- | --- |
| `mean_absolute_timing_error_ms` | `mean(abs(timing_error_ms))` | ms | **Phase 5 已实现**（写成 DB 列 `timing_mae_ms`） |
| `early_press_rate` | `count(timing_error_ms < −THRESHOLD) / valid_count` | 无量纲 | **Phase 5 已实现**；`THRESHOLD = median(abs(timing_error_ms))`（**由数据导出，不引入外部临床常数**） |
| `late_press_rate` | `count(timing_error_ms > +THRESHOLD) / valid_count`；阈值同上 | 无量纲 | **Phase 5 已实现**，阈值同上 |
| `sequence_completion_rate` | 完整正确的音符组数 / 已开始的组数 | 无量纲 | **Phase 5 已实现** |
| `error_streak_max` | 最长连续非正确目标数 | 次 | **Phase 5 已实现** |
| `key_hold_duration_ms` | `mean(hold_duration_ms)` | ms | **Phase 5 已实现**（Raw Event 已含 `hold_duration_ms`） |
| `timing_error_std_ms` | `std(timing_error_ms)` | ms | **Phase 5 新增**：`timing_error_cv` 不可用时的替代量（见 §2.3.1.1） |
| `hand_switch_latency` | 相邻不同手别事件之间的实际时间差均值 | ms | `NEEDS_IMPLEMENTATION`，定义待后续固化 |

> **`median_response_latency_ms`** 与 **`median_timing_error_ms`** 在 V2 §18 列表中出现，
> 已与均值一同实现（DB 列已存在）。
>
> **`early_press_rate` / `late_press_rate` 的阈值口径说明**：V2 原文写 `EARLY_THRESHOLD` 需配置化但未给值。
> 本实现取「该次训练中 |节拍误差| 的中位数」作为阈值，即**相对该患者本次表现**判定过早/过晚，
> 而不是引入一个没有出处的绝对毫秒数。阈值随指标一起可由原始事件复算。

#### 2.3.3 P2（后续科研扩展，第一版**不做**）

MIDI velocity / 力度、复杂节奏同步指标、频域震颤指标、运动平滑度高级指标、多模态融合分数、ML 自动难度预测。

> **第一版禁止伪造力度（velocity）**：普通键盘无法获得真实击键力度（V2 §14.1、§26）。

#### 2.3.4 数据来源标记 `input_source`（**两份规格均未定义，本系统新增**）

**问题**：Phase 5 的自检用脚本合成键盘事件跑通了全流程并保存进库，但**记录里没有任何字段
说明它不是真人数据**。这类行会以 100% 准确率出现在训练历史里，与真实测量无法区分。

**处理**：`piano_sessions.input_source`（非空，索引，封闭集合）：

| 取值 | 含义 | 产生方式 | 允许用途 |
| --- | --- | --- | --- |
| `HUMAN_KEYBOARD` | 真人在浏览器里按键 | 页面默认值 | 展示 / 趋势 / 难度调整 / 科研 |
| `SYNTHETIC_SELFTEST` | 脚本合成按键 | 页面以 `?selftest=1` 打开 | **仅**流程验证 |
| `SEED_DEMO` | 随机生成的历史记录（**无任何原始事件**） | `scripts/seed_demo.py` | **仅**界面演示 |

强制规则：

1. 服务端不推断来源，由客户端在创建会话时声明，默认 `HUMAN_KEYBOARD`；非法值 422 拒绝。
2. 非 `HUMAN_KEYBOARD` 的 Calibration 生成的 Baseline，其 `snapshot.note` 必须写明
   「不是真人测量值……不得作为临床或科研基线使用」，并在 `quality_metadata.input_source` 留痕。
3. 页面在非真人来源时显示醒目提示（`PianoTrainingPage.vue`）。
4. **Phase 8 的趋势与报告只允许使用 `HUMAN_KEYBOARD`**；`SEED_DEMO` 无原始事件，永远无法复算。
5. 迁移 `b1c7f0a2d4e5` 对历史行做保守回填：**已完成但没有任何原始事件**的行 → `SEED_DEMO`
   （真实一轮不可能不存事件），其余一律保持 `HUMAN_KEYBOARD`，**不猜测**。

> 该字段不影响任何指标公式，**不计入算法版本号**；它是数据可信度元数据。
> 同类问题在 Pose（Phase 6）与功能测试（Phase 7）落地时同样需要标记，已记入待办。

### 2.4 钢琴 Calibration 与 Baseline

Calibration 时长建议 **30～60 秒**（V2 §20）。产出并保存：

| 英文 key | 定义 | 单位 |
| --- | --- | --- |
| `baseline_accuracy` | Calibration 期间 `accuracy` | 无量纲 |
| `baseline_response_latency` | Calibration 期间 `mean_response_latency_ms` | ms |
| `baseline_response_latency_cv` | Calibration 期间 `response_latency_cv` | 无量纲 |
| `baseline_timing_mae` | Calibration 期间 `mean_absolute_timing_error_ms` | ms |
| `baseline_left_accuracy` | 左手 `accuracy` | 无量纲 |
| `baseline_right_accuracy` | 右手 `accuracy` | 无量纲 |
| `baseline_left_latency` | 左手 `mean_response_latency_ms` | ms |
| `baseline_right_latency` | 右手 `mean_response_latency_ms` | ms |

### 2.5 自适应难度规则引擎（**规则以 V2 §23/§24 为准，Agent 不得自行发明治疗规则**）

**输入（仅这些）**：`Accuracy`、`Miss Rate`、`Response Latency`、`Response Latency CV`、
`Timing MAE`、`Left/Right Difference`、`Weak Finger Error Rate`。

**明确不作为输入**：微表情 tag 占比、PD 概率（V2 §5.3、§20 明文；用户任务书第十五条亦明确）。

| 决策 | 条件（V2 §23.1/23.2/23.3） | 可调整参数 |
| --- | --- | --- |
| **升级** | `Accuracy >= 90%` **AND** `Miss Rate <= 5%` **AND** `Response Latency CV <= 0.25` **AND** `Timing MAE <= 当前阈值` | `BPM +5`；或缩小 `judgement_window`；或 `sequence_length +1`；或增加左右交替；或适度提高弱侧任务比例 |
| **维持** | `70% <= Accuracy < 90%` 且无指标失控 | 保持当前难度 |
| **降级** | `Accuracy < 70%` **OR** `Miss Rate > 20%` **OR** `Response Latency` 明显高于个人 Baseline **OR** 连续错误过多 | `BPM −5`；扩大 `judgement_window`；`sequence_length −1`；降低 `note_density`；减少双手切换 |

**左右手自适应（V2 §24）**：若 `Left Latency > Right Latency` **且** `Left Accuracy <= Right Accuracy`
→ 下一轮适度增加左手任务比例；反之同理。
**每轮调整幅度上限 10%～15%**（必须配置化，禁止 `50% → 90%` 的突变）。

**约束**：
- **一次只改变少量参数**，避免无法归因（V2 §23.1）。
  **Phase 5 已把这条从约定变成硬约束**：`RULES.maxChangesPerRound = 2`，
  统计范围包含 `weak_side_ratio`。**v1.0.0 曾经违反过它**——一次降级同时改了
  `bpm −5`、`judgement_window +25`、`sequence_length −1`、`weak_side_ratio +0.15`
  共 4 个字段，下一轮的结果无法归因到其中任何一个。v1.1.0 起按优先级消耗预算：
  降级 = 先加宽判定窗 → 再降 BPM → 再缩短序列（到 2 个字段即停）；
  升级 = 只动一个难度杠杆（BPM → 判定窗 → 序列 → 手指复杂度，前一个到顶才动下一个），
  剩余的预算才允许左右手比例调整。无法真正改变数值的提案不占用预算。
- `Timing MAE <= 当前阈值` 中的"当前阈值" **`TBD`**，必须由 Calibration 的 `baseline_timing_mae` 派生，
  具体系数在 Phase 5 定稿并写入规则引擎配置版本号。
  **Phase 5 定稿**：`timingMaeBaselineFactor = 1.0`（即不劣于本人基线 MAE），
  同时记录 `timing_mae_threshold_ms` 与 `latency_threshold_ms`（= 基线延迟 × 1.3）到
  `applied_rules.computed`，使决策可复算。
- 难度参数配置结构（V2 §23）：

```json
{
  "bpm": 60,
  "judgement_window_ms": 300,
  "sequence_length": 4,
  "note_density": 1.0,
  "hand_mode": "SINGLE",
  "weak_side_ratio": 0.5,
  "finger_complexity": 1,
  "session_duration_sec": 60
}
```

- 规则引擎必须版本化：`difficulty_engine_version`。
  **记录的必须是真正做出该决策的引擎版本**：规则引擎跑在前端，服务端在建会话时只是
  按当时的部署预期写了一个值，若前端是旧版本就会出现"决策来自从未运行过的引擎"这种记录。
  因此 `complete` 时以请求里 `adaptation.engine_version` 为准覆盖并在不一致时记 warning
  （见 `piano_service.complete_session` 与 `test_piano_api.py`）。
- **这是训练个性化，不是临床诊断**（V2 §24 明文）。

#### 2.5.1 规则引擎回归测试（零依赖）

`frontend/tests/difficulty.test.ts`，15 项，用 Node 22 的 `--experimental-strip-types` 直接运行，
**不引入 vitest / jest 等新依赖**：

```bash
cd frontend && npm run test:rules
```

覆盖：每轮改动字段数上限、降级只动两个字段、升级只动一个难度杠杆、
被夹紧的字段不浪费预算、记录值与返回配置一致、左右手步长落在 10%–15%、
弱手推断需要延迟与准确率一致、比例不越界、**不读取微表情标签与 PD 概率**、
缺少 Calibration 时退化为纯行为规则而不猜测、八项基线值的来源、版本与阈值随决策记录、
引擎不修改传入配置。该目录已加入 `tsconfig.json` 的 references，因此 `npm run build`
会一并做类型检查。

### 2.6 长期难度进阶（配置驱动，第一版**不固定治疗处方**）

```json
{
  "program_duration_weeks": 4,
  "sessions_per_week": 3,
  "session_duration_min": 10,
  "review_week": [2, 4],
  "weekly_progression_enabled": true
}
```

依据：PPT 第 11 页整理的 TIMP（节奏音乐演奏疗法）参考资料提到"4–8 周疗程、每次 10–15 分钟、
第 4/8 周复评、进阶节奏每周 +5%、上限 180 bpm"。
**具体训练频率由医生 / 研究方案配置，系统不强行规定**（V2 §25）。

---

## 3. Pose / 简单动作

### 3.1 原则

**先保存可解释原始指标，再由规则引擎计算展示分。**
**禁止随机生成 `82 分` / `90 分` 之类的展示分。每一个 Score 必须有公式。**（V2 §28/§29，任务书第十六条）

### 3.2 五个动作（V2 §27）

| # | 动作 | 主要关节 | 关键指标 |
| --- | --- | --- | --- |
| 1 | 山式双臂上举 | 左右肩 / 肘 / 腕 / 躯干 | 肩关节上举角度、左右对称性、保持时间、完成度 |
| 2 | 双臂侧平举 | 左右肩外展 | 左右肩外展角、左右角度差、保持稳定性 |
| 3 | 左右侧屈伸展 | 躯干 | 躯干倾角、左右活动范围、动作速度、稳定性 |
| 4 | 坐姿躯干旋转 | 肩关键点 + 髋关键点 | 躯干旋转完成度、左右对称、保持时间 |
| 5 | 坐姿交替抬臂 | 左右肩 / 肘 | 动作次数、节奏、角度、左右差异 |

**第一版不加入**：单脚长时间站立、快速深蹲、复杂倒立、大幅度扭转（V1 §26）。

### 3.3 原始指标（**优先保存**，V2 §28 字段名即 DB/JSON key）

| 中文名称 | 英文 key | 单位 | 计算公式 | 来源 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 左肩最大角度 | `left_shoulder_max_angle_deg` | 度 | `max(θ_left_shoulder(t))`，θ 由 MediaPipe Pose 的肩-肘-腕（或躯干-肩）关键点计算 | `NEW` | `NEEDS_IMPLEMENTATION` |
| 右肩最大角度 | `right_shoulder_max_angle_deg` | 度 | `max(θ_right_shoulder(t))` | `NEW` | `NEEDS_IMPLEMENTATION` |
| 左右角度差 | `left_right_angle_difference_deg` | 度 | `abs(left_shoulder_max_angle_deg − right_shoulder_max_angle_deg)` | `NEW` | `NEEDS_IMPLEMENTATION` |
| 躯干角度 | `trunk_angle_deg` | 度 | 由左右肩中点与左右髋中点连线相对垂直轴的夹角 | `NEW` | `NEEDS_IMPLEMENTATION` |
| 保持时间 | `hold_time_sec` | 秒 | 角度进入目标区间（`target ± tolerance`）的累计/最长持续时间 | `NEW` | `NEEDS_IMPLEMENTATION` |
| 动作次数 | `repetition_count` | 次 | 角度越过"进入/退出"双阈值的完整周期计数（滞回计数） | `NEW` | `NEEDS_IMPLEMENTATION` |
| 动作间隔 | `repetition_interval_ms` | ms | 相邻两次动作峰值的时间差 | `NEW` | `NEEDS_IMPLEMENTATION` |
| 动作速度 | `movement_speed_deg_per_sec` | 度/秒 | `d(angle)/dt` 的均值或峰值 | `NEW` | `NEEDS_IMPLEMENTATION` |
| 角度标准差 | `angle_std_deg` | 度 | 保持阶段 `std(angle(t))` | `NEW` | `NEEDS_IMPLEMENTATION` |
| 有效姿态帧比例 | `valid_pose_frame_ratio` | 无量纲 | `detected_pose_frames / total_frames` | `NEW` | `NEEDS_IMPLEMENTATION` |

### 3.4 展示指标（**必须由 §3.3 原始指标经固定公式计算**）

| 中文名称 | 英文 key | 单位 | 公式 | 状态 |
| --- | --- | --- | --- | --- |
| 完成度 | `completion_score` | 0–100 | **`TBD`** | `NEEDS_IMPLEMENTATION` |
| 关节活动范围 | `range_of_motion` | 0–100 或 度 | 基于指定关节角度的 `max_angle − min_angle`，或相对目标角度的完成比例。**每个动作必须分别定义**（V2 §30.1） | `NEEDS_IMPLEMENTATION` |
| 对称性 | `symmetry_score` | 0–100 | 基于 `abs(left_angle − right_angle)` 再映射到 0–100（V2 §30.2）。**映射函数 `TBD`** | `NEEDS_IMPLEMENTATION` |
| 稳定性 | `stability_score` | 0–100 | 基于保持阶段的 `angle_std_deg` 与关键点位移波动（V2 §30.3）。**公式 `TBD`** | `NEEDS_IMPLEMENTATION` |
| 保持时间 | `hold_time_sec` | 秒 | 见 §3.3 | `NEEDS_IMPLEMENTATION` |
| 动作次数 | `repetition_count` | 次 | 见 §3.3 | `NEEDS_IMPLEMENTATION` |

> **`TBD` 的处理规则**：Phase 6 实现前，必须先在本文件补齐每个公式（含归一化区间、目标角度、
> 容差、边界钳位），并把公式写入 `exercise_definition`（含 `exercise_definition_version`）。
> **在公式固化前，任何 0–100 分数都不得入库、不得展示。** 原始指标可先行入库。

### 3.5 Pose 难度调整（V1 §27 方向，第一版为方向性说明）

主要调节：保持时间、动作次数、动作范围目标、动作节奏、左右交替复杂度。
示例阈值：`完成度 > 90%` **且** `稳定性 > 85%` → 下一轮保持时间 `+2 秒` 或次数 `+1`；
`完成度 < 65%` → 降低要求。**具体阈值 `TBD`，Phase 6 定稿并版本化。**

### 3.6 Pose 安全文案（固定，V2 §59 / V1 §26）

```
请在医生或工作人员指导下完成。
如出现疼痛、头晕或明显不适，请立即停止。
```

---

## 4. 功能测试（Functional Assessment）

### 4.1 Nine-Hole Peg Test（9-HPT）—— 第一版唯一必须实现的 UI

| 字段 | 内容 |
| --- | --- |
| 中文名称 | 九孔插棒测试 |
| 英文 key | `NINE_HOLE_PEG`（`functional_assessments.test_type`） |
| 输入 | 医生/工作人员手动录入 |
| 记录字段 | `value_primary`（完成时间，**秒**）、`hand`（`LEFT`/`RIGHT`）、`unit`（`s`）、`medication_state`、`performed_at`、`notes`、`created_by` |
| 单位 | **秒（s）** |
| 公式 | **无公式 —— 人工录入的原始观测值**，系统不计算、不推断 |
| 异常处理 | 必须为正数；缺失值不写入（不允许填 0 占位） |
| 最小有效数据要求 | 每次测试至少一只手；趋势图需 ≥ 2 个时间点 |
| 来源模块 | `NEW`（V2 §31.1） |
| 算法版本 | `N/A`（人工录入，无算法） |
| 用于展示 | ✅ |
| 用于长期趋势 | ✅ |
| 用于难度调整 | ❌（第一版） |
| 用于医学诊断 | **NO**（系统只记录，不解读） |
| 趋势口径 | 左手时间 / 右手时间分别成图，**不得合并为单一分数** |

### 4.2 Box and Block Test（BBT）

| 字段 | 内容 |
| --- | --- |
| 英文 key | `BOX_AND_BLOCK` |
| 记录 | `value_primary` = 60 秒内转移木块数（个），`hand`，`unit` = `blocks/60s` |
| 公式 | 人工录入，无公式 |
| 第一版 | **只保留数据结构与接口扩展能力**，UI 不做 |

### 4.3 手指协同运动测试

| 字段 | 内容 |
| --- | --- |
| 英文 key | `HAND_COORDINATION` |
| 记录 | 医生人工记录的 `0–4` 分或定性描述 |
| **强制规则** | **系统不自动生成该分数**（V2 §31.3） |
| 第一版 | 只保留结构 |

### 4.4 MDS-UPDRS

| 字段 | 内容 |
| --- | --- |
| 英文 key | `MDS_UPDRS` |
| 记录 | **必须由医生人工录入** |
| **强制规则** | **系统不得自动声称自己生成 MDS-UPDRS 评分**（V2 §31.4） |
| 第一版 | 只保留结构 |

### 4.5 PDQ-39

| 字段 | 内容 |
| --- | --- |
| 英文 key | `PDQ39` |
| 记录 | 患者自评问卷（8 维度分 + 总分 0–100） |
| 第一版 | 只保留结构，**不属于 MVP 核心** |

---

## 5. 微表情 / AI 模型输出指标

### 5.1 当前状态

**`MODEL_NOT_CONFIGURED`** —— 模型未提供，所有模型输出字段当前均为 `NEEDS_IMPLEMENTATION` / `NOT_AVAILABLE`。

### 5.2 字段定义（待真实模型提供后填实）

| 中文名称 | 英文 key | 单位 | 来源 | 当前状态 |
| --- | --- | --- | --- | --- |
| 模型名称 | `model_name` | — | `EXTERNAL_REPO`（由 Adapter 从模型配置读取） | `NEEDS_IMPLEMENTATION` |
| 模型版本 | `model_version` | — | 同上 | `NEEDS_IMPLEMENTATION` |
| 预测类别 | `predicted_class` | — | 真实模型有则存，无则 `null` | `NOT_AVAILABLE` |
| PD 概率 | `pd_probability` | 0–1 | 真实模型有则存，无则 `null` | `NOT_AVAILABLE` |
| 主导标签 | `dominant_tag` | — | 真实模型有则存 | `NOT_AVAILABLE` |
| 标签分布 | `tag_distribution` | 0–1 each | 真实模型有则**原样保存** | `NOT_AVAILABLE` |
| 原始输出 | `raw_output_json` | — | 模型原始返回，**原样保存不做裁剪** | `NEEDS_IMPLEMENTATION` |
| 推理耗时 | `inference_time_ms` | ms | 计时得到 | `NEEDS_IMPLEMENTATION` |
| 质量元数据 | `quality_json` | — | 视频时长/帧率/尺寸等 | `NEEDS_IMPLEMENTATION` |
| 特征 schema 版本 | `feature_schema_version` | — | 常量 | `NEEDS_IMPLEMENTATION` |

### 5.3 强制规则（V2 §5.3）

1. **实际模型没有的字段必须返回 `null` 或不返回。**
2. **不允许为了前端展示强行伪造标签或概率。**
3. **微表情 Tag 占比不得直接作为疾病严重程度**，**也不得直接用于调整钢琴训练难度**。
4. **二分类概率默认也不直接映射为治疗强度。**
5. 页面统一用"辅助识别概率 / 模型输出概率"，**不得**写"确诊概率 / 病情严重度"。
6. 若以后科研方案明确验证"模型概率可作为难度先验"，**只能作为受限修正项，并通过配置开关启用**。

> ⚠️ **已记录的规格冲突（详见 `docs/spec_conflicts.md`）**：
> `帕金森应用.pptx` 第 10 页提出"以患病概率调节基础难度（如 0.7 → 0.7 的基础难度配置）"，
> 而 V2 §5.3/§20/§22 与用户任务书第十五条**明确否定**该做法。
> **最终采用 V2：第一版难度只依赖个人 Calibration + 实际训练表现。**

---

## 6. 综合与结构化指标

| 英文 key | 定义 | 单位 | 状态 |
| --- | --- | --- | --- |
| `left_right_difference` | 见 §1.3.12 | 同源指标 | `NEW`（FT）/ `NEW`（Piano 已有更细分的 `left_right_latency_difference`） |
| `algorithm_version` | 产生该结果的算法版本标识 | 字符串 | 强制字段 |
| `feature_schema_version` | 特征 JSON schema 版本 | 字符串 | 强制字段 |
| `analysis_config_json` | 本次分析全部可调参数快照（阈值、滤波参数、归一化方式等） | JSON | 强制字段，保证可复现 |
| 帕金森总分 | —— | —— | **❌ 不存在，禁止创造**（V2 §6、V1 §16、V1 §39） |

---

## 7. 文档与真实实现的差异（**不得静默选择**）

> 依据：任务书第二条"需求文档中的指标定义不能凌驾于真实算法代码"。

| # | 差异 | 文档说法 | 真实代码 | 最终决定 |
| --- | --- | --- | --- | --- |
| **D1** | `cov_percycle_max_speed` 分子错误 | 未定义 | `feature_extraction.py:128`：`cov_per_cycle_speed_maxima = std_amp / mean_percycle_max_speed`（分子应为 `std_per_cycle_speed_maxima`） | **采用修正后公式**，标记 `EXTERNAL_REPO_BUGFIX`。**不修改原仓库**；差异已在此记录 |
| **D2** | 滤波 `fs` 硬编码 | 未规定 | `feature_extraction.py:34`：`fs = 30.0`，与视频真实 fps 解耦 | **采用真实 fps**；`filter_fs_used_hz` 写入 `quality_json`；差异已记录 |
| **D3** | `tapping_frequency` 不存在 | V2 §11.1 给了公式 | 仓库无该字段 | **新项目实现**，标记 `NEW_DERIVED`。**Phase 4 已固化**：两种口径 `(峰值数−1)/跨度秒` 与 `1/平均周期` 在真实视频与合成信号上**完全一致**（真实片段均为 2.595 Hz；合成正弦均为 3.000 Hz），两值均保存，`tapping_frequency` 为展示口径 |
| **D4** | 左右差异不存在 | V2 §13 要求 8 个成对指标 | 仓库无任何左右比较代码 | **新项目在结果层实现**，标记 `NEW`。Phase 4 已实现 4 个成对指标并存库 |
| **D5** | `interval_distribution` / `opening_speed` / `closing_speed` / `asymmetry_ratio`（P1） | V2 §7.1 列出 | 仓库**均无** | 除 `asymmetry_ratio`（Phase 4 已在结果层实现）外，其余标记 `NEEDS_IMPLEMENTATION`，第一版不实现 |
| **D6** | `severity_score` / `severity_label` | V2 §41 允许"有真实模型时写入" | 仓库**无预训练模型、无持久化、无推理链路** | **恒为 `NULL`**，标记 `NOT_AVAILABLE`。Phase 4 实测再次确认 |
| **D7** | `avg_landmark_confidence` | V2 §12 建议保存 | Tasks API 的 `visibility` / `presence` **属性存在但恒为 `None`**（327/327 帧实测） | **Phase 4 已定案**：改用真实可得的 `handedness[0].score`，并在 `quality_json` 注明含义。详见 §1.3.11 |
| **D8** | `avg_speed` 命名 | V2 §41 单一字段 | 仓库有 `avg_percycle_avg_speed` 与 `avg_percycle_max_speed` | `avg_speed := avg_percycle_avg_speed`（Phase 4 已按此落库）；`avg_percycle_max_speed` 与 `cov_percycle_max_speed` 存入 `raw_features_json` |
| **D9** | `cycle_duration_cv` vs `cycle_cv` | V2 §7.1 用 `cycle_duration_cv`；V2 §41 用 `cycle_cv` | 仓库用 `cov_cycle_duration` | DB 列 `cycle_cv`（依 V2 §41），Phase 4 已落库 |
| **D10** | 特征列数不一致 | — | 生产者 `feature_extraction.py:152` 定义 **6** 个元数据列（`ids, video_path, label, medication_state, visit, hand`），消费者 `optimization_training.py:56` 却用 `iloc[0, 3:]` 取 **3** 列后的特征 | **产品化时全部不复用该 CSV 契约**；新项目自定义 schema 并版本化 |
| **D11** | 手别约定 | 未规定 | MediaPipe `handedness` 按镜像约定输出，仓库未纠正 | Phase 4 **沿用仓库行为**（直接字符串比对），但在 `analysis_config.handedness_convention` 标记 `TBD` 并在结果中附带 `handedness_note`。**仍需用已知手别的真实录制验证**（现有 demo 视频只有一只手，无法同时验证左右两侧） |
| **D12** | `interruptions` 阈值 | V2 §11.7 要求"不能随意固定阈值" | 仓库已固定 `1.5 × median` | 采用仓库定义（已存在即优先），**已配置化**并写入 `analysis_config_json` |
| **D13** | **`mp.solutions` 已被移除** | 仓库代码依赖 `mp.solutions.hands.HandLandmark` | **mediapipe 1.0.1 完全删除了 `mp.solutions`**（`hasattr(mp,'solutions') == False`，`mediapipe.python.solutions` 与 `mediapipe.solutions` 均不可导入）→ **仓库的 `keypoint_extraction.py` 在本环境无法运行** | **不复用其代码**；把关键点索引作为常量固定在 `signal.py`（`WRIST=0, THUMB_TIP=4, INDEX_FINGER_MCP=5, INDEX_FINGER_TIP=8`），并用真实推理验证。**未修改原仓库** |
| **D14** | `cov_percycle_max_speed` 未被持久化为独立列 | V2 §41 只有 `speed_cv` | 仓库同时输出 `cov_percycle_avg_speed` 与 `cov_percycle_max_speed` | `speed_cv := cov_percycle_avg_speed`（含修正后公式）；`cov_percycle_max_speed` 存入 `raw_features_json`，不丢失 |

---

## 7.1 Phase 4 实测记录（真实数据）

对**外部仓库自带 demo 视频**（`finger_tapping_test.mp4`，914×894，30 fps，327 帧，右手）的一次完整分析：

| 项 | 实测值 |
| --- | --- |
| 检测到手的帧 | **327 / 327（100%）** |
| 有效周期数 | 25 |
| `tapping_frequency` | **2.5952 Hz** |
| `avg_cycle_duration` | 0.3853 s |
| `avg_amplitude` | 1.3299（掌宽归一化，无量纲） |
| `avg_speed` | 6.9866（1/秒） |
| `amplitude_cv` / `speed_cv` / `cycle_cv` | 0.0663 / 0.1043 / 0.1250 |
| `amplitude_slope` / `speed_slope` / `cycle_slope` | −0.0066 / +0.0086 / −0.0027 |
| `interruptions` | 0 |
| `avg_landmark_confidence` | 0.9531（手别置信度） |
| `severity_score` / `severity_label` | **None / None** |
| 单次分析耗时 | 约 6.4 s（CPU，327 帧，含模型加载） |
| 请求视频中不存在的那只手 | 返回 `HAND_NOT_DETECTED`，不返回任何指标 |

**独立算术核验**：26 个峰值 → 25 个间隔，跨度 289 帧 / 30 fps = 9.6333 s，
`25 / 9.6333 = 2.5952 Hz`；`1 / 0.385333 = 2.5952 Hz`。两种口径一致，
且落在手指敲击的生理合理区间（约 1–6 Hz）内。

**合成信号核验**（有无解析真值，见 `scripts/_phase4_validate.py`，34/34 通过）：
已知频率的正弦被准确还原；测得幅度与闭式解 `2A·cos(πf/fs)` 吻合
（3.0 Hz / 30 fps 时预测 0.5706，实测 0.5706）。

---

## 8. 算法版本登记表

| 版本标识 | 覆盖范围 | 状态 |
| --- | --- | --- |
| `ft-features-v1.0.0` | Finger Tapping 12 个运动特征（§1.3.2–§1.3.9） | ✅ **Phase 4 已实现** |
| `ft-qc-v1.0.0` | Finger Tapping 质量控制（§1.4，8 道门限） | ✅ **Phase 4 已实现** |
| `ft-compare-v1.0.0` | 左右手比较（§1.3.12） | ✅ **Phase 4 已实现** |
| `piano-metrics-v1.0.0` | 钢琴 Session 指标（§2.3） | ✅ **Phase 5 已实现** |
| `piano-difficulty-v1.1.0` | 钢琴自适应规则引擎（§2.5） | ✅ **Phase 5 已实现**（v1.1.0 起强制每轮改动上限 2 个字段） |
| `pose-metrics-v1.0.0` | Pose 原始指标（§3.3） | 待实现（Phase 6） |
| `pose-score-v0.0.0-TBD` | Pose 展示分（§3.4） | **公式未定，禁止启用** |
| `micro-expression-adapter-v0.1.0` | 微表情 Adapter 接口 | 待实现（模型未提供） |

> 每次修改公式**必须**递增版本号，并在本表登记变更。长期趋势必须能按版本回溯。
>
> `input_source`（§2.3.4）**不是算法版本**：它不参与任何指标计算，只是标明这一行是不是
> 真人测量值，因此不登记在上表中，也不随公式变更递增。

---

## 9. "医学诊断" 汇总声明

**本文档中所有指标、所有 Score、所有模型的"医学诊断"一栏均为 `NO`。**

系统不产出诊断结论、不产出治疗建议、不产出"病情改善 X%"之类表述。
所有输出定位为：辅助识别结果、运动表现、训练表现、运动状态变化、趋势变化。

> 本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。
