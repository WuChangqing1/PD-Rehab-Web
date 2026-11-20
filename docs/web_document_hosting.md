# 文档服务器托管与阅读

当前批准收录 15 份 Markdown；PUBLIC 11、STAFF 2、ADMIN 2。批准 PDF 为 0 份；代码和合成用例支持 PDF 文件及浏览器预览，不宣称已上线真实 PDF 文档。Word 等其他格式未自动发布。

| 稳定 ID | 文档 | 权限 | 版本 |
|---|---|---|---|
| accounts | 注册、登录与找回密码 | PUBLIC | 2026-11-19 |
| piano | 钢琴训练操作与双手练习 | PUBLIC | 2026-11-19 |
| metrics | 训练与评估指标如何阅读 | PUBLIC | 2026-11-19 |
| sync | 跨端同步、历史与离线重试 | PUBLIC | 2026-11-19 |
| face | 面部录像、选帧与结果 | PUBLIC | 2026-11-19 |
| dance | 舞蹈课程与芭蕾动作 | PUBLIC | 2026-11-19 |
| plans | 训练计划与每日进度 | PUBLIC | 2026-11-19 |
| reports | 随访报告与数据导出 | PUBLIC | 2026-11-19 |
| assistant | AI 问答与资料引用 | PUBLIC | 2026-11-19 |
| faq | 常见问题与故障排查 | PUBLIC | 2026-11-19 |
| developer-readme | 项目 README 与运行说明 | ADMIN | source-4794609 |
| metric-reference | Web 指标技术定义 | STAFF | source-4794609 |
| integration-authority | 双端数据权威与一致性 | ADMIN | source-4794609 |
| staff-guide | 工作人员权限与使用 | STAFF | source-4794609 |
| app-android-updates | 琴伴 Android 安装包更新与下载 | PUBLIC | app-6f4c8cc |

## 访问与渲染

页面 `/pd-rehab/docs/{id}`；API `/pd-rehab/api/documents/{id}`。PUBLIC 不要求工作人员登录；STAFF 仅有效医护与管理员；ADMIN 仅管理员。权限由服务器验证，浏览器隐藏按钮不构成授权。PATIENT 不因知道 ID 获得内部权限。API 采用 private/no-store 和 Authorization Vary；附件同样鉴权。

Markdown 原生渲染标题、可点击目录、列表、代码块、表格、锚点和批准的图片。关闭原始 HTML；非法 URI、javascript/data 链接和未知相对文件不执行、不任意读取；禁止远程图片。README 中批准的14张图片经鉴权请求转为临时 Blob，避免 img 不发送 Bearer 导致401；离开页面释放对象 URL。PDF 经鉴权获取 Blob 后内嵌阅读/下载，不把私有文件变公开。

## 清单、更新和撤销

批准清单 `docs/library/manifest.json` 记录稳定 ID、来源、权限、版本、产品版本、更新时间及 SHA256；`inventory.json` 记录双仓库扫描和排除决定。当前扫描快照为 Web 133、App 126，不把扫描数量当成索引数量。历史部署报告、设计草案、未审核资料不自动公开；密钥/患者数据库/上传目录不扫描发布。

执行 `python scripts/publish_document_inventory.py` 更新清单和哈希。已有指南的人工编辑、取消授权状态、额外批准条目会保留，不由种子文字覆盖。新文档必须先审核再加入清单；App 文档先将已审核来源同步到发布副本，保留相同 ID，不修改逐条 AI 链接。格式不受支持时不伪装成可阅读文档。

服务每次请求检测清单哈希；更改权限、设置 enabled=false 或删除文件会使阅读/检索即时失效，不依赖服务重启。正文变化按内容哈希刷新；无效清单采取拒绝访问策略。只用白名单文件和批准附件，不开放任意路径或 GitHub Raw 代理。

## 真实验证

本机 Chrome：15个批准文档 API 全部200，8类问题来源均为本站路由，真实点击 AI 引用成功；私有 README 14张图片均加载。中英文界面分别验证1440/820/390宽度，文档与登录页无横向溢出。测试数据均为隔离数据；生产尚未发布这些路由。
