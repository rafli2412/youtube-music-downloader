"""Read image representations explicitly supplied by a macOS paste/drop action."""

from __future__ import annotations

import platform

from ytmp3.tags import MAX_COVER_BYTES


def native_image(source: str) -> bytes:
    if source not in {"paste", "drop"}:
        raise ValueError("Choose paste or drop.")
    if platform.system() != "Darwin":
        raise ValueError("No image data was supplied. Copy the image itself or browse for a file.")
    from AppKit import (
        NSBitmapImageRep,
        NSDragPboard,
        NSImage,
        NSPasteboard,
        NSPasteboardTypePNG,
        NSPasteboardTypeTIFF,
        NSPNGFileType,
    )

    board = (
        NSPasteboard.generalPasteboard()
        if source == "paste"
        else NSPasteboard.pasteboardWithName_(NSDragPboard)
    )
    # Prefer bytes over URLs: a copied Google Images link is not an image.
    for kind in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
        data = board.dataForType_(kind)
        if data is not None:
            if len(data) > MAX_COVER_BYTES:
                raise ValueError("Cover images must be 10 MB or smaller.")
            bitmap = NSBitmapImageRep.imageRepWithData_(data)
            break
    else:
        image = NSImage.alloc().initWithPasteboard_(board)
        if image:
            size = image.size()
            if size.width * size.height > 40_000_000:
                raise ValueError("Cover images must contain 40 megapixels or fewer.")
            data = image.TIFFRepresentation()
            if data is not None and len(data) > MAX_COVER_BYTES:
                raise ValueError("Cover images must be 10 MB or smaller.")
            bitmap = NSBitmapImageRep.imageRepWithData_(data) if data is not None else None
        else:
            bitmap = None
    if bitmap is None:
        raise ValueError(
            "No image found. Use Copy Image rather than Copy Link, or browse for a file."
        )
    if bitmap.pixelsWide() * bitmap.pixelsHigh() > 40_000_000:
        raise ValueError("Cover images must contain 40 megapixels or fewer.")
    png = bitmap.representationUsingType_properties_(NSPNGFileType, {})
    if png is None or len(png) > MAX_COVER_BYTES:
        raise ValueError("Cover images must be 10 MB or smaller.")
    return bytes(png)
