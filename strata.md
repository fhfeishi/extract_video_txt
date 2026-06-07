# Strata: Project Launch Charter

`strata.md` is the long-lived launch charter for this project. It records why the project exists, what workflow it is meant to preserve, and how future agents should understand the solution.

It is not a user manual, not a changelog, and not a task tracker.

## Project

Name:

```text
extract_video_txt
```

One-line intent:

```text
Extract reliable, notes-friendly text from video/audio artifacts while preserving a reusable media-text workflow for a personal knowledge palace.
```

## Why This Exists

Many useful learning materials arrive as downloaded video/audio files. They may have platform subtitles, embedded subtitles, hard subtitles, or only audio. The goal is to avoid treating every file as an ASR problem and instead recover the best available text source first.

This project should become both:

- A practical CLI for extracting transcripts.
- A reusable solution pattern for media inspection, text extraction, normalization, and knowledge-base preparation.

## Users

- Primary: the owner of this knowledge workflow.
- Secondary: future agents continuing development.
- Possible later users: people who want a small local-first transcript tool.

## Inputs

- Video files, usually `.mp4` / `.mkv`.
- Audio files, such as `.mp3`.
- Nearby external subtitles, such as `.srt`, `.ass`, `.vtt`.
- Future: platform subtitles, OCR frames, source metadata.

Input quality is unreliable. Downloaded MP4 files must not be assumed to contain subtitle streams.

## Outputs

- `txt`: readable transcript with timestamps.
- `srt`: reusable subtitle file.
- `json`: structured segments with source metadata.
- Future: Markdown notes for Obsidian/Logseq-style knowledge bases.

## Canonical Pipeline

```text
inspect media quality
  -> use explicit or nearby external subtitles
  -> use embedded text subtitle streams
  -> fall back to ASR
  -> split long segments
  -> write txt/srt/json
  -> record lessons and next steps
```

Future enrichment pipeline:

```text
ASR transcript
  -> terms dictionary
  -> optional OCR correction for hard subtitles
  -> optional LLM cleanup/translation
  -> Markdown knowledge artifact
```

## Success Criteria

Minimum useful version:

- Can inspect a real video with `--list-streams`.
- Can extract external or embedded text subtitles when present.
- Can fall back to DashScope ASR for a short sample.
- Writes stable `txt/srt/json`.
- Gives understandable errors.
- Has tests for core parsing/rendering behavior.

Better version:

- Local FunASR validated in WSL.
- Terms dictionary for common ASR mistakes.
- Hard subtitle OCR experiment.
- Batch processing and cache.
- Markdown note output.

## Engineering Principles

- Existing text before ASR.
- Local-first where practical, cloud as explicit fallback.
- Every text segment should be timestamped and source-traceable.
- Provider backends stay behind config/adapters.
- CLI stays thin; reusable logic lives in small typed modules.
- Validation starts with inspect, then short smoke test, then full run.

## Skill Contract

This project may use reusable skills to preserve cross-project agent workflow knowledge. Skills should guide how future agents approach a class of work; project-specific facts stay in this repository's docs.

Recommended skills:

- `video-text-extraction`: use when improving subtitle discovery, ASR, OCR, terminology correction, translation, timestamped outputs, or knowledge-base transcript workflows.

Promotion rule:

```text
repo-specific facts       -> AGENTS.md / plan.md / logs.md / notes.md
stable project intent     -> strata.md
cross-project workflow    -> skills/
```

Do not duplicate skill bodies inside `strata.md`. Link to recommended skills and keep the project charter focused on intent, pipeline, success criteria, and document contracts.

## Documentation Contract

```text
README.md   = how to use the tool
AGENTS.md   = how agents should work in the repo
strata.md   = why the project exists and what solution it preserves
plan.md     = what is implemented, missing, and next
logs.md     = what happened, with commands and conclusions
notes.md    = stable knowledge and reusable design lessons
CLAUDE.md   = compatibility pointer to AGENTS.md
skills/     = cross-project reusable workflow assets
```

## Current Highest-Value Next Steps

1. Add a terms dictionary for `Claude`, `token`, `API key`, `GPT`.
2. Validate or revise the local FunASR backend in WSL.
3. Experiment with hard subtitle OCR on `videoplaybask.mp4`.
4. Add Markdown output for knowledge-base ingestion.
