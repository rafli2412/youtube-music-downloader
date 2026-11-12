#!/usr/bin/env python3
"""Verify the DMG by mounting read-only and installing into an isolated staging folder."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_installers import app_version  # noqa: E402


def verify(image: Path) -> dict:
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX", "DYLD_LIBRARY_PATH"):
        environment.pop(key, None)
    environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    environment["PYTHONNOUSERSITE"] = "1"
    subprocess.run(["/usr/bin/hdiutil", "verify", str(image)], check=True, capture_output=True)
    checks = {"image_integrity": True}
    with tempfile.TemporaryDirectory(prefix="install-check-", dir=ROOT / "build") as directory:
        root = Path(directory)
        mount = root / "mounted"
        mount.mkdir()
        subprocess.run(
            [
                "/usr/bin/hdiutil",
                "attach",
                "-readonly",
                "-nobrowse",
                "-mountpoint",
                str(mount),
                str(image),
            ],
            check=True,
            capture_output=True,
        )
        try:
            if (
                not (mount / "Applications").is_symlink()
                or os.readlink(mount / "Applications") != "/Applications"
            ):
                raise RuntimeError("The disk image is missing its Applications link.")
            checks["applications_link"] = True
            app = root / "Applications" / "YouTube Music Downloader.app"
            shutil.copytree(mount / app.name, app, symlinks=True)
            subprocess.run(
                [
                    "/usr/bin/codesign",
                    "--verify",
                    "--deep",
                    "--strict",
                    str(app),
                ],
                check=True,
                capture_output=True,
            )
            checks["copied_app_signature_integrity"] = True
            helper = mount / "Install terminal command.command"
            commands = root / "terminal commands"

            def run(arguments: list[str], *, success: bool = True):
                process = subprocess.run(
                    arguments,
                    cwd=root,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                if success and process.returncode != 0:
                    raise RuntimeError(f"Command failed: {process.stderr[-2000:]}")
                return process

            run(["/bin/sh", str(helper), "install", str(app), str(commands)])
            # A repeated setup must be harmless and must resolve all runtime resources.
            run(["/bin/sh", str(helper), "install", str(app), str(commands)])
            version = run([str(commands / "ytmp3"), "--version"])
            if version.stdout.strip() != f"ytmp3 {app_version()}":
                raise RuntimeError("The installed terminal link reported an unexpected version.")
            checks["terminal_helper_idempotent"] = True
            doctor = root / "doctor.json"
            run([str(commands / "ytmp3"), "doctor", "--report", str(doctor)])
            if not json.loads(doctor.read_text())["ok"]:
                raise RuntimeError(
                    "The installed CLI could not find or run its bundled dependencies."
                )
            checks["installed_cli_offline_engine"] = True
            desktop_report = root / "desktop.json"
            run(
                [
                    str(app / "Contents/MacOS/ytmp3-desktop"),
                    "--self-check",
                    "--report",
                    str(desktop_report),
                ]
            )
            if not json.loads(desktop_report.read_text())["ok"]:
                raise RuntimeError("The copied GUI bundle failed its offline check.")
            checks["copied_desktop_offline_engine"] = True
            run(["/bin/sh", str(helper), "remove", str(app), str(commands)])
            if (commands / "ytmp3").is_symlink():
                raise RuntimeError("The terminal link was not removed.")
            checks["owned_terminal_link_removed"] = True
            conflict = commands / "ytmp3"
            conflict.write_text("unrelated user command", encoding="utf-8")
            for operation in ("install", "remove"):
                process = run(
                    ["/bin/sh", str(helper), operation, str(app), str(commands)], success=False
                )
                if process.returncode == 0 or conflict.read_text() != "unrelated user command":
                    raise RuntimeError("The terminal helper did not preserve an unrelated command.")
            checks["unrelated_command_preserved"] = True
        finally:
            subprocess.run(
                ["/usr/bin/hdiutil", "detach", str(mount)], check=True, capture_output=True
            )
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "scope": (
            "Isolated read-only DMG/copy install, CLI helper and offline engine checks; "
            "no /Applications or shell-profile changes."
        ),
        "clean_machine_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "build/reports/install-macos.json")
    args = parser.parse_args()
    if platform.system() != "Darwin":
        parser.error("This verification requires macOS.")
    image = (
        args.image or ROOT / "dist" / f"youtube-music-downloader-{app_version()}-macos-arm64.dmg"
    )
    try:
        report = verify(image.resolve())
    except Exception as error:
        report = {"ok": False, "error": str(error), "clean_machine_verified": False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
