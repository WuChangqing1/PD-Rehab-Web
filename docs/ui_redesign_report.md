# UI 视觉升级与训练交互重构交付

## 页面改进

| 页面 | 改进 |
| --- | --- |
| 全站框架 | 统一冷灰背景、白色卡片、蓝色交互与青色辅助；重做品牌区、侧栏选中状态、账户区、留白和手机导航；提供跳转主要内容与键盘焦点样式。 |
| 工作台 | 欢迎区、统计图标、三项快捷入口与统一卡片排布，修复 grid 中相邻卡片 margin 造成的错位。 |
| 训练中心 | 自绘钢琴／芭蕾 SVG 封面，两张等高卡片、固定内容层级、对齐主按钮；手机改为单列。 |
| 钢琴 | 练习选择与预览分栏，明确选中状态；开始按钮进入预览卡片，手机先显示预览；原有模式与医生参数使用折叠区。琴键支持未选患者试听。 |
| 芭蕾 | 紧凑动作列表与示范分栏，保留坐姿／扶椅站姿、禁忌提示、动作步骤、节拍、真实指标；摄像头只在正式任务中出现。 |
| 评估中心 | 三项入口直接可见，图标封面、统一描述与底部操作；实际开始时才选择患者。 |
| 患者档案 | 优化搜索、表头、行间距和空状态；详情将基本／医疗资料分栏，去掉重复身份条，窄屏单列。 |
| 随访报告 | 增加真实记录数量概览，调整页签、图表颜色和空状态；切换患者先清空旧数据。 |

## 训练入口与启动

原 TrainingHubPage、PianoTrainingPage、MovementTrainingPage 的前置 PatientSelector 条件渲染阻断了目录与设置。现在目录、练习配方、动作和示范均不依赖患者即可浏览。

统一流程：开始按钮 → 核实患者 → 准备音频与服务端会话 → 3、2、1 → 原训练引擎／患者任务模式。

- 未选择患者：弹出复用的 PatientSelector，明确选择后保留练习，自动继续启动。
- 已明确选择：复用 URL 或当前上下文患者，每次启动重新请求患者资料，已删除／不存在患者不能开始。最近使用列表只作选择捷径。
- 切换患者：取消旧准备与倒计时，等待新患者基线／历史资料绑定；新身份准备完毕再倒计时。旧患者结果、录像和指标不会保留到新患者。
- 取消／离开：中止启动控制器，清理倒计时；迟到的准备响应不能进入任务。准备期间可能已创建有患者归属的未完成会话，但取消不会写入采集结果。
- 异常：显示明确提示，留在设置页面，可重新选择患者或重试；服务端创建失败不会提前进入患者模式。
- 钢琴无基线：先完成原基础能力测试，保留原先选中的练习，保存基线后恢复。保留三轮、自适应、原始事件和服务端重算路径。

共享 TrainingStartController 负责可取消准备与每次 1000 ms 的 3／2／1；钢琴使用 countInMs: 0 避免引擎二次预备。节拍声音在真实点击时解锁，倒计时配轻提示音；测量计时仍由原引擎负责。

患者加载增加请求版本与身份检查，避免迟到的初始请求误清钢琴基线，或旧患者历史覆盖新患者。关闭弹窗使用 Element Plus before-close，避免动画完成的 model-value 事件误取消新一轮启动。

## 设计系统

- 背景 #f5f7fa、正文 #18283c、次级文字 #586b81、主蓝 #356ac3、辅助青 #276a67。
- 使用现有系统字体，统一页面／分区／正文层级，完整展示关键标题与说明；统一按钮、标签、输入框、表格和圆角。
- 封面为项目内 SVG，自绘钢琴与芭蕾意象；未添加未经审核的第三方视频。芭蕾素材审核规则保持，缺少已审核视频时显示诚实的示意图。
- 桌面分栏、手机单列与触摸尺寸；悬停／按压为轻量反馈，尊重 prefers-reduced-motion。

## 验证与限制

最终验证：前端 187／187 项通过，生产构建成功，后端完整 336／336 项通过。后端有 2 条非失败警告（现有 Starlette/httpx 弃用与极端数值平方溢出测试）。[机器可读浏览器记录](ui-browser-results.json) 保存实际验收结果。

浏览器以 1440×900、1366×768、1024×768、768×1024、430×932、390×844、375×812、320×812 检查训练中心、钢琴、芭蕾、工作台、评估、患者列表、随访和患者详情，共 64 个页面／尺寸组合：没有整体横向溢出，桌面训练卡片主按钮对齐。

13 项交互检查覆盖：无患者浏览／开始选人、配置保留、已有患者跳过选择、重复点击仅创建一次、完成后显示保存、切换基线、已删除患者、无基线先测试、服务失败、芭蕾五个站姿动作、手机取消、延迟患者／历史响应、准备阶段取消、倒计时换人及离开页面。没有浏览器 pageerror。独立代码审查指出的患者加载竞争问题已修复并复核。

额外修复手机第一次点击的布局问题：点击解锁音频时，状态标签变化曾使页头重排，开始按钮在按下和松开间移动；现用固定的网格行分隔状态与标题，浏览器点击检查通过。

截图中的患者、计数与账户均为隔离夹具，所有 /api 请求由浏览器拦截，不访问真实患者数据库。浏览器结果验证交互与页面，不等同于真实设备采集验收。

已运行：

```powershell
cd frontend
npm run test
npm run build
cd ../backend
& 'D:\App\Business\Coding\Python\Miniconda\envs\pd\python.exe' -m pytest -o addopts='' -q
cd ..
node scripts/ui_before_server.mjs 92a8495a7761bf3b91aa6839c44fd3e7df5db3b4
node scripts/ui_redesign_browser.mjs before
node scripts/ui_redesign_browser.mjs after
```

原界面对照服务从指定 Git 提交读取源码，不切换或修改工作树。浏览器脚本当前使用本机 Chrome 与 Codex 打包的 Playwright 路径，其他机器需调整导入／可执行路径；静态动作夹具来自项目已有动作定义。

未验证的范围：真实 iOS Safari／Android 触摸与系统音频策略、实际摄像头权限／设备录像、真人运动采集及线下患者使用。没有修改后端算法、数据库模型／迁移或生产配置，没有推送和部署。

## 前后截图

同尺寸 1440×900：

| 页面 | 优化前 | 优化后 |
| --- | --- | --- |
| 训练中心 | [前](ui-screenshots/before/training-1440.png) | [后](ui-screenshots/after/training-1440.png) |
| 钢琴训练 | [前](ui-screenshots/before/piano-1440.png) | [后](ui-screenshots/after/piano-1440.png) |
| 芭蕾训练 | [前](ui-screenshots/before/ballet-1440.png) | [后](ui-screenshots/after/ballet-1440.png) |
| 工作台 | [前](ui-screenshots/before/dashboard-1440.png) | [后](ui-screenshots/after/dashboard-1440.png) |
| 评估中心 | [前](ui-screenshots/before/assessment-1440.png) | [后](ui-screenshots/after/assessment-1440.png) |
| 患者档案 | [前](ui-screenshots/before/patients-1440.png) | [后](ui-screenshots/after/patients-1440.png) |
| 随访报告 | [前](ui-screenshots/before/followup-1440.png) | [后](ui-screenshots/after/followup-1440.png) |

另保存 390／375 宽主要页面、桌面／手机患者选择及倒计时截图，位于 docs/ui-screenshots/after。

## 完整修改路径

- `D:\CodingData\Competition\PD\PD-Rehab-Web\README.md`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\package.json`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\ballet\BalletRhythmPanel.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\ballet\ExerciseDemoPanel.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\components\PatientSelector.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\components\SelectedPatientBar.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\components\TrendChart.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\layouts\MainLayout.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\pages\AssessmentHubPage.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\pages\DashboardPage.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\pages\FollowUpPage.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\pages\MovementTrainingPage.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\pages\PatientDetailPage.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\pages\PatientsPage.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\pages\PianoTrainingPage.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\pages\TrainingHubPage.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\router\index.ts`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\stores\patientContext.ts`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\styles\main.css`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\styles\responsive.css`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\components\TrainingArtwork.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\components\TrainingStartGate.vue`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\composables\useTrainingStartGate.ts`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\src\training\startController.ts`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\frontend\tests\training_start.test.ts`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\scripts\ui_redesign_browser.mjs`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\scripts\ui_before_server.mjs`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\docs\ui_redesign_plan.md`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\docs\ui_redesign_report.md`
- `D:\CodingData\Competition\PD\PD-Rehab-Web\docs\ui-browser-results.json`

截图文件：D:\CodingData\Competition\PD\PD-Rehab-Web\docs\ui-screenshots\before 与 D:\CodingData\Competition\PD\PD-Rehab-Web\docs\ui-screenshots\after；动作定义夹具：D:\CodingData\Competition\PD\PD-Rehab-Web\docs\ui-screenshots\exercises.json。

## 本地 Git 交付

代码、交互测试和前后截图提交：`c7036f6bf279a917c4a1a6e5806c031f8f64c8f5` — `feat(ui): refine rehabilitation workspace and training startup`。

本报告与静态 JSON 夹具的换行规范化以独立 docs 提交记录，可用 `git log -2 --oneline` 查看。交付时工作区已提交且干净；仅在本地保存，没有推送或部署。
