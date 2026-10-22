# 中英文切换：验收记录与发布授权

**状态：本地验收完成；用户已于 2026-10-22 明确授权提交 main、推送和部署。**

最初按用户要求仅在本地开发；随后用户明确授权发布，并要求同步更新 GitHub README 与截图。开发基线为 `7bce0d4`。本目录记录本地验收证据，最终发布版本以 Git 提交及线上校验为准。

## 使用

- 默认中文，登录页、主导航右上角、患者任务界面与曲目跟弹沉浸工具栏提供切换按钮。
- 中文界面点击 `English`；英文界面点击 `中文`。选择保存在本机浏览器的 `paqin-language`，刷新后保留。
- 导航、页面、表单、评估与训练提示、随访图表、日历、Element Plus 控件、弹窗和已知错误提示随语言更新。
- 患者姓名、账户显示名、医生备注、原始 JSON 和图表采样值不做自动翻译。未收录的新服务端提示保留原文，避免不明含义的替换。
- 不重建路由视图，不修改训练参数、数据库、模型或算法。

## 实现与维护

- `frontend/src/i18n/core.ts`：语言值校验、持久化容错、已知文案与参数占位符翻译；更具体的模板优先匹配。
- `frontend/src/i18n/index.ts`：Vue 响应式语言状态、词库与标题。
- `frontend/src/i18n/en-*.json`：1312 条去重英文文案，按通用、患者随访、钢琴、模型等分组。
- `frontend/src/i18n/charts.ts`：图表展示标签翻译；保留原始 data/id 与数值。
- `frontend/src/components/LanguageSwitcher.vue`：统一切换按钮。
- `App.vue`：Element Plus locale 与文档标题，不用 locale 作为路由组件 key。
- `OptionalValue.vue`：默认展示原始资料，枚举等界面值需显式 localize。

新增文案时应同时补英文词库并执行测试；含患者资料的文本要显式保护，不能对整段病历做字词替换。

## 验证结果

- `npm --prefix frontend run test`：304 passed，0 failed。
- `npm --prefix frontend run build`：通过。
- `VITE_BASE=/pd-rehab/` 下构建 `dist-under-path`：通过。
- `git diff --check`：通过。发布时仅暂存中英文功能、相关文档及截图。
- 本地隔离测试 API `127.0.0.1:8016`，前端浏览器预览 `127.0.0.1:5184`，不使用生产患者数据。
- 检查视口：桌面 1440、平板 768、手机 390 像素；英文导航与页面无横向溢出。
- 表单填写姓名与备注后中英往返：内容保留；未创建患者记录。
- 随访中英往返：保留患者、日期范围、练习、参数和图表，月份与星期同步。
- 曲目跟弹暂停时中英往返：保持 `SEGMENT_1_DEMO`、暂停状态、原路由与进度；测试会话结束于隔离环境。
- 英文登录校验、分页日期控件与退出确认文案已检查。

## 截图

- `assessment-en-desktop.png`、`assessment-en-mobile.png`：英文评估中心。
- `patients-en-desktop.png`：患者资料保持原名，枚举使用英文。
- `followup-en-desktop.png`、`followup-zh-desktop.png`：同一随访图表中英往返。
- `followup-en-tablet.png`、`followup-en-mobile.png`：平板与手机。
- `guided-paused-en.png`、`guided-paused-zh.png`：训练暂停状态中英往返。
- `dialog-en-mobile.png`、`login-en-validation-mobile.png`：英文弹窗与登录校验。

详细变更文件清单见 `verification.json`。新增错误提示后缀翻译修正；切换语言不会因规则变化提前触发空表单校验。后端回归 481 passed、1 skipped（测试环境无 PyTorch）。
