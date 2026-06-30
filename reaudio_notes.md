# reaudio 开发说明

`reaudio` 是 `extract_video_txt` 的轻量脚本化方向：把一个音频/视频文件转成 Markdown 文本，优先满足个人小工具合集里的复用、搬迁和维护。视频可以直接传入，但只取音频流，画面、字幕探测和 OCR 不进入这个轻量脚本。

## 文件分工

```text
reaudio.py             主入口：参数解析、ffmpeg 抽音频、缓存、分段、Markdown/txt/srt/json 输出
reaudio_dashscope.py   DashScope 适配：ASR 调用、LLM 中文整理、返回统一 segments
video_text_tool/       旧包式实现：保留作字幕优先、测试和后续重构参考
```

后续如果继续保持“小工具”形态，优先改这两个脚本。只有当字幕/OCR/批量处理明显膨胀时，再考虑恢复包式拆分。

## 运行方式

安装依赖：

```bash
cd ~/wslcodespace/extract_video_txt
uv sync --extra dashscope --extra dev
source ~/.zshrc
```

最常用命令：

```bash
uv run python reaudio.py res/audioplayback.mp3 --output-dir outputs/reaudio
```

只转写前 10 秒，适合烟测和控制 DashScope 成本：

```bash
uv run python reaudio.py res/audioplayback.mp3 --max-seconds 10 --output-dir outputs/reaudio_smoke
```

转写后整理为中文 Markdown 笔记：

```bash
uv run python reaudio.py audio.mp3 --translate-to zh --formats md,json --output-dir outputs/reaudio
```

需要字幕复用时额外输出 SRT：

```bash
uv run python reaudio.py audio.mp3 --formats md,srt,json --output-dir outputs/reaudio
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
- ASR 后端
- ASR 模型
- 语言提示
- `--max-seconds` 截取参数

`--force` 会忽略已有缓存并重新 ASR；`--no-cache` 完全禁用缓存。`--translate-to zh` 目前不缓存，避免 LLM 整理策略变化后拿到旧结果。

## 设计取舍

- 两个脚本保持标准库优先，DashScope SDK 只在 `reaudio_dashscope.py` 中导入。
- 主目标从“视频字幕/ASR 全能 pipeline”收敛为“音频到 Markdown 文本”。
- 仍用 `ffmpeg` 把音频或视频输入统一成临时 16 kHz mono WAV；视频输入只取音频流，不处理画面。
- 保留时间戳，方便回看音频、切字幕和定位原文。
- 保留 JSON 输出，方便未来统一小工具合集时接入批处理、术语纠错、摘要等脚本。

## 后续整合建议

个人工具合集可以采用这种目录形态：

```text
tools/
  reaudio.py
  reaudio_dashscope.py
  reaudio_notes.md
  shared/
    file_cache.py
    markdown.py
```

先不要急着抽 `shared/`。等至少三个小工具都需要同一段缓存、Markdown 或 API key 检查逻辑时，再抽公共模块。

## 可继续增强

- 增加 `terms.json`，在 ASR 后修正常见误识别词。
- 增加批量目录处理。
- 增加 Markdown 章节标题和摘要。
- 增加平台下载器字幕输入，但这可能会再次把脚本推向包式架构。
