# 医院反馈PR3发布

使用项目Python3.11：`sudo /opt/pd-rehab/venv/bin/python deploy.py /opt/pd-rehab/releases/hospital-pr3-20261127`。

manifest绑定旧/新SHA和发布文件摘要。先对SQLite在线backup到服务器700目录的600副本，在候选源码上运行alembic upgrade head，逐表核对28张旧表原列、行数、数据摘要和外键；副本不离开服务器。通过后只停止目标后端，重新备份并核对当前业务数据，快进源码，运行3个加法迁移，验证旧内容完全保留及新字段默认值，然后启动并核对原4模型。最后安装两种base静态文件并原子切换入口，保留旧hash资源。

不更改ASR密钥、GLM、代理、端口、App APK或其他服务。失败恢复旧代码和静态入口并保留新增列，不执行破坏性downgrade、不覆盖数据库。备份仅在目标服务器保存。部署完成还需HTTPS鉴权、表单和真实ASR验收。
