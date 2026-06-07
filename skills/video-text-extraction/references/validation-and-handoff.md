# Validation and Handoff

## Validation Layers

Run the cheapest useful checks first:

```text
static import/compile checks
  -> unit tests for parsing/rendering/text utilities
  -> CLI help
  -> media inspect/list mode
  -> subtitle extraction path
  -> short ASR/OCR smoke sample
  -> full realistic run if cost/time allows
```

For cloud ASR or LLM calls, use a short clipped sample before full-file processing.

## Evidence to Record

When a repo has logs, record:

- Command run.
- Input type and duration when relevant.
- Backend used.
- Output files generated.
- Representative result, not the full transcript.
- Known mistakes such as terminology errors.
- Conclusion and next action.

Do not print API keys. Report only whether a required key is set.

## Test Coverage Targets

Prioritize tests for:

- External subtitle discovery.
- SRT parsing and rendering.
- Timestamp formatting and segment splitting.
- Subtitle source priority.
- Structured JSON source metadata.
- Error cases for missing subtitle/audio/provider configuration.

Broaden tests when changing shared parsing, timestamp math, or provider contracts.

## Handoff Checklist

Before handing off:

- State the canonical pipeline.
- State implemented and planned backends.
- List validated sample paths or describe why validation was deferred.
- List output formats and source metadata behavior.
- Call out quality traps.
- Update README, AGENTS, strata, plan, logs, or notes according to their roles.

## Common Quality Traps

- Jumping to ASR before checking subtitles.
- Treating image subtitles as text subtitles.
- Losing timestamps during cleanup.
- Replacing raw transcript with LLM-polished text without preserving source.
- Hiding provider-specific logic inside CLI orchestration.
- Running long cloud jobs before a short smoke test.
- Letting docs drift into duplicate or conflicting instructions.
