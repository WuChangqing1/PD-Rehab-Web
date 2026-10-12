# 数据来源（provenance）审计

日期：2026-10-12
方法：用 **WAL 感知方式**取生产库副本（`server_deployment_plan.md` §9.1），
逐表读取真实数据，检查「哪些表能区分真人测量与合成数据，哪些读取路径会区分」。

起因：在**钢琴基线**上发现一处「合成数据被当成患者真实能力展示」（见
`UX_issue_inventory.md` U06）。本审计回答的是：同一类问题在别的测量面上是否存在。

---

## 1. 结论摘要

| 测量面 | 有无来源标记 | 读取路径是否过滤 | 判定 |
| --- | --- | --- | --- |
| 钢琴会话 `piano_sessions` | ✅ `input_source`（89 行：84 seed / 4 human / 1 selftest） | ✅ 趋势层过滤（前端） | 会话本身没问题 |
| **钢琴基线** `baselines` (PIANO_CALIBRATION) | ⚠️ 无独立列，标记在 `snapshot_json` 内 | ❌ **原本完全不过滤** | **U06，已修** |
| 手指敲击结果 `finger_tapping_results` | ✅ `input_source`（1 行：`UNLABELLED`） | ⚠️ 未见显式过滤 | 数据量极小；`UNLABELLED` 不会被误读为真人 |
| 姿势会话 `pose_sessions` | ✅ `input_source`（58 行：56 seed / 1 human / 1 selftest） | ✅ 趋势层过滤 | 会话本身没问题 |
| **综合评估基线** `baselines` (COMPREHENSIVE) | ⚠️ 无独立列；`snapshot_json.quality_metadata = {"source":"seed_demo","synthetic":true}` | — **无任何代码读取** | **休眠，非线上缺陷**（见 §3） |
| `assessment_sessions` | ❌ **完全没有 `input_source` 列** | — | 结构性缺口，见 §4 |
| 微表情结果 `micro_expression_results` | ❌ 无来源列 | — | 0 行（模型未接入，无可泄露内容） |

---

## 2. 已修复：钢琴基线（U06）

生产库上患者 `984c1aa3` 的活动钢琴基线来自唯一一条 `SYNTHETIC_SELFTEST` 校准
（`accuracy 0.778`、`latency 732 ms`、`CV 0.031`），而 3 条真人校准全部未完成。
界面把它显示为「基础能力测试已完成」。详见 `UX_issue_inventory.md` U06。

修复：代码层只对 `HUMAN_KEYBOARD` 写 `is_active=True`；数据迁移 `g3b5c7d9e1f2`
把已存在的非真人活动基线置为非活动（不删行）。

---

## 3. 综合评估基线：休眠数据，不是线上缺陷

生产库有 **10 条 `COMPREHENSIVE` 基线，全部 `is_active=1`**。逐条核查后确认：

- **每一条的 `source_id` 对应评估会话都没有任何结果行**（`finger_tapping_results` 0 行、
  `micro_expression_results` 0 行）；
- 每条基线与它的来源会话**创建时间戳完全相同**（同一段种子脚本写出）；
- 每条 `snapshot_json` 都带 `quality_metadata: {"source": "seed_demo", "synthetic": true}`
  与说明文字「虚拟演示 Baseline。模型输出与运动学指标为空，因为尚无真实模型与分析流水线。」；
- **所有测量字段都是 `null`**。

**最关键的一点：全仓库只有 `scripts/seed_demo.py` 会写 `COMPREHENSIVE` 基线，
而应用代码从不读取它。** 后端只在 `piano_service.py` 中以
`baseline_type == "PIANO_CALIBRATION"` 读写基线；前端只调用
`/patients/{id}/piano/baseline`。也就是说：

> 这 10 条综合基线是**没有任何代码读取的休眠数据**。
> 它们不会在任何界面出现，因此**不构成线上缺陷**。

**但风险是真实的、且值得记录**：如果将来实现「综合评估建立基线」功能，
并沿用今天的写法（无来源门槛地取 `is_active=True` 的那一条），就会立刻复现 U06。
届时的正确做法是：**先给 `assessment_sessions` 补 `input_source`，再设来源门槛。**

---

## 4. 结构性缺口：`assessment_sessions` 没有来源列

```
assessment_sessions: id, patient_id, session_type, medication_state, status,
                     created_by, started_at, completed_at, notes, created_at, updated_at
```

评估会话本身**不记录数据来源**。来源标记只存在于挂在它下面的结果表
（`finger_tapping_results.input_source`、`pose_sessions.input_source`）。

后果：

1. 一次「综合评估」如果**没有产生任何结果行**，事后完全无法判断它是不是脚本跑的。
   生产库里 29 条综合会话中有 28 条属于这种情况。
2. 任何按会话聚合的统计（例如"这位患者做过几次评估"）**无法按来源过滤**。

不在本轮修改，因为：
- 加列是加性、可回滚的迁移，但**补不出历史值**——已有的 29 条会话只能标 `UNLABELLED`；
- 而挂在其下的结果表已经带来源，当下没有读取路径因此产生错误展示。

**建议**（列入待办，不是本轮交付）：为 `assessment_sessions` 增加可空的
`input_source`，与既有结果表保持同一套枚举，历史行留 NULL 表示"未知"。

---

## 5. 手指敲击结果

生产库只有 **1 行**，`input_source = 'UNLABELLED'`，`hand = RIGHT`。

`UNLABELLED` 是**刻意**的默认值（不是 `HUMAN_KEYBOARD`），所以「忘记赋值」会
失败在安全一侧。这一行不会被任何按真人过滤的路径读成真人测量。

未发现需要修改的问题。

---

## 6. 建议的通用规则（写给未来的改动）

本轮发现的所有问题都指向同一条规则：

> **凡是能从存储行推导出「患者能力」的读取路径，都必须在查询层按来源过滤，
> 而不是把来源标记存下来、指望界面去提示。**

理由很直接：U06 那一条基线**确实存了警告**，接口也**确实返回了警告**，
但因为没有任何界面读它，线上照样把脚本结果当成患者的测量能力展示了整整一段时间。
**存下来的警告不构成防护，只有查询层的过滤才是。**

对应的自动化检查已经就位：
- `backend/tests/test_piano_baseline_provenance.py` —— 断言基线只在真人输入时为活动；
- `backend/tests/test_piano_event_storage.py` —— 断言 API 接受的每个事件字段都有归宿，
  不会被静默丢弃。
