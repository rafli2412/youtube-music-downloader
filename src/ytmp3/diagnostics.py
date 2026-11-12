"""Offline checks used to prove that the distribution contains its dependencies."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ytmp3.runtime import app_info, frontend_directory, tool_path


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # A failed/partial write must not look like a completed smoke test.
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_tool(
    name: str, arguments: list[str], timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    executable = tool_path(name)
    if not executable.is_file():
        raise FileNotFoundError(f"Bundled {name} is missing: {executable}")
    options: dict[str, Any] = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        [str(executable), *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
        **options,
    )


def collect_diagnostics() -> dict[str, Any]:
    report: dict[str, Any] = {"app": app_info(), "checks": {}, "ok": False}
    checks = report["checks"]

    frontend = frontend_directory()
    checks["frontend"] = {
        "ok": (frontend / "index.html").is_file() and any(frontend.glob("assets/*.js")),
        "path": str(frontend),
    }
    for package, module in (("yt-dlp", "yt_dlp"), ("yt-dlp-ejs", "yt_dlp_ejs")):
        try:
            loaded = importlib.import_module(module)
            version = importlib.metadata.version(package)
            details: dict[str, Any] = {"ok": True, "version": version}
            if module == "yt_dlp_ejs":
                package_path = Path(loaded.__file__).parent
                scripts = list(package_path.rglob("*.js"))
                details["scripts"] = len(scripts)
                details["ok"] = bool(scripts)
            checks[package] = details
        except Exception as error:
            checks[package] = {"ok": False, "error": str(error)}

    for name in ("ffmpeg", "ffprobe", "deno"):
        try:
            arguments = ["--version"] if name == "deno" else ["-version"]
            output = run_tool(name, arguments).stdout
            checks[name] = {"ok": True, "version": output.splitlines()[0]}
        except Exception as error:
            checks[name] = {"ok": False, "error": str(error)}

    try:
        execution = run_tool(
            "deno", ["eval", "--no-config", "--no-remote", "--no-npm", "console.log(6 * 7)"]
        )
        checks["javascript_execution"] = {"ok": execution.stdout.strip() == "42"}
    except Exception as error:
        checks["javascript_execution"] = {"ok": False, "error": str(error)}

    # Exercise the actual encoder/decoder, rather than merely finding executable files.
    try:
        with tempfile.TemporaryDirectory(prefix="ytmp3-package-check-") as directory:
            output = Path(directory) / "probe.mp3"
            run_tool(
                "ffmpeg",
                [
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=0.1",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "192k",
                    str(output),
                ],
            )
            probe = run_tool(
                "ffprobe",
                [
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=codec_name",
                    "-of",
                    "json",
                    str(output),
                ],
            )
            streams = json.loads(probe.stdout).get("streams", [])
            checks["mp3_conversion"] = {
                "ok": bool(streams) and streams[0].get("codec_name") == "mp3",
            }
    except Exception as error:
        checks["mp3_conversion"] = {"ok": False, "error": str(error)}

    report["ok"] = all(check["ok"] for check in checks.values())
    return report
