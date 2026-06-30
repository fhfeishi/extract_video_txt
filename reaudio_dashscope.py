from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


class DashScopeReaudioError(RuntimeError):
    pass


def transcribe_dashscope(
    audio_wav: Path,
    *,
    api_key_env: str = "DASHSCOPE_API_KEY",
    asr_model: str = "paraformer-realtime-v2",
    language_hints: list[str] | None = None,
) -> list[dict[str, Any]]:
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise DashScopeReaudioError(
            f"{api_key_env} is not set. Source ~/.zshrc or export the variable before running ASR."
        )

    try:
        import dashscope
        from dashscope.audio.asr import Recognition
    except Exception as exc:
        raise DashScopeReaudioError(
            "DashScope SDK is not installed. Run `uv sync --extra dashscope --extra dev`."
        ) from exc

    dashscope.api_key = api_key
    recognition = Recognition(
        model=asr_model,
        format="wav",
        sample_rate=16000,
        language_hints=language_hints or ["zh", "en"],
        callback=None,
    )
    result = recognition.call(str(audio_wav))
    if getattr(result, "status_code", 200) >= 300:
        raise DashScopeReaudioError(f"DashScope ASR failed: {getattr(result, 'message', result)}")
    return normalize_dashscope_result(result)


def translate_segments_dashscope(
    segments: list[dict[str, Any]],
    *,
    target: str = "zh",
    api_key_env: str = "DASHSCOPE_API_KEY",
    llm_model: str = "qwen-plus",
) -> list[dict[str, Any]]:
    if target != "zh":
        raise DashScopeReaudioError(f"Unsupported translation target: {target}")
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise DashScopeReaudioError(
            f"{api_key_env} is required for translation. Source ~/.zshrc or export it first."
        )

    try:
        import dashscope
        from dashscope import Generation
    except Exception as exc:
        raise DashScopeReaudioError(
            "DashScope SDK is not installed. Run `uv sync --extra dashscope --extra dev`."
        ) from exc

    dashscope.api_key = api_key
    output: list[dict[str, Any]] = []
    batch_size = 20
    for offset in range(0, len(segments), batch_size):
        batch = segments[offset : offset + batch_size]
        payload = "\n".join(f"{index + 1}. {item.get('text', '')}" for index, item in enumerate(batch))
        prompt = (
            "请把下面的音频转写文本整理为中文为主的 Markdown 笔记素材。要求：\n"
            "1. 保留不适合翻译的英文专有名词、产品名、代码名。\n"
            "2. 不要添加原文没有的信息。\n"
            "3. 逐条输出，数量和编号必须与输入一致。\n\n"
            f"{payload}"
        )
        response = Generation.call(model=llm_model, prompt=prompt)
        if getattr(response, "status_code", 200) >= 300:
            raise DashScopeReaudioError(f"DashScope translation failed: {getattr(response, 'message', response)}")
        translated = parse_numbered_lines(extract_dashscope_text(response))
        for index, item in enumerate(batch):
            replacement = translated[index] if index < len(translated) and translated[index] else item.get("text", "")
            updated = dict(item)
            updated["text"] = clean_text(replacement)
            output.append(updated)
    return output


def normalize_dashscope_result(result: Any) -> list[dict[str, Any]]:
    data = None
    if hasattr(result, "get_sentence"):
        data = result.get_sentence()
    if data is None and hasattr(result, "output"):
        data = result.output
    if data is None:
        data = result

    segments: list[dict[str, Any]] = []
    for item in flatten_possible_segments(data):
        text = clean_text(str(item.get("text") or item.get("sentence") or item.get("result") or ""))
        if not text:
            continue
        start = milliseconds_to_seconds(item.get("begin_time", item.get("start_time", item.get("start", 0))))
        end = milliseconds_to_seconds(item.get("end_time", item.get("end", item.get("finish", 0))))
        segments.append({"start": start, "end": end, "text": text})

    if not segments:
        text = clean_text(str(data))
        if text:
            segments.append({"start": 0.0, "end": 0.0, "text": text})
    return fix_segment_times(segments)


def flatten_possible_segments(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("sentences", "sentence", "results", "transcripts"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def fix_segment_times(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fixed: list[dict[str, Any]] = []
    for index, item in enumerate(segments):
        start = max(0.0, float(item.get("start") or 0.0))
        end = float(item.get("end") or 0.0)
        if end <= start:
            next_start = float(segments[index + 1].get("start") or 0.0) if index + 1 < len(segments) else 0.0
            end = next_start if next_start > start else start + 0.1
        fixed.append({"start": start, "end": end, "text": clean_text(str(item.get("text") or ""))})
    return fixed


def milliseconds_to_seconds(value: Any) -> float:
    try:
        return float(value) / 1000.0
    except (TypeError, ValueError):
        return 0.0


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def parse_numbered_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    parsed: list[str] = []
    for line in lines:
        line = re.sub(r"^\s*\d+\s*[\.、)]\s*", "", line).strip()
        if line:
            parsed.append(line)
    return parsed


def extract_dashscope_text(response: Any) -> str:
    output = getattr(response, "output", None)
    if isinstance(output, dict):
        choices = output.get("choices") or []
        if choices:
            return str(choices[0].get("message", {}).get("content") or "")
        return str(output.get("text") or "")
    return str(output or response)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="reaudio_dashscope.py",
        description="Transcribe an existing 16 kHz mono WAV file with DashScope and write JSON segments.",
    )
    parser.add_argument("audio_wav", help="16 kHz mono WAV file.")
    parser.add_argument("--output", default=None, help="Output JSON file. Defaults to <audio>.dashscope.json.")
    parser.add_argument("--language-hints", default="zh,en", help="Comma-separated language hints.")
    parser.add_argument("--asr-model", default="paraformer-realtime-v2")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    args = parser.parse_args(argv)

    try:
        audio_wav = Path(args.audio_wav).expanduser().resolve()
        hints = [item.strip() for item in args.language_hints.split(",") if item.strip()]
        segments = transcribe_dashscope(
            audio_wav,
            api_key_env=args.api_key_env,
            asr_model=args.asr_model,
            language_hints=hints,
        )
        output = Path(args.output).expanduser().resolve() if args.output else audio_wav.with_suffix(".dashscope.json")
        output.write_text(json.dumps({"segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {output}")
    except DashScopeReaudioError as exc:
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main(sys.argv[1:])
