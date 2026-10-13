# UI 与钢琴优化：授权推送和生产部署

用户在本地优化验收后明确要求“推送并部署”，沿用此前指定的 GitHub `main` 和 `https://ccqspace.site/pd-rehab/`。本记录覆盖 2026-10-13 的实际发布。

## 发布版本与方式

- GitHub：`WuChangqing1/PD-Rehab-Web`，本地 main 从 `fb4d9d0` fast-forward 到 `19dba0f5165b0c06104422437deb0a14654a5ce2` 后推送成功。
- 生产应用源码与两套静态构建均来自 `19dba0f`；本部署记录、脚本和验证截图为后续交付提交，不改变应用源码。
- 通过 `ssh fengz` 现场核实服务器工作区干净、实际路径、空间与服务；没有依赖升级或数据库迁移。
- 后端目录 `/opt/pd-rehab/app/PD-Rehab-Web` 使用 Git bundle fast-forward，保留 `.env`、模型、患者库和上传文件。
- 前端分别以 `VITE_BASE=/`、`VITE_BASE=/pd-rehab/` 构建；发布至 `/var/www/pd-rehab/dist`、`/var/www/pd-rehab/dist-under-path`。
- 先复制静态资源，再原子替换两套 index.html；保留旧 hash 资源供已打开的页面加载。
- 仅重启 `pd-rehab-backend`，启动时间 2026-10-13 14:39:23 CST；Nginx 配置未变，`nginx -t` 通过，没有重启同机其他项目。
- 发布前使用 SQLite backup API 做 WAL 感知一致性备份，并备份旧前端与上传文件。部署脚本遇到发布错误会恢复旧源码和入口，保留备份；本次执行正常完成。

构建包 SHA256：`07f51685c5f66e0548ea786391d713ee7bfea5d170e118a4d01e33a2cd776d67`。

源码 bundle SHA256：`465dcb6d857419d8ff16b6fa0e53818dc8b518e3bb7310fb60f0e4ebd0632a61`。

## 发布前复验

| 检查 | 结果 |
| --- | --- |
| main 上 `npm run test --prefix frontend` | 219 passed |
| 根路径与子路径两次 `npm run build` | TypeScript 与 Vite 全部通过 |
| backend `python -m pytest -o addopts='' -q` | 386 passed，2 个既有 warnings，95.69s |
| 生产 Python 新配方 schema | 五种新配方和 tempo_ceiling_bpm 均接受，无会话写入 |

## 实际线上验证

见 [线上 HTTP / 浏览器结果](../artifacts/ui_piano_production_results.json) 和 [数据与清理结果](../artifacts/ui_piano_production_data_results.json)。

| 检查 | 结果 |
| --- | --- |
| `https://ccqspace.site/pd-rehab/` | 200，入口 SHA256 与本地子路径构建一致 |
| `http://110.42.236.65:18085/` | 200，入口 SHA256 与本地根路径构建一致 |
| 两套共 112 个 JS / CSS 文件 | 全部下载成功，逐文件 SHA256 与本地产物一致 |
| 8 个 SPA 入口刷新 | 全部 200，返回本次入口 |
| 公开健康接口 | 200，status=ok，env=production |
| 未登录 auth/me | 401 JSON |
| 钢琴音源 Range | 206，返回请求的 100 字节 |
| 真实 Chrome HTTPS | 登录重定向正确，Secure Context=true |
| 实际账号与实际只读 API | 13 项练习目录、五种新练习选择、试听、未选人开始弹选择器、取消均正常 |
| 390×844 手机 | 无页面横向溢出 |
| 浏览器异常 / 失败请求 / 训练写请求 | 0 / 0 / 0 |
| 实际后端 OpenAPI | 包含五种新配方 |

已登录线上浏览没有模拟患者 API；验证使用实际服务返回。脚本禁止已登录浏览器发出任何非 GET API 请求，未执行线上患者采集或训练保存。正常登录经过现有认证接口，增加 1 条 LOGIN_SUCCESS 审计；没有创建测试患者或训练记录。临时访问令牌未写入报告、结果 JSON、截图或 Git，使用后已删除。

生产截图：[登录页](../artifacts/screenshots/production/login.png)、[练习目录](../artifacts/screenshots/production/piano-desktop.png)、[手机目录](../artifacts/screenshots/production/piano-mobile.png)。

## 数据保留与备份清理

部署后与一致性备份逐表、逐行序列化 SHA256 比较，以下 13 张表内容完全相同：

`alembic_version`、`assessment_sessions`、`baselines`、`finger_tapping_results`、`functional_assessments`、`media_files`、`micro_expression_results`、`patients`、`piano_events`、`piano_sessions`、`pose_sessions`、`staff_users`、`training_plans`。

患者 10、钢琴会话 89、钢琴事件 45、芭蕾会话 58、评估会话 37、基线 11 均保留，迁移版本仍为 `g3b5c7d9e1f2`。唯一预期变化是正常验证登录使 audit_logs 从 82 增至 83；数据库 `quick_check=ok`。

按用户此前要求，上线验证和数据核对成功后，删除本次明确的 `/opt/pd-rehab/backups/ui-piano-20261013-19dba0f`，释放备份文件 **9,301,437 字节**。清理脚本只允许该固定目录，验证不是符号链接且父目录正确；没有遍历删除其他项目备份。上传 bundle、构建包、暂存产物及本地临时认证文件在发布完成后清理。

清理备份后，快速恢复旧 index 的文件备份不再存在；历史源码仍在 Git。旧 hash 静态资源继续服务已经打开的页面。

## 交付脚本

- `scripts/ui_piano_deploy_20261013.sh`：本次指定版本、校验值、备份、增量发布与失败回滚。
- `scripts/ui_piano_live_verify.mjs`：公网入口/静态资源/真实浏览器只读验收。
- `scripts/ui_piano_deploy_cleanup_20261013.py`：内容完整性验证与固定备份路径清理。

这些是本次发布审计脚本，带明确版本、目录和预期状态，不应作为下一次发布可直接重复执行的通用命令。实体手机验证和既有跨请求崩溃边界仍见 [优化报告](ui_piano_20261013_report.md)。
