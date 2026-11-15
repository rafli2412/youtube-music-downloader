"""History persistence, pagination, safe deletion, and success-only integration."""

import hashlib
import io
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from test_engine import TOOLS_AVAILABLE, URL, _wave_worker

from ytmp3 import cli
from ytmp3.desktop import DesktopApi
from ytmp3.desktop_jobs import DesktopJobs
from ytmp3.engine import DownloadEngine, DownloadError
from ytmp3.history import HistoryStore, fallback_song_title
from ytmp3.settings import SettingsStore


class HistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.settings = SettingsStore(self.root / "settings.json")
        self.store = HistoryStore(self.settings.path)
        self.audio = self.root / "Edited filename.mp3"
        self.audio.write_bytes(b"keep this audio")

    def test_terminal_fallback_preserves_real_titles_and_versions(self):
        self.assertEqual(
            fallback_song_title(
                {"title": "Hindia - Song (Official Lyric Video)", "channel": "Hindia"}
            ),
            "Song",
        )
        self.assertEqual(
            fallback_song_title(
                {"title": "Artist - Song [Lirik Video]", "channel": "Artist - Topic"}
            ),
            "Song",
        )
        self.assertEqual(fallback_song_title({"title": "Video (Official Video)"}), "Video")
        self.assertEqual(
            fallback_song_title({"title": "Song (DJ Name Remix)"}), "Song (DJ Name Remix)"
        )
        self.assertEqual(fallback_song_title({"track": "Lyrics", "title": "Ignored"}), "Lyrics")

    def test_reopen_remove_and_clear_never_change_audio(self):
        first = self.store.add(self.audio, "Song title, not filename", URL)
        second = self.store.add(self.audio, "Another download", URL)
        reopened = HistoryStore(self.settings.path)
        page = reopened.page()
        self.assertEqual([item["id"] for item in page["entries"]], [second, first])
        self.assertEqual(page["entries"][1]["song_title"], "Song title, not filename")
        self.assertEqual(page["entries"][1]["filename"], self.audio.name)
        self.assertTrue(page["entries"][1]["downloaded_at"].endswith("+00:00"))
        reopened.remove(first)
        self.assertEqual(self.audio.read_bytes(), b"keep this audio")
        reopened.clear()
        self.assertEqual(reopened.page()["entries"], [])
        self.assertEqual(self.audio.read_bytes(), b"keep this audio")
        self.assertGreater(reopened.add(self.audio, "Next", URL), second)

    def test_pagination_and_concurrent_writers(self):
        def add(index):
            HistoryStore(self.settings.path).add(self.audio, f"Song {index}", URL)

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(add, range(105)))
        page = self.store.page()
        self.assertEqual(len(page["entries"]), 100)
        next_page = self.store.page(page["next_cursor"])
        self.assertEqual(len(next_page["entries"]), 5)
        self.assertIsNone(next_page["next_cursor"])
        ids = [item["id"] for item in page["entries"] + next_page["entries"]]
        self.assertEqual(len(set(ids)), 105)
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_missing_file_keeps_record_and_reveal_rechecks_disk(self):
        identity = self.store.add(self.audio, "Song", URL)
        jobs = DesktopJobs(self.settings)
        api = DesktopApi(jobs=jobs)
        self.audio.unlink()
        self.assertFalse(api.get_history()["entries"][0]["available"])
        with self.assertRaisesRegex(ValueError, "moved or deleted"):
            api.reveal_history_file(identity)
        self.assertEqual(len(api.get_history()["entries"]), 1)
        api.remove_history(identity)
        self.assertEqual(api.get_history()["entries"], [])

    def test_history_buttons_open_recorded_url_and_reveal_exact_file(self):
        identity = self.store.add(self.audio, "Song", URL)
        api = DesktopApi(jobs=DesktopJobs(self.settings))
        with patch("ytmp3.desktop.webbrowser.open") as browser:
            api.open_history_youtube(identity)
            browser.assert_called_once_with(self.store.get(identity)["url"])
        with (
            patch("ytmp3.desktop.platform.system", return_value="Darwin"),
            patch("ytmp3.desktop.subprocess.run") as run,
        ):
            api.reveal_history_file(identity)
            run.assert_called_once_with(
                ["/usr/bin/open", "-R", str(self.audio.resolve())], check=True, timeout=10
            )
        with (
            patch("ytmp3.desktop.platform.system", return_value="Windows"),
            patch("ytmp3.desktop.subprocess.Popen") as run,
        ):
            api.reveal_history_file(identity)
            run.assert_called_once_with(["explorer.exe", "/select,", str(self.audio.resolve())])

    def test_unknown_database_version_and_invalid_actions_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.page(-1)
        with self.assertRaises(ValueError):
            self.store.get("1 OR 1=1")
        self.store.page()
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaises(ValueError):
            self.store.clear()
        with closing(sqlite3.connect(self.store.path)) as db, db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 99)

    @unittest.skipUnless(TOOLS_AVAILABLE, "Native runtime tools required")
    def test_gui_and_terminal_history_survive_reopen_and_removal_keeps_real_mp3s(self):
        self.settings.set_download_directory(self.root / "audio")
        engine = DownloadEngine(self.settings, _worker_target=_wave_worker)
        engine.preview = Mock(return_value={"title": "Original video"})
        jobs = DesktopJobs(self.settings, engine)
        api = DesktopApi(jobs=jobs)
        api.preview_video(URL)
        jobs.wait(3)
        api.start_download(
            URL,
            api.get_job()["preview_id"],
            "GUI filename",
            {"title": "GUI edited title", "cover": "none"},
        )
        jobs.wait(10)
        self.assertEqual(api.get_job()["status"], "complete")
        jobs.shutdown()
        jobs.wait(3)
        with (
            patch.object(cli, "SettingsStore", return_value=self.settings),
            patch.object(
                cli,
                "DownloadEngine",
                side_effect=lambda store: DownloadEngine(store, _worker_target=_wave_worker),
            ),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(cli.main(["download", URL]), 0)
        reopened = DesktopApi(jobs=DesktopJobs(SettingsStore(self.settings.path)))
        records = reopened.get_history()["entries"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["song_title"], "GUI edited title")
        self.assertEqual(records[1]["filename"], "GUI filename.mp3")
        originals = {
            Path(row["path"]): hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest()
            for row in records
        }
        self.assertEqual(len(originals), 2)
        reopened.remove_history(records[0]["id"])
        self.assertEqual(len(reopened.get_history()["entries"]), 1)
        for path, fingerprint in originals.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), fingerprint)
        reopened.clear_history()
        self.assertEqual(
            DesktopApi(jobs=DesktopJobs(SettingsStore(self.settings.path))).get_history()[
                "entries"
            ],
            [],
        )
        for path, fingerprint in originals.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), fingerprint)

    @unittest.skipUnless(TOOLS_AVAILABLE, "Native runtime tools required")
    def test_completed_desktop_download_records_edited_tag_title_and_disabled_parsed_title(self):
        self.settings.set_download_directory(self.root / "audio")
        for enabled, title in ((True, "Edited song tag"), (False, "Parsed song title")):
            engine = DownloadEngine(self.settings, _worker_target=_wave_worker)
            engine.preview = Mock(return_value={"title": "Original video (Official Video)"})
            jobs = DesktopJobs(self.settings, engine)
            jobs.preview(URL)
            jobs.wait(3)
            jobs.confirm(
                URL,
                jobs.snapshot()["preview_id"],
                "Custom filename",
                {
                    "enabled": enabled,
                    "title": "Edited song tag",
                    "cover": "none",
                    "parsed_title": "Parsed song title",
                },
            )
            jobs.wait(10)
            self.assertEqual(jobs.snapshot()["status"], "complete", jobs.snapshot())
            entry = self.store.page()["entries"][0]
            self.assertEqual(entry["song_title"], title)
            self.assertTrue(Path(entry["path"]).is_file())
            self.assertTrue(entry["filename"].startswith("Custom filename"))
        jobs = DesktopJobs(self.settings, Mock())
        jobs._engine.preview.side_effect = DownloadError("Failed")
        jobs.preview(URL)
        jobs.wait(3)
        self.assertEqual(jobs.snapshot()["status"], "failed")
        self.assertEqual(len(self.store.page()["entries"]), 2)

    @unittest.skipUnless(TOOLS_AVAILABLE, "Native runtime tools required")
    def test_history_write_failure_does_not_turn_saved_mp3_into_failure(self):
        self.settings.set_download_directory(self.root / "audio")
        jobs = DesktopJobs(
            self.settings, DownloadEngine(self.settings, _worker_target=_wave_worker)
        )
        with patch.object(jobs.history, "add", side_effect=OSError("Disk full")):
            jobs._start(URL, preview=False, tags={"cover": "none"})
            jobs.wait(10)
        state = jobs.snapshot()
        self.assertEqual(state["status"], "complete", state)
        self.assertTrue(Path(state["result"]["path"]).is_file())
        self.assertIn("could not be recorded", state["history_warning"])
