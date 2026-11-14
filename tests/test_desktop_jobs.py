"""Desktop concurrency, results, settings, and cancellation without opening a window."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ytmp3.desktop import DesktopApi
from ytmp3.desktop_jobs import DesktopJobs, download_error_message
from ytmp3.engine import DownloadCancelled, DownloadProgress, DownloadResult
from ytmp3.settings import SettingsStore
from ytmp3.urls import InvalidYouTubeURL

URL = "https://youtu.be/jNQXAC9IVRw"


class ControlledEngine:
    def __init__(self):
        self.running = threading.Event()
        self.finish = threading.Event()
        self.failure = None
        self.complete_on_cancel = False

    def download(self, url, directory, on_progress, cancel, tags=None, cover_data=None):
        on_progress(DownloadProgress("downloading", 25, 100))
        self.running.set()
        while not self.finish.wait(0.01):
            if cancel.is_set():
                if self.complete_on_cancel:
                    break
                raise DownloadCancelled("Cancelled")
        if self.failure:
            raise self.failure
        return DownloadResult(Path(directory) / "Example.mp3", "Example", "jNQXAC9IVRw")


class DesktopJobsTests(unittest.TestCase):
    def test_provider_verification_error_does_not_suggest_unsupported_login_workarounds(self):
        message = download_error_message(
            RuntimeError("ERROR: Sign in to confirm you're not a bot. Use --cookies-from-browser.")
        )
        self.assertIn("verification", message)
        self.assertIn("public link", message)
        self.assertIn("No new MP3 was saved", message)
        self.assertIn("different network", message)
        self.assertNotIn("cookies", message)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.settings = SettingsStore(self.root / "settings.json")
        self.settings.set_download_directory(self.root / "audio")
        self.engine = ControlledEngine()
        self.jobs = DesktopJobs(self.settings, self.engine)
        self.addCleanup(self.cleanup_job)

    def cleanup_job(self):
        self.jobs.shutdown()
        self.engine.finish.set()
        self.jobs.wait(3)

    def start(self):
        self.jobs.start(URL)
        self.assertTrue(self.engine.running.wait(3))

    def test_preview_requires_confirmation_and_matching_video_before_downloading(self):
        self.engine.preview = Mock(return_value={"title": "Example", "channel": "Test"})
        api = DesktopApi(jobs=self.jobs)
        api.preview_video(URL)
        self.jobs.wait(3)
        preview = self.jobs.snapshot()
        self.assertEqual(preview["status"], "ready")
        self.assertFalse(preview["busy"])
        self.assertIsNone(preview["result"])
        self.assertFalse(self.engine.running.is_set(), "Preview started downloading audio")
        with self.assertRaisesRegex(RuntimeError, "Preview"):
            api.start_download("https://youtu.be/abcdefghijk", preview["job_id"])
        with self.assertRaisesRegex(RuntimeError, "Preview"):
            api.start_download(URL, "stale-preview")
        self.assertFalse(self.engine.running.is_set())
        api.start_download(URL, preview["job_id"])
        self.assertTrue(self.engine.running.wait(3))
        self.engine.finish.set()
        self.jobs.wait(3)
        self.assertEqual(self.jobs.snapshot()["status"], "complete")
        with self.assertRaisesRegex(RuntimeError, "Preview"):
            api.start_download(URL, preview["job_id"])

    def test_confirm_passes_optional_filename_to_the_engine(self):
        self.engine.preview = Mock(return_value={"title": "Example"})
        self.engine.download = Mock(
            return_value=DownloadResult(self.root / "Custom.mp3", "Example", "jNQXAC9IVRw")
        )
        api = DesktopApi(jobs=self.jobs)
        api.preview_video(URL)
        self.jobs.wait(3)
        api.start_download(URL, self.jobs.snapshot()["job_id"], "Custom")
        self.jobs.wait(3)
        self.assertEqual(self.engine.download.call_args.kwargs["filename"], "Custom")
        self.assertEqual(self.jobs.snapshot()["status"], "complete")

    def test_tag_validation_keeps_preview_available_without_starting_audio(self):
        self.engine.preview = Mock(return_value={"title": "Example"})
        api = DesktopApi(jobs=self.jobs)
        api.preview_video(URL)
        self.jobs.wait(3)
        preview_id = self.jobs.snapshot()["job_id"]
        for tags in ({"year": "invalid"}, {"cover": "local"}):
            with self.subTest(tags=tags), self.assertRaises(ValueError):
                api.start_download(URL, preview_id, tags=tags)
            self.assertEqual(self.jobs.snapshot()["status"], "ready")
            self.assertFalse(self.engine.running.is_set())

    def test_local_cover_is_selected_by_picker_and_bound_to_its_preview(self):
        from test_tags import cover_png

        self.engine.preview = Mock(return_value={"title": "Example", "track": "Song"})
        self.engine.download = Mock(
            return_value=DownloadResult(self.root / "Custom.mp3", "Example", "jNQXAC9IVRw")
        )
        api = DesktopApi(jobs=self.jobs)
        api._window = Mock()
        api.preview_video(URL)
        self.jobs.wait(3)
        path = self.root / "cover.png"
        data = cover_png()
        path.write_bytes(data)
        api._window.create_file_dialog.return_value = [str(path)]
        with patch.dict(
            "sys.modules", {"webview": SimpleNamespace(FileDialog=SimpleNamespace(OPEN=1))}
        ):
            selected = api.choose_cover()
        self.assertEqual(selected["name"], "cover.png")
        self.assertTrue(selected["preview"].startswith("data:image/png;base64,"))
        path.unlink()  # The selected image is snapshotted rather than reopened later.
        api.start_download(
            URL, self.jobs.snapshot()["job_id"], tags={"title": "Edited song", "cover": "local"}
        )
        self.jobs.wait(3)
        self.assertEqual(self.engine.download.call_args.kwargs["cover_data"], data)
        self.assertEqual(self.engine.download.call_args.kwargs["tags"]["title"], "Edited song")
        api.preview_video(URL)
        self.jobs.wait(3)
        with self.assertRaises(ValueError):
            api.start_download(URL, self.jobs.snapshot()["job_id"], tags={"cover": "local"})
        self.assertEqual(self.engine.download.call_count, 1)

    def test_failed_preview_cannot_be_retried_as_an_approved_download(self):
        self.engine.preview = Mock(side_effect=RuntimeError("Verification required"))
        api = DesktopApi(jobs=self.jobs)
        api.preview_video(URL)
        self.jobs.wait(3)
        failed = self.jobs.snapshot()
        self.assertEqual(failed["status"], "failed")
        self.assertIsNone(failed["preview_id"])
        with self.assertRaises(RuntimeError):
            api.start_download(URL, failed["job_id"], "Draft")
        self.assertFalse(self.engine.running.is_set())

    def test_metadata_is_retained_during_conversion_and_snapshots_are_isolated(self):
        metadata = {"title": "A song", "channel": "A channel", "duration": 187}
        self.jobs._progress(DownloadProgress("resolving", metadata=metadata))
        metadata["title"] = "Changed outside the controller"
        self.jobs._progress(DownloadProgress("converting"))
        snapshot = self.jobs.snapshot()
        self.assertEqual(snapshot["metadata"]["title"], "A song")
        snapshot["metadata"]["title"] = "Changed snapshot"
        self.assertEqual(self.jobs.snapshot()["metadata"]["title"], "A song")

    def test_progress_snapshot_is_isolated_and_result_is_published_after_completion(self):
        self.start()
        state = self.jobs.snapshot()
        self.assertTrue(state["busy"])
        self.assertEqual(state["fraction"], 0.25)
        state["status"] = "corrupted"
        self.assertEqual(self.jobs.snapshot()["status"], "downloading")
        self.engine.finish.set()
        self.jobs.wait(3)
        result = self.jobs.snapshot()
        self.assertFalse(result["busy"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["result"]["title"], "Example")
        self.assertEqual(self.jobs.result_directory(), str(self.root / "audio"))

    def test_duplicate_jobs_and_folder_changes_are_rejected_while_busy(self):
        self.start()
        with self.assertRaisesRegex(RuntimeError, "already running"):
            self.jobs.start(URL)
        with self.assertRaises(RuntimeError):
            self.jobs.save_directory(str(self.root / "other"))
        self.assertEqual(self.settings.get_download_directory(), self.root / "audio")

    def test_cancel_stays_busy_until_worker_cleanup_then_allows_another_job(self):
        self.start()
        self.assertEqual(self.jobs.cancel()["status"], "cancelling")
        self.jobs.wait(3)
        self.assertEqual(self.jobs.snapshot()["status"], "cancelled")
        self.assertFalse(self.jobs.snapshot()["busy"])
        self.engine.finish.set()
        self.jobs.start(URL)
        self.jobs.wait(3)
        self.assertEqual(self.jobs.snapshot()["status"], "complete")

    def test_shutdown_cancels_work_and_prevents_new_jobs(self):
        self.start()
        self.jobs.shutdown()
        self.jobs.wait(3)
        self.assertFalse(self.jobs.snapshot()["busy"])
        with self.assertRaisesRegex(RuntimeError, "closing"):
            self.jobs.start(URL)

    def test_late_cancel_preserves_successful_publication(self):
        self.engine.complete_on_cancel = True
        self.start()
        self.jobs.cancel()
        self.jobs.wait(3)
        self.assertEqual(self.jobs.snapshot()["status"], "complete")
        self.assertIsNotNone(self.jobs.snapshot()["result"])

    def test_failed_job_can_be_retried_and_does_not_reuse_a_success_result(self):
        self.engine.failure = RuntimeError("Video unavailable")
        self.engine.finish.set()
        self.jobs.start(URL)
        self.jobs.wait(3)
        state = self.jobs.snapshot()
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["error"], "Video unavailable")
        self.assertIsNone(state["result"])
        self.engine.failure = None
        self.jobs.start(URL)
        self.jobs.wait(3)
        self.assertEqual(self.jobs.snapshot()["status"], "complete")

    def test_invalid_url_starts_no_work_and_settings_are_shared_with_cli(self):
        with self.assertRaises(InvalidYouTubeURL):
            self.jobs.start("https://example.com")
        self.assertIsNone(self.jobs.snapshot()["job_id"])
        self.jobs.save_directory(str(self.root / "new 音楽 folder"))
        self.assertEqual(
            SettingsStore(self.settings.path).get_download_directory(),
            self.root / "new 音楽 folder",
        )

    def test_native_picker_cancel_and_selection_save_only_chosen_directory(self):
        api = DesktopApi(jobs=self.jobs)
        api._window = Mock()
        api._window.create_file_dialog.return_value = None
        webview = SimpleNamespace(FileDialog=SimpleNamespace(FOLDER=1))
        with patch.dict("sys.modules", {"webview": webview}):
            self.assertEqual(
                api.choose_download_directory()["download_directory"], str(self.root / "audio")
            )
            api._window.create_file_dialog.return_value = [str(self.root / "picked")]
            self.assertEqual(
                api.choose_download_directory()["download_directory"], str(self.root / "picked")
            )
        self.assertEqual(self.settings.get_download_directory(), self.root / "picked")

    def test_open_folder_restricts_target_to_completed_result(self):
        api = DesktopApi(jobs=self.jobs)
        with self.assertRaises(RuntimeError):
            api.open_download_folder()
        self.engine.finish.set()
        self.jobs.start(URL)
        self.jobs.wait(3)
        with (
            patch("ytmp3.desktop.platform.system", return_value="Darwin"),
            patch("ytmp3.desktop.subprocess.run") as run,
        ):
            api.open_download_folder()
            self.assertEqual(run.call_args.args[0], ["/usr/bin/open", str(self.root / "audio")])


if __name__ == "__main__":
    unittest.main()
