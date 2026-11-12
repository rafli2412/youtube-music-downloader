"""Locate bundled resources without relying on the working directory or PATH."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from ytmp3 import APP_NAME, __version__


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def target_name() -> str:
    systems = {"Darwin": "macos", "Windows": "windows"}
    architectures = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}
    system = systems.get(platform.system(), platform.system().lower())
    architecture = architectures.get(platform.machine().lower(), platform.machine().lower())
    return f"{system}-{architecture}"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    if is_packaged():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return project_root()


def frontend_directory() -> Path:
    if is_packaged():
        return resource_root() / "frontend"
    return project_root() / "frontend" / "dist"


def tools_directory() -> Path:
    if is_packaged():
        return resource_root() / "runtime-tools"
    return project_root() / "vendor" / target_name()


def tool_path(name: str) -> Path:
    if name not in {"ffmpeg", "ffprobe", "deno"}:
        raise ValueError(f"Unknown runtime tool: {name}")
    suffix = ".exe" if platform.system() == "Windows" else ""
    return tools_directory() / f"{name}{suffix}"


def app_info() -> dict[str, str | bool]:
    return {
        "name": APP_NAME,
        "version": __version__,
        "platform": platform.system(),
        "architecture": platform.machine(),
        "packaged": is_packaged(),
    }
