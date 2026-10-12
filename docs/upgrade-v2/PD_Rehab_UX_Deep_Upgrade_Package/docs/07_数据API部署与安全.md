# 07 · API、数据版本、线上部署与项目边界

## 保留的项目技术路线

Vue3 + TypeScript + Vite + Element Plus + ECharts；FastAPI + Python3.11/Conda `pd`、PyTorch、OpenCV、MediaPipe、SQLAlchemy/Alembic。正式站点 `https://ccqspace.site/pd-rehab/` 为子路径部署；后端统一 `/api`，代理按真实 Nginx 配置核查。`ssh fengz` 仅是已知连接方式，未知部署根目录/端口/域名证书状态不能猜。

## 标准实体关系

`patient → assessment_sessions → micro_expression_results/finger_tapping_results`；`patient → piano_sessions → piano_events`；`patient → pose_sessions → raw_pose_metrics`；`patient → history/trends/reports`。其中 `pose_sessions` 引用媒体示范 (`demo_asset_id`) 与真正的患者原始录像 (`recorded_media_id`) **严格分离**。

只做增加型 migration，保持旧 Yoga 和 Piano 历史可读，旧算法版本仍能做版本过滤，不允许将旧结果批量改名为 Ballet。

## 芭蕾媒体注册表接口（两种可行策略）

**首选 A：静态编译资产 + manifest**。有效素材复制到 `frontend/public/assets/ballet/`；读取经过审核的 manifest，`frontend` 使用 `import.meta.env.BASE_URL` 构造链接。无需新增后台复杂媒体 CMS。

**可选 B：服务器受控媒体资源**。如文件尺寸/版权要求不进 Public GitHub，可存 `backend private media` 并由授权 API 签名/受控读取，不硬编码公开 URL，仍要有 manifest。

样例 `GET /api/movement/exercises?execution_mode=SEATED` 应保留，返回定义与支持模式；扩展媒体元数据时不要破坏旧 schema。媒体 readiness 应和动作 readiness 分开，不代表 Pose 模型 READY 就有合格动作视频。

## 媒体资产状态

`NOT_SELECTED → SOURCE_FOUND → LICENSE_VERIFIED → DOWNLOADED → CLIP_REVIEWED → MOVEMENT_APPROVED → TRANSCODED → QA_PASSED → PUBLISHED`。

任何 `license_verified=false` 或 `movement_reviewed=false` 的媒体都不能在公共站点自动作为正式示范播放。资产落库包含 source URL、license URL、作者、取得日期、SHA256、剪辑起止、训练模式、审核人、技术文件信息。manifest 可分源码候选/生产批准两个文件。

## 数据质量与可解释性

- 钢琴新 `recipe_id`、cue 策略、速度、输入来源、判定窗、round ID；CFT撤提示后 latency 为 null。
- 芭蕾 raw metrics、effective frame ratio、摄像头视角与质量门槛、exercise/mode、媒体示范版本；不通过视频 QC 时不给可用评分。
- 微表情模型 `MODEL_NOT_CONFIGURED` 与 `FAILED` 与 `NO_EVENT_DETECTED` 三种语义区分；无实际模型不能显示“本次未检测到表情”以免误解为真实阴性。
- 所有趋势保留 patient、采集时间、药物 ON/OFF/UNKNOWN、算法版本、模式、provenance；不同训练模式不混合平均。
- 演示数据可保留供界面预览，但内部仍须明确标记 `SEED_DEMO/SYNTHETIC`。不得对外宣称合成结果属于已验证患者疗效。UI 可以不显示繁杂技术标签，不得产生虚假的临床陈述。

## 部署安全与体验

1. 修改前记录服务器配置、可用空间、端口、Nginx/HTTPS、当前正常版本、备份数据库和上传文件清单。不要覆盖其它服务。
2. `frontend` 打包 `VITE_BASE=/pd-rehab/`；测试页面刷新可回退 index.html、静态 MP4 MIME/Range 和子路径 URL。
3. HTTPS 下 getUserMedia 可用；手机 Safari `playsinline`；音频上下文必须由实际点击恢复。
4. 安全 API（`/api/system/models`, `/api/system/gpu`）保留用于运维，但不要将本机绝对路径、GPU详细内部信息和敏感配置无鉴权暴露给公网访问者；不必建独立 ADMIN 用户，只做服务端认证/最小必要输出或内网访问限制。
5. 所有登录人员业务体验一致，安全认证不能取消；患者真实数据需按组织要求授权和审计。
6. 发布过程：本地 `pytest`/`npm test`/`npm run build` → Git main/部署分支 → 服务器拉取 → 验证/回滚。明确回滚指令和 DB migration 回滚策略。

## 需谨慎的用户文案

- 主页面不显示“用于科研、比赛、Demo、Phase、Mock、虚拟”，但**训练时“站不稳请扶椅/不适请立即停止”必须可见**，并保留法律/版权要求的必要媒体署名渠道。
- 非医疗结论仅用“本次观察到的动作幅度/节拍表现/面部分析输出”；无有效跨期数据不说“病情改善”。
- 公网上的演示账号需独立凭据和 rate limit，不把初始密码写到登录页。
