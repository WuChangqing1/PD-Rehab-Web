# Web × Flutter 统一后端维护与部署报告

日期：2026-11-03。原基线：06b1c19745309719b86d205de9276f50d702db65。功能提交：`a6284477653c7e3177d608a817d25d801ac614f6`。用户在本轮明确授权部署 ssh fengz，并要求最终合并原 D 盘项目与推送 GitHub；只操作 PD 项目。

## 代码与协议

实施目录为 D:/CodingData/Competition/PD/PD-Rehab-Web-integrated-20261103/PD-Rehab-Web-main。原项目 D:/CodingData/Competition/PD/PD-Rehab-Web 在实施阶段保持原样，验收后按文件清单合并；原有未提交文档、PPT、输出和私人资源保留。交付包没有 .git，没有给它另建不相关历史或强推。

协议原 JSON 保留。兼容扩展版本 integration-1.1 见 cross_client_openapi_integration-v1.1.json；原字段/路径不改名，新增授权与撤销接口、问答来源字段，强化幂等元数据和任务异步状态。具体实体权威源、方向、版本与离线边界见 INTEGRATION_ENTITY_AUTHORITY.md。

## 已完成

- 复用 Web JWT、患者 UUID；患者访问实行 ADMIN 全部 / DOCTOR 明确授权或原创建及评估/跟弹归属。显式撤销优先，旧 Web 读取和 WebSocket 同样受限，不可换路径绕过。授权查询限定请求会话，迁移和后台任务不受隐式过滤。患者编号全局唯一探测用 Core 存在性查询，不泄漏其他档案。
- 设备档案绑定所属操作人，禁止静默换患者、盗用其他账号设备或重新启用已撤销绑定；授权变更写脱敏审计。
- Flutter 原始记录 append-only；同来源 ID 的 payload/患者/Profile/schema/task/metric/时间戳冲突均拒绝，保留来源、哈希与算法版本，不混入 Web KPI。
- 面部任务改为数据库持久 PENDING + 单实例 dispatcher，原子领取，帧号持久化；消除外层/模型适配器重复加锁的死锁。全局最多8个上传/复核/排队/运行任务，最大50MB，复核24小时到期；每用户上传4次/分钟、候选4次/分钟、问答12次/分钟、同步120次/分钟。当前单进程限流，不声称分布式限流。
- 服务重启保留未领取 PENDING；中断 RUNNING/UPLOADING 明确失败，已提交真实结果可恢复关联。复核检查顺序及实际视频边界；复核 CAS 防重复。权限撤销不被重启恢复逻辑重新标为成功。后台正在运行的评估不被浏览器90秒租约误删。
- 不上传私人录像到生产；当前 CausalNet s12.pth、三分类、原预处理/权重未修改。候选仍需确认，不虚构实时或七类分析。
- 带版本固定的平台知识摘录和真实来源链接检索；可配置本地 Spark Chat Completions。当前问题与固定知识片段以外不读取/发送患者 DB、视频或训练记录。涉及诊断/用药等问题走限制回答；不让模型执行 SQL。不宣称已完成临床知识库验证。
- Vue 新问答页、随访的软件原始记录页签；来源版本保留，详情请求在患者切换后失效。原五项导航及训练启动倒计时保留。

## Windows 本地模型与服务器连接

用户提供模型位于 Windows http://127.0.0.1:18091/v1，实际模型名 Spark-X2.6-4B。服务器不能把自己的127.0.0.1当成Windows；建立仅监听 fengz 127.0.0.1:18091 的 SSH reverse forwarding。公网客户端仍访问 https://ccqspace.site/pd-rehab/api。

配置：EXPERT_LLM_BASE_URL=http://127.0.0.1:18091/v1，EXPERT_LLM_MODEL=Spark-X2.6-4B，EXPERT_LLM_API_KEY 为空，EXPERT_LLM_ALLOW_LOCAL_HTTP=true；只为显式允许的 loopback HTTP 放行，不降低客户端 HTTPS 要求。重建通道可在 Windows 运行 scripts/start-local-llm-tunnel.ps1。当前通道依赖 Windows 在线、Spark运行和SSH连接；没有安装系统自动启动任务，也没有改动本机模型/Harness/QQBot配置。

## 实际测试与证据

- npm ci 使用真实锁文件安装134个包；最终 npm run test 339 passed；根路径和 /pd-rehab/ 两种 build 通过。
- compileall 通过；集成交付目录完整 pytest 536 passed / 3 skipped；最终原 Git 仓库完整 pytest **540 passed / 1 skipped**（148.81秒），真实 python-jose/MediaPipe，未使用临时 JWT 替代。最终唯一跳过项为 Web 解释器没有 torch 的旧 MicroFlow 结构测试；真实 CausalNet 在独立 worker 另行实跑。Git 跟踪检查在原仓库通过。新增代理文档、授权及 WebSocket 目标回归42 passed；早期目标回归27 passed。没有声称尚未执行的 MySQL 兼容或真机检查通过。
- 使用未修改的 Flutter lib/integration/remote_api.dart，实际 Dart SDK 驱动 HTTPS 本地测试代理，完成登录→绑定→同步→幂等重试→不同指标版本409→Web快照→真实Spark→视频上传→候选确认→异步CausalNet SUCCESS。客户端 TLS 回调只信任本地8447自签测试网关，不进入产品源码。原手机视频仅在本机使用。
- 官方公开 MediaPipe portrait.jpg 制作明确的人工变形视频作为技术反例/流水线素材；得到22/47/70帧候选，真实 CausalNet任务成功；不是真实表情或准确率评估。
- fengz 隔离预发布 127.0.0.1:18087（限400MB、25% CPU）完成登录、绑定、同步、冲突、Web快照、经SSH真实Spark、模型不可用拒绝。为保护共享服务器资源，预发布不再并行加载第二份大型CausalNet；真实权重本地单独实跑，生产切换后复查。
- 生产数据库只读备份副本升级 i5d7e9f1a3b4→j6e8f0a2b4c6→k7f9a1b3c5d7，原15张业务表计数与逐表内容指纹一致，新增5表；integrity_check=ok，foreign_key_check=[]。从备份恢复到另一隔离DB并核对指纹通过。
- 浏览器验收受工具环境阻断：cua_repl 与备用 node_repl 初始化均报 failed to write kernel assets / 系统找不到指定的路径。本轮没有实际完成PC/手机交互截图，不使用历史截图冒充；此项仍待工具恢复后补验。
- Flutter SDK 现有Dart3.12 / Flutter3.44，客户端项目要求Dart>=3.13.5；未擅自升级SDK或降低约束，没有声称 flutter analyze/test/build apk 或Android真机验收通过。实际独立Dart API客户端联通已完成。

## 尚未实现的范围

持续自动增量双向可编辑同步、ETag/稳定change cursor、跨端冲突合并、设备后台同步、共享设备缓存撤权回收、Flutter APK/真机、MySQL迁移、完整医学语料/RAG效果评估、自动患者病历解读、多进程/多机推理调度均不在本次完成声明内。当前只读快照与手动可重试上传不是全面双向编辑。

## 部署与回滚记录

功能代码 `a6284477653c7e3177d608a817d25d801ac614f6` 已在2026-11-03部署。只迁移和重启PD后端、替换PD两套静态入口。全量362个静态文件核验通过；Windows外部另核验根入口与子路径各35个变更资源SHA-256、实际 /expert 等深链接、health与401鉴权。两条公开API文档入口 /api/docs 与 /pd-rehab/api/docs 的相对OpenAPI地址通过检查。

公网HTTPS端到端通过：新建临时技术QA工作人员→真实登录→新建QA患者→绑定→上报→幂等重试→元数据不同409→Web读取→患者快照→经SSH调用Windows Spark→公开人工变形视频上传→22/47/70帧候选与确认→异步CausalNet SUCCESS→已完成评估历史回读。随后仅删除本次确切QA行与媒体，未修改既有患者；患者编号分配器继续递增，不回收序号。原手机视频没有传到生产。

生产迁移至 `k7f9a1b3c5d7`，原15张表迁移中指纹保持一致，新增5张表。PD服务active，CausalNet版本causalnet-34b854298eca，其他原READY模型保持READY。共享Nginx配置SHA-256完全一致，未reload/restart Nginx；其他项目PID对比如下，均未变化：nginx1225140、exercises1649531、llm-api-platform3979478、smoking-monitor-api1800107、smoking-monitoring-system-api1838442、gong-e-wendai3121880。

生产回滚备份保留 `/opt/pd-rehab/backups/integration-20261103`，约1.1GB，目录0700，含数据库、模型、媒体和PD服务配置。磁盘仍约20GB可用。预发布使用独立SQLite和限额服务，不与生产共享数据库；验收后停止预发布。窗口模型转发仅127.0.0.1:18091监听，没有公网LLM端口。

原始日志和部署脚本留在本地忽略目录；公开证据摘要为 `cross-client-release-20261103.json`，不含账号密码、私人媒体或患者原文。浏览器截图与Flutter APK/真机限制仍按前文保留，API联通不冒充视觉/设备验收。

部署范围：/opt/pd-rehab/app/PD-Rehab-Web、PD专属模型连接配置、/opt/pd-rehab/data、/var/www/pd-rehab 两套静态入口和 pd-rehab-backend.service。共享nginx及其他项目配置不改，nginx不重启。旧hash资源保留给缓存客户端。

回滚顺序：只停止PD后端→保存故障现场→恢复本次备份DB与配置→将代码回到06b1c19→恢复两套index入口→启动PD后端→检查健康、模型和旧API。回滚数据库会丢弃发布后的新增写入，必须在维护窗口操作；优先对新增表功能回退，勿覆盖其他项目数据。

详细未提交原始测试日志、密钥、私有视频、数据库和部署包都在原项目 _deploy/integration-20261103 忽略目录，不纳入公开Git。


## 本次提交文件（相对仓库根目录）

- `backend/app/api/deps.py`
- `backend/app/api/live_emotion.py`
- `backend/app/api/router.py`
- `backend/app/core/config.py`
- `backend/app/db/models/__init__.py`
- `backend/app/main.py`
- `backend/app/services/assessment_lifecycle.py`
- `backend/app/services/patient_service.py`
- `backend/tests/test_followup.py`
- `backend/tests/test_guided_song.py`
- `backend/tests/test_live_emotion.py`
- `backend/tests/test_schema_bootstrap.py`
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/pages/FollowUpPage.vue`
- `frontend/src/router/index.ts`
- `backend/app/api/integration.py`
- `backend/app/db/models/integration.py`
- `backend/app/services/integration_access.py`
- `backend/app/services/integration_jobs.py`
- `backend/app/services/integration_knowledge.py`
- `backend/alembic/versions/j6e8f0a2b4c6_cross_client_integration.py`
- `backend/alembic/versions/k7f9a1b3c5d7_integration_hardening.py`
- `backend/tests/test_cross_client_integration.py`
- `backend/tests/test_integration_hardening.py`
- `frontend/src/components/ExternalRecordsPanel.vue`
- `frontend/src/pages/ExpertChatPage.vue`
- `docs/CROSS_CLIENT_INTEGRATION_HANDOFF.md`
- `docs/cross_client_openapi_integration.json`
- `docs/cross_client_openapi_integration-v1.1.json`
- `docs/INTEGRATION_ENTITY_AUTHORITY.md`
- `docs/WEB_INTEGRATION_MAINTENANCE_REPORT.md`
- `docs/superpowers/plans/2026-11-03-cross-client-release.md`
- `scripts/start-local-llm-tunnel.ps1`
- `docs/cross-client-release-20261103.json`（发布证据摘要）
