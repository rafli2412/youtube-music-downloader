#!/usr/bin/env python3
"""Run the desktop with React hot reload and automatic Python restarts."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:5173"


def snapshot() -> dict[str, int]:
    paths = list((ROOT / "src").rglob("*.py")) + list((ROOT / "packaging/icons").glob("app.*"))
    result = {}
    for path in paths:
        try:
            result[str(path)] = path.stat().st_mtime_ns
        except FileNotFoundError:
            pass
    return result


def stop_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()


def main() -> int:
    if not shutil.which("npm"):
        raise SystemExit("Install Node.js and npm before starting development mode.")
    if not (ROOT / "frontend/node_modules").is_dir():
        raise SystemExit("Run npm ci --prefix frontend first.")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 5173)) == 0:
            raise SystemExit("Port 5173 is in use. Stop the existing Vite server and retry.")
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    vite = subprocess.Popen(
        "npm run dev --prefix frontend"
        if os.name == "nt"
        else ["npm", "run", "dev", "--prefix", "frontend"],
        cwd=ROOT,
        shell=os.name == "nt",
        **options,
    )
    desktop = None
    with tempfile.TemporaryDirectory(prefix="ytmp3-dev-") as temporary:
        close_file = Path(temporary) / "close-desktop"

        def stop_desktop():
            if desktop is not None and desktop.poll() is None:
                close_file.touch()
                try:
                    desktop.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    print("Desktop cleanup timed out; stopping the test process.", flush=True)
                    stop_tree(desktop)

        def launch():
            close_file.unlink(missing_ok=True)
            environment = os.environ.copy()
            environment["YTMP3_DEV_CLOSE_FILE"] = str(close_file)
            process = subprocess.Popen(
                [sys.executable, "-m", "ytmp3.desktop", "--dev-url", URL],
                cwd=ROOT,
                env=environment,
                **options,
            )
            print(f"Desktop started (PID {process.pid}).", flush=True)
            return process

        try:
            deadline = time.monotonic() + 30
            while True:
                if vite.poll() is not None:
                    raise RuntimeError("Vite could not start. See its output above.")
                try:
                    # Ignore external proxy settings for this local development server.
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with opener.open(URL, timeout=1) as response:
                        if response.status == 200:
                            break
                except (OSError, urllib.error.URLError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Timed out waiting for the local Vite server.")
                time.sleep(0.2)
            previous = snapshot()
            desktop = launch()
            print(
                "React edits update instantly. Python/icon edits restart the window after cleanup. "
                "Ctrl+C or close the window to stop.",
                flush=True,
            )
            while desktop.poll() is None:
                if vite.poll() is not None:
                    raise RuntimeError("The Vite server stopped unexpectedly.")
                current = snapshot()
                if current != previous:
                    time.sleep(0.3)  # Combine editor save events before restarting.
                    previous = snapshot()
                    print("Python or icon changed; restarting the desktop…", flush=True)
                    stop_desktop()
                    desktop = launch()
                time.sleep(0.3)
            return desktop.returncode
        except KeyboardInterrupt:
            return 0
        finally:
            stop_desktop()
            stop_tree(vite)


if __name__ == "__main__":
    raise SystemExit(main())
