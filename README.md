# extract_video_txt

本地优先的视频/音频文案提取工具。它按“已有文本优先”的策略工作：

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
uv run video-text-tool videoplaybask.mp4 --list-streams
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
uv run video-text-tool videoplaybask.mp4 --list-streams
```

DashScope 10 秒烟测：

```bash
source ~/.zshrc
mkdir -p outputs/smoke_dashscope_10s
ffmpeg -y -v error -ss 0 -t 10 -i audioplayback.mp3 -ac 1 -ar 16000 outputs/smoke_dashscope_10s/sample_10s.wav
uv run video-text-tool outputs/smoke_dashscope_10s/sample_10s.wav --backend dashscope --subtitle ignore --output-dir outputs/smoke_dashscope_10s --formats txt,json --max-segment-chars 60
```

已验证 DashScope ASR 和 `--translate-to zh` 调用链路可运行。短样例仍有 `Claude -> cloud` 这类术语误识别，后续需要术语词典或 LLM 纠错。

## PDF RAG Experiments

`rag_pdfs/` 是独立的 PDF RAG 切分实验子目录，重点比较 caption-aware chunks：

```bash
uv sync --extra pdf-rag --extra dev
uv run pdf-rag-experiment paper.pdf --query "What does Figure 2 show?"
```

核心策略：

- `inline_captions_chunks`：caption 内联进正文 chunk。
- `separate_caption_chunks`：caption 独立成 chunk，并带邻近上下文。

实验结果默认写入 `outputs/rag_pdfs/`，包含对比报告和各策略 JSONL chunks。

## Boundaries

- 支持文字字幕：外挂 `.srt/.ass/.vtt`，内嵌 `srt/ass/mov_text/webvtt`。
- 图片字幕和烧录在画面里的硬字幕需要 OCR，当前未实现。
- 平台字幕下载、批处理、缓存、Markdown 知识库输出仍在路线图中。
- faster-whisper、WhisperX、Whishper 是参考方案，当前没有集成进代码。
