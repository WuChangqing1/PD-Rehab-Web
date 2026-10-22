# 文案清理与 MicroFlow-DA 权重安置

日期：2026-10-22。基线：`19fbf8a6cc30b2e78736a68d83fe09f3e2a8e809`。

## 修改范围

- 删除页面原指定词语，来源标签使用“参考”；历史备注仅在渲染时处理。原始记录、来源枚举及患者数据库不修改。
- 模型状态区分“尚无权重”与“权重已安置但资源未齐备”，不改变 READY 条件或现有算法。
- 两份用户提供的权重保存在 Git 之外。本地 `models/microflow_da/`，服务器 `/opt/pd-rehab/models/microflow-da/`。

## 权重识别与安置

| 用户文件 | 安置位置 | 验证结果 |
|---|---|---|
| recognition_best_weights.pth.tar | recognition.pth | 原文件为 TAR，精确读取其唯一普通文件 `recognition_best_weights.pth.tar/samm_024_best.pth`；以 `weights_only=True` 加载，322 个 tensor 严格匹配现有 FG-LGL |
| checkpoint_epoch_054.pth.tar | spotting/checkpoint_epoch_054.pth.tar | 包含 epoch/state_dict/optimizer/scheduler，state_dict 有 121 个 tensor，属于微表情区间定位分支，不接入上传视频识别接口 |

识别权重 SHA256：`202a150b982baa8a8fc5c3ab93fce6d1d592f254e66927e95a3f27ebf2abc89e`。

区间定位权重 SHA256：`3d3da90154ac498e39751afa78fdb260e342dc151467576f8e2d9f8347c6994b`。

没有使用 `weights_only=False` 或执行任意 pickle；也未把外层 TAR 当成 PyTorch checkpoint。原始用户文件保持不变。

## 模型尚不能激活的实测原因

- 使用真实识别权重严格加载成功，输出为有限的 1×3 logits；这只证明结构与数值检查通过。
- 在固定起始帧与 AU 区域时，改变峰值帧和光流，最大 logit 差值为 **0.0**。加载诊断返回 `TEMPORAL_BRANCH_DISCONNECTED`。
- 用户新目录源码及当前部署源码均复现这一问题，没有修改源网络、跳过诊断或伪造训练确认标记。
- 当前仍缺 68 点关键点资源及确认过的训练/预处理部署清单，生产依赖也未齐备。权重文件存在并不代表可用推理。
- 下一步需修正网络时序路径，并提供匹配的新权重、关键点资源与训练预处理契约，再进行完整视频推理验收。当前不生成预测概率或临床结论。

安装目录附 `checkpoint-installation.json` 作为安置回执；它不是运行时信任的 `deployment.json`，`activation_allowed=false`、`training_contract_verified=false`。

## 验证

- 前端测试：293 passed。
- 后端全量：481 passed，1 skipped；跳过项是默认 Web Python 环境缺少 torch 的模型结构测试。
- 实际权重另外在 `pd_marker` 环境以 PyTorch 2.14 CPU 安全加载并执行结构/时序诊断；不以跳过测试代替权重验证。
- 根路径及 `/pd-rehab/` 构建均通过。
- 浏览器实际检查随访日历、趋势及历史评估结果；1440/768/390 宽度均不再出现目标词语，无横向溢出。
- 独立源码复核无新增缺陷；发布脚本核对权重、配置、源码哈希，保留现有模型不可用状态。

## 证据

- [当前源码与权重核验](runtime-checkpoint-audit.json)
- [用户目录源码与权重核验](checkpoint-audit.json)
- [浏览器文字与宽度检查](browser-checks.json)
- [PC 趋势](trends-1440.png)
- [平板趋势](trends-768.png)
- [手机趋势](trends-390.png)
- [历史结果](assessment-result-pc.png)

本轮不迁移数据库，不补写训练数据，不修改或训练网络，不把权重上传至 GitHub。
