"""Phase-one CLI entry point. Download commands arrive in the following phases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ytmp3 import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ytmp3", description="YouTube Music Downloader — desktop foundation preview."
    )
    parser.add_argument("--version", action="version", version=f"ytmp3 {__version__}")
    commands = parser.add_subparsers(dest="command")
    gui = commands.add_parser("gui", help="Open the desktop app")
    gui.add_argument("--dev-url", help="Load the local React development server")
    doctor = commands.add_parser("doctor", help="Check bundled assets and runtime dependencies")
    doctor.add_argument("--report", type=Path, help="Also write a JSON report")
    args = parser.parse_args(argv)
    if args.command == "gui":
        from ytmp3.desktop import launch_desktop

        return launch_desktop(dev_url=args.dev_url)
    if args.command == "doctor":
        from ytmp3.diagnostics import collect_diagnostics, write_report

        report = collect_diagnostics()
        if args.report:
            write_report(args.report, report)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    parser.print_help()
    return 0
