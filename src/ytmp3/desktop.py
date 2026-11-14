"""Native desktop launcher and the small, explicit React-to-Python bridge."""

from __future__ import annotations

import argparse
import base64
import multiprocessing
import os
import platform
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ytmp3 import APP_NAME, __version__
from ytmp3.desktop_jobs import DesktopJobs
from ytmp3.diagnostics import collect_diagnostics, write_report
from ytmp3.runtime import app_info, frontend_directory, is_packaged, resource_root
from ytmp3.tags import MAX_COVER_BYTES, image_mime


class DesktopApi:
    def __init__(self, on_ready: Any = None, *, jobs: DesktopJobs | None = None):
        self._on_ready = on_ready
        self._jobs = jobs if jobs is not None else DesktopJobs()
        self._window: Any = None
        self._dialog_lock = threading.Lock()
        self._cover_data: bytes | None = None
        self._cover_job_id: str | None = None
        self._cover_name: str | None = None

    def get_app_info(self) -> dict[str, str | bool]:
        return app_info()

    def frontend_ready(self, payload: dict[str, Any]) -> dict[str, bool]:
        if not isinstance(payload, dict) or payload.get("version") != __version__:
            raise ValueError("The frontend and Python application versions do not match.")
        if self._on_ready is not None:
            self._on_ready()
        return {"ok": True}

    def get_settings(self) -> dict[str, str]:
        return self._jobs.settings()

    def get_job(self) -> dict[str, Any]:
        return self._jobs.snapshot()

    def get_draft(self) -> dict[str, Any] | None:
        with self._dialog_lock:
            saved = self._jobs.drafts.load()
            if saved is None:
                return None
            record, data = saved
            self._jobs.restore_draft(record)
            state = self._jobs.snapshot()
            self._cover_data = data
            self._cover_job_id = state.get("preview_id") if data else None
            self._cover_name = record.get("cover_name")
            cover = None
            if data:
                mime = image_mime(data)
                cover = {
                    "name": self._cover_name or "Selected cover",
                    "preview": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}",
                }
            return {
                "url": record["url"],
                "filename": record["filename"],
                "tags": record["tags"],
                "cover": cover,
                "warning": record.get("warning"),
            }

    def save_draft(
        self, url: str, filename: str, tags: dict[str, Any], preview_id: str | None = None
    ) -> dict[str, bool]:
        with self._dialog_lock:
            cover = self._cover_data if self._cover_job_id == preview_id else None
            self._jobs.save_draft(url, filename, tags, preview_id, cover, self._cover_name)
            return {"saved": True}

    def clear_draft(self) -> dict[str, bool]:
        with self._dialog_lock:
            self._jobs.clear_draft()
            self._cover_data = None
            self._cover_name = None
            self._cover_job_id = None
            return {"cleared": True}

    def preview_video(self, url: str) -> dict[str, Any]:
        with self._dialog_lock:
            state = self._jobs.preview(url)
            self._cover_data = None
            self._cover_name = None
            self._cover_job_id = None
            return state

    def start_download(
        self,
        url: str,
        preview_job_id: str,
        filename: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._dialog_lock:
            cover = self._cover_data if self._cover_job_id == preview_job_id else None
            return self._jobs.confirm(url, preview_job_id, filename, tags, cover)

    def choose_cover(self) -> dict[str, str] | None:
        with self._dialog_lock:
            state = self._jobs.snapshot()
            if (
                state["busy"]
                or state["status"] not in {"ready", "failed", "cancelled"}
                or not state.get("preview_id")
            ):
                raise RuntimeError("Preview a video before choosing its cover.")
            if self._window is None:
                raise RuntimeError("The desktop window is not ready.")
            import webview

            selected = self._window.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=("Images (*.jpg;*.jpeg;*.png;*.webp)",),
            )
            if not selected:
                return None
            path = Path(selected[0])
            with path.open("rb") as source:
                data = source.read(MAX_COVER_BYTES + 1)
            if len(data) > MAX_COVER_BYTES:
                raise ValueError("Cover images must be 10 MB or smaller.")
            mime = image_mime(data)
            self._cover_data = data
            self._cover_name = path.name
            self._cover_job_id = state["preview_id"]
            return {
                "name": path.name,
                "preview": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}",
            }

    def import_native_cover(self, preview_id: str, source: str = "paste") -> dict[str, str]:
        from ytmp3.clipboard import native_image

        state = self._jobs.snapshot()
        if state["busy"] or not preview_id or state.get("preview_id") != preview_id:
            raise RuntimeError("Preview a video before choosing its cover.")
        data = native_image(source)
        return self.import_cover(
            preview_id,
            "Pasted image.png" if source == "paste" else "Dropped image.png",
            base64.b64encode(data).decode("ascii"),
        )

    def import_cover(self, preview_id: str, name: str, encoded: str) -> dict[str, str]:
        """Accept bounded image bytes from a drop or clipboard, never a supplied path."""
        with self._dialog_lock:
            state = self._jobs.snapshot()
            if (
                state["busy"]
                or state["status"] not in {"ready", "failed", "cancelled"}
                or not preview_id
                or state.get("preview_id") != preview_id
            ):
                raise RuntimeError("Preview a video before choosing its cover.")
            if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_COVER_BYTES + 2) // 3):
                raise ValueError("Cover images must be 10 MB or smaller.")
            try:
                data = base64.b64decode(encoded, validate=True)
            except ValueError as error:
                raise ValueError("The image data is invalid.") from error
            if len(data) > MAX_COVER_BYTES:
                raise ValueError("Cover images must be 10 MB or smaller.")
            mime = image_mime(data)
            self._cover_data = data
            self._cover_name = (
                Path(name).name[:255] if isinstance(name, str) and name else "Pasted image"
            )
            self._cover_job_id = preview_id
            return {
                "name": self._cover_name,
                "preview": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}",
            }

    def cancel_download(self) -> dict[str, Any]:
        return self._jobs.cancel()

    def choose_download_directory(self) -> dict[str, str]:
        with self._dialog_lock:
            if self._jobs.snapshot()["busy"]:
                raise RuntimeError("Wait for the current download before changing its folder.")
            if self._window is None:
                raise RuntimeError("The desktop window is not ready.")
            import webview

            current = self._jobs.settings()
            selected = self._window.create_file_dialog(
                webview.FileDialog.FOLDER,
                directory=current["download_directory"],
            )
            return self._jobs.save_directory(selected[0]) if selected else current

    def open_download_folder(self) -> dict[str, bool]:
        directory = Path(self._jobs.result_directory())
        if not directory.is_dir():
            raise RuntimeError("The download folder is no longer available.")
        if platform.system() == "Windows":
            os.startfile(str(directory))
        elif platform.system() == "Darwin":
            subprocess.run(["/usr/bin/open", str(directory)], check=True, timeout=10)
        else:
            raise RuntimeError("Opening folders is supported on Windows and macOS.")
        return {"ok": True}


def validate_dev_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "[::1]", "::1"}:
        raise ValueError("The development URL must use HTTP on localhost.")
    if parsed.username or parsed.password:
        raise ValueError("The development URL cannot contain credentials.")
    if is_packaged():
        raise ValueError("Development URLs are disabled in packaged applications.")
    return url


def launch_desktop(
    dev_url: str | None = None,
    smoke_report: Path | None = None,
    smoke_timeout: float = 30,
    _jobs: DesktopJobs | None = None,
) -> int:
    if dev_url:
        entry = validate_dev_url(dev_url)
    else:
        index = frontend_directory() / "index.html"
        if not index.is_file():
            raise FileNotFoundError(
                "Build the React interface first: npm run build --prefix frontend"
            )
        # A directory supplied as http_server root keeps only frontend assets exposed.
        entry = str(index)

    import webview

    started = time.monotonic()
    result = {"ok": False, "completed": False}
    lock = threading.Lock()
    ready = threading.Event()
    closed = threading.Event()
    close_requested = threading.Event()
    allow_close = threading.Event()
    window: Any = None

    def finish(ok: bool, reason: str | None = None) -> None:
        if smoke_report is None:
            return
        with lock:
            if result["completed"]:
                return
            result.update(ok=ok, completed=True)
            report = {
                "ok": ok,
                "app": app_info(),
                "frontend_loaded": ok,
                "bridge_round_trip": ok,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
            if reason:
                report["error"] = reason
            write_report(smoke_report, report)
        if window is not None and not closed.is_set():
            allow_close.set()
            window.destroy()

    def monitor_frontend() -> None:
        deadline = started + smoke_timeout
        while time.monotonic() < deadline and not closed.is_set():
            if ready.wait(0.1):
                # The API handler must return its Promise reply before we close WebKit.
                # React renders this marker only after awaiting that reply. Closing from
                # inside frontend_ready would strand pywebview's non-daemon reply thread.
                rendered = window.evaluate_js(
                    "document.querySelector('[data-desktop-state=\"ready\"]') !== null"
                )
                if rendered:
                    finish(True)
                    return
                time.sleep(0.05)
        finish(False, "The desktop closed or React bridge readiness timed out")

    def on_closing() -> bool:
        if allow_close.is_set():
            return True
        api._jobs.shutdown()
        close_requested.set()
        return False

    def lifecycle() -> None:
        if smoke_report:
            monitor_frontend()
            return
        dev_close_file = os.environ.get("YTMP3_DEV_CLOSE_FILE") if dev_url else None
        while not close_requested.wait(0.15):
            if closed.is_set():
                return
            if dev_close_file and Path(dev_close_file).is_file():
                api._jobs.shutdown()
                close_requested.set()
        if closed.is_set():
            return
        window.run_js("window.dispatchEvent(new Event('desktopclosing'))")
        # Stop React polling and drain Promise replies before destroying the webview.
        while api._jobs.snapshot()["busy"] and not closed.wait(0.1):
            pass
        deadline = time.monotonic() + 15
        while not closed.is_set() and time.monotonic() < deadline:
            if window.evaluate_js("document.documentElement.dataset.desktopClosing === 'ready'"):
                break
            time.sleep(0.05)
        allow_close.set()
        if not closed.is_set():
            window.destroy()

    api = DesktopApi(ready.set, jobs=_jobs)
    window = webview.create_window(
        APP_NAME,
        entry,
        js_api=api,
        width=760,
        height=800,
        min_size=(580, 600),
        background_color="#f7f7f5",
    )
    api._window = window
    window.events.closing += on_closing
    window.events.closed += closed.set
    try:
        options = {"gui": "edgechromium"} if app_info()["platform"] == "Windows" else {}
        icon_name = "app.icns" if platform.system() == "Darwin" else "app.ico"
        icon_directory = "icons" if is_packaged() else "packaging/icons"
        icon = resource_root() / icon_directory / icon_name
        if icon.is_file():
            options["icon"] = str(icon)
        # Keep inspection available in development without opening it on every restart.
        webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
        webview.start(lifecycle, debug=bool(dev_url), **options)
    finally:
        api._jobs.shutdown()
        api._jobs.wait()
        closed.set()
        close_requested.set()
        if smoke_report is not None and not result["completed"]:
            finish(False, "The desktop window closed before the React bridge was ready")
    return 0 if smoke_report is None or result["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--dev-url")
    parser.add_argument("--self-check", action="store_true", help="Run offline package checks")
    parser.add_argument("--smoke-test", action="store_true", help="Verify React in a native window")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if (args.self_check or args.smoke_test) and args.report is None:
        parser.error("--report is required for package checks")
    if args.self_check:
        report = collect_diagnostics()
        write_report(args.report, report)
        return 0 if report["ok"] else 1
    try:
        return launch_desktop(
            dev_url=args.dev_url, smoke_report=args.report if args.smoke_test else None
        )
    except Exception as error:
        if args.report:
            write_report(args.report, {"ok": False, "app": app_info(), "error": str(error)})
        else:
            raise
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
