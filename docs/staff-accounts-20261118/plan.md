# 医护注册与姓名同步 Implementation Plan

> For agentic workers: Use subagent-driven-development or executing-plans task by task.

**Goal:** 完成批准的医护注册、角色权限和App姓名同步。
**Architecture:** 后端统一身份和授权边界；Web只消费接口；App在既有会话和同步中更新姓名，ID保持稳定。
**Tech Stack:** Vue3/TypeScript, FastAPI/SQLAlchemy/Alembic, Flutter/Dart, SQLite。
**Spec:** design.md

## Global Constraints
保留已有医护/患者/训练/模型/同步/短信数据及功能，仅PD服务可重启。不伪造真实短信、设备或模型验收。共享单机构，不扩建多租户。

## Review Focus
- 患者或未审核申请直接调用医护API必须拒绝；护士不能计划写入/删除完整结果/批量导出。
- 审核并发、最后管理员、旧JWT与停用角色变化必须按数据库实时角色判断。
- 姓名并发409、退出登录期间晚响应、跨账号隔离、离线失败和双向同步不覆盖新名字。
- 部分完成/取消/历史训练继续兼容；护士可以清理本人的未完成任务。
- 大字体双语界面不溢出，敏感资料不进日志和Git。

## Tasks
- [ ] Backend: tests for profile+roles+registration -> fail -> implement additive migration/endpoints/authorization -> full pytest+isolated migration.
- [ ] Web: tests for public registration/admin lifecycle/nurse action visibility -> fail -> implement routes/pages/types/permissions/i18n -> npm test/build two bases.
- [ ] Flutter: tests for edit/display/remote rename/account switch/errors -> fail -> implement API/session/UI/sync -> analyze/full test/APK.
- [ ] Independent review, fix findings, PC/tablet/phone/en/zh/large-font browser acceptance.
- [ ] Migration rehearsal on protected server DB copy, baseline hashes and other service PIDs, GitHub main and target-only deploy with rollback.
- [ ] Public read checks, publish versioned QA APK, documentation+SHAs+known unverified device tests.
