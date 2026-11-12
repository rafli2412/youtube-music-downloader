#!/usr/bin/env python3
"""Open an isolated desktop test session; --offline uses synthetic audio fixtures.

All UI interaction is manual. Test settings/output live beneath --directory, leaving
normal app preferences alone. Finished files may be inspected after closing the app.
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import sys
import time
from pathlib import Path


def fixture_worker(connection, url, directory, deno):
    from ytmp3.engine_check import _probe_worker

    if "BaW_jenozKc" in url:
        return _probe_worker(connection, url, directory, deno)
    if os.name != "nt":
        os.setsid()
    if "abcdefghijk" in url:
        connection.send(
            {"kind": "error", "unsupported": False, "message": "This test video is unavailable."}
        )
        connection.close()
        return
    connection.send({"kind": "progress", "downloaded": 25, "total": 100})
    time.sleep(120)  # The engine must kill this process when the UI cancels.


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from ytmp3.desktop import launch_desktop
    from ytmp3.desktop_jobs import DesktopJobs
    from ytmp3.engine import DownloadEngine
    from ytmp3.settings import SettingsStore

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = args.directory.resolve()
    settings = SettingsStore(root / "settings.json")
    if not settings.path.exists():
        settings.set_download_directory(root / "downloads")
    engine = (
        DownloadEngine(settings, _worker_target=fixture_worker)
        if args.offline
        else DownloadEngine(settings)
    )
    return launch_desktop(_jobs=DesktopJobs(settings, engine))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
