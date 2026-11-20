# 双端回归与真实验收结果

核查时间：2026-11-19 至 2026-11-20。实现版本（文档提交前）：Web `58f80c0674d5fdb51dbce4ab2d3a812a94ee1fd2`，App `87df481315ec568169594df3b85532627c586ad1`。不将 Mock、模型 READY 或页面打开当作真实患者训练闭环。

| 检查 | 实际结果 | 范围 |
|---|---|---|
| 全部后端 pytest | 704通过，2跳过，0失败，0错误（共706） | 合成/隔离数据；JUnit可核对 |
| 全部 Vue/规则测试 | 397通过，0失败 | 原测试保留，含文档、日期、切换患者及取消导出 |
| 根路径与子路径生产构建 | 均退出0 | Vue类型检查与Vite构建，/ 与 /pd-rehab/ |
| Flutter analyze | No issues found | 队友基线业务代码未改变 |
| Flutter全部测试 | 911通过，2个默认opt-in跳过，0失败 | 未删旧测试 |
| 真实本地HTTPS同步 | 1通过 | 实际Flutter FFI库与Web，去重/计划进度/增量/解绑 |
| 真实本地HTTPS账号 | 1通过 | 注册登录/账号隔离/恢复/退出撤销/恢复码轮换 |
| 浏览器 | 6种语言/宽度组合；另6种报告日历组合通过 | Chrome，1440/820/390，中英文 |
| 文档/引用 | 15文档200、14鉴权图片、8类问题、真实引用点击通过 | 本机真实API，无生产LLM调用 |
| PDF | 实际浏览器下载通过；中文字体嵌入 | 合成空/大数据/趋势分页与A4视觉检查 |
| 迁移与恢复 | 隔离升级/回退一版/再升级通过；27表恢复一致 | 无新增迁移，无生产操作 |

Flutter 默认跳过的是 live_sync_smoke_test.dart 与 live_account_integration_test.dart：默认不提供本地HTTPS环境。两项后来各自用原有 run_local_sync_smoke.ps1 独立实际运行且通过，故不能把默认跳过当作失败，也不虚报全套默认跳过为0。

后端可选跳过项：
- `tests.test_microflow_integration::test_supplied_fglgl_source_forward_and_strict_weight_reload`：external MicroFlow-DA source not supplied; pass --microflow-source=PATH
- `tests.test_microflow_integration::test_supplied_transforms_are_used_without_dummy_landmarks`：external MicroFlow-DA source not supplied; pass --microflow-source=PATH

## 修复与边界

修复均通过失败复现再回归：持久化任务恢复；NULL评估关联误排除附件；NaN/Infinity改为空而非零；训练target/comparison key不被凭证清理误删；文档实时撤销及当前正文；恶意/畸形链接；需登录图片；导出中切换患者；单边日期歧义；手机646px日历截断；PDF不扫描大视频；PDF递归排除App嵌套原始事件且原JSON/CSV保持完整；APK昂贵重复校验缓存。

早期并行基线运行收集到了尚未实现的新导出用例，不能当作纯原基线结果。中间另有旧测试的模拟函数未接收新role参数、静态基线扫描误判导出字段声明、以及Windows默认临时目录ACL错误，均已准确区分并修复/使用独立basetemp。当前最终结果以上表为准，没有删除原测试制造通过。

现有 Starlette/httpx 弃用、既有OpenAPI重复operation ID及极端浮点测试溢出警告保留，未做无关依赖升级。无新增未解决失败。完整性证据：[测试结果](platform-release-20261119/evidence/web-test-results.json)、[App日志哈希及尾部](platform-release-20261119/evidence/app-checks.json)、[浏览器](platform-release-20261119/evidence/browser-checks.json)、[产物哈希](platform-release-20261119/evidence/hashes.json)。原始日志/截图保留本机 `D:/CodingData/Competition/PD/PD-Rehab-Web/_deploy/platform-release-20261119-qa`；不提交测试数据库、凭证或真实患者媒体。

## 尚未完成的外部验收

未连接Android真机，未完成本轮真实安装/覆盖升级/录像原生流程；正式APK尚无可信批准产物。未把生产模型READY写成新一轮真实患者推理成功。未上线新功能，生产GLM知识库答案质量需合并后受控验收。服务器中文字体未检测到，需要安装项目专属许可字体和reportlab后才能启用PDF；不能直接把本地字体可用当作服务器就绪。
