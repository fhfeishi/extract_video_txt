from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ToolError
from .models import Segment
from .text import clean_text


TEXT_SUBTITLE_CODECS = {"srt", "subrip", "ass", "ssa", "mov_text", "webvtt"}
IMAGE_SUBTITLE_CODECS = {"hdmv_pgs_subtitle", "pgs", "dvd_subtitle", "dvb_subtitle"}
SUBTITLE_SUFFIXES = (".srt", ".ass", ".ssa", ".vtt", ".webvtt")
LANG_ALIASES = {
    "zh": {"zh", "chi", "zho", "chs", "cht", "cn", "zh-cn", "zh-hans", "zh-hant"},
    "en": {"en", "eng", "english"},
}


@dataclass(frozen=True)
class SubtitleFile:
    path: Path
    language: str | None = None


@dataclass(frozen=True)
class SubtitleStream:
    index: int
    codec: str
    language: str | None = None
    title: str | None = None

    @property
    def is_text(self) -> bool:
        return self.codec in TEXT_SUBTITLE_CODECS


@dataclass(frozen=True)
class SubtitleResult:
    segments: list[Segment]
    source: str


def check_binary(name: str) -> None:
    if not shutil.which(name):
        raise ToolError(
            f"Required binary not found: {name}",
            hints=[
                "Install ffmpeg/ffprobe in WSL.",
                "Run `ffmpeg -version` and `ffprobe -version` to confirm they are on PATH.",
            ],
        )


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise ToolError(f"Command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise ToolError(f"Command failed: {command[0]}", detail=detail) from exc


def ffprobe_json(input_path: Path) -> dict[str, Any]:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(input_path),
        ]
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ToolError("ffprobe returned invalid JSON.", detail=str(exc)) from exc


def get_duration(input_path: Path) -> float:
    data = ffprobe_json(input_path)
    duration = data.get("format", {}).get("duration")
    try:
        return float(duration)
    except (TypeError, ValueError):
        return 0.0


def render_stream_report(input_path: Path) -> str:
    data = ffprobe_json(input_path)
    lines = [f"file: {input_path}", ""]
    format_info = data.get("format", {})
    if format_info:
        lines.append("format:")
        for key in ("format_name", "duration", "size", "bit_rate"):
            if key in format_info:
                lines.append(f"  {key}: {format_info[key]}")
        tags = format_info.get("tags") or {}
        for key in ("encoder", "title"):
            if key in tags:
                lines.append(f"  {key}: {tags[key]}")
        lines.append("")

    lines.append("streams:")
    for stream in data.get("streams", []):
        index = stream.get("index", "?")
        codec_type = stream.get("codec_type", "?")
        codec_name = stream.get("codec_name", "?")
        tags = stream.get("tags") or {}
        suffix = []
        if "language" in tags:
            suffix.append(f"language={tags['language']}")
        if "title" in tags:
            suffix.append(f"title={tags['title']}")
        lines.append(f"  {index}: {codec_type} / {codec_name}" + (f" ({', '.join(suffix)})" if suffix else ""))
    external = find_external_subtitles(input_path)
    if external:
        lines.append("")
        lines.append("external subtitles:")
        for item in external:
            suffix = f" (language={item.language})" if item.language else ""
            lines.append(f"  {item.path.name}{suffix}")
    return "\n".join(lines) + "\n"


def try_load_subtitle(
    input_path: Path,
    output_srt: Path,
    *,
    lang: str = "auto",
    stream_index: int | None = None,
    subtitle_file: Path | None = None,
) -> SubtitleResult | None:
    if subtitle_file:
        segments = load_subtitle_file(subtitle_file, output_srt)
        return SubtitleResult(segments=segments, source=f"external:{subtitle_file}") if segments else None

    for external in choose_external_subtitles(find_external_subtitles(input_path), lang):
        segments = load_subtitle_file(external.path, output_srt)
        if segments:
            return SubtitleResult(segments=segments, source=f"external:{external.path}")

    stream = choose_subtitle_stream(list_subtitle_streams(input_path), lang=lang, stream_index=stream_index)
    if not stream:
        return None
    segments = extract_subtitle_stream(input_path, output_srt, stream)
    return SubtitleResult(segments=segments, source=f"embedded:{stream.index}") if segments else None


def find_external_subtitles(input_path: Path) -> list[SubtitleFile]:
    directory = input_path.parent
    stem = input_path.stem
    found: dict[Path, SubtitleFile] = {}
    language_tokens = ["zh", "zh-cn", "zh-hans", "chs", "cht", "cn", "en", "eng"]

    for suffix in SUBTITLE_SUFFIXES:
        add_subtitle_candidate(found, directory / f"{stem}{suffix}", None)
        for lang in language_tokens:
            add_subtitle_candidate(found, directory / f"{stem}.{lang}{suffix}", lang)

    for path in directory.glob(f"{stem}.*"):
        if path.suffix.lower() in SUBTITLE_SUFFIXES:
            add_subtitle_candidate(found, path, infer_subtitle_language(path))

    return sorted(found.values(), key=lambda item: (subtitle_file_rank(item), item.path.name.lower()))


def add_subtitle_candidate(found: dict[Path, SubtitleFile], path: Path, language: str | None) -> None:
    if path.exists() and path.is_file():
        found[path.resolve()] = SubtitleFile(path=path.resolve(), language=language or infer_subtitle_language(path))


def infer_subtitle_language(path: Path) -> str | None:
    parts = [part.lower() for part in path.name.split(".")[1:-1]]
    for lang, aliases in LANG_ALIASES.items():
        if any(part in aliases for part in parts):
            return lang
    return None


def subtitle_file_rank(item: SubtitleFile) -> int:
    if language_matches(item.language, "zh"):
        return 0
    if item.language is None:
        return 1
    if language_matches(item.language, "en"):
        return 2
    return 3


def choose_external_subtitles(files: list[SubtitleFile], lang: str) -> list[SubtitleFile]:
    if lang and lang != "auto":
        preferred = [item for item in files if language_matches(item.language, lang)]
        return preferred + [item for item in files if item not in preferred]
    return files


def load_subtitle_file(path: Path, output_srt: Path) -> list[Segment]:
    suffix = path.suffix.lower()
    if suffix == ".srt":
        return parse_srt(path.read_text(encoding="utf-8-sig", errors="replace"))
    if suffix in {".vtt", ".webvtt"}:
        return parse_vtt(path.read_text(encoding="utf-8-sig", errors="replace"))
    if suffix in {".ass", ".ssa"}:
        return convert_subtitle_file(path, output_srt)
    return []


def list_subtitle_streams(input_path: Path) -> list[SubtitleStream]:
    streams = []
    for stream in ffprobe_json(input_path).get("streams", []):
        if stream.get("codec_type") != "subtitle":
            continue
        tags = stream.get("tags") or {}
        streams.append(
            SubtitleStream(
                index=int(stream["index"]),
                codec=str(stream.get("codec_name") or ""),
                language=normalize_language(tags.get("language")),
                title=tags.get("title"),
            )
        )
    return streams


def choose_subtitle_stream(
    streams: list[SubtitleStream],
    *,
    lang: str = "auto",
    stream_index: int | None = None,
) -> SubtitleStream | None:
    if stream_index is not None:
        return next((stream for stream in streams if stream.index == stream_index), None)
    text_streams = [stream for stream in streams if stream.is_text]
    if lang and lang != "auto":
        preferred = [stream for stream in text_streams if language_matches(stream.language, lang)]
        if preferred:
            return preferred[0]
    for preferred_lang in ("zh", "en"):
        preferred = [stream for stream in text_streams if language_matches(stream.language, preferred_lang)]
        if preferred:
            return preferred[0]
    return text_streams[0] if text_streams else None


def extract_subtitle_stream(input_path: Path, output_srt: Path, stream: SubtitleStream) -> list[Segment]:
    if not stream.is_text:
        return []
    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(input_path),
        "-map",
        f"0:{stream.index}",
        str(output_srt),
    ]
    run_command(command)
    return parse_srt(output_srt.read_text(encoding="utf-8", errors="replace"))


def convert_subtitle_file(path: Path, output_srt: Path) -> list[Segment]:
    run_command(["ffmpeg", "-y", "-v", "error", "-i", str(path), str(output_srt)])
    return parse_srt(output_srt.read_text(encoding="utf-8", errors="replace"))


def extract_audio(input_path: Path, output_wav: Path, *, max_seconds: float | None = None) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(input_path),
    ]
    if max_seconds:
        command += ["-t", f"{max_seconds:g}"]
    command += [
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(output_wav),
    ]
    run_command(command)


def parse_srt(content: str) -> list[Segment]:
    blocks = re.split(r"\n\s*\n", content.strip().replace("\r\n", "\n"))
    segments: list[Segment] = []
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        time_line_index = next((idx for idx, line in enumerate(lines) if "-->" in line), None)
        if time_line_index is None:
            continue
        start_text, end_text = [part.strip() for part in lines[time_line_index].split("-->", 1)]
        text = clean_text(" ".join(lines[time_line_index + 1 :]))
        if text:
            segments.append(Segment(start=parse_srt_time(start_text), end=parse_srt_time(end_text), text=text))
    return segments


def parse_vtt(content: str) -> list[Segment]:
    lines = []
    for line in content.replace("\r\n", "\n").splitlines():
        stripped = line.strip()
        if stripped == "WEBVTT" or stripped.startswith(("NOTE", "STYLE", "REGION")):
            continue
        lines.append(stripped)
    return parse_srt("\n".join(lines))


def parse_srt_time(value: str) -> float:
    value = value.split()[0].replace(",", ".")
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def normalize_language(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip().lower()
    return value or None


def language_matches(actual: str | None, requested: str) -> bool:
    if not actual:
        return False
    requested = requested.strip().lower()
    actual = actual.strip().lower()
    aliases = LANG_ALIASES.get(requested, {requested})
    return actual in aliases or requested == actual
