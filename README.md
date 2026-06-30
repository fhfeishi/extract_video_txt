# extract_video_txt

本地优先的视频/音频文案提取工具。当前推荐入口是单文件脚本 `reaudio_dashscope.py`：输入一个音频或视频文件，脚本内部自动抽成临时音频，借助 DashScope ASR 和 LLM 输出润色后的 Markdown 文本，适合后续汇总到个人小工具合集。

旧包式 CLI `video-text-tool` 仍保留，作为字幕优先 pipeline、测试和后续重构参考。

## Quick Start

```bash
cd ~/wslcodespace/extract_video_txt
uv sync --extra dashscope --extra dev
source ~/.zshrc
uv run python reaudio_dashscope.py res/audioplayback.mp3 --output-dir outputs/reaudio
```

默认输出：

```text
outputs/reaudio/audioplayback.md
outputs/reaudio/audioplayback.json
```

只转写前 10 秒，用于烟测和控制云端成本：

```bash
uv run python reaudio_dashscope.py res/audioplayback.mp3 --max-seconds 10 --output-dir outputs/reaudio_smoke
```

默认会转写并润色为中文 Markdown；如果只要 ASR 原文，可跳过润色：

```bash
uv run python reaudio_dashscope.py audio.mp3 --no-polish --formats md,json --output-dir outputs/reaudio
```

需要字幕文件时：

```bash
uv run python reaudio_dashscope.py audio.mp3 --formats md,srt,json --output-dir outputs/reaudio
```

也可以直接传视频文件；`reaudio_dashscope.py` 会用 `ffmpeg` 提取音频流后再 ASR，不会把视频画面、字幕探测、OCR 纳入这个轻量脚本：

```bash
uv run python reaudio_dashscope.py video.mp4 --output-dir outputs/reaudio
```

更多开发取舍见 `reaudio_notes.md`。

## Legacy Pipeline

包式 CLI 按“已有文本优先”的策略工作：

```text
外挂字幕
  -> 内嵌文字字幕
  -> ASR
  -> 可选 LLM 中文整理
```

适合把课程、播客、公开视频等素材转换成可读、可检索、可继续加工的 `txt/srt/json`。

## Setup

主开发和运行环境在 WSL：

```bash
cd ~/wslcodespace/extract_video_txt
uv venv --python 3.12
uv sync --extra dashscope --extra dev
```

系统依赖：

```bash
ffmpeg -version
ffprobe -version
```

DashScope 需要环境变量：

```bash
source ~/.zshrc
# or
export DASHSCOPE_API_KEY="sk-..."
```

本地 FunASR 后端可选：

```bash
uv sync --extra local --extra dev
```

WSL 默认优先查找 `/mnt/e/local_models`，也可以显式指定：

```bash
export VIDEO_TEXT_TOOL_MODEL_ROOT=/mnt/e/local_models
```

## Usage

检查媒体流：

```bash
uv run video-text-tool res/videoplaybask.mp4 --list-streams
```

自动模式：优先字幕，无字幕时走 ASR：

```bash
uv run video-text-tool video.mp4 --output-dir outputs
```

强制 DashScope ASR：

```bash
uv run video-text-tool video.mp4 --subtitle ignore --backend dashscope
```

纯英文或中英混合内容，转写后整理为中文素材：

```bash
uv run video-text-tool video.mp4 --backend dashscope --translate-to zh
```

指定字幕：

```bash
uv run video-text-tool video.mp4 --subtitle only --subtitle-file video.zh.srt
uv run video-text-tool video.mkv --subtitle-lang zh
uv run video-text-tool video.mkv --subtitle-stream 2
```

控制分段长度：

```bash
uv run video-text-tool video.mp4 --max-segment-chars 70
```

只转写前 N 秒，用于烟测或控制云端成本：

```bash
uv run video-text-tool video.mp4 --backend dashscope --max-seconds 10
```

## Cache

ASR 结果默认缓存在 `<output-dir>/.cache/`，按文件内容哈希、后端、模型和截取参数键控。同一文件重复运行不会重复调用 ASR：

```bash
uv run video-text-tool video.mp4 --force      # 忽略缓存，强制重新转写
uv run video-text-tool video.mp4 --no-cache   # 本次运行完全禁用缓存
```

## Outputs

默认输出到 `outputs/`：

- `<name>.txt`：带时间戳的阅读文本
- `<name>.srt`：字幕文件
- `<name>.json`：结构化片段

JSON 包含 `source`，用于追溯文本来源：

```json
{
  "source": "asr:dashscope",
  "segments": []
}
```

常见来源包括 `external:...`、`embedded:2`、`asr:dashscope`。

## Subtitle Rules

`--subtitle prefer` 是默认策略：

```text
显式 --subtitle-file
  -> 同名外挂字幕 .srt/.ass/.vtt
  -> 内嵌文字字幕 srt/ass/mov_text/webvtt
  -> ASR
```

常见外挂字幕命名：

```text
video.srt
video.zh.srt
video.en.srt
video.ass
video.vtt
```

`--subtitle only` 只接受字幕来源。`--subtitle ignore` 跳过字幕，直接 ASR。

## Validation

常规验证：

```bash
uv run python -m compileall video_text_tool tests
uv run pytest -q
uv run video-text-tool --help
uv run video-text-tool res/videoplaybask.mp4 --list-streams
```

DashScope 10 秒烟测：

```bash
source ~/.zshrc
uv run video-text-tool res/audioplayback.mp3 --backend dashscope --subtitle ignore --max-seconds 10 --output-dir outputs/smoke_dashscope_10s --formats txt,json --max-segment-chars 60
```

已验证 DashScope ASR 和 `--translate-to zh` 调用链路可运行。短样例仍有 `Claude -> cloud` 这类术语误识别，后续需要术语词典或 LLM 纠错。


## Boundaries

- 支持文字字幕：外挂 `.srt/.ass/.vtt`，内嵌 `srt/ass/mov_text/webvtt`。
- 图片字幕和烧录在画面里的硬字幕需要 OCR，当前未实现。
- 平台字幕下载、批处理、Markdown 知识库输出仍在路线图中。
- faster-whisper、WhisperX、Whishper 是参考方案，当前没有集成进代码。
