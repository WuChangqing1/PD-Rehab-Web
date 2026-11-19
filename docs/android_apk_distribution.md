# 琴伴 Android 安装包分发

## 当前结果与边界（2026-11-19）

登录页增加无需登录的「下载琴伴 Android App」入口，查询失败不影响原有登录。未配置正式签名及获批 APK 时按钮禁用并显示「正式安装包准备中」。本轮没有发布 APK，没有正式下载文件 SHA256；不得把该入口状态描述为正式 APK 已上线。

拟正式地址为 `https://ccqspace.site/pd-rehab/api/android/download`，目录 API 为 `/pd-rehab/api/android/latest`。后端自身路由为 `/api/android/*`，由现有子路径代理转发。元数据提供版本、大小、SHA256、证书指纹、最低 Android API、发布时间、包名、Shorebird app ID 与 Release、相对于元数据地址的 `download_url: ./download`。

## 启用条件

管理员配置 `ANDROID_RELEASE_DIR`（默认 `data/android-releases`）、`ANDROID_EXPECTED_SIGNER_SHA256`（独立核对原正式安装包的证书 SHA256），以及绝对路径 `ANDROID_APKSIGNER`、`ANDROID_AAPT`。两个 Android SDK 工具必须在服务器可执行；Linux 部署使用 Linux SDK 工具。目录应由发布管理员拥有，Web worker 只有读取权限；不得让普通上传接口写入。

服务器读取该目录的 `stable.json`。模型拒绝额外字段，必填字段如下：

- `approved: true`、`channel: stable`、安全的同目录 `.apk` 文件名 `filename`。
- `version_name`、整数 `version_code`、`package_id: com.pianoforparkinson.piano_practice`。
- 正整数 `size_bytes`、小写 64 位 `sha256`、`signer_sha256`、整数 `min_sdk`。
- 含时区的 ISO8601 `published_at`。
- 真实 `shorebird_app_id`、`shorebird_release`（必须等于 `version_name+version_code`）。

这里只是 schema，未提供伪造的「批准版本」示例或清单。正式发布时先由 Shorebird APK Release 构建，人工审核账号 Release 和来源，确认包名/原证书/覆盖安装/数据保留后再写清单。先上传带版本号的不可变 APK，再原子替换 `stable.json`。修改同名 APK 会破坏校验，应发布新文件名。APK、签名私钥和密码均不得提交 Git。

每次读取目录或下载都验证文件大小、实际 SHA256、apksigner 签名验证和证书、aapt 包名/版本/minSDK/debuggable 标志以及 APK 内 `assets/flutter_assets/shorebird.yaml` 的 app ID。拒绝 Android Debug 证书、未配置工具、缺失文件、路径遍历、未批准轨道与普通 Flutter APK。清单是发布管理员的批准记录，不能代替 Shorebird 账号中的 Release 来源审核。

## HTTPS、缓存与断点续传

沿用网站 HTTPS。响应 MIME 为 `application/vnd.android.package-archive`，Attachment 文件名来自安全清单。Starlette FileResponse 支持 Range，测试验证 `bytes=0-9` 返回 206 与 10 字节。稳定别名及元数据 `Cache-Control: no-store` 防止批准撤销后复用缓存；不开放整个发布目录静态浏览。服务器代理需允许 APK 大小和 Range/If-Range，不得将错误响应替换成 SPA HTML。完整 APK 的每次校验包含磁盘读取与外部工具调用，发布前按真实包体积测量耗时与下载并发；高频大规模分发应改为经验证后的不可变对象分发。

## 验证

`python -m pytest backend/tests/test_android_distribution.py`：19 项通过（后续集成报告为最终数字）。覆盖无签名配置、匿名元数据、匿名下载与 Range、证书、debug、版本、包名、大小和哈希错配、路径遍历、Shorebird 关联及工具失败。APK fixture 和工具输出为测试构造，未声称完成正式签名实包验收。

发布验收必须在真实 HTTPS 地址检查登录、元数据、下载状态/MIME/Range、下载后 SHA256 与 `apksigner verify --print-certs`，用现有正式安装包做覆盖升级并验证历史、登录、离线训练、同步与面部采集。当前缺失原正式签名、正式 Shorebird Release 与测试设备，正式下载验收未通过。

回滚：先原子恢复上一份获批且原证书兼容的清单；如证书/构建来源不确定则移走 `stable.json` 关闭入口。不要删除设备数据或发布降低 versionCode 的 APK。
