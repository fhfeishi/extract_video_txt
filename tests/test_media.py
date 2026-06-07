from video_text_tool.media import (
    SubtitleStream,
    choose_subtitle_stream,
    find_external_subtitles,
    parse_srt,
    parse_vtt,
)


def test_parse_srt_cleans_text() -> None:
    segments = parse_srt(
        """
1
00:00:01,000 --> 00:00:02,500
hello
world
"""
    )

    assert len(segments) == 1
    assert segments[0].start == 1
    assert segments[0].end == 2.5
    assert segments[0].text == "hello world"


def test_parse_vtt_skips_header() -> None:
    segments = parse_vtt(
        """
WEBVTT

00:00:01.000 --> 00:00:02.000
hello
"""
    )

    assert segments[0].text == "hello"


def test_find_external_subtitles_prefers_zh(tmp_path) -> None:
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"")
    (tmp_path / "demo.en.srt").write_text("", encoding="utf-8")
    (tmp_path / "demo.zh.srt").write_text("", encoding="utf-8")

    result = find_external_subtitles(video)

    assert [item.path.name for item in result[:2]] == ["demo.zh.srt", "demo.en.srt"]


def test_choose_subtitle_stream_prefers_requested_language() -> None:
    streams = [
        SubtitleStream(index=2, codec="mov_text", language="eng"),
        SubtitleStream(index=3, codec="mov_text", language="zho"),
    ]

    assert choose_subtitle_stream(streams, lang="zh").index == 3
    assert choose_subtitle_stream(streams, stream_index=2).index == 2
