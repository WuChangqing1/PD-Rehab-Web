# 最新远程代码与接管基线

核查与开发：2026-11-19 至 2026-11-20。本文依据实际 Git、源码和隔离验证，不使用旧 ZIP 覆盖代码。

| 项目 | Web | App |
|---|---|---|
| 远程 | https://github.com/WuChangqing1/PD-Rehab-Web.git | https://github.com/CapriChris/PianoForParkinson.git |
| 远程默认分支 | main | main |
| 选定基线 | main：4794609ad37dcc77d4421af2d7f7a3a39650b7c6 | feature/android-apk-updates：6f4c8ccdd16603f7cfe20c3ba9582ed49f33dba2 |
| 本轮分支 | codex/web-docs-ai-pdf-export | codex/app-integration-followup |
| 独立工作区 | D:/CodingData/Competition/PD/Codex-Delivery-20261119/PD-Rehab-Web | D:/CodingData/Competition/PD/Codex-Delivery-20261119/PianoForParkinson |
| 报告生成前实现 HEAD | 58f80c0674d5fdb51dbce4ab2d3a812a94ee1fd2 | 87df481315ec568169594df3b85532627c586ad1 |

两个仓库为并列 Clone，不互相嵌套。原 `D:/CodingData/Competition/PD/PD-Rehab-Web` 的未提交成果保留；旧隔离目录也保留。先 fetch 全部远程分支后选择基础。App main 为 cf12656，未包括队友完整 APK 更新器；当前选择包含 3ee3763 的最新目标分支。另一个 foreground-cloud-sync 候选没有该更新交付，不无条件混入。

## 队友更新机制的实际结论

队友实现位置：`lib/platform/apk_updates.dart`、`lib/features/apk_update_page.dart`、Android `updates/ApkUpdateBridge.kt`；使用同源 HTTPS 的 latest-android.json，下载完整 APK 后由 Android 确认覆盖安装。源码未见 Shorebird App ID、shorebird.yaml 或 SDK 依赖，不能认定为 Dart Patch。本轮不初始化、不重配签名、不改版本/原生/训练/同步；App 相对基线只增加一份真实兼容审计文档。旧隔离 App 的 5f7525e/18ffbb7 未进入交付分支。

## 生产基线与差异

只读实测生产源目录 `/opt/pd-rehab/app/PD-Rehab-Web`，HEAD 为 4794609，工作区干净；pd-rehab-backend active，PID 1389185 在前后核查中未变化。现有后端回环地址 127.0.0.1:18086；外部入口为 https://ccqspace.site/pd-rehab/。SQLite `/opt/pd-rehab/data/pd.db`，Alembic p2e4f6a8b0c2。GLM 供应商主机 open.bigmodel.cn，模型 glm-4-flash-250414，密钥仅确认已配置，没有读取到交付文件。本轮不更换供应商。

生产模型实测 4/4 READY，包含既有 CausalNet、手指和姿态资源；不等同于本轮重新完成真实患者推理。新 Clone 无私有模型/生产配置，本机验收环境只有部分模型就绪，因此未冒称本地完整模型闭环通过。此次未执行服务器写入、重启、迁移或 Nginx 覆盖。现有静态目录/代理配置需合并后按真实配置再次复核，不凭历史路径自动覆盖。

本轮未新增 Alembic 文件或业务表。现有迁移链已在独立库完成升级、回退一版、再次升级；实际生产无需本轮新迁移。

## 已实现与待办

文档站内阅读、授权检索、JSON/CSV 导出、任务状态持久化、可验证备份恢复、随访日期/PDF 和下载元数据/入口代码已实现。正式 APK 及证书未获可核验的稳定产物，下载入口保持不可用，不拿旧开发签名包替代。正式生产部署、真机安装和现场模型推理不在本轮已完成验收之列。

测试见 [跨端回归报告](cross_client_regression_report.md)，逐文件原因见 [修改文件清单](modification_file_inventory.md)。


## 2026-11-20 推送前远程变化

再次 fetch 确认 App 队友分支由6f4c8cc前进到98a122fb48013b048aee079fcd1d5a51cb06a3cd，新增5cbf055、98a122f。差异仅README、练习页移除姓名17行和v0.1.73验证说明；账号、同步、接口、APK清单协议及签名配置没有变化。本轮未自动合并这两个提交，App开发分支仍以核查时的6f4c8cc为基础，仅交付审计文档；维护者在PR中协调。已运行的911项回归对应6f4c8cc，不冒称复测了新98a122f全部源码。

GitHub现在有v0.1.73候选APK：isPrerelease=true，102920214字节，公布SHA256为457eff09c8852865d4a719d2039d41b4369c0c1679128c4cdf227a34ca7a9d5c。队友记录显示其真机覆盖安装仍待验证。此处只是公开清单元数据核查，没有将该预发布包当作批准的稳定正式包，也没有镜像到生产。正式下载入口仍保持未启用。
