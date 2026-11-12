#!/usr/bin/env python3
"""Developer smoke check; default is offline, --url explicitly enables a live download."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from ytmp3.engine import DownloadEngine
    from ytmp3.engine_check import check_engine

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Download one public YouTube / YouTube Music URL")
    parser.add_argument("--directory", type=Path, help="Required output folder for a live download")
    args = parser.parse_args()
    if not args.url:
        print(json.dumps(check_engine(), indent=2))
        return 0
    if not args.directory:
        parser.error("--directory is required with --url")
    try:
        result = DownloadEngine().download(
            args.url,
            args.directory,
            on_progress=lambda event: print(
                json.dumps({"stage": event.stage, "fraction": event.fraction}), flush=True
            ),
        )
        print(json.dumps({"ok": True, "path": str(result.path), "title": result.title}))
        return 0
    except (ValueError, RuntimeError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
