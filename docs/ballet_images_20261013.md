# 芭蕾动作配图交付

用户明确授权先用生成图片填充缺失素材。新增 9 张独立 AI 静态人物示意图，覆盖五个动作的全部有效模式：手臂组合、第一位、伸腿、重心转移各坐姿和站姿；浅屈膝仅站姿。

图片位于 frontend/public/assets/ballet/ai-v1/；由内置 image_gen 工具生成，提示词记录于 ballet_image_prompts_20261013.json。并非实拍、临床审核或动态动作演示，不变更原视频发布审核状态。页面显示“AI 生成动作示意”，保留文字步骤及节拍作为动作指导。

代码：illustrations.ts 按动作与模式映射；BalletIllustration.vue 统一图片、标注、加载失败回退和模式切换。ExerciseDemoPanel.vue 与 MovementTrainingPage.vue 将图片接入目录、详情和训练展示。没有后端、算法或数据库修改。

验证：220 项前端测试通过；根路径与 /pd-rehab/ 两种构建通过。真实 Chrome 使用隔离 QA API 在 1440、820、390 宽度逐个选择全部 9 种组合，图片解码通过，训练展示区图片可见，无横向溢出或页面异常。截图及 JSON 位于 artifacts/ballet-images/；线上复验仍使用隔离 API，不向生产数据库写训练数据。非移动真机验证。

部署采用静态资源增量复制及入口原子替换，旧哈希资源保留以供已打开的页面使用。验证后删除本次入口备份与上传压缩包。
