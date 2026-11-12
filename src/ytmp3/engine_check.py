"""Offline integration probe: exercise the engine using synthetic audio, never YouTube."""

from __future__ import annotations

import math
import os
import struct
import tempfile
import wave
from pathlib import Path
from typing import Any


def _probe_worker(connection: Any, url: str, directory: str, deno: str) -> None:
    if os.name != "nt":
        os.setsid()
    source = Path(directory) / "source.wav"
    with wave.open(str(source), "wb") as output:
        output.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        output.writeframes(
            b"".join(
                struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * index / 8000)))
                for index in range(800)
            )
        )
    connection.send(
        {"kind": "progress", "downloaded": source.stat().st_size, "total": source.stat().st_size}
    )
    connection.send(
        {
            "kind": "result",
            "source": str(source),
            "id": "BaW_jenozKc",
            "title": "Offline engine check",
        }
    )
    connection.close()


def check_engine() -> dict[str, Any]:
    from ytmp3.engine import DownloadEngine

    stages: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ytmp3-engine-check-") as directory:
        result = DownloadEngine(_worker_target=_probe_worker).download(
            "https://www.youtube.com/watch?v=BaW_jenozKc",
            directory,
            on_progress=lambda event: stages.append(event.stage),
        )
        return {
            "ok": result.path.is_file() and result.path.stat().st_size > 0,
            "source": "synthetic audio; no network access",
            "stages": stages,
            "output_bytes": result.path.stat().st_size,
        }
