# PD-Rehab-Web 曲目跟弹与面部分析通道交付报告

日期：2026-10-16。基于磁盘源码与 Git 基线 `cf73687` 增量开发。本轮只修改本地源码，未推送、未部署、未操作正式数据库。

## 实际完成

钢琴训练目录新增“曲目跟弹”，没有新增侧栏入口。原有 13 项练习、基础能力测试、三轮自适应、芭蕾、Finger Tapping、独立面部评估及随访页面均保留。

新练习支持左/右任务手别、初级60/中级80/高级100 BPM、《两只老虎》两段示范与弹性跟弹。七个白键无正面文字，使用统一坐标叠加透明波浪线和本地音符 SVG；当前音符与琴键共用目标状态。Pointer Events、电脑 A S D F G H J、取消触点、失焦暂停、减少动画模式均有处理。

启动沿用 TrainingStartGate：可无患者浏览；点击开始才核实患者；3秒倒计时取消不创建会话；倒计时成功后才创建。已选患者无需重复选择。正式会话绑定登录医生和患者，重复请求由 client_request_id 约束。异步创建迟到会取消；取消同步失败保留事件、阻止新训练或历史覆盖，并提供重试。

两段各自自动演示，真实音频通过 Web Audio 时钟预排；动画用同一音频时钟驱动。演示点击不进入患者记录。错键被保存且不前进；正确按下只前进一音；最后一个音符等到释放才进入段间或合成。支持暂停、跳过、结束。页面隐藏与退出停止声音和视频采集，硬退出采用尽力而为的 keepalive 取消，不把部分练习标成完成。

原始事件先保存，后端复算逐音记录和准确率。结果可查看、重听、下载、重新合成；历史音频通过鉴权接口获取。历史列表不读取音频 BLOB 或全部原始事件，避免长录音导致内存峰值。

## 曲目与时钟

`song.ts` 维护 song_id、song_version、标题、七音阶、支持难度、分段及每音 MIDI/时值/全局序号。第一段14音，第二段18音；Vue 模板不解析音名字符串。

Raw Events 包含 seq、type、segment_index、note_index、time_ms、midi、press_id。类型为 CUE/DOWN/UP/SKIP/PAUSE/RESUME；每次物理按下使用独立 press_id。time_ms 使用 performance.now 的训练单调时间。client_clock_origin_epoch_ms 保留浏览器墙钟原点，与服务端 created_at 分别记录，可重建操作的绝对时间；客户端与服务器时钟未宣称已高精度同步。

每音记录提示、首次尝试、正确按下、松开、按住时长、尝试/错误次数、首次是否正确、跳过。绝对时钟和段间教学等待保留在审计中；正式行为和音频只来源于跟弹区间。

首次尝试准确率 = 首次按对的目标数 / 实际尝试目标数。
总体尝试准确率 = 正确按键次数 / 有效尝试次数。
完成率 = 正确完成目标数 / 32。
正确响应时延 = 初次提示至第一次正确按下；首次尝试时延另存。没有为弹性跟弹编造固定节拍 Timing Error。手别是任务指定，未声称识别实际手或按压力度。

## 音频实现

OfflineAudioContext 复用原钢琴采样表，重建真实 DOWN/UP，包括错音、每段真实等待与按住时长。两段仅保留150ms自然过渡，尾部250ms释放，渐入/渐出并做峰值保护。输出16位单声道44.1kHz WAV。

保存元信息：audio_url、duration_ms/audio_duration_ms、audio_format、audio_source=SYNTHESIZED_FROM_KEY_EVENTS、render_version=1。明确不是麦克风录音，不申请麦克风权限。音频合成或上传失败不会撤销已保存的原始事件。

当前离线合成设五分钟内存保护，超过时长仍可保存训练记录，但本版无法生成该长音频；重新生成仍受同一上限约束。后续可通过分块离线渲染或服务端渲染扩展。

## 视频通道与真实模型状态

新增 /api/live-emotion/stream WebSocket。首包提交登录 token 和 session_id/patient_id；不把 token 放在 URL。校验活动医生、会话拥有者、患者及 ACTIVE 状态。每医生最多一连接，全局最多16连接；鉴权5秒超时，片段等待/推理有超时。

连续 MediaRecorder 容器片段采用“JSON元数据 + 二进制 + result + ACK”。元数据包含序号、采集时间、时长、字节长度、MIME。每片最大2MiB、100–5000ms、最短发送间隔0.5秒；只允许一个在途片段。序号、连续时间、MIME、实际字节数校验失败则停止通道，避免无界堆积或破坏时序后继续推理。

仅明确同意后，在服务端返回 READY 及已验证输入契约时申请前置摄像头，audio:false。拒绝权限、非安全上下文、无设备、网络断开、背压或页面退出均停止采集并降级，不影响钢琴记录。原始面部视频不落盘。

模型结果协议包含训练/患者/流ID、采集与结果时间、序号、模型名/版本、固定标签顺序、七类概率、质量、来源、延迟。质量不足的结果概率为空；没有填正常值。保留结果消费、质量计数和延迟统计。未来已接入适配器的推理通过现有 GPU 同步并发锁。

**真实老师模型仍未提供。** 默认 temporal_adapter=None，返回 MODEL_NOT_CONFIGURED、capture_required=false，不开启摄像头、不上传无用视频、不展示虚假概率。现有独立面部 Adapter 与页面未替换。

FPS、窗口、尺寸、光流要求、真实标签映射、推理速度均尚不能从真实模型核实。测试注入的 TEST_ONLY adapter 只验证二进制接收/状态保持/ACK，不是已接入真实微表情识别或连续视频解码器。实际接入必须实现 open/infer/close 的有状态解码与模型推理，并验证 MediaRecorder 容器能否满足时序要求；否则评估 WebRTC。传输超时可立即关闭连接，原生推理线程不能安全强杀，接入真实模型时仍需可中断的工作进程或模型级超时。

## 模拟与正式难度

EMOTION_SIMULATION_MODE 默认 false，仅 development/test 环境有效；还要求会话 is_simulation=true、input_source=SYNTHETIC_SELFTEST。浏览器模拟结果消费另要求显式 opt-in。开发界面的模拟选项有明确告知，生产构建隐藏。

固定七类样本 other=.35、happiness=.35，总和.70> .50。只在第一段完成并全部释放后，60→80、80→100、100→110，最高120 BPM。服务端保存前后难度、来源、概率快照、原因与策略版本。SIMULATED 数据明确标记 clinical_eligible=false；新曲目记录不混入旧固定节拍随访指标。

正式模式结合可用真人基线与实际按键表现。没有经过验证的情绪策略时不会用情绪升级；低表现或跳过可降速，其余维持。原有钢琴自适应算法未修改。

## 数据库

新增 Alembic `h4c6d8e0f2a3`，上接 `g3b5c7d9e1f2`。仅创建 guided_song_sessions，保存配置、原始事件、服务端逐音结果、音频、来源及时间。没有删除或重命名旧字段。

测试从旧 revision 建库、插入患者后升级 head，验证患者记录保留。现有环境需要运维按原迁移流程执行 alembic upgrade head；本次没有对真实数据库执行迁移。

## 验证结果

| 验证 | 结果 |
|---|---|
| npm run test | 243通过，0失败 |
| npm run build | 根路径成功 |
| VITE_BASE=/pd-rehab/ npm run build | 子路径成功 |
| 后端 pytest | 417通过，2个已有依赖/数值测试警告 |
| 原有前端/后端回归 | 包含在完整套件中 |
| 本机 Chrome | 完整32音、错键、暂停、倒计时取消、保存/回放/下载、三种尺寸通过 |
| 本机 Edge | 键盘跟弹、断网恢复、跳过、历史音频、模拟段间提速、取消通过 |
| 摄像头资源单测 | 拒绝授权、无模型不采集、权限迟到释放、断流清理、质量/延迟统计通过 |
| WebSocket测试 | 鉴权、绑定、超时、限流背压、二进制ACK、模拟隔离通过 |

Chrome 自动操作为 SYNTHETIC_SELFTEST：32目标全部完成，33次尝试（1次错误）；首次尝试准确率96.875%、总体尝试准确率96.9697%、完成率100%。这些仅用于程序验收，不是患者能力测量。

响应式截图使用桌面 Chrome 的1440×1000、820×1180、390×844及844×390视口；七键均可见，无横向页面溢出，音符框中心与键中心误差<1像素。**未以模拟尺寸声称真实 Android Chrome 或 iPhone Safari 已验证。** 当前没有可用真机或远程设备环境，原生全屏、方向锁定、触控音频与实际前置摄像头仍待设备验收。

## 截图与证据

全部位于 ../artifacts/guided-song/，可打开 index.html 浏览17张截图。before-piano-catalogue-20261013.png 是上一轮留存的原目录截图，来源于2026-10-13截图包；其余为本轮实际浏览器截图。

- pc-config.png / pc-demo.png / pc-paused.png / pc-wrong-key.png / pc-segment-2-demo.png / pc-result.png / pc-note-records.png
- tablet-config.png / tablet-stage.png
- mobile-config.png / mobile-stage.png
- mobile-landscape-config.png / mobile-landscape-stage.png
- edge-network-failure.png / edge-recovered-result.png / edge-simulation-80bpm.png
- browser-results.json / edge-results.json：运行记录与虚拟患者来源说明。
- selftest-performance.wav：按自动验收事件合成的演奏，只在本地保留。
- ../artifacts/guided-song-frontend-tests.txt / guided-song-backend-tests.txt / guided-song-pytest.xml / guided-song-build.txt / guided-song-subpath-build.txt。

## Git Commit

- caf1c03 — 曲目、状态机、音频重建、七键舞台与音符素材。
- d21a349 — 后端会话、指标、迁移与实时视频传输。
- 6c9dc6b — 页面集成、启动/退出竞态、回放历史与摄像头生命周期。

后续文档与浏览器验收提交包含本报告、脚本与截图。所有提交在本地 main，未自动推送或部署。

## 尚待完成

1. 接入老师真实模型与连续视频解码器，核实输入契约、七类标签、质量门槛和真实推理延迟。
2. 真机 Android Chrome / iPhone Safari 原生行为验收；桌面回退与资源单测已覆盖，但不能代替真机。
3. 超过五分钟的演奏音频渲染；原始记录保存不受该音频上限影响。
4. 硬关闭且网络不可用时，keepalive 无法保证送达；页面内有取消同步重试，未确认的会话保持未完成，不伪造完成结果。

## 本轮源码与文档文件清单

```text
backend/alembic/versions/h4c6d8e0f2a3_guided_song.py
backend/app/api/guided_song.py
backend/app/api/live_emotion.py
backend/app/api/router.py
backend/app/core/config.py
backend/app/db/models/__init__.py
backend/app/db/models/guided_song.py
backend/app/schemas/guided_song.py
backend/app/services/guided_song_service.py
backend/app/services/live_emotion_service.py
backend/tests/test_guided_song.py
backend/tests/test_live_emotion.py
backend/tests/test_schema_bootstrap.py
docs/guided_song_upgrade_plan.md
docs/guided_song_upgrade_report.md
frontend/package.json
frontend/public/assets/music/README.md
frontend/public/assets/music/music-notes-source.svg
frontend/public/assets/music/quarter-note.svg
frontend/src/emotion/streamClient.ts
frontend/src/emotion/types.ts
frontend/src/emotion/useLiveEmotion.ts
frontend/src/pages/GuidedSongPage.vue
frontend/src/pages/PianoTrainingPage.vue
frontend/src/piano/catalogue.ts
frontend/src/piano/engine.ts
frontend/src/piano/guided-song/GuidedSongStage.vue
frontend/src/piano/guided-song/SevenKeyKeyboard.vue
frontend/src/piano/guided-song/WaveStaffOverlay.vue
frontend/src/piano/guided-song/api.ts
frontend/src/piano/guided-song/audio.ts
frontend/src/piano/guided-song/geometry.ts
frontend/src/piano/guided-song/machine.ts
frontend/src/piano/guided-song/song.ts
frontend/src/piano/guided-song/useGuidedSong.ts
frontend/src/router/index.ts
frontend/tests/guided_controller.test.ts
frontend/tests/guided_song.test.ts
frontend/tests/guided_stage.test.ts
frontend/tests/live_emotion.test.ts
frontend/tests/live_emotion_capture.test.ts
frontend/vite.config.ts
scripts/guided_song_browser.mjs
scripts/guided_song_edge_browser.mjs
scripts/guided_song_capture_views.mjs
```
