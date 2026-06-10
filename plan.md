# 项目需求与计划

## 项目名称

`extract_video_txt`

## 项目目标

构建一个通用的视频文案提取工具，把视频/音频转换成可读、可检索、可继续加工的文字材料。

核心使用场景：

- 从课程、播客、B站/YouTube 视频中提取完整文案。
- 生成笔记、摘要、关键词和知识库索引。
- 为后续 LLM 提问、复盘和主题研究提供原始文本。
- 中文视频中尽量保留英文专有名词。
- 纯英文视频可整理成中文为主的笔记素材。

## 当前输入来源假设

目前主要输入来自第三方免费视频下载平台获取的 `.mp4` 文件，质量不可控：

- 可能只有视频流和音频流。
- 可能不包含平台字幕。
- 可能有硬字幕，但没有软字幕流。
- 可能压缩较重，但通常不影响 ASR。
- 可能缺少语言标签、标题、章节等元数据。

当前样例 `videoplaybask.mp4` 就是这种情况：只有 H.264 视频流和 AAC 音频流，没有 subtitle stream。

## 目标 Pipeline

理想流水线：

```text
1. 输入路径解析
   - 视频文件
   - 音频文件
   - 同名外挂字幕
   - 下载器附带字幕文件

2. 文本来源探测
   - 同名 .srt/.ass/.vtt
   - 容器内 subtitle stream
   - 平台字幕接口或下载器元数据
   - 硬字幕画面区域
   - 音频流

3. 最佳来源选择
   - 中文软字幕优先
   - 其次英文软字幕，并翻译/整理为中文
   - 没有软字幕时，尝试硬字幕 OCR
   - 最后使用 ASR 转写音频

4. 文本规范化
   - 清理字幕样式标签
   - 合并/切分段落
   - 修正时间戳
   - 标点恢复
   - 术语词典纠错

5. 多源融合
   - 字幕作为主干
   - ASR 补充字幕遗漏
   - OCR 辅助纠正专有名词
   - LLM 做轻量润色和中英整理

6. 输出
   - .txt：面向阅读和笔记
   - .srt：面向字幕复用
   - .json：面向程序处理
   - 后续可加 .md：面向知识库
```

## 当前已实现

- CLI 入口：`uv run video-text-tool`，兼容 `python -m video_text_tool`
- 使用 Pydantic v2 定义运行配置、本地 ASR 配置、DashScope 配置、输出配置和文本片段结构。
- 使用 `ffprobe` 检测容器内字幕流。
- 自动扫描同名外挂字幕：`.srt/.ass/.vtt`，包含 `video.zh.srt`、`video.en.srt` 等常见命名。
- 支持显式 `--subtitle-file` 指定外挂字幕。
- 支持 `--subtitle-lang zh/en/auto` 选择字幕语言。
- 支持 `--subtitle-stream` 指定内嵌字幕 stream index。
- 使用 `ffmpeg` 提取文字型内嵌字幕流。
- 没有字幕时抽取音频为 16 kHz mono WAV。
- 支持 DashScope ASR 后端。
- 预留 FunASR 本地模型后端。
- 支持 `txt/srt/json` 输出。
- JSON 输出记录文本来源，例如 `external:...`、`embedded:2`、`asr:dashscope`。
- 支持长段按字符数切分。
- 支持 `--subtitle prefer/ignore/only`。
- 支持 `--translate-to zh` 调用 DashScope LLM 做中文化整理。
- 支持 `--list-streams` 查看输入媒体 stream 摘要。
- 支持结构化错误提示，包含错误标题、细节和下一步建议。
- 增加 `media/text/output` 的最小 pytest 覆盖。
- 新增 `rag_pdfs/` PDF RAG 切分实验子项目：
  - `inline_captions_chunks`：caption 内联进正文 chunk。
  - `separate_caption_chunks`：caption 独立成 chunk，并带邻近上下文。
  - `page_chunks`、`section_chunks`、`recursive_text_chunks` 作为对照策略。
  - `pdf-rag-experiment` 输出对比 JSON、Markdown 报告和各策略 JSONL chunks。
  - 提供 LangChain Document/FAISS 适配层，依赖放在可选 `pdf-rag` extra。

## 当前缺陷

- 没有解析 `.ass/.vtt` 的样式和特殊结构，只做了基础 SRT 解析。
- 没有处理图片字幕流，例如 `pgs`、`dvd_subtitle`。
- 没有硬字幕 OCR。
- 没有平台字幕下载能力，例如 B站/YouTube 的单独字幕接口。
- ASR 对专有名词仍会误识别，例如 `Claude`、`token`、`API key`、`GPT`。
- DashScope ASR 有时返回长段，当前按字符比例切时间戳，只是可用的近似方案。
- 本地 FunASR 依赖还没有在当前 `.venv` 中安装和完整验证。
- 还没有做批量处理、断点续跑和缓存。
- 没有自动质量评估，例如字幕覆盖率、ASR 置信度、文本重复率。

## 优先级计划

### P0：稳定当前工具

- 保持字幕优先、ASR 兜底的主流程可用。
- 继续完善错误信息，尤其是无音频流、ffmpeg 失败、云端 API 失败时的提示。
- 保持 `txt/srt/json` 输出格式稳定。

### P1：完善字幕优先策略

- 在 `--list-streams` 中更详细标注字幕流是否文字型/图片型。
- 支持更多外挂字幕命名规则和语言别名。
- 强化 `.ass/.vtt` 解析质量，减少样式标签残留。
- 支持图片字幕流检测后给出 OCR 提示。

### P2：术语纠错和文本清洗

- 增加术语词典，例如：
  - `cloud -> Claude`
  - `植皮T -> GPT`
  - `头肯/偷看 -> token`
  - `A P I -> API`
  - `key/kee -> key`
- 增加可配置 `terms.yaml` 或 `terms.json`。
- 增加 LLM 后处理模式：
  - 轻量纠错
  - 中英术语保留
  - 中文笔记化
  - 摘要和章节标题

### P3：硬字幕 OCR

- 自动抽帧判断底部是否存在字幕。
- 对字幕区域裁剪，减少 OCR 干扰。
- 尝试 PaddleOCR 或其他本地 OCR。
- 将 OCR 文本和 ASR 文本按时间对齐，用 OCR 修正专有名词。

### P4：下载源增强

- 支持接入更可靠的视频下载工具，例如 `yt-dlp`。
- 下载视频时同时尝试下载字幕：
  - 自动字幕
  - 人工字幕
  - 中文优先
  - 英文备选
- 记录来源 URL、标题、作者、发布时间等元数据。

### P5：批量处理和知识库输出

- 批量处理目录。
- 已处理文件缓存，避免重复 ASR。
- 生成 Markdown 笔记：
  - 标题
  - 元数据
  - 时间戳文案
  - 摘要
  - 术语表
  - 可追溯片段链接
- 支持输出到 Obsidian/Logseq 风格目录。

### P6：PDF RAG chunk 实验

- 用真实论文/手册样本验证 `inline_captions_chunks` 和 `separate_caption_chunks` 的检索差异。
- 增加带标准答案或人工标注的 query set。
- 对比 caption 命中率、答案上下文完整度、chunk 数量、平均长度和召回结果。
- 接入实际 embeddings 后复测当前轻量 lexical retrieval 的结论。
- 继续探索表格块、版面坐标、章节层级和参考文献过滤。

## 近期最值得做的改进

1. 增加术语词典后处理，优先修正 `Claude/token/API key/GPT`。
2. 把 `videoplaybask.mp4` 这类硬字幕视频纳入 OCR 实验。
3. 为 ASR 后端增加更细的 smoke test 和错误处理测试。
4. 生成 Markdown 笔记输出，适配知识库。
5. 选一个真实 PDF 样本跑 `rag_pdfs`，比较 inline/separate caption chunks。

## 设计原则

- 已有文本优先，ASR 兜底。
- 可追溯：每段文本保留时间戳和来源。
- 可替换：本地模型和云端 API 都能作为后端。
- 可扩展：字幕、OCR、ASR、LLM 后处理解耦。
- 笔记友好：最终输出应该能直接进入个人知识库。
