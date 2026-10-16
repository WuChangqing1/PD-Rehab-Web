# 曲目跟弹：键盘字母与示范试弹修复

应用代码提交：`9dd0df62469b779541603c2a2b9c7e35f6cd5fd3`，已推送 GitHub main 并发布到 https://ccqspace.site/pd-rehab/ 。后续截图与本文的审计提交不改变运行代码。

## 修改内容

按照用户最新反馈，修订初版“琴键正面无文字”的约束。七个琴键始终显示 A、S、D、F、G、H、J；可访问名称包含音名与对应电脑按键。字母与键盘输入使用同一份映射，示范和正式练习均显示“按 X 键，或点击发光琴键”。

示范阶段开放键盘、鼠标及触屏试弹，有琴声和按下反馈，标明“不计成绩”。试弹不生成 DOWN/UP 原始事件，不改变示范时间线、进度、错误次数或最后合成的演奏音频。进入正式练习、暂停或结束时释放试弹按键，避免粘键和把示范按键误计入成绩。正式练习保留错误颜色与文字反馈。

患者选择、3 秒倒计时、正式训练状态机、后端算法及数据库结构保持既有流程。

## 验证

- `npm run test`：246 项通过，0 失败。新增 3 项控制器回归测试，分别覆盖示范输入隔离、示范结束时释放按键、暂停与恢复。
- `npm run build`：通过；`npx vite build --base=/pd-rehab/ --outDir dist-under-path`：通过。
- `pytest tests/test_guided_song.py tests/test_guided_song_deployment.py -q`：11 项通过。存在既有 Starlette httpx 弃用提示及受限环境 pytest 缓存写入提示，无测试失败；本次未修改后端源码。
- 真实 Chrome 与独立内存数据库跑通两段共 32 音。示范中额外按键和触屏试弹后，最终只有正式练习的 33 次 DOWN（32 次正确与 1 次故意错误）；完成率 100%，错误计数 1，演奏 WAV 正常生成。取消选择患者、取消倒计时均未创建会话。
- PC 1440×1000、平板 820×1180、手机 390×844、横屏手机 844×390：字母可见、七键对齐、无横向溢出，页面异常 0。属于桌面浏览器视口及触摸模拟验收，未声称已在原生手机硬件验收。

本地全流程证据：[browser-results.json](../artifacts/guided-song-key-hints/browser-results.json)。

## 上线验证与清理

使用 ssh fengz 向服务器 fast-forward 发布；296 个静态文件逐一 SHA256 校验通过，两套线上入口与各自构建完全一致。静态文件权限为目录 755、文件 644，保留旧 hash 资源供已打开的页面继续使用。本次无需重启后端、修改 Nginx 或迁移数据库。

公网只读验证：主要页面均 200，健康接口正常，未认证训练接口 401、已认证历史接口 200、音源 Range 206。WSS 握手到达后端，无效凭证按预期返回 4403。PC、平板、手机页面无运行异常。只读验证禁止非 GET API 请求，生产训练写入 0。

另外使用实际发布的 HTTPS 前端，将全部 API 请求拦截并转向本地独立验收数据库，复验示范阶段键盘与触屏输入。四个视口下字母均正常，试弹后进度仍为 0/32；未向生产数据库写入训练记录。复验脚本：[guided_song_live_demo_verify.mjs](../scripts/guided_song_live_demo_verify.mjs)。

验证成功后删除本次固定目录 `/opt/pd-rehab/backups/key-hints-20261016` 与 `/tmp/pd-key-hints-20261016`，共释放 79,623,326 字节。未删除其他项目文件。清理后后端与 Nginx 均 active，公网健康接口正常。

证据：[线上只读验证](../artifacts/guided-song-key-hints-production/verification.json)、[公网前端示范复验](../artifacts/guided-song-key-hints-production/live-demo-verification.json)、[静态文件校验](../artifacts/guided-song-key-hints-production/release-assets.json)、[清理结果](../artifacts/guided-song-key-hints-production/cleanup.json)。

## 效果截图

- [PC 示范界面](../artifacts/guided-song-key-hints-production/live-demo-pc.png)
- [平板示范界面](../artifacts/guided-song-key-hints-production/live-demo-tablet.png)
- [手机示范界面](../artifacts/guided-song-key-hints-production/live-demo-mobile.png)
- [手机横屏示范界面](../artifacts/guided-song-key-hints-production/live-demo-mobile-landscape.png)
- [本地完整练习结果](../artifacts/guided-song-key-hints/pc-result.png)

本次功能修复无待完成项；真实面部模型未配置、原生手机硬件验收等既有边界仍见上一轮交付记录。
