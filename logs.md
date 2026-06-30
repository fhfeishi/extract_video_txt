# 开发日志

## 2026-06-30

### 脚本化收敛

用户希望把仓库从包式工具收敛为后续可汇总的小工具形态，核心需求变成：

```text
audio-file -> markdown text
```

新增：

```text
reaudio_dashscope.py
reaudio_notes.md
```

取舍：

- `reaudio_dashscope.py` 作为当前推荐入口，接受音频或视频输入，负责用 `ffmpeg` 抽取/规范化音频、DashScope ASR、默认 LLM 润色、ASR 缓存、分段、Markdown/txt/srt/json 输出。
- 删除拆分出来的 `reaudio.py`，避免一个固定 DashScope 工具被过度分层。
- `video_text_tool/` 暂不删除，继续作为字幕优先 pipeline 和测试参考。

## 2026-06-07

### 初始目标

用户希望构建一个 Python 小工具，用于快速获得视频的文字版本。主要需求：

- 中文视频为主，允许夹杂英文词和专有名词。
- 纯英文视频需要整理成中文为主的形式。
- 优先考虑本地模型，也可以使用 DashScope API。
- 工具应适合作为个人笔记和知识库构建的前置步骤。

### 本地环境探测

工作目录：

```text
D:\codespace\fhfeishi\extract_video_txt
```

本地模型目录：

```text
E:\local_models
```

发现可用模型：

```text
E:\local_models\asr\iic--speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch
E:\local_models\vad\iic--speech_fsmn_vad_zh-cn-16k-common-pytorch
E:\local_models\punc\iic--punc_ct-transformer_cn-en-common-vocab471067-large
E:\local_models\llm\Qwen3.5-0.8B-Q4_1.gguf
E:\local_models\llm\Qwen3.5-4B-Q4_1.gguf
```

系统工具：

```text
Python 3.13.13
ffmpeg available
ffprobe available
```

注意：全局 Python 是 conda 受管环境，直接 `pip install` 被拦截，因此创建并使用项目内 `.venv`。

### 第一版实现

新增文件：

```text
video_text_tool/__init__.py
video_text_tool/__main__.py
video_text_tool/cli.py
requirements.txt
README.md
.gitignore
```

主要功能：

- `python -m video_text_tool` 作为 CLI 入口。
- 默认先尝试提取容器内字幕流。
- 没有字幕时，使用 `ffmpeg` 抽取音频为 16 kHz mono WAV。
- 支持 FunASR 本地后端。
- 支持 DashScope 云端 ASR 后端。
- 支持 DashScope LLM 将英文转写整理成中文。
- 输出 `txt/srt/json`。
- 增加 `--max-segment-chars` 切分长段。
- 增加 `--subtitle prefer/ignore/only`。
- 引入 Pydantic v2，并拆分为 `models.py`、`media.py`、`asr.py`、`text.py`、`output.py`、`cli.py`。
- 增加 `--list-streams`，用于只查看容器结构。

### DashScope 验证

创建虚拟环境并安装 SDK：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install dashscope
```

截取 30 秒测试音频：

```powershell
ffmpeg -y -v error -ss 0 -t 30 -i audioplayback.mp3 -ac 1 -ar 16000 outputs\sample_30s.wav
```

运行烟测：

```powershell
.\.venv\Scripts\python -m video_text_tool outputs\sample_30s.wav --backend dashscope --subtitle ignore --output-dir outputs\smoke_split --formats txt,srt,json --max-segment-chars 50
```

结果：

```text
outputs\smoke_split\sample_30s.txt
outputs\smoke_split\sample_30s.srt
outputs\smoke_split\sample_30s.json
```

结论：DashScope ASR 能跑通，但对术语有误识别风险。

### 完整音频测试

输入：

```text
audioplayback.mp3
```

时长：

```text
947.86s
```

运行：

```powershell
.\.venv\Scripts\python -m video_text_tool audioplayback.mp3 --backend dashscope --subtitle ignore --output-dir outputs\audioplayback_full --formats txt,srt,json --max-segment-chars 80
```

输出：

```text
outputs\audioplayback_full\audioplayback.txt
outputs\audioplayback_full\audioplayback.srt
outputs\audioplayback_full\audioplayback.json
```

结果：

```text
93 段文本
```

观察到的 ASR 误识别：

```text
Claude -> cloud
token -> 头肯/偷看
GPT -> 植皮T 等音近词
API key -> A P I / key 等不稳定形式
```

后续需要术语词典和 LLM 纠错。

### 原视频容器分析

输入：

```text
videoplaybask.mp4
```

用户说明：这是 `audioplayback.mp3` 对应的原视频，由网页下载工具下载。

检查命令：

```powershell
ffprobe -v error -show_entries stream=index,codec_type,codec_name:stream_tags=language,title -of json videoplaybask.mp4
ffprobe -v error -select_streams s -show_entries stream=index,codec_name,codec_type:stream_tags=language,title -of json videoplaybask.mp4
```

结果：

```text
stream 0: video, h264
stream 1: audio, aac
subtitle stream: none
```

格式信息：

```text
format: mov,mp4,m4a,3gp,3g2,mj2
duration: 947.861333
size: 78533787
bit_rate: 662829
encoder: Lavf61.7.105
```

视频流：

```text
codec: h264
resolution: 1280x720
pix_fmt: yuv420p
bit_rate: 545105
```

音频流：

```text
codec: aac
sample_rate: 48000
channels: 2
bit_rate: 107658
```

结论：该 MP4 没有可提取的软字幕流。

### 硬字幕检查

抽帧命令：

```powershell
ffmpeg -y -v error -ss 00:01:00 -i videoplaybask.mp4 -frames:v 1 outputs\video_probe\frame_001m.jpg
ffmpeg -y -v error -ss 00:05:00 -i videoplaybask.mp4 -frames:v 1 outputs\video_probe\frame_005m.jpg
ffmpeg -y -v error -ss 00:10:00 -i videoplaybask.mp4 -frames:v 1 outputs\video_probe\frame_010m.jpg
```

输出：

```text
outputs\video_probe\frame_001m.jpg
outputs\video_probe\frame_005m.jpg
outputs\video_probe\frame_010m.jpg
```

观察：

- 画面底部存在中文字幕。
- 字幕是画面像素的一部分，不是 subtitle stream。
- 这类字幕需要 OCR，而不是 ffmpeg 直接提取。

### 小修复

修复 `--subtitle only` 语义：

- 之前：没有字幕流时仍可能继续走 ASR。
- 现在：没有内嵌字幕流时明确退出。

验证命令：

```powershell
.\.venv\Scripts\python -m video_text_tool videoplaybask.mp4 --subtitle only --output-dir outputs\subtitle_probe --formats srt
```

结果：

```text
No embedded subtitle stream found in: D:\codespace\fhfeishi\extract_video_txt\videoplaybask.mp4
```

### 当前结论

当前最合理的 pipeline 是：

```text
软字幕/外挂字幕优先
  -> 没有软字幕时，用 ASR 生成主文案
  -> 若视频有硬字幕，用 OCR 辅助纠正术语
  -> 用术语词典/LLM 做后处理
```

对 `videoplaybask.mp4` 这类文件，不能直接提取字幕流。需要依赖音频 ASR，或者进一步开发硬字幕 OCR。

### 下一步建议

- 增加同名外挂字幕扫描。
- 支持多字幕流选择和语言优先级。
- 增加术语词典纠错。
- 实验硬字幕 OCR。
- 研究是否接入 `yt-dlp`，在下载阶段优先拿到平台字幕。

### Pydantic 与 Agent 工作流整理

用户进一步明确：本地模型和 DashScope 云端 API 是两种主要转写方式，通常二选一；代码应该更有条理，并希望使用 Pydantic v2。

完成调整：

```text
video_text_tool/models.py   Pydantic v2 配置与 Segment 模型
video_text_tool/media.py    ffprobe/ffmpeg、字幕解析、音频抽取
video_text_tool/asr.py      FunASR 与 DashScope 后端
video_text_tool/text.py     文本清理、分段、时间格式化
video_text_tool/output.py   txt/srt/json 输出
video_text_tool/cli.py      CLI 参数和 pipeline 编排
```

新增 agent/skill 相关文件：

```text
AGENTS.md
CLAUDE.md
skills/dev-tools-solution/SKILL.md
skills/dev-tools-solution/references/solution-workflow.md
skills/dev-tools-solution/agents/openai.yaml
```

验证：

```powershell
.\.venv\Scripts\python -m compileall video_text_tool
.\.venv\Scripts\python -m video_text_tool --help
.\.venv\Scripts\python -m video_text_tool videoplaybask.mp4 --list-streams
.\.venv\Scripts\python C:\Users\10354\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\dev-tools-solution
.\.venv\Scripts\python -m video_text_tool outputs\sample_30s.wav --backend dashscope --subtitle ignore --output-dir outputs\smoke_pydantic --formats txt,json --max-segment-chars 50
```

结果：

```text
Skill is valid.
DashScope 30s smoke test passed.
```

### 通用初始化模板

新增 `strata.md`，用于以后创建个人知识宫殿小工具仓库时作为起草入口。原先考虑过 `knowledge_project_template.md`，最终改名为更有个人标识感的 `strata.md`。

模板覆盖：

```text
项目初衷
目标用户和使用场景
成功标准
核心需求和非功能需求
首选 pipeline 与兜底 pipeline
技术方案
notes/plan/logs 知识沉淀规范
AGENTS.md 与 CLAUDE.md
skill 沉淀规范
验证和交付 checklist
```

### WSL 主开发环境迁移

用户希望后续主开发放在 WSL，目录为 `~/wslcodespace/`，Windows 侧只保留避免开发和兼容测试用途，并偏好 Python 3.12 与 `uv`。

执行：

```powershell
wsl -e bash -lc 'mkdir -p ~/wslcodespace/extract_video_txt && rsync -av --exclude=.venv --exclude=outputs --exclude=__pycache__ --exclude="*.pyc" --exclude=.vscode /mnt/d/codespace/fhfeishi/extract_video_txt/ ~/wslcodespace/extract_video_txt/'
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && uv venv --python 3.12'
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && uv pip install -r requirements.txt dashscope pyyaml'
```

结果：

```text
WSL project path: /home/baheas/wslcodespace/extract_video_txt
Python: CPython 3.12.13
uv: 0.11.16
ffmpeg/ffprobe: available in WSL
DASHSCOPE_API_KEY: missing in WSL environment
```

验证：

```powershell
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && .venv/bin/python -m compileall video_text_tool'
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && .venv/bin/python -m video_text_tool --help'
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && .venv/bin/python -m video_text_tool videoplaybask.mp4 --list-streams'
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && .venv/bin/python /mnt/c/Users/10354/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/dev-tools-solution'
```

结论：

```text
WSL 侧工程可用。
后续开发以 ~/wslcodespace/extract_video_txt 为准。
需要在 WSL shell 中单独 export DASHSCOPE_API_KEY 才能跑 DashScope ASR。
```

补充：

- 新增 `pyproject.toml`，声明 Python `>=3.12`、核心依赖、DashScope/local/dev 可选依赖和 `video-text-tool` console script。
- `uv sync --extra dashscope --extra dev` 初次失败，因为 setuptools 自动发现到了 `skills/` 和 `video_text_tool/` 两个顶层包。
- 已通过 `[tool.setuptools.packages.find]` 显式只包含 `video_text_tool*` 修复。
- WSL 侧重新执行 `uv sync --extra dashscope --extra dev` 成功。
- 已整理 WSL 侧项目文件权限，保留 `.venv` 自身权限。

最终验证：

```powershell
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && uv run python -m compileall video_text_tool'
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && uv run video-text-tool --help'
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && uv run video-text-tool videoplaybask.mp4 --list-streams'
wsl -e bash -lc 'cd ~/wslcodespace/extract_video_txt && uv run python /mnt/c/Users/10354/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/dev-tools-solution'
```

### Codex 项目目录切换说明

用户确认：Codex 项目目录也应迁移到 WSL 侧 `/home/baheas/wslcodespace/extract_video_txt`，Windows 侧不再作为项目目录。

处理：

```text
当前线程仍由 Codex App 绑定到 D:\codespace\fhfeishi\extract_video_txt。
当前可用工具没有暴露“原地修改当前线程 cwd”的能力。
已将当前线程标题标记为旧 Windows 副本。
已新增 WINDOWS_COMPAT.md，声明 Windows 侧只用于样例保留、同步和兼容测试。
```

后续应在 Codex App 中以 WSL 路径重新打开/创建项目：

```text
/home/baheas/wslcodespace/extract_video_txt
```

### WSL 主仓库文档清理

当前工作目录已经是 WSL 主仓库：

```text
/home/baheas/wslcodespace/extract_video_txt
```

处理：

- 删除 `requirements.txt`，避免和 `pyproject.toml` / `uv.lock` 形成重复依赖入口。
- 删除 `WINDOWS_COMPAT.md`，避免在 WSL 主仓库里继续声明“当前目录是 Windows 副本”。
- 更新 `README.md`、`AGENTS.md`、`notes.md` 中的常用命令，统一为 WSL/uv 口径。
- 清理验证过程中生成的 `extract_video_txt.egg-info/` 和 `video_text_tool/__pycache__/`。

保留：

- `strata.md` 作为通用项目启动模板。
- `skills/dev-tools-solution/` 作为可复用 solution workflow skill。
- `CLAUDE.md` 作为极薄的兼容入口，继续指向 `AGENTS.md`。

### 字幕策略、WSL 路径和测试优化

用户要求继续优化代码，并确认 `source ~/.zshrc` 后 WSL 中能读取 `DASHSCOPE_API_KEY`。验证时只输出了 key 是否存在和长度，没有打印 key 内容。

完成代码调整：

```text
video_text_tool/errors.py   结构化错误类型 ToolError
video_text_tool/models.py   WSL 默认模型根目录、SubtitleConfig
video_text_tool/media.py    外挂字幕扫描、字幕语言/stream 选择、SRT/VTT 解析、ASS/VTT 转换入口
video_text_tool/cli.py      --subtitle-file / --subtitle-lang / --subtitle-stream
video_text_tool/output.py   JSON 增加 source 字段
video_text_tool/asr.py      DashScope/FunASR 错误提示结构化
tests/                      media/text/output 最小 pytest 覆盖
```

WSL 本地模型路径策略：

```text
1. 优先读取 VIDEO_TEXT_TOOL_MODEL_ROOT
2. 自动使用 /mnt/e/local_models
3. 兼容 Windows 侧 E:\local_models 描述
```

验证命令：

```bash
uv sync --extra dashscope --extra dev
uv run python -m compileall video_text_tool tests
uv run pytest -q
uv run video-text-tool --help
uv run video-text-tool videoplaybask.mp4 --list-streams
uv run video-text-tool videoplaybask.mp4 --subtitle only --output-dir outputs/subtitle_only_check
```

结果：

```text
pytest: 8 passed
videoplaybask.mp4: 只有 video/audio stream，没有软字幕流
--subtitle only: 输出结构化错误和下一步建议
```

外挂字幕测试：

```bash
tmpdir=$(mktemp -d)
printf fake > "$tmpdir/demo.mp4"
cat > "$tmpdir/demo.zh.srt" <<'SRT'
1
00:00:00,000 --> 00:00:01,000
你好，外挂字幕。
SRT
uv run video-text-tool "$tmpdir/demo.mp4" --subtitle only --subtitle-file "$tmpdir/demo.zh.srt" --output-dir "$tmpdir/out" --formats txt,json
```

结果：

```text
JSON source: external:/tmp/.../demo.zh.srt
segments[0].text: 你好，外挂字幕。
```

DashScope 云端验证：

```bash
source ~/.zshrc
mkdir -p outputs/smoke_dashscope_10s
ffmpeg -y -v error -ss 0 -t 10 -i audioplayback.mp3 -ac 1 -ar 16000 outputs/smoke_dashscope_10s/sample_10s.wav
uv run video-text-tool outputs/smoke_dashscope_10s/sample_10s.wav --backend dashscope --subtitle ignore --output-dir outputs/smoke_dashscope_10s --formats txt,json --max-segment-chars 60
uv run video-text-tool outputs/smoke_dashscope_10s/sample_10s.wav --backend dashscope --subtitle ignore --translate-to zh --output-dir outputs/smoke_dashscope_translate_10s --formats txt,json --max-segment-chars 60
```

结果：

```text
DashScope ASR passed.
DashScope LLM post-processing passed.
JSON source: asr:dashscope
短样例仍有术语问题：Claude 被识别为 cloud。
```

### 文档职责收敛

用户希望整理过多 Markdown 文件，让项目文档更专业、简洁、高效，同时保留适合 agent 协作的知识沉淀体系。

调整：

- `README.md`：重写为简洁用户手册，只保留安装、使用、输出、验证和边界。
- `AGENTS.md`：重写为 canonical agent guide，明确环境、pipeline、模块边界、验证命令和文档更新规则。
- `strata.md`：从通用空模板改为本项目 launch charter，记录项目为什么存在、输入输出、canonical pipeline、成功标准和长期原则。
- `plan.md`：修正 CLI 入口描述。
- `notes.md`：新增“Agent 友好的文档架构”，沉淀文档分层设计方法。

文档职责模型：

```text
README.md   = how to use
AGENTS.md   = how to work
strata.md   = why this project exists
plan.md     = what next
logs.md     = what happened
notes.md    = what we learned
CLAUDE.md   = compatibility pointer
```

### 新增 strata 中文示例模板

新增 `strata_example.md`，作为可复制到新项目的中文 launch charter 模板。

设计取舍：

- `strata.md` 保持为当前项目已经填写好的启动宪章。
- `strata_example.md` 保存通用中文模板，供后续新项目复制。
- `notes.md` 记录该区分，避免模板内容和项目事实混在一起。

### Skill 分层沉淀

用户希望把“提取视频文案工具开发完成案例”进一步整理成可复用 skill，而不是只留在当前项目文档里。

调整：

- 新增 `skills/video-text-extraction`，专门沉淀视频文案提取工具的开发工作流。
- 保留 `skills/dev-tools-solution` 作为通用小工具工程化 skill，并让它指向更专门的媒体文本 skill。
- `strata.md` 的 `Skill Contract` 从未来占位改为推荐使用 `video-text-extraction`。
- `notes.md` 更新为两层 skill 模型：通用工程化 skill + 媒体文本领域 skill。

结论：

```text
dev-tools-solution      = 小工具工程化和 agent 协作方法
video-text-extraction   = 字幕/ASR/OCR/术语/输出的视频文案方法
```

随后根据命名收敛原则，将 skill 名称从更宽泛的 `media-text-extraction` 收敛为 `video-text-extraction`。当前先围绕一个个具体视频文案提取问题积累，不急着扩大抽象范围。

### Skill 单一化收敛

用户判断这是一个小项目，skill 也应该干净高效，只保留一个真正有用的项目 skill。

调整：

- 删除 `skills/dev-tools-solution`。
- 保留 `skills/video-text-extraction` 作为唯一 skill。
- 更新 `strata.md`、`notes.md` 和 `video-text-extraction/SKILL.md`，去掉两层 skill 模型。

结论：

```text
skills/video-text-extraction = 当前唯一 skill
```

### 2026-06-10 仓库梳理：聚焦音视频转文本

项目定位收敛为单一职责的音视频转文本工具，做一次工业级清理。

删除：

- `rag_pdfs/` 子项目、`tests/test_rag_pdfs.py`、`pyproject.toml` 中的 `pdf-rag` extra 和 `pdf-rag-experiment` 入口，以及 `plan.md`/`notes.md` 中的 PDF RAG 章节。PDF RAG 实验与本工具职责无关，整体移除。
- `video_transcript/` 原型目录。它依赖仓库中不存在的 `configs.config` 和未声明的 `loguru`，无法独立运行；吸收其有价值的设计后删除。
- `git_logs.md`（git push 排障记录）和 `strata_example.md`（跨项目模板），与本项目无关。
- dev 依赖中未被使用的 `pyyaml`。

从 `video_transcript` 吸收进 `video_text_tool` 的设计：

- ASR 结果缓存：新增 `video_text_tool/cache.py`，按文件内容哈希、后端、模型、截取参数键控，缓存写入 `<output-dir>/.cache/`；新增 `--no-cache` 和 `--force`。
- `--max-seconds`：抽音频时用 ffmpeg `-t` 截取前 N 秒，用于烟测和控制云端成本。

验证：

```bash
uv lock
uv run python -m compileall video_text_tool tests
uv run pytest -q
uv run video-text-tool --help
uv run video-text-tool res/videoplaybask.mp4 --list-streams
```

结果：

```text
uv lock 移除 faiss/langchain/pypdf/pyyaml 等 RAG 依赖
compileall passed
pytest: 11 passed（含 3 个新的 cache 测试）
video-text-tool --help passed
res/videoplaybask.mp4: video/audio streams only, no subtitle stream
预置缓存后空 DASHSCOPE_API_KEY 运行 ASR 路径，命中缓存直接产出 txt/srt/json
```
