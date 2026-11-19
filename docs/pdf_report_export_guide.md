# 随访报告与业务数据导出

在「随访与报告」选择患者后，点击「导出 PDF 报告 / 数据」。没有选中患者时按钮不可用，接口也不提供默认全患者导出。

日期可通过日历选择，也可选择最近 7 天、最近 30 天、本月或全部历史。日期统一使用北京时间 UTC+8，起止当天均包含；全部历史不发送日期参数。快捷范围以北京时间当天为准，与浏览器所在时区无关。

PDF 下载接口：`GET /api/patients/{patient_id}/report.pdf`。可选参数为 `start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`。结构化数据入口共用弹窗，调用 `GET /api/business-exports/patients/{patient_id}?format=json|csv`，附带相同日期参数。

## 实际内容及边界

报告读取与结构化导出相同的授权快照，包含患者姓名、编号、日期、生成时间、按来源/任务/版本分组的记录条数与完成标记条数，以及已保存的评估、敲击结果、钢琴、曲目跟弹、舞蹈、计划及软件端记录。原生面部结构化结果只在关联评估为 `COMPLETED` 时呈现。不同任务、模拟来源和指标版本分别显示；不计算混合分数或生成医疗诊断。

记录明细保留原始字段值，常用字段附中文标签；未覆盖中文名称的字段保留原系统标识。时间字段沿用保存值，无时区后缀的服务器时间为 UTC；软件端毫秒值为 Unix 时间。缺失字段表示未保存，不能解释为零。报告概览中的完成数仅统计明确的完成时间或 `COMPLETED` 状态，不将未标注的记录推断为完成。

没有业务记录时输出明确空结果 PDF。评估历史按记录呈现；本轮未增加趋势曲线、跨版本比较或自动治疗解释。计划配置与已有状态按保存值展示；没有伪造未保存的计划历史或独立随访记录。

PDF 不含聊天、视频二进制、媒体路径、原始训练事件及账号凭证。JSON/CSV 的字段范围见 `data_persistence_export_audit.md`。PDF 中的数据快照 SHA-256 与响应 `X-Content-SHA256`（PDF 本身的哈希）用途不同。

## 权限、文件和部署前提

接口要求有效工作人员会话，并在生成前复核患者权限、停用状态与撤销的访问授权。角色、日期过滤复用 `build_patient_export`，不依赖前端按钮进行授权。下载成功记入现有审计日志，记录患者编号关联、日期范围及 PDF SHA-256。

PDF 在内存生成并通过私有响应返回，`Cache-Control: no-store`；不写静态目录或临时公共文件。A4 竖版，表格可跨页、重复表头，页脚显示页码。文件名含患者编号及日期范围，非法路径/换行字符被替换。

依赖为 `reportlab==4.4.9`。必须提供允许嵌入的中文 TrueType 字体：优先设置 `PD_REPORT_FONT` 为字体绝对路径；否则检测 `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`、`/usr/share/fonts/truetype/arphic/uming.ttc` 或 Windows `C:/Windows/Fonts/simsun.ttc`。Linux 部署须预先安装并验证所选字体，不复制 Windows 商业字体到服务器或 Git。字体作为子集嵌入 PDF，接收者无需安装同一字体；字体缺失时报错，不生成乱码文件。

## 本地验证（2026-11-19）

- 首次运行新增测试时因服务和日期模块缺失失败；实现后 `pytest backend/tests/test_patient_reports.py backend/tests/test_business_exports.py -q`：13 项通过。
- 报告测试覆盖授权撤销、普通用户拒绝、下载头、空报告、300 条多页记录、版本隔离、完成面部过滤、文件名净化与单日/跨年 UTC+8 边界。
- `node --experimental-strip-types --test tests/report_export.test.ts`：2 项通过，覆盖北京时间跨年、7 天/本月/全部历史、患者必选、无效日期和反向日期。
- `npm run build`：通过（Vue 类型检查及生产构建）。
- 仅使用合成患者生成并通过 Poppler 渲染空报告和 32 条记录的多页报告，人工检查中文、表头续页、页码和无重叠；`pdfinfo` 验证 A4 竖版，`pdffonts` 验证中文字体子集嵌入且 Unicode 映射存在。QA 文件位于本地忽略目录 `tmp/pdfs`，不是生产患者数据。

尚未将本地验证称为线上验收：部署环境中文字体与浏览器真实下载流程需要由集成发布阶段单独验证；本轮没有读取生产患者数据。
