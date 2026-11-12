#!/usr/bin/env python3
"""Build the desktop package on its native operating system and archive it."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from ytmp3.runtime import target_name

    target = target_name()
    if target not in {"macos-arm64", "windows-x64"}:
        raise SystemExit(f"Build on a supported native host; received {target}.")
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        raise SystemExit("Run npm ci --prefix frontend and npm run build --prefix frontend first.")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "fetch_tools.py"), "--verify"], check=True
    )
    environment = os.environ.copy()
    environment["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build" / ".pyinstaller-cache")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "packaging/desktop.spec"],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    distribution = ROOT / "dist"
    basename = distribution / f"youtube-music-downloader-{target}"
    if platform.system() == "Darwin":
        bundle = distribution / "YouTube Music Downloader.app"
        archive = basename.with_suffix(".tar.gz")
        # tar preserves executable modes and macOS framework symlinks.
        with tarfile.open(archive, "w:gz") as output:
            output.add(bundle, arcname=bundle.name)
    else:
        bundle = distribution / "YouTube Music Downloader"
        archive = Path(shutil.make_archive(str(basename), "zip", distribution, bundle.name))
    report = {
        "target": target,
        "python": platform.python_version(),
        "pyinstaller": importlib.metadata.version("pyinstaller"),
        "bundle": str(bundle.relative_to(ROOT)),
        "archive": str(archive.relative_to(ROOT)),
        "archive_bytes": archive.stat().st_size,
        "bundle_bytes": sum(
            path.stat().st_size
            for path in bundle.rglob("*")
            if path.is_file() and not path.is_symlink()
        ),
        "signed_for_distribution": False,
    }
    report_path = ROOT / "build" / "reports" / "package.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
