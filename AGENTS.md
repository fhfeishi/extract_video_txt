# Agent Guide

This is the canonical engineering guide for agents working on `extract_video_txt`.

For project intent and scope, read `strata.md`. For user-facing commands, read `README.md`. For stable workflow knowledge, read `notes.md`.

## Active Environment

Use WSL as the primary workspace:

```bash
cd ~/wslcodespace/extract_video_txt
uv sync --extra dashscope --extra dev
```

Environment facts:

- Python is managed by `uv`, targeting Python 3.12.
- `ffmpeg` and `ffprobe` are required.
- DashScope uses `DASHSCOPE_API_KEY`; source `~/.zshrc` when needed.
- Local model root defaults to `/mnt/e/local_models`; override with `VIDEO_TEXT_TOOL_MODEL_ROOT`.
- Sample files: `videoplaybask.mp4`, `audioplayback.mp3`.

Never print API keys. Report only whether a key is set.

## Canonical Pipeline

```text
inspect media
  -> prefer external subtitles
  -> prefer embedded text subtitles
  -> fall back to ASR
  -> split and render txt/srt/json
  -> later apply terms/LLM/OCR cleanup
```

Implemented:

- External subtitle scan: `.srt/.ass/.vtt`.
- Embedded text subtitle extraction.
- `--subtitle-file`, `--subtitle-lang`, `--subtitle-stream`.
- DashScope ASR validated.
- DashScope `--translate-to zh` path validated.
- FunASR path present but not fully validated in WSL.

Planned:

- Terms dictionary.
- Hard subtitle OCR.
- Platform subtitle download.
- Batch/cache/Markdown knowledge output.

## Code Boundaries

- `cli.py`: argument parsing and pipeline orchestration.
- `models.py`: Pydantic v2 configs and structured records.
- `media.py`: ffprobe/ffmpeg, subtitle discovery, subtitle parsing, audio extraction.
- `asr.py`: local/cloud ASR and DashScope LLM adapters.
- `text.py`: pure text and timestamp utilities.
- `output.py`: render and write output artifacts.
- `errors.py`: structured user-facing errors.

Keep provider code out of `cli.py`. Keep parsing/rendering logic testable as small functions.

## Documentation Rules

- `README.md`: concise user manual only.
- `strata.md`: project launch charter and long-lived intent.
- `plan.md`: requirements, gaps, priorities.
- `logs.md`: chronological evidence and command results.
- `notes.md`: durable knowledge, reusable workflow lessons, design principles.
- `CLAUDE.md`: compatibility shim pointing to this file.

When changing workflow assumptions, update `notes.md`. When changing priorities, update `plan.md`. When running meaningful experiments, append to `logs.md`.

## Validation

Before finishing code changes:

```bash
uv run python -m compileall video_text_tool tests
uv run pytest -q
uv run video-text-tool --help
uv run video-text-tool videoplaybask.mp4 --list-streams
```

For ASR validation, prefer a short clipped sample before full-file processing.
