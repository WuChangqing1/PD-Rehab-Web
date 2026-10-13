# 导航与非钢琴界面精修记录（2026-10-13）

## 修改内容

- `frontend/src/layouts/MainLayout.vue`：删除侧栏假加号说明卡、英语口号与工作人员端装饰文案；整个品牌为返回 dashboard 的语义链接，含 accessible name/title/focus-visible。折叠时品牌居中且不裁切，平板默认折叠，移动抽屉有品牌链接。任务状态继续隐藏侧栏、页头及抽屉，保留单一 router-view。
- `frontend/src/pages/DashboardPage.vue`：删除大横幅、英语与重复快捷入口；保留患者总数、今日评估次数、今日训练次数三个 API 真实 KPI。分析组件状态移到紧凑状态区，逐项显示组件名称和就绪/不可用等状态。最近患者含真实链接“查看档案”，最近评估姓名链接到患者档案；刷新有 loading 与并发保护。手机版三 KPI 同排，记录表格在自身区域滚动。
- `frontend/src/pages/TrainingHubPage.vue`：中文功能标题，删除教程/营销段；两张卡按相同封面比例、标题、说明、元信息和底部 CTA 布局；保留首次基础能力测试与患者基线状态，CTA 明确表示浏览练习，未选患者可直接浏览。
- `frontend/src/components/TrainingArtwork.vue`：保留自主 SVG 封面，删除英语装饰标签。
- `frontend/src/styles/main.css`：区块标题 token 18px、边框 token 统一、标题默认 margin 归零、主要按钮不低于 44px；沿用现有全站布局/空态/表单/弹窗/减少动画规则，未添加大范围覆盖。
- `frontend/src/pages/AssessmentHubPage.vue`：精简副标题和封面重复“客观评估”标签，保留三种评估与操作说明。
- `frontend/src/pages/LoginPage.vue`：品牌形状和侧栏一致，统一卡片圆角，保留用户名/密码和登录操作。
- `frontend/src/pages/PatientsPage.vue`、`PatientDetailPage.vue`、`FollowUpPage.vue`：删除重复口号/导航提示，精简综合报告工程说明；患者身份、编辑/恢复/删除、来源真实性、缺失值和指标单位均保留。PatientDetail/FollowUp 后续钢琴历史修改归主线程。
- `frontend/src/pages/MicroExpressionPage.vue`、`frontend/src/utils/errors.ts`：错误文案“系统管理员”改为“技术维护人员”。
- `frontend/src/pages/MovementTrainingPage.vue`：去掉普通目录中的英文副标题和结果“展示分公式未定义”段，保留中文坐姿适配名和安全提示；该文件后续由 start_consistency agent 负责，在高级指标中安排缺失评分的技术说明。

## 账号来源

已核实 `frontend/src/stores/auth.ts`：`auth.displayName` 读取 `user.display_name`，登录/启动分别经登录响应和 `/auth/me` 获取。后端 `backend/app/core/config.py` 的 bootstrap 默认昵称为“系统管理员”，`backend/app/db/init_db.py` 初始化写入该昵称；本轮仅查看来源，没有修改账号、密码、角色或数据库。

## 验证证据

- `node --experimental-strip-types --test frontend/tests/navigation.test.ts frontend/tests/ui_contract.test.ts`：42 / 42 通过。
- `npm run build --prefix frontend`：TypeScript 与 Vite 构建通过（并行主线程收敛后的最新运行）。
- 早期 `npm run test --prefix frontend`：193 项，188 通过，5 项失败均为主线程正在扩展钢琴时的旧 recipes 约束/算法测试；已向主线程报告，最终全量结果以主线程集成验收为准。
- `git diff --check` 针对本任务所属源码：通过。
- `node scripts/ui_piano_shell_browser.mjs`：真实本地 Chrome 无头浏览器通过。使用隔离合成 API 夹具，真实数值映射/组件状态/键盘品牌链接/折叠品牌链接/手机抽屉品牌链接/患者档案链接均已点击与断言；零页面异常、零 API 写请求。
- 七种尺寸：1440×900、1366×768、1024×768、768×1024、430×932、390×844、375×812。每种检查 dashboard/training/assessment/patients/followup/ballet 六页无页面横向溢出，桌面和平板两卡封面、标题、CTA 顶边和高度误差不超过 2px。
- 22 张截图与机器结果：`docs/ui-screenshots/ui-piano-shell-20261013/`；`results.json`。已人工查看桌面 dashboard/training、手机 dashboard 375/training 390 截图。

## 边界与集成提醒

- 本任务未编辑 piano 目录、PianoTrainingPage、Gate、backend、package.json；未新增 source 文字匹配测试，新增的是隔离浏览器行为脚本。
- Dashboard 当前 API 只有 recent_assessments，没有最近训练列表；未杜撰训练历史数据或增加后端接口。工作台仍显示真实今日训练 KPI，完整训练历史继续从随访查看。
- 浏览器截图来自明确的合成夹具，不能当作真人临床数据或真实后端集成证据。钢琴训练/倒计时/持久化由主线程另行验收。
- 未部署、未推送、未 commit；用户未跟踪设计包保持原样。截图属于交付证据，主线程可按仓库体积约定决定纳入提交方式。
