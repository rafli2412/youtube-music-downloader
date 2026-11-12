"""Integrity and archive tests for build-time runtime acquisition (no network)."""

import hashlib
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "fetch_tools", Path(__file__).resolve().parents[1] / "scripts" / "fetch_tools.py"
)
fetch_tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_tools)


class FetchToolsTests(unittest.TestCase):
    def asset(self, content=b"executable", **overrides):
        digest = hashlib.sha256(content).hexdigest()
        return {
            "output": "deno",
            "url": "https://example.com/pinned.zip",
            "format": "raw",
            "sha256": digest,
            "output_sha256": digest,
            "executable": True,
            **overrides,
        }

    def test_rejects_traversal_and_insecure_url(self):
        for name in ("../outside", "..\\outside", "/outside", ".."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                fetch_tools.validate_asset(self.asset(output=name))
        with self.assertRaises(ValueError):
            fetch_tools.validate_asset(self.asset(url="http://example.com/tool"))

    def test_checksum_failure_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive"
            archive.write_bytes(b"corrupted")
            destination = root / "tools"
            destination.mkdir()
            (destination / "deno").write_bytes(b"existing")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                fetch_tools.install_asset(self.asset(), archive, destination)
            self.assertEqual((destination / "deno").read_bytes(), b"existing")
            self.assertEqual([p.name for p in destination.iterdir()], ["deno"])

    def test_zip_extracts_only_exact_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../outside", b"untrusted extra entry")
                bundle.writestr("deno", b"executable")
            output = fetch_tools.install_asset(
                self.asset(format="zip", member="deno"), archive, root / "tools"
            )
            self.assertEqual(output.read_bytes(), b"executable")
            self.assertFalse((root / "outside").exists())

    def test_zip_rejects_duplicate_executable_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("deno", b"executable")
                # Zip files can legally contain duplicate names; accepting one is ambiguous.
                import warnings

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    bundle.writestr("deno", b"other")
            with self.assertRaisesRegex(ValueError, "exactly one"):
                fetch_tools.install_asset(
                    self.asset(format="zip", member="deno"), archive, root / "tools"
                )

    def test_verify_detects_missing_and_modified_file(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            self.assertEqual(
                fetch_tools.verify_target([self.asset()], destination), ["Missing deno"]
            )
            (destination / "deno").write_bytes(b"modified")
            self.assertEqual(
                fetch_tools.verify_target([self.asset()], destination), ["Checksum mismatch: deno"]
            )


if __name__ == "__main__":
    unittest.main()
