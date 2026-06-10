from video_text_tool.cache import (
    asr_cache_key,
    asr_cache_path,
    load_asr_cache,
    save_asr_cache,
)
from video_text_tool.models import Backend, RunConfig, Segment


def build_config(tmp_path, **overrides):
    media = tmp_path / "demo.mp3"
    if not media.exists():
        media.write_bytes(b"fake-audio")
    return RunConfig(input_path=media, backend=Backend.DASHSCOPE, **overrides)


def test_asr_cache_key_changes_with_content_and_clip(tmp_path) -> None:
    config = build_config(tmp_path)
    key_full = asr_cache_key(config, Backend.DASHSCOPE)

    clipped = build_config(tmp_path, max_seconds=10)
    assert asr_cache_key(clipped, Backend.DASHSCOPE) != key_full

    config.input_path.write_bytes(b"other-audio")
    assert asr_cache_key(config, Backend.DASHSCOPE) != key_full


def test_save_and_load_asr_cache_roundtrip(tmp_path) -> None:
    segments = [Segment(start=0.0, end=1.5, text="hello")]
    path = asr_cache_path(tmp_path, "demo", "key123")

    save_asr_cache(path, segments, backend=Backend.DASHSCOPE, model="paraformer-realtime-v2")

    assert path.parent.name == ".cache"
    assert load_asr_cache(path) == segments


def test_load_asr_cache_rejects_invalid_payload(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    assert load_asr_cache(missing) is None

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not json", encoding="utf-8")
    assert load_asr_cache(corrupt) is None

    bad_schema = tmp_path / "bad.json"
    bad_schema.write_text('{"segments": [{"text": "no times"}]}', encoding="utf-8")
    assert load_asr_cache(bad_schema) is None
