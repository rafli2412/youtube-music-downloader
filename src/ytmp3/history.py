"""Shared, transactional download records. Deleting a record never touches audio."""

from __future__ import annotations

import sqlite3
import unicodedata
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ytmp3.urls import normalize_youtube_url


class HistoryStore:
    def __init__(self, settings_path: Path):
        self.path = settings_path.with_name("history.sqlite3")

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=5)) as connection, connection:
            connection.row_factory = sqlite3.Row
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("This history was created by a newer app version.")
            connection.execute("""CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT, song_title TEXT NOT NULL,
                filename TEXT NOT NULL, url TEXT NOT NULL, path TEXT NOT NULL,
                downloaded_at TEXT NOT NULL)""")
            connection.execute("PRAGMA user_version = 1")
            yield connection

    def add(self, path: Path, song_title: str, url: str) -> int:
        url = normalize_youtube_url(url)
        path = path.resolve()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO downloads(song_title, filename, url, path, downloaded_at) "
                "VALUES(?,?,?,?,?)",
                (song_title, path.name, url, str(path), datetime.now(UTC).isoformat()),
            )
            return int(cursor.lastrowid)

    def page(self, before: int | None = None, query: str = "") -> dict[str, Any]:
        if before is not None and (type(before) is not int or before < 1):
            raise ValueError("Invalid history page.")
        if not isinstance(query, str) or len(query) > 500:
            raise ValueError("History searches must be 500 characters or fewer.")
        needle = unicodedata.normalize("NFKC", query.strip()).casefold()
        with self._connect() as db:
            db.create_function(
                "search_text",
                1,
                lambda text: unicodedata.normalize("NFKC", text).casefold(),
                deterministic=True,
            )
            rows = db.execute(
                "SELECT * FROM downloads WHERE (? IS NULL OR id < ?) "
                "AND (? = '' OR instr(search_text(song_title), ?) > 0 "
                "OR instr(search_text(filename), ?) > 0) ORDER BY id DESC LIMIT 101",
                (before, before, needle, needle, needle),
            ).fetchall()
        entries = [dict(row, available=Path(row["path"]).is_file()) for row in rows[:100]]
        return {"entries": entries, "next_cursor": entries[-1]["id"] if len(rows) > 100 else None}

    def get(self, entry_id: int) -> dict[str, Any]:
        if type(entry_id) is not int or entry_id < 1:
            raise ValueError("Invalid history entry.")
        with self._connect() as db:
            row = db.execute("SELECT * FROM downloads WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            raise ValueError("This history entry is no longer available.")
        return dict(row)

    def remove(self, entry_id: int) -> None:
        self.get(entry_id)
        with self._connect() as db:
            db.execute("DELETE FROM downloads WHERE id = ?", (entry_id,))

    def clear(self) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM downloads")


def fallback_song_title(metadata: dict[str, Any]) -> str:
    """Small conservative fallback for terminal downloads without a title tag."""
    import re

    track = metadata.get("track")
    if isinstance(track, str) and track.strip():
        return track.strip()
    title = str(metadata.get("title") or "").strip()
    noise = re.compile(
        r"^(?:(?:official|resmi|lyric|lyrics|lirik|music|musik|video|audio|hd|4k|1080p)\s*)+$", re.I
    )

    def label(match):
        prefix = title[: match.start()].strip()
        if (
            prefix
            and not re.search(r"\s[-–—|:]$", prefix)
            and noise.fullmatch((match[1] if match[1] is not None else match[2]).strip())
        ):
            return ""
        return match[0]

    title = re.sub(r"\(([^()]*)\)|\[([^\[\]]*)\]", label, title)
    title = re.sub(r"\s+", " ", title).strip()
    channel = str(metadata.get("channel") or "").strip().casefold()
    channel = re.sub(r"(?:\s*[-–—|:]?\s*(?:official|topic)|vevo)$", "", channel).strip()
    split = re.match(r"^(.+?)\s+[-–—|:]\s+(.+)$", title)
    if (
        split
        and split[1].casefold() == channel
        and not re.search(r"[&,]|\b(?:feat|ft)\b", split[1], re.I)
    ):
        return split[2]
    return title
