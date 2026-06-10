from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import Backend, RunConfig, Segment


def file_hash(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk_size):
            digest.update(block)
    return digest.hexdigest()


def asr_model_name(config: RunConfig, backend: Backend) -> str:
    if backend == Backend.DASHSCOPE:
        return config.dashscope.asr_model
    return config.local.asr_model


def asr_cache_key(config: RunConfig, backend: Backend) -> str:
    model_tag = hashlib.sha256(asr_model_name(config, backend).encode("utf-8")).hexdigest()[:8]
    if backend == Backend.DASHSCOPE:
        lang = "-".join(config.dashscope.language_hints) or "auto"
    else:
        lang = "local"
    clip = f"clip{config.max_seconds:g}" if config.max_seconds else "full"
    return f"{backend.value}_{model_tag}_{lang}_{clip}_{file_hash(config.input_path)[:16]}"


def asr_cache_path(out_dir: Path, stem: str, key: str) -> Path:
    return out_dir / ".cache" / f"{stem}.{key}.json"


def load_asr_cache(path: Path) -> list[Segment] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [Segment(**item) for item in payload["segments"]]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def save_asr_cache(path: Path, segments: list[Segment], *, backend: Backend, model: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "backend": backend.value,
        "model": model,
        "segments": [seg.model_dump() for seg in segments],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
