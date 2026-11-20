# 当前采用完整 APK 更新：Shorebird 方案不执行

用户最新要求以队友 `feature/android-apk-updates` 分支为准。App 真实基线 `6f4c8cc`，完整 APK updater 来自 `3ee3763`。该分支没有 shorebird.yaml 或 shorebird_code_push 依赖，未发现 Shorebird app_id。

此次保留已有的登录页/主界面更新检查、关于页手动检查、下载进度/取消/校验及 Android 安装确认；Web 仅复用队友 latest-android.json。此机制需要下载完整 APK，经 Android 确认安装，不是无需重装的 Dart Patch。用户已接受跟随现有实现，不再建立第二套升级管线。

旧隔离 App 工作区的 `5f7525e`、`18ffbb7` 没有进入此次独立 App 交付分支；不重新 init、不创建 App ID、不改签名、不安装 CLI、不发布 Shorebird Release/Patch。

当前操作、唯一清单协议及正式 APK 审核边界见 [Android APK 分发](android_apk_distribution.md)；队友的客户端约定见 App 仓库 `docs/android-apk-update.md`。本文件仅记录方案变更，不能作为当前 Shorebird 已接入或补丁测试已完成的证据。
