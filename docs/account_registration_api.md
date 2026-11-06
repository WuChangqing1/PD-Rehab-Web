# 移动账号接口约定

日期：2026-11-06。本轮本地实现，尚未正式上线。基路径 `/api/mobile/auth`，JSON 请求；与工作人员 `/api/auth/login` 分离。

## 公共接口

| 路径 / 方法 | 请求字段 | 成功响应 |
| --- | --- | --- |
| `POST /register` | `username`、`password`、`display_name`、`sync_consent_version="account-sync-v1"` | 201；身份、双 Token、一次性 `recovery_code` |
| `POST /login` | `username`、`password` | 200；身份与双 Token，不返回恢复码 |
| `POST /refresh` | `refresh_token` | 200；新身份、新双 Token，旧刷新令牌立即失效 |
| `POST /logout` | `refresh_token` | 200；幂等撤销该设备会话，也接受刚轮换前的一代凭证用于退出补偿 |
| `POST /reset-password` | `username`、`password`（新密码）、`recovery_code` | 200；新恢复码和提示，撤销全部会话，需重新登录 |

用户名为 3–32 个英文字母、数字或下划线，统一小写，拒绝与工作人员用户名大小写重名。注册和密码更新要求 8–64 字符且 UTF-8 不超过 72 字节。姓名/昵称 1–64 字符，去除首尾空白。额外角色/患者字段不允许；不能指定已有患者或升级工作人员身份。

## 需 Bearer 的接口

| 路径 / 方法 | 请求 | 成功响应 |
| --- | --- | --- |
| `GET /me` | `Authorization: Bearer <access_token>` | 当前 `user`、`patient` |
| `POST /change-password` | Bearer + `current_password`、`new_password` | 200；撤销全部移动会话，需重新登录 |

注册/登录/刷新成功结构：

```json
{
  "user": {
    "id": "<用户UUID>",
    "username": "<规范化用户名>",
    "display_name": "<姓名或昵称>",
    "role": "PATIENT"
  },
  "patient": {
    "id": "<患者UUID>",
    "name": "<姓名或昵称>",
    "hospital_number": "<后端分配编号>"
  },
  "access_token": "<仅内存使用>",
  "refresh_token": "<安全密文保存>",
  "expires_in": 900,
  "refresh_expires_at": "<UTC ISO8601时间>",
  "token_type": "bearer"
}
```

注册另加 `recovery_code`；重置仅返回提示和轮换后的恢复码。恢复码只交给用户一次，不写日志、数据库明文、分析统计或公共文档。

## 同步使用

从登录响应取本人患者 UUID，调用 `POST /api/integration/v1/bindings` 绑定当前本地 `device_id` 与 `local_profile_id`，之后复用既有 records、plans、changes、patient-data 与视频接口。普通账号 bootstrap 仅返回本人，不返回工作人员目录；客户端无需选择其他患者。

普通账号只允许明确列出的本人接口。认证成功不能替代对象授权；操作录像仍检查患者、上传者、设备绑定和文件归属。媒体播放 Cookie 同样受会话撤销约束。

## 客户端错误处理

- 400 当前密码错误：保持页面并提示，不静默改密。
- 401 失效/撤销/错误凭证：终止重试循环并退出相应身份；刷新重试最多一次。
- 403 权限/对象不匹配：停止对应操作，不能当成空列表或另一个患者的数据。
- 409 用户名冲突：更换用户名，不重复创建患者。
- 422 字段不合法：显示校验错误；不记录密码内容。
- 429：遵守 Retry-After。注册和恢复每 IP 每 10 分钟最多 6 次，登录默认 12 次，刷新 120 次；当前实现是进程内补充限制，上线多 worker 需要边缘共享限流。
- 404/未部署：提示服务需要更新，不能在本地假注册、降级为工作人员登录或绕过账号门。
- 网络不可达：已有未到期的加密会话可进入原账号离线训练；首次注册/登录不得离线成功。

认证响应 `Cache-Control: no-store`。Access Token 15 分钟、刷新会话轮换后 30 天；不得无限延长离线缓存身份。最新精确字段和校验以该版本 OpenAPI/源码为准。
