"""Conservative album suggestions from explicit English/Indonesian descriptions."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_LABEL = re.compile(r"^[ \t]*album[ \t]*:[ \t]*(.*?)[ \t]*$", re.I | re.M)
_PHRASE = re.compile(
    r"\b(?:(?:taken\s+)?from\s+(?:the\s+)?album|"
    r"diambil\s+dari\s+album|(?:lagu\s+ini\s+)?merupakan\s+bagian\s+dari\s+album)[ \t]+",
    re.I,
)
_QUOTES = {'"': '"', "'": "'", "“": "”", "‘": "’", "«": "»"}


def _quoted(value: str) -> tuple[str, str] | None:
    closing = _QUOTES.get(value[:1])
    if not closing:
        return None
    end = value.find(closing, 1)
    if end < 0:
        return None
    return value[1:end], value[end + 1 :]


def _candidate(value: str) -> str | None:
    value = re.sub(r"\s+", " ", value).strip()
    if (
        not value
        or len(value) > 200
        or not any(char.isalnum() for char in value)
        or re.search(r"https?://|www\.|[#@|;/]|[\x00-\x1f]", value, re.I)
        or any(char in value for char in '"“”«»')
        or re.search(
            r"\b(?:out now|available now|stream now|subscribe|dengarkan sekarang)\b", value, re.I
        )
    ):
        return None
    return value


def description_album(description: Any) -> str | None:
    """Require explicit boundaries and one distinct candidate; never guess from prose."""
    if not isinstance(description, str) or len(description) > 100_000:
        return None
    candidates: dict[str, str] = {}
    uncertain = False

    def add(value: str | None) -> None:
        nonlocal uncertain
        candidate = _candidate(value) if value is not None else None
        if candidate is None:
            uncertain = True
        else:
            key = unicodedata.normalize("NFKC", candidate).casefold()
            candidates.setdefault(key, candidate)

    for match in _LABEL.finditer(description):
        value = match[1].strip()
        if value[:1] in _QUOTES:
            quoted = _quoted(value)
            add(quoted[0] if quoted and not quoted[1].strip() else None)
        else:
            add(value)
    # Some official descriptions put the quoted name before the album label.
    # Require a complete heading, not a playlist title or an arbitrary prose mention.
    for line in description.splitlines():
        heading = re.sub(r"^[ \t]*(?:▶\ufe0f?|►|▸)[ \t]*", "", line).strip()
        quoted = _quoted(heading)
        if quoted and re.fullmatch(r"[ \t]+album[ \t]*", quoted[1], re.I):
            add(quoted[0])
    for match in _PHRASE.finditer(description):
        # Negated references do not establish the recording's album.
        prefix = description[max(0, match.start() - 30) : match.start()]
        if re.search(r"\b(?:not|never|bukan|tidak)\s*$", prefix, re.I):
            uncertain = True
            continue
        remainder = description[match.end() :].split("\n", 1)[0].strip()
        quoted = _quoted(remainder)
        if quoted and not re.match(r"\s*(?:,?\s*(?:and|or|dan|atau)\b|[/|])", quoted[1], re.I):
            add(quoted[0])
        else:
            add(None)
    return next(iter(candidates.values())) if len(candidates) == 1 and not uncertain else None
