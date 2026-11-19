# 业务数据持久化与导出审计（2026-11-19）

## 审计边界和结论

基于本轮隔离克隆的 SQLAlchemy 模型、业务服务、文件写入/删除实现及合成数据库测试完成静态审计；没有查询生产患者数据库、复制真实患者文件、运行数据库迁移或变更生产服务。本轮不改变数据库结构和训练算法。

新增患者级 JSON/CSV、管理员账号元数据 JSON/CSV，以及附件备份元数据清单。修复原有通用 JobManager 仅在进程内保存状态的问题：状态快照以 UUID JSON 文件原子写入 `settings.output_path/jobs`，重启后可查询已结束任务；中断的 PENDING/RUNNING 明确标为 FAILED/TASK_INTERRUPTED，不伪称继续运行。微表情跨端任务原先已通过数据库和 dispatcher 恢复，本轮保留该机制。

“已持久化”指代码存在保存路径，不代表已对生产历史逐条核验。完整备份与业务导出不同；本轮未执行生产备份和恢复演练。

## 对象、存储、关联和导出矩阵

以下数据库位置均为既有 `DATABASE_URL`；SQLite 相对路径由 `app/db/session.py` 按项目根目录解析，也支持配置的其他 SQLAlchemy 数据库。P 表示患者导出，A 表示管理员导出；两者均为 JSON/CSV。未特别说明的记录不新增自动清理策略，沿用现有业务删除操作；患者逻辑停用后不允许使用患者导出。

| 数据对象 | 表/文件 | 主键 | 患者关联 | 保存、保留及导出 |
|---|---|---|---|---|
| 患者档案 | patients | id | 本身 | DB；is_deleted 逻辑停用；P |
| 患者编号永久占位 | patient_number_allocations | id | 编号分配，不存患者 FK | DB；删除患者不复用编号；A |
| 普通/工作人员账号 | staff_users | id | 普通账号经 mobile_accounts | DB；is_active；A 白名单，不导出密码哈希 |
| 待审批工作人员申请 | staff_applications | id | 无 | DB；审批状态和 reviewed_by；A，排除申请密码哈希 |
| 普通账号绑定与同步授权 | mobile_accounts | user_id | patient_id | DB；P/A；排除 recovery_hash |
| 外部身份绑定 | mobile_identities | id | user_id→mobile_accounts | DB；A；身份标识属于授权管理员隐私数据 |
| 登录会话元数据 | mobile_sessions | id | user_id→mobile_accounts | DB；expires_at/revoked；A；两个 refresh_hash 均排除 |
| 登录挑战 | mobile_login_challenges | id | 可经 user_id/session_id | DB；短期 expires_at、attempts/status；认证流程数据，不进入普通导出，完整受控数据库备份保留 |
| 认证限流 | mobile_auth_limits | key | 无 | DB；resets_at；防滥用运行数据，不进入业务导出 |
| 患者授权及撤销 | patient_access_grants | id | patient_id | DB；active；P/A，撤销立即阻止患者导出 |
| 设备/本地档案映射 | device_patient_links | id | patient_id | DB；active/bound_by；P/A |
| 原生训练计划 | training_plans | id | patient_id | DB；config_json 和状态；P；按计划起止日期与所选区间重叠纳入 |
| App 计划、历史版本和 daily_progress | external_practice_records，record_type=training_plan_snapshot | id + 来源唯一约束 | patient_id | 不可变 payload_json；来源修订号/设备/档案/plan_id 可核对；P，保留各快照而非只导出最新版本 |
| App 钢琴、曲目、舞蹈等原始同步记录 | external_practice_records | id | patient_id | DB；来源类型、schema/task/metric_version、来源哈希、captured_at_ms；P 全部授权记录 |
| 原生钢琴训练 | piano_sessions | id | patient_id | DB；任务条件、来源、版本和结果；P，不重新计算分数 |
| 钢琴原始事件 | piano_events | id | session_id→piano_sessions | DB；P 随父训练记录完整保留，不受分页截断 |
| 原生曲目跟弹 | guided_song_sessions | id | patient_id + owner_id | config/events/result 和音频 BLOB 都在 DB；P 仅当前调用者拥有的记录，ADMIN 可读所有；音频不内联导出 |
| 舞蹈训练 | pose_sessions | id | patient_id | DB；raw_metrics/quality、任务与算法版本；P，历史 exercise_type 不改写 |
| 评估会话 | assessment_sessions | id | patient_id | DB；类型、用药、起止和状态；P |
| 微表情结构化结果 | micro_expression_results | id | assessment_session_id | DB；P，原模型输出/版本；不推断临床诊断 |
| 指敲结构化结果 | finger_tapping_results | id | assessment_session_id | DB；P；内部 analysis_config_json 不导出，特征与质量保留 |
| 指敲原始时序附件 | output_path/{session_id}/*.npz | DB raw_timeseries_path | 评估父记录 | 文件；受控根目录内存在才列入附件清单，大小与实际 SHA256；不含原始文件字节/服务器路径 |
| 人工功能评估 | functional_assessments | id | patient_id，可带 assessment_session_id | DB；performed_at；P，保留原始单位及手别 |
| 历史基线快照 | baselines | id | patient_id | DB；新基线停用旧基线而非删除；P 包括历史 snapshot_json |
| 原生媒体及已有报告文件索引 | media_files | id | patient_id/assessment_session_id | DB 索引；upload_path 内的文件与 SHA256/大小；P 元数据和可用附件清单 |
| App 面部分析任务 | mobile_face_jobs | id | patient_id | DB；索引、候选、结果关联、错误码；P；不导出 stored_path/error_message；原机制清除原片 |
| 训练关联录像 | face_recordings + upload_path/training-face/{id} | id | patient_id/external_record_id | DB manifest/segments/result；P 排除 DELETED，已删媒体 manifest 不回填；原片过期/取消/删除后不列附件 |
| AI 问答 | expert_chat_turns | id | 可空 patient_id，operator_id | DB question/answer/model；P 仅当前工作人员拥有的关联患者对话，ADMIN 可读；无患者关联的问答经 A 导出 |
| 审计记录 | audit_logs | id | entity_type/entity_id | DB；A 仅身份、动作、对象、时间；不导出任意 detail_json，避免历史请求敏感字段泄露 |
| 通用评估任务状态 | output_path/jobs/{UUID}.json | job_id | patient_id | 本轮修复为受控文件持久化；P 包含患者范围任务状态、结果和错误码；原有 jobs API 保持对象授权 |
| 随访页面汇总及趋势 | 读取上述 DB 记录 | 原记录 ID | patient_id | 动态计算视图；无独立的临床随访笔记写入模型/页面，不伪造“随访表” |
| PDF 报告 | 本轮 report.pdf 服务返回内存字节 | 患者 ID + 日期 + 内容哈希 | patient_id | 不落公开静态目录；生成元数据写既有 audit_logs；PDF 实际内容见独立说明 |
| 实时摄像头预览、关键帧预览 | WebSocket/TemporaryDirectory | 当前请求 | 授权评估上下文 | 按现有隐私设计临时处理；不是已提交评估结果，不额外永久留存原片 |

## 日期、权限和可核对性

- 患者导出：`GET /api/business-exports/patients/{patient_id}?format=json`，CSV 使用 `format=csv`；可选 `start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`，两端日期包含在内，时区明确为 Asia/Shanghai（UTC+8）。不传日期导出该授权患者全部历史；没有“缺省导出全部患者”的入口。
- 仅活跃 ADMIN/DOCTOR/NURSE；复用 `integration_access.patient`，遵守现有共同机构范围及显式撤销授权。普通患者不能调用工作人员导出 API。除 ADMIN 外，曲目和 AI 对话进一步限制调用者所有权。
- 管理数据：`GET /api/business-exports/administration?format=json|csv`，仅活跃 ADMIN；包含账号安全元数据、审批、绑定、授权、编号、无患者关联 AI 对话及审计摘要，不含密码、恢复码、令牌或认证凭证。
- App 记录优先按 captured_at_ms；原生会话按 started_at（无值时回退 completed_at/created_at）；功能评估按 performed_at；子结果/原始事件跟随选中的父会话。身份/绑定/授权是当前状态，不伪装成历史切片；计划按有效日期重叠判断，未定义起止日期的计划保留。
- 字段使用显式静态白名单，新数据库列不会自动进入导出。嵌套 JSON 递归移除密码、token、密钥、cookie、认证头及内部路径等字段；嵌套 JSON 字符串同样处理；无法解析的结构化字符串置空。业务自由文本（例如问答原文）是授权内容，管理员仍应按隐私制度保存导出文件。
- 外部 payload_sha256、manifest_sha256 是原始入站内容的来源校验值，经过安全字段过滤后的对象不能用该哈希直接验证。导出新增 `integrity.sha256`，算法为除 integrity 本身之外整个对象的 UTF-8、ensure_ascii=False、sort_keys=True、separators=(',', ':')、allow_nan=False JSON SHA256；counts 为各类记录条数。
- HTTP `X-Content-SHA256` 是实际下载字节的 SHA256；JSON 与 CSV 各自有哈希，不能混用。CSV 使用 UTF-8 BOM 长表（category,record_id,field,value），完整保留异构记录与 JSON 嵌套内容；前置单引号避免电子表格公式执行。
- 每次成功生成调用既有 audit_service.record，保存操作者、范围、类型、条数和字节哈希，不把患者原文复制到审计详情。既有审计为 best-effort，数据库审计写入失败会记录服务器警告，当前导出接口不宣称强制审计事务。
- 响应为 private,no-store，不在公共目录创建可猜测下载文件。患者及管理员 JSON/CSV 目前在服务进程内生成，不静默截断；极大历史会消耗内存，发布前须根据真实规模评估，不能把单患者测试当作容量证明。

## 附件及独立完整备份清单

患者导出的 attachments 是**备份附件元数据清单**，不是附件下载或备份完成凭证。每项包含逻辑类型/ID/backup_reference、实际大小及 SHA256，已有 DB 哈希时另给 metadata_sha256_matches；缺失、越界路径、已删除及已过期训练原片均不恢复、不复制。临时上传分块不作为有效已完成患者附件导出。

需要正式备份时，应由具有服务器备份权限的运维人员按发布回滚文档执行并另行核验：

1. 使用当前数据库引擎的在线一致性备份工具（SQLite 使用 backup API/`.backup`，不能在写入中只复制主文件遗漏 WAL；其他数据库使用对应一致性工具）。完整数据库可能包含密码哈希和令牌哈希，必须与普通业务导出分开、限制访问并加密保存。
2. 从数据库索引定位受控 upload_path、output_path 内仍获授权且未到删除期限的附件，按 manifest 的逻辑 ID 对照 DB，复制后重算 SHA256；不依赖公开导出暴露服务器路径。guided_song_sessions.audio 为数据库 BLOB，随数据库备份；metadata 只说明音频信息。
3. 备份 output_path/jobs 的有效 UUID 状态快照；其内容可含分析结果与服务器错误详情，属于受控业务文件，不能作为静态资源发布。
4. 模型权重、已审核文档与部署配置独立备份；密钥和签名私钥采用现有秘密管理机制，不加入业务 JSON/CSV、附件 manifest 或 Git。
5. 在隔离恢复环境验证数据库完整性、附件存在性/哈希及授权；记录时间、版本、数量、验证结果和备份加密信息。本轮未执行生产完整备份和恢复。

## 保留和已确认边界

- 录像沿用已有策略：终态最长为创建后 7 天与更新时间后 24 小时的较早者；未完成上传 24 小时，其他活动录像最长 7 天。导出即使遇到尚未执行清理的残留文件也不会将过期原片列入附件。普通 mobile_face_jobs 待复核/待处理超过 24 小时不列原片；现有 dispatcher 继续负责实际删除。
- 原生 TrainingPlan 无独立版本表，未发现修改原生计划的持久化编辑接口；本轮不创建新 schema。App 不可变 training_plan_snapshot 保存已同步的历史计划与 daily_progress；未同步的本地历史不可能由服务器导出，不能声称已覆盖所有设备本地数据。
- 随访页面是已有训练/评估记录的聚合，不存在本轮应补写但已有 UI 丢弃的独立随访笔记。PDF 生成以审计元数据追踪，不增设报告历史表。
- JobManager 为当前单 worker 架构以 200 个状态为保留目标上限（超限优先删除最旧结束任务快照；活动任务不强删，因此活动数大时可暂时超过上限）；因此它是运行状态历史，不是永久全部任务档案。临床结构化结果仍在业务表内。多 worker 同时写同目录未作为受支持架构验证。
- 通用任务快照故障采用失败可见策略：写盘失败不会把内存状态伪称已持久化，原文件由原子替换保留；异常需运维修复磁盘后重试。

## 实际验证

先新增失败测试确认缺失模块/持久化接口，再实现。使用 `D:/App/Business/Coding/Python/Miniconda/envs/pd/python.exe`，合成内存 SQLite 数据和临时目录，不接触生产患者数据。

- 新增业务导出 9 项：患者范围、显式撤销、角色、调用者对话/曲目范围、深层凭证字段过滤、原始事件/结果/计划保留、UTC+8 年界单日边界、附件真实哈希/缺失/越界/已删/已过期、CSV 公式、HTTP 参数/认证及审计；新增任务持久化 7 项：恢复终态/中断、撤销访问、外来/坏文件、保留上限、真实 AnalysisOutcome dataclass 合约、原子替换失败和并发写入。
- 相关回归批次：test_business_exports.py、test_job_persistence.py、test_cross_client_integration.py、test_integration_hardening.py、test_followup.py、test_active_training.py、test_staff_review_regressions.py，共 52 项，51 通过、1 失败。失败为原有 AI 用例 `test_ai_without_provider_fails_transparently`，预期无供应商返回 503，实际 200；该问题交给 AI 模块核实，本模块没有删除/绕过该用例。结果对应并行开发中的代码快照，最终集成结果以 integration_test_report.md 为准。
- 当前生产导出、真实患者全量规模、实际备份恢复及正式 PDF 页面验收不属于上述合成测试证据。

## 修改文件

- backend/app/services/business_export.py
- backend/app/api/business_exports.py
- backend/app/jobs/manager.py
- backend/tests/test_business_exports.py
- backend/tests/test_job_persistence.py
- docs/data_persistence_export_audit.md

路由注册由本轮集成负责人在既有主路由完成；JSON/CSV 入口由“随访与报告”页面复用患者及日期选择。
