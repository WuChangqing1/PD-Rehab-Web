# 双仓库分支交付与合并计划

| 项目 | 基线 | 独立分支 | PR |
|---|---|---|---|
| Web | 4794609 | codex/web-docs-ai-pdf-export | https://github.com/WuChangqing1/PD-Rehab-Web/pull/2 |
| App | 6f4c8cc（feature/android-apk-updates） | codex/app-integration-followup | https://github.com/CapriChris/PianoForParkinson/pull/1 |

两仓库分别提交和Push；不用force，不自动合并，不推main。App PR以队友更新分支为base，确保仅审计文档属于本轮，不替队友把整个更新器宣称为Codex改造。Web PR以main为base，供维护者审查新增的授权阅读/导出/报告能力。原始本地未提交工作和旧试验分支保留。

## 合并协调

1. 维护者审查Web权限、持久化、备份和日期/PDF证据，确认与队友近期提交的交叉文件。
2. App仅有审计文档，先由队友确认完整APK更新分支的归属和合并顺序；不改其源代码或签名。
3. 合并前重新fetch并检查差异，不能盲目合入他人新提交。Web仍保留既有登录、同步、训练和模型接口。
4. 由维护者决定是否及何时合并main；合并SHA重新测试后才进入正式发布。
5. 依[部署与回滚](production_deployment_and_rollback.md)准备依赖、字体、备份和目标服务切换；当前没有执行。

逐文件修改见 [清单](modification_file_inventory.md)。当前实现SHA和最终分支Tip可能因交接文档提交不同，测试记录对应产品实现，最终GitHub分支SHA以Push后ls-remote复核为准。没有把“分支已推送”称作“线上已发布”。


## 2026-11-20 推送前远程变化

再次 fetch 确认 App 队友分支由6f4c8cc前进到98a122fb48013b048aee079fcd1d5a51cb06a3cd，新增5cbf055、98a122f。差异仅README、练习页移除姓名17行和v0.1.73验证说明；账号、同步、接口、APK清单协议及签名配置没有变化。本轮未自动合并这两个提交，App开发分支仍以核查时的6f4c8cc为基础，仅交付审计文档；维护者在PR中协调。已运行的911项回归对应6f4c8cc，不冒称复测了新98a122f全部源码。

GitHub现在有v0.1.73候选APK：isPrerelease=true，102920214字节，公布SHA256为457eff09c8852865d4a719d2039d41b4369c0c1679128c4cdf227a34ca7a9d5c。队友记录显示其真机覆盖安装仍待验证。此处只是公开清单元数据核查，没有将该预发布包当作批准的稳定正式包，也没有镜像到生产。正式下载入口仍保持未启用。
