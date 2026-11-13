"""Structured song fields stay distinct from video title and uploader identity."""

import unittest

from ytmp3.engine import video_metadata


class SongMetadataTests(unittest.TestCase):
    def test_track_artist_and_original_preview_fields_are_forwarded(self):
        result = video_metadata(
            {"title": "Video title", "channel": "Label", "track": " Song ", "artist": " Artist "}
        )
        self.assertEqual(result["track"], "Song")
        self.assertEqual(result["artist"], "Artist")
        self.assertEqual(result["title"], "Video title")
        self.assertEqual(result["channel"], "Label")

    def test_missing_or_invalid_music_fields_do_not_use_uploader_as_artist(self):
        result = video_metadata({"track": {}, "artist": [], "uploader": "Publisher"})
        self.assertIsNone(result["track"])
        self.assertIsNone(result["artist"])

    def test_multiple_artists_are_retained_when_singular_artist_is_missing(self):
        result = video_metadata({"artists": [" Artist A ", "Artist B", None, ""]})
        self.assertEqual(result["artist"], "Artist A, Artist B")
