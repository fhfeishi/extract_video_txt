from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Segment:
    start: float
    end: float
    text: str


class ReaudioError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> None:
    try:
        args = parse_args(argv)
        run(args)
    except ReaudioError as exc:
        raise SystemExit(f"Error: {exc}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="reaudio.py",
        description="Turn an audio/video file into Markdown transcript notes.",
    )
    parser.add_argument("input", help="Audio or video file.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for generated files.")
    parser.add_argument("--title", default=None, help="Markdown title. Defaults to the input file stem.")
    parser.add_argument("--formats", default="md,json", help="Comma-separated: md,txt,srt,json.")
    parser.add_argument("--backend", choices=["dashscope"], default="dashscope")
    parser.add_argument("--language-hints", default="zh,en", help="Comma-separated DashScope language hints.")
    parser.add_argument("--translate-to", choices=["zh"], default=None, help="Use DashScope LLM to polish into Chinese.")
    parser.add_argument("--dashscope-asr-model", default="paraformer-realtime-v2")
    parser.add_argument("--dashscope-llm-model", default="qwen-plus")
    parser.add_argument("--dashscope-api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--max-segment-chars", type=int, default=90, help="Split long segments. Set 0 to disable.")
    parser.add_argument("--max-seconds", type=float, default=None, help="Only process the first N seconds.")
    parser.add_argument("--no-cache", action="store_true", help="Disable ASR cache.")
    parser.add_argument("--force", action="store_true", help="Ignore ASR cache and transcribe again.")
    parser.add_argument("--keep-wav", action="store_true", help="Keep normalized 16 kHz WAV beside outputs.")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise ReaudioError(f"Input file does not exist: {input_path}")
    if args.max_seconds is not None and args.max_seconds <= 0:
        raise ReaudioError("--max-seconds must be greater than 0.")

    check_binary("ffmpeg")
    check_binary("ffprobe")

    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    formats = parse_formats(args.formats)
    stem = input_path.stem
    title = args.title or stem
    language_hints = [item.strip() for item in args.language_hints.split(",") if item.strip()]

    cache_path = None
    if not args.no_cache:
        cache_path = out_dir / ".cache" / f"{stem}.{cache_key(input_path, args, language_hints)}.json"

    segments: list[Segment] | None = None
    source = f"asr:{args.backend}"
    if cache_path and cache_path.exists() and not args.force:
        segments = load_cache(cache_path)

    if segments is None:
        with tempfile.TemporaryDirectory(prefix="reaudio_") as temp_dir:
            temp_wav = Path(temp_dir) / f"{stem}.16k.wav"
            extract_audio(input_path, temp_wav, max_seconds=args.max_seconds)
            segments = transcribe(temp_wav, args, language_hints)
            if args.keep_wav:
                shutil.copy2(temp_wav, out_dir / f"{stem}.16k.wav")
        if cache_path:
            save_cache(cache_path, segments, backend=args.backend, model=args.dashscope_asr_model)

    if args.translate_to:
        segments = translate(segments, args)
        source = f"{source}+translate:{args.translate_to}"

    segments = split_long_segments(segments, args.max_segment_chars)
    write_outputs(
        segments,
        out_dir=out_dir,
        stem=stem,
        title=title,
        source=source,
        input_path=input_path,
        formats=formats,
        max_seconds=args.max_seconds,
    )


def transcribe(audio_wav: Path, args: argparse.Namespace, language_hints: list[str]) -> list[Segment]:
    if args.backend == "dashscope":
        try:
            from reaudio_dashscope import DashScopeReaudioError, transcribe_dashscope
        except Exception as exc:
            raise ReaudioError("Cannot import reaudio_dashscope.py. Keep it beside reaudio.py.") from exc
        try:
            raw = transcribe_dashscope(
                audio_wav,
                api_key_env=args.dashscope_api_key_env,
                asr_model=args.dashscope_asr_model,
                language_hints=language_hints,
            )
        except DashScopeReaudioError as exc:
            raise ReaudioError(str(exc)) from exc
        return normalize_segments(raw)
    raise ReaudioError(f"Unsupported backend: {args.backend}")


def translate(segments: list[Segment], args: argparse.Namespace) -> list[Segment]:
    try:
        from reaudio_dashscope import DashScopeReaudioError, translate_segments_dashscope
    except Exception as exc:
        raise ReaudioError("Cannot import reaudio_dashscope.py. Keep it beside reaudio.py.") from exc
    try:
        raw = translate_segments_dashscope(
            [asdict(item) for item in segments],
            target=args.translate_to,
            api_key_env=args.dashscope_api_key_env,
            llm_model=args.dashscope_llm_model,
        )
    except DashScopeReaudioError as exc:
        raise ReaudioError(str(exc)) from exc
    return normalize_segments(raw)


def normalize_segments(raw: list[dict[str, Any]]) -> list[Segment]:
    segments: list[Segment] = []
    for item in raw:
        text = clean_text(str(item.get("text") or ""))
        if not text:
            continue
        start = as_float(item.get("start"))
        end = as_float(item.get("end"))
        if end <= start:
            end = start + 0.1
        segments.append(Segment(start=start, end=end, text=text))
    return segments


def extract_audio(input_path: Path, output_wav: Path, *, max_seconds: float | None = None) -> None:
    command = ["ffmpeg", "-y", "-v", "error", "-i", str(input_path)]
    if max_seconds:
        command += ["-t", f"{max_seconds:g}"]
    command += ["-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(output_wav)]
    run_command(command)


def write_outputs(
    segments: list[Segment],
    *,
    out_dir: Path,
    stem: str,
    title: str,
    source: str,
    input_path: Path,
    formats: set[str],
    max_seconds: float | None,
) -> None:
    if "md" in formats:
        (out_dir / f"{stem}.md").write_text(
            render_markdown(segments, title=title, source=source, input_path=input_path, max_seconds=max_seconds),
            encoding="utf-8",
        )
    if "txt" in formats:
        (out_dir / f"{stem}.txt").write_text(render_txt(segments), encoding="utf-8")
    if "srt" in formats:
        (out_dir / f"{stem}.srt").write_text(render_srt(segments), encoding="utf-8")
    if "json" in formats:
        payload = {"source": source, "segments": [asdict(item) for item in segments]}
        (out_dir / f"{stem}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {', '.join(sorted(formats))} to {out_dir}")


def render_markdown(
    segments: list[Segment],
    *,
    title: str,
    source: str,
    input_path: Path,
    max_seconds: float | None,
) -> str:
    generated = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = [
        f"# {title}",
        "",
        f"- Source file: `{input_path.name}`",
        f"- Text source: `{source}`",
        f"- Generated: `{generated}`",
    ]
    if max_seconds:
        lines.append(f"- Clip: first `{max_seconds:g}` seconds")
    lines += ["", "## Transcript", ""]
    for seg in segments:
        lines.append(f"### {format_clock(seg.start)} - {format_clock(seg.end)}")
        lines.append("")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_txt(segments: list[Segment]) -> str:
    return "\n".join(f"[{format_clock(seg.start)} - {format_clock(seg.end)}] {seg.text}" for seg in segments) + "\n"


def render_srt(segments: list[Segment]) -> str:
    blocks = []
    for index, seg in enumerate(segments, start=1):
        blocks.append(f"{index}\n{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}\n{seg.text}")
    return "\n\n".join(blocks) + "\n"


def split_long_segments(segments: list[Segment], max_chars: int) -> list[Segment]:
    if max_chars <= 0:
        return segments
    output: list[Segment] = []
    for seg in segments:
        chunks = split_text(seg.text, max_chars)
        if len(chunks) == 1:
            output.append(seg)
            continue
        total_chars = sum(max(1, len(chunk)) for chunk in chunks)
        cursor = seg.start
        duration = max(0.1, seg.end - seg.start)
        for index, chunk in enumerate(chunks):
            end = seg.end if index == len(chunks) - 1 else cursor + duration * (max(1, len(chunk)) / total_chars)
            output.append(Segment(start=cursor, end=end, text=chunk))
            cursor = end
    return output


def split_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces = re.findall(r"[^。！？!?；;，,]+[。！？!?；;，,]?", text)
    chunks: list[str] = []
    current = ""
    for piece in pieces or [text]:
        piece = piece.strip()
        if not piece:
            continue
        if len(piece) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(piece[index : index + max_chars] for index in range(0, len(piece), max_chars))
            continue
        if current and len(current) + len(piece) > max_chars:
            chunks.append(current)
            current = piece
        else:
            current += piece
    if current:
        chunks.append(current)
    return chunks


def parse_formats(value: str) -> set[str]:
    formats = {item.strip().lower() for item in value.split(",") if item.strip()}
    allowed = {"md", "txt", "srt", "json"}
    unknown = formats - allowed
    if unknown:
        raise ReaudioError(f"Unsupported formats: {', '.join(sorted(unknown))}")
    return formats or {"md"}


def cache_key(input_path: Path, args: argparse.Namespace, language_hints: list[str]) -> str:
    model_tag = hashlib.sha256(args.dashscope_asr_model.encode("utf-8")).hexdigest()[:8]
    lang_tag = "-".join(language_hints) or "auto"
    clip_tag = f"clip{args.max_seconds:g}" if args.max_seconds else "full"
    return f"{args.backend}_{model_tag}_{lang_tag}_{clip_tag}_{file_hash(input_path)[:16]}"


def load_cache(path: Path) -> list[Segment] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return normalize_segments(payload.get("segments") or [])
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def save_cache(path: Path, segments: list[Segment], *, backend: str, model: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"backend": backend, "model": model, "segments": [asdict(item) for item in segments]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def file_hash(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk_size):
            digest.update(block)
    return digest.hexdigest()


def check_binary(name: str) -> None:
    if not shutil.which(name):
        raise ReaudioError(f"Required binary not found: {name}. Install ffmpeg/ffprobe in WSL.")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise ReaudioError(f"Command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise ReaudioError(f"Command failed: {command[0]}\n{detail}") from exc


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def as_float(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def format_clock(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    rest = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{rest:05.2f}"


def format_srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


if __name__ == "__main__":
    main(sys.argv[1:])
