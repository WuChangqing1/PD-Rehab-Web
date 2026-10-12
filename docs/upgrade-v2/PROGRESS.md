# V2 深度升级 · 进度

更新时间：2026-10-12
基线：`9343061`（工作树干净，本地 = `origin/main`）
线上：`https://ccqspace.site/pd-rehab/`（部署版本 `ed0fefe`，仅落后一个纯文档 commit）

---

## 阶段状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| **P0** 源码与线上审计 | ✅ 完成 | 3 份报告 + 34 张改造前截图；发现并修复 1 个升级包未列出的 P0 缺陷 |
| **P1** 视觉系统 / 信息架构 | 🔄 进行中 | |
| **P2** 芭蕾媒体闭环 | ⏳ 待开始 | 1/2 候选已下载，动作审核仍缺 |
| **P3** 钢琴训练深化 | ⏳ 待开始 | |
| **P4** 微表情模型 | 🚫 **BLOCKED** | 无源码、无权重 |
| **P5** 回归 / 部署 | ⏳ 待开始 | 部署前需用户确认 |

---

## P0 已完成

**产出**
- `docs/upgrade-v2/UX_issue_inventory.md`
- `docs/upgrade-v2/model_readiness_report.md`
- `docs/upgrade-v2/asset_gap_report.md`
- `docs/upgrade-v2/spec_decisions.md`（D01–D10）
- `docs/upgrade_screenshots/before/`（34 张，7 种屏宽 × 8 个页面）

**修复**
- **U01（新发现，P0）**：`MovementTrainingPage` 在未选患者时请求 `/api/patients/`，
  FastAPI 307 重定向时因 nginx 已剥离子路径前缀而生成根路径 `Location`，
  被**另一个项目的 nginx block** 接走并返回 502。代码侧已加守卫；
  nginx 侧改法已记录，等确认。

**验证**
- 线上站点真实浏览器登录并逐页点击，5 项主导航一致，11 页面 × 7 尺寸无横向溢出。
- 本地 `127.0.0.1:8010` + `127.0.0.1:5173` 复现并确认修复。

## P0 阻塞项

| # | 阻塞 | 需要谁 |
| --- | --- | --- |
| B1 | 微表情模型源码 + 权重 + 标签表 + 依赖 + 输入规范 | 老师 |
| B2 | 5 个芭蕾动作的康复安全审核意见 | 老师 / 康复指导者 |
| B3 | `SRC-TENDU-01` 下载被 Wikimedia 限流（429） | 稍后重试，无需人工 |
| B4 | nginx 子路径重定向逃逸是否修 | 用户决策 |

---

## 下一步（P1）

1. 落地 `docs/02` 的设计 token（颜色 / 字号 / 圆角 / 间距 / 内容宽 1360px）。
2. 解除 `/follow-up` 的 `hidden` 语义冲突并加测试（D02）。
3. 按 `drive_series` 重构芭蕾结果卡片，让 Tendu/Demi-Plié 显示膝/髋而非肩角度（D01）。
4. 芭蕾动作卡补 CTA 并按 `margin-top:auto` 对齐（U04）。
5. 卡片等高与对齐做成可自动化断言的检查。
