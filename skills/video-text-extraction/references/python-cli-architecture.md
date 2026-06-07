# Python CLI Architecture

## Preferred Module Boundaries

Use small modules with clear ownership:

```text
package/
  cli.py          argument parsing and pipeline orchestration
  models.py       typed configs and segment records
  media.py        ffprobe/ffmpeg, subtitle discovery, audio extraction
  asr.py          local/cloud ASR and LLM provider adapters
  ocr.py          optional hard-subtitle OCR experiments
  text.py         timestamps, segmentation, normalization, terms
  output.py       txt/srt/json/md renderers
  errors.py       structured user-facing errors
```

Keep provider and parsing details out of `cli.py`. CLI code should assemble config, choose pipeline branches, call helpers, and present errors.

## Typed Records

Use structured records for:

- Run configuration.
- Backend configuration.
- Output configuration.
- Media stream summaries.
- Transcript segments.
- Error payloads.

Every segment should be able to carry:

```text
start time
end time
text
source
optional confidence/language/speaker metadata
```

## CLI Controls

Useful flags for media text tools:

```text
--list-streams
--subtitle prefer|only|ignore
--subtitle-file PATH
--subtitle-lang zh|en|auto
--subtitle-stream INDEX
--backend local|cloud-provider
--translate-to LANG
--output-dir DIR
--formats txt,srt,json,md
--max-segment-chars N
```

Expose explicit controls for expensive or ambiguous behavior. Avoid hidden cloud calls.

## Output Contract

Start with stable formats:

- `txt`: readable transcript with timestamps.
- `srt`: reusable subtitle file.
- `json`: structured segments and source metadata.
- `md`: knowledge-base note output when the workflow is ready.

JSON should preserve enough metadata for future processing. At minimum, include output-level source and segment list; better versions include media metadata, backend, language, and warnings.

## Error Design

Prefer user-facing structured errors:

```text
title
detail
suggested next steps
```

Common cases:

- No audio stream.
- No extractable subtitle in `subtitle only` mode.
- Unsupported image subtitle stream.
- `ffmpeg` or `ffprobe` missing.
- Cloud API key missing.
- Provider request failed.
- Local model dependency missing.

Error messages should help the user choose the next command.
