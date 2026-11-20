# 修改文件及原因

下表按最终基线diff逐文件列出，未列入数据库、APK、模型、密钥或测试私有产物。App相对6f4c8cc只有`docs/web-apk-integration-audit-20261119.md`，用于记录实际机制与真实HTTPS回归，不含业务修改。

| 文件 | 必要原因与影响 | 验证 |
|---|---|---|
| `backend/app/api/android_distribution.py` | 兼容队友唯一清单；正式包验证和独立下载状态，不改登录协议 | APK校验/缓存回归；入口浏览器检查 |
| `backend/app/api/business_exports.py` | 受控JSON/CSV、字段保留/凭证清理、日期和附件核对 | 导出与权限回归 |
| `backend/app/api/deps.py` | 注册本轮路由；患者仅可读获授权文档 | 角色/患者/原接口回归 |
| `backend/app/api/documents.py` | 批准文档阅读、权限、资源与安全渲染；不开放任意文件 | 文档权限/渲染测试及真实Chrome |
| `backend/app/api/integration.py` | 复用现有AI接口，按角色检索当前文档并链接本站 | 知识库测试、8类问题与真实点击 |
| `backend/app/api/patient_reports.py` | 随访日期/PDF、投影、版本隔离、取消旧请求和手机日历 | 报告/前端/实际下载与分页 |
| `backend/app/api/router.py` | 注册本轮路由；患者仅可读获授权文档 | 角色/患者/原接口回归 |
| `backend/app/core/config.py` | 新增批准安装包目录及证书信任配置，默认关闭；不修改原秘密配置 | APK单元测试及原有回归 |
| `backend/app/jobs/manager.py` | 修复仅内存任务状态丢失；原子快照和重启失败状态 | 任务持久化7项回归 |
| `backend/app/services/android_distribution.py` | 兼容队友唯一清单；正式包验证和独立下载状态，不改登录协议 | APK校验/缓存回归；入口浏览器检查 |
| `backend/app/services/business_export.py` | 受控JSON/CSV、字段保留/凭证清理、日期和附件核对 | 导出与权限回归 |
| `backend/app/services/document_library.py` | 批准文档阅读、权限、资源与安全渲染；不开放任意文件 | 文档权限/渲染测试及真实Chrome |
| `backend/app/services/integration_knowledge.py` | 复用现有AI接口，按角色检索当前文档并链接本站 | 知识库测试、8类问题与真实点击 |
| `backend/app/services/patient_report.py` | 随访日期/PDF、投影、版本隔离、取消旧请求和手机日历 | 报告/前端/实际下载与分页 |
| `backend/requirements.txt` | 只加入本轮PDF/Markdown必要固定依赖及测试入口 | 完整构建与锁文件安装 |
| `backend/tests/test_android_distribution.py` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `backend/tests/test_backup_business_data.py` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `backend/tests/test_baseline_read_paths.py` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `backend/tests/test_business_exports.py` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `backend/tests/test_document_library.py` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `backend/tests/test_document_publication.py` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `backend/tests/test_job_persistence.py` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `backend/tests/test_mobile_accounts.py` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `backend/tests/test_patient_reports.py` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `docs/ai_knowledge_base_coverage.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/android_apk_distribution.md` | 兼容队友唯一清单；正式包验证和独立下载状态，不改登录协议 | APK校验/缓存回归；入口浏览器检查 |
| `docs/apk_download_integration.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/branch_delivery_and_merge_plan.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/cross_client_regression_report.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/current_codebase_audit.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/data_persistence_export_audit.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/integration_test_report.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/knowledge_base_implementation.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/latest_remote_code_audit.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/accounts.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/app-android-updates.md` | 兼容队友唯一清单；正式包验证和独立下载状态，不改登录协议 | APK校验/缓存回归；入口浏览器检查 |
| `docs/library/assistant.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/dance.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/developer-readme.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/face.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/faq.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/inventory.json` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/manifest.json` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/metrics.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/piano.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/plans.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/reports.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/library/sync.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/pdf_report_export_guide.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/pdf_report_export_test.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/platform-release-20261119/evidence/app-checks.json` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/platform-release-20261119/evidence/browser-checks.json` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/platform-release-20261119/evidence/hashes.json` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/platform-release-20261119/evidence/web-test-results.json` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/platform-release-20261119/latest-request.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/platform-release-20261119/request.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/platform-release-20261119/review_resolution.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/production_deployment_and_rollback.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/shorebird_update_guide.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/superpowers/plans/2026-11-19-platform-release.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `docs/web_document_hosting.md` | 本轮批准说明、清单、验收或交接；不作为患者数据 | 文档/清单审查及来源哈希 |
| `frontend/package-lock.json` | 只加入本轮PDF/Markdown必要固定依赖及测试入口 | 完整构建与锁文件安装 |
| `frontend/package.json` | 只加入本轮PDF/Markdown必要固定依赖及测试入口 | 完整构建与锁文件安装 |
| `frontend/src/documents/render.ts` | 批准文档阅读、权限、资源与安全渲染；不开放任意文件 | 文档权限/渲染测试及真实Chrome |
| `frontend/src/documents/sourceLinks.ts` | 批准文档阅读、权限、资源与安全渲染；不开放任意文件 | 文档权限/渲染测试及真实Chrome |
| `frontend/src/followup/reportDates.ts` | 随访日期/PDF、投影、版本隔离、取消旧请求和手机日历 | 报告/前端/实际下载与分页 |
| `frontend/src/i18n/en-reports.json` | 仅补齐本轮新增控件的英文 | 翻译与构建测试 |
| `frontend/src/i18n/index.ts` | 仅补齐本轮新增控件的英文 | 翻译与构建测试 |
| `frontend/src/pages/DocumentPage.vue` | 批准文档阅读、权限、资源与安全渲染；不开放任意文件 | 文档权限/渲染测试及真实Chrome |
| `frontend/src/pages/ExpertChatPage.vue` | 复用现有AI接口，按角色检索当前文档并链接本站 | 知识库测试、8类问题与真实点击 |
| `frontend/src/pages/FollowUpPage.vue` | 随访日期/PDF、投影、版本隔离、取消旧请求和手机日历 | 报告/前端/实际下载与分页 |
| `frontend/src/pages/LoginPage.vue` | 兼容队友唯一清单；正式包验证和独立下载状态，不改登录协议 | APK校验/缓存回归；入口浏览器检查 |
| `frontend/src/router/index.ts` | 注册本轮路由；患者仅可读获授权文档 | 角色/患者/原接口回归 |
| `frontend/tests/document_render.test.ts` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `frontend/tests/followup_controller.test.ts` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `frontend/tests/report_export.test.ts` | 为本轮功能和边界提供回归；保留原测试的业务断言 | pytest / npm test |
| `scripts/backup_business_data.py` | 标准库备份、清单校验与只写新目录的恢复 | WAL和27模型表实际恢复测试 |
| `scripts/prepare_android_release.py` | 兼容队友唯一清单；正式包验证和独立下载状态，不改登录协议 | APK校验/缓存回归；入口浏览器检查 |
| `scripts/publish_document_inventory.py` | 可重复发布清单/哈希，保留人工编辑与撤销 | 发布不覆盖回归 |
