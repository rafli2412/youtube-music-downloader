"""Supported paste formats and malformed inputs should stay single-video requests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ytmp3.urls import InvalidYouTubeURL, normalize_youtube_url

VIDEO_ID = "dQw4w9WgXcQ"
CANONICAL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


class YouTubeURLTests(unittest.TestCase):
    def test_supported_watch_hosts_and_schemes(self):
        for host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            for scheme in ("https", "http"):
                with self.subTest(host=host, scheme=scheme):
                    value = f"{scheme}://{host}/watch?v={VIDEO_ID}"
                    self.assertEqual(normalize_youtube_url(value), CANONICAL)

    def test_single_video_routes_and_short_links(self):
        for path in (f"shorts/{VIDEO_ID}", f"live/{VIDEO_ID}", f"embed/{VIDEO_ID}"):
            for suffix in ("", "/", "?feature=share"):
                with self.subTest(path=path, suffix=suffix):
                    self.assertEqual(
                        normalize_youtube_url(f"https://www.youtube.com/{path}{suffix}"),
                        CANONICAL,
                    )
        for suffix in ("", "/", "?si=tracking&t=30"):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    normalize_youtube_url(f"https://youtu.be/{VIDEO_ID}{suffix}"), CANONICAL
                )

    def test_video_in_playlist_still_normalizes_to_one_video(self):
        link = f"https://music.youtube.com/watch?v={VIDEO_ID}&list=PLAYLIST&index=2&si=tracking#t=5"
        self.assertEqual(normalize_youtube_url(link), CANONICAL)

    def test_surrounding_whitespace_case_and_standard_ports(self):
        self.assertEqual(
            normalize_youtube_url(f" \nHTTPS://WWW.YouTube.COM:443/watch?v={VIDEO_ID}\t"), CANONICAL
        )
        self.assertEqual(normalize_youtube_url(f"http://youtu.be:80/{VIDEO_ID}"), CANONICAL)
        self.assertEqual(
            normalize_youtube_url("https://youtu.be/abc_DEF-123"),
            "https://www.youtube.com/watch?v=abc_DEF-123",
        )

    def test_rejects_nonvideo_and_invalid_ids(self):
        for value in (
            "",
            " ",
            "https://youtube.com/",
            "https://youtube.com/playlist?list=example",
            "https://youtube.com/results?search_query=music",
            "https://youtube.com/@channel",
            "https://youtube.com/watch",
            "https://youtube.com/watch?v=",
            "https://youtu.be/short",
            "https://youtube.com/watch?v=aaaaaaaaaaaa",
            "https://youtube.com/watch?v=aaaaaaaaaa!",
            f"https://youtu.be/{VIDEO_ID}/extra",
            f"https://youtube.com/watch?v={VIDEO_ID}&v={VIDEO_ID}",
            f"https://youtube.com/watch?v={VIDEO_ID}&v=",
            f"https://youtu.be/{VIDEO_ID}?v=abcdefghijk",
        ):
            with self.subTest(value=value), self.assertRaises(InvalidYouTubeURL):
                normalize_youtube_url(value)

    def test_rejects_lookalikes_credentials_custom_ports_and_nonweb_links(self):
        for value in (
            f"https://youtube.com.evil.example/watch?v={VIDEO_ID}",
            f"https://evilyoutube.com/watch?v={VIDEO_ID}",
            f"https://youtube.com./watch?v={VIDEO_ID}",
            f"https://user:password@youtube.com/watch?v={VIDEO_ID}",
            f"https://@youtube.com/watch?v={VIDEO_ID}",
            f"https://youtube.com:444/watch?v={VIDEO_ID}",
            f"https://youtube.com:80/watch?v={VIDEO_ID}",
            f"https://youtube.com:invalid/watch?v={VIDEO_ID}",
            f"ftp://youtube.com/watch?v={VIDEO_ID}",
            f"youtube.com/watch?v={VIDEO_ID}",
            f"file:///watch?v={VIDEO_ID}",
            f"https://[youtube.com/watch?v={VIDEO_ID}",
        ):
            with self.subTest(value=value), self.assertRaises(InvalidYouTubeURL):
                normalize_youtube_url(value)

    def test_rejects_internal_whitespace_controls_and_multiple_links(self):
        for separator in (" ", "\n", "\r", "\t", "\x00", "\x7f"):
            with self.subTest(separator=repr(separator)), self.assertRaises(InvalidYouTubeURL):
                normalize_youtube_url(f"{CANONICAL}{separator}https://youtu.be/{VIDEO_ID}")

    def test_nonstring_input_is_a_validation_error(self):
        for value in (None, 12, [], {}):
            with self.subTest(value=value), self.assertRaises(InvalidYouTubeURL):
                normalize_youtube_url(value)


if __name__ == "__main__":
    unittest.main()
