# Shorebird 热更新交付与验收

## 当前已完成与未完成

App 基线 `cf12656`，版本 `0.1.73+74`，package `com.pianoforparkinson.piano_practice`；SDK 约束 Dart >=3.13.5，本机 Flutter 3.47.7。原 release 构建使用 Android Debug 签名，没有 shorebird.yaml。已移除正式发布的 debug 签名回退，增加从未入库 `android/key.properties` 读取原批准签名配置的守卫。签名缺失时实际 release 构建在 Gradle 明确失败，不产生冒充正式版本的 APK。

已固定 `shorebird_code_push: 2.0.7`（本次 pub get 仅增加这一依赖，未升级其他依赖），在设置→关于本版本加入检查更新。支持检查、下载中、不支持、已准备好、失败、当前最新提示；进度条不显示虚构百分比。不会退出 App、重启进程、中断训练或写数据库；用户完成训练后自行冷启动。普通 Flutter 安装包明确显示不支持热更新。UI 状态的 mock 测试不能等同实际补丁验证。

未安装 Shorebird CLI，未登录或开通账号；没有创建/臆造 app_id、基础 Release、补丁编号或正式签名。`adb devices -l` 实际未列出设备。场景 A/B 的设备补丁、覆盖升级数据保留和生产热更新仍未验证。

## 本次核对的官方资料

2026-11-19 通过 HTTPS 实际读取：

- [APK Release 与网站分发](https://docs.shorebird.dev/code-push/release/)：`shorebird release android --artifact apk`，必须分发 Shorebird 命令输出的 APK，普通 flutter build apk 不具备接收能力；支持 `--dry-run`。
- [Patch](https://docs.shorebird.dev/code-push/patch/)：显式 `--release-version` 和 `--track`，补丁继承基础版本构建参数。
- [更新策略](https://docs.shorebird.dev/code-push/update-strategies/)：下载后下次启动生效；自动更新默认开启，关闭会限制回滚检查。
- [Flutter 版本](https://docs.shorebird.dev/getting-started/flutter-version/)：官方页面当时显示稳定 3.47.9 / Dart 3.13.7，项目本次保留 3.47.7，未擅自升级；实际 Shorebird 引擎对该精确版本支持仍需 CLI 核实。
- [官方 updater 包](https://pub.dev/packages/shorebird_code_push)：API 返回最新 2.0.7，要求 Dart>=3.5.4 / Flutter>=3.24.5。此包基于 Dart FFI，不代表当前普通 Flutter 引擎已获得 Shorebird 能力。

Windows 是官方支持的 CLI 环境。账号/费用、组织归属和精确 Flutter 引擎版本未核实，不自动开通付费服务。

## 签名与基础版本准备

请由发布负责人提供原 keystore 的安全本地位置及独立核对证书，禁止在聊天或 Git 粘贴密码。已有正式包与新包必须同 package、同证书，新 versionCode 大于已发布版本。`android/key.properties` 已在原 .gitignore 中排除，字段 `storeFile`、`storePassword`、`keyAlias`、`keyPassword`；相对 storeFile 以 android 目录解析。禁止生成新钥匙替代原证书。

账号授权后由负责人按官方安装说明安装 CLI，先执行 `shorebird doctor`、`shorebird --version` 和 `shorebird flutter versions list` 核实。执行 `shorebird init` 绑定正确组织/真实 App，审查生成的 shorebird.yaml 与 pubspec assets（由 init 生成，不预置假 app_id）。保留官方默认自动下载策略，使冷启动回滚检查不依赖 About 页面；任何重启动作仍由用户自行决定。

先用隔离测试身份/经同意的测试设备验证，保护已有正式安装数据；首次 Shorebird 基础 APK 必须安装一次。安全检查后运行 `shorebird release android --artifact apk --flutter-version 3.47.7 --dry-run`。若精确版本不受支持，应停止并另行审批引擎升级，不修改原生插件来绕过。真实 Release 创建前记录版本、Git commit、构建参数、证书、SHA256、渠道及组织；官网稳定 APK 只接受正式审核通过的 Release。

## 测试轨道与真实 A/B 场景

验证基础版本时可编译 `--dart-define=SHOREBIRD_UPDATE_TRACK=staging`；该参数只改变本面板手动检查的 track，不能改变引擎默认自动检查轨道。不得给测试基线发布 stable 补丁；使用官方测试流程/preview 的 track 配置，记录冷启动日志和实际轨道。生产基线使用默认 stable；必须保持各基础 Release 的构建参数一致。

1. 记录测试账号、包版本、当前补丁、SQLite 历史数量、离线训练记录及已授权视频状态。不要使用真实患者资料上传第三方。
2. Dart 登录提示微调，执行 `shorebird patch android --release-version 实际基础版本 --track staging`。设备接收后完全退出再打开，拍摄提示变化，验证登录/会话恢复/历史/离线及同步，不重新安装 APK。
3. 第二次补丁在低风险页面添加打开已有页面的普通按钮，同样 staging 发布并测试跳转，记录补丁编号及设备变化。临时按钮验收后恢复，避免留下无用 UI。
4. 钢琴、舞蹈、计划进度、账号隔离、Android Keystore、面部视频 AES-GCM/分块上传均回归。没有实际设备不能完成这一步。
5. 将具体测试证据、稳定发布范围和回滚步骤交用户最终批准，才可推广到 stable；不要默认向 stable 推送未验证补丁。

本轮没有创建任何测试/稳定补丁。上述命令含说明性占位文字，必须先替换为实际 Release，不是可以直接运行的生产发布脚本。

## 原生边界与回滚

Kotlin/Java、AndroidManifest、插件、权限、引擎变化都需要完整基础 APK；Dart 业务逻辑/UI 才适合 Patch。资源变化须按 CLI 判定和官方支持范围审查，不能承诺所有资源可补丁。

回滚由 Shorebird 控制台/CLI 的真实 Release 和 patch 记录操作，先在测试轨道验证设备接收撤销、下次冷启动恢复。默认自动检查有助于启动失败场景恢复，手动入口不能保证救回所有启动失败。未验证前不得承诺零风险。网站 APK 清单回退与 Shorebird 补丁回滚是两个独立动作，不能靠降 versionCode 覆盖安装回退数据库；不要卸载清数据。

## 本地执行证据

Flutter analyze：No issues found。完整 flutter test：912 通过、2 跳过、0 失败（包含本次新增 4 项 widget 测试）；其他集成项见 integration_test_report；原 SQLite 下载器网络超时后，通过官方 GitHub release 下载相同 DLL，SHA256 `2bf39f2aadafdc59a90b260f582a8fccebc5b89eb94175fdbaa9148c1e1f084d`，放入忽略的本地 hook cache，依赖自身哈希校验后重跑。没有修改 SQLite 版本或实现。

Android Release：使用现有 `_deploy/gradle-autosync` 和 `_deploy/android-sdk-autosync` 缓存执行，Gradle 在新签名守卫处失败：`Formal release signing is not configured`。这是正式发布阻碍的真实证据，不能计为 release 构建通过。真实 Shorebird Release/patch/设备验证均未执行。
