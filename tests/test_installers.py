"""Installation helpers must preserve unrelated commands and produce verifiable artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.build_installers import write_checksums
from scripts.fetch_tools import validate_asset

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "packaging/macos/Install terminal command.command"


class InstallerManifestTests(unittest.TestCase):
    def test_checksum_list_covers_exact_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "example.dmg"
            archive.write_bytes(b"installer bytes")
            checksum = root / "SHA256SUMS"
            write_checksums([archive], checksum)
            self.assertEqual(
                checksum.read_text(),
                hashlib.sha256(b"installer bytes").hexdigest() + "  example.dmg\n",
            )

    def test_prerequisite_manifest_has_verified_integrity_metadata(self):
        manifest = json.loads((ROOT / "packaging/prerequisites.json").read_text())
        asset = manifest["webview2"]
        validate_asset(asset)
        self.assertEqual(asset["sha256"], asset["output_sha256"])
        self.assertEqual(asset["output"], "MicrosoftEdgeWebview2Setup.exe")
        self.assertTrue(asset["url"].startswith("https://go.microsoft.com/"))


@unittest.skipUnless(os.name == "posix", "macOS helper requires a POSIX shell")
class TerminalInstallTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="ytmp3-helper-tests-")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name).resolve()
        self.app = self.root / "App 音楽 folder" / "YouTube Music Downloader.app"
        executable = self.app / "Contents/MacOS/ytmp3"
        executable.parent.mkdir(parents=True)
        executable.write_text("#!/bin/sh\nprintf 'fixture command\\n'\n", encoding="utf-8")
        executable.chmod(0o755)
        self.commands = self.root / "User commands"

    def invoke(self, operation):
        return subprocess.run(
            ["/bin/sh", str(HELPER), operation, str(self.app), str(self.commands)],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_install_is_repeatable_and_removal_only_deletes_owned_link(self):
        for _ in range(2):
            result = self.invoke("install")
            self.assertEqual(result.returncode, 0, result.stderr)
        command = self.commands / "ytmp3"
        self.assertTrue(command.is_symlink())
        self.assertEqual(
            subprocess.check_output([str(command)], text=True).strip(), "fixture command"
        )
        self.assertEqual(self.invoke("remove").returncode, 0)
        self.assertFalse(command.is_symlink())
        self.assertTrue(self.app.is_dir())
        self.assertEqual(self.invoke("remove").returncode, 0)

    def test_unrelated_file_and_symlink_are_never_replaced_or_removed(self):
        self.commands.mkdir()
        command = self.commands / "ytmp3"
        command.write_text("keep user command")
        for operation in ("install", "remove"):
            self.assertNotEqual(self.invoke(operation).returncode, 0)
            self.assertEqual(command.read_text(), "keep user command")
        command.unlink()
        unrelated = self.root / "other-command"
        unrelated.write_text("keep other command")
        command.symlink_to(unrelated)
        for operation in ("install", "remove"):
            self.assertNotEqual(self.invoke(operation).returncode, 0)
            self.assertEqual(command.resolve(), unrelated)

    def test_missing_app_does_not_create_a_dangling_command(self):
        (self.app / "Contents/MacOS/ytmp3").unlink()
        self.assertNotEqual(self.invoke("install").returncode, 0)
        self.assertFalse(self.commands.exists())

    def test_owned_link_can_be_removed_after_app_is_deleted(self):
        self.assertEqual(self.invoke("install").returncode, 0)
        (self.app / "Contents/MacOS/ytmp3").unlink()
        self.assertEqual(self.invoke("remove").returncode, 0)
        self.assertFalse((self.commands / "ytmp3").is_symlink())


if __name__ == "__main__":
    unittest.main()
