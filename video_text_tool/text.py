from __future__ import annotations

import re
from typing import Any

from .models import Segment


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def milliseconds_to_seconds(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number / 1000.0


def fix_segment_times(segments: list[Segment], duration: float) -> list[Segment]:
    fixed: list[Segment] = []
    for index, seg in enumerate(segments):
        start = max(0.0, float(seg.start or 0.0))
        end = float(seg.end or 0.0)
        if end <= start:
            next_start = segments[index + 1].start if index + 1 < len(segments) else duration
            end = max(start + 0.1, float(next_start or duration or start + 0.1))
        if duration:
            end = min(end, duration)
        fixed.append(Segment(start=start, end=end, text=seg.text, speaker=seg.speaker))
    return fixed


def split_long_segments(segments: list[Segment], max_chars: int) -> list[Segment]:
    if max_chars <= 0:
        return segments
    output: list[Segment] = []
    for seg in segments:
        chunks = split_text(seg.text, max_chars)
        if len(chunks) <= 1:
            output.append(seg)
            continue
        total_chars = sum(max(1, len(chunk)) for chunk in chunks)
        cursor = seg.start
        duration = max(0.1, seg.end - seg.start)
        for index, chunk in enumerate(chunks):
            if index == len(chunks) - 1:
                end = seg.end
            else:
                end = cursor + duration * (max(1, len(chunk)) / total_chars)
            output.append(Segment(start=cursor, end=end, text=chunk, speaker=seg.speaker))
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
            chunks.extend(piece[i : i + max_chars] for i in range(0, len(piece), max_chars))
            continue
        if current and len(current) + len(piece) > max_chars:
            chunks.append(current)
            current = piece
        else:
            current += piece
    if current:
        chunks.append(current)
    return chunks


def parse_numbered_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    parsed: list[str] = []
    for line in lines:
        line = re.sub(r"^\s*\d+\s*[\.、)]\s*", "", line).strip()
        if line:
            parsed.append(line)
    return parsed


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
