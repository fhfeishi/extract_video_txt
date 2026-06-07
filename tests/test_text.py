from video_text_tool.models import Segment
from video_text_tool.text import format_srt_time, split_long_segments, split_text


def test_split_text_prefers_sentence_punctuation() -> None:
    assert split_text("第一句。第二句。第三句。", 4) == ["第一句。", "第二句。", "第三句。"]


def test_split_long_segments_preserves_bounds() -> None:
    segments = [Segment(start=0, end=10, text="第一句。第二句。")]

    result = split_long_segments(segments, max_chars=4)

    assert [item.text for item in result] == ["第一句。", "第二句。"]
    assert result[0].start == 0
    assert result[-1].end == 10


def test_format_srt_time_rolls_milliseconds() -> None:
    assert format_srt_time(1.9999) == "00:00:02,000"
