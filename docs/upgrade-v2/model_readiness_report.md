# P0 · 微表情模型就绪度报告

审计时间：2026-10-12
结论：**BLOCKED —— 老师未提供源码与权重，本平台不具备真实推理条件。**

---

## 1. 磁盘证据

```
$ find . -include *.pth,*.pt,*.onnx,*.ckpt,*.safetensors   （排除 node_modules）
（无输出）

$ ls backend/app/ml/micro_expression/
adapter.py          8497 bytes
__init__.py            0 bytes
adapter.cpython-311.pyc
__init__.cpython-311.pyc
```

**整个仓库不存在任何模型权重文件。** `micro_expression` 目录只有适配器本身。

## 2. 适配器的真实状态

`backend/app/ml/micro_expression/adapter.py` 开头的模块文档明确写着：

```
The teacher's model has not been provided, so this adapter currently reports
MODEL_NOT_CONFIGURED and refuses to analyse.
```

构造函数：

```python
self._status = ModelStatus(
    name=MODEL_NAME,
    version=MODEL_VERSION,          # "unknown"
    state=ModelState.MODEL_NOT_CONFIGURED,
    detail="MICRO_EXPRESSION_MODEL_DIR 未配置",
)
self._model: Any = None
```

`_infer()` 不产生任何数值输出，只抛 `model_not_configured()`。

## 3. PPT 里有什么、没有什么

| PPT 内容 | 是否等于可运行资源 |
| --- | --- |
| FG-LGL（Flow-Guided Local-Global Representation）微表情识别，光流引导双注意力 / ViT-DA、9 个 AU 语义区、两级 Transformer | ❌ 论文方法描述，不是 checkpoint |
| AUG-GCN（AU-Guided Graph Convolutional Network）微表情检测，滑窗累积光流、鼻尖运动补偿、AU 先验图卷积、BATEM onset/apex/offset | ❌ 同上 |
| UF1 / UAR / F1 实验数值 | ❌ **原论文结果**，不是本平台在 PD 数据上的准确率 |
| Vue3 + Python/PyTorch + MySQL 分层与「登录→采集→对齐→检测→识别→展示」流程 | ✅ 可作为架构参考（本平台已是等价分层） |

**PPT 中的模型介绍不等于已经具备模型权重。** 这是本次审计的核心判断。

## 4. 缺什么（逐项清单）

要真正接入，以下每一项都必须由提供方给出，缺一不可：

| # | 待提供资源 | 用途 |
| --- | --- | --- |
| 1 | FG-LGL 源码目录与可执行推理入口 | 识别阶段 |
| 2 | AUG-GCN 源码目录与可执行推理入口 | 检测阶段 |
| 3 | 两个模型的权重文件 + **SHA256** | 可追溯 |
| 4 | 标签映射表（类别索引 → 名称） | 结果语义 |
| 5 | 训练/预处理超参（归一化、采样、窗口长度） | 复现输入 |
| 6 | 依赖版本（Python / PyTorch / CUDA / OpenCV / MMCV…） | 环境 |
| 7 | 输入规范（分辨率、FPS、最短最长时长、正侧脸与光照要求） | 采集引导 |
| 8 | 两模型关系：**串联（先 spotting 再 recognition）还是已有一体化工程** | 接口形态 |
| 9 | 真实错误模型（找不到脸 / 光流失败 / 无有效 apex） | 失败路径 |
| 10 | 输出语义：detection segments？每段类别？情绪标签分布？PD 二分类概率？ | 决定哪些字段可以为非 null |
| 11 | 授权范围：是否允许部署到公网服务器 | 合规 |
| 12 | 至少 3 段可重复测试且有权的视频（有微表情 / 无微表情 / 低质量） | 验收 |

## 5. 本平台已具备的部分（不需要模型也能用）

已经写好、**只等资源到位即可接线**的部分：

- `MicroExpressionAnalyzer` 单例与 `status()` 状态上报；
- `MODEL_NOT_CONFIGURED` / `FAILED` / `NO_EVENT_DETECTED` 三种语义区分
  （`docs/07` §数据质量要求）；
- `MicroExpressionResult` 数据契约，除真实模型产出的字段外**一律保持 `None`**；
- `MICRO_EXPRESSION_MODEL_DIR` 配置项与缺失时的降级路径；
- 面部分析页在不可用时的产品化表现：按钮禁用 + 「当前暂不可用」，
  **不绘制任何虚拟彩色饼图、不显示随机百分比**。

## 6. 本次没有做、也不会做的事

- ❌ 不训练替代模型冒充老师的模型；
- ❌ 不用 MediaPipe Face Landmarker 的 blendshape 输出伪称 FG-LGL 结果；
- ❌ 不依据 PPT 的实验数值展示为平台性能；
- ❌ 不在 UI 上把面部标签换算成疾病严重度、诊断概率或康复成效百分比；
- ❌ 不把模型权重放进 Public GitHub。

## 7. 需要你提供的

> 老师模型的**源码、权重、requirements / 依赖锁、标签表、推理示例、输入规范与授权范围**。
>
> 拿到后即可按 `docs/06` 的推荐结构实施 E2E：
> `preprocess → spotting_adapter → recognition_adapter → aggregate → persistence`，
> 并按「模型验收最低标准」逐条验证（load 成功、hash 可追溯、同视频重复推理一致、
> 逐段可定位、空/失败路径可用）。

在此之前，P4 的状态是 **BLOCKED**，不会以任何形式宣称已完成。
