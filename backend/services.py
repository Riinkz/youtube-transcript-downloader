"""Core helpers for the YouTube transcript app."""

from __future__ import annotations

import os
import re
import io
import logging
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from requests.exceptions import RequestException
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    VideoUnavailable,
    YouTubeTranscriptApiException,
)

YT_API_BASE = "https://www.googleapis.com/youtube/v3"
logger = logging.getLogger(__name__)


def parse_video_id(url: str) -> str:
    """Extract the YouTube video ID from a URL (or return the ID if given)."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")
    url = url.strip()

    patterns = [
        r"(?:[?&]v=|v=)([0-9A-Za-z_-]{11})",
        r"(?:be/)([0-9A-Za-z_-]{11})",
        r"(?:embed/)([0-9A-Za-z_-]{11})",
        r"(?:shorts/)([0-9A-Za-z_-]{11})",
        r"^([0-9A-Za-z_-]{11})$",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract a valid YouTube video ID from: {url}")


def parse_playlist_id(url: str) -> Optional[str]:
    """Extract playlist ID from URL (watch?list=..., playlist?list=..., etc.)."""
    if not isinstance(url, str):
        return None
    # look for list= parameter
    m = re.search(r"[?&]list=([0-9A-Za-z_-]+)", url)
    return m.group(1) if m else None


def parse_channel_id(url: str) -> Optional[str]:
    """Extract /channel/UCxxxx from URL."""
    if not isinstance(url, str):
        return None
    m = re.search(r"/channel/(UC[0-9A-Za-z_-]{22})", url)
    return m.group(1) if m else None


def parse_channel_handle(url: str) -> Optional[str]:
    """Extract @handle from channel URL if present."""
    if not isinstance(url, str):
        return None
    m = re.search(r"/@([A-Za-z0-9._-]+)", url)
    return m.group(1) if m else None


def _api_key() -> Optional[str]:
    return os.getenv("YOUTUBE_API_KEY") or os.getenv("YT_API_KEY")


def _yt_api_get(endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = _api_key()
    if not key:
        logger.warning("No YouTube API key found - playlist/channel expansion will fail")
        return None
    try:
        url = f"{YT_API_BASE}/{endpoint}"
        r = requests.get(url, params={**params, "key": key}, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            logger.error(f"YouTube API error {r.status_code} for {endpoint}: {r.text[:200]}")
            return None
    except RequestException as e:
        logger.error(f"YouTube API request failed for {endpoint}: {e}")
        return None


def fetch_video_title(video_id: str) -> Optional[str]:
    """Best-effort video title lookup. Data API if key, else oEmbed."""
    key = _api_key()
    if key:
        data = _yt_api_get("videos", {"part": "snippet", "id": video_id})
        if data and data.get("items"):
            try:
                return (data["items"][0]["snippet"]["title"] or "").strip() or None
            except Exception:
                pass
    try:
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=8,
        )
        if r.status_code == 200:
            return (r.json().get("title") or "").strip() or None
    except RequestException:
        pass

    return None


def get_available_transcripts(video_id: str) -> List[Dict[str, str]]:
    """Return available transcript languages (name, code, is_generated)."""
    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
    except YouTubeTranscriptApiException:
        return []

    langs: List[Dict[str, str]] = []
    for t in transcript_list:
        langs.append(
            {
                "language": t.language,
                "language_code": t.language_code,
                "is_generated": t.is_generated,
            }
        )
    return sorted(langs, key=lambda x: x["language"])


def _to_raw_segments(fetched: Any) -> List[Dict[str, Any]]:
    """Handle different return types from youtube-transcript-api versions."""
    if hasattr(fetched, "to_raw_data"):
        return list(fetched.to_raw_data())
    return list(fetched)


def normalize_transcript(
    segments: Iterable[Dict[str, Any]], include_timestamps: bool = False
) -> str:
    """Convert transcript segments to plain text with optional timestamps."""
    lines: List[str] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if include_timestamps:
            start_seconds = float(seg.get("start") or 0)
            minutes = int(start_seconds // 60)
            seconds = int(start_seconds % 60)
            lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def fetch_transcript(
    video_id: str,
    language_code: Optional[str] = None,
    include_timestamps: bool = False,
) -> Tuple[str, str]:
    """Retrieve and normalize transcript for the video. Returns (text, language_used)."""
    api = YouTubeTranscriptApi()
    try:
        if language_code:
            try:
                fetched = api.fetch(video_id, languages=[language_code])
                used_language = getattr(fetched, "language_code", language_code)
            except CouldNotRetrieveTranscript:
                tlist = api.list(video_id)
                candidate = None
                try:
                    candidate = tlist.find_manually_created_transcript([language_code])
                except Exception:
                    for t in tlist:
                        candidate = t
                        break
                if candidate is None:
                    raise ValueError("No transcripts available for this video.")
                try:
                    fetched = candidate.translate(language_code).fetch()
                    used_language = language_code
                except Exception:
                    fetched = candidate.fetch()
                    used_language = candidate.language_code
        else:
            fetched = api.fetch(video_id)
            used_language = getattr(fetched, "language_code", "")

    except InvalidVideoId:
        raise ValueError("Invalid video ID provided; could not fetch transcript.")
    except VideoUnavailable:
        raise ValueError("The requested video is unavailable or private.")
    except CouldNotRetrieveTranscript as ex:
        raise ValueError(str(ex))
    except YouTubeTranscriptApiException as ex:
        raise ValueError(str(ex))

    raw_segments = _to_raw_segments(fetched)
    transcript_text = normalize_transcript(raw_segments, include_timestamps=include_timestamps)
    return transcript_text, used_language


def expand_playlist_video_ids(playlist_id: str, limit: int = 50) -> List[str]:
    """Return video IDs from a playlist (requires API key)."""
    data = _yt_api_get("playlistItems", {
        "part": "contentDetails",
        "maxResults": 50,
        "playlistId": playlist_id,
    })
    results: List[str] = []
    if not data:
        return results
    while True:
        for it in data.get("items", []):
            vid = it.get("contentDetails", {}).get("videoId")
            if vid:
                results.append(vid)
                if len(results) >= limit:
                    return results
        token = data.get("nextPageToken")
        if not token or len(results) >= limit:
            break
        data = _yt_api_get("playlistItems", {
            "part": "contentDetails",
            "maxResults": 50,
            "playlistId": playlist_id,
            "pageToken": token,
        }) or {}
    return results


def _uploads_playlist_id(channel_id: str) -> Optional[str]:
    data = _yt_api_get("channels", {"part": "contentDetails", "id": channel_id})
    try:
        return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except Exception:
        return None


def _resolve_channel_id_from_handle(handle: str) -> Optional[str]:
    data = _yt_api_get("search", {"part": "snippet", "type": "channel", "q": f"@{handle}", "maxResults": 1})
    try:
        return data["items"][0]["snippet"]["channelId"]
    except Exception:
        return None


def expand_channel_recent_video_ids(channel_url: str, limit: int = 50) -> List[str]:
    """Return recent video IDs for a channel (requires API key)."""
    cid = parse_channel_id(channel_url)
    if not cid:
        handle = parse_channel_handle(channel_url)
        if handle:
            cid = _resolve_channel_id_from_handle(handle)
    if not cid:
        return []

    uploads = _uploads_playlist_id(cid)
    if not uploads:
        return []
    return expand_playlist_video_ids(uploads, limit=limit)


def expand_inputs_to_video_ids(
    urls: List[str],
    playlist_url: Optional[str] = None,
    channel_url: Optional[str] = None,
    limit: int = 50,
) -> Tuple[List[str], List[str]]:
    """Expand mixed inputs to video IDs. Returns (video_ids, errors)."""
    errors: List[str] = []
    out: List[str] = []
    seen = set()

    # Direct URLs list
    for u in urls or []:
        try:
            vid = parse_video_id(u)
            if vid not in seen:
                out.append(vid); seen.add(vid)
        except ValueError:
            pl = parse_playlist_id(u)
            ch = parse_channel_id(u) or parse_channel_handle(u)
            if not (pl or ch):
                errors.append(f"Unrecognized URL (not a video/playlist/channel): {u}")
    if playlist_url:
        if not _api_key():
            errors.append("Playlist expansion requires YOUTUBE_API_KEY / YT_API_KEY.")
        else:
            plid = parse_playlist_id(playlist_url)
            if plid:
                vids = expand_playlist_video_ids(plid, limit=limit)
                for v in vids:
                    if v not in seen:
                        out.append(v); seen.add(v)
            else:
                errors.append("Could not extract playlist ID from playlist_url.")
    if channel_url:
        if not _api_key():
            errors.append("Channel expansion requires YOUTUBE_API_KEY / YT_API_KEY.")
        else:
            vids = expand_channel_recent_video_ids(channel_url, limit=limit)
            if vids:
                for v in vids:
                    if v not in seen:
                        out.append(v); seen.add(v)
            else:
                errors.append("Could not resolve channel videos from channel_url.")

    return out, errors


def sanitize_filename(name: str) -> str:
    cleaned = (name or "").replace("\\", "").replace("/", "").replace(":", "")
    cleaned = cleaned.replace("*", "").replace("?", "").replace('"', "")
    cleaned = cleaned.replace("<", "").replace(">", "").replace("|", "").strip()
    return (cleaned or "transcript")[:120]


def unique_name(base: str, used: Dict[str, int]) -> str:
    """Return a unique filename base given a counter dict."""
    if base not in used:
        used[base] = 1
        return base
    used[base] += 1
    return f"{base} ({used[base]})"
