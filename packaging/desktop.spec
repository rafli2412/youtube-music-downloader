# -*- mode: python ; coding: utf-8 -*-
"""Native one-folder package, including the React UI and conversion tools."""

import platform
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
target = "macos-arm64" if platform.system() == "Darwin" else "windows-x64"
tools = root / "vendor" / target
suffix = ".exe" if platform.system() == "Windows" else ""

datas = [(str(root / "frontend" / "dist"), "frontend")]
datas += collect_data_files("yt_dlp_ejs")
for package in ("yt-dlp", "yt-dlp-ejs", "pywebview"):
    datas += copy_metadata(package)
datas += [(str(path), "runtime-tools") for path in tools.iterdir() if path.suffix in {".txt", ".md", ".json"}]
binaries = [(str(tools / f"{name}{suffix}"), "runtime-tools") for name in ("ffmpeg", "ffprobe", "deno")]
native_backend = "webview.platforms.cocoa" if platform.system() == "Darwin" else "webview.platforms.edgechromium"

a = Analysis(
    [
        str(root / "packaging" / "desktop_entry.py"),
        str(root / "packaging" / "cli_entry.py"),
    ],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=[native_backend, "yt_dlp", "yt_dlp_ejs", "yt_dlp_ejs.yt.solver", "ytmp3.engine"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "tkinter", "gi", "cefpython3"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    [entry for entry in a.scripts if entry[0] != "cli_entry"],
    [],
    exclude_binaries=True,
    name="ytmp3-desktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch="arm64" if platform.system() == "Darwin" else None,
    codesign_identity=None,
    entitlements_file=None,
)
cli_exe = EXE(
    pyz,
    [entry for entry in a.scripts if entry[0] != "desktop_entry"],
    [],
    exclude_binaries=True,
    name="ytmp3",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    target_arch="arm64" if platform.system() == "Darwin" else None,
    codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(
    # Both launchers share one copy of Python, assets, and conversion tools. Keep
    # the GUI last so COLLECT/BUNDLE inherits its windowed application settings.
    cli_exe, exe, a.binaries, a.datas, strip=False, upx=False, name="YouTube Music Downloader",
)
if platform.system() == "Darwin":
    app = BUNDLE(
        collection,
        name="YouTube Music Downloader.app",
        bundle_identifier="com.rafli2412.youtubemusicdownloader",
        version="0.1.0",
        info_plist={
            "CFBundleDisplayName": "YouTube Music Downloader",
            # COLLECT sorts executable names; explicitly retain the GUI as the
            # Finder/Dock entry point while ytmp3 remains callable from a terminal.
            "CFBundleExecutable": "ytmp3-desktop",
            "LSBackgroundOnly": False,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "13.0",
        },
    )

