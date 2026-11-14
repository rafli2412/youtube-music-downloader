"""Verify real ID3v2.3 output, artwork, disabled tags, and atomic failure cleanup."""

import struct
import subprocess
import tempfile
import threading
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3
from test_engine import TOOLS_AVAILABLE, URL, _wave_worker

from ytmp3.desktop import DesktopApi
from ytmp3.desktop_jobs import DesktopJobs
from ytmp3.engine import DownloadCancelled, DownloadEngine, DownloadError, video_metadata
from ytmp3.runtime import tool_path
from ytmp3.settings import SettingsStore
from ytmp3.tags import image_mime, normalize_tags, validate_thumbnail_url


def cover_png():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    pixels = (b"\x00" + b"\xff\x00\x00" * 2) * 2
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


class TagOptionsTests(unittest.TestCase):
    def test_defaults_use_release_metadata_and_not_upload_year(self):
        metadata = video_metadata(
            {
                "title": "Video",
                "track": "Song",
                "artist": "Artist",
                "album": "Album",
                "upload_date": "20250101",
            }
        )
        defaults = normalize_tags(None, metadata)
        self.assertEqual(defaults["title"], "Song")
        self.assertEqual(defaults["album"], "Album")
        self.assertEqual(defaults["year"], "")
        self.assertEqual(
            video_metadata({"release_date": "19980102", "upload_date": "20250101"})["release_year"],
            "",
        )
        self.assertEqual(
            video_metadata({"release_year": 2001, "release_date": "19980102"})["release_year"],
            "2001",
        )

    def test_edits_can_clear_fields_and_invalid_year_is_rejected(self):
        self.assertEqual(
            normalize_tags({"title": "", "artist": ""}, {"track": "Song", "artist": "Artist"})[
                "title"
            ],
            "",
        )
        for year in ("0000", "98", "abcd", "2020-01-01"):
            with self.subTest(year=year), self.assertRaises(ValueError):
                normalize_tags({"year": year}, {})
        self.assertFalse(normalize_tags({"enabled": False, "year": "invalid"}, {})["enabled"])

    def test_artwork_urls_and_image_types_are_restricted(self):
        self.assertEqual(image_mime(cover_png()), "image/png")
        for url in (
            "http://i.ytimg.com/a.jpg",
            "https://localhost/a",
            "https://ytimg.com.evil.test/a",
            "https://user@i.ytimg.com/a",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_thumbnail_url(url)
        self.assertEqual(
            validate_thumbnail_url("https://i.ytimg.com/a.jpg"), "https://i.ytimg.com/a.jpg"
        )
        with self.assertRaises(ValueError):
            image_mime(b"<svg>not a supported image</svg>")


@unittest.skipUnless(TOOLS_AVAILABLE, "Fetch native runtime tools first")
class TagIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.engine = DownloadEngine(_worker_target=_wave_worker)

    def test_real_mp3_has_edited_unicode_tags_and_embedded_jpeg_separate_from_filename(self):
        result = self.engine.download(
            URL,
            directory=self.root,
            filename="Custom name",
            tags={
                "title": "Song 音楽",
                "artist": "Artist & Guest",
                "album": "Album",
                "year": "1998",
                "cover": "local",
            },
            cover_data=cover_png(),
        )
        tags = ID3(result.path, translate=False)
        self.assertEqual(tags.version, (2, 3, 0))
        for frame, value in (
            ("TIT2", "Song 音楽"),
            ("TPE1", "Artist & Guest"),
            ("TALB", "Album"),
            ("TYER", "1998"),
        ):
            self.assertEqual(str(tags[frame]), value)
        image = tags.getall("APIC")[0]
        self.assertEqual(image.mime, "image/jpeg")
        self.assertEqual(image.type, 3)
        self.assertTrue(image.data.startswith(b"\xff\xd8\xff"))
        self.assertGreater(MP3(result.path).info.length, 0)
        self.assertEqual(result.path.name, "Custom name.mp3")
        self.assertEqual(list(self.root.iterdir()), [result.path])
        embedded = self.root / "embedded-cover.jpg"
        embedded.write_bytes(image.data)
        decoded = subprocess.run(
            [
                str(tool_path("ffmpeg")),
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(embedded),
                "-frames:v",
                "1",
                "-vf",
                "scale=1:1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
        )
        red, green, blue = decoded.stdout[:3]
        self.assertGreater(red, 220)
        self.assertLess(green, 30)
        self.assertLess(blue, 30)

    def test_different_filenames_keep_identical_edited_title_tags_and_artwork(self):
        options = {
            "title": "Same song title",
            "artist": "Edited artist",
            "album": "Edited album",
            "year": "2004",
            "cover": "local",
        }
        outputs = [
            self.engine.download(
                URL, directory=self.root, filename=name, tags=options, cover_data=cover_png()
            )
            for name in ("First filename", "Completely different filename")
        ]
        first, second = [ID3(output.path, translate=False) for output in outputs]
        self.assertNotEqual(outputs[0].path.name, outputs[1].path.name)
        for frame, expected in (
            ("TIT2", "Same song title"),
            ("TPE1", "Edited artist"),
            ("TALB", "Edited album"),
            ("TYER", "2004"),
        ):
            self.assertEqual(str(first[frame]), expected)
            self.assertEqual(str(second[frame]), expected)
        self.assertEqual(first.getall("APIC")[0].data, second.getall("APIC")[0].data)
        self.assertGreater(MP3(outputs[1].path).info.length, 0)

    def test_cleared_tags_and_no_cover_are_not_replaced_by_defaults(self):
        result = self.engine.download(
            URL,
            directory=self.root,
            tags={"title": "Only a title", "artist": "", "album": "", "year": "", "cover": "none"},
        )
        tags = ID3(result.path, translate=False)
        self.assertEqual(str(tags["TIT2"]), "Only a title")
        for frame in ("TPE1", "TALB", "TYER", "APIC"):
            self.assertEqual(tags.getall(frame), [])

    def test_failed_download_retry_preserves_filename_tags_and_selected_cover(self):
        settings = SettingsStore(self.root / "settings.json")
        settings.set_download_directory(self.root / "audio")
        jobs = DesktopJobs(settings, self.engine)
        api = DesktopApi(jobs=jobs)
        api._window = Mock()
        self.engine.preview = Mock(
            return_value={"title": "Original video", "track": "Original song"}
        )
        api.preview_video(URL)
        jobs.wait(3)
        preview_id = jobs.snapshot()["preview_id"]
        image_path = self.root / "selected.png"
        image_path.write_bytes(cover_png())
        api._window.create_file_dialog.return_value = [str(image_path)]
        with patch.dict(
            "sys.modules", {"webview": SimpleNamespace(FileDialog=SimpleNamespace(OPEN=1))}
        ):
            selection = api.choose_cover()
        image_path.unlink()
        options = {
            "title": "Edited title",
            "artist": "Edited artist",
            "album": "Edited album",
            "year": "2004",
            "cover": "local",
        }
        retrieve = self.engine._retrieve
        calls = []

        def fail_once(*args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise DownloadError("Sign in to confirm you're not a bot")
            return retrieve(*args, **kwargs)

        try:
            with patch.object(self.engine, "_retrieve", side_effect=fail_once):
                api.start_download(URL, preview_id, "Edited filename", options)
                jobs.wait(10)
                failed = jobs.snapshot()
                self.assertEqual(failed["status"], "failed")
                self.assertEqual(failed["preview_id"], preview_id)
                self.assertEqual(failed["metadata"]["title"], "Original video")
                self.assertFalse(failed["busy"])
                self.assertEqual(list((self.root / "audio").iterdir()), [])
                with self.assertRaises(RuntimeError):
                    api.start_download(
                        "https://youtu.be/abcdefghijk", preview_id, "Edited filename", options
                    )
                api.start_download(URL, preview_id, "Edited filename", options)
                jobs.wait(10)
            completed = jobs.snapshot()
            self.assertEqual(completed["status"], "complete", completed)
            path = Path(completed["result"]["path"])
            self.assertEqual(path.name, "Edited filename.mp3")
            tags = ID3(path, translate=False)
            for frame, value in (
                ("TIT2", "Edited title"),
                ("TPE1", "Edited artist"),
                ("TALB", "Edited album"),
                ("TYER", "2004"),
            ):
                self.assertEqual(str(tags[frame]), value)
            self.assertTrue(tags.getall("APIC")[0].data.startswith(b"\xff\xd8\xff"))
            self.assertEqual(selection["name"], "selected.png")
            self.engine.preview.assert_called_once()
        finally:
            jobs.shutdown()
            jobs.wait(10)

    def test_disabled_tags_omit_id3_and_keep_audio_playable(self):
        result = self.engine.download(URL, directory=self.root, tags={"enabled": False})
        with self.assertRaises(ID3NoHeaderError):
            ID3(result.path)
        self.assertGreater(MP3(result.path).info.length, 0)

    def test_tagging_cancellation_and_bad_cover_do_not_publish_partial_files(self):
        cancel = threading.Event()
        with self.assertRaises(DownloadCancelled):
            self.engine.download(
                URL,
                directory=self.root,
                cancel=cancel,
                on_progress=lambda event: cancel.set() if event.stage == "tagging" else None,
            )
        self.assertEqual(list(self.root.iterdir()), [])
        with self.assertRaises(DownloadError):
            self.engine.download(
                URL,
                directory=self.root,
                tags={"cover": "local"},
                cover_data=b"\x89PNG\r\n\x1a\ninvalid",
            )
        self.assertEqual(list(self.root.iterdir()), [])

    def test_thumbnail_is_normalized_and_embedded(self):
        self.engine._worker_target = _wave_worker
        metadata = {"title": "Song", "thumbnail": "https://i.ytimg.com/a.webp"}
        original_retrieve = self.engine._retrieve

        def retrieve(*args, **kwargs):
            item = original_retrieve(*args, **kwargs)
            item["metadata"] = metadata
            return item

        with (
            patch.object(self.engine, "_retrieve", side_effect=retrieve),
            patch("ytmp3.engine.load_thumbnail", return_value=cover_png()) as fetch,
        ):
            result = self.engine.download(URL, directory=self.root)
        fetch.assert_called_once()
        self.assertTrue(ID3(result.path).getall("APIC"))
