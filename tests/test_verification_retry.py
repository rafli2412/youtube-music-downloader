"""Transient provider verification gets a bounded retry without account access."""

import unittest
from unittest.mock import patch

from yt_dlp.utils import DownloadError

from ytmp3.engine import _extract_audio


class VerificationRetryTests(unittest.TestCase):
    def test_preview_extracts_information_without_downloading_media(self):
        info = {"id": "abcdefghijk", "title": "Preview", "availability": "public"}
        with patch("yt_dlp.YoutubeDL") as factory:
            downloader = factory.return_value.__enter__.return_value
            downloader.extract_info.return_value = info
            downloader.prepare_filename.return_value = "unused.webm"
            _extract_audio("https://youtu.be/abcdefghijk", {}, download=False)
            downloader.extract_info.assert_called_once_with(
                "https://youtu.be/abcdefghijk", download=False
            )

    def test_transient_verification_retries_once_with_a_pause_and_fresh_downloader(self):
        info = {"id": "abcdefghijk", "title": "Audio", "availability": "public"}
        with patch("yt_dlp.YoutubeDL") as factory, patch("ytmp3.engine.time.sleep") as pause:
            downloader = factory.return_value.__enter__.return_value
            downloader.extract_info.side_effect = [
                DownloadError("Sign in to confirm you're not a bot"),
                info,
            ]
            downloader.prepare_filename.return_value = "source.wav"
            result, source = _extract_audio("https://youtu.be/abcdefghijk", {})
            self.assertEqual(result, info)
            self.assertEqual(source.name, "source.wav")
            self.assertEqual(factory.call_count, 2)
            pause.assert_called_once_with(10)

    def test_persistent_verification_stops_after_one_retry(self):
        with patch("yt_dlp.YoutubeDL") as factory, patch("ytmp3.engine.time.sleep") as pause:
            factory.return_value.__enter__.return_value.extract_info.side_effect = DownloadError(
                "Sign in to confirm you're not a bot"
            )
            with self.assertRaises(DownloadError):
                _extract_audio("https://youtu.be/abcdefghijk", {})
            self.assertEqual(factory.call_count, 2)
            pause.assert_called_once_with(10)

    def test_unavailable_content_is_not_retried(self):
        with patch("yt_dlp.YoutubeDL") as factory, patch("ytmp3.engine.time.sleep") as pause:
            factory.return_value.__enter__.return_value.extract_info.side_effect = DownloadError(
                "Private video"
            )
            with self.assertRaises(DownloadError):
                _extract_audio("https://youtu.be/abcdefghijk", {})
            self.assertEqual(factory.call_count, 1)
            pause.assert_not_called()
