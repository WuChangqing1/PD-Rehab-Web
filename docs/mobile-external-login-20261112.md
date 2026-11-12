# App 手机号登录及预留微信接口：后端部署交接

2026-11-13 更新。本机代码基线 `20761b9`；本轮代码尚未推送或部署。用户已完成阿里云控制台测试短信接收及专用 RAM 用户授权，专用 RAM 凭证通过此后端真实发送/核验、App 登录仍未验收。当前只启用短信，微信开关须保持 false；App 微信登录、绑定入口均已隐藏。请使用 `sms-login-20261113-handoff.zip`，本次操作顺序见 `docs/mobile-sms-release-20261113.md`。

## 集成内容

手机号＋短信验证码登录与微信授权登录；首次验证创建普通 PATIENT 及本人 Web 档案，已有身份复用旧账号。原账号可主动绑定新登录身份，患者 ID 和记录归属不变。

新增表：`mobile_identities`、`mobile_login_challenges`、`mobile_auth_limits`。迁移：`o1d3e5f7a9b1`，父版本 `n0c2d4e6f8a0`。原用户名/密码注册建档逻辑提取为共享函数，权限和原有 Token、刷新、撤销逻辑继续复用。

微信通过固定 HTTPS 端点由服务端交换 code，仅使用已核验、按 AppID 隔离的 OpenID；不信任客户端提供的患者、角色、昵称匹配或 UnionID。短信使用 PNVS `SendSmsVerifyCode`/`CheckSmsVerifyCode`，必须检查 `Model.VerifyResult=PASS`。默认关闭，无模拟登录模式或测试验证码后门。

Python 侧使用标准库实现阿里云 RPC 1.0 HTTPS 签名请求，签名已与官方 SDK 的含中文固定向量交叉校验，不新增 Python 运行时依赖。`ReturnVerifyCode=false`、`AutoRetry=0`；验证码由阿里云产生/核验，不通过我们的 API 或日志返回。

## API

所有路径相对 `/api/mobile/auth`。响应使用现有统一错误格式，认证响应禁止缓存。

| 路径 | 请求 | 返回 |
| --- | --- | --- |
| GET `/providers` | 无 | `wechat_enabled`、`sms_enabled`、可公开 AppID |
| POST `/sms/challenge` | `phone`（11 位或 +86） | 挑战 ID、脱敏号码、300 秒有效期、60 秒重发间隔 |
| POST `/sms/login` | 挑战 ID、6 位 `code`、`sync_consent_version=account-sync-v1` | 原有双 Token、身份；新账号额外返回一次性恢复码 |
| POST `/wechat/challenge` | 无 | 挑战 ID、随机 `state`、AppID、有效期 |
| POST `/wechat/login` | 挑战 ID、`code`、`state`、同步版本 | 同上 |
| GET `/identities` | 当前移动账号 Bearer | 本人的脱敏绑定列表 |
| POST `/identities/sms/challenge` | Bearer、`phone` | 绑定专用短信挑战 |
| POST `/identities/sms/bind` | Bearer、挑战 ID、`code` | 绑定确认，不签发新身份 |
| POST `/identities/wechat/challenge` | Bearer | 绑定专用微信挑战 |
| POST `/identities/wechat/bind` | Bearer、挑战 ID、`code`、`state` | 同上 |

登录验证失败为 401；绑定中的验证码/授权错误为 400，避免误触客户端 Token 续期。绑定要求登录后 15 分钟内发起及完成；超时为 403，重新登录后再绑定。其他账号已占用同一身份或已绑定另一号码时为 409，不自动覆盖/合并。未配置为 503，限流为 429 并附 Retry-After。重复、过期、用途不符、会话不符的挑战都不接受。

## 配置与开通

使用 `deploy/mobile-login.env.example`，将新增变量合入现有后端环境，保留既有 DB/JWT 配置；服务开通并填入真实配置后才把对应 ENABLED 改为 true。

- 微信：预留接口，本次不启用、不要求提供 AppID/AppSecret。未来启用时需要开放平台移动应用 AppID、AppSecret，登记安装包的包名与签名，并取得微信登录权限。
- 阿里云：开通**号码认证服务中的短信认证**，配置系统赠送签名及匹配的模板，模板变量须为 `code`、`min`。默认方案名称留空。
- 专用 RAM 权限：`dypns:SendSmsVerifyCode`、`dypns:CheckSmsVerifyCode`；后端静态凭证从环境变量读取。
- 每手机号每 60 秒 1 次/24 小时 10 次、每 IP 每小时 20 次，全服务每 24 小时默认 100 次预留。各自使用首次请求起算的固定窗口，不是严格滑动窗口，也不按自然日重置。失败也占预留；额度配置为 `MOBILE_SMS_DAILY_BUDGET`。持久化配额在多个 worker 之间共享；外层继续使用可信代理的真实 IP 和既有流控。
- 不将密钥放入 App、源码仓库、测试报告或聊天。部署包不包含 `.env`、生产库、患者数据和密钥。

## 部署步骤

1. 在服务器当前分支上合并本轮变更。若已有其他后端更新或迁移头，应先合并迁移链，保留现有业务源码；不能直接覆盖成此本机旧基线。
2. 备份当前数据库，在隔离副本运行 `python -m alembic upgrade head`；核对旧表逐行数据、账号、记录及外键，仅应增加三张表。
3. 在现有维护窗口升级目标后端，执行迁移并按已有方式重启该服务；不改其他项目或代理路由。
4. 保持两个功能开关 false，确认旧账号登录、患者与训练记录不受影响；检查 `/api/mobile/auth/providers` 返回 false。
5. 本次只配置短信，在独立测试账号上核对真实短信、绑定和重登录；微信开关继续保持 false。
6. 分发包含新手机号界面的新版 App。既有 APK 不会因为后端升级就自动获得这些入口。

本地自动化测试使用假提供方和临时数据库，不会发送真实短信或写入生产患者。微信主体、包名/签名审核、服务开通、真实验证码到达率、设备回调和公网部署仍需实际验收。

最终账号相关回归：`python -m pytest -o addopts= -q tests/test_mobile_accounts.py tests/test_mobile_external_login.py tests/test_external_login_migration.py tests/test_patient_numbers.py tests/test_schema_bootstrap.py`，44 通过。全量回归另有 5 项在原始 HEAD 同样失败：缺少 mediapipe/pandas，以及 Python 3.11 固定版本断言与本机 3.13 不符。完整结果在 App 的 `validation/wechat-phone-login-20261112.md`，不能将本次结果理解为后端所有测试通过。

回退优先关闭新增开关、切回已知可用代码，保留身份映射和用户数据。尚未产生任何绑定时可正常 downgrade；已有绑定时迁移拒绝破坏性 downgrade，避免删除用户登录身份。
