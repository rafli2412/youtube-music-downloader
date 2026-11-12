"""Native desktop launcher and the small, explicit React-to-Python bridge."""

from __future__ import annotations

import argparse
import multiprocessing
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ytmp3 import APP_NAME, __version__
from ytmp3.diagnostics import collect_diagnostics, write_report
from ytmp3.runtime import app_info, frontend_directory, is_packaged


class DesktopApi:
    def __init__(self, on_ready: Any = None):
        self._on_ready = on_ready

    def get_app_info(self) -> dict[str, str | bool]:
        return app_info()

    def frontend_ready(self, payload: dict[str, Any]) -> dict[str, bool]:
        if not isinstance(payload, dict) or payload.get("version") != __version__:
            raise ValueError("The frontend and Python application versions do not match.")
        if self._on_ready is not None:
            self._on_ready()
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

    api = DesktopApi(ready.set)
    window = webview.create_window(
        APP_NAME,
        entry,
        js_api=api,
        width=760,
        height=740,
        min_size=(580, 600),
        background_color="#f7f7f5",
    )
    window.events.closed += closed.set
    try:
        options = {"gui": "edgechromium"} if app_info()["platform"] == "Windows" else {}
        webview.start(monitor_frontend if smoke_report else None, debug=bool(dev_url), **options)
    finally:
        closed.set()
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
