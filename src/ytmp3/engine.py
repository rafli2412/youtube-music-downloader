"""Single-item download engine shared by the terminal and desktop interfaces.

Retrieval is isolated in a spawned process so cancellation can stop yt-dlp and Deno.
Conversion is owned by the caller and never publishes an incomplete output file.
"""

from __future__ import annotations

import errno
import json
import logging
import multiprocessing
import os
import re
import signal
import subprocess
import tempfile
import threading
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ytmp3.runtime import tool_path
from ytmp3.settings import SettingsStore, prepare_download_directory
from ytmp3.urls import normalize_youtube_url


class DownloadError(RuntimeError):
    """A download failed with a message suitable for either user interface."""


class DownloadCancelled(DownloadError):
    pass


class DownloadBusy(DownloadError):
    pass


class UnsupportedContent(DownloadError):
    pass


class DependencyError(DownloadError):
    pass


class ConversionError(DownloadError):
    pass


@dataclass(frozen=True)
class DownloadProgress:
    stage: str
    downloaded_bytes: int = 0
    total_bytes: int | None = None

    @property
    def fraction(self) -> float | None:
        if not self.total_bytes:
            return None
        return min(1.0, self.downloaded_bytes / self.total_bytes)


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    title: str
    video_id: str


def validate_content(info: dict[str, Any]) -> None:
    if info.get("_type", "video") != "video":
        raise UnsupportedContent("Only a single video or song can be downloaded.")
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        raise UnsupportedContent("Choose a finished video or song; live streams are not supported.")
    if info.get("availability") not in {None, "public", "unlisted"}:
        raise UnsupportedContent("This item requires account access or is not publicly available.")


def safe_stem(title: str, video_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise DownloadError("YouTube returned an invalid video identifier.")
    title = unicodedata.normalize("NFC", title)
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", title).strip(" .")
    title = title.encode("utf-8")[:140].decode("utf-8", errors="ignore").rstrip(" .")
    title = title or "Audio"
    device = title.split(".", 1)[0].rstrip(" ").upper()
    if device in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} or re.fullmatch(
        r"(?:COM|LPT)[1-9¹²³]", device
    ):
        title = f"_{title}"
    return title


def publish_mp3(source: Path, directory: Path, stem: str) -> Path:
    """Publish without overwriting, even when another app creates the same name."""
    for index in range(1, 10001):
        suffix = "" if index == 1 else f" ({index})"
        destination = directory / f"{stem}{suffix}.mp3"
        try:
            if os.name == "nt":
                # Windows rename refuses an existing destination; POSIX rename replaces it.
                source.rename(destination)
            else:
                os.link(source, destination)
            return destination
        except FileExistsError:
            continue
        except OSError as error:
            if error.errno in {errno.EPERM, errno.EOPNOTSUPP, errno.EXDEV}:
                raise DownloadError(
                    "This folder does not support safe file publication. "
                    "Choose a folder on the computer's local disk."
                ) from error
            raise DownloadError(f"Cannot save the MP3 in {directory}: {error}") from error
    raise DownloadError("Too many files with the same name; choose another download folder.")


def _download_worker(connection: Any, url: str, directory: str, deno: str) -> None:
    """No GUI imports or inherited yt-dlp state in this child process."""
    try:
        # The CLI parent owns cancellation, including Windows console Ctrl+C.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if os.name != "nt":
            os.setsid()
        os.environ["YTDLP_NO_PLUGINS"] = "1"
        os.environ["DENO_NO_UPDATE_CHECK"] = "1"
        import yt_dlp

        # Only the parent reports failures. Direct child logs could duplicate errors
        # or bypass the terminal interface's control-character sanitization.
        logger = logging.getLogger("ytmp3.retrieval")
        logger.addHandler(logging.NullHandler())
        logger.propagate = False

        last_progress = 0.0

        def progress(data: dict[str, Any]) -> None:
            nonlocal last_progress
            now = time.monotonic()
            if data["status"] != "finished" and now - last_progress < 0.15:
                return
            last_progress = now
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            connection.send(
                {
                    "kind": "progress",
                    "downloaded": int(data.get("downloaded_bytes") or 0),
                    "total": int(total) if total else None,
                }
            )

        def content_filter(info: dict[str, Any], *, incomplete: bool = False) -> None:
            if not incomplete:
                validate_content(info)

        options = {
            "format": "bestaudio/best",
            "outtmpl": str(Path(directory) / "source.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": logger,
            "overwrites": False,
            "restrictfilenames": True,
            "windowsfilenames": True,
            "cachedir": False,
            "socket_timeout": 15,
            "retries": 2,
            "fragment_retries": 2,
            "fixup": "never",
            "js_runtimes": {"deno": {"path": deno}},
            "ffmpeg_location": str(Path(deno).parent),
            "remote_components": [],
            "progress_hooks": [progress],
            "match_filter": content_filter,
            "extractor_args": {"youtube": {"player_client": ["default"]}},
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            if not info:
                raise UnsupportedContent("This item is unavailable or cannot be downloaded.")
            validate_content(info)
            source = Path(downloader.prepare_filename(info))
        connection.send(
            {
                "kind": "result",
                "source": str(source),
                "id": info["id"],
                "title": info.get("title") or info["id"],
            }
        )
    except Exception as error:
        connection.send(
            {
                "kind": "error",
                "unsupported": isinstance(error, UnsupportedContent),
                "message": str(error),
            }
        )
    finally:
        connection.close()


def _stop_process_tree(process: Any, *, worker: bool = False) -> None:
    pid = process.pid
    if pid is None:
        return
    if os.name == "nt":
        # taskkill is provided by Windows, even with the development PATH removed.
        if process.is_alive() if worker else process.poll() is None:
            taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/taskkill.exe"
            try:
                subprocess.run(
                    [str(taskkill), "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass  # Still stop/reap the owned process if Windows tree cleanup fails.
            if process.is_alive() if worker else process.poll() is None:
                process.kill()
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            # A cancellation can arrive before a spawned worker establishes its session.
            if process.is_alive() if worker else process.poll() is None:
                process.kill()
    if worker:
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
    else:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


class DownloadEngine:
    """One active job per engine. Call from a background thread in a desktop UI.

    Cancellation uses a threading.Event owned by the caller; callbacks run on the
    caller's thread. A directory override applies to this job without changing settings.
    """

    def __init__(
        self, settings: SettingsStore | None = None, *, _worker_target: Callable = _download_worker
    ) -> None:
        self.settings = settings or SettingsStore()
        self._worker_target = _worker_target
        self._lock = threading.Lock()

    @staticmethod
    def _check_cancel(cancel: threading.Event) -> None:
        if cancel.is_set():
            raise DownloadCancelled("Download cancelled.")

    def download(
        self,
        url: str,
        directory: str | Path | None = None,
        *,
        on_progress: Callable[[DownloadProgress], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> DownloadResult:
        if not self._lock.acquire(blocking=False):
            raise DownloadBusy("A download is already running.")
        cancellation = cancel if cancel is not None else threading.Event()

        def notify(event: DownloadProgress) -> None:
            if on_progress is not None:
                on_progress(event)

        try:
            normalized = normalize_youtube_url(url)
            self._check_cancel(cancellation)
            destination = prepare_download_directory(
                directory if directory is not None else self.settings.get_download_directory()
            )
            for name in ("ffmpeg", "ffprobe", "deno"):
                path = tool_path(name)
                if not path.is_file() or (os.name != "nt" and not os.access(path, os.X_OK)):
                    raise DependencyError(f"Bundled {name} is missing. Reinstall the application.")
            with tempfile.TemporaryDirectory(prefix=".ytmp3-", dir=destination) as work:
                temporary = Path(work)
                notify(DownloadProgress("resolving"))
                item = self._retrieve(normalized, temporary, cancellation, notify)
                source = Path(item["source"])
                if source.resolve().parent != temporary.resolve() or not source.is_file():
                    raise DownloadError("The audio download did not produce a complete file.")
                self._check_cancel(cancellation)
                notify(DownloadProgress("converting"))
                mp3 = self._convert(source, temporary, cancellation)
                stem = safe_stem(item["title"], item["id"])
                self._check_cancel(cancellation)
                result = DownloadResult(
                    publish_mp3(mp3, destination, stem), item["title"], item["id"]
                )
            # Publication is the commit point. A late cancellation cannot remove a completed file.
            if on_progress is not None:
                try:
                    notify(DownloadProgress("complete"))
                except Exception:
                    pass  # A display failure must not turn a successfully saved MP3 into failure.
            return result
        except Exception as error:
            try:
                notify(
                    DownloadProgress(
                        "cancelled" if isinstance(error, DownloadCancelled) else "failed"
                    )
                )
            except Exception:
                pass
            raise
        finally:
            self._lock.release()

    def _retrieve(
        self, url: str, directory: Path, cancel: threading.Event, notify: Callable
    ) -> dict[str, Any]:
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        process = context.Process(
            target=self._worker_target,
            args=(send, url, str(directory), str(tool_path("deno"))),
        )
        started = False
        try:
            process.start()
            started = True
            send.close()
            while True:
                self._check_cancel(cancel)
                if receive.poll(0.1):
                    try:
                        event = receive.recv()
                    except EOFError as error:
                        raise DownloadError("The download process stopped unexpectedly.") from error
                    if event["kind"] == "progress":
                        notify(DownloadProgress("downloading", event["downloaded"], event["total"]))
                    elif event["kind"] == "result":
                        process.join(timeout=2)
                        return event
                    elif event["kind"] == "error":
                        error_type = (
                            UnsupportedContent if event.get("unsupported") else DownloadError
                        )
                        raise error_type(
                            event["message"] or "YouTube could not provide this audio."
                        )
                elif not process.is_alive():
                    raise DownloadError("The download process stopped unexpectedly.")
        finally:
            if started:
                _stop_process_tree(process, worker=True)
            receive.close()
            send.close()
            process.close()

    def _convert(self, source: Path, directory: Path, cancel: threading.Event) -> Path:
        output = directory / "converted.mp3"
        self._execute_tool(
            "ffmpeg",
            [
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-n",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-map_metadata",
                "-1",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(output),
            ],
            directory,
            cancel,
        )
        probe = self._execute_tool(
            "ffprobe",
            [
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "json",
                str(output),
            ],
            directory,
            cancel,
        )
        try:
            streams = json.loads(probe).get("streams", [])
            valid = streams and streams[0].get("codec_name") == "mp3" and output.stat().st_size > 0
        except (ValueError, OSError, TypeError):
            valid = False
        if not valid:
            raise ConversionError("Conversion did not produce a valid MP3 file.")
        return output

    def _execute_tool(
        self, name: str, arguments: list[str], directory: Path, cancel: threading.Event
    ) -> str:
        self._check_cancel(cancel)
        options: dict[str, Any] = {}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True
        # Files avoid blocked pipes when FFmpeg emits diagnostics during a long job.
        with (
            tempfile.TemporaryFile(dir=directory) as stdout,
            tempfile.TemporaryFile(dir=directory) as stderr,
        ):
            process = subprocess.Popen(
                [str(tool_path(name)), *arguments],
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                **options,
            )
            try:
                while process.poll() is None:
                    self._check_cancel(cancel)
                    cancel.wait(0.1)
                self._check_cancel(cancel)
                if process.returncode:
                    stderr.seek(max(0, stderr.tell() - 2000))
                    details = stderr.read().decode("utf-8", errors="replace").strip()
                    raise ConversionError(
                        f"{name} failed: {details or 'unable to process this audio'}"
                    )
                stdout.seek(0)
                return stdout.read().decode("utf-8", errors="replace")
            finally:
                if process.poll() is None:
                    _stop_process_tree(process)
