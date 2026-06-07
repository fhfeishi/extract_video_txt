---
name: video-text-extraction
description: Build, debug, validate, or refactor video transcript extraction tools and workflows, including audio-only fallbacks when they are part of a video text pipeline. Use when Codex works on video-to-text pipelines involving external subtitles, embedded subtitle streams, hard subtitles/OCR, ASR backends, LLM cleanup or translation, terminology correction, timestamped txt/srt/json/md outputs, ffmpeg/ffprobe inspection, or knowledge-base transcript preparation.
---

# Video Text Extraction

## Purpose

Use this skill to turn audio/video materials into reliable, timestamped, source-traceable text. Prefer recoverable text sources before inference, and preserve the workflow knowledge needed for future agent handoff.

This skill is intentionally small and project-shaped. Keep it close to concrete video transcript extraction problems instead of expanding it into a broad agent-development framework.

## Core Workflow

```text
inspect input
  -> select best text source
  -> extract or infer transcript
  -> normalize, split, and trace segments
  -> render txt/srt/json/md outputs
  -> validate with real artifacts
  -> record reusable lessons
```

Use this source priority unless the user or repo explicitly says otherwise:

```text
explicit subtitle file
  -> nearby external subtitles
  -> embedded text subtitle streams
  -> platform/downloaded subtitles
  -> hard subtitle OCR
  -> audio ASR
  -> terms/LLM cleanup
```

Never treat ASR as the first option until subtitle and platform text possibilities have been inspected.

## Decision Points

Before implementing, answer these:

- What media inputs are expected: video, audio, subtitle files, platform URLs, or batches?
- What text source is most authoritative: human subtitles, generated subtitles, OCR, ASR, or mixed?
- What outputs are required: `txt`, `srt`, `json`, Markdown notes, or all of them?
- What backend modes are needed: local-only, cloud-only, or interchangeable local/cloud?
- What constraints matter: privacy, cost, language, terminology, latency, reproducibility?

For detailed source-selection rules, read `references/pipeline-patterns.md`.

## Implementation Guardrails

- Keep CLI orchestration thin; put reusable logic in modules.
- Keep provider code behind backend adapters or config objects.
- Keep text parsing, timestamp math, segmentation, rendering, and terms cleanup testable as pure functions where practical.
- Use typed configs and structured segment records.
- Preserve `source` metadata for each transcript or output bundle.
- Add read-only inspection/list modes before costly ASR, OCR, or cloud calls.
- Report whether secrets are set, never their values.

For Python CLI architecture and module boundaries, read `references/python-cli-architecture.md`.

## Validation

Validate in layers:

```text
probe/list streams
  -> test subtitle path
  -> smoke-test ASR/OCR with a short clip
  -> render outputs
  -> inspect representative text
  -> run compile/tests/help command
```

Prefer short clips before full-file cloud processing. Record commands, results, and limitations in the repo's evidence log when it exists.

For validation and handoff checklists, read `references/validation-and-handoff.md`.

## Documentation Rules

When the target repo has layered docs, keep responsibilities separate:

- User commands and current boundaries go in `README.md`.
- Agent environment, code boundaries, and validation commands go in `AGENTS.md`.
- Long-lived project intent and skill connections go in `strata.md`.
- Current gaps and priorities go in `plan.md`.
- Experiment evidence goes in `logs.md`.
- Durable workflow lessons go in `notes.md`.
- Cross-project media-text workflow knowledge belongs in this skill.

Do not copy repo-specific paths, API keys, local model locations, or sample-file conclusions into the skill unless they are generalized.

## Done Criteria

A media-text extraction workflow is ready when:

- The best-source-first pipeline is explicit and inspectable.
- At least one real artifact path has been validated or intentionally deferred with a reason.
- Outputs are timestamped and source-traceable.
- Fallback behavior is clear when subtitles, OCR, ASR, or provider calls fail.
- Current limits and next improvements are documented.
