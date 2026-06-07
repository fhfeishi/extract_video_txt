# Strata 示例：小工具项目启动宪章

`strata.md` 是一个项目的 launch charter，用来在项目开始时固定“为什么做、做什么、怎么做、如何沉淀”。它不是 README、不是日志、也不是任务清单。

复制本文件到新项目时，可以改名为 `strata.md`，再把占位内容替换为真实项目内容。

## 项目

项目名称：

```text
<project_name>
```

一句话意图：

```text
构建一个 <工具/流程/系统>，用于解决 <问题类型>，并把过程沉淀为可复用的知识工作流。
```

## 为什么存在

我遇到的问题：

- <具体问题 1>
- <具体问题 2>
- <具体问题 3>

这个问题为什么值得做成工具：

- 它会重复出现。
- 人工处理成本高或容易遗漏。
- 结果需要进入知识库、工作流或后续 agent 处理。

长期意图：

```text
这个项目不是一次性脚本，而是一个 solution：它应该沉淀工具、流程、经验、验证方法和 agent 协作方式。
```

## 用户

主要用户：

- 我自己。
- 未来接手项目的 agent。
- 可能复用这个工具或流程的人。

典型场景：

- <场景 1>
- <场景 2>
- <场景 3>

## 输入

输入类型：

- <文件/API/网页/文本/数据库等>

输入质量假设：

- <哪些部分可靠>
- <哪些部分不可靠>
- <哪些情况必须先 inspect>

最不可靠的部分：

```text
<例如：下载文件可能缺元数据；网页结构可能变化；音频可能噪声大。>
```

## 输出

给人读的结果：

- <例如：Markdown 笔记、txt 文本、报告>

给程序继续处理的结果：

- <例如：json、csv、结构化记录>

给知识库沉淀的结果：

- <例如：Obsidian/Logseq 文档、术语表、pipeline 说明>

## Canonical Pipeline

首选路径：

```text
inspect 输入质量
  -> 优先使用最可靠的数据来源
  -> 清洗/规范化
  -> 结构化输出
  -> 写入知识库或后续工作流
```

兜底路径：

```text
首选路径失败
  -> 使用备用数据来源或模型
  -> 保留中间产物
  -> 输出可理解的错误或低置信结果
  -> 记录到 logs.md
```

质量检查路径：

```text
先 inspect
  -> 再跑短样例 smoke test
  -> 再跑完整样例
  -> 最后抽样检查输出
```

## 成功标准

最小可用版本：

- [ ] 能处理一个真实样例。
- [ ] 有清晰 CLI/API/入口命令。
- [ ] 能输出稳定文件。
- [ ] 错误时有可理解的提示。
- [ ] 有基础验证命令。
- [ ] 已更新 `README.md`、`plan.md`、`logs.md`、`notes.md`。

更理想的版本：

- [ ] 支持本地/云端/备用后端。
- [ ] 支持批量处理。
- [ ] 支持缓存或断点续跑。
- [ ] 支持结构化输出。
- [ ] 支持知识库友好输出。
- [ ] 能沉淀为 reusable skill/workflow。

## 明确不做

当前不做：

- <不做事项 1>
- <不做事项 2>

不追求：

- <例如：不追求复杂 UI；不追求覆盖所有边缘格式。>

原因：

```text
<说明取舍，避免后续 agent 误扩范围。>
```

## 工程原则

- 优先复用已有可靠数据，再使用模型推断。
- 本地优先；云端能力必须显式配置。
- 每个输出尽量保留来源和可追溯信息。
- CLI 保持薄，核心逻辑放到可测试的小函数。
- 配置和结构化记录优先使用 Pydantic v2。
- 先做 inspect 和 smoke test，再跑完整任务。

## 推荐代码结构

```text
project/
  package/
    cli.py        CLI 参数与流程编排
    models.py     配置和结构化数据
    media.py      媒体/文件/API 探测
    backends.py   本地/云端后端
    text.py       文本处理工具
    output.py     输出渲染
    errors.py     用户可理解的错误
  tests/
  README.md
  AGENTS.md
  strata.md
  plan.md
  logs.md
  notes.md
  CLAUDE.md
```

## 文档契约

```text
README.md   = how to use，面向用户
AGENTS.md   = how to work，面向 agent
strata.md   = why this project exists，项目启动宪章
plan.md     = what next，需求、缺陷、路线图
logs.md     = what happened，实验和命令证据链
notes.md    = what we learned，稳定知识和解决方案沉淀
CLAUDE.md   = compatibility pointer，指向 AGENTS.md
skills/     = reusable workflow，可跨项目复用
```

内容放置规则：

```text
用户要照着运行            -> README.md
agent 接手必须遵守        -> AGENTS.md
项目长期为什么这样做      -> strata.md
下一步开发什么            -> plan.md
今天试了什么、结果如何    -> logs.md
以后别忘的经验和方法      -> notes.md
```

## 验证命令

每次较大改动后至少运行：

```bash
uv run python -m compileall <package> tests
uv run pytest -q
uv run <tool-command> --help
uv run <tool-command> <sample_input> <safe_test_args>
```

如果涉及外部 API：

- 先跑短样例。
- 不打印 API key。
- 记录模型名称、耗时、结果质量和明显错误。

如果涉及文件处理：

- 先 inspect 文件。
- 再处理小样本。
- 最后处理完整样本。

## 当前最高价值下一步

1. <最小可执行下一步>
2. <最值得验证的风险>
3. <最值得沉淀的知识点>
4. <后续可以产品化的方向>
