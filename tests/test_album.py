"""Explicit album fallback, metadata precedence, and conservative ambiguity handling."""

import unittest

from ytmp3.album import description_album
from ytmp3.engine import video_metadata


class AlbumTests(unittest.TestCase):
    def test_explicit_english_and_indonesian_patterns(self):
        for description in (
            "Album: LAGIPULA HIDUP AKAN BERAKHIR",
            "album: “LAGIPULA HIDUP AKAN BERAKHIR”",
            "From the album “LAGIPULA HIDUP AKAN BERAKHIR”. Stream now!",
            'Taken from the album "LAGIPULA HIDUP AKAN BERAKHIR" released in 2023.',
            "Diambil dari album 'LAGIPULA HIDUP AKAN BERAKHIR'.",
            "Lagu ini merupakan bagian dari album “LAGIPULA HIDUP AKAN BERAKHIR”.",
        ):
            with self.subTest(description=description):
                self.assertEqual(description_album(description), "LAGIPULA HIDUP AKAN BERAKHIR")

    def test_repeated_equivalent_mentions_are_not_ambiguous(self):
        self.assertEqual(
            description_album("Album: My Album\nFrom the album “my album”."), "My Album"
        )

    def test_ambiguous_unbounded_and_unrelated_mentions_stay_blank(self):
        for description in (
            None,
            {},
            "",
            "LAGIPULA HIDUP AKAN BERAKHIR",
            "#Album #MyAlbum",
            "Listen to my favourite album “Other Album”",
            "From the album My Album released in 2023.",
            "Album: First\nAlbum: Second",
            "From the album “First” and “Second”.",
            "Diambil dari album “Pertama” atau “Kedua”.",
            "Album: https://example.com/album",
            "Album: #MyAlbum",
            'Album: "First" and "Second"',
            "Album: “Unclosed",
            "Not from the album “First”.",
            "Bukan diambil dari album “First”.",
            "Album: First\nFrom the album something uncertain.",
            "Album: First | Second",
            "Album:\nAn unrelated sentence",
            "From the album\nAn unrelated sentence",
            "Album: Stream now",
        ):
            with self.subTest(description=description):
                self.assertIsNone(description_album(description))

    def test_hindia_quoted_album_heading(self):
        heading = "▶️ ‘LAGIPULA HIDUP AKAN BERAKHIR’ Album"
        self.assertEqual(
            video_metadata({"description": heading})["album"],
            "LAGIPULA HIDUP AKAN BERAKHIR",
        )
        self.assertEqual(video_metadata({"description": heading})["album_source"], "description")
        self.assertIsNone(description_album(heading + "\nAlbum: A different album"))
        for unrelated in (
            "‘Some Album’ Album Playlist",
            "My favourite ‘Some Album’ Album",
            "‘Some Album’ Album review",
        ):
            self.assertIsNone(description_album(unrelated))

    def test_structured_album_wins_and_source_is_reported(self):
        result = video_metadata({"album": " Structured ", "description": "Album: Other"})
        self.assertEqual(result["album"], "Structured")
        self.assertEqual(result["album_source"], "metadata")
        result = video_metadata({"album": " ", "description": "Album: Description Album"})
        self.assertEqual(result["album"], "Description Album")
        self.assertEqual(result["album_source"], "description")
        result = video_metadata({"description": "Album: First\nAlbum: Second"})
        self.assertIsNone(result["album"])
        self.assertIsNone(result["album_source"])
        self.assertNotIn("description", result)
