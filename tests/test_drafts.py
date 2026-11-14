"""Persistent draft restore, cover snapshots, rollback, and successful cleanup."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mutagen.id3 import ID3
from test_engine import TOOLS_AVAILABLE, URL, _wave_worker
from test_tags import cover_png

from ytmp3.desktop import DesktopApi
from ytmp3.desktop_jobs import DesktopJobs
from ytmp3.drafts import DraftError, DraftStore
from ytmp3.engine import DownloadEngine, video_metadata
from ytmp3.settings import SettingsStore


def options():
    return {
        "enabled": True,
        "title": "Edited title",
        "artist": "Edited artist",
        "album": "Edited album",
        "year": "2004",
        "cover": "local",
    }


def record():
    return {
        "url": URL,
        "filename": "Edited filename",
        "tags": options(),
        "metadata": {"title": "Original title"},
        "previewed_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    }


class DraftStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.store = DraftStore(self.root / "settings.json")

    def test_roundtrip_keeps_partial_edits_and_cover_in_a_new_store_instance(self):
        data = record()
        data["tags"]["year"] = "20"
        data["tags"]["track_number"] = "12"
        self.store.save(data, cover_png(), "selected.png")
        saved, cover = DraftStore(self.root / "settings.json").load()
        self.assertEqual(saved["filename"], data["filename"])
        self.assertEqual(saved["tags"]["year"], "20")
        self.assertEqual(saved["tags"]["track_number"], "12")
        self.assertEqual(cover, cover_png())
        self.assertEqual(saved["cover_name"], "selected.png")
        if __import__("os").name != "nt":
            self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)

    def test_atomic_failure_keeps_the_previous_draft_and_cover(self):
        self.store.save(record(), cover_png(), "first.png")
        original = self.store.path.read_bytes()
        replace = __import__("os").replace

        def fail_metadata(source, destination):
            if destination == self.store.path:
                raise OSError("Disk full")
            return replace(source, destination)

        changed = record()
        changed["filename"] = "New edit"
        with (
            patch("ytmp3.drafts.os.replace", side_effect=fail_metadata),
            self.assertRaises(DraftError),
        ):
            self.store.save(changed, cover_png() + b"new", "new.png")
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(self.store.load()[1], cover_png())

    def test_unknown_version_and_unsafe_cover_references_are_not_overwritten(self):
        self.root.mkdir(exist_ok=True)
        for data in ({"version": 99}, {**record(), "version": 1, "cover_ref": "../settings"}):
            self.store.path.write_text(json.dumps(data))
            original = self.store.path.read_bytes()
            with self.assertRaises(DraftError):
                self.store.load()
            with self.assertRaises(DraftError):
                self.store.save(record(), None, None)
            self.assertEqual(self.store.path.read_bytes(), original)

    def test_missing_cover_keeps_other_edits_and_requires_reselection(self):
        self.store.save(record(), cover_png(), "selected.png")
        for image in self.store.covers.iterdir():
            image.unlink()
        saved, cover = self.store.load()
        self.assertIsNone(cover)
        self.assertEqual(saved["filename"], "Edited filename")
        self.assertEqual(saved["tags"]["cover"], "local")
        self.assertIn("unavailable", saved["warning"])

    def test_clear_only_removes_managed_draft_data(self):
        self.store.save(record(), cover_png(), "selected.png")
        unrelated = self.store.covers / "keep.txt"
        unrelated.write_text("keep")
        settings = self.root / "settings.json"
        settings.write_text("existing settings")
        self.store.clear()
        self.assertIsNone(self.store.load())
        self.assertEqual(unrelated.read_text(), "keep")
        self.assertEqual(settings.read_text(), "existing settings")


@unittest.skipUnless(TOOLS_AVAILABLE, "Fetch native runtime tools first")
class DraftRestartTests(unittest.TestCase):
    def test_reopen_restores_edits_and_cover_then_saves_them_without_another_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            settings = SettingsStore(root / "settings.json")
            settings.set_download_directory(root / "audio")
            engine = DownloadEngine(_worker_target=_wave_worker)
            engine.preview = Mock(
                return_value=video_metadata(
                    {
                        "title": "Original video",
                        "track": "Original track",
                        "description": "▶️ ‘LAGIPULA HIDUP AKAN BERAKHIR’ Album",
                    }
                )
            )
            jobs = DesktopJobs(settings, engine)
            api = DesktopApi(jobs=jobs)
            api._window = Mock()
            api.preview_video(URL)
            jobs.wait(3)
            identity = jobs.snapshot()["preview_id"]
            local = root / "original.png"
            local.write_bytes(cover_png())
            api._window.create_file_dialog.return_value = [str(local)]
            with patch.dict(
                "sys.modules", {"webview": SimpleNamespace(FileDialog=SimpleNamespace(OPEN=1))}
            ):
                selected = api.choose_cover()
            api.save_draft(URL, "Edited filename", options(), identity)
            local.unlink()
            jobs.shutdown()
            jobs.wait(3)
            # Entirely new API/controller/engine simulates a new app process.
            resumed_engine = DownloadEngine(_worker_target=_wave_worker)
            resumed_engine.preview = Mock(
                side_effect=AssertionError("Must not preview or download automatically")
            )
            resumed_jobs = DesktopJobs(SettingsStore(settings.path), resumed_engine)
            resumed_api = DesktopApi(jobs=resumed_jobs)
            saved = resumed_api.get_draft()
            state = resumed_api.get_job()
            self.assertEqual(saved["url"], URL)
            self.assertEqual(saved["filename"], "Edited filename")
            self.assertEqual(saved["tags"], options())
            self.assertEqual(saved["cover"], selected)
            self.assertEqual(state["status"], "ready")
            self.assertTrue(state["restored"])
            self.assertEqual(state["metadata"]["album"], "LAGIPULA HIDUP AKAN BERAKHIR")
            self.assertEqual(state["metadata"]["album_source"], "description")
            self.assertEqual(saved["tags"]["album"], "Edited album")
            self.assertEqual(list((root / "audio").iterdir()), [])
            resumed_engine.preview.assert_not_called()
            resumed_api.start_download(
                saved["url"], state["preview_id"], saved["filename"], saved["tags"]
            )
            resumed_jobs.wait(10)
            completed = resumed_jobs.snapshot()
            try:
                self.assertEqual(completed["status"], "complete", completed)
                path = Path(completed["result"]["path"])
                self.assertEqual(path.name, "Edited filename.mp3")
                tags = ID3(path, translate=False)
                self.assertEqual(str(tags["TIT2"]), "Edited title")
                self.assertEqual(str(tags["TALB"]), "Edited album")
                self.assertTrue(tags.getall("APIC"))
                self.assertIsNone(resumed_jobs.drafts.load())
                # A delayed autosave for the completed preview cannot resurrect it.
                resumed_api.save_draft(URL, saved["filename"], saved["tags"], state["preview_id"])
                self.assertIsNone(resumed_jobs.drafts.load())
            finally:
                resumed_jobs.shutdown()
                resumed_jobs.wait(3)
