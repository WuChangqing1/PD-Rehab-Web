# 真人素材制作与审核预览（2026-10-13）

## 已完成

- 从发布者标为 Creative Commons Attribution (reuse allowed) 的教学视频制作两段真人视频和六张同源 WebP 图片。
- 坐姿手臂：Canada’s National Ballet School，源片 175–188 秒；13 秒，228499 bytes。
- 扶把伸腿：Sleek Technique - Ballet Fitness，源片 458–465 秒；6.96 秒，132529 bytes。
- H.264 / yuv420p / 25fps / 640px，无音轨，faststart；无变速、无镜像、无动作合成。
- 作者、原作品标题、来源 URL、许可链接、修改说明、源文件及成品 SHA256 均在 frontend/public/ballet-review/manifest.json。NBS 编舞者 Jera Wolfe、Lua Shayenne 的署名保留在 source.json 原描述。
- 独立审核预览：https://ccqspace.site/pd-rehab/ballet-review/ 。未加入训练导航，noindex，不应作为患者指导。

## 尚未完成：患者训练示范替换

两段均 movement_reviewed=false，未改动 demoAssets 的发布门槛。不得将本交付描述为已经替换全部火柴人。

坐姿片段有抬头、躯干运动，节拍与本站抬起—展开—回落不完全一致。站姿片段使用把杆而非椅背，有脚尖外旋。页面逐条注明差异；需要教师或专业指导者决定可否使用或重新拍摄。其他七个动作/模式没有可发布的真人素材。

已浏览源视频全时段的稀疏截图，并对选段逐秒检查；这不等同于完整实时观看或专业动作审核。未虚构人工签字。Kaiser Permanente 及 Quoc Tran 候选没有纳入发布。

依据 docs/upgrade-v2/PD_Rehab_UX_Deep_Upgrade_Package/docs/04_视频素材授权与制作SOP.md 第 8 条：“至少两位审核：开发者技术审核 + 教师/专业指导者动作审核。签名或审查人保留在内部审计记录。”待提供片段编号、适配结论、修改要求、审核人和日期后，才可进入训练发布流程。

## 验证与部署

- npm run test --prefix frontend 通过（219 项）；npm run build --prefix frontend 通过。
- 本次没有后端变化，未重复 pytest；此前 UI/钢琴发布的后端测试结果不算作本次运行。
- 真实 Chrome 在 PC 1440×1000、平板 820×1180、手机 390×844 尺寸检查本地和线上预览：两段视频 currentTime 实际前进、六张图片加载、没有横向溢出、没有页面异常、同时仅播放一段。
- 手机尺寸模拟不是 Android/iOS 真机验证；Safari 未验证。
- 线上两个 MP4 的 SHA256 与本地一致，MIME video/mp4，Range 返回 206；ffprobe 确认无音轨。
- 截图和机器记录：artifacts/ballet-review/；复验脚本：scripts/ballet_media_verify.mjs。
- 增量上传预览目录至 dist 和 dist-under-path；未替换应用 index、未重启服务、未修改数据库。临时上传压缩包已删除；没有创建备份副本。
