#!/usr/bin/env python3
"""Create a native DMG or per-user Windows setup from an existing desktop build."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import ssl
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fetch_tools import download_asset, install_asset, sha256_file  # noqa: E402


def app_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as source:
        return tomllib.load(source)["project"]["version"]


def build_dmg() -> Path:
    app = ROOT / "dist" / "YouTube Music Downloader.app"
    if not app.is_dir():
        raise RuntimeError("Build the native desktop app first: python scripts/build_desktop.py")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_macos_compatibility.py"), str(app)], check=True
    )
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    image = ROOT / "dist" / f"youtube-music-downloader-{app_version()}-macos-arm64.dmg"
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dmg-stage-", dir=ROOT / "build") as directory:
        staging = Path(directory) / "contents"
        staging.mkdir()
        temporary_image = Path(directory) / "installer.dmg"
        shutil.copytree(app, staging / app.name, symlinks=True)
        (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
        for source in (ROOT / "packaging" / "macos").iterdir():
            shutil.copy2(source, staging / source.name)
            if source.suffix == ".command":
                (staging / source.name).chmod(0o755)
        subprocess.run(
            [
                "/usr/bin/hdiutil",
                "create",
                "-volname",
                "YouTube Music Downloader",
                "-srcfolder",
                str(staging),
                "-format",
                "UDZO",
                "-fs",
                "HFS+",
                str(temporary_image),
            ],
            check=True,
        )
        subprocess.run(["/usr/bin/hdiutil", "verify", str(temporary_image)], check=True)
        temporary_image.replace(image)
    return image


def fetch_webview(ca_bundle: Path | None = None) -> Path:
    manifest = json.loads((ROOT / "packaging" / "prerequisites.json").read_text())
    asset = manifest["webview2"]
    target = ROOT / "vendor" / "installers" / asset["output"]
    if target.is_file() and sha256_file(target) == asset["sha256"]:
        return target
    context = ssl.create_default_context(cafile=str(ca_bundle) if ca_bundle else None)
    archive = download_asset(asset, ROOT / "vendor" / ".downloads", context)
    return install_asset(asset, archive, target.parent)


def build_windows(compiler: str | None = None, ca_bundle: Path | None = None) -> Path:
    app = ROOT / "dist" / "YouTube Music Downloader"
    if not (app / "ytmp3.exe").is_file() or not (app / "ytmp3-desktop.exe").is_file():
        raise RuntimeError("Build the native desktop app first: python scripts/build_desktop.py")
    compiler = compiler or shutil.which("ISCC.exe") or shutil.which("iscc")
    if not compiler:
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            for edition in ("Inno Setup 7", "Inno Setup 6"):
                candidate = (
                    Path(os.environ.get(variable, "C:/Program Files")) / edition / "ISCC.exe"
                )
                if candidate.is_file():
                    compiler = str(candidate)
                    break
            if compiler:
                break
    if not compiler:
        raise RuntimeError("Install Inno Setup 7 (or 6.3+) and pass --iscc with its ISCC.exe path.")
    bootstrapper = fetch_webview(ca_bundle)
    # Check the downloaded vendor signature as well as the committed checksum.
    signature_script = ROOT / "packaging" / "windows" / "verify_microsoft_signature.ps1"
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(signature_script),
            "-FilePath",
            str(bootstrapper),
        ],
        check=True,
    )
    subprocess.run(
        [
            compiler,
            f"/DAppVersion={app_version()}",
            f"/DSourceDir={app}",
            f"/DPrerequisiteDir={bootstrapper.parent}",
            f"/DOutputDir={ROOT / 'dist'}",
            f"/DWebViewSHA256={sha256_file(bootstrapper)}",
            str(ROOT / "packaging" / "windows" / "installer.iss"),
        ],
        check=True,
    )
    installer = ROOT / "dist" / f"youtube-music-downloader-{app_version()}-windows-x64-setup.exe"
    if not installer.is_file():
        raise RuntimeError("The installer compiler did not produce its expected output.")
    return installer


def write_checksums(paths: list[Path], destination: Path) -> None:
    destination.write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in paths), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", help="Windows: path to Inno Setup's ISCC.exe")
    parser.add_argument("--ca-bundle", type=Path, help="Optional trusted PEM bundle for downloads")
    args = parser.parse_args()
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin" and machine == "arm64":
        target, extension = "macos-arm64", "tar.gz"
        installer = build_dmg()
    elif system == "Windows" and machine in {"amd64", "x86_64"}:
        target, extension = "windows-x64", "zip"
        installer = build_windows(args.iscc, args.ca_bundle)
    else:
        raise SystemExit("Build installers on native Windows x64 or Apple Silicon macOS.")
    archive = ROOT / "dist" / f"youtube-music-downloader-{target}.{extension}"
    artifacts = [installer] + ([archive] if archive.is_file() else [])
    checksums = ROOT / "dist" / f"youtube-music-downloader-{app_version()}-{target}.SHA256SUMS"
    write_checksums(artifacts, checksums)
    report = {
        "target": target,
        "version": app_version(),
        "installer": str(installer.relative_to(ROOT)),
        "installer_bytes": installer.stat().st_size,
        "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
        "checksums": str(checksums.relative_to(ROOT)),
        "distribution_signed": False,
        "notarized": False,
        "windows_execution_verified": False,
    }
    output = ROOT / "build" / "reports" / "installers.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
