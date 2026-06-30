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
- Sample files: `res/videoplaybask.mp4`, `res/audioplayback.mp3`.

Never print API keys. Report only whether a key is set.

## Canonical Pipeline

Current lightweight path:

```text
audio/video file
  -> ffmpeg extracts/normalizes audio to temporary 16 kHz mono wav
  -> DashScope ASR
  -> optional DashScope zh polish
  -> split and render md/json/txt/srt
```

Recommended user command:

```bash
uv run python reaudio_dashscope.py res/audioplayback.mp3 --output-dir outputs/reaudio
```

Legacy package path:

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
- ASR result cache in `<output-dir>/.cache/`, keyed by file hash/backend/model/clip; `--no-cache` and `--force` override it.
- `--max-seconds` clips audio before ASR for smoke tests and cost control.
- FunASR path present but not fully validated in WSL.

Planned:

- Terms dictionary.
- Hard subtitle OCR.
- Platform subtitle download.
- Batch processing and Markdown knowledge output.

## Code Boundaries

- `reaudio_dashscope.py`: single-file lightweight entry, ffmpeg audio extraction from audio/video inputs, DashScope ASR, default LLM polishing, cache, splitting, Markdown/txt/srt/json rendering.
- `reaudio_notes.md`: development notes for the lightweight script direction and later tool-suite integration.
- `cli.py`: argument parsing and pipeline orchestration.
- `models.py`: Pydantic v2 configs and structured records.
- `media.py`: ffprobe/ffmpeg, subtitle discovery, subtitle parsing, audio extraction.
- `asr.py`: local/cloud ASR and DashScope LLM adapters.
- `cache.py`: ASR result cache (file-hash keyed JSON under `<output-dir>/.cache/`).
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
uv run python -m compileall reaudio_dashscope.py video_text_tool tests
uv run pytest -q
uv run python reaudio_dashscope.py --help
uv run video-text-tool --help
uv run video-text-tool res/videoplaybask.mp4 --list-streams
```

For ASR validation, prefer `--max-seconds 10` on a real sample before full-file processing.
