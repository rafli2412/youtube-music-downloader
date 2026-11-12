"""Keep native runtime deployment targets consistent with the advertised Mac minimum."""

from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.verify_macos_compatibility import audit_bundle, minimum_versions, version_tuple

MODERN = """
Load command 10
      cmd LC_BUILD_VERSION
 platform MACOS
    minos 11.0
      sdk 27.0
   ntools 1
     tool LD
  version 27037.1
"""
LEGACY = """
Load command 9
      cmd LC_VERSION_MIN_MACOSX
  version 10.13
      sdk 14.5
"""


class MacCompatibilityTests(unittest.TestCase):
    def test_reads_deployment_targets_without_confusing_sdk_or_linker_versions(self):
        self.assertEqual(minimum_versions(MODERN + LEGACY), ["11.0", "10.13"])
        self.assertEqual(version_tuple("13"), version_tuple("13.0.0"))
        self.assertEqual(minimum_versions(MODERN.replace("platform MACOS", "platform IOS")), [])

    def test_rejects_a_bundle_with_python_requiring_a_newer_os(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            contents = bundle / "Contents"
            contents.mkdir()
            with (contents / "Info.plist").open("wb") as target:
                plistlib.dump({"LSMinimumSystemVersion": "13.0"}, target)
            (contents / "Python").write_bytes(b"\xcf\xfa\xed\xfe")
            (contents / "launcher").write_bytes(b"\xcf\xfa\xed\xfe")
            (contents / "asset.txt").write_text("An ordinary data file")

            def inspect(command, **kwargs):
                version = "27.0" if Path(command[-1]).name == "Python" else "11.0"
                return SimpleNamespace(
                    returncode=0, stdout=MODERN.replace("minos 11.0", f"minos {version}")
                )

            with patch("scripts.verify_macos_compatibility.subprocess.run", side_effect=inspect):
                report = audit_bundle(bundle)
            self.assertFalse(report["ok"])
            self.assertEqual(report["binaries_checked"], 2)
            self.assertEqual(report["required_minimum_macos"], "27.0.0")
            self.assertEqual(
                report["violations"], [{"path": "Contents/Python", "minimum_macos": "27.0"}]
            )
            with patch(
                "scripts.verify_macos_compatibility.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=MODERN),
            ):
                self.assertTrue(audit_bundle(bundle)["ok"])

    def test_missing_arm64_load_commands_cannot_pass_the_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "Contents").mkdir()
            with (bundle / "Contents/Info.plist").open("wb") as target:
                plistlib.dump({"LSMinimumSystemVersion": "13.0"}, target)
            (bundle / "Contents/launcher").write_bytes(b"\xcf\xfa\xed\xfe")
            for process in (
                SimpleNamespace(returncode=1, stdout=""),
                SimpleNamespace(returncode=0, stdout=""),
            ):
                with self.subTest(process=process):
                    with patch(
                        "scripts.verify_macos_compatibility.subprocess.run", return_value=process
                    ):
                        report = audit_bundle(bundle)
                    self.assertFalse(report["ok"])
                    self.assertIn("No Apple Silicon", report["violations"][0]["error"])


if __name__ == "__main__":
    unittest.main()
