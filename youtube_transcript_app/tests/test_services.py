# youtube_transcript_app/tests/test_services.py
"""
Unit tests for the backend services.

These tests focus on pure functions which are responsible for
parsing video IDs and normalising transcript segments. Network
interactions are not covered here since they would slow down the
tests and require network connectivity.
"""

import pytest

from youtube_transcript_app.backend.services import parse_video_id, normalize_transcript
from backend.services import parse_video_id, normalize_transcript


def test_parse_video_id_valid_watch():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert parse_video_id(url) == "dQw4w9WgXcQ"


def test_parse_video_id_shortlink():
    url = "https://youtu.be/dQw4w9WgXcQ"
    assert parse_video_id(url) == "dQw4w9WgXcQ"


def test_parse_video_id_embed():
    url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
    assert parse_video_id(url) == "dQw4w9WgXcQ"


def test_parse_video_id_invalid():
    url = "https://example.com"
    with pytest.raises(ValueError):
        parse_video_id(url)


def test_normalize_transcript_no_timestamps():
    segments = [
        {"text": "Hello world", "start": 1.0, "duration": 2.0},
        {"text": "Test", "start": 3.0, "duration": 1.0},
    ]
    result = normalize_transcript(segments)
    assert result == "Hello world\nTest"


def test_normalize_transcript_with_timestamps():
    segments = [
        {"text": "Hello world", "start": 1.0, "duration": 2.0},
        {"text": "Test", "start": 62.5, "duration": 1.0},
    ]
    result = normalize_transcript(segments, include_timestamps=True)
    # [00:01] Hello world
    # [01:02] Test
    assert result == "[00:01] Hello world\n[01:02] Test"
