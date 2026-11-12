"""Exercise OS signal handling in the real terminal entrypoint without a download."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ytmp3.runtime import tool_path


@unittest.skipUnless(os.name == "posix", "This test sends a POSIX SIGINT")
@unittest.skipUnless(
    all(tool_path(name).is_file() for name in ("ffmpeg", "ffprobe", "deno")),
    "Fetch runtime tools before running the CLI cancellation integration test",
)
class CliProcessTests(unittest.TestCase):
    def test_sigint_cancels_real_cli_without_traceback_or_partial_output(self):
        with tempfile.TemporaryDirectory(prefix="ytmp3-cli-signal-") as temporary:
            directory = Path(temporary) / "output"
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "ytmp3",
                    "download",
                    "https://youtu.be/jNQXAC9IVRw",
                    "--directory",
                    str(directory),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                # Resolving is emitted only after the cancellation handler is installed,
                # before retrieval starts. The signal stops this job before network work.
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stderr, selectors.EVENT_READ)
                    self.assertTrue(selector.select(timeout=10), "CLI startup timed out")
                    first_line = process.stderr.readline()
                self.assertIn("Resolving", first_line)
                process.send_signal(signal.SIGINT)
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 130, first_line + stderr)
                self.assertNotIn("Traceback", stderr)
                self.assertNotIn("Saved:", stdout)
                self.assertIn("cancel", stderr.lower())
                self.assertEqual(list(directory.iterdir()), [])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
