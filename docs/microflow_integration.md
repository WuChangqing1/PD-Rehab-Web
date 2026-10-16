# MicroFlow-DA 视频模型接入

## 当前交付边界

用户提供的 MicroFlow-DA.zip 只有源码，没有训练权重。接入的是 `recognition/FGLGL` 起始帧—峰值帧三分类识别分支，标签顺序固定为 `negative / positive / surprise`（负向 / 正向 / 惊讶）。不是 PD 疾病分类器，也不能转换成七类情绪概率。连续摄像头分析与自动情绪提速保持关闭。

源码中的 spotting 分支处理预提取的 AU/光流特征，与上传视频识别分支输入不同；本次没有把它当成现成视频推理接口使用。

源码另有已复现问题：FG-LGL 在 ViT-DA 后才拼接 CLS token，分类时只对这个尚未汇入输入的 CLS 做 pooling；另一融合分支仅使用起始帧 AU 区域。固定起始帧及 AU 区域后，改变峰值帧与光流，分类 logits 完全相同。适配器增加加载诊断，失败返回 `TEMPORAL_BRANCH_DISCONNECTED`，不能标记 READY。未静默修改用户模型结构。

因此此次上线的是接入代码、输入/资源校验和明确的未就绪界面。真实预测、准确率、连续视频模型和生产模型激活尚未完成，需要修正源码并取得匹配的训练权重后再验证。

## 实现

- 专用 MicroFlowRuntime：隔离源码模块命名空间，读取三分类模型配置，严格加载匹配 state_dict；只有资源哈希、训练/标签/预处理契约和前向诊断全部通过才 READY。
- 复用提供源码的对齐、裁脸、9 个 AU 区域、归一化与光学应变函数。没有调用训练数据集的 DummyLandmarkProvider、空图替代或检测失败回退。
- 明确选择 TV-L1 或 Farneback，不能因依赖不同而静默改变训练时的光流算法。图像保持提供源码实际使用的 BGR 顺序。
- 上传接口增加可选 `onset_frame / apex_frame`（从 1 开始、成对、起始早于峰值、最多第 1800 帧）。按原始视频顺序解码，避免容器关键帧跳转误差；检查帧率、实际长度、分辨率、单人脸及真实 68 点关键点。
- 模型推理在线程池执行，沿用全局推理锁。三类结果使用现有标签分布、原始输出与数据库字段；`pd_probability` 留空，结果不声明临床有效性。
- 缺少 MicroFlow 资源时，在存储上传文件和媒体行前返回 MODEL_NOT_CONFIGURED，不写结果。帧配对非法返回 422。
- 前端增加关键帧输入及三类中文名称，切换视频后清空原有选帧。无权重或模型验证不通过时禁用分析，摄像头不启动。

## 资源与配置

第三方模型源码不提交到 GitHub，部署在独立模型目录，运行包仅包含必要代码和提供的配置；不包含训练数据 CSV、测试视频、随机权重或研究数据。

```text
/opt/pd-rehab/models/microflow-da/
  source/recognition/{__init__,fglgl,flow_branch,magnet,vit_da,au_local_global,dataset}.py
  source/common/{__init__,optical_flow,au_regions}.py
  model-config.yaml
  recognition.pth                         # 尚未提供
  shape_predictor_68_face_landmarks.dat    # 尚未提供
  deployment.json                         # 尚未提供，须由训练交付确认
```

配置：`MICRO_EXPRESSION_ENTRY=microflow_da`，`MICRO_EXPRESSION_MODEL_DIR=/opt/pd-rehab/models/microflow-da`。默认 CPU，可显式配置设备；生产本次未安装尚无权重可用的 PyTorch/dlib，也不会借用其他模型的权重。

未来 `deployment.json` 至少包含：`schema_version=1`、真实确认的 `training_verified=true`、上述标签顺序、`channel_order=BGR`、明确 `flow_method`，以及 `checkpoint_sha256 / landmark_sha256 / config_sha256 / source_sha256`。其中 source_sha256 按 `microflow.py` 的 SOURCE_FILES 顺序生成，训练配置必须匹配交付权重；不能简单将验证标记改为 true 来代替训练验证。

权重加载使用 `weights_only=True`、`load_state_dict(strict=True)` 和 eval 模式。相关依据：[PyTorch 模型加载文档](https://docs.pytorch.org/tutorials/beginner/basics/saveloadrun_tutorial.html)、[序列化文档](https://docs.pytorch.org/docs/stable/notes/serialization)。

## 检查证据

- 原始 zip SHA256：`d1b823e4f4a83d7af7b734e0876b36ed1c3405842a3fa84fb83d5ae3e2543ec4`。
- 运行源码 SHA256：`797b82bb842e505ad464fdb8bba12ac4aa9261a13e46d859cc3891a4866bafa6`；当前已知时序问题只绑定此源码版本，修正版本需重新加载诊断。
- 默认结构约 25,134,636 参数，CPU 前向得到有限的 1×3 logits；替换峰值帧及光流后的最大差异 0。此为未训练结构检查，不是准确率或真实模型推理验收。
- 测试包含严格权重重载、三类输出与 PD 字段隔离、非法分布、真实视频帧号解码、清晰资源状态、缺失权重时无上传/结果持久化、选帧 API 与数据库往返，以及禁用实时摄像头。
- 本地浏览器 PC / 平板 / 手机：显示未就绪和源码问题、分析按钮禁用、摄像头调用 0、临床写入 0、页面异常 0。属于桌面视口检查，未声称真机验收。

证据见 [源码诊断](../artifacts/microflow/source-diagnostic.json) 与 [浏览器验证](../artifacts/microflow/browser-verification.json)。最终测试、部署版本和线上验证见同目录后续交付记录。
