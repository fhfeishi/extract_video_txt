import json

from video_text_tool.models import Segment
from video_text_tool.output import write_outputs


def test_write_outputs_includes_source(tmp_path) -> None:
    segments = [Segment(start=0, end=1.5, text="hello")]

    write_outputs(segments, tmp_path, "demo", {"txt", "srt", "json"}, source="external:demo.srt")

    assert (tmp_path / "demo.txt").read_text(encoding="utf-8") == "[00:00:00.00 - 00:00:01.50] hello\n"
    assert "00:00:00,000 --> 00:00:01,500" in (tmp_path / "demo.srt").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "demo.json").read_text(encoding="utf-8"))
    assert payload["source"] == "external:demo.srt"
    assert payload["segments"][0]["text"] == "hello"
