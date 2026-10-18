# 缺陷单 01 完整交付报告

范围：PDF 1～20 项及档案数据安全附加要求。基线 `4823889`，分支 `main`。页面截图与交互仅使用隔离内存数据库中的虚拟患者，未把真实患者身份或缺陷 PDF 截图提交到仓库。

## 逐项验收

| 项 | 状态 | 实际修改文件（相对项目根目录） | 验收证据 |
|---|---|---|---|
|1|完成|frontend/src/layouts/MainLayout.vue|桌面底部折叠，手机菜单保留，状态 ARIA|
|2|完成|frontend/src/components/NavigationIcon.vue、layouts/MainLayout.vue|五个同形线框/填充图标；背景与键盘焦点保留|
|3|完成|frontend/src/styles/main.css|表头/表单/患者值 14px，手机输入 16px|
|4|完成|frontend/src/pages/PatientsPage.vue、styles/main.css|40px 控件，12px 间距；七种尺寸截图|
|5|完成|frontend/src/components/OptionalValue.vue、PatientCard.vue、pages/PatientsPage.vue、PatientDetailPage.vue、utils/format.ts|普通缺值灰色 —；0/false、姓名/性别/用药语义测试|
|6|完成|frontend/src/pages/PatientsPage.vue、styles/main.css|原 110px cell 内容宽 125px 被 ellipsis 裁剪；现 126px 宽/scrollWidth 均 126px|
|7|完成|frontend/src/utils/format.ts、pages/PatientFormPage.vue、PatientsPage.vue|统一开期 (ON)、关期 (OFF)|
|8|完成|frontend/src/pages/PatientFormPage.vue|顶部标签，统一壳高度，长文本独立布局|
|9|完成|frontend/src/pages/PatientFormPage.vue|取消编辑/保存编辑等宽，手机底部固定可达|
|10|完成|frontend/src/pages/PatientFormPage.vue、patients/editState.ts、api/index.ts|校验→无修改检测→确认→最小 PATCH；取消不写入、失败保留、重复提交守卫|
|11|完成|frontend/src/pages/PatientFormPage.vue、router/index.ts|页面、顶栏及浏览器标题统一编辑患者档案|
|12|完成|frontend/src/pages/PatientFormPage.vue|左上取消/底部取消；未保存离开保护及 beforeunload|
|13|完成，独立提交|backend/app/db/models/patient_number.py、models/__init__.py、schemas/patient.py、services/patient_service.py、alembic/versions/i5d7e9f1a3b4_patient_number_allocation.py；frontend/src/pages/PatientFormPage.vue、utils/format.ts|`1b305d2`；24 个并发创建、旧编号碰撞、删除不重用、迁移保留 UUID/外键；异常重试另提交 `620255f`|
|14|完成|frontend/src/pages/PatientFormPage.vue、patients/editState.ts|新增男/女/未知；已有 OTHER 回填保留；浏览器验证|
|15|完成|frontend/src/styles/main.css|完整外壳焦点，内部无双框；输入/选择/日期/数字/文本域统一规则|
|16|完成|frontend/src/styles/main.css|Select padding 6px、行高 36px；日期弹层保留原布局|
|17|完成|frontend/src/pages/PatientDetailPage.vue|基本信息、医疗资料、最近活动、近期评估四卡独立且全宽|
|18|完成|frontend/src/pages/PatientDetailPage.vue|两卡右侧展开/收起，ARIA 与 v-show；无重复获取|
|19|完成|frontend/src/pages/PatientDetailPage.vue|基本信息标题统一|
|20|完成|frontend/src/pages/PatientDetailPage.vue|PC 两表同内容宽度；手机记录卡，无页面级横向溢出|

## 额外修复与数据保护

- 初始化并回填末次用药时间；UTC 2026-10-17 01:30 回填北京时间 09:30，未修改不提交，修改时转 UTC，清空为 null。
- 编辑只传变化字段；0/false 不当空值，历史 OTHER 不静默覆盖；加载失败禁止保存，网络失败保留编辑。
- SQLite 下使用原子 `UPDATE ... WHERE updated_at=expected` 检测并发版本，返回 409 后要求刷新。旧客户端不传版本仍兼容。
- 已删除患者在手机卡片中只有恢复按钮，接真实 restore API；恢复后才显示查看/编辑。
- 修复 Tooltip 覆盖折叠按钮 aria-expanded；详情切换患者增加请求代次守卫。
- 新增编号使用独立永久预留表的原生自增，唯一约束兜底，只有确认编号冲突才重试。保留全部原编号与完整前缀、UUID、外键；不读取或改写医疗字段。详见 [编号机制与迁移回滚](../patient_number_allocation.md)。

## 测试与复核

- `cd frontend; npm run test`：283 passed，0 failed。
- `cd frontend; npm run build`：TypeScript 与根路径构建成功。
- `cd frontend; $env:VITE_BASE='/pd-rehab/'; npm run build -- --outDir dist-under-path`：子路径构建成功。
- `cd backend; python -m pytest -o addopts= -q -p no:cacheprovider --basetemp ../_deploy/defect01-qa/release-final-backend`：469 passed，1 skipped；退出码 0。跳过为可选 Torch 条件测试；保留原有 httpx 弃用与极端值 numpy 溢出警告。
- 单独编号/编辑 API：23 项通过；新增非编号 IntegrityError 回归先复现失败，再修复通过。编号 8 线程/24 创建使用文件 SQLite 多连接，非进程锁。
- 编辑控制器旧基线运行 4 failed/1 passed；当前 5 passed。覆盖无变化、取消确认、最小请求/重复点击、失败保留、加载失败保护。
- 独立只读整轮代码复核：当前 SQLite 发布无阻断项；MySQL 边界见下节。

## 浏览器与截图

真实浏览器检查 1440×900、1366×768、1024×768、768×1024、430×932、390×844、375×812。列表/详情/编辑三页均保存截图与 [布局测量](browser-metrics.json)，页面宽度不超出视口。1440px 四卡宽度均约 1121.61px，两张表均约 1080.43px。

筛选栏实际测量：输入、两个选择器、查询/重置均约 39.99px 高，顶边一致（1440px）。Logo 实际点击已返回工作台。

真实交互通过：无修改保存提示、取消确认保留电话输入、确认保存、未保存离开继续/放弃、OTHER 和用药时间保留、手机删除恢复、自动创建 P000001、仅三个新增性别选项、折叠详情、选择/日期弹层、外壳焦点。仅在隔离环境创建和修改虚拟患者。

| 页面 | 修改前 | 修改后 |
|---|---|---|
|患者列表 PC|[before](before/patients-1440.jpg)|[after](after/patients-1440.jpg)|
|编辑 PC|[before](before/edit-1440.jpg)|[after](after/edit-1440.jpg)|
|资料 PC|[before](before/detail-1440.jpg)|[after](after/detail-expanded-1440.jpg)|
|患者列表手机|[before](before/patients-390.jpg)|[after](after/patients-390.jpg)|

补充：[保存确认](after/edit-save-confirm-1440.jpg)、[未保存离开](after/edit-unsaved-1440.jpg)、[手机焦点](after/edit-focused-375.jpg)、[手机恢复](after/deleted-restore-after-375.jpg)、[自动编号](after/automatic-number-created-375.jpg)、[手机折叠](after/detail-collapsed-375.jpg)、[日期弹层](after/date-popup-1440.jpg)。before/after 目录保存全部尺寸原图。

## 提交与已知限制

- `4260726` 导航与患者列表。
- **`1b305d2` #13 患者编号独立提交。**
- `a90a202` 编辑数据保护与版本检查。
- `620255f` 编号冲突重试边界（仅 #13 相关）。
- `0df840b` 详情四卡与移动恢复。
- 原有未跟踪目录/脚本完整保留，未纳入本轮提交。

SQLite 已实测。MySQL 仅验证 AUTO_INCREMENT DDL 编译，未获可用实库，不能声称完成 MySQL 迁移/并发验收。已有 MySQL DATETIME 若仅秒精度，会削弱同秒编辑的 updated_at 冲突检测；部署到 MySQL 前需引入可靠版本号或微秒字段迁移并独立实测。这不影响当前 SQLite 生产版本。

本轮没有修改训练算法。MicroFlow-DA 缺权重的既有状态保持，不属于本次缺陷修复范围。

## 生产发布

首次发布在迁移前的指纹预检查遇到可空外键排序错误，已自动恢复服务，服务器源码仍为原版本，未执行迁移。新增对应回归测试复现后修复。第二次发布使用独立暂存/备份目录，成功完成。


发布功能版本：`44b9117bd3a80c02b3cd31cc6f12894c1c0e3faa`，已推送 GitHub main。后续仅提交本节验收证据，不改变已部署功能。

- SQLite 已升级至 `i5d7e9f1a3b4`。迁移前后所有原表记录数、主键/外键及患者编号的身份指纹一致；quick_check、foreign_key_check 均正常。只读取身份/关联列及记录数，未读取医疗字段。
- 312 个部署文件逐一 SHA256 校验，根入口与域名入口 index 均与本机构建一致；后端和 nginx active，健康返回 ok。
- 公网 `https://ccqspace.site/pd-rehab/` 与 `http://110.42.236.65:18085/` 均通过独立验证：患者列表/编辑/详情三个新 JS 块哈希一致，深链接正常，未登录患者 API 返回 401。未在生产创建测试患者。
- 模型运行配置哈希不变，无权重状态不变。
- 按用户要求，验收通过后删除本次两轮发布的四个备份/暂存目录，共释放 192,961,672 字节（约 184 MiB），生产数据目录未动。
- 生产源代码工作区干净；本地只保留原有六处未跟踪内容。

验收原始证据：[迁移](database-verification.json)、[资源](release-ok.json)、[公网](production-verification.json)、[备份清理](backup-cleanup.json)。发布脚本可空外键修复与新增回归测试提交 `44b9117`；完整源码修改清单见 [changed-files.txt](changed-files.txt)。
