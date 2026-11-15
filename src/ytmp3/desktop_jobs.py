"""Thread-safe desktop job state, independent of the native window and React."""

from __future__ import annotations

import copy
import re
import threading
import uuid
from typing import Any

from ytmp3.drafts import DraftError, DraftStore
from ytmp3.engine import DownloadCancelled, DownloadEngine, DownloadProgress
from ytmp3.settings import SettingsStore
from ytmp3.tags import normalize_tags
from ytmp3.urls import normalize_youtube_url


def download_error_message(error: Exception) -> str:
    message = str(error)
    lower = message.lower()
    if "not a bot" in lower or "sign in to confirm" in lower:
        return (
            "YouTube blocked this request for verification. No new MP3 was saved. "
            "Wait a few minutes before retrying. If it persists, try a different network "
            "or another public link."
        )
    if any(text in lower for text in ("private video", "login required", "sign in")):
        return "This video requires account access. Choose a public video or song."
    return re.sub(r"^ERROR:\s*", "", message).strip() or "The download could not finish. Try again."


class DesktopJobs:
    def __init__(self, settings: SettingsStore | None = None, engine: Any = None):
        self._settings = settings if settings is not None else SettingsStore()
        self.drafts = DraftStore(self._settings.path)
        self._engine = engine if engine is not None else DownloadEngine(self._settings)
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._closing = False
        self._preview_url: str | None = None
        self._thread: threading.Thread | None = None
        self._state: dict[str, Any] = {
            "job_id": None,
            "preview_id": None,
            "status": "idle",
            "busy": False,
            "downloaded_bytes": 0,
            "total_bytes": None,
            "fraction": None,
            "directory": None,
            "result": None,
            "error": None,
            "metadata": None,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def settings(self) -> dict[str, str]:
        with self._lock:
            return {"download_directory": str(self._settings.get_download_directory())}

    def save_directory(self, directory: str) -> dict[str, str]:
        with self._lock:
            if self._closing or self._state["busy"]:
                raise RuntimeError("Wait for the current download before changing its folder.")
            return {"download_directory": str(self._settings.set_download_directory(directory))}

    def clear_draft(self) -> None:
        with self._lock:
            if self._state["busy"]:
                raise RuntimeError("Wait for the current job before clearing its draft.")
            self.drafts.clear()
            self._preview_url = None
            self._state.update(
                job_id=None,
                preview_id=None,
                status="idle",
                metadata=None,
                result=None,
                error=None,
                restored=False,
            )

    def restore_draft(self, record: dict[str, Any]) -> None:
        with self._lock:
            if (
                self._state["status"] != "idle"
                or not record.get("metadata")
                or not record.get("previewed_url")
            ):
                return
            normalized = normalize_youtube_url(record["url"])
            if normalized != record["previewed_url"] or not isinstance(
                record["metadata"].get("title"), str
            ):
                return
            self._preview_url = normalized
            identity = uuid.uuid4().hex
            self._state.update(
                job_id=identity,
                preview_id=identity,
                status="ready",
                busy=False,
                metadata=copy.deepcopy(record["metadata"]),
                directory=str(self._settings.get_download_directory()),
                restored=True,
            )

    def save_draft(
        self,
        url: str,
        filename: str,
        tags: dict[str, Any],
        preview_id: str | None,
        cover_data: bytes | None = None,
        cover_name: str | None = None,
    ) -> None:
        with self._lock:
            if (
                self._state["status"] == "complete"
                and preview_id
                and preview_id == self._state["preview_id"]
            ):
                self.drafts.clear()
                return
            try:
                normalized = normalize_youtube_url(url)
            except ValueError:
                normalized = None
            approved = bool(
                preview_id
                and preview_id == self._state["preview_id"]
                and normalized == self._preview_url
            )
            self.drafts.save(
                {
                    "url": url,
                    "filename": filename,
                    "tags": tags,
                    "metadata": copy.deepcopy(self._state["metadata"]) if approved else None,
                    "previewed_url": normalized if approved else None,
                },
                cover_data if approved and tags.get("cover") == "local" else None,
                cover_name,
            )

    def preview(self, url: str) -> dict[str, Any]:
        return self._start(url, preview=True)

    def confirm(
        self,
        url: str,
        preview_job_id: str,
        filename: str | None = None,
        tags: dict[str, Any] | None = None,
        cover_data: bytes | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_youtube_url(url)
        with self._lock:
            if (
                self._state["status"] not in {"ready", "failed", "cancelled"}
                or self._state["busy"]
                or self._state["preview_id"] != preview_job_id
                or self._preview_url != normalized
            ):
                raise RuntimeError("Preview this video before downloading it.")
            metadata = copy.deepcopy(self._state["metadata"])
            options = normalize_tags(tags, metadata or {})
            if options["enabled"] and options["cover"] == "local" and not cover_data:
                raise ValueError("Choose a local cover image before downloading.")
            self._start(
                normalized,
                preview=False,
                filename=filename,
                tags=options,
                cover_data=cover_data,
                preview_id=preview_job_id,
            )
            self._state["metadata"] = metadata
            return self.snapshot()

    def start(self, url: str) -> dict[str, Any]:
        return self._start(url, preview=False)

    def _start(
        self,
        url: str,
        *,
        preview: bool,
        filename: str | None = None,
        tags: dict[str, Any] | None = None,
        cover_data: bytes | None = None,
        preview_id: str | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_youtube_url(url)
        with self._lock:
            if self._closing:
                raise RuntimeError("The app is closing.")
            if self._state["busy"]:
                raise RuntimeError("A download is already running.")
            directory = self._settings.get_download_directory()
            self._preview_url = normalized if preview or preview_id else None
            self._cancel = threading.Event()
            self._state.update(
                job_id=uuid.uuid4().hex,
                preview_id=preview_id,
                restored=False,
                status="resolving",
                busy=True,
                downloaded_bytes=0,
                total_bytes=None,
                fraction=None,
                directory=str(directory),
                result=None,
                metadata=None,
                error=None,
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(normalized, directory, preview, filename, tags, cover_data),
                name="ytmp3-desktop-job",
            )
            try:
                self._thread.start()
            except Exception:
                self._state.update(status="failed", busy=False, error="Cannot start the download.")
                raise
            return self.snapshot()

    def cancel(self) -> dict[str, Any]:
        with self._lock:
            if self._state["busy"]:
                self._cancel.set()
                self._state["status"] = "cancelling"
            return self.snapshot()

    def shutdown(self) -> None:
        with self._lock:
            self._closing = True
            self.cancel()

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)

    def result_directory(self) -> str:
        with self._lock:
            if self._state["busy"] or not self._state["result"]:
                raise RuntimeError("Complete a download before opening its folder.")
            from pathlib import Path

            return str(Path(self._state["result"]["path"]).parent)

    def _progress(self, event: DownloadProgress) -> None:
        with self._lock:
            if event.metadata is not None:
                self._state["metadata"] = copy.deepcopy(event.metadata)
            # Final status is decided by the engine's result/exception after cleanup.
            if event.stage in {"complete", "cancelled", "failed"}:
                return
            self._state.update(
                status="cancelling" if self._cancel.is_set() else event.stage,
                downloaded_bytes=event.downloaded_bytes,
                total_bytes=event.total_bytes,
                fraction=event.fraction,
            )

    def _run(
        self,
        url: str,
        directory: Any,
        preview: bool = False,
        filename: str | None = None,
        tags: dict[str, Any] | None = None,
        cover_data: bytes | None = None,
    ) -> None:
        try:
            if preview:
                metadata = self._engine.preview(
                    url, cancel=self._cancel, on_progress=self._progress
                )
                with self._lock:
                    if self._cancel.is_set():
                        raise DownloadCancelled("Preview cancelled.")
                    self._state.update(
                        status="ready",
                        preview_id=self._state["job_id"],
                        metadata=metadata,
                        result=None,
                        error=None,
                    )
                return
            result = self._engine.download(
                url,
                directory=directory,
                on_progress=self._progress,
                cancel=self._cancel,
                **({"filename": filename} if filename else {}),
                **({"tags": tags} if tags is not None else {}),
                **({"cover_data": cover_data} if cover_data is not None else {}),
            )
            with self._lock:
                self._state.update(
                    status="complete",
                    result={
                        "path": str(result.path),
                        "title": result.title,
                        "video_id": result.video_id,
                    },
                    error=None,
                )
                try:
                    self.drafts.clear()
                except DraftError as error:
                    self._state["draft_warning"] = str(error)
        except DownloadCancelled:
            with self._lock:
                self._state.update(status="cancelled", error=None)
        except Exception as error:
            with self._lock:
                self._state.update(
                    status="cancelled" if self._cancel.is_set() else "failed",
                    error=None if self._cancel.is_set() else download_error_message(error),
                )
        finally:
            with self._lock:
                self._state["busy"] = False
