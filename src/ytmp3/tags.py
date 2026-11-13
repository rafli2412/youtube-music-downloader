"""ID3v2.3 song tags and bounded cover-art loading for newly converted MP3s."""

from __future__ import annotations

import re
import ssl
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

MAX_COVER_BYTES = 10 * 1024 * 1024


def image_mime(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("Choose a JPEG, PNG, or WebP cover image.")


def release_year(info: dict[str, Any]) -> str:
    # Never derive a song year from upload_date or the generic video release_date.
    value = str(info.get("release_year") or "").strip()
    return value if re.fullmatch(r"\d{4}", value) and int(value) > 0 else ""


def normalize_tags(payload: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    if payload is not None and not isinstance(payload, dict):
        raise ValueError("Song tags must be an object.")
    defaults = {
        "enabled": True,
        "title": metadata.get("track") or metadata.get("title") or "",
        "artist": metadata.get("artist") or "",
        "album": metadata.get("album") or "",
        "year": metadata.get("release_year") or "",
        "cover": "thumbnail" if metadata.get("thumbnail") else "none",
    }
    result = {**defaults, **(payload or {})}
    if not isinstance(result["enabled"], bool):
        raise ValueError("The tags option must be enabled or disabled.")
    if not result["enabled"]:
        return {**defaults, "enabled": False, "cover": "none"}
    for field in ("title", "artist", "album", "year"):
        if not isinstance(result[field], str):
            raise ValueError(f"The {field} tag must be text.")
        result[field] = result[field].strip()
        if len(result[field]) > 1000 or "\x00" in result[field]:
            raise ValueError(f"The {field} tag is too long or contains invalid characters.")
    if result["year"] and (not re.fullmatch(r"\d{4}", result["year"]) or int(result["year"]) == 0):
        raise ValueError("Enter a four-digit release year, or leave it blank.")
    if result["cover"] not in ("thumbnail", "local", "none"):
        raise ValueError("Choose the video thumbnail, a local cover image, or no cover.")
    return {key: result[key] for key in defaults}


def validate_thumbnail_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or not parsed.hostname
        or not (parsed.hostname == "ytimg.com" or parsed.hostname.endswith(".ytimg.com"))
    ):
        raise ValueError(
            "The video thumbnail URL is not supported. Choose a local image or no cover."
        )
    return url


class _ThumbnailRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_thumbnail_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def load_thumbnail(url: str, check_cancel: Callable[[], None]) -> bytes:
    import certifi

    validate_thumbnail_url(url)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())),
        _ThumbnailRedirect(),
    )
    check_cancel()
    with opener.open(url, timeout=5) as response:
        chunks = []
        size = 0
        while True:
            check_cancel()
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_COVER_BYTES:
                raise ValueError("Cover images must be 10 MB or smaller.")
            chunks.append(chunk)
    check_cancel()
    data = b"".join(chunks)
    image_mime(data)
    return data


def write_tags(path: Path, options: dict[str, Any], jpeg_cover: bytes | None = None) -> None:
    from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, delete

    if not options["enabled"]:
        delete(path)
        return
    tags = ID3()
    for field, frame in (("title", TIT2), ("artist", TPE1), ("album", TALB), ("year", TDRC)):
        if options[field]:
            tags.add(frame(encoding=1, text=[options[field]]))
    if jpeg_cover:
        tags.add(APIC(encoding=1, mime="image/jpeg", type=3, desc="Cover", data=jpeg_cover))
    tags.update_to_v23()
    tags.save(path, v2_version=3, v1=0)
