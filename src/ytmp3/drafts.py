"""Atomic per-user download drafts with private, content-addressed cover copies."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from ytmp3.tags import MAX_COVER_BYTES, image_mime


class DraftError(RuntimeError):
    pass


class DraftStore:
    def __init__(self, settings_path: Path):
        self.path = settings_path.with_name("download-draft.json")
        self.covers = settings_path.parent / "draft-covers"

    def _validate(self, record: Any) -> dict[str, Any]:
        if (
            not isinstance(record, dict)
            or type(record.get("version")) is not int
            or record["version"] != 1
        ):
            raise DraftError("Unsupported or invalid saved draft. The existing file was kept.")
        for key, limit in (("url", 8192), ("filename", 1000)):
            if not isinstance(record.get(key), str) or len(record[key]) > limit:
                raise DraftError(f"Invalid saved draft {key}.")
        tags = record.get("tags")
        if not isinstance(tags, dict) or not isinstance(tags.get("enabled"), bool):
            raise DraftError("Invalid saved song tags.")
        for key in ("title", "artist", "album", "year"):
            if not isinstance(tags.get(key), str) or len(tags[key]) > 1000 or "\x00" in tags[key]:
                raise DraftError(f"Invalid saved {key} tag.")
        if tags.get("cover") not in ("local", "thumbnail", "none"):
            raise DraftError("Invalid saved cover option.")
        if record.get("metadata") is not None and not isinstance(record["metadata"], dict):
            raise DraftError("Invalid saved video information.")
        preview_url = record.get("previewed_url")
        if preview_url is not None and not isinstance(preview_url, str):
            raise DraftError("Invalid saved preview URL.")
        reference = record.get("cover_ref")
        if reference is not None and (
            not isinstance(reference, str) or not re.fullmatch("[a-f0-9]{64}", reference)
        ):
            raise DraftError("Invalid saved cover reference.")
        if record.get("cover_name") is not None and not isinstance(record["cover_name"], str):
            raise DraftError("Invalid saved cover name.")
        return record

    def _read(self) -> dict[str, Any] | None:
        try:
            with self.path.open("rb") as source:
                data = source.read(256 * 1024 + 1)
            if len(data) > 256 * 1024:
                raise DraftError("The saved draft is too large.")
            return self._validate(json.loads(data))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as error:
            raise DraftError(f"Cannot read saved draft: {error}") from error

    def load(self) -> tuple[dict[str, Any], bytes | None] | None:
        record = self._read()
        if record is None:
            return None
        cover = None
        reference = record.get("cover_ref")
        if reference:
            try:
                path = self.covers / f"{reference}.img"
                if path.is_symlink():
                    raise ValueError("Cover reference must be a regular file.")
                with path.open("rb") as source:
                    cover = source.read(MAX_COVER_BYTES + 1)
                if len(cover) > MAX_COVER_BYTES or hashlib.sha256(cover).hexdigest() != reference:
                    raise ValueError("Cover integrity check failed.")
                image_mime(cover)
            except (OSError, ValueError):
                record["warning"] = (
                    "The saved cover is unavailable. Choose an image again or select no cover."
                )
                cover = None
        return record, cover

    def _atomic(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix="draft-", delete=False
            ) as target:
                temporary = Path(target.name)
                if os.name != "nt":
                    os.fchmod(target.fileno(), 0o600)
                target.write(data)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def save(self, record: dict[str, Any], cover: bytes | None, cover_name: str | None) -> None:
        if not isinstance(record.get("url"), str):
            raise DraftError("The draft URL must be text.")
        if not record["url"].strip():
            self.clear()
            return
        self._read()  # Preserve unknown-version or corrupt files instead of overwriting them.
        record = dict(record, version=1, cover_ref=None, cover_name=None)
        if cover is not None:
            if len(cover) > MAX_COVER_BYTES:
                raise DraftError("Cover images must be 10 MB or smaller.")
            image_mime(cover)
            record["cover_ref"] = hashlib.sha256(cover).hexdigest()
            record["cover_name"] = cover_name or "Selected cover"
        self._validate(record)
        encoded = json.dumps(record, ensure_ascii=False).encode("utf-8")
        if len(encoded) > 256 * 1024:
            raise DraftError("The draft is too large to save.")
        try:
            if cover is not None:
                path = self.covers / f"{record['cover_ref']}.img"
                if (
                    not path.is_file()
                    or path.is_symlink()
                    or path.stat().st_size != len(cover)
                    or path.read_bytes() != cover
                ):
                    self._atomic(path, cover)
            self._atomic(self.path, encoded)
            self._prune(record["cover_ref"])
        except OSError as error:
            raise DraftError(f"Cannot save download draft: {error}") from error

    def _prune(self, keep: str | None = None) -> None:
        if self.covers.is_dir():
            for path in self.covers.iterdir():
                if re.fullmatch("[a-f0-9]{64}\\.img", path.name) and path.stem != keep:
                    path.unlink(missing_ok=True)

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
            self._prune()
        except OSError as error:
            raise DraftError(f"Cannot clear download draft: {error}") from error
