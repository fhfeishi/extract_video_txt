from __future__ import annotations

import json
from pathlib import Path

from .models import Segment
from .text import format_clock, format_srt_time


def write_outputs(segments: list[Segment], out_dir: Path, stem: str, formats: set[str], source: str | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if "txt" in formats:
        (out_dir / f"{stem}.txt").write_text(render_txt(segments), encoding="utf-8")
    if "srt" in formats:
        (out_dir / f"{stem}.srt").write_text(render_srt(segments), encoding="utf-8")
    if "json" in formats:
        payload = {"source": source, "segments": [seg.model_dump() for seg in segments]}
        (out_dir / f"{stem}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {', '.join(sorted(formats))} to {out_dir}")


def render_txt(segments: list[Segment]) -> str:
    lines = []
    for seg in segments:
        speaker = f" {seg.speaker}" if seg.speaker else ""
        lines.append(f"[{format_clock(seg.start)} - {format_clock(seg.end)}]{speaker} {seg.text}".rstrip())
    return "\n".join(lines) + "\n"


def render_srt(segments: list[Segment]) -> str:
    blocks = []
    for index, seg in enumerate(segments, start=1):
        text = seg.text if not seg.speaker else f"{seg.speaker}: {seg.text}"
        blocks.append(f"{index}\n{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}\n{text}")
    return "\n\n".join(blocks) + "\n"
