# P0 · 芭蕾示范视频素材缺口报告

审计时间：2026-10-12
结论：**部分可做。2 个候选中的 1 个已成功下载；仍需人工动作审核，未审核前不得上线。**

---

## 1. 升级包内实际有什么

```
assets/ballet_asset_manifest.json   5.8 KB  ← 9 个条目，全部 PENDING_MEDIA_REVIEW
assets/source_candidates.csv        1.2 KB  ← 3 个候选链接
scripts/process_ballet_clips.py     4.9 KB  ← 裁剪工具（不下载、不审核、不标记通过）
```

**升级包内没有任何视频文件。** manifest 里 9 个条目的 `video_path` / `poster_path`
全是 `null`，`license_verified` 与 `movement_reviewed` 全是 `false`。

## 2. 网络与工具可用性实测

| 项 | 结果 |
| --- | --- |
| `ffmpeg` | ✅ `D:\App\Middle\TansferMP4ToMP3\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe` |
| `ffprobe` | ✅ 同目录 |
| Wikimedia 可达 | ✅ HEAD 200（首次） |
| **SRC-PLIE-01 下载** | ✅ **成功**，868 406 bytes |
| **SRC-TENDU-01 下载** | ❌ **失败，三个网络都试过**（见下） |
| SRC-DEMI-ANIM-01 | 未尝试——3D 动画，doc 04 明确「不适合作为真人患者扶椅演示」 |

#### SRC-TENDU-01 的下载尝试记录

| # | 方式 | 结果 |
| --- | --- | --- |
| 1 | 本机 `Invoke-WebRequest` | HTTP 429（Wikimedia bot 限流） |
| 2 | 本机 `curl` + 描述性 User-Agent + 5 次退避重试 | `curl (35) Recv failure: Connection reset`，随后仍 429 |
| 3 | **服务器**（不同 IP）`curl` | `error:0A000126:SSL routines::unexpected eof while reading`——服务器无外网出口（与无法访问 GitHub 一致） |

三次失败、三种网络，**该候选目前取不到**。未取得即未观看，未观看即未审核。
这不影响其它结论，但意味着 `BALLET_TENDU / STANDING_SUPPORTED` 连技术审核都做不了。

已下载文件的真实探测结果：

```
SRC-PLIE-01.webm   868406 bytes
  video: vp8  960x540  2997/100 fps
  audio: vorbis
  sha256: 60385318167FDF58B8AE6883D0638FC9C179EF073D969D10FCC51A9F48740E75
```

存放位置：`private/source_videos/`（**已 gitignore，不进 Public 仓库**）。

## 3. 逐动作缺口

| 动作 | 模式 | 候选 | 状态 | 说明 |
| --- | --- | --- | --- | --- |
| `BALLET_PORT_DE_BRAS` | SEATED | 无 | ❌ **无候选** | 需自录或另找 |
| `BALLET_PORT_DE_BRAS` | STANDING_SUPPORTED | 无 | ❌ **无候选** | 需自录或另找 |
| `BALLET_FIRST_POSITION` | SEATED | 无 | ❌ **无候选** | 坐姿上身改编版，市面几乎没有对应素材 |
| `BALLET_FIRST_POSITION` | STANDING_SUPPORTED | 无 | ❌ **无候选** | 且标准第一位足外旋对 PD 患者不安全 |
| `BALLET_TENDU` | SEATED | 无 | ❌ **无候选** | 坐姿伸膝改编版，需自录 |
| `BALLET_TENDU` | STANDING_SUPPORTED | SRC-TENDU-01 | ⚠️ **下载被限流** | 待重试 |
| `BALLET_DEMI_PLIE` | STANDING_SUPPORTED | SRC-PLIE-01 | ⚠️ **已下载，未审核** | doc 04 提示「未必符合扶椅小幅屈膝要求」 |
| `BALLET_WEIGHT_SHIFT` | SEATED | 无 | ❌ **无候选** | 需自录 |
| `BALLET_WEIGHT_SHIFT` | STANDING_SUPPORTED | 无 | ❌ **无候选** | 需自录 |

**9 个「动作 × 模式」组合中，只有 2 个有候选，其中 1 个已下载、0 个已审核。**

## 4. 为什么不能直接上线（doc 04 与我实测的共同结论）

1. **动作安全**：标准芭蕾 `plié` 与 `first position` 演示的是大幅足外旋与较深屈膝，
   doc 03 明确禁止 PD 患者照做，必须裁出安全的浅范围段并经专业指导者审核。
2. **模式错配**：`SRC-PLIE-01` 是**站姿无扶椅**教学；我们的 Demi-Plié 只支持
   `STANDING_SUPPORTED`（扶固定椅）。用无扶椅视频当扶椅示范是错误素材。
3. **授权义务**：`CC BY-SA 3.0` 的裁剪属于**衍生作品**，必须署名 + 链接来源 + 许可，
   并以相同/兼容许可分享。doc 04 要求在非干扰位置提供鸣谢入口。
4. **肖像风险**：不得让普通舞者被暗示为 PD 患者。
5. **坐姿版不能用站姿视频冒充**（doc 03 明文）。

## 5. 本轮的处理策略

按 doc 04「推荐优先级」执行：

> 项目组获授权自行录制 ＞ 确认开放授权且动作完全匹配的片段 ＞ 仅展示静态安全动作示意

因此：

1. **已有候选的动作**：重试下载 → `ffprobe` + 逐秒 contact sheet → **人工看片**
   标注 in/out → 生成无声 H.264 循环 MP4 + poster → 填写 manifest →
   但仍标记 `movement_reviewed=false`，**等待老师/专业指导者签字**。
2. **无候选的动作**：**明确标记 BLOCKED**，不放任何视频，
   也不拿别的动作的视频顶替；卡片显示「暂无视频示范」，
   并使用已有的静态动作分解示意（不伪装成真人视频）。
3. 卡片封面：有视频的用视频抽帧；无视频的用一个**明确标注为示意**的静态图，
   不冒充真人示范。

---

## 6. 播放器本身已验证（用一次性 fixture）

因为所有动作当前都解析为静态示意，**播放器的视频分支从来没有运行过**。
如果老师审核通过的片段到位，它第一次运行就是在患者面前——这不能接受。

因此用一段**已被判为不可临床使用**的素材做了一次**临时播放验证**
（写入 `public/` → 翻一条 manifest → 验证 → **立刻全部还原**。
规则测试断言「可发布条目为 0」，还原失手会让测试挂掉，而不是悄悄上线）：

| 检查项 | 结果 |
| --- | --- |
| `<video muted loop playsinline preload="metadata" poster>` | ✅ 全部正确 |
| 实际播放并推进（t 0 → 1.47 s） | ✅ |
| 循环 | ✅ `loop = true` |
| 静音（不与节拍器抢音频） | ✅ `muted = true` |
| 播放/暂停按钮文案切换 | ✅ 播放 → 暂停 |
| 版权署名（作者 + 许可 + 源页链接） | ✅ 正确渲染且可点 |
| 子路径 URL 构造 | ✅ 走 `BASE_URL`，未硬编码根路径 |
| 加载失败时的回退 | ✅ 退回静态示意并说明原因，不留破图 |
| 患者页示范区 | ✅ 现在**真的渲染 `<video>`**，标签显示「视频」而非「示意」 |
| 患者页与摄像头区分离 | ✅ 动作示范 / 录制动作（您的动作）各自独立 |

还原后确认：`public/assets` 已删除、manifest 与 git 一致、可发布条目回到 **0**。

### 6.1 顺带修掉一个真实缺陷

上表「患者页示范区」一行原本是**不通过的**：患者页示范区**从来没有渲染 `<video>`**，
只渲染静态示意图，但下方文字写着「示范视频循环播放中，没有声音」。也就是说：
**界面告诉患者"正在播放示范视频"，而屏幕上是一张静态图**；标签也无条件写着「示意」。

已修：解析为 VIDEO 时真正渲染 `<video muted loop playsinline>` 并显示「视频」标签。

### 6.2 重要：本机 Chromium 无法解码 H.264 —— 这是**验证环境限制**，不是产品缺陷

用 SOP 脚本的标准参数（`libx264 -crf … -pix_fmt yuv420p -movflags +faststart`）
产出的 MP4，在本机 Playwright Chromium 中报：

```
DEMUXER_ERROR_NO_SUPPORTED_STREAMS: FFmpegDemuxer: no supported streams
```

逐项排查确认**文件本身完全正常**（`h264 High profile, level 3.0, yuv420p, avc1, 640×360, 25fps`），
问题在浏览器：

| `canPlayType` | 结果 |
| --- | --- |
| `video/mp4; codecs="avc1.42E01E"` | `""`（**不能播**） |
| `video/mp4; codecs="avc1.64001e"` | `""`（**不能播**） |
| `video/webm; codecs="vp8"` | `probably` |
| `video/webm; codecs="vp9"` | `probably` |

UA 为 `HeadlessChrome/139` —— **Playwright 自带的 Chromium 不含 H.264 等专有编解码器**。
同一段内容转成 VP9/WebM 后立刻正常播放。

**这个结论必须写下来**：

> 在本机这套 Playwright Chromium 里跑「视频能不能播」的检查，**对 MP4 一律是假阴性**。
> 要验证 MP4 播放必须换用带专有编解码器的 Chrome/Edge，或用真机浏览器。
> **不要据此认为 SOP 产出的 MP4 有问题——它是标准编码。**

**由此提出的一条建议（未实施）**：doc 03 提到「手机走低码率 MP4/H.264，**另可 WebM**」，
但 `process_ballet_clips.py` 目前只产出 MP4。若要让「任何浏览器都能播」成立，
应同时产出 WebM 并在 `<video>` 内提供 `<source>` 回退。
本轮**没有**加这个回退，因为管道尚不产出 WebM 文件，加了只会产生 404 请求。

---

## 7. 需要你提供的

- 老师/康复指导者对 **5 个动作 × 支持模式**的动作审核意见（哪些可放、哪些要改范围）；
- 若走自录路线：一次标准化教学片拍摄（同一机位、同一服装、有无扶椅各一版）；
- 对 `CC BY-SA 3.0` 素材的**署名与许可文字**是否接受放在「资源来源/鸣谢」入口的确认。
