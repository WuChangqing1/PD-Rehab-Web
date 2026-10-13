# UI 与钢琴优化审计（2026-10-13）

基线：fb4d9d049fc3e8006e59d4a5e67ad7aa5a45249a。开始时仅用户资料目录 `docs/codex-ui-piano-20261013/` 未跟踪，无未提交源码。工作分支 `codex/ui-piano-20261013`，不推送、不部署、不访问生产服务器。

已完整阅读包内 README、执行总 Prompt、01–07 专项文档并查看原始首页截图。

## 真实源码结论

- MainLayout 存在静态品牌、无交互说明卡、重复英语/工作人员端装饰；任务时整个导航隐藏，保留此退出保护。
- Dashboard 有大横幅和重复快捷导航；模型组件计数误称可用功能；最近患者整行点击缺少语义详情控件。
- PianoTrainingPage 和 session 存在重复模式配置；5 基础模式折叠，4 配方分别展示。SFT 与单键提示机制等价，应合并为变体。
- ACCENT_GROUPING 无力度采集却提示重按/轻按，必须修正文案。
- Cue/事件已有 JSON 扩展存储，适合增量实现，不需要数据库迁移。新增字段必须进入 schema、存储 side channel、详情与服务端重算。
- runner 在按下窗口结束时解析，长音会过早解析而丢失释放；取消没有清理全部持键。双手同步现有解析还会把第二键列为错键，主键漏按时丢掉次键，需要窄范围回归修复。
- 启动 Gate 在倒计时之前 prepare 中创建 Session，取消可能遗留空会话；改成训练保存时创建，绑定患者/配置快照，未采集不写库。
- 账号来自 auth.displayName（后端用户 display_name），不修改账号和数据库。

## 实施计划与接口

1. 首页导航与全站视觉：删无价值装饰，真实状态和近期工作，品牌链接、语义详情操作；保留安全指令和来源。
2. 单一 catalogue：SINGLE/SFT 同卡可选变体，另外 7 种旧机制保持可发现；加 5 新练习，共 13 个实质练习。
3. 新配方：TEMPO_RAMP / HOLD_RELEASE / BIMANUAL_OFFSET / REVERSE_SEQUENCE / GO_NO_GO。沿用 PianoMode，新增 RecipeId；v2 配方版本仅用于新项。
4. 原始字段：tempo_segment(0..3)、target_hold_ms、pair_id、target_offset_ms、cue_type(GO/NO_GO)。反向序列复用 is_prompt/memory_group/sequence_position。服务端分别重算分段准确率/MAE、持续时间 MAE/释放完成率、双手相位 MAE/左右漏击、逆序位置准确率/完成率、误按/漏按/反应时。
5. Gate 保留三秒倒计时；训练 Session 在实际事件保存时创建，取消准备/倒计时/退出不创建空记录。保存锁和持久 ID 避免重复。
6. 自动测试按行为先失败再实现；运行前端 test/build 与后端 pytest。独立浏览器夹具验证布局和取消；另用临时数据库真实 API 验证全部新增配方保存与读取，合成输入明确标识。
7. 七种指定尺寸截图，最终报告列明证据、文件、指标、提交和限制。分阶段本地 commit；保留用户原包不纳入源码提交。

并行边界：导航/一般页面视觉与后端扩展互不写同一文件；主线程负责钢琴引擎、目录、Gate 与集成。采用 parallel-agents 技能处理这两个独立领域，统一复核后提交。
