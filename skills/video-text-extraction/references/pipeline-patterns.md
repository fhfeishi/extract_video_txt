# Pipeline Patterns

## Source Priority

Use recoverable text before inference:

```text
explicit subtitle file
  -> nearby external subtitle file
  -> embedded text subtitle stream
  -> platform/downloaded subtitle
  -> hard subtitle OCR
  -> audio ASR
  -> terms/LLM cleanup
```

This priority is about reliability, cost, and traceability. A human subtitle usually beats ASR. OCR may beat ASR for proper nouns visible in hard subtitles, but OCR often needs ASR timestamps or alignment.

## Input Inspection

Inspect before processing:

- Nearby subtitle files: `.srt`, `.ass`, `.vtt`, and language-suffixed names such as `video.zh.srt`.
- Container streams: video, audio, subtitle stream codec, language, title, duration.
- Subtitle codec type: text subtitles are extractable; image subtitles need OCR.
- Audio availability and quality before ASR.
- Frame samples when hard subtitles are suspected.

Useful tools:

```bash
ffprobe -v error -show_streams -of json input.mp4
ffprobe -v error -select_streams s -show_entries stream=index,codec_name,codec_type:stream_tags=language,title -of json input.mp4
ffmpeg -y -ss 00:05:00 -i input.mp4 -frames:v 1 frame.jpg
```

## Subtitle Handling

Support three user-facing modes when building a CLI:

```text
prefer  = use subtitles first, then fallback
only    = fail with guidance if no text subtitle source is available
ignore  = skip subtitles and force ASR/OCR path
```

Recommended controls:

- Explicit subtitle file path.
- Preferred subtitle language.
- Exact embedded subtitle stream index.
- List/inspect mode that explains available streams and codecs.

Normalize subtitles by removing style tags, preserving timestamps, and splitting long text only after parsing.

## ASR Fallback

Use ASR when no better text source exists or when the user explicitly requests it.

Implementation pattern:

```text
extract audio
  -> convert to ASR-friendly mono/16 kHz if needed
  -> call selected backend
  -> normalize segments
  -> render outputs
```

Keep local and cloud ASR interchangeable. Cloud backends need secret checks and short smoke tests. Local backends need model-root detection and clear dependency errors.

## OCR and Multi-Source Correction

For hard subtitles:

- Sample frames before committing to OCR.
- Crop likely subtitle regions to reduce noise.
- Use OCR as either a primary transcript source or a correction layer.
- Align OCR text with ASR or subtitle timestamps when possible.

Use OCR especially to correct visible proper nouns, product names, and technical terms that ASR misses.

## Terms and LLM Cleanup

Add deterministic terms correction before broad LLM cleanup when repeated ASR mistakes are known.

Examples of term rules:

```text
cloud -> Claude
A P I -> API
head token variants -> token
```

LLM cleanup is useful for translation, punctuation, note shaping, and terminology preservation, but keep raw transcript artifacts when traceability matters.
