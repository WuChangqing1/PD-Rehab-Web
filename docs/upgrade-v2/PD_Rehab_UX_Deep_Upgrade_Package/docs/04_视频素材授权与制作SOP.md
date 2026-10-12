# 04 · 芭蕾视频素材采集、观看审核、裁剪与发布 SOP

## 状态说明

本包内的公开视频为**候选源**，并非完成剪辑的视频：本次运行环境无法从外网成功下载二进制视频，且尚未逐帧审核具体动作。因此目前所有候选的 `movement_reviewed=false`。Harness 在具备网络的视频处理环境中执行下载与审片，按当前清单核验授权后生成最终视频；无法合格取得的动作优先拍摄原创示范，不能随便截取 YouTube/B站视频上线。

## 已核实候选（均为普通舞蹈教学，不保证适用于 PD）

| 候选编号 | 资料页（不是直接媒体二进制 URL） | 描述 | 授权状态 | 适合做什么 |
|---|---|---|---|---|
| SRC-TENDU-01 | https://commons.wikimedia.org/wiki/File:Tendu,_ballet_technique_tutorial.webm | 第一位前/侧/后 Tendu 教学，16s | 页面注明 CC BY-SA 3.0，作者 Tcshaw427 | **仅候选**，剪出安全幅度单次前/侧伸腿；需动作专家审核 |
| SRC-PLIE-01 | https://commons.wikimedia.org/wiki/File:Plié,_ballet_technique_tutorial.webm | 第一位 Plié 教学，13s | CC BY-SA 3.0，作者 Tcshaw427 | **仅候选**，未必符合扶椅小幅屈膝要求 |
| SRC-DEMI-ANIM-01 | https://commons.wikimedia.org/wiki/File:Demi_plié.ogv | 6.3s，3D动画演示 | CC BY-SA 3.0，作者/归属见源页 | 仅用于了解动作，不适合作为真人患者扶椅演示；如引用必须标明动画性质 |

可进一步检索 Pexels/其他素材库，但每个具体视频需**逐条记录作品链接、原作者、许可证及人物使用风险**；Pexels 授权说明 https://www.pexels.com/legal-pages/license/ 允许网站/APP使用和修改，但禁止虚构素材中人物对产品的认可，且不能以对人物不利方式呈现。用途涉及神经系统疾病时尤其不应把普通舞者暗示为 PD 患者。

### Creative Commons 使用注意

- Commons 视频为 `CC BY-SA` 时，剪裁/改编属于衍生作品，必须适当署名、链接来源与许可，并按相同或兼容许可处理改编视频；具体分享方式核查 `https://creativecommons.org/licenses/by-sa/3.0/`。
- 可在“资源来源/鸣谢”或视频信息小入口履行版权声明，无需用巨大的法律文字遮挡患者的训练界面。
- 不得未经授权截取临床机构、医院、专业舞团、商业教学课或社交平台视频，尤其避免从受版权保护的视频下载、裁切后直接放到 Public GitHub。
- **推荐优先级**：项目组获授权自行录制标准化教学片（更符合病人安全需求） ＞ 确认开放授权且动作完全匹配的片段 ＞ 仅展示静态安全动作示意。不要为了“必须五段视频”而使用错误动作。

## 按每一个 `exercise_key + execution_mode` 审核

1. 验证该模式确实支持，当前 Demi-Plié 坐姿不支持。
2. 录制/授权视频是否完整展示开始-动作-回位的一次循环。
3. 是否穿着便于辨别关节位置的服装，腿部/躯干无大面积遮挡。
4. 是否与软件提示/节拍节奏相匹配，且站姿有安全支撑。
5. 是否避免高难度芭蕾旋转、踮脚、跳跃、深蹲、脚极端外旋。
6. 是否有视频源许可证、原始 URL、作者、下载时间、SHA256。
7. 是否明确示范者不是被认定为患有某种疾病的人。
8. 至少两位审核：开发者技术审核 + 教师/专业指导者动作审核。签名或审查人保留在内部审计记录。

## 必须先看完整视频再决定裁剪段

使用 `ffprobe` 获取时间、FPS、尺寸、格式；利用 `ffmpeg` 生成按每秒采样的 contact sheet 供审片；**关键步骤不可只凭标题自动认定视频可用**。检查动作开始帧、结束帧、中途是否有错误示范/其他动作/切镜。

建议处理工序：

```text
许可与动作筛选
→ 下载到本地 private/source_videos
→ sha256、ffprobe、截图/contact sheet
→ 人工标注安全的 in/out 时间戳
→ 裁剪出一整个动作循环（不是随便前5秒）
→ H.264 mp4 + 无音频
→ 抽 poster 并转 WebP / JPG
→ QC：ffprobe、关键帧、循环跳切、手机播放
→ 两类审核签字
→ asset manifest 状态设为 APPROVED
→ 进入 frontend/public/assets/ballet/
```

### 简单 FFmpeg 命令范例

```bash
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,avg_frame_rate -of json input.webm
ffmpeg -ss 00:00:02.200 -i input.webm -t 00:00:06.400 -an -vf "fps=25,scale=1280:-2:flags=lanczos,format=yuv420p" -c:v libx264 -crf 24 -preset medium -movflags +faststart tendu-standing-loop.mp4
ffmpeg -ss 00:00:03.700 -i tendu-standing-loop.mp4 -frames:v 1 -vf "scale=960:-2" tendu-standing-poster.jpg
```

上例时间是 **FFmpeg 语法演示，不是已审查并确定的源视频裁剪时间**；不得拿来直接做产品视频。

也提供 `scripts/process_ballet_clips.py`：使用本地授权源文件 + 人工审核起止时间，生成循环 MP4 和 poster，并输出 sha256/QC 元数据。

## 发布要求

- 统一命名 `ballet_<key>_<mode>_v1.mp4` 和 `_poster.webp`；资产名 ASCII，避免 Windows/Linux URL 不一致。
- 同一个动作卡 poster 必须从同一模式的视频中抽帧；不允许从站姿视频抓图充当坐姿版。
- 页面上 `<video muted loop playsinline preload="metadata" poster="...">`，切换动作时销毁旧 `<video>` 和释放引用。
- 必须符合 `/pd-rehab/` 静态路径；不写死根路径 `/assets/...` 导致线上404。
- 视频缓存可加 `Cache-Control`，文件 URL 随版本变更；支持 Range 请求与合理 MIME (`video/mp4`, `image/webp`)；无效资源不应抛用户不可读错误。
- 实际播放时应检查 PC Chrome、Android Chrome 和 iPhone Safari；移动网络下控制体积，建议一段展示环时 1–4MB 以内为优先目标（取决于长短，不强制假定）。

## 没有视频时正确回退

未获授权、视频动作不符、模式不符或资源不可达：**不使用错误视频顶替**。动作可在医生工作区标记“暂无视频示范”，如果该任务仍可安全执行则显示已审核的分解动作图；如果缺少必需指导，则禁用启动并记录阻塞。不得把静态 SVG 伪装成已经实现的真人视频。
