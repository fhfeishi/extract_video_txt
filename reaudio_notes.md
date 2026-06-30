# reaudio_dashscope 开发说明

`reaudio_dashscope.py` 是 `extract_video_txt` 当前的轻量脚本化入口：输入音频或视频文件，内部用 `ffmpeg` 抽取/规范化音频，再借助 DashScope ASR 和 DashScope LLM 输出润色后的 Markdown 文本。

它刻意保持为一个完整 `.py` 文件，方便后续搬进个人小工具合集。旧 `video_text_tool/` 包式结构继续保留，作为字幕优先、OCR、批量 pipeline 的参考。

## 文件分工

```text
reaudio_dashscope.py   主入口：参数解析、ffmpeg 抽音频、DashScope ASR、默认润色、缓存、Markdown/txt/srt/json 输出
video_text_tool/       旧包式实现：保留作字幕优先、测试和后续重构参考
```

## 运行方式

安装依赖：

```bash
cd ~/wslcodespace/extract_video_txt
uv sync --extra dashscope --extra dev
source ~/.zshrc
```

最常用命令：

```bash
uv run python reaudio_dashscope.py res/audioplayback.mp3 --output-dir outputs/reaudio
```

只转写前 10 秒，适合烟测和控制 DashScope 成本：

```bash
uv run python reaudio_dashscope.py res/audioplayback.mp3 --max-seconds 10 --output-dir outputs/reaudio_smoke
```

视频也可以直接传入；脚本只取音频流：

```bash
uv run python reaudio_dashscope.py video.mp4 --output-dir outputs/reaudio
```

默认会调用 LLM 润色。只想保留 ASR 原文时：

```bash
uv run python reaudio_dashscope.py audio.mp3 --no-polish --output-dir outputs/reaudio
```

需要字幕复用时额外输出 SRT：

```bash
uv run python reaudio_dashscope.py audio.mp3 --formats md,srt,json --output-dir outputs/reaudio
```

## 输出约定

默认输出：

```text
<output-dir>/<stem>.md
<output-dir>/<stem>.json
```

可选输出：

```text
<output-dir>/<stem>.txt
<output-dir>/<stem>.srt
```

Markdown 面向 Obsidian/知识库阅读；JSON 面向后续脚本处理；SRT 面向字幕校对；TXT 面向纯文本检索。

## 缓存策略

ASR 结果缓存在：

```text
<output-dir>/.cache/
```

缓存 key 包含：

- 输入文件内容哈希
- DashScope ASR 模型
- 语言提示
- `--max-seconds` 截取参数

`--force` 会忽略已有缓存并重新 ASR；`--no-cache` 完全禁用缓存。LLM 润色结果目前不缓存，避免提示词策略变化后拿到旧结果。

## 设计取舍

- 保留一个完整脚本文件，不再拆 `reaudio.py` 和 provider 文件。
- 输入可以是音频或视频；视频只抽音频流，不处理画面、字幕探测或 OCR。
- 默认输出润色文本，因为这个工具的目标是直接得到可读笔记。
- 保留 `--no-polish`，便于成本控制、问题定位和获取原始 ASR。
- 保留 JSON 输出，方便未来接入术语纠错、摘要和批量脚本。

## 后续整合建议

个人工具合集可以采用这种目录形态：

```text
tools/
  reaudio_dashscope.py
  reaudio_notes.md
```

先不要急着抽公共模块。等至少三个小工具都需要同一段缓存、Markdown 或 API key 检查逻辑时，再考虑 `shared/`。

## 可继续增强

- 增加 `terms.json`，在 ASR 后修正常见误识别词。
- 增加批量目录处理。
- 增加 Markdown 章节标题和摘要。
- 增加润色结果缓存开关。
