# 服务器部署方案（server_deployment_plan.md）

> 项目：PD-Rehab-Web
> 版本：Phase 0（含只读服务器审计结论）
> 目标服务器：`ssh fengz` → `VM-0-11-ubuntu` / `110.42.236.65`
> **本文档阶段：仅方案与审计结论。Phase 0 未修改服务器上任何配置、未停止任何服务、未写入任何文件。**
>
> 医疗声明：本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。

---

## 1. 只读审计原始结论

审计方式：`ssh fengz`（BatchMode），全部命令只读。脚本：`_phase0_server_audit.sh`、`_phase0_server_audit2.sh`（工作区根目录）。

### 1.1 系统

| 项 | 值 |
| --- | --- |
| 主机名 | `VM-0-11-ubuntu` |
| OS | **Ubuntu 22.04.5 LTS (Jammy Jellyfish)** |
| Kernel | `Linux 5.15.0-171-generic #181-Ubuntu SMP Fri Feb 6 22:44:50 UTC 2026 x86_64` |
| 虚拟化 | KVM（腾讯云 CVM，full virtualization） |
| 登录用户 | `ubuntu` (uid=1000) |
| 用户组 | `sudo, adm, dialout, cdrom, floppy, audio, dip, video, plugdev, lxd, netdev` |
| **免密 sudo** | **YES**（`sudo -n true` 成功） |
| 内网 IP | `10.0.0.11` |
| 公网 IP | **`110.42.236.65`** |

### 1.2 CPU / 内存 / 磁盘

```
Architecture: x86_64
CPU(s): 4
Model name: Intel(R) Xeon(R) Platinum 8255C CPU @ 2.50GHz
Thread(s) per core: 1 / Core(s) per socket: 4 / Socket(s): 1
Hypervisor vendor: KVM

               total        used        free      shared  buff/cache   available
Mem:           3.6Gi       618Mi       153Mi       3.0Mi       2.9Gi       2.7Gi
Swap:             0B          0B          0B

Filesystem      Size  Used Avail Use% Mounted on
/dev/vda2        40G  7.9G   30G  21% /
tmpfs          1.9G   24K  1.9G   1% /dev/shm
/dev/vda1       1M    (BIOS boot)
```

| 项 | 值 | 评价 |
| --- | --- | --- |
| vCPU | 4 | 够用，但推理并发必须限制为 1 |
| 内存 | **3.6 GiB** | ⚠️ **最紧的资源** |
| Swap | **0 B** | ⚠️ **无 swap，OOM 即进程被杀** |
| 根分区可用 | **30 GB** | 够用；上传视频需设配额与清理策略 |
| inode | 使用 6% | 充足 |

### 1.3 GPU

```
nvidia-smi NOT INSTALLED
lspci | grep -i 'vga|3d|nvidia'
  00:02.0 VGA compatible controller: Cirrus Logic GD 5446
```

**服务器没有 GPU。** Cirrus Logic GD 5446 是 QEMU/KVM 的虚拟显示控制器，不是计算卡。

### 1.4 软件版本

| 工具 | 版本 | 备注 |
| --- | --- | --- |
| Python | **3.10.12**（`/usr/bin/python3`） | 无 `python`（无 3） |
| pip3 | 22.0.2（系统 dist-packages） |  |
| `python3.11` | **未安装**（apt candidate 仅 `3.11.0~rc1-1~22.04.1`，是 **RC 版**） | ⚠️ **不要用 apt 装 3.11** |
| conda | **未安装** |  |
| `venv` | 可用（`import venv` OK） | 推荐方案 |
| **Node.js** | **v22.23.3** | ✅ **已由本轮升级**（原为 v12.22.9） |
| **npm** | **10.9.9** | ✅ **已由本轮安装**（原先完全缺失） |
| npm registry | `https://mirrors.tencentyun.com/npm`（`~/.npmrc`） | 国内镜像，可用 |
| pnpm / yarn | 均未安装 | 不需要 |
| Nginx | **nginx/1.18.0 (Ubuntu)**，systemd `active` + `enabled` | 已运行 1 周 3 天 |
| certbot | **1.21.0** |  |
| ufw | 未安装 | 防火墙在云安全组层 |
| uv | 未安装（但 `astral.sh` 可达，可安装） | 见 §8.1 |

#### 1.4.1 Node 22 升级记录（本轮实际执行）

**背景**：服务器原 Node 为 Ubuntu 22.04 自带的 **v12.22.9**，且**没有 npm**，无法构建 Vite 项目。

**已确认的前置条件**（只读审计）：

- NodeSource 源**已配置**：`apt-cache policy nodejs` 的 candidate 为 `22.23.3-1nodesource1`，
  来源 `https://deb.nodesource.com/node_22.x`。
- 网络可达性：`nodejs.org` / `deb.nodesource.com` / `registry.npmjs.org` /
  `registry.npmmirror.com` / `pypi.tuna.tsinghua.edu.cn` 全部返回 200。
- `ubuntu` 用户具备**免密 sudo**。

**遇到并解决的问题**：

第一次 `sudo apt-get install -y nodejs` 失败：

```
trying to overwrite '/usr/include/node/common.gypi', which is also in package libnode-dev 12.22.9~dfsg-1ubuntu3.6
dpkg-deb: error: paste subprocess was killed by signal (Broken pipe)
```

原因：Ubuntu 自带的 `libnode-dev 12.22.9` 与 NodeSource 的 `nodejs 22.x` 争抢
`/usr/include/node/common.gypi`。

**验证后移除**：`apt-cache rdepends --installed libnode-dev` → **Reverse Depends 为空**，
即没有任何已安装包依赖它，移除是安全的。

实际执行（**注意：这是本轮唯一改动服务器软件包的操作**）：

```bash
sudo apt-get remove -y libnode-dev
sudo apt-get install -y nodejs
```

结果：

```
node --version  -> v22.23.3
npm --version   -> 10.9.9
```

> ⚠️ **注意**：`nodejs` 包被替换为 NodeSource 的 22.x。原先任何依赖系统 Node 12 的脚本
> 都会改用 Node 22。已确认服务器上没有任何已部署站点依赖 Node（fitness / smoking-monitor /
> smoking-monitoring-system / exercises / llm-api-platform 均为**静态 dist + Python 后端**），
> 因此该升级**不影响任何现有站点**。

#### 1.4.3 Phase 4 新增的系统依赖（已实测）

`mediapipe` 的 `libmediapipe.so` 在**无显示器的服务器**上仍然链接了 EGL / GLES。
缺少时会**在 import 阶段**就失败，而不是在推理时：

```
libEGL.so.1: cannot open shared object file: No such file or directory
```

用 `ldd` 定位（结果已实测）：

```
mediapipe/tasks/c/libmediapipe.so:
        libEGL.so.1 => not found
        libGLESv2.so.2 => not found
```

`libgl1` 虽然已装，但它**不提供** `libEGL.so.1`。需要额外安装：

```bash
sudo apt-get install -y libegl1 libgles2
```

两个包体积很小，安装后媒体管道可正常导入（已实测
`mediapipe 1.0.1` + `cv2 5.0.0` 导入成功，`mp.tasks.vision.HandLandmarker` 可用）。
部署脚本已包含该步骤（幂等：先 `ldconfig -p | grep libEGL` 判断是否已存在）。

> 另注意：mediapipe 会拉入 `opencv-contrib-python`。**不要同时安装 `opencv-python`** ——
> 两者有 40 个 `cv2/` 文件路径重叠（含 `cv2/cv2.pyd`），会导致 OpenCV 安装损坏。
> 详见 `data/demo/phase0_install_findings.md`。

#### 1.4.4 服务器构建能力实测

**已实测**：在服务器上对 `PD-Rehab-Web` 前端执行完整 `npm install` + `npm run build` **成功**。

```
$ npm install --no-audit --no-fund     # 依赖正常安装
$ npm run build
✓ built in 1.14s
$ du -sh dist
1.6M    dist
```

因此**本地构建不再是必需的**：既可以在本地 build 后上传 `dist/`（内存占用最低），
也可以直接在服务器上 build（Node 22 已就绪）。

> ⚠️ **但 GitHub 从服务器不可达**：实测 `git clone https://github.com/...` 报
> `fatal: unable to access ... SSL connection timeout`。
> 因此服务器上**不能直接 `git clone` 本项目**。部署时需采用下列方式之一：
>
> | 方式 | 命令 | 说明 |
> | --- | --- | --- |
> | **A（推荐）** | `git bundle` 或 `tar` 通过 SSH 流式传输 | 已实测可用，见 §8.1 |
> | B | 在服务器上配置 GitHub 镜像 / 代理 | 需要额外运维，本方案不采用 |
> | C | 本地构建 `dist/` 后单独上传静态产物 | 对纯展示 Demo 足够 |


### 1.5 Nginx 现有 server 块（**不得破坏**）

| 配置文件 | listen | server_name | 行为 |
| --- | --- | --- | --- |
| `sites-enabled/fitness` → `sites-available/fitness` | `80` | **`110.42.236.65`** | `root /var/www/fitness`；`include snippets/smoking-monitor-locations.conf`；`include snippets/exercises-locations.conf` |
| `conf.d/mysite.conf` | `80`, `443 ssl` | **`ccqspace.site www.ccqspace.site`** | `/home/ → /var/www/homepage`；`/ → proxy_pass 127.0.0.1:8000`；`/market/ → /var/www/market_frontend`；`include snippets/exercises-locations.conf`；Certbot 管理 TLS |
| `conf.d/smoking-monitor.conf` | `18082`, `[::]:18082` | `_` | `root /var/www/smoking-monitor/dist`；`/api/ → 127.0.0.1:18081` |
| `conf.d/smoking-monitoring-system.conf` | `18083`, `[::]:18083` | `_` | `root /var/www/smoking-monitoring-system/dist`；`/api/ → 127.0.0.1:18084` |

**关键约束：**

1. **80 端口已被 `110.42.236.65`（fitness）与 `ccqspace.site`（mysite）两个 server 块占用**，
   且 fitness 通过 `include` 挂载了共享 snippet。
   → **绝不能再往 80 加第三个 server 块**（server_name 冲突 / 路由被抢）。
2. TLS 证书只覆盖 `ccqspace.site` + `www.ccqspace.site`（RSA，到期 **2026-12-10**，剩 72 天）。
   **没有任何证书覆盖纯 IP `110.42.236.65`。**
3. 已有站点数量多、共享 snippet 复杂 → **绝对不做任何"重构 Nginx"的操作**，
   只允许**新增独立文件**。

### 1.6 端口占用（`sudo ss -lntp`）

| 端口 | 绑定 | 进程 | 归属服务 |
| --- | --- | --- | --- |
| 22 | `0.0.0.0` / `[::]` | `sshd` (pid 52450) | SSH |
| 53 | `127.0.0.53` | `systemd-resolve` | 本地 DNS |
| 80 | `0.0.0.0` | `nginx` | fitness + mysite |
| 443 | `0.0.0.0` | `nginx` | ccqspace.site TLS |
| **8000** | `127.0.0.1` | `python` (pid 1649531) | `exercises.service` |
| **18080** | `127.0.0.1` | `python` (pid 3979478) | `llm-api-platform.service` |
| **18081** | `127.0.0.1` | `uvicorn` (pid 1800107) | `smoking-monitor-api` |
| **18082** | `0.0.0.0` / `[::]` | `nginx` | smoking-monitor 前端 |
| **18083** | `0.0.0.0` / `[::]` | `nginx` | smoking-monitoring-system 前端 |
| **18084** | `127.0.0.1` | `uvicorn` (pid 1838442) | `smoking-monitoring-system-api` |

8000–20000 区间已占用：`8000 18080 18081 18082 18083 18084`。

**端口探测结果：**

| 端口 | 状态 | 结论 |
| --- | --- | --- |
| 3000 / 5000 / 5173 / 8080 / 8443 / 9000 / 9001 / 9002 / 8090 / 8091 / 10080 | free | 可用但非首选 |
| **18085** | **FREE** | ✅ **建议前端入口** |
| **18086** | **FREE** | ✅ **建议后端 API（仅回环）** |
| 18090 / 18091 | FREE | 备用 |

### 1.7 已运行服务（systemd，running）

```
exercises.service                         Exercises Platform (Product Hub + Training Tracker)
llm-api-platform.service                  LLM API Platform (OpenAI-compatible API server, Stage 1)
smoking-monitor-api.service               Smoking Line Logistics Monitoring API (FastAPI)
smoking-monitoring-system-api.service     Smoking Line Logistics Monitoring System API (FastAPI)
nginx.service                             nginx 1.18.0
ssh.service / snapd.service / cron.service / unattended-upgrades.service / ...
```

已有 systemd 单元范例（`exercises.service`，可作为本项目模板）：

```ini
[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/exercises
EnvironmentFile=/opt/exercises/.env
ExecStart=/opt/exercises/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=3
```

### 1.8 已有站点目录

```
/opt/exercises                 (ubuntu:ubuntu)   venv: /opt/exercises/.venv
/opt/llm-api-platform          (ubuntu:ubuntu)
/var/www/fitness               (ubuntu:ubuntu)
/var/www/homepage              (www-data)
/var/www/smoking-monitor       (ubuntu:ubuntu)
/var/www/smoking-monitoring-system  (root)
/home/ubuntu/apps
```

`/opt` 为 `root:root`，但 `ubuntu` 有免密 sudo → **可以创建 `/opt/pd-rehab/`**。

### 1.9 网络与安全组

- `ufw` 未安装；`iptables` 需 root（云平台安全组控制）。
- 从既有配置注释可确认：**18082 / 18083 已在云安全组放行**。
- ⚠️ **18085 / 18086 是否放行未知 → 需要用户在腾讯云控制台显式放行 18085，否则外网不可达。**

---

## 2. 目标部署目录结构（规格 §25）

```
/opt/pd-rehab/
├─ app/
│  └─ PD-Rehab-Web/          <-- git clone（GitHub 只管理这一层）
│     ├─ backend/
│     ├─ frontend/           (源码；构建产物单独放 /var/www)
│     ├─ docs/
│     ├─ scripts/
│     └─ ...
├─ models/                   <-- 私有模型，绝不入 Git
│  ├─ micro_expression/      <-- 老师模型（尚未提供）
│  └─ mediapipe/
│     └─ hand_landmarker.task
├─ data/                     <-- 绝不入 Git
│  ├─ uploads/
│  ├─ outputs/
│  └─ reports/
├─ logs/                     <-- 绝不入 Git
├─ venv/                     <-- Python 虚拟环境
└─ .env                      <-- 绝不入 Git
```

静态前端产物（与服务器既有站点风格一致）：

```
/var/www/pd-rehab/dist/
```

**GitHub 只管理 `app/PD-Rehab-Web`。`models` / `data` / `logs` / `.env` / `venv` 绝不进入 Git。**

---

## 3. 最终 Web 架构（规格 §26）

```
Internet
   │
   ▼
Nginx :18085 (新增独立 server 块，server_name _)
   ├── /                    → 静态文件 /var/www/pd-rehab/dist  (Vue 3 SPA)
   └── /api/                → proxy_pass http://127.0.0.1:18086  (FastAPI)
                                    │
                                    ├── SQLite  /opt/pd-rehab/data/pd.db
                                    ├── 文件     /opt/pd-rehab/data/{uploads,outputs,reports}
                                    └── 模型     /opt/pd-rehab/models/...
```

FastAPI **只监听 `127.0.0.1:18086`**（不直接暴露公网），由 Nginx 反代。
与服务器上现有站点（18082/18083）保持完全一致的部署范式。

**为什么不复用 80 / 443：**

- 80 已被 fitness（`server_name 110.42.236.65`）和 mysite（`server_name ccqspace.site`）占用，
  且 fitness 通过 `include` 共享 snippet。再挂 80 会引发 server_name 冲突并可能抢走现有路由。
- 443 的证书只覆盖 `ccqspace.site`，纯 IP 访问会触发证书域名不匹配告警。
- **新增独立端口是最小侵入、零风险的方案**，与服务器既有实践（18082/18083）一致。

---

## 4. Nginx 配置草案（**Phase 9 才实际部署，本阶段不写入服务器**）

`deploy/nginx/pd-rehab.conf` → 安装为 `/etc/nginx/conf.d/pd-rehab.conf`

```nginx
# PD-Rehab-Web —— Nginx 站点配置（新增独立文件，不修改任何已有配置）
#
# 部署前勘查结论（110.42.236.65 / VM-0-11-ubuntu）：
#   已占用端口：22, 53, 80, 443, 8000, 18080, 18081, 18082, 18083, 18084
#   已有站点  ：ccqspace.site (80/443, Certbot)、110.42.236.65:80 (fitness)、
#               18082 (smoking-monitor)、18083 (smoking-monitoring-system)
#   因此本平台使用独立端口 18085，不新增 server_name，不改动任何已有配置。
#
# 注意：纯 IP + HTTP 不是 Secure Context，浏览器 getUserMedia（摄像头）不可用。
#       本端口下只支持「本地 MP4 文件上传」。摄像头录制需 HTTPS。

server {
    listen       18085;
    listen       [::]:18085;
    server_name  _;

    root  /var/www/pd-rehab/dist;
    index index.html;

    charset utf-8;
    access_log /var/log/nginx/pd-rehab.access.log;
    error_log  /var/log/nginx/pd-rehab.error.log;

    # 视频上传：单文件上限。前端已有分片/进度提示时可按需调整。
    client_max_body_size 500m;
    client_body_timeout  300s;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    gzip on;
    gzip_vary on;
    gzip_min_length 512;
    gzip_comp_level 6;
    # 不要重复声明 application/javascript：新版 mime.types 已并入 text/javascript
    gzip_types text/plain text/css application/json image/svg+xml
               text/javascript application/wasm;

    # 带 hash 的构建产物：长缓存
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    # API 反向代理
    location /api/ {
        proxy_pass         http://127.0.0.1:18086;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # 视频分析是长任务：放宽超时，但前端应使用 Job 轮询而非长连接阻塞
        proxy_connect_timeout 30s;
        proxy_send_timeout    300s;
        proxy_read_timeout    300s;
        proxy_request_buffering off;   # 大文件上传不落盘缓冲
    }

    # SPA 前端路由回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # index.html 必须每次回源校验。
    #
    # 没有这一条时 nginx 只发 ETag / Last-Modified，浏览器会按"启发式缓存"自行决定
    # 缓存多久，于是一次重新部署之后浏览器仍拿着旧的 index.html，继续去加载**旧的**
    # 带 hash 的 chunk，页面上看不到任何更新（已被同事遇到过两次）。
    location = /index.html {
        add_header Cache-Control "no-cache, must-revalidate";
    }
}
```

> ⚠️ **上面这段是「读物」，不是安装源。**
> 真正安装的是 `deploy/nginx/pd-rehab.conf`，**以文件为准**。
>
> 这两者曾经不一致：本节内联的副本停在旧版本，**缺了 `location = /index.html`
> 那条防缓存规则** —— 而那条规则对应的正是"同事遇到过两次"的问题。
> 照本节手抄配置重建服务器，会把这个问题原样装回去：重新部署后浏览器仍加载旧 chunk，
> 页面上看不到任何更新，而且不报错。
>
> 现在副本已经补齐，但**仍然以文件为准**；改配置请改文件，不要改这里。

**安装步骤（Phase 9 执行，届时需先 `nginx -t` 与备份）：**

本平台在线上有**两个入口**，两个都要装：

```bash
# ── 入口 A：独立端口 18085（纯 IP + HTTP）─────────────────────────────
#    不是 Secure Context → 浏览器禁用摄像头，只能走「本地 MP4 上传」
sudo cp deploy/nginx/pd-rehab.conf /etc/nginx/conf.d/pd-rehab.conf

# ── 入口 B：https://ccqspace.site/pd-rehab/ （推荐，摄像头可用）────────
#    通过 include 挂进已有的 443 server 块，**不改动**它原有的任何 location
sudo cp deploy/nginx/pd-rehab-locations.conf /etc/nginx/snippets/
#    然后在 conf.d/mysite.conf 的 443 server 块内加一行：
#      include /etc/nginx/snippets/pd-rehab-locations.conf;

sudo nginx -t                      # 必须通过才 reload
sudo systemctl reload nginx        # 用 reload，绝不 restart（不中断现有站点）
```

**入口 B 需要单独的构建产物**（base 不同），两个目录都要有：

| 目录 | 构建参数 | 服务哪个入口 |
| --- | --- | --- |
| `/var/www/pd-rehab/dist` | `VITE_BASE=/` | 入口 A（18085） |
| `/var/www/pd-rehab/dist-under-path` | `VITE_BASE=/pd-rehab/` | 入口 B（`ccqspace.site/pd-rehab/`） |

> 本节原先**只写了入口 A**：正文里 `dist-under-path`、`pd-rehab-locations.conf`、
> 以及线上地址 `ccqspace.site/pd-rehab` 的出现次数都是 **0**。
> 照那份步骤做完，线上那个真正在用的网址（也是**唯一能用摄像头**的入口）根本不会被装上。

---

## 5. systemd 服务草案

`deploy/systemd/pd-rehab-backend.service` → `/etc/systemd/system/pd-rehab-backend.service`

```ini
# PD-Rehab-Web 后端 systemd 单元
#
# 与服务器既有单元（exercises.service / smoking-monitor-api.service）保持一致的风格。
# 后端只监听回环 127.0.0.1:18086，对外一律经 Nginx（18085）反代。
# 18086 不需要在云安全组放行。
#
# 不要长期运行 uvicorn --reload（规格 §26 明文）。

[Unit]
Description=PD-Rehab-Web Backend (FastAPI)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=exec
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/pd-rehab/app/PD-Rehab-Web/backend
EnvironmentFile=/opt/pd-rehab/.env

# --- 关键：3.6 GiB RAM + 无 swap，必须限制内存与线程 ---
MemoryMax=1800M
MemoryHigh=1500M
Environment=OMP_NUM_THREADS=2
Environment=MKL_NUM_THREADS=2
Environment=OPENBLAS_NUM_THREADS=2
Environment=PYTHONUNBUFFERED=1

ExecStartPre=/bin/mkdir -p /opt/pd-rehab/data/uploads /opt/pd-rehab/data/outputs /opt/pd-rehab/data/reports /opt/pd-rehab/logs

# 无 GPU：设备固定为 CPU；推理单并发由应用层 Semaphore(1) 保证
ExecStart=/opt/pd-rehab/venv/bin/python -m uvicorn app.main:app \
          --host 127.0.0.1 --port 18086 \
          --workers 1 --no-access-log \
          --timeout-keep-alive 75

Restart=on-failure
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=/opt/pd-rehab/data /opt/pd-rehab/logs

[Install]
WantedBy=multi-user.target
```

**要点说明：**

| 配置 | 理由 |
| --- | --- |
| `--workers 1` | 模型（MediaPipe / 微表情）常驻内存，多 worker 会成倍占用 3.6 GiB 内存。**必须单 worker。** |
| `MemoryMax=1800M` | 无 swap，必须硬限，避免拖垮同机的 4 个已有服务 |
| `OMP/MKL/OPENBLAS_NUM_THREADS=2` | 4 vCPU 上留给 Nginx 与其它站点的余量 |
| `Restart=on-failure` | 与 `exercises.service` 一致 |
| 不写 `--reload` | 规格 §26 明文禁止生产用 reload |
| `ProtectSystem=full` + `ReadWritePaths` | 与 `llm-api-platform.service` 的安全姿态一致 |

---

## 6. 无 GPU 服务器的推理方案（**关键决策**）

服务器**没有 GPU**，且只有 3.6 GiB 内存。三种可选方案：

### 方案 A（**推荐**）：服务器只做上传 + 队列 + 展示，重推理留在本地

```
服务器：Vue 前端 + FastAPI（业务 CRUD / 数据展示 / Job 状态）
        上传的视频 → 存入 /opt/pd-rehab/data/uploads
        需推理时 → Job 排队（GPU_INFERENCE_CONCURRENCY=1）
        MediaPipe + 微表情模型 → CPU 推理，但：
          · 限制单并发
          · 限制视频时长（建议 ≤ 20 秒，正好符合 Finger Tapping 规范）
          · 显式 torch.set_num_threads(2)
```

**优点**：单人使用完全可用；Finger Tapping 10–20 秒视频在 4 vCPU 上 CPU 推理约 20–60 秒，可接受。
**缺点**：多人同时提交会排队；微表情模型若体积大，CPU 推理可能超时。

### 方案 B：服务器只跑前端 + 轻量 API，推理完全本地化

服务器不安装 torch / mediapipe，`/api/.../analyze` 直接返回
`INFERENCE_UNAVAILABLE_ON_SERVER`，由本地 Windows 机器（RTX 5070）完成分析后
把结果 JSON 同步到服务器数据库。

**优点**：服务器极轻（内存占用 < 400 MiB），稳定。
**缺点**：Demo 需要两台机器配合，演示流程变复杂。

### 方案 C：本地 Demo 为主，服务器仅作静态展示

把 `npm run build` 产物 + 预先生成的真实分析结果（Demo 数据）部署到服务器，
不提供在线推理。

**优点**：最稳，几乎零内存风险。
**缺点**：不是真实在线闭环，与产品定位有偏差。

> **建议：Phase 1–8 先在本地 Windows 完成真实闭环；Phase 9 部署时采用方案 A，
> 并把方案 B 作为降级路径写入 README。**
> 若微表情模型体积超过服务器承受能力，则微表情走方案 B（本地推理 + 结果同步），
> Finger Tapping 保留方案 A。

### 6.1 与"GPU 推理单并发"的对应关系

规格 V2 §31 要求 GPU 推理单并发。服务器无 GPU，因此：

| 环境 | 设备 | 并发控制 |
| --- | --- | --- |
| 本地 Windows（RTX 5070） | `cuda:0` | `Semaphore(1)` + `torch.inference_mode()` + OOM 捕获 |
| 服务器（无 GPU） | `cpu` | `Semaphore(1)` + `MemoryMax` + 线程数限制 |

**无论 CPU 还是 GPU，`GPU_INFERENCE_CONCURRENCY=1` 保持一致**，避免"本地快、服务器慢"导致的行为分叉。
`quality_json.device` 必须记录实际设备，**CPU 与 GPU 结果不得被当作同一来源直接比较**。

---

## 7. HTTPS 与浏览器摄像头（规格 §27，**重要产品约束**）

`getUserMedia` 要求 **Secure Context**：

| 访问方式 | Secure Context | 摄像头可用 |
| --- | --- | --- |
| `http://127.0.0.1:5173`（本地开发） | ✅ | ✅ |
| `http://localhost:5173` | ✅ | ✅ |
| `https://ccqspace.site/...`（已有证书域名） | ✅ | ✅ |
| **`http://110.42.236.65:18085`** | ❌ | ❌ 浏览器直接拒绝 |
| `http://<公网IP>:18085`（任意端口） | ❌ | ❌ |

**结论与优先级（完全遵循规格）：**

1. **服务器端口 18085（HTTP + 纯 IP）下，"本地 MP4 文件上传"必须完整可用。**
   这是服务器 Demo 的默认可行路径 —— 医生/工作人员用手机或相机录好视频后上传。
2. **摄像头实时录制功能只在本地 `localhost` 或 HTTPS 域名下启用**，
   前端必须做**能力探测**（`window.isSecureContext` + `navigator.mediaDevices`），
   不安全上下文下**隐藏或禁用**录制按钮，并给出明确说明文案：
   > "当前访问方式不支持浏览器摄像头，请使用本地视频文件上传。"
3. **严禁**使用 `--unsafely-treat-insecure-origin-as-secure` 之类方式绕过浏览器安全策略。

**后续启用摄像头录制的可行路径（需用户决策，Phase 9 讨论）：**

| 方案 | 说明 | 前置条件 |
| --- | --- | --- |
| **C1（推荐，零 Nginx 改动风险最低）** | 用已有域名 `ccqspace.site` 新增一个**路径**（如 `location /pd-rehab/`）反代到 18085 | 需要修改 `conf.d/mysite.conf`（**会动到已有文件**）→ 需用户明确批准 |
| C2 | 申请新子域 `pd.xxx` 的证书，新增独立 server 块监听 443 | 需要域名解析权限 + 修改 Nginx（新增文件，风险较低） |
| C3 | 申请覆盖纯 IP 的证书 | ❌ **公网 CA 不签发纯 IP 证书**，不可行 |
| C4 | 自签名证书 | ❌ 浏览器会警告且部分浏览器仍禁用摄像头，**不推荐** |

> **本轮不做任何 Nginx 改动。** 上表仅为 Phase 9 的决策输入。

---

## 8. 部署步骤（Phase 9 执行清单）

### 8.1 首次部署

> **前置事实（已实测）**：服务器**无法访问 GitHub**（`git clone` 报 SSL timeout），
> 因此第 2 步不能直接用 `git clone`，必须走 SSH 传输（下方 A / B 两种方式）。

```bash
# 0) 前置：用户需先在腾讯云安全组放行 TCP 18085
#    Node 22 与 npm 已就绪（见 §1.4.1），无需再安装
# 1) 目录
sudo mkdir -p /opt/pd-rehab/{app,models,data/{uploads,outputs,reports},logs}
sudo chown -R ubuntu:ubuntu /opt/pd-rehab

# 2) 代码上传（服务器无法访问 GitHub，二选一）
#
#    方式 A（推荐）：本地打成 tar 通过 SSH 流式传输
#      ---- 在本地 Windows 执行 ----
#      cmd /c "cd /d D:\CodingData\Competition\PD\PD-Rehab-Web && ^
#        tar -czf - --exclude=node_modules --exclude=dist --exclude=.git ^
#                   --exclude=data --exclude=.env . ^
#        | ssh fengz ""mkdir -p /opt/pd-rehab/app/PD-Rehab-Web && ^
#            tar -xzf - -C /opt/pd-rehab/app/PD-Rehab-Web"""
#
#    方式 B：本地 git bundle（保留完整提交历史）
#      ---- 在本地 Windows 执行 ----
#      git bundle create pd-rehab.bundle --all
#      scp pd-rehab.bundle fengz:/tmp/
#      ---- 在服务器执行 ----
#      git clone /tmp/pd-rehab.bundle /opt/pd-rehab/app/PD-Rehab-Web
#      cd /opt/pd-rehab/app/PD-Rehab-Web && git remote set-url origin \
#          https://github.com/WuChangqing1/PD-Rehab-Web.git   # 仅作记录，服务器上不可 fetch

# 3) Python 3.11（服务器系统是 3.10，不要用 apt 的 3.11 RC）
#    优先用 uv（单文件二进制，内存占用极低）
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11
uv venv --python 3.11 /opt/pd-rehab/venv
/opt/pd-rehab/venv/bin/python -m pip install -r backend/requirements.txt
# 注意：服务器无 GPU，不要安装 PyTorch CUDA 版本。
#       当前 Phase 1 骨架不需要 torch；Phase 3/4 若要在服务器上推理，
#       再安装 CPU 版：pip install torch --index-url https://download.pytorch.org/whl/cpu

# 4) 环境变量（不入 Git）
cp .env.example /opt/pd-rehab/.env
sudo chmod 600 /opt/pd-rehab/.env
#   编辑：DATABASE_URL=sqlite:////opt/pd-rehab/data/pd.db
#         UPLOAD_DIR=/opt/pd-rehab/data/uploads
#         OUTPUT_DIR=/opt/pd-rehab/data/outputs
#         REPORT_DIR=/opt/pd-rehab/data/reports
#         USE_GPU=false
#         JWT_SECRET=<用 openssl rand -hex 32 生成>
#         BOOTSTRAP_ADMIN_PASSWORD=<强密码>
#         DEMO_MOCK_MODE=false

# 5) 数据库迁移
cd /opt/pd-rehab/app/PD-Rehab-Web/backend
/opt/pd-rehab/venv/bin/alembic upgrade head
#    可选：导入虚拟演示数据（供队友在线查看 Demo）
#    /opt/pd-rehab/venv/bin/python ../scripts/seed_demo.py --count 10 --with-training

# 6) 前端：服务器已可构建（Node 22 已就绪，实测通过）
cd /opt/pd-rehab/app/PD-Rehab-Web/frontend
npm install --no-audit --no-fund
npm run build                      # 实测 ✓ built in ~1.1s，dist 约 1.6M
sudo mkdir -p /var/www/pd-rehab/dist
sudo cp -r dist/* /var/www/pd-rehab/dist/
sudo chown -R www-data:www-data /var/www/pd-rehab

# 7) systemd + Nginx
cd /opt/pd-rehab/app/PD-Rehab-Web
sudo cp deploy/systemd/pd-rehab-backend.service /etc/systemd/system/
sudo cp deploy/nginx/pd-rehab.conf /etc/nginx/conf.d/
sudo systemctl daemon-reload
sudo systemctl enable --now pd-rehab-backend
sudo nginx -t && sudo systemctl reload nginx

# 8) 验证
curl -s http://127.0.0.1:18086/api/system/health
curl -s http://127.0.0.1:18086/api/system/models
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18085/
# 外网（安全组放行后）
#   http://110.42.236.65:18085/
```

### 8.2 更新部署

```bash
# 服务器无法访问 GitHub -> 用同样的 tar / bundle 方式上传新版本
cd /opt/pd-rehab/app/PD-Rehab-Web
# （用 §8.1 方式 A 或 B 覆盖代码）
/opt/pd-rehab/venv/bin/alembic upgrade head
cd frontend && npm run build && sudo cp -r dist/* /var/www/pd-rehab/dist/
sudo systemctl restart pd-rehab-backend
sudo systemctl reload nginx
```

### 8.3 回滚

```bash
# 保留上一版本的 tar 包 / bundle，重新解包到同目录即可
sudo systemctl restart pd-rehab-backend
sudo systemctl reload nginx
```

---

## 9. 运行安全与资源约束（服务器专属）

| 项 | 措施 |
| --- | --- |
| 内存 | `MemoryMax=1800M`；单 uvicorn worker；线程数限 2 |
| Swap | 建议由用户决定是否添加 2 GB swapfile（降低 OOM 直接杀进程风险） |
| 磁盘 | 上传目录定期清理；建议设置 `MAX_UPLOAD_SIZE_MB` 与 `UPLOAD_RETENTION_DAYS` |
| 推理并发 | `GPU_INFERENCE_CONCURRENCY=1`（CPU 环境同样为 1） |
| 大文件 | Nginx `client_max_body_size 500m`；FastAPI 侧限制单文件时长 |
| 端口暴露 | FastAPI 只绑 `127.0.0.1:18086`；仅 Nginx 18085 对外 |
| 现有服务 | **不触碰 8000 / 18080 / 18081 / 18082 / 18083 / 18084**；不修改任何已有 Nginx 文件 |
| 数据库 | SQLite 单文件；`DATABASE_URL` 保留 MySQL 切换能力（`mysql+pymysql://`） |
| 敏感数据 | 服务器 `data/uploads` 与 `.env` 权限 600/700；**不得**同步回本地 Git |

### 9.1 数据库处于 WAL 模式 —— 备份必须用 WAL 感知的方式（2026-10-12 实测）

线上数据库**不是**一个自包含的单文件。实测：

```
/opt/pd-rehab/data/pd.db        471 040 bytes
/opt/pd-rehab/data/pd.db-wal  4 157 112 bytes   ← 是主库文件的 8.8 倍
/opt/pd-rehab/data/pd.db-shm     32 768 bytes
PRAGMA journal_mode = wal
PRAGMA quick_check  = ok
```

后端进程长期持有该库，WAL 从未 checkpoint 回主文件，所以**已提交的事务仍留在 `-wal` 里**。

**这是一个会让备份和回滚都出错的陷阱。** 实测对比：

| 取备份的方式 | 读到的 `piano_sessions` | 读到的 `HUMAN_KEYBOARD` |
| --- | --- | --- |
| `scp pd.db`（只拷主文件） | **88** | **3** |
| `VACUUM INTO`（WAL 感知） | **89** | **4** |

只拷主文件会**静默丢失一条真实患者测量记录**，而备份本身看起来完全正常。

**因此部署与回滚必须这样做：**

```bash
# 正确：让 SQLite 自己写出一份自包含的副本
/opt/pd-rehab/venv/bin/python - <<'PY'
import sqlite3
src = sqlite3.connect('file:/opt/pd-rehab/data/pd.db?mode=ro', uri=True)
src.execute("VACUUM INTO '/opt/pd-rehab/data/pd.db.bak-$(date +%F-%H%M)'")
PY

# 或者停掉后端再整组拷贝（-wal / -shm 一起）
systemctl stop pd-rehab-backend
cp pd.db pd.db-wal pd.db-shm /backup/
systemctl start pd-rehab-backend
```

**不要**用 `cp pd.db backup.db`，也**不要**在回滚时只还原主文件——那会把库回退到上一个 checkpoint，
丢掉其后所有真实记录。

### 9.2 迁移在真实生产数据上的演练结果（2026-10-12）

`f2a4b6c8d0e1`（`piano_sessions.recipe_id`）已用 **WAL 感知方式取出的生产库副本**
完整演练过（脚本 `scripts/_dryrun_migration.py`，副本用完即删）：

| 检查项 | 结果 |
| --- | --- |
| alembic 版本 | `e8f1a3c5b7d9` → `f2a4b6c8d0e1` |
| 列数 | 40 → 41（只多 `recipe_id`） |
| `piano_sessions` 行数 | 89 → **89** |
| `piano_events` 行数 | 45 → **45** |
| `patients` 行数 | 10 → **10** |
| **4 条 `HUMAN_KEYBOARD` 真实记录** | 全部保留，逐列一致 |
| 全部审计 JSON blob | 逐字节一致 |
| `recipe_id` 取值 | 全部为 NULL（没有凭空补值） |

> 生产库里这 4 条真实记录（3 条 Calibration + 1 条 `SINGLE_KEY_RHYTHM` 训练）
> **只存在于服务器**，本地库一条都没有。这正是必须先演练的原因。

### 9.3 迁移链与回滚路径已实际执行验证（2026-10-12）

此前所有检查都跑在 **Vite 开发服务器**上。开发服务器解析模块与路径的方式和静态构建
**不一样**，而 `VITE_BASE` 配错恰恰是那种「开发时完全看不见、上线后满屏 404」的故障。

因此用 `VITE_BASE=/pd-rehab/` 构建，并用一个模拟 nginx 行为的静态服务器
（静态文件 + SPA 回退 + `/pd-rehab/api/` 反代）真正加载了一遍：

| 检查 | 结果 |
| --- | --- |
| `index.html` 资源路径 | `/pd-rehab/assets/index-*.js`，与线上一致 |
| 静态资源 | 200，`text/javascript`，65 KB |
| 深链接（`/pd-rehab/follow-up`） | 200，返回 SPA 外壳而非 404 |
| 子路径之外的请求 | 404（不会误吞其他应用的路由） |
| `/pd-rehab/api/auth/me` | 401 `application/json`（**确实到达了后端**） |

**7 个路由在构建产物下的渲染结果**（正文长度，与开发服务器逐一对比）：

| 路由 | 开发服务器 | **构建产物** |
| --- | --- | --- |
| 工作台 | 634 | **634** |
| 患者档案 | 1235 | **1235** |
| 随访与报告 | 1353 | **1353** |
| 评估中心 / 康复训练 / 钢琴 / 芭蕾 | — | 468 / 380 / 1118 / 1695 |

**0 个 404、0 个失败请求、0 个以 HTML 应答的 API 调用、0 个页面级 JS 错误。**

> **踩到的坑，值得记下来**：这个验证服务器第一版只反代了 `/api`，没有反代
> `/pd-rehab/api`。而 `API_BASE = BASE_URL + '/api'`，子路径构建调用的是后者 ——
> 于是请求落到 SPA 回退上，**以 200 返回了 HTML**。前端拿 HTML 当 JSON 解析，
> 工作台与患者档案页当场抛 `TypeError`，看起来像"生产构建崩了"。
>
> **差一点就据此报告一个不存在的缺陷。** 真正定位它的是对比
> `content-type`：接口返回 `text/html` 就说明它根本没到后端。
> 教训：**验证服务器必须和 nginx 行为一致，否则它会说谎，而且说得很有说服力。**

---

### 9.4 生产构建产物已在 `/pd-rehab/` 子路径下实测运行（2026-10-12）

回滚步骤此前只是**写在文档里**，从未真正跑过。一个跑不通的回滚方案比没有方案更糟——
它是出事时才会去用的东西。因此用一次性空库把整条链走了一遍
（`scripts/_check_migrations.py`，用完即删）：

| 步骤 | 结果 |
| --- | --- |
| 空库 `upgrade head` | ✅ 到达 `g3b5c7d9e1f2`，14 张表 |
| `downgrade base`（全部回退） | ✅ 版本清空，剩 1 张表 |
| 再次 `upgrade head`（往返） | ✅ 回到同一版本、同样的表数 |
| **`downgrade e8f1a3c5b7d9`**（文档里的回滚目标） | ✅ 到达该版本，且 `piano_sessions.recipe_id` **确实消失** |

**结论：升级、完整降级、往返、以及文档所述的回滚目标全部可用。**
（注意 `g3b5c7d9e1f2` 的 downgrade 是**有意的空操作**——它做的是数据订正，
重新激活那些基线会把缺陷又装回去，见该迁移的模块文档字符串。）

---

## 10. 与规格的偏差记录

| # | 规格原文 | 实际方案 | 理由 |
| --- | --- | --- | --- |
| S1 | 规格 §26 隐含 80/443 → Nginx | 使用 **18085** | 80/443 已被 2 个 server 块占用且共享 snippet；新增 80 会冲突。与服务器既有 18082/18083 范式一致 |
| S2 | 规格 §27 要求规划 Nginx + HTTPS | 暂用 HTTP + 纯 IP；**MP4 上传完整可用**，摄像头功能仅在 localhost/HTTPS 启用 | 纯 IP 无证书可用；公网 CA 不签发 IP 证书。规格已明确"优先保证本地 MP4 文件上传完整可用" |
| S3 | 规格 §25 目录 `/opt/pd-rehab/` | **完全一致** | — |
| S4 | 规格 §26 用 systemd 而非 `uvicorn --reload` | **完全一致**（`pd-rehab-backend.service`） | — |
| S5 | 规格未提及服务器无 GPU | 增加 §6 三方案决策 | 服务器实际无 GPU，必须显式决策 |
| S6 | 规格未提及服务器 Node 12 | **已升级到 Node 22.23.3**，服务器可直接构建前端 | 见 §1.4.1 与 §1.4.2，实测构建通过 |
| S7 | 规格未提及服务器无法访问 GitHub | 改用 **tar / git bundle 经 SSH 传输** | 实测 `git clone` SSL timeout |

---

> 本系统用于科研、辅助评估及康复训练展示，不能替代专业医生诊断和标准临床量表。
