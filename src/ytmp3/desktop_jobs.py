"""Thread-safe desktop job state, independent of the native window and React."""

from __future__ import annotations

import copy
import re
import threading
import uuid
from typing import Any

from ytmp3.engine import DownloadCancelled, DownloadEngine, DownloadProgress
from ytmp3.settings import SettingsStore
from ytmp3.urls import normalize_youtube_url


def download_error_message(error: Exception) -> str:
    message = str(error)
    lower = message.lower()
    if "not a bot" in lower or "sign in to confirm" in lower:
        return (
            "YouTube is asking for verification for this video. "
            "Try another public link or try again later."
        )
    if any(text in lower for text in ("private video", "login required", "sign in")):
        return "This video requires account access. Choose a public video or song."
    return re.sub(r"^ERROR:\s*", "", message).strip() or "The download could not finish. Try again."


class DesktopJobs:
    def __init__(self, settings: SettingsStore | None = None, engine: Any = None):
        self._settings = settings if settings is not None else SettingsStore()
        self._engine = engine if engine is not None else DownloadEngine(self._settings)
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._closing = False
        self._thread: threading.Thread | None = None
        self._state: dict[str, Any] = {
            "job_id": None,
            "status": "idle",
            "busy": False,
            "downloaded_bytes": 0,
            "total_bytes": None,
            "fraction": None,
            "directory": None,
            "result": None,
            "error": None,
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

    def start(self, url: str) -> dict[str, Any]:
        normalized = normalize_youtube_url(url)
        with self._lock:
            if self._closing:
                raise RuntimeError("The app is closing.")
            if self._state["busy"]:
                raise RuntimeError("A download is already running.")
            directory = self._settings.get_download_directory()
            self._cancel = threading.Event()
            self._state.update(
                job_id=uuid.uuid4().hex,
                status="resolving",
                busy=True,
                downloaded_bytes=0,
                total_bytes=None,
                fraction=None,
                directory=str(directory),
                result=None,
                error=None,
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(normalized, directory),
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
            # Final status is decided by the engine's result/exception after cleanup.
            if event.stage in {"complete", "cancelled", "failed"}:
                return
            self._state.update(
                status="cancelling" if self._cancel.is_set() else event.stage,
                downloaded_bytes=event.downloaded_bytes,
                total_bytes=event.total_bytes,
                fraction=event.fraction,
            )

    def _run(self, url: str, directory: Any) -> None:
        try:
            result = self._engine.download(
                url,
                directory=directory,
                on_progress=self._progress,
                cancel=self._cancel,
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
