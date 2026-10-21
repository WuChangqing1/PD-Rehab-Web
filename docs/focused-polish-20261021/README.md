# 定向优化验收记录

代码提交：`15a4415a22b9c7dcf2425350625d0c146e20bce0`。验收跨 2026-10-21 至 2026-10-22。

## 本轮改动

- 移除公共面包屑重复标题，患者条、资料标题和患者卡片不再显示内部编号/未知摘要；编号存储与自动分配保留。
- 评估中心采用问诊、面部关键点、手指对指三个真实图片封面，统一比例、按钮底部对齐；图片来源入口保留。
- 小明对应已验证的预置仿真患者。补充脚本只修改该预置患者的资料；其他患者只追加带来源标记的仿真历史，不覆盖原记录。
- 日历仅显示完成记录；固定六行，双栏底部对齐，右侧内部滚动且隐藏滚动条。
- 同一患者同一北京时间日期最多一个进行中的钢琴基础测试/钢琴/曲目/芭蕾任务；支持显式清除。并发、幂等、倒计时取消、迟到响应和取消后结果写入受到保护。
- 无数据库结构迁移、无模型/真实测量算法改动。

## 验证

- `npm --prefix frontend run test`：292 passed。
- `npm --prefix frontend run build`：通过。
- `VITE_BASE=/pd-rehab/` 子路径构建：通过。
- 后端完整 `pytest backend/tests`：480 passed，1 skipped；2 条既有警告。
- 新增安全用例验证 SQLite 并发只允许一个启动胜者，后续清除不会伪造完成，迟到芭蕾分析不能写回，重复补充不增殖记录，发布摘要能拒绝旧结果被改写。
- 浏览器：1920、1440、1280、1024、768、390、375 宽度，无横向溢出，三张图片均加载。桌面同排按钮底部一致。
- 有记录日期的日历与右卡均高 671.92px，底部坐标均 924.69px；无记录日期也保持对齐。
- 浏览器实际走通身份倒计时、注册训练、离开后显示进行中、确认清除后卡片消失；患者资料不暴露内部来源 JSON。
- 独立代码复核后修正两处 MySQL 一致性读问题；本轮未运行 MySQL 实机并发测试。

仿真数据保留 `SEED_DEMO`、算法版本与原始输入来源，界面以“仿真”区分；未生成面部模型预测或临床诊断/疗效结论。生产严格空患者先由发布脚本重新检查，不能按资料不完整直接删人。

## 截图

- [评估中心 PC](assessment-pc.png)
- [评估中心平板](assessment-768.png)
- [评估中心手机](assessment-390.png)
- [有训练记录的日历](calendar-with-records.png)
- [无记录日期](calendar-empty-date.png)
- [手机日历](calendar-phone.png)
- [进行中训练入口](pending-training.png)
- [患者资料](patient-detail.png)
- [趋势分析](trends-pc.png)

图片许可及裁剪记录见 `frontend/public/images/assessment-20261021/SOURCES.html`。

## 修改文件

```text
backend/app/api/active_training.py
backend/app/api/router.py
backend/app/services/active_training_service.py
backend/app/services/followup_service.py
backend/app/services/guided_song_service.py
backend/app/services/piano_service.py
backend/app/services/pose_service.py
backend/tests/test_active_training.py
backend/tests/test_focused_database_guard.py
backend/tests/test_piano_api.py
backend/tests/test_polish_patient_data.py
backend/tests/test_pose_api.py
docs/superpowers/plans/2026-10-21-focused-polish.md
frontend/public/images/assessment-20261021/SOURCES.html
frontend/public/images/assessment-20261021/comprehensive.webp
frontend/public/images/assessment-20261021/face.webp
frontend/public/images/assessment-20261021/finger.webp
frontend/src/components/ActiveTrainingNotice.vue
frontend/src/components/ActivityCalendar.vue
frontend/src/components/AssessmentArtwork.vue
frontend/src/components/PatientCard.vue
frontend/src/components/PatientSelector.vue
frontend/src/components/PatientTaskLayout.vue
frontend/src/components/SelectedPatientBar.vue
frontend/src/components/TrainingStartGate.vue
frontend/src/composables/useTrainingStartGate.ts
frontend/src/followup/calendar.ts
frontend/src/layouts/MainLayout.vue
frontend/src/pages/DashboardPage.vue
frontend/src/pages/FollowUpPage.vue
frontend/src/pages/MovementTrainingPage.vue
frontend/src/pages/PatientDetailPage.vue
frontend/src/pages/PatientsPage.vue
frontend/src/pages/PianoTrainingPage.vue
frontend/src/pages/TrainingHubPage.vue
frontend/src/piano/guided-song/useGuidedSong.ts
frontend/src/training/activeTraining.ts
frontend/src/training/startController.ts
frontend/tests/defect02_interaction.test.ts
frontend/tests/guided_controller.test.ts
frontend/tests/training_start.test.ts
scripts/focused_database_guard.py
scripts/focused_deploy_20261021.sh
scripts/polish_patient_data.py
scripts/seed_followup_showcase.py
```
