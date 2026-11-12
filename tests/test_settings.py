"""Persistence and failure behavior for the shared download-folder setting."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ytmp3 import APP_NAME
from ytmp3.settings import (
    SettingsError,
    SettingsStore,
    default_settings_path,
    prepare_download_directory,
)


class SettingsTests(unittest.TestCase):
    def test_default_read_does_not_create_settings_or_download_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            settings = home / "config" / "settings.json"
            with patch("ytmp3.settings.Path.home", return_value=home):
                self.assertEqual(
                    SettingsStore(settings).get_download_directory(), home / "Downloads"
                )
            self.assertFalse(settings.exists())
            self.assertFalse((home / "Downloads").exists())

    def test_folder_with_spaces_and_unicode_persists_across_store_instances(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "config" / "settings.json"
            folder = root / "Music downloads 音楽"
            self.assertEqual(
                SettingsStore(settings).set_download_directory(folder), folder.resolve()
            )
            self.assertTrue(folder.is_dir())
            self.assertEqual(SettingsStore(settings).get_download_directory(), folder.resolve())
            self.assertEqual(list(folder.iterdir()), [])

    def test_corrupt_or_unsupported_settings_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            values = (
                "not JSON",
                "[]",
                "{}",
                '{"version":2,"download_directory":"/tmp"}',
                '{"version":true,"download_directory":"/tmp"}',
                '{"version":1,"download_directory":42}',
                '{"version":1,"download_directory":"relative"}',
            )
            for value in values:
                with self.subTest(value=value):
                    path.write_text(value, encoding="utf-8")
                    with self.assertRaises(SettingsError):
                        SettingsStore(path).set_download_directory(Path(temporary) / "new")
                    self.assertEqual(path.read_text(encoding="utf-8"), value)

    def test_atomic_replace_failure_preserves_saved_settings_and_removes_temporary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "config" / "settings.json"
            store = SettingsStore(settings)
            original = store.set_download_directory(root / "original")
            with patch("ytmp3.settings.os.replace", side_effect=PermissionError("read-only")):
                with self.assertRaisesRegex(SettingsError, "Cannot save settings"):
                    store.set_download_directory(root / "new")
            self.assertEqual(store.get_download_directory(), original)
            self.assertEqual(list(settings.parent.iterdir()), [settings])

    def test_write_probe_failure_does_not_change_saved_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = SettingsStore(root / "settings.json")
            original = store.set_download_directory(root / "original")
            with patch(
                "ytmp3.settings.tempfile.TemporaryFile", side_effect=PermissionError("denied")
            ):
                with self.assertRaisesRegex(SettingsError, "Cannot use download folder"):
                    store.set_download_directory(root / "unwritable")
            self.assertEqual(store.get_download_directory(), original)

    def test_cleanup_failure_does_not_hide_readable_save_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = SettingsStore(root / "settings.json")
            original = store.set_download_directory(root / "original")
            with (
                patch("ytmp3.settings.os.replace", side_effect=PermissionError("save denied")),
                patch("ytmp3.settings.Path.unlink", side_effect=PermissionError("cleanup denied")),
            ):
                with self.assertRaisesRegex(SettingsError, "Cannot save settings.*save denied"):
                    store.set_download_directory(root / "new")
            self.assertEqual(store.get_download_directory(), original)

    def test_file_cannot_be_used_as_download_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "file"
            file.write_text("existing content")
            with self.assertRaises(SettingsError):
                prepare_download_directory(file)
            self.assertEqual(file.read_text(), "existing content")

    def test_platform_config_paths_and_windows_missing_appdata_fallback(self):
        home = Path.home()
        with patch("ytmp3.settings.platform.system", return_value="Darwin"):
            self.assertEqual(
                default_settings_path(),
                home / "Library" / "Application Support" / APP_NAME / "settings.json",
            )
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch("ytmp3.settings.platform.system", return_value="Windows"),
                patch.dict("os.environ", {"APPDATA": temporary}),
            ):
                self.assertEqual(
                    default_settings_path(), Path(temporary) / APP_NAME / "settings.json"
                )
            with (
                patch("ytmp3.settings.platform.system", return_value="Windows"),
                patch.dict("os.environ", {"APPDATA": ""}),
            ):
                self.assertEqual(
                    default_settings_path(),
                    home / "AppData" / "Roaming" / APP_NAME / "settings.json",
                )

    def test_saved_missing_directory_is_read_without_creating_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "missing"
            path = root / "settings.json"
            path.write_text(json.dumps({"version": 1, "download_directory": str(missing)}))
            self.assertEqual(SettingsStore(path).get_download_directory(), missing)
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
