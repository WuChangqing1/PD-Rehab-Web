# 曲目跟弹与实时面部通道实施计划

> 使用 writing-plans 与测试驱动方式逐项实现。用户已明确授权计划后直接继续开发，不增加审批阶段。

**目标**：新增独立曲目跟弹练习，完整记录两段演奏、服务端复算、可回放合成音频；建立可授权、可降级、无伪造结果的视频通道。
**架构**：保留旧 Piano Engine/Runner/自适应逻辑。新增 guided-song 纯状态机、七键舞台和页面；复用样本、患者上下文与 TrainingStartGate。新增独立 guided_song_sessions 表与接口，避免弹性跟弹指标污染固定节拍指标。
**技术**：Vue 3、TypeScript、Web Audio/OfflineAudioContext、FastAPI、SQLAlchemy、Alembic。
**规格**：用户附件 96bccc0c-308d-4ab3-9295-6f36c4f39cfe/已粘贴的文本.txt（2026-10-15）。

## 已审计与复用
- TrainingStartGate/useTrainingStartGate：患者校验、取消令牌、3秒倒计时可复用；正式会话在倒计时成功后创建，准备期间只读。
- PianoEngine/samples：本地钢琴采样、Web Audio 时钟；不改旧算法。新合成器复用相同采样表。
- catalogue/recipes/session/useRunner：旧练习完全保留，目录新增曲目入口，独立路由无额外侧栏。
- PianoKeyboard 是双八度；新增 SevenKeyKeyboard，避免修改旧键盘。
- PatientTaskLayout、patientContext 与 taskMode：复用患者身份与退出约定；新舞台固定视口覆盖导航。
- VideoCapturePanel：独立录制保留；新流使用单独显式同意、可中止采集生命周期。
- micro_expression adapter 明确未配置；无真实 FPS/窗口/尺寸/光流/标签证据，禁止宣称已推理。
- 旧 training 表/schema/service 不混入新事件。使用新迁移新增表。

## 全局约束
- 不部署、不清库、不覆盖未跟踪截图/PPT/资料。
- 浏览与配置无需患者；取消倒计时不创建训练。
- 32音：14+18；错键保存且不前进；跳过独立标记；无反应超时失败。
- 左右手是任务指定，不是自动识别。默认60/80/100 BPM，最高120，仅段间变更。
- 正式难度依据个人基线及按键表现，情绪调整仅显式模拟模式；模拟来源与临床数据隔离。
- 摄像头可选明确同意，无模型返回 MODEL_NOT_CONFIGURED，不编造概率。
- 原始事件先保存，音频失败可重试；音频来源 SYNTHESIZED_FROM_KEY_EVENTS。

## 数据契约与分工
前端 song.ts 定义 song_id=two_tigers、version=1、7音阶、两段音符与beats。
原始事件：seq、type(CUE/DOWN/UP/SKIP/PAUSE/RESUME)、segment_index(1/2)、note_index(全局0..31)、time_ms(训练单调时钟)、midi(DOWN/UP)、press_id；区间由首次CUE至最后正确音/跳过及末次释放定义。绝对 started_at 与相对时间共同保留段间等待。
后端创建参数 patient_id、client_request_id、selected_hand、initial_difficulty、song_id、song_version、input_source；返回 id、初始及段落难度。events 为完整可重试快照，服务端校验且复算；GET 历史与详情；完成与音频上传独立。
直播身份经首包token鉴权，绑定已有训练及拥有者；单一在途片段、ACK背压、大小/时长/速率/连接上限、超时，原视频不落盘。未配置模型时不接受无意义视频上传。

## 实施步骤
- [ ] 1. 纯状态机与算法：song.ts、machine.ts、audio.ts，测试14/18、错键、重复按下、释放、暂停、取消、准确率、段间拼接。先运行新增测试确认缺失失败，再实现并运行。
- [ ] 2. 后端：models/guided_song.py、schemas/guided_song.py、services/guided_song_service.py、api/guided_song.py、Alembic。测试未授权/无患者/重试/伪造指标/错误事件/音频/历史。
- [ ] 3. 直播：services/live_emotion_service.py、api/live_emotion.py、emotion/{types,streamClient,useLiveEmotion}.ts。测试未配置/模拟隔离/权限/背压/超时。契约确定前不假装支持真实推理。
- [ ] 4. 视觉与流程：SevenKeyKeyboard、WaveStaffOverlay、GuidedSongStage、GuidedSongPage；SVG合法来源本地保存并记录许可。接入目录、路由、历史、统一启动门。
- [ ] 5. 集成：完整演示→跟弹→段间策略→后段→保存→渲染回放；网络失败保留内存事件并允许重试，退出取消释放摄像头/音频/全屏。
- [ ] 6. npm run test、npm run build、后端pytest；浏览器实际操作并截图PC/平板/手机。真实Android/iOS设备不可用时明确记录，不冒充验证。
- [ ] 7. 分阶段Git提交、docs/guided_song_upgrade_report.md，列出文件、算法、迁移、测试与未解决限制。

## 审查重点
1. 取消与异步准备竞态：signal与运行代次防止迟到创建/摄像头泄漏。
2. 相邻重复音与多指：按下去重、释放配对，单次按下仅前进一音。
3. 最后音符长按：记录最终释放后才渲染，不截断尾音。
4. 网络重试与段间升级：服务端幂等且复算，不信任客户端概率或分数。
5. 页面隐藏/退出/权限挂起：停止声音、停止采集、冻结响应，保留真实时间审计。
