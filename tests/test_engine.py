"""Exercise process isolation and actual MP3 conversion without external services."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ytmp3.engine import (
    DownloadBusy,
    DownloadCancelled,
    DownloadEngine,
    DownloadError,
    UnsupportedContent,
    validate_content,
)
from ytmp3.runtime import tool_path
from ytmp3.settings import SettingsStore

URL = "https://youtu.be/dQw4w9WgXcQ"
TITLE = "An example song"


def _start_session() -> None:
    if os.name != "nt":
        os.setsid()


def _wave_worker(connection, url, directory, deno) -> None:
    """Mimic retrieval using an actual small uncompressed audio fixture."""
    _start_session()
    try:
        source = Path(directory) / "source.wav"
        with wave.open(str(source), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b"\x00\x00" * 1600)
        connection.send({"kind": "progress", "downloaded": 3200, "total": 3200})
        video_id = url.rsplit("=", 1)[-1]
        title = TITLE if video_id == "dQw4w9WgXcQ" else 'CON: 音楽/<>:*?\\| "' + "🎵" * 100
        connection.send({"kind": "result", "source": str(source), "id": video_id, "title": title})
    finally:
        connection.close()


def _metadata_worker(connection, url, directory, deno) -> None:
    connection.send(
        {
            "kind": "metadata",
            "metadata": {
                "title": TITLE,
                "channel": "Example channel",
                "duration": 187,
                "published_date": "20260102",
                "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            },
        }
    )
    _wave_worker(connection, url, directory, deno)


def _error_worker(connection, url, directory, deno) -> None:
    _start_session()
    connection.send({"kind": "error", "message": "Content unavailable", "unsupported": False})
    connection.close()


def _crash_worker(connection, url, directory, deno) -> None:
    _start_session()
    os._exit(7)


def _hanging_worker(connection, url, directory, deno) -> None:
    _start_session()
    connection.send({"kind": "progress", "downloaded": 1, "total": 10})
    time.sleep(60)


TOOLS_AVAILABLE = all(tool_path(name).is_file() for name in ("ffmpeg", "ffprobe", "deno"))


@unittest.skipUnless(TOOLS_AVAILABLE, "Fetch the native runtime tools for engine integration tests")
class EngineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="ytmp3-engine-tests-")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name).resolve()
        self.destination = self.root / "My 音楽 Downloads"
        self.settings = SettingsStore(self.root / "config" / "settings.json")
        self.settings.set_download_directory(self.destination)
        self.engine = DownloadEngine(self.settings, _worker_target=_wave_worker)

    def assert_destination_has_only(self, *paths):
        self.assertEqual(set(self.destination.iterdir()), set(paths))

    def test_real_spawn_conversion_and_saved_destination_produce_playable_mp3(self):
        events = []
        result = self.engine.download(URL, on_progress=events.append)
        self.assertEqual(result.path.parent, self.destination)
        self.assertEqual(result.title, TITLE)
        self.assertEqual(result.video_id, "dQw4w9WgXcQ")
        self.assertEqual(result.path.name, f"{TITLE}.mp3")
        self.assert_destination_has_only(result.path)
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        probe = subprocess.run(
            [
                str(tool_path("ffprobe")),
                "-v",
                "error",
                "-show_streams",
                "-of",
                "json",
                str(result.path),
            ],
            capture_output=True,
            text=True,
            check=True,
            **options,
        )
        stream = json.loads(probe.stdout)["streams"][0]
        self.assertEqual(stream["codec_name"], "mp3")
        self.assertGreater(float(stream["duration"]), 0)
        self.assertEqual(
            [event.stage for event in events],
            ["resolving", "downloading", "converting", "complete"],
        )
        self.assertEqual(events[1].fraction, 1)

    def test_metadata_arrives_before_download_and_conversion(self):
        events = []
        engine = DownloadEngine(self.settings, _worker_target=_metadata_worker)
        engine.download(URL, on_progress=events.append)
        metadata_events = [event for event in events if event.metadata]
        self.assertEqual(len(metadata_events), 1)
        self.assertEqual(metadata_events[0].metadata["channel"], "Example channel")
        self.assertEqual(metadata_events[0].metadata["published_date"], "20260102")
        self.assertLess(
            events.index(metadata_events[0]),
            next(i for i, event in enumerate(events) if event.stage == "downloading"),
        )

    def test_custom_filename_is_safe_preserves_title_and_numbers_duplicates(self):
        first = self.engine.download(URL, filename="My / Song.mp3")
        second = self.engine.download(URL, filename="My / Song.mp3")
        self.assertEqual(first.path.name, "My _ Song.mp3")
        self.assertEqual(second.path.name, "My _ Song (2).mp3")
        self.assertEqual(first.title, TITLE)
        self.assertEqual(first.path.parent, self.destination)
        self.assert_destination_has_only(first.path, second.path)

    def test_blank_custom_filename_uses_video_title(self):
        result = self.engine.download(URL, filename="   ")
        self.assertEqual(result.path.name, f"{TITLE}.mp3")

    def test_repeated_download_keeps_existing_bytes_and_uses_new_filename(self):
        existing = self.destination / f"{TITLE}.mp3"
        existing.write_bytes(b"existing user content")
        result = self.engine.download(URL)
        self.assertEqual(existing.read_bytes(), b"existing user content")
        self.assertEqual(result.path.name, f"{TITLE} (2).mp3")
        self.assert_destination_has_only(existing, result.path)
        third = self.engine.download(URL)
        self.assertEqual(third.path.name, f"{TITLE} (3).mp3")
        self.assertEqual(existing.read_bytes(), b"existing user content")
        self.assert_destination_has_only(existing, result.path, third.path)

    def test_unicode_and_long_titles_are_saved_as_portable_bounded_names(self):
        result = self.engine.download("https://music.youtube.com/watch?v=abcdefghijk")
        self.assertIn("音楽", result.path.name)
        self.assertTrue(result.path.name.endswith(".mp3"))
        self.assertNotIn("abcdefghijk", result.path.name)
        self.assertLess(len(result.path.name.encode("utf-8")), 200)
        self.assertFalse(any(character in result.path.name for character in '<>:"/\\|?*'))
        self.assert_destination_has_only(result.path)

    def test_worker_errors_and_crashes_leave_no_partial_files(self):
        for target, message in (
            (_error_worker, "Content unavailable"),
            (_crash_worker, "unexpectedly"),
        ):
            with self.subTest(target=target.__name__):
                engine = DownloadEngine(self.settings, _worker_target=target)
                with self.assertRaisesRegex(DownloadError, message):
                    engine.download(URL)
                self.assert_destination_has_only()

    def test_cancelling_retrieval_stops_worker_and_removes_temporary_files(self):
        engine = DownloadEngine(self.settings, _worker_target=_hanging_worker)
        existing = self.destination / "keep.mp3"
        existing.write_bytes(b"existing audio")
        cancel = threading.Event()
        stages = []

        def progress(event):
            stages.append(event.stage)
            if event.stage == "downloading":
                cancel.set()

        started = time.monotonic()
        with self.assertRaises(DownloadCancelled):
            engine.download(URL, on_progress=progress, cancel=cancel)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(stages[-1], "cancelled")
        self.assert_destination_has_only(existing)
        self.assertEqual(existing.read_bytes(), b"existing audio")

    def test_cancelling_when_conversion_starts_does_not_publish_output(self):
        cancel = threading.Event()

        def progress(event):
            if event.stage == "converting":
                cancel.set()

        with self.assertRaises(DownloadCancelled):
            self.engine.download(URL, on_progress=progress, cancel=cancel)
        self.assert_destination_has_only()

    def test_concurrent_job_is_rejected_and_first_job_can_be_cancelled(self):
        engine = DownloadEngine(self.settings, _worker_target=_hanging_worker)
        cancel = threading.Event()
        downloading = threading.Event()
        errors = []

        def run():
            try:
                engine.download(
                    URL,
                    cancel=cancel,
                    on_progress=lambda event: downloading.set()
                    if event.stage == "downloading"
                    else None,
                )
            except Exception as error:
                errors.append(error)

        first = threading.Thread(target=run, daemon=True)
        first.start()
        try:
            self.assertTrue(downloading.wait(10), "The first job did not start")
            with self.assertRaises(DownloadBusy):
                engine.download(URL)
        finally:
            cancel.set()
            first.join(timeout=10)
        self.assertFalse(first.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], DownloadCancelled)
        self.assert_destination_has_only()

    def test_callback_error_cleans_up_and_engine_can_start_another_job(self):
        def broken_callback(event):
            if event.stage == "downloading":
                raise RuntimeError("Display callback failed")

        with self.assertRaisesRegex(RuntimeError, "Display callback failed"):
            self.engine.download(URL, on_progress=broken_callback)
        self.assert_destination_has_only()
        result = self.engine.download(URL)
        self.assert_destination_has_only(result.path)


class ContentValidationTests(unittest.TestCase):
    def test_finished_public_unlisted_or_unknown_availability_can_proceed(self):
        for availability in ("public", "unlisted", None):
            with self.subTest(availability=availability):
                validate_content({"availability": availability, "live_status": "was_live"})

    def test_live_upcoming_restricted_and_multiitem_content_are_rejected(self):
        for info in (
            {"is_live": True},
            {"live_status": "is_live"},
            {"live_status": "is_upcoming"},
            {"availability": "private"},
            {"availability": "needs_auth"},
            {"availability": "premium_only"},
            {"_type": "playlist"},
            {"_type": "multi_video"},
        ):
            with self.subTest(info=info), self.assertRaises(UnsupportedContent):
                validate_content(info)


if __name__ == "__main__":
    unittest.main()
