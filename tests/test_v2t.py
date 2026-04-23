from pathlib import Path

import pytest

import v2t


def test_format_transcript_groups_segments_into_paragraphs() -> None:
    result = {
        "segments": [
            {"text": "This opening sentence is intentionally long enough to trigger a paragraph break."},
            {"text": "Second sentence."},
            {"text": "Third sentence."},
        ]
    }

    assert (
        v2t.format_transcript(result, max_paragraph_chars=40)
        == "This opening sentence is intentionally long enough to trigger a paragraph break.\n\nSecond sentence. Third sentence."
    )


def test_format_transcript_uses_plain_text_when_segments_missing() -> None:
    assert v2t.format_transcript({"text": "Standalone transcript"}) == "Standalone transcript"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00"),
        (65, "01:05"),
        (3661, "1:01:01"),
    ],
)
def test_format_duration(seconds: float, expected: str) -> None:
    assert v2t.format_duration(seconds) == expected


@pytest.mark.parametrize(
    ("num_bytes", "expected"),
    [
        (999, "999 B"),
        (1024, "1.0 KB"),
        (1024 * 1024, "1.0 MB"),
    ],
)
def test_format_size(num_bytes: int, expected: str) -> None:
    assert v2t.format_size(num_bytes) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.com/video.mp4", True),
        ("http://example.com/video.mp4", True),
        ("ftp://example.com/video.mp4", False),
        ("/tmp/video.mp4", False),
    ],
)
def test_is_url(value: str, expected: bool) -> None:
    assert v2t.is_url(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc", True),
        ("https://youtu.be/abc", True),
        ("https://example.com/watch?v=abc", False),
    ],
)
def test_is_youtube_url(value: str, expected: bool) -> None:
    assert v2t.is_youtube_url(value) is expected


def test_get_unique_path_adds_numeric_suffix(tmp_path: Path) -> None:
    original = tmp_path / "movie.mp4"
    original.write_text("data", encoding="utf-8")

    assert v2t.get_unique_path(str(original)) == str(tmp_path / "movie_1.mp4")


class _Headers:
    def __init__(self, filename: str | None) -> None:
        self._filename = filename

    def get_filename(self) -> str | None:
        return self._filename


class _Response:
    def __init__(self, filename: str | None) -> None:
        self.headers = _Headers(filename)


def test_get_download_filename_prefers_header_filename() -> None:
    response = _Response("lecture.mp4")

    assert v2t.get_download_filename("https://example.com/video.mp4", response) == "lecture.mp4"


def test_get_download_filename_falls_back_to_url_path() -> None:
    response = _Response(None)

    assert (
        v2t.get_download_filename("https://example.com/files/video%20name.mp4", response)
        == "video name.mp4"
    )


def test_get_output_path_uses_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "transcripts"

    output_path = v2t.get_output_path("/tmp/movie.mp4", "srt", str(output_dir))

    assert output_path == str(output_dir / "movie_transcript.srt")
    assert output_dir.exists()


def test_resolve_youtube_download_path_prefers_hook_result() -> None:
    info = {"filepath": "info.mp4"}

    assert v2t.resolve_youtube_download_path("hook.mp4", info, "prepared.mp4") == "hook.mp4"


def test_resolve_youtube_download_path_uses_fallbacks() -> None:
    assert v2t.resolve_youtube_download_path(None, {"filepath": "info.mp4"}, None) == "info.mp4"
    assert v2t.resolve_youtube_download_path(None, {}, "prepared.mp4") == "prepared.mp4"


def test_resolve_youtube_download_path_requires_resolved_file() -> None:
    with pytest.raises(RuntimeError, match="did not provide an output file path"):
        v2t.resolve_youtube_download_path(None, {}, None)


def test_format_subtitles_supports_srt_and_vtt() -> None:
    result = {"segments": [{"start": 0.0, "end": 1.25, "text": "Hello world."}]}

    assert v2t.format_subtitles(result, "srt") == (
        "1\n00:00:00,000 --> 00:00:01,250\nHello world.\n"
    )
    assert v2t.format_subtitles(result, "vtt") == (
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.250\nHello world.\n"
    )


def test_format_subtitles_requires_segments() -> None:
    with pytest.raises(RuntimeError, match="timestamped segments"):
        v2t.format_subtitles({}, "srt")
