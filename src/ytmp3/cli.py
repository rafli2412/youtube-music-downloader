"""Terminal commands sharing the same engine and settings as the desktop app."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import re
import signal
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from ytmp3 import __version__
from ytmp3.engine import DownloadCancelled, DownloadEngine, DownloadError, DownloadProgress
from ytmp3.settings import SettingsError, SettingsStore
from ytmp3.urls import InvalidYouTubeURL, normalize_youtube_url


def _display_text(value: object) -> str:
    """Remote errors and local paths must not emit terminal control sequences."""
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(value))
    return "".join(
        " " if character in "\n\r\t" else character
        for character in text
        if character in "\n\r\t" or not (ord(character) < 32 or 127 <= ord(character) <= 159)
    )


def _bytes(value: int) -> str:
    amount = float(max(0, value))
    for unit in ("B", "KiB", "MiB", "GiB"):
        if amount < 1024 or unit == "GiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    raise AssertionError("Unreachable")


class TerminalProgress:
    def __init__(self, stream: TextIO):
        self.stream = stream
        self.interactive = stream.isatty()
        self._stage: str | None = None
        self._width = 0
        self._updated = 0.0

    def __call__(self, event: DownloadProgress) -> None:
        if event.stage in {"complete", "cancelled", "failed"}:
            self.finish()
            return
        labels = {
            "resolving": "Resolving link...",
            "downloading": "Downloading audio...",
            "converting": "Converting to MP3...",
        }
        if event.stage not in labels:
            return
        changed = event.stage != self._stage
        now = time.monotonic()
        if not changed and (not self.interactive or now - self._updated < 0.15):
            return
        label = labels[event.stage]
        if self.interactive and event.stage == "downloading":
            amount = _bytes(event.downloaded_bytes)
            if event.fraction is not None:
                total = _bytes(event.total_bytes or 0)
                label = f"Downloading: {event.fraction:.0%} ({amount} / {total})"
            else:
                label = f"Downloading: {amount}"
        if self.interactive:
            self.stream.write("\r" + label.ljust(self._width))
            self._width = len(label)
        else:
            self.stream.write(label + "\n")
        self.stream.flush()
        self._stage, self._updated = event.stage, now

    def finish(self) -> None:
        if self._width:
            self.stream.write("\n")
            self.stream.flush()
            self._width = 0


@contextmanager
def _cancel_on_sigint(cancel: threading.Event):
    # CLI entrypoints run on the main thread; embedded callers can still provide
    # their own cancellation without attempting to install a thread-local handler.
    installed = threading.current_thread() is threading.main_thread()
    previous = signal.getsignal(signal.SIGINT) if installed else None
    if installed:
        signal.signal(signal.SIGINT, lambda signum, frame: cancel.set())
    try:
        yield
    finally:
        if installed:
            signal.signal(signal.SIGINT, previous)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytmp3",
        description="Save one public YouTube or YouTube Music link as MP3.",
        epilog='Shortcut: ytmp3 "https://www.youtube.com/watch?v=VIDEO_ID"',
    )
    parser.add_argument("--version", action="version", version=f"ytmp3 {__version__}")
    commands = parser.add_subparsers(dest="command")
    download = commands.add_parser("download", help="Download one video or song as MP3")
    download.add_argument("url", nargs="?", help="YouTube or YouTube Music video link")
    download.add_argument(
        "-d", "--directory", type=Path, help="Output folder for this download only"
    )
    config = commands.add_parser("config", help="View or change the saved download folder")
    configuration = config.add_subparsers(dest="config_command", required=True)
    configuration.add_parser("show", help="Show the default folder and settings file")
    setting = configuration.add_parser("set", help="Save a default folder")
    setting.add_argument("key", choices=["download-dir"])
    setting.add_argument("directory", type=Path)
    gui = commands.add_parser("gui", help="Open the desktop app")
    gui.add_argument("--dev-url", help="Load the local React development server")
    doctor = commands.add_parser("doctor", help="Check bundled assets and runtime dependencies")
    doctor.add_argument("--report", type=Path, help="Also write a JSON report")
    return parser


def _download(url: str, directory: Path | None) -> int:
    normalized = normalize_youtube_url(url)
    cancel = threading.Event()
    progress = TerminalProgress(sys.stderr)
    try:
        with _cancel_on_sigint(cancel):
            try:
                result = DownloadEngine(SettingsStore()).download(
                    normalized, directory=directory, on_progress=progress, cancel=cancel
                )
            except DownloadError as error:
                if cancel.is_set():
                    raise DownloadCancelled("Download cancelled.") from error
                raise
    finally:
        progress.finish()
    print(f"Saved: {_display_text(result.path)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0].lower().startswith(("http://", "https://")):
        arguments.insert(0, "download")
    parser = _parser()
    try:
        args = parser.parse_args(arguments)
        if args.command in {None, "download"}:
            url = getattr(args, "url", None)
            if url is None:
                if not sys.stdin.isatty():
                    parser.print_help(file=sys.stderr)
                    print(
                        "\nProvide one URL, or run ytmp3 in a terminal to be prompted.",
                        file=sys.stderr,
                    )
                    return 2
                try:
                    url = input("YouTube or YouTube Music link: ")
                except EOFError:
                    return 0
            return _download(url, getattr(args, "directory", None))
        if args.command == "config":
            settings = SettingsStore()
            if args.config_command == "show":
                print(f"Download folder: {_display_text(settings.get_download_directory())}")
                print(f"Settings file: {_display_text(settings.path)}")
            else:
                folder = settings.set_download_directory(args.directory)
                print(f"Default download folder saved: {_display_text(folder)}")
            return 0
        if args.command == "gui":
            from ytmp3.desktop import launch_desktop

            return launch_desktop(dev_url=args.dev_url)
        if args.command == "doctor":
            from ytmp3.diagnostics import collect_diagnostics, write_report

            report = collect_diagnostics()
            if args.report:
                write_report(args.report, report)
            print(json.dumps(report, indent=2))
            return 0 if report["ok"] else 1
    except (KeyboardInterrupt, DownloadCancelled):
        print("Cancelled.", file=sys.stderr)
        return 130
    except InvalidYouTubeURL as error:
        print(f"Error: {_display_text(error)}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 1
    except (DownloadError, SettingsError, OSError, ValueError) as error:
        print(f"Error: {_display_text(error)}", file=sys.stderr)
        return 1
    return 0
