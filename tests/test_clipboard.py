"""Native TIFF/PNG clipboard conversion without changing the user's clipboard."""

import platform
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ytmp3.clipboard import native_image


class ClipboardTests(unittest.TestCase):
    def appkit(self, data=b"tiff", width=2, height=2):
        bitmap = Mock()
        bitmap.pixelsWide.return_value = width
        bitmap.pixelsHigh.return_value = height
        bitmap.representationUsingType_properties_.return_value = b"converted png"
        board = Mock()
        board.dataForType_.side_effect = lambda kind: data if kind == "TIFF" else None
        kit = SimpleNamespace(
            NSBitmapImageRep=Mock(),
            NSImage=Mock(),
            NSPasteboard=Mock(),
            NSDragPboard="Apple CFPasteboard drag",
            NSPasteboardTypePNG="PNG",
            NSPasteboardTypeTIFF="TIFF",
            NSPNGFileType=4,
        )
        kit.NSBitmapImageRep.imageRepWithData_.return_value = bitmap
        kit.NSPasteboard.generalPasteboard.return_value = board
        kit.NSPasteboard.pasteboardWithName_.return_value = board
        return kit, board

    def test_tiff_paste_and_drop_are_converted_to_png(self):
        for source in ("paste", "drop"):
            kit, _ = self.appkit()
            with (
                patch("ytmp3.clipboard.platform.system", return_value="Darwin"),
                patch.dict("sys.modules", {"AppKit": kit}),
            ):
                self.assertEqual(native_image(source), b"converted png")
                if source == "drop":
                    kit.NSPasteboard.pasteboardWithName_.assert_called_once_with(
                        "Apple CFPasteboard drag"
                    )
                kit.NSBitmapImageRep.imageRepWithData_.assert_called_once_with(b"tiff")

    def test_missing_and_oversized_images_are_rejected(self):
        for size in ((10000, 10000),):
            kit, _ = self.appkit(width=size[0], height=size[1])
            with (
                patch("ytmp3.clipboard.platform.system", return_value="Darwin"),
                patch.dict("sys.modules", {"AppKit": kit}),
                self.assertRaises(ValueError),
            ):
                native_image("paste")
        kit, _ = self.appkit(data=None)
        kit.NSImage.alloc.return_value.initWithPasteboard_.return_value = None
        with (
            patch("ytmp3.clipboard.platform.system", return_value="Darwin"),
            patch.dict("sys.modules", {"AppKit": kit}),
            self.assertRaisesRegex(ValueError, "Copy Image"),
        ):
            native_image("paste")
        with self.assertRaises(ValueError):
            native_image("anything")

    @unittest.skipUnless(platform.system() == "Darwin", "macOS representation conversion")
    def test_real_appkit_tiff_conversion(self):
        from AppKit import NSBitmapImageRep, NSTIFFFileType
        from test_tags import cover_png

        bitmap = NSBitmapImageRep.imageRepWithData_(cover_png())
        tiff = bitmap.representationUsingType_properties_(NSTIFFFileType, {})
        board = Mock()
        board.dataForType_.side_effect = lambda kind: tiff if kind == "public.tiff" else None
        # Patch only the pasteboard accessor; real AppKit decodes TIFF and encodes PNG.
        import AppKit

        accessor = Mock()
        accessor.generalPasteboard.return_value = board
        with patch.object(AppKit, "NSPasteboard", accessor):
            png = native_image("paste")
        self.assertTrue(png.startswith(b"\x89PNG"))
        decoded = NSBitmapImageRep.imageRepWithData_(png)
        self.assertEqual((decoded.pixelsWide(), decoded.pixelsHigh()), (2, 2))
