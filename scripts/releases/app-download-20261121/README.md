# App 下载入口发布

登录页平台名称下方、登录后的侧栏，以及手机导航菜单提供 App下载。中英文界面共用同一份普通 Android 安装包，无需账号。

安装包：琴伴 0.1.73，构建号 75，包名 `com.pianoforparkinson.piano_practice`。本次不包含 Shorebird。

公开路径：`/pd-rehab/assets/app-releases/0.1.73-75/qinban-0.1.73-android-universal.apk`。

SHA-256：`88079438cc9f191a995fc438427929a0aad5ba422159f378fdb87323fde64986`。

源码只保存下载组件和发布脚本，不保存 APK 或签名私钥。后续更换安装包时同步修改组件路径，上传到新的版本目录，核验签名、包名、构建号和摘要后再发布前端。

## 发布与回滚

分别使用 `VITE_BASE=/` 和 `VITE_BASE=/pd-rehab/` 执行 `npm run build`，将两份产物以 `root/`、`under/` 打入 frontend.tar.gz。将真实 APK 以 app.apk 放在 `/opt/pd-rehab/releases/app-download-20261121`，额外使用 `git bundle create release.bundle HEAD ^4794609ad37dcc77d4421af2d7f7a3a39650b7c6` 导出本次增量源码并上传同一目录，传入包摘要及已推送 main 的提交运行 deploy.py。服务器历史 origin 指向离线临时文件，本流程不修改 origin。

脚本检查旧提交、干净工作区、资源软链接、文件摘要及路径；只添加静态文件并最后替换 HTML，保留旧 hash 资源。不改 Nginx、数据库或服务配置，不重启服务。

需要回滚时，将发布目录 backup/dist.html 和 backup/dist-under-path.html 分别恢复到对应 index.html；旧资源保留，可直接恢复。恢复源码时先核对干净状态及旧提交，不覆盖线上新修改。

## 验证

前端 `npm run test`：386 项通过。两个 base 的 `npm run build` 均通过。
后端 `python -m pytest backend/tests/test_auth.py -q`：12 项通过，仅现有依赖弃用警告。
Chrome 实测 1440、820、390 像素宽度的未登录下载入口、真实登录后侧栏/手机菜单入口，无横向溢出。实际匿名下载 102942933 字节，SHA-256 与发布包一致；下载不离开登录页。线上结果另存发布目录验收报告。
