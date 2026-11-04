# 训练面部录像 Android 基线对照

日期：2026-11-04。使用同一 Windows 运行环境、Flutter 3.47.7 / Dart 3.13.5，以及通过原仓库 SHA-256 校验的四个离线课程视频。Android 检出和构建均在独立目录；未修改或推送 Android 分支，未操作生产 Web。

| 验证 | 旧基线 `dc25b33` | 录像版 `c5607f8` |
| --- | ---: | ---: |
| `flutter test --no-pub --machine` 通过 | 622 | 630 |
| 失败 | 102 | 102 |
| 仅该版本失败的「测试文件 + 名称」 | 0 | 0 |
| 录像专用测试 | 不适用 | 8 通过 |
| `flutter analyze --no-pub` | 本轮未执行 | 通过，无问题 |

本轮跑的是全量 Flutter 单元和组件测试，交接的 23 项是所选页面和训练用例；仓库没有提供那次选择集的逐项输出，不能把 102 逐项对应到原 23。当前全量失败集合在两版完全一致，不能宣称 Flutter 全量通过。

按录像版每条失败首次报告的异常类型分类，互不重复：

| 数量 | 类型 | 代表性问题 |
| ---: | --- | --- |
| 51 | 断言失败（`TestFailure`） | 文案查找、页面可见状态、横屏控制布局或溢出不符合旧断言 |
| 39 | 类型转换（`_TypeError`） | 测试将 `QinOutlinedButton` 等控件转换成旧的 `OutlinedButton` |
| 6 | 状态异常（`StateError`） | 引导或训练入口，例如点击目标超出测试视口后流程无法继续 |
| 3 | 延迟初始化（`LateError`） | `InstructionPage` 的 `song` 尚未初始化 |
| 3 | 组件框架断言 | 例如 `tap()` 找不到目标控件 |

以上失败都在原有 widget 用例中。新增录像用例覆盖相机替身、静音采集、前后台和身份切换、放弃练习以及侧库迁移；不代表物理相机或手机网络实测。

两个功能目前位于不同的 Android 分支：`main@c5607f8` 含训练录像，尚不发送 `daily_progress` 和 `snapshot_revision`；`codex/foreground-cloud-sync@085f36d` 含计划进度上报。Web 已验证接收、保留版本及按日显示；若要验收单个 APK 同时具备这两项功能，需要先在 Android 协作分支合并并回归。

本机证据位于 `_deploy/training-face-android-{baseline,candidate}-tests.jsonl`、`_deploy/training-face-android-comparison.txt` 和 `_deploy/training-face-android-analyze.log`。ADB 尚未连接设备，预发布 Web 仅绑定回环地址；手机联调需要受控且设备信任的 HTTPS 预发布入口。真机验收和生产批准均尚未完成。

已从原样的 `c5607f8` 构建 `_deploy/PianoForParkinson-training-face-QA-arm64.apk`（686145731 字节）。`aapt` 确认 ABI 为 `arm64-v8a`、包名为 `com.pianoforparkinson.piano_practice.validation`、包含相机权限；`apksigner` v2 验证通过。它与正式 App 包名不同，但与上一份自动同步验证 APK 使用同一测试包名，安装时不要把两份测试包当作可并存应用。SHA-256：`2001145f60128bbfb7a3381136f748f875d4fbe3b6fbb6ca1b0ca1e9282a1298`。
