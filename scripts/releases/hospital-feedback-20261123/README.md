# 医院反馈发布

只发布本轮医护录入、本地录音和训练点评。两种前端 base 分别构建至 root/under 并打为 frontend.tar.gz，使用 git archive 导出 backend.tar.gz，增量源码使用 release.bundle。manifest.json 指定旧新 SHA 和所有上传文件 SHA256。

部署脚本核对干净旧源码、生产数据库路径、单 worker、原模型版本、资源软链接和文件摘要。先在内存数据库与候选后端执行预检及一次真实供应商自测调用，不读取生产患者。

仅暂停目标后端，使用 SQLite backup API 在服务器受保护目录备份，快进更新源码，不运行迁移；启动并核对原4个模型就绪后安装静态文件，最后原子替换 HTML。保留旧 hash 资源、App APK、Nginx 和其他服务。

失败会恢复旧源码和入口、被覆盖的可变静态文件，只启动目标服务；不使用备份覆盖现有数据库。备份路径为本发布目录 backup，权限700，SQLite副本权限600，不复制到本机或Git。

使用 sudo python3 deploy.py /opt/pd-rehab/releases/hospital-feedback-20261123。预检和发布结果保存在对应发布目录。无患者的自测用于检查真实 GLM 连通性，不是模型效果或临床验证。
