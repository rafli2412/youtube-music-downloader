"""Regression checks for stopping owned processes and publishing portable filenames."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ytmp3.engine import (
    DownloadCancelled,
    DownloadEngine,
    _stop_process_tree,
    safe_stem,
)


class ProcessTests(unittest.TestCase):
    def test_cancellation_terminates_and_reaps_a_running_converter(self):
        # Exercise the actual Popen lifecycle with a controlled long-running process.
        processes = []
        create_process = subprocess.Popen
        cancel = threading.Event()

        def launch(*args, **kwargs):
            process = create_process(*args, **kwargs)
            processes.append(process)
            cancel.set()
            return process

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("ytmp3.engine.tool_path", return_value=Path(sys.executable)),
                patch("ytmp3.engine.subprocess.Popen", side_effect=launch),
                self.assertRaises(DownloadCancelled),
            ):
                DownloadEngine()._execute_tool(
                    "ffmpeg", ["-c", "import time; time.sleep(60)"], Path(directory), cancel
                )
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].poll(), "The owned converter was left running")

    def test_windows_taskkill_failure_still_kills_and_reaps_owned_process(self):
        for error in (OSError("taskkill unavailable"), subprocess.TimeoutExpired("taskkill", 10)):
            with self.subTest(error=type(error).__name__):
                process = SimpleNamespace(pid=12345, returncode=None)
                process.poll = lambda: process.returncode
                process.kill = lambda: setattr(process, "returncode", -9)
                process.wait = lambda **kwargs: process.returncode
                with (
                    patch("ytmp3.engine.os", SimpleNamespace(name="nt", environ=os.environ)),
                    patch("ytmp3.engine.subprocess.CREATE_NO_WINDOW", 0, create=True),
                    patch("ytmp3.engine.subprocess.run", side_effect=error),
                ):
                    _stop_process_tree(process)
                self.assertEqual(process.returncode, -9)

    def test_device_names_before_first_dot_are_safe_on_windows(self):
        for title in ("CON.txt", "nul.song", "AUX.", "LPT1.wav", "COM9.mp3", "CONIN$.txt"):
            with self.subTest(title=title):
                self.assertTrue(safe_stem(title, "abcdefghijk").startswith("_"))


if __name__ == "__main__":
    unittest.main()
