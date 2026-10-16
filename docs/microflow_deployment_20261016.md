# MicroFlow-DA 接入层发布记录

应用代码提交 `8cedabcefb169cdf0ee570988b10ed20bd6a5bf5` 已推送 GitHub main 并部署。后续审计提交只增加本记录和验证证据，不改变运行代码。

入口：[面部表现分析](https://ccqspace.site/pd-rehab/assessment/micro-expression)。当前状态明确为 MicroFlow-DA 已接入、等待训练权重，`MODEL_NOT_CONFIGURED / is_ready=false`；没有启用真实模型预测或实时摄像头分析。

## 验证结果

- `npm run test`：247 通过，0 失败。
- `npm run build` 与 `/pd-rehab/` base 构建：通过。
- 完整后端 pytest：445 通过，0 失败；最终改动的相关测试集另有 88 项通过。
- 本次新增 27 项后端测试及 1 项前端测试，覆盖缺失资源、三类输出语义、非法关键帧、上传前置拒绝、API 与数据库往返、原始视频帧号解码、权重严格重载、时序分支诊断和禁用摄像头。
- 全量测试初次遇到项目外上传测试夹具和系统临时目录权限错误；使用仓库内新的 `--basetemp` 并允许既有存储夹具执行后，最终全量通过。保留既有 Starlette httpx 弃用与极值 NumPy 运算两项警告，没有隐藏测试失败。
- 实际提供源码的默认结构前向、测试专用 state_dict 严格重载已验证。测试生成的临时权重不属于训练权重，未部署、未提交，也没有用于临床预测。
- 检查确认源码存在 `TEMPORAL_BRANCH_DISCONNECTED`：替换峰值帧与光流后 logits 差异 0。生产未修改这份算法来冒充已验证模型。详细原因和资源要求见 [接入说明](microflow_integration.md)。

## 发布

服务器使用 ssh fengz，代码以 bundle fast-forward 同步到 `/opt/pd-rehab/app/PD-Rehab-Web`。必要私有模型源码与提供的配置放在 `/opt/pd-rehab/models/microflow-da`，目录 750、文件 640，归后端服务用户 ubuntu 所有；没有上传训练数据或权重到 GitHub。

服务原有 `/opt/pd-rehab/.env` 保留。追加独立 EnvironmentFile `/opt/pd-rehab/models/microflow-da/runtime.env`，由 systemd drop-in 引用，避免既有环境文件覆盖模型选择。重启后健康检查通过；未安装生产 PyTorch/dlib、未改 Nginx、未迁移或清空数据库。

296 个静态文件 SHA256 校验全部通过，两个线上入口与各自构建完全一致。SQLite `quick_check=ok`，Alembic 版本仍为 `h4c6d8e0f2a3`。

## 公网验收

两个入口返回正确 MicroFlow 资源状态和源码 hash，标签严格为 negative / positive / surprise，模拟模式关闭。PC / 平板 / 手机实际 Chrome 页面无异常、无横向溢出。验收禁止非 GET API 请求；截图隐藏患者列表，未留存真实患者信息或写入生产训练数据。

钢琴目录、曲目跟弹、芭蕾入口均 200，七键字母保留，钢琴音源 Range 206，受保护接口仍 401，已认证历史接口 200。WSS 正常到达鉴权层，无效凭证返回预期 4403。

验证后删除 `/opt/pd-rehab/backups/microflow-20261016` 和 `/tmp/pd-microflow-20261016`，释放 78,575,118 字节；保留运行所需模型源码及配置。两个服务仍 active，公网健康接口正常。

证据：[测试汇总](../artifacts/microflow-production/test-summary.json)、[模型及页面验证](../artifacts/microflow-production/verification.json)、[钢琴回归](../artifacts/microflow-production/piano-regression/verification.json)、[资源校验](../artifacts/microflow-production/release-assets.json)、[清理记录](../artifacts/microflow-production/cleanup.json)。

截图：[PC](../artifacts/microflow-production/pc-pending.png)、[平板](../artifacts/microflow-production/tablet-pending.png)、[手机](../artifacts/microflow-production/mobile-pending.png)。

## 未完成事项

需修正并重新验证时序分支，再提供匹配的训练权重、真实 68 点人脸资源及训练/预处理交付信息。取得这些资源之前，无法完成真实模型推理、准确率或生产预测启用验收。此三分类识别器也不能直接用作七分类连续情绪模型。
