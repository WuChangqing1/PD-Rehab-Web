# 实时语音输入发布

仅发布Web流式ASR、专用密钥配置和本项目WebSocket路由，不迁移数据库，不更换GLM、既有模型或APK。

上传清单：源码bundle、候选backend/deploy归档、双base前端归档、预检脚本与合成普通话音频。manifest逐一记录SHA256。密钥不进归档、manifest或Git，单独通过SSH标准输入加密传输，服务器运行配置0600归ubuntu。

`sudo /opt/pd-rehab/venv/bin/python deploy.py /opt/pd-rehab/releases/asr-api-20261123` 会验证预期旧SHA、干净工作区、单worker、4个模型、APK摘要与其他服务PID；在候选源码和内存数据库环境中实际调用ASR合成语音与GLM。通过后追加本项目两个精确代理路径，nginx -t，暂停目标后端、在线backup API备份SQLite、快进源码、安装专用systemd drop-in并启动。静态资源先安装再原子切换HTML，最后平滑reload Nginx。

失败自动恢复旧源码、入口、被覆盖资源、项目代理和专用配置，只启动目标后端。数据库不做覆盖恢复，不删除上线后的业务写入。依赖复用现有websockets17.1。

上线验收需实际HTTPS网页的普通话合成音频转写、取消/停止/离开释放、英文/移动布局和未登录拒绝；方言及真实患者声音仍需现场实测。脚本只读现有账号元数据，不创建生产患者或训练数据。

发布证据在服务器deployment-result.json，回滚文件在backup（700）。密钥和数据库副本不下载到本机，不提交Git。
