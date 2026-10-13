# 钢琴后端增量实现（2026-10-13）

本轮仅修改钢琴 schema、service、metrics、API 与新增测试。未修改数据库结构、迁移、清库、生产数据或旧指标公式；未 commit/push。

## 接口与存储

- 新配方 `TEMPO_RAMP`、`HOLD_RELEASE`、`BIMANUAL_OFFSET`、`REVERSE_SEQUENCE`、`GO_NO_GO` 加入请求白名单。前四项中反向序列基于 `MEMORY_RHYTHM`，其余基于 `SINGLE_KEY_RHYTHM`；错误组合返回 422。
- 原始事件新增 `tempo_segment`（0..3）、`target_hold_ms`（>=1）、`pair_id`（>=0）、`target_offset_ms`（>=0）、`cue_type`（GO/NO_GO），均可为空。字段通过 Pydantic 校验，进入已有 `events_extra_json`，在 GET/complete 的 events 中返回。
- 原有 recipe、pair、accent 扩展字段现在也显式进入 `PianoEventRead`，避免响应模型过滤原始数据。
- 各批事件扩展元数据合并，后续批次不会抹掉早先的 prompt/pair/sequence 字段；省略 planned_cues 时保留前批值。
- 同一 session 下，相同 `event_index` 的相同内容重传返回 stored=0；内容改变返回 409，保留先前证据。单个批次重复行同样不重复存储。
- `PianoEventsBatch.raw_presses` 为可选列表（每批最多 5000），每行包含 `key_code`、`midi`（0..127）、非负有限数 `key_down_time_ms`、可空的 `key_up_time_ms`，并要求 up>=down。时间保留毫秒小数，相对本轮开始。audit.raw_presses 保留示范阶段、额外按键和未释放输入；重传合并，允许后来补上释放时间；不进入正确率分母。
- 新配方创建时 audit.recipe_algorithm_version=`piano-recipe-v2.0.0`，旧配方使用 v1.0.0；无配方为 null，不回填历史数据。
- SessionCreate/CalibrationRequest 可选 `started_at`，要求带时区、不能超过当前时间 5 秒，归一 UTC；未传时保留服务端当前时间默认值。
- 两种创建请求可选 `client_request_id`（1..64 字符），按患者和 audit 中该值复用已创建会话；相同请求 ID 改 mode/recipe/input_source、任一 difficulty 字段、seed、round_number 或 weak_hand 返回 409，患者之间独立。SQLite 在去重读之前用无值变化的 UPDATE 取得事务写锁（明确保留患者 updated_at），其他数据库使用 FOR UPDATE；后续 session/event 查询亦使用锁定读取，避免已有 repeatable-read 快照影响去重。事件批写同样先锁 session 再查已有事件；未增加唯一索引或迁移。
- complete 可选 `interrupted`（默认 false），audit.completion_status 写 INTERRUPTED/COMPLETED；completed_at 保留原先的关闭时间定义。中断校准不创建或替换有效基线，真实采集的事件仍保存。

## 服务端新增指标定义

所有新增值写入 audit.server_metrics，旧数据库列映射保持不变；无适用原始字段时数值为 null，tempo_segments 为空列表。

| 配方 | 指标与定义 |
| --- | --- |
| TEMPO_RAMP | tempo_segments 按实际出现的 0..3 分段返回 accuracy、timing_mae_ms、miss_rate、cue_count；MAE 从 actual-target 重算，仅计正确响应；另提供 tempo_segment_0..3_accuracy / tempo_segment_0..3_mae_ms 数值键。 |
| HOLD_RELEASE | hold_duration_mae_ms=有效 up-down 与 target_hold 的绝对差均值，不信客户端 hold_duration；hold_release_completion_rate=有有效按下及释放的目标数/全部 hold 目标数，未释放与漏击仍在分母。 |
| BIMANUAL_OFFSET | 两手有独立 cue_index，以 pair_id 配对，PRIMARY 左、SECONDARY 右；inter_hand_phase_mae_ms=abs(右actual-左actual-target_offset)均值；缺一手无相位值；offset_left/right_miss_rate 以配对总数为分母。错位配对不混入旧双手同步指标。 |
| REVERSE_SEQUENCE | reverse_position_accuracy 为非prompt目标位置正确率；reverse_completion_rate 要求该 memory_group 的完整 1..length 位置都存在且正确，部分组不能算完成。与现有 session 和前端序列的 1-based 位置契约一致。 |
| GO_NO_GO | go_commission_count 为发生实际按键的 NO_GO 目标数，额外 wrong-key 行不重复计目标；go_omission_count 为无实际按键的 GO 目标数；go_response_latency_ms 从正确 GO 的 actual-onset 重算。正确不按计正确目标，不计漏按；NO_GO 不进入 latency/timing 击键指标。 |

## 验证证据

使用 `D:/App/Business/Coding/Python/Miniconda/envs/pd/python.exe -m pytest -o addopts='' -q`，cwd=backend。所有 API 用例通过真实 FastAPI TestClient 与独立内存 SQLite 数据库完成，未连接开发/生产数据库。五种新配方生命周期明确标记 SYNTHETIC_SELFTEST。

TDD：先运行新增 16 条用例，全部因缺少配方接受、字段校验、NO_GO 排除或版本/状态而失败，再实现至通过；started_at 6 条失败后实现；中断校准用例先复现旧基线被替换，再修复；raw_presses 5 条失败后实现；client_request_id 5 条失败后实现。

最终相关测试命令：

```powershell
& 'D:/App/Business/Coding/Python/Miniconda/envs/pd/python.exe' -m pytest -o addopts='' -q tests/test_piano_extended_recipes.py tests/test_piano_concurrent_retries.py tests/test_piano_api.py tests/test_piano_metrics.py tests/test_piano_recipe_metrics.py tests/test_piano_event_storage.py tests/test_piano_regressions.py tests/test_piano_baseline_provenance.py tests/test_no_fabricated_scores.py --tb=short
```

结果：**128 passed，1 warning，19.36 秒**。警告为已有 Starlette TestClient/httpx 弃用提示。

早先完整后端运行：358 passed、1 failed，96.40 秒；失败为并行 UI 工作期间 MovementTrainingPage 缺“展示分”说明的 `test_the_interface_explains_why_the_scores_are_blank`，已交由 UI 修正，以上最终相关运行已覆盖并通过该回归。最终全量测试由主线程统一执行。

`git diff --check` 无空白错误。浏览器/移动端验收由主线程负责，本后端测试不替代真实输入设备验收。

集成复核修正：增加 1-based 完整 [1,2,3] 完成率为 1、缺位置 [1,3] 为 0 的测试，并把真实 API fixture 改为 1-based；先观察完整序列及 API 用例 2 failed，再改为 `range(1, length + 1)`。修正后 extended recipes、旧 recipe metrics 与 piano regressions 共 **60 passed，1 warning，8.22 秒**。

后续 TDD 修正：4 条请求配置变化用例先复现错误返回 201；2 条独立连接的真实文件 SQLite 并发 API 用例先复现重复 session ID、重复事件 stored=[1,1]。严格参数比较和事务锁实现后，新 6 条及上述全钢琴相关 128 条通过。并发测试通过 SQL 执行后 50ms 等待扩大真实竞争窗口，不模拟业务服务；测试文件数据库在专用临时目录销毁。非 SQLite 的 FOR UPDATE 分支未连接真实 MySQL/PostgreSQL 做并发验收。

保留并报告的既有边界：校准 complete 与 baseline 保存仍是两次提交；若服务进程恰在两次提交间退出，session 可能已关闭而新 baseline 尚未建立。重复 complete 仍按旧契约返回 409，前端可 GET 恢复已保存的结果；本轮未宣称修复该跨提交崩溃场景。
