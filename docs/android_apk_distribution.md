# 琴伴 Android 安装包分发：复用 App 现有协议

## 当前基线与结果

以独立 App 克隆的 `origin/feature/android-apk-updates` / `6f4c8cc` 为基线，其 `3ee3763` 已实现完整 APK 更新。协议以队友 `docs/android-apk-update.md` 为准。此次不引入 Shorebird、不复用此前隔离工作区的 App 签名或热更新改动，不改 App Dart、原生插件、包名、签名或版本。

Web 登录页「下载琴伴 Android App」和 App 共用唯一发布指针：

`https://ccqspace.site/pd-rehab/assets/app-releases/latest-android.json`

Web `/pd-rehab/api/android/latest` 从同一文件派生元数据，验证后按钮直接指向清单 `apkUrl`；兼容下载路由 `/pd-rehab/api/android/download` 读取同一 APK，没有独立 stable.json。普通经过批准且正式签名的完整 Flutter APK 可以分发，不要求 Shorebird 配置，也不宣称 Dart 热更新。

当前公开清单实测 404（2026-11-19），未准备/上传真实 APK，登录页保持「正式安装包准备中」。没有正式下载 SHA256 或正式上线成功的结论。

## 唯一清单格式

字段严格采用队友协议，不添加客户端必需字段：`schemaVersion`（整数 1）、`packageName`、`versionName`、`versionCode`、`apkUrl`、`sizeBytes`、`sha256`、`notesZh`、`notesEn`。

packageName 固定为 `com.pianoforparkinson.piano_practice`；versionCode 范围 1..2100000000；包体积不超过 1 GiB；两种说明最长各 2000 字。清单和 APK 是同源 HTTPS、直接文件响应，不重定向。网站当前允许的静态前缀为 `https://ccqspace.site/pd-rehab/assets/app-releases/`，APK 可置于版本子目录。服务拒绝路径遍历、编码路径、查询参数、符号链接、其他域名和未匹配的 APK。

## 本地准备发布包，不部署

管理员在本地配置 Android SDK 工具绝对路径 `ANDROID_APKSIGNER` 与 `ANDROID_AAPT`。使用已批准的真实 APK 和独立核对的原批准签名 SHA256。脚本不生成或修改签名、不构建 App、不访问生产服务、不上传文件：

```powershell
python scripts/prepare_android_release.py --source-apk C:/review/approved.apk --output-dir C:/review/android-bundle --trusted-signer-sha256 ORIGINAL_CERT_SHA256 --notes-zh '已审核更新说明' --notes-en 'Reviewed release notes' --approved-artifact
```

命令含说明性路径和证书占位文字，必须换成实际审核过的输入。脚本从实际 APK 读取包名/版本/minSDK，验证 apksigner、原签名、非 debug、非 debuggable，计算 SHA256 与大小。复制为 `版本/qinban-版本-android.apk` 后再次检查副本 SHA256，最后原子写入 latest-android.json。缺少明确的 artifact 批准则不写任何产物；现有版本文件绝不覆盖，已有清单要求 versionCode 严格增加，防止不慎降级。

在独立目录审阅产物后，仍须用户最终批准生产发布。上传时先部署不可变版本 APK，再替换清单，不可反序。配置 Nginx 将该公开路径映射至同一发布目录，不使用 SPA fallback；清单不存在返回真实 404。

## Web 校验和服务器配置

`ANDROID_RELEASE_DIR` 指向上述已部署静态目录，默认仍为 `data/android-releases`，须与 Nginx alias 指向同一位置。`ANDROID_EXPECTED_SIGNER_SHA256` 是独立可信原签名，绝不从公开清单读取。配置 Linux 对应版本的 `ANDROID_APKSIGNER`、`ANDROID_AAPT`。发布目录由管理员写入、Web worker 只读；普通上传入口无写权限。

每次 API 读取验证实际 APK 的大小、SHA256、签名、包名、版本和 minSDK；工具/配置/校验失败则不开放下载。发布清单文件的存在代表管理员批准指针，不替代人为来源审核。生产容量及并发需按实包测量，因为当前 API 会读取全文件并调用工具。

HTTPS 静态 APK 使用 `application/vnd.android.package-archive`，支持 Range/If-Range；版本文件可使用 immutable 缓存，latest-android.json 设置 no-cache。兼容 API 元数据和下载 no-store，FileResponse 的 Range 单元测试通过。不要把整个数据目录公开。生产部署前验证无重定向、正确 MIME、SHA256、字节数、Range 与真实 App 升级；当前尚未部署。

## 当前可用产物审计

只读查询 [GitHub 最新公开 Release v0.1.72](https://github.com/CapriChris/PianoForParkinson/releases/tag/v0.1.72)：非 draft、非 prerelease，2026-11-14 发布，APK `qinban-0.1.72-android-universal.apk` 为 102723070 字节，GitHub 元数据摘要 `61747fb78564a4d60d51759b3d67296b108fe924420dceb319cd78516a159a51`。这只是 GitHub 元数据，未下载实包核验。

Release 正文明示沿用「原内部测试开发签名」。它早于当前源码 `0.1.73+74`，不能仅凭 stable 标签当作此次批准正式最新版，未用于清单。原正式签名及获批最新版 APK 仍是分发前置条件。此次不修改队友 App 中现存签名配置，也不重新生成钥匙。

## 测试与回滚

`python -m pytest backend/tests/test_android_distribution.py --basetemp 指定的隔离目录`：22 项通过。覆盖同一清单权威、普通 APK、匿名下载/Range、schema/类型/包名/版本/大小/哈希、域名/路径、安全签名与工具失败、本地准备脚本的明确批准和单调版本号。工具输出和 APK fixture 是单元测试构造，不是正式实包验收。

回滚 Web 代码和撤下清单可关闭新增下载；不要降低 versionCode 使设备覆盖安装。任何旧 APK 指针恢复必须确认当前设备升级策略及独立批准，不能把源代码回滚等同设备数据回退。不得卸载/清除患者数据。App 当前完整 APK 升级机制的真机验收须由队友原方案完成。
