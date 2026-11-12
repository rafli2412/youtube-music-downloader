"""Checks around resource isolation, bridge boundaries and terminal independence."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ytmp3 import __version__
from ytmp3.desktop import DesktopApi, validate_dev_url
from ytmp3.diagnostics import write_report
from ytmp3.runtime import frontend_directory, tool_path


class FoundationTests(unittest.TestCase):
    def test_terminal_does_not_import_webview(self):
        process = subprocess.run(
            [sys.executable, "-c", "from ytmp3.cli import main; main(['--help'])"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        check = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import ytmp3.cli; assert 'webview' not in sys.modules",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_frozen_assets_use_bundle_instead_of_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", directory, create=True),
            ):
                self.assertEqual(frontend_directory(), Path(directory) / "frontend")
                self.assertEqual(tool_path("ffmpeg").parent, Path(directory) / "runtime-tools")

    def test_tools_cannot_escape_bundle_directory(self):
        with self.assertRaises(ValueError):
            tool_path("../untrusted")

    def test_remote_pages_cannot_be_attached_to_privileged_bridge(self):
        for url in (
            "https://example.com",
            "http://localhost.evil.test",
            "file:///tmp/page.html",
            "http://user:secret@localhost:5173",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_dev_url(url)
        self.assertEqual(validate_dev_url("http://127.0.0.1:5173"), "http://127.0.0.1:5173")
        with patch.object(sys, "frozen", True, create=True), self.assertRaises(ValueError):
            validate_dev_url("http://localhost:5173")

    def test_bridge_rejects_mismatched_frontend_version(self):
        ready = []
        bridge = DesktopApi(lambda: ready.append(True))
        with self.assertRaises(ValueError):
            bridge.frontend_ready({"version": "different"})
        self.assertEqual(ready, [])
        self.assertEqual(bridge.frontend_ready({"version": __version__}), {"ok": True})
        self.assertEqual(ready, [True])

    def test_report_replaces_old_result_without_leaving_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "results" / "check.json"
            write_report(report, {"ok": False})
            write_report(report, {"ok": True})
            self.assertEqual(json.loads(report.read_text()), {"ok": True})
            self.assertEqual(list(report.parent.iterdir()), [report])


if __name__ == "__main__":
    unittest.main()
