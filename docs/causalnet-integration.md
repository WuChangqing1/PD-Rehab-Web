# CausalNet 视频分析接入与运行说明

日期：2026-10-31。支持现有面部评估入口，不迁移数据库，不替换钢琴、手指或芭蕾算法。

## 已实现的流程

1. 评估中心选择面部表现分析，确认患者。
2. 使用摄像头录制或选择原始视频文件，系统读取真实帧率、帧数和时间戳。
3. 拖动预览滑块并设置起始、峰值、结束帧，也可直接填写帧号；必须满足 `1 <= onset < apex < offset <= 1800`。
4. 顺序解码关键帧，检测唯一人脸；对于缺失方向标签的手机文件，按眼睛和嘴部几何关系尝试四个直角方向，整组关键帧使用同一方向。
5. 人脸对齐、TV-L1 光流、四路特征，经真实 CausalNet 权重推理。
6. 保存模型版本、权重/源码哈希、帧号、原始帧率、预处理版本、质量信息和三类分数。页面刷新及评估历史均可回读。

新适配器在输入、检测、推理或数据库提交失败时回滚本次媒体与结果，清理本次上传文件。视频预览不创建评估或媒体记录。

## 权重与算法范围

- 当前工程候选：用户提供的 `s12.pth`，SHA256 为 `34b854298eca115b57aefd042f9350026359414561039ba9b0dc86970f8be973`。
- 原网络配置：`image_size=28, patch_size=7, dim=256, heads=3, block_repeats=(3,3,7), num_classes=3`，严格恢复权重内保存的掩码；不使用原 eval.py 中不匹配的 `(3,3,9)`。
- 原模型源码 SHA256：`351d8c0823b40b7550b2d3c9f129cf38b50c9a64f130ca3504436dc2f21f4472`。
- 使用 `weights_only=True`、`mmap=True` 和 `load_state_dict(strict=True, assign=True)`。为降低冷启动内存，只跳过将被完整权重替换的大张量随机填充；不修改网络计算、结构或权重。
- 输出顺序：`negative / positive / surprise`（负向 / 正向 / 惊讶）。`pd_probability` 始终为空。softmax 分数不等于校准后的置信度，不提供中性类或疾病诊断。
- 作者采用复合数据集 LOSO；文件名对应留出的受试者，不表示单一数据集专用模型。s12 是工程联调候选，不能通过本次小样本宣布为最优模型。

## 预处理依据及限制

作者明确了 TV-L1、光学应变、48 像素归一化后缩放至 28 像素，以及保存通道 `OS / V / U`。方向图基于归一化后的 U/V，未增加第三方复现代码中的 clipping 或改动 TV-L1 默认 lambda。

依据：[作者核心代码](https://github.com/tony19980810/CausalNet/issues/3#issuecomment-3635225903)、[通道与方向说明](https://github.com/tony19980810/CausalNet/issues/4#issuecomment-3732101176)、[无 clipping 的确认](https://github.com/tony19980810/CausalNet/issues/4#issuecomment-3752569011)。

完整训练裁脸代码未公开，因此采用显式版本化的 `mediapipe-eyes-canonical-v1` 对齐，结合随附训练脚本的固定区域拼接。`training_crop_equivalence_verified=false`、`training_contract_verified=false`、`clinical_eligible=false` 如实保留。输入输出运行通过不意味着复现论文准确率，普通 30 FPS 与训练用高速数据的泛化仍需独立验证。没有把视频重新标为高速帧率，也没有插帧伪造采集信息。

## 安装与配置

Web 继续使用原 Python 环境。CausalNet 在独立持久 CPU 子进程加载，避免 Web 环境的 NumPy/OpenCV/MediaPipe 版本冲突；不需要 GPU。

本地实际运行环境为 Python 3.11 / PyTorch 2.14 CPU；服务器独立环境为 Python 3.10 / PyTorch 2.6 CPU，均使用同一源码与权重。服务器冷启动及前向检查通过，峰值 RSS 约 1.28 GiB；生产服务需为原 Web 进程与视频解码另外预留内存，本次服务上限为 2304 MiB。

Linux 示例：

```bash
python3 -m venv /opt/pd-rehab/causalnet-venv
/opt/pd-rehab/causalnet-venv/bin/python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
/opt/pd-rehab/causalnet-venv/bin/python -m pip install -r backend/requirements-causalnet.txt
```

模型资源放在源码仓库之外：

```text
/opt/pd-rehab/models/causalnet/
  Models.py         原始用户网络源码
  LICENSE           原模型许可证
  s12.pth           用户训练权重，不入 Git
  causalnet.json    资源清单与哈希
  runtime.env       部署配置，不入 Git
```

`causalnet.json` 示例，路径按实际安装调整：

```json
{
  "schema_version": 1,
  "labels": ["negative", "positive", "surprise"],
  "checkpoint": "s12.pth",
  "checkpoint_sha256": "34b854298eca115b57aefd042f9350026359414561039ba9b0dc86970f8be973",
  "source_model": "Models.py",
  "source_sha256": "351d8c0823b40b7550b2d3c9f129cf38b50c9a64f130ca3504436dc2f21f4472",
  "python_executable": "/opt/pd-rehab/causalnet-venv/bin/python",
  "threads": 4,
  "training_contract_verified": false
}
```

Web 环境配置：

```dotenv
MICRO_EXPRESSION_ENTRY=causalnet
MICRO_EXPRESSION_MODEL_DIR=/opt/pd-rehab/models/causalnet
MICRO_EXPRESSION_CHECKPOINT=
MICRO_EXPRESSION_DEVICE=cpu
```

重启后通过 `/api/system/models` 检查适配器为 `causalnet`、状态为 `READY`。缺失资源、哈希不匹配、严格加载失败或进程启动失败都不能标为就绪。请求按进程锁串行执行，校验请求 ID，启动/推理有超时与失败状态处理。服务退出会关闭模型子进程。

旧 `microflow_da` 适配保留；切换回旧配置不会修复其已有时序问题。不要将旧 MicroFlow 的 `deployment.json` 和 CausalNet 的 `causalnet.json` 混用。

## 验证记录

- 用户手机原视频：约 30.006 FPS、3840×2160、262 帧；无插帧。31 / 121 / 211 帧通过方向校正、检测、真实推理、API 保存和回读验证。该录像与其缩略图、原始输出仅存本地忽略目录，不提交 Git 或上传生产服务器。
- 实际网页另行检查文件选择、元数据读取、无效帧拦截、分析和结果回读。修复了上传按钮不触发文件选择器、FormData 被 JSON 默认头转换，以及已存分类分数未映射到 API 的问题。
- 后端全量回归：495 passed、1 skipped；跳过项是 Web 测试解释器无 torch 的旧模型结构测试。真实 CausalNet 在独立 worker 另外执行，不能用跳过测试代替推理。
- 前端测试：307 passed。根路径和 `/pd-rehab/` 两种构建及 PC/手机检查以最终发布记录为准。
- 此次证明的是已实现链路可运行，不是临床效用、论文复现准确率或实时连续微表情检测验收。

源码新增文件主要为 `causalnet.py`、`causalnet_worker.py`、`causalnet_preprocess.py`；接口沿用现有面部分析结果类型，新增可选结束帧和无持久化的视频信息接口。无需数据库迁移。
