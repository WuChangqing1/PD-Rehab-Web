# 曲目跟弹升级生产部署记录

日期：2026-10-16（Asia/Shanghai）。用户明确授权“部署并推送”。

## 发布状态

- GitHub `WuChangqing1/PD-Rehab-Web` 的 main 已推送。
- 应用代码发布版本：`35adc62380435cf726d0bdd5601424438d5d35b7`。后续审计提交仅包含本记录、验证脚本和截图，不改变运行代码。
- 主入口：https://ccqspace.site/pd-rehab/
- 曲目跟弹：https://ccqspace.site/pd-rehab/training/piano/guided-song
- 备用入口：http://110.42.236.65:18085/
- 两套构建分别来自 frontend/dist 和 frontend/dist-under-path；服务器296个静态文件全部通过逐文件SHA256校验。

## 发布操作

沿用 ssh fengz、/opt/pd-rehab/app/PD-Rehab-Web、/opt/pd-rehab/venv/bin/python 与 /opt/pd-rehab/data/pd.db。使用 Git bundle fast-forward，未覆盖 .env、模型、上传文件或未提交修改。

新增专用 WebSocket location：HTTPS 下 /pd-rehab/api/live-emotion/stream、独立端口下 /api/live-emotion/stream。保留 Upgrade / Connection 头并关闭缓冲；其他项目路由未改。Nginx配置测试通过，随后平滑reload；后端完成重启与健康检查。

数据库升级 g3b5c7d9e1f2 → h4c6d8e0f2a3，只新增 guided_song_sessions。生产 EMOTION_SIMULATION_MODE=false，真实模型返回 MODEL_NOT_CONFIGURED，不启用模拟概率。

发布前在停止后端后做 SQLite backup API 一致性备份。首次发布在静态校验时发现：私有暂存 umask 导致静态目录变成700，校验用户无法读取；脚本自动恢复旧源码、入口和Nginx配置，重启旧后端。新增表迁移为增量操作，保留且未回写旧数据。修复rsync发布权限为目录755、文件644后安全重试，复用首次备份，最终发布成功。

## 线上验证

- 主域名与独立端口：入口、钢琴、曲目跟弹、芭蕾刷新均200，入口字节与对应构建一致。
- 音符SVG正常，本地与公网内容一致；钢琴MP3 Range返回206及100字节。
- 健康接口status=ok、env=production；受保护曲目接口未登录返回401。
- 已认证历史接口返回200，证明生产新增表可查询。
- 真正的Chrome登录态只读浏览：目录新增曲目入口、七键、五条波浪线、患者选择弹窗均正常；PC/平板/手机视口无横向溢出，页面运行异常0。
- WSS握手成功到达后端；发送无效首包凭证后返回4403鉴权关闭，符合预期。此项验证传输路由，未声称真实模型推理已完成。
- 验证使用服务器内存生成的5分钟短时令牌，不读取或修改密码。令牌未落盘或写入报告；浏览器关闭后不保留登录态。
- 验证脚本禁止非GET API请求，未创建患者、会话或训练数据。

证据：../artifacts/guided-song-production/verification.json，以及 live-pc.png、live-tablet.png、live-mobile.png。

## 数据与清理

对所有已有表逐表序列化SHA256比较，除Alembic版本变更外内容完全一致，数据库quick_check=ok。患者10、钢琴会话89、钢琴事件45、芭蕾会话58、评估会话43、基线11均保留；新增曲目会话0，审计日志仍为91。详见 data-check.json。

依照用户此前要求，在公网和数据验证成功后删除本次固定目录：

- /opt/pd-rehab/backups/guided-song-20261016
- /tmp/pd-guided-song-20261016

合计删除81,036,728字节的备份与暂存文件；没有删除其他项目备份或临床数据。清理后再次确认两个服务active及公网健康接口正常。清理证据见 cleanup.json。

旧hash资源继续供已打开的页面使用，不作为备份删除。源码历史保留在Git。

## 限制

老师真实面部模型仍未提供，线上明确显示未配置；没有虚构推理结果。原生Android/iPhone验收和超过五分钟的音频合成仍按本地交付报告列为待补齐项。
