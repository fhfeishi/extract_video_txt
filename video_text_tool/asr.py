from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from .errors import ToolError
from .media import get_duration
from .models import Backend, DashScopeConfig, Device, LocalAsrConfig, RunConfig, Segment
from .text import clean_text, fix_segment_times, milliseconds_to_seconds, parse_numbered_lines


def choose_backend(config: RunConfig) -> Backend:
    if config.backend != Backend.AUTO:
        return config.backend
    try:
        import funasr  # noqa: F401

        return Backend.FUNASR
    except Exception:
        pass
    try:
        import dashscope  # noqa: F401

        return Backend.DASHSCOPE
    except Exception:
        pass
    raise ToolError(
        "No ASR backend is installed.",
        hints=[
            "Run `uv sync --extra dashscope --extra dev` for DashScope.",
            "Run `uv sync --extra local --extra dev` for FunASR.",
        ],
    )


def transcribe(audio_path: Path, config: RunConfig) -> list[Segment]:
    segments, _backend = transcribe_with_backend(audio_path, config)
    return segments


def transcribe_with_backend(
    audio_path: Path, config: RunConfig, backend: Backend | None = None
) -> tuple[list[Segment], Backend]:
    backend = backend or choose_backend(config)
    if backend == Backend.FUNASR:
        return transcribe_funasr(audio_path, config.local), backend
    if backend == Backend.DASHSCOPE:
        return transcribe_dashscope(audio_path, config.dashscope), backend
    raise ToolError(f"Unknown backend: {backend}")


def transcribe_funasr(audio_path: Path, config: LocalAsrConfig) -> list[Segment]:
    try:
        from funasr import AutoModel
    except Exception as exc:
        raise ToolError(
            "FunASR backend is not installed.",
            detail=f"Import error: {exc}",
            hints=["Run `uv sync --extra local --extra dev`."],
        ) from exc

    device = config.device.value
    if config.device == Device.AUTO:
        device = "cuda" if has_cuda() else "cpu"

    model = AutoModel(
        model=normalize_model_arg(config.asr_model),
        vad_model=normalize_model_arg(config.vad_model),
        punc_model=normalize_model_arg(config.punc_model),
        device=device,
    )
    raw = model.generate(input=str(audio_path), batch_size_s=300, merge_vad=True, merge_length_s=15)
    return normalize_funasr_result(raw, get_duration(audio_path))


def normalize_model_arg(value: str) -> str:
    path = Path(value)
    if path.exists():
        return str(path)
    return value


def has_cuda() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def normalize_funasr_result(raw: Any, duration: float) -> list[Segment]:
    items = raw if isinstance(raw, list) else [raw]
    segments: list[Segment] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sentence_info = item.get("sentence_info") or item.get("sentences")
        if isinstance(sentence_info, list):
            for sentence in sentence_info:
                text = clean_text(sentence.get("text", ""))
                if not text:
                    continue
                start = milliseconds_to_seconds(sentence.get("start", sentence.get("begin", 0)))
                end = milliseconds_to_seconds(sentence.get("end", sentence.get("finish", 0)))
                speaker = sentence.get("spk") or sentence.get("speaker")
                segments.append(Segment(start=start, end=end, text=text, speaker=speaker))
            continue

        text = clean_text(item.get("text", ""))
        if text:
            timestamps = item.get("timestamp")
            if isinstance(timestamps, list) and timestamps:
                start = milliseconds_to_seconds(timestamps[0][0]) if isinstance(timestamps[0], list) else 0.0
                last = timestamps[-1]
                end = milliseconds_to_seconds(last[-1]) if isinstance(last, list) else duration
            else:
                start, end = 0.0, duration
            segments.append(Segment(start=start, end=end, text=text))
    return fix_segment_times(segments, duration)


def transcribe_dashscope(audio_path: Path, config: DashScopeConfig) -> list[Segment]:
    api_key = os.getenv(config.api_key_env)
    if not api_key:
        raise ToolError(
            f"{config.api_key_env} is not set.",
            hints=[f"Run `source ~/.zshrc` or export {config.api_key_env} in the current WSL shell."],
        )
    try:
        import dashscope
        from dashscope.audio.asr import Recognition
    except Exception as exc:
        raise ToolError(
            "DashScope SDK is not installed.",
            detail=f"Import error: {exc}",
            hints=["Run `uv sync --extra dashscope --extra dev`."],
        ) from exc

    dashscope.api_key = api_key
    recognition = Recognition(
        model=config.asr_model,
        format="wav",
        sample_rate=16000,
        language_hints=config.language_hints,
        callback=None,
    )
    result = recognition.call(str(audio_path))
    if getattr(result, "status_code", None) and getattr(result, "status_code") >= 300:
        raise ToolError("DashScope ASR failed.", detail=str(getattr(result, "message", result)))
    return normalize_dashscope_result(result, get_duration(audio_path))


def normalize_dashscope_result(result: Any, duration: float) -> list[Segment]:
    data = None
    if hasattr(result, "get_sentence"):
        data = result.get_sentence()
    if data is None and hasattr(result, "output"):
        data = result.output
    if data is None:
        data = result

    segments: list[Segment] = []
    for item in flatten_possible_segments(data):
        text = clean_text(str(item.get("text") or item.get("sentence") or item.get("result") or ""))
        if not text:
            continue
        start = milliseconds_to_seconds(item.get("begin_time", item.get("start_time", item.get("start", 0))))
        end = milliseconds_to_seconds(item.get("end_time", item.get("end", duration * 1000)))
        segments.append(Segment(start=start, end=end, text=text))
    if not segments:
        text = clean_text(str(data))
        if text:
            segments.append(Segment(start=0.0, end=duration, text=text))
    return fix_segment_times(segments, duration)


def flatten_possible_segments(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("sentences", "sentence", "results", "transcripts"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield item
                return
        yield data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item


def translate_segments_dashscope(segments: list[Segment], target: str, config: DashScopeConfig) -> list[Segment]:
    if target != "zh":
        raise ToolError(f"Unsupported translation target: {target}")
    api_key = os.getenv(config.api_key_env)
    if not api_key:
        raise ToolError(
            f"{config.api_key_env} is required for --translate-to.",
            hints=[f"Run `source ~/.zshrc` or export {config.api_key_env} in the current WSL shell."],
        )
    try:
        import dashscope
        from dashscope import Generation
    except Exception as exc:
        raise ToolError(
            "DashScope SDK is not installed.",
            detail=f"Import error: {exc}",
            hints=["Run `uv sync --extra dashscope --extra dev`."],
        ) from exc

    dashscope.api_key = api_key
    output: list[Segment] = []
    batch_size = 20
    for offset in range(0, len(segments), batch_size):
        batch = segments[offset : offset + batch_size]
        payload = "\n".join(f"{i + 1}. {seg.text}" for i, seg in enumerate(batch))
        prompt = (
            "请把下面的视频转写文本整理为中文为主的笔记素材。要求：\n"
            "1. 保留不适合翻译的英文专有名词、产品名、代码名。\n"
            "2. 不要添加原文没有的信息。\n"
            "3. 逐条输出，数量和编号必须与输入一致。\n\n"
            f"{payload}"
        )
        response = Generation.call(model=config.llm_model, prompt=prompt)
        if getattr(response, "status_code", 200) >= 300:
            raise ToolError("DashScope translation failed.", detail=str(getattr(response, "message", response)))
        text = extract_dashscope_text(response)
        translated = parse_numbered_lines(text)
        for index, seg in enumerate(batch):
            new_text = translated[index] if index < len(translated) and translated[index] else seg.text
            output.append(Segment(start=seg.start, end=seg.end, text=new_text, speaker=seg.speaker))
    return output


def extract_dashscope_text(response: Any) -> str:
    output = getattr(response, "output", None)
    if isinstance(output, dict):
        return str(output.get("text") or output.get("choices", [{}])[0].get("message", {}).get("content") or "")
    return str(output or response)
