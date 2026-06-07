# 视频文案提取笔记

## 目标

把视频尽可能可靠地转换成文字版材料，用于笔记、摘要、检索、提示词构建和知识库沉淀。

最优路径不是一上来就 ASR，而是按“已有文本优先”的原则逐级尝试：

```text
外挂字幕文件
  -> 内嵌软字幕流
  -> 平台字幕接口/下载器附带字幕
  -> 画面硬字幕 OCR
  -> 音频流 ASR
  -> LLM/词典后处理
```

## 视频容器里的字幕

`.mp4`、`.mkv`、`.mov` 这类文件通常是容器。容器里可以放多条 stream：

```text
video stream: H.264 / H.265 / AV1
audio stream: AAC / Opus / MP3
subtitle stream: srt / ass / mov_text / webvtt / pgs / dvd_subtitle
metadata: language / title / chapters / encoder
```

字幕大致分三类：

- 软字幕：容器里独立的 subtitle stream，或者同名外挂 `.srt/.ass/.vtt`。这是最值得优先提取的文本来源。
- 图片字幕：例如 `pgs`、`dvd_subtitle`，虽然是字幕流，但不是文本，需要 OCR。
- 硬字幕：已经烧进视频画面像素里，容器里看不到字幕流，也需要 OCR。

## 当前样例结论

`videoplaybask.mp4` 来自网页下载工具。检查结果：

```text
stream 0: video, h264, 1280x720
stream 1: audio, aac, stereo, 48kHz
subtitle stream: none
duration: 947.86s
encoder: Lavf61.7.105
```

它没有可提取的软字幕流。画面底部能看到字幕，但这些字幕是硬字幕，已经成为视频画面的一部分。

`audioplayback.mp3` 是对应音频文件，已用 DashScope ASR 跑完整转写，生成了 `txt/srt/json`。

## 常用命令

查看容器结构：

```powershell
ffprobe -v error -show_streams -of json "video.mp4"
```

只查看字幕流：

```powershell
ffprobe -v error -select_streams s -show_entries stream=index,codec_name,codec_type:stream_tags=language,title -of json "video.mp4"
```

使用项目 CLI 查看 stream 摘要：

```bash
uv run video-text-tool video.mp4 --list-streams
```

查看视频基本信息：

```powershell
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate,duration,bit_rate -of json "video.mp4"
```

查看音频基本信息：

```powershell
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels,duration,bit_rate -of json "video.mp4"
```

提取第一条软字幕流：

```powershell
ffmpeg -i "video.mkv" -map 0:s:0 "subtitle.srt"
```

抽取音频为 ASR 友好的 WAV：

```powershell
ffmpeg -y -i "video.mp4" -vn -ac 1 -ar 16000 -f wav "audio.16k.wav"
```

抽帧检查是否有硬字幕：

```powershell
ffmpeg -y -ss 00:05:00 -i "video.mp4" -frames:v 1 "frame.jpg"
```

## 当前 CLI 用法

自动模式：先尝试同名外挂字幕和内嵌软字幕，没有字幕时走 ASR。

```bash
uv run video-text-tool video.mp4 --output-dir outputs
```

只检查/提取字幕，不做 ASR：

```bash
uv run video-text-tool video.mp4 --subtitle only --output-dir outputs
```

指定外挂字幕：

```bash
uv run video-text-tool video.mp4 --subtitle only --subtitle-file video.zh.srt --output-dir outputs
```

优先中文字幕或指定内嵌字幕 stream：

```bash
uv run video-text-tool video.mkv --subtitle-lang zh --output-dir outputs
uv run video-text-tool video.mkv --subtitle-stream 2 --output-dir outputs
```

强制忽略字幕，使用 DashScope ASR：

```bash
uv run video-text-tool video.mp4 --subtitle ignore --backend dashscope --output-dir outputs
```

纯英文视频转成中文笔记素材：

```bash
uv run video-text-tool english.mp4 --backend dashscope --translate-to zh --output-dir outputs
```

控制分段长度：

```bash
uv run video-text-tool video.mp4 --max-segment-chars 80
```

## 已用工具

- `ffprobe`：分析容器结构、stream 类型、编码、时长、码率、语言标签。
- `ffmpeg`：提取字幕流、抽取音频、转 16 kHz WAV、抽帧。
- `DashScope ASR`：云端语音识别兜底，已在 WSL 中验证 10 秒样例。
- `DashScope LLM`：由 `--translate-to zh` 触发，已验证调用链路，但短样例中文内容基本保持原样。
- `FunASR/Paraformer`：本地中文优先 ASR 方案，当前机器已有模型，后续可补安装依赖并验证。
- `Pydantic v2`：定义运行配置、后端配置、输出配置和文本片段结构，让 CLI 参数和内部 pipeline 更清晰。
- `Python CLI`：项目自己的流水线入口，负责串联字幕探测、音频抽取、ASR、分段、输出。

## 现成工具参考

- `FunASR`：中文生态强，适合中文夹英文、标点、VAD、说话人分离等。
- `faster-whisper`：Whisper 的高性能实现，适合多语言 ASR。
- `WhisperX`：适合词级时间戳、对齐、说话人分离。
- `Whishper`：开源 Web UI，适合批量转写和人工校对。

## 核心判断

ASR 是强兜底，但不是最优先方案。更聪明的提取策略应该先把视频文件、同名字幕文件、平台字幕接口里的已有文本用尽，再用 ASR/OCR 补缺。

## 当前代码能力

- WSL 下默认优先使用 `/mnt/e/local_models` 作为本地模型根目录，也可用 `VIDEO_TEXT_TOOL_MODEL_ROOT` 覆盖。
- 支持同名外挂字幕扫描：`.srt/.ass/.vtt`，包含 `video.zh.srt`、`video.en.srt` 等命名。
- 支持 `--subtitle-file`、`--subtitle-lang`、`--subtitle-stream`。
- JSON 输出包含 `source` 字段，用于追溯文本来源。
- 错误提示包含标题、细节和下一步建议。
- `media/text/output` 已有最小 pytest 覆盖。

## Agent 友好的文档架构

一个适合长期和 agent 协作的小工具仓库，不一定要把所有信息塞进一个 `README.md` 或 `CLAUDE.md`。更好的做法是按“读者”和“时间稳定性”分层。

推荐分工：

```text
README.md   = how to use
AGENTS.md   = how to work
strata.md   = why this project exists
plan.md     = what next
logs.md     = what happened
notes.md    = what we learned
CLAUDE.md   = compatibility pointer
```

核心原则：

- `README.md` 面向用户，只放安装、运行、输出、边界。不要放长篇开发过程。
- `AGENTS.md` 面向 agent，只放当前工程事实、模块边界、验证命令、文档更新规则。
- `strata.md` 是项目 launch charter，记录项目为什么存在、解决哪类问题、默认 pipeline、成功标准和长期原则。
- `plan.md` 是状态和路线图，允许重写和调整优先级。
- `logs.md` 是证据链，只追加有价值的命令、实验、结论，不追求像 README 一样整洁。
- `notes.md` 是稳定知识库，沉淀已经验证过、可复用的判断规则和设计方法。
- `CLAUDE.md` 如果存在，最好只是指向 `AGENTS.md`，避免维护两套 agent 规范。

判断内容放哪里：

```text
用户要照着运行            -> README
agent 接手必须遵守        -> AGENTS
项目长期为什么这样做      -> strata
下一步开发什么            -> plan
今天试了什么、结果如何    -> logs
以后别忘的经验和方法      -> notes
```

这种结构的好处：

- 降低重复：每个文件只有一个职责。
- 降低漂移：权威入口明确，`AGENTS.md` 管 agent，`README.md` 管用户。
- 方便复盘：临时过程留在 `logs.md`，稳定结论再迁移到 `notes.md`。
- 适合 agent：agent 先读 `AGENTS.md`，再按需要读 `strata.md`、`plan.md`、`notes.md`。

`strata` 这个名字适合表达“层理/地层”的感觉：一个项目不是一次性脚本，而是由意图、工具、实验、知识和 reusable workflow 一层层沉淀出来的 solution。

`strata_example.md` 是可复制到新项目的中文示例模板；当前项目自己的 `strata.md` 应该保持为本项目已经填写好的 launch charter。这样可以避免“模板”和“项目事实”混在一个文件里。

## Strata 与 Skill 的关系

`strata.md` 可以连接 skill，但不应该承载 skill 的完整内容，也不应该负责生成 skill。

更合理的分工：

```text
strata.md   = 本项目为什么存在、需要哪类 agent 能力
AGENTS.md   = 本仓库 agent 具体怎么工作
skill       = 跨项目可复用的方法、流程、判断规则
plan.md     = 当前项目下一步做什么
logs.md     = 实验和执行证据
notes.md    = 稳定经验沉淀
```

所以 `strata.md` 里适合放一个很短的 skill contract：

- 当前项目推荐使用哪些 skill。
- 为什么这些 skill 能帮助项目推进。
- 哪些知识应该沉淀回 skill。
- 哪些项目事实必须留在 repo 文档里。

核心判断：

```text
strata 连接 skill，而不是替代 skill。
```

`strata.md` 像项目宪章，告诉 agent：这个项目属于哪类问题，需要哪些能力。skill 像可复用能力模块，告诉 agent：遇到这类问题，应该怎样推进。

当前阶段只保留一个干净有用的 `video-text-extraction` skill。这个项目很小，不需要额外维护通用工程化 skill；先围绕“字幕优先、ASR/OCR 兜底、术语纠错、时间戳输出、知识库文案生成”等视频文案提取问题慢慢积累。

判断一个经验是否应该进入 skill：

- 只对当前仓库有效，放入 `AGENTS.md`、`plan.md`、`logs.md` 或 `notes.md`。
- 对未来同类项目也有效，提炼后放入 skill。
- 仍在实验中，先放 `logs.md`。
- 已经反复验证、能指导决策，沉淀到 `notes.md`，必要时再推广到 skill。

Skill 的成熟不是一次写出来的，而是通过真实任务迭代出来的。好的路径是先用一个轻量 skill 指挥 2-3 个真实项目或功能，再观察 agent 是否仍然反复犯同类错误；如果会，就把触发描述、控制点、检查清单或脚本补进 skill。
