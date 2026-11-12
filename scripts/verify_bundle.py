#!/usr/bin/env python3
"""Run the packaged app outside the project with development PATH entries removed."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def packaged_executable(*, cli: bool = False) -> Path:
    name = "ytmp3" if cli else "ytmp3-desktop"
    if platform.system() == "Darwin":
        return ROOT / "dist" / "YouTube Music Downloader.app" / "Contents" / "MacOS" / name
    if platform.system() == "Windows":
        return ROOT / "dist" / "YouTube Music Downloader" / f"{name}.exe"
    raise ValueError("Package verification supports Windows and macOS only.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--headless", action="store_true", help="Check dependencies and a real MP3 encode"
    )
    mode.add_argument(
        "--gui", action="store_true", help="Open a native window and wait for React/Python"
    )
    mode.add_argument(
        "--cli", action="store_true", help="Check the packaged terminal launcher and offline engine"
    )
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "reports" / "bundle.json")
    args = parser.parse_args(argv)
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Never accept a report left over from a previous execution.
    destination.unlink(missing_ok=True)
    executable = packaged_executable(cli=args.cli)
    if not executable.is_file():
        parser.error("The packaged executable is missing; run scripts/build_desktop.py first.")
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX", "DYLD_LIBRARY_PATH"):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    if os.name == "nt":
        windows = Path(environment.get("SystemRoot", r"C:\Windows"))
        environment["PATH"] = os.pathsep.join([str(windows / "System32"), str(windows)])
    else:
        environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    with tempfile.TemporaryDirectory(prefix="ytmp3-isolated-check-") as directory:
        try:
            options = {
                "cwd": directory,
                "env": environment,
                "capture_output": True,
                "text": True,
                "timeout": 90,
                "stdin": subprocess.DEVNULL,
            }
            if args.cli:
                version = subprocess.run([str(executable), "--version"], **options)
                help_result = subprocess.run([str(executable), "--help"], **options)
                doctor_report = Path(directory) / "doctor.json"
                process = subprocess.run(
                    [str(executable), "doctor", "--report", str(doctor_report)], **options
                )
                report = (
                    json.loads(doctor_report.read_text(encoding="utf-8"))
                    if doctor_report.is_file()
                    else {"ok": False, "error": "The packaged CLI did not write its doctor report"}
                )
                app_version = report.get("app", {}).get("version")
                report["cli_checks"] = {
                    "version": {
                        "ok": version.returncode == 0
                        and version.stdout.strip() == f"ytmp3 {app_version}",
                        "exit_code": version.returncode,
                        "stdout": version.stdout.strip(),
                    },
                    "help": {
                        "ok": help_result.returncode == 0 and "usage:" in help_result.stdout,
                        "exit_code": help_result.returncode,
                    },
                    "doctor": {"ok": process.returncode == 0, "exit_code": process.returncode},
                }
                report["ok"] = bool(report.get("ok")) and all(
                    check["ok"] for check in report["cli_checks"].values()
                )
            else:
                flag = "--self-check" if args.headless else "--smoke-test"
                process = subprocess.run(
                    [str(executable), flag, "--report", str(destination)], **options
                )
                report = (
                    json.loads(destination.read_text(encoding="utf-8"))
                    if destination.exists()
                    else {"ok": False, "error": "The packaged app did not write a report"}
                )
            report["exit_code"] = process.returncode
            if process.returncode != 0:
                report["stderr"] = process.stderr[-5000:]
                report["ok"] = False
        except subprocess.TimeoutExpired as error:
            report = {"ok": False, "error": f"Package verification timed out: {error}"}
    report["verification_mode"] = "cli" if args.cli else "headless" if args.headless else "gui"
    report["development_path_removed"] = True
    if not report.get("app", {}).get("packaged"):
        report["ok"] = False
        report["error"] = report.get("error", "The running app is not packaged")
    if args.gui and not report.get("bridge_round_trip"):
        report["ok"] = False
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
