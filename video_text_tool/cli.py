import argparse
import sys
import tempfile
import textwrap
from pathlib import Path

from pydantic import ValidationError

from .asr import choose_backend, transcribe_with_backend, translate_segments_dashscope
from .cache import asr_cache_key, asr_cache_path, asr_model_name, load_asr_cache, save_asr_cache
from .errors import ToolError
from .media import check_binary, extract_audio, render_stream_report, try_load_subtitle
from .models import Backend, Device, LocalAsrConfig, OutputConfig, RunConfig
from .output import write_outputs
from .text import split_long_segments

def main(argv: list[str] | None = None) -> None:
    try:
        args = parse_args(argv)
        run(args)
    except ValidationError as exc:
        raise SystemExit(format_validation_error(exc)) from exc
    except ToolError as exc:
        raise SystemExit(str(exc)) from exc


def run(args: argparse.Namespace) -> None:
    config = build_config(args)

    check_binary("ffmpeg")
    check_binary("ffprobe")

    if config.list_streams:
        print(render_stream_report(config.input_path), end="")
        return

    out_dir = config.output.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = config.input_path.stem

    if config.subtitle.mode.value != "ignore":
        subtitle_result = try_load_subtitle(
            config.input_path,
            out_dir / f"{stem}.subtitle.srt",
            lang=config.subtitle.lang,
            stream_index=config.subtitle.stream,
            subtitle_file=config.subtitle.file,
        )
        if subtitle_result and config.subtitle.mode.value == "only":
            segments = split_long_segments(subtitle_result.segments, config.output.max_segment_chars)
            write_outputs(segments, out_dir, stem, config.output.formats, source=subtitle_result.source)
            return
        if subtitle_result and config.subtitle.mode.value == "prefer":
            segments = split_long_segments(subtitle_result.segments, config.output.max_segment_chars)
            write_outputs(segments, out_dir, stem, config.output.formats, source=subtitle_result.source)
            return
        if config.subtitle.mode.value == "only":
            raise ToolError(
                "No usable subtitle source found.",
                detail=str(config.input_path),
                hints=[
                    "Run with `--list-streams` to inspect embedded streams and nearby external subtitle files.",
                    "Use `--subtitle ignore --backend dashscope` or `--backend funasr` to fall back to ASR.",
                ],
            )

    asr_backend = choose_backend(config)
    cache_path = asr_cache_path(out_dir, stem, asr_cache_key(config, asr_backend)) if config.use_cache else None

    segments = None
    if cache_path and not config.force:
        segments = load_asr_cache(cache_path)
    if segments is None:
        with tempfile.TemporaryDirectory(prefix="video_text_tool_") as temp_dir:
            audio_path = Path(temp_dir) / f"{stem}.16k.wav"
            extract_audio(config.input_path, audio_path, max_seconds=config.max_seconds)
            segments, asr_backend = transcribe_with_backend(audio_path, config, backend=asr_backend)
        if cache_path:
            save_asr_cache(cache_path, segments, backend=asr_backend, model=asr_model_name(config, asr_backend))

    if config.translate_to:
        segments = translate_segments_dashscope(segments, config.translate_to, config.dashscope)

    segments = split_long_segments(segments, config.output.max_segment_chars)
    write_outputs(segments, out_dir, stem, config.output.formats, source=f"asr:{asr_backend.value}")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="video-text-tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Extract a readable transcript from video/audio files.",
        epilog=textwrap.dedent(
            """
            Examples:
              video-text-tool lecture.mp4 --backend funasr --output-dir out
              video-text-tool talk.mp4 --backend dashscope --translate-to zh
              video-text-tool movie.mkv --subtitle prefer --formats txt,srt,json
            """
        ).strip(),
    )
    parser.add_argument("input", help="Video or audio file.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for txt/srt/json outputs.")
    parser.add_argument("--backend", choices=[item.value for item in Backend], default=Backend.AUTO.value)
    parser.add_argument("--device", choices=[item.value for item in Device], default=Device.AUTO.value, help="FunASR device.")
    parser.add_argument("--formats", default="txt,srt,json", help="Comma-separated output formats.")
    parser.add_argument(
        "--subtitle",
        choices=["prefer", "ignore", "only"],
        default="prefer",
        help="How to handle external/embedded subtitle sources.",
    )
    parser.add_argument(
        "--subtitle-lang",
        default="auto",
        help="Preferred subtitle language, for example zh or en. Defaults to auto.",
    )
    parser.add_argument(
        "--subtitle-stream",
        type=int,
        default=None,
        help="Embedded ffprobe stream index to extract, for example 2.",
    )
    parser.add_argument(
        "--subtitle-file",
        default=None,
        help="Explicit external subtitle file path (.srt/.ass/.vtt).",
    )
    parser.add_argument("--asr-model", default=LocalAsrConfig().asr_model, help="FunASR ASR model path/name.")
    parser.add_argument("--vad-model", default=LocalAsrConfig().vad_model, help="FunASR VAD model path/name.")
    parser.add_argument("--punc-model", default=LocalAsrConfig().punc_model, help="FunASR punctuation model path/name.")
    parser.add_argument(
        "--language-hints",
        default="zh,en",
        help="Comma-separated language hints for DashScope realtime ASR.",
    )
    parser.add_argument(
        "--translate-to",
        choices=["zh"],
        default=None,
        help="Translate/polish the transcript to Chinese with DashScope LLM.",
    )
    parser.add_argument("--dashscope-asr-model", default="paraformer-realtime-v2")
    parser.add_argument("--dashscope-llm-model", default="qwen-plus")
    parser.add_argument("--dashscope-api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument(
        "--max-segment-chars",
        type=int,
        default=90,
        help="Split long transcript segments for readable txt/srt output. Set 0 to disable.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        metavar="SEC",
        help="Only transcribe the first N seconds of audio (smoke tests, cost control).",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable the ASR result cache.")
    parser.add_argument("--force", action="store_true", help="Ignore cached ASR results and transcribe again.")
    parser.add_argument("--list-streams", action="store_true", help="Print ffprobe stream summary and exit.")
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> RunConfig:
    return RunConfig(
        input_path=args.input,
        backend=args.backend,
        subtitle={
            "mode": args.subtitle,
            "lang": args.subtitle_lang,
            "stream": args.subtitle_stream,
            "file": args.subtitle_file,
        },
        translate_to=args.translate_to,
        list_streams=args.list_streams,
        max_seconds=args.max_seconds,
        use_cache=not args.no_cache,
        force=args.force,
        local={
            "asr_model": args.asr_model,
            "vad_model": args.vad_model,
            "punc_model": args.punc_model,
            "device": args.device,
        },
        dashscope={
            "asr_model": args.dashscope_asr_model,
            "llm_model": args.dashscope_llm_model,
            "language_hints": args.language_hints,
            "api_key_env": args.dashscope_api_key_env,
        },
        output=OutputConfig(
            output_dir=args.output_dir,
            formats=args.formats,
            max_segment_chars=args.max_segment_chars,
        ),
    )


def format_validation_error(exc: ValidationError) -> str:
    lines = ["Error: invalid configuration"]
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", ())) or "config"
        lines.append(f"- {location}: {error.get('msg', 'invalid value')}")
    return "\n".join(lines)


if __name__ == "__main__":
    main(sys.argv[1:])
