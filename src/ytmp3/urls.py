"""Normalize supported single-video links before passing them to the downloader."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
_VIDEO_PATH = re.compile(r"/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})/?\Z")
_SHORT_PATH = re.compile(r"/([A-Za-z0-9_-]{11})/?\Z")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


class InvalidYouTubeURL(ValueError):
    """The input does not identify exactly one supported YouTube video."""


def normalize_youtube_url(value: str) -> str:
    """Return an HTTPS watch URL, removing playlist context and tracking parameters."""
    if not isinstance(value, str) or not value.strip():
        raise InvalidYouTubeURL("Paste a YouTube or YouTube Music video link.")
    value = value.strip()
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise InvalidYouTubeURL("Enter one complete link without spaces or line breaks.")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise InvalidYouTubeURL(
            "This link is malformed. Copy the full link from your browser."
        ) from error
    if parsed.scheme not in {"http", "https"}:
        raise InvalidYouTubeURL("Use a full YouTube link starting with https:// or http://.")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidYouTubeURL("YouTube links cannot contain sign-in credentials.")
    if host not in _YOUTUBE_HOSTS | {"youtu.be"}:
        raise InvalidYouTubeURL("Use a youtube.com, music.youtube.com, or youtu.be video link.")
    expected_port = 443 if parsed.scheme == "https" else 80
    if port is not None and port != expected_port:
        raise InvalidYouTubeURL("Use a standard YouTube link without a custom port.")

    query = parse_qs(parsed.query, keep_blank_values=True)
    video_parameters = query.get("v", [])
    if len(video_parameters) > 1:
        raise InvalidYouTubeURL("This link contains multiple video IDs. Copy a single video link.")
    video_id = None
    if host == "youtu.be":
        match = _SHORT_PATH.fullmatch(parsed.path)
        video_id = match.group(1) if match else None
    elif parsed.path in {"/watch", "/watch/"}:
        video_id = video_parameters[0] if video_parameters else None
    else:
        match = _VIDEO_PATH.fullmatch(parsed.path)
        video_id = match.group(1) if match else None

    if video_id is None and (parsed.path.rstrip("/") == "/playlist" or "list" in query):
        raise InvalidYouTubeURL(
            "Playlists are not supported yet. Copy the link to one video or song."
        )
    if video_id is None or not _VIDEO_ID.fullmatch(video_id):
        raise InvalidYouTubeURL("This link must point to one video or song with a valid video ID.")
    if video_parameters and video_parameters[0] != video_id:
        raise InvalidYouTubeURL("This link has conflicting video IDs. Copy a single video link.")
    return f"https://www.youtube.com/watch?v={video_id}"
